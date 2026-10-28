"""SDF raymarch -> per-ray samples -> a per-pixel geometry buffer -> the light value of each pixel.

Orthographic top-down 3/4 camera. The light is fixed in world space, the model is
rotated (yaw) for each of the 8 directions, so shading stays consistent.
"""

from typing import NamedTuple

import numpy as np

from .sdf import norm, normalize


class Camera:
    def __init__(self, size=64, pitch=38.0, scale=0.048, center=(0, 1.0, 0), supersample=3, coverage=None, **_):
        self.size = int(size)
        self.ss = max(1, int(supersample))
        # samples per pixel that must hit for it to fill: about 44% (4 of 9 at the default 3x3)
        self.cover = min(self.ss**2, int(coverage) if coverage else int(np.ceil(0.44 * self.ss**2)))
        self.pitch = np.radians(pitch)
        self.scale = float(scale)
        self.center = np.asarray(center, float)
        self.D = np.array([0.0, -np.sin(self.pitch), -np.cos(self.pitch)])
        self.R = np.array([1.0, 0.0, 0.0])
        self.U = np.array([0.0, np.cos(self.pitch), -np.sin(self.pitch)])

    @classmethod
    def from_spec(cls, spec):
        c = dict(spec['camera'])
        c['size'] = spec['size']
        return cls(**c)

    def project(self, P):
        q = np.asarray(P, float) - self.center
        return self.size / 2 + (q @ self.R) / self.scale, self.size / 2 - (q @ self.U) / self.scale


class Light:
    def __init__(
        self, dir=(-0.55, 1.0, 0.45), rim=(0.8, 0.35, -0.9), rim_strength=0.45, ambient=0.12, shadows=True, ao=True, **_
    ):
        self.L = normalize(dir)
        self.RIM = normalize(rim)
        self.rim_strength = rim_strength
        self.ambient = ambient
        self.shadows = shadows
        self.ao = ao


class Scene:
    def __init__(self, groups, yaw=0.0, offset=(0, 0, 0)):
        self.groups = groups
        c, s = np.cos(-yaw), np.sin(-yaw)
        self.Rwl = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])  # world -> local (about Y)
        self.Rlw = self.Rwl.T
        self.off = np.asarray(offset, float)
        self.solid_idx = [i for i, g in enumerate(groups) if not g.emissive]
        # whole-scene bounding sphere (world space)
        if groups:
            cs = np.array([g.bc for g in groups])
            rs = np.array([g.br for g in groups])
            lo = (cs - rs[:, None]).min(0)
            hi = (cs + rs[:, None]).max(0)
            centre = (lo + hi) / 2
            self.bc = self.Rlw @ centre + self.off
            self.br = float((np.linalg.norm(cs - centre, axis=1) + rs).max())
        else:
            self.bc = np.zeros(3)
            self.br = 0.0

    def to_local(self, p):
        return (p - self.off if self.off.any() else p) @ self.Rwl.T

    def dist_all(self, p):
        q = self.to_local(p)
        return np.stack([g(q) for g in self.groups], 0)

    def dist(self, p):
        q = self.to_local(p)
        d = self.groups[0](q)
        for g in self.groups[1:]:
            d = np.minimum(d, g(q))
        return d

    def dist_solid(self, p, exact_within=0.05):
        """Distance to the non-emissive parts; exact wherever it is below `exact_within` (see Group)."""
        q = self.to_local(p)
        d = np.full(len(p), 1e3)
        for i in self.solid_idx:
            d = np.minimum(d, self.groups[i](q, exact_within))
        return d


def march(scene, ro, rd, t0, tmax, steps=110, eps=0.0015):
    n = len(ro)
    t = t0.copy()
    hit = np.zeros(n, bool)
    active = np.nonzero(t < tmax)[0]
    for _ in range(steps):
        if active.size == 0:
            break
        p = ro[active] + rd[0] * t[active, None]  # orthographic: every ray has the same direction
        d = scene.dist(p)
        t[active] += d * 0.85
        h = d < eps
        hit[active[h]] = True
        keep = (~h) & (t[active] < tmax[active])
        active = active[keep]
    return t, hit


def soft_shadow(scene, P, L, steps=28):
    t = np.full(len(P), 0.04)
    res = np.ones(len(P))
    idx = np.arange(len(P))
    for _ in range(steps):
        if idx.size == 0:
            break
        ti = t[idx]
        # exact where it can matter: the penumbra term darkens below d = t / 10, the step changes below 0.2,
        # so a bounding sphere farther than both never shades (it used to: "phantom shadows")
        d = scene.dist_solid(P[idx] + L * ti[:, None], np.maximum(ti / 10, 0.2))
        r = np.minimum(res[idx], 10 * d / ti)
        res[idx] = r
        t[idx] = ti + np.clip(d, 0.02, 0.2)
        idx = idx[r > 0]
    return np.clip(res, 0, 1)


def camera_rays(cam):
    """Origins of the supersampled camera rays, row by row (every ray goes along cam.D)."""
    S = cam.size
    N = S * cam.ss
    o = (np.arange(N) + 0.5) / cam.ss
    px, py = np.meshgrid(o, o)
    u = (px - S / 2) * cam.scale
    v = (S / 2 - py) * cam.scale
    return cam.center + u.reshape(-1, 1) * cam.R + v.reshape(-1, 1) * cam.U - cam.D * 20


class Samples(NamedTuple):
    """The supersampled rays of a frame (cam.size * cam.ss squared): what a backend's render returns."""

    gid: np.ndarray  # [N, N] int: the nearest group, -1 for background
    depth: np.ndarray  # [N, N] ray distance, inf for background
    normal: np.ndarray  # [N, N, 3] world normal
    shadow: np.ndarray  # [N, N] soft shadow towards the light, 0..1 (1 = lit)
    ao: np.ndarray  # [N, N] ambient occlusion, 0..1 (1 = open)


class GBuffer(NamedTuple):
    """A frame per output pixel, after the coverage vote: the geometry the render cache keeps. Light, materials,
    palette and style are applied to it in 2D (shade, then pixelize.compose)."""

    gid: np.ndarray  # [S, S] int16, -1 for background
    depth: np.ndarray  # [S, S] float32
    normal: np.ndarray  # [S, S, 3] float16, averaged over the winner's samples
    shadow: np.ndarray  # [S, S] uint8, 255 = lit
    ao: np.ndarray  # [S, S] uint8, 255 = open
    cover: np.ndarray  # [S, S] uint8: how many samples the winner had
    paint: np.ndarray  # [S, S] int16: the paint layer (paint.layers_of order) of the pixel, -1 for none


def render(scene, cam, light):
    """Samples of a frame: per ray, the nearest group, depth, normal, soft shadow and AO. The numpy reference;
    fast.render is the compiled one (backend.py picks)."""
    S = cam.size
    N = S * cam.ss
    ro = camera_rays(cam)
    rd = np.broadcast_to(cam.D, ro.shape).copy()
    # ray / bounding sphere -> skip empty space and rays that miss everything
    oc = ro - scene.bc
    b = oc @ cam.D
    c = (oc * oc).sum(-1) - scene.br**2
    disc = b * b - c
    miss = disc < 0
    sq = np.sqrt(np.maximum(disc, 0))
    t0 = np.maximum(-b - sq, 0)
    tmax = np.where(miss, -1.0, -b + sq)
    if scene.groups:
        C = np.array([scene.Rlw @ g.bc + scene.off for g in scene.groups])
        BR = np.array([g.br for g in scene.groups])
        never = np.ones(len(ro), bool)
        for c, br in zip(C, BR):  # perpendicular distance from each (parallel) ray to the sphere centre
            w = c - ro
            h = norm(w - (w @ cam.D)[:, None] * cam.D) - br
            never &= h >= 0.05 + 1e-6
        tmax = np.where(never, -1.0, tmax)
    t, hit = march(scene, ro, rd, t0, tmax)
    gid = np.full(len(ro), -1)
    nrm = np.zeros((len(ro), 3))
    shadow = np.ones(len(ro))
    occl = np.ones(len(ro))
    P = ro[hit] + rd[hit] * t[hit, None]
    if len(P):
        D = scene.dist_all(P)
        g = D.argmin(0)
        gid[hit] = g
        e = 0.002
        n = np.zeros_like(P)
        for i in range(3):
            dv = np.zeros(3)
            dv[i] = e
            n[:, i] = scene.dist(P + dv) - scene.dist(P - dv)
        n /= np.maximum(norm(n)[:, None], 1e-9)
        two = np.array([gr.two_sided for gr in scene.groups])[g]
        flip = two & ((n @ cam.D) > 0)
        n[flip] *= -1
        if light.ao:
            ao = np.zeros(len(P))
            w = 1.0
            for h in (0.04, 0.09, 0.16, 0.26):  # a part at least h away does not occlude: exact below h
                ao += w * np.clip(h - scene.dist_solid(P + n * h, h), 0, None)
                w *= 0.6
            occl[hit] = np.clip(1 - 3.2 * ao, 0, 1)
        if light.shadows:
            shadow[hit] = soft_shadow(scene, P + n * 0.01, light.L)
        nrm[hit] = n
    depth = np.where(hit, t, np.inf)
    return Samples(
        gid.reshape(N, N), depth.reshape(N, N), nrm.reshape(N, N, 3), shadow.reshape(N, N), occl.reshape(N, N)
    )


def to_gbuffer(samples, nG, cam, weight=None, min_cover=None, paint=None):
    """Samples -> GBuffer (size x size): a pixel is filled when enough samples hit (cam.cover) and goes to the
    group with the most samples; depth is the winner's nearest, normal, shadow and AO the winner's average.
    `weight`: per group, how much each of its samples counts in the vote (a part's `priority`); `min_cover`: per
    group, how many of its samples fill a pixel even below the camera's coverage (thin weapons, antennae).
    `paint`: per sample (paint.surface); a pixel's paint is the majority of the winner's samples."""
    S, k = cam.size, cam.ss

    def blk(a):
        sh = a.shape[2:]
        return a.reshape(S, k, S, k, *sh).swapaxes(1, 2).reshape(S, S, k * k, *sh)

    g, dd, nn, ss, aa = (blk(a) for a in samples)
    out_g = np.full((S, S), -1)
    hits = (g >= 0).sum(-1)
    if nG == 0:
        filled = np.zeros((S, S), bool)
        m = np.zeros(g.shape, bool)
    else:
        counts = np.stack([(g == j).sum(-1) for j in range(nG)], -1)
        best = (counts if weight is None else counts * weight).argmax(-1)
        filled = hits >= cam.cover
        if min_cover is not None:
            filled |= (counts >= min_cover).any(-1)
        m = (g == best[..., None]) & filled[..., None]
        out_g[filled] = best[filled]
    cnt = m.sum(-1)
    c1 = np.maximum(cnt, 1)
    ns = (nn * m[..., None]).sum(-2)
    ns /= np.maximum(np.linalg.norm(ns, axis=-1, keepdims=True), 1e-9)

    def unit(a):  # a 0..1 average as 0..255
        return np.where(filled, np.round((a * m).sum(-1) / c1 * 255), 255).astype(np.uint8)

    out_p = np.full((S, S), -1, np.int16)
    if paint is not None:
        pp = blk(paint)
        ids = [int(i) for i in np.unique(pp[m]) if i >= 0]
        if ids:
            votes = np.stack([((pp == i) & m).sum(-1) for i in [-1, *ids]], -1)
            out_p = np.array([-1, *ids], np.int16)[votes.argmax(-1)]
            out_p[~filled] = -1

    return GBuffer(
        out_g.astype(np.int16),
        np.where(filled, np.where(m, dd, np.inf).min(-1), np.inf).astype(np.float32),
        np.where(filled[..., None], ns, 0).astype(np.float16),
        unit(ss),
        unit(aa),
        cnt.astype(np.uint8),
        out_p,
    )


def facing(gb, cam, light):
    """n.h per pixel (Blinn-Phong): 1 where the surface faces halfway between the light and the camera."""
    h = normalize(np.asarray(light.L, float) - cam.D)
    return np.where(gb.gid >= 0, gb.normal.astype(np.float64) @ h, -1.0)


def shade(gb, cam, light, rim=None):
    """The light value (0..1) of each pixel of a GBuffer: wrap diffuse darkened by the soft shadow and AO, plus a
    rim light on the shadow side (`rim`: its strength per pixel; default the light's). 0 for background."""
    n = gb.normal.astype(np.float64)
    sh = gb.shadow / 255.0
    ao = gb.ao / 255.0
    wrap = np.clip((n @ light.L + 0.25) / 1.25, 0, 1)
    diff = wrap * (0.45 + 0.55 * sh)
    rim_light = np.clip(n @ light.RIM, 0, 1) * (1 - np.clip(-(n @ cam.D), 0, 1)) ** 2
    lv = light.ambient + 0.98 * diff * (0.62 + 0.38 * ao)
    lv = lv + (light.rim_strength if rim is None else rim) * rim_light * (wrap < 0.45)
    return np.where(gb.gid >= 0, np.clip(lv, 0, 1), 0.0)
