"""SDF raymarch -> per-pixel buffers (group id, light value, depth, normal).

Orthographic top-down 3/4 camera. The light is fixed in world space, the model is
rotated (yaw) for each of the 8 directions, so shading stays consistent.
"""
import numpy as np
from .sdf import norm, normalize


class Camera:
    def __init__(self, size=64, pitch=38.0, scale=0.048, center=(0, 1.0, 0), supersample=3, coverage=4, **_):
        self.size = int(size)
        self.ss = int(supersample)
        self.cover = int(coverage)
        self.pitch = np.radians(pitch)
        self.scale = float(scale)
        self.center = np.asarray(center, float)
        self.D = np.array([0.0, -np.sin(self.pitch), -np.cos(self.pitch)])
        self.R = np.array([1.0, 0.0, 0.0])
        self.U = np.array([0.0, np.cos(self.pitch), -np.sin(self.pitch)])

    @classmethod
    def from_spec(cls, spec):
        c = dict(spec['camera']); c['size'] = spec['size']
        return cls(**c)

    def project(self, P):
        q = np.asarray(P, float) - self.center
        return self.size / 2 + (q @ self.R) / self.scale, self.size / 2 - (q @ self.U) / self.scale


class Light:
    def __init__(self, dir=(-0.55, 1.0, 0.45), rim=(0.8, 0.35, -0.9), rim_strength=0.45, ambient=0.12,
                 shadows=True, ao=True, **_):
        self.L = normalize(dir); self.RIM = normalize(rim)
        self.rim_strength = rim_strength; self.ambient = ambient
        self.shadows = shadows; self.ao = ao


class Scene:
    def __init__(self, groups, yaw=0.0, offset=(0, 0, 0)):
        self.groups = groups
        c, s = np.cos(-yaw), np.sin(-yaw)
        self.Rwl = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])   # world -> local (about Y)
        self.Rlw = self.Rwl.T
        self.off = np.asarray(offset, float)
        self.solid_idx = [i for i, g in enumerate(groups) if not g.emissive]
        # whole-scene bounding sphere (world space)
        if groups:
            cs = np.array([g.bc for g in groups]); rs = np.array([g.br for g in groups])
            lo = (cs - rs[:, None]).min(0); hi = (cs + rs[:, None]).max(0)
            self.bc = self.Rlw @ ((lo + hi) / 2) + self.off
            self.br = np.linalg.norm(hi - lo) / 2
        else:
            self.bc = np.zeros(3); self.br = 0.0

    def to_local(self, p):
        return (p - self.off) @ self.Rwl.T

    def dist_all(self, p):
        q = self.to_local(p)
        return np.stack([g(q) for g in self.groups], 0)

    def dist(self, p):
        q = self.to_local(p)
        d = self.groups[0](q)
        for g in self.groups[1:]:
            d = np.minimum(d, g(q))
        return d

    def dist_solid(self, p):
        q = self.to_local(p)
        d = np.full(len(p), 1e3)
        for i in self.solid_idx:
            d = np.minimum(d, self.groups[i](q))
        return d


def march(scene, ro, rd, t0, tmax, steps=110, eps=0.0015):
    n = len(ro)
    t = t0.copy()
    hit = np.zeros(n, bool)
    active = np.nonzero(t < tmax)[0]
    for _ in range(steps):
        if active.size == 0:
            break
        p = ro[active] + rd[active] * t[active, None]
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
    for _ in range(steps):
        d = scene.dist_solid(P + L * t[:, None])
        res = np.minimum(res, 10 * d / t)
        t += np.clip(d, 0.02, 0.2)
    return np.clip(res, 0, 1)


def render(scene, cam, light):
    """Supersampled buffers: gid, val (0..1 light), depth, normal (world)."""
    S = cam.size; N = S * cam.ss
    o = (np.arange(N) + 0.5) / cam.ss
    px, py = np.meshgrid(o, o)
    u = (px - S / 2) * cam.scale
    v = (S / 2 - py) * cam.scale
    ro = cam.center + u.reshape(-1, 1) * cam.R + v.reshape(-1, 1) * cam.U - cam.D * 20
    rd = np.broadcast_to(cam.D, ro.shape).copy()
    # ray / bounding sphere -> skip empty space and rays that miss everything
    oc = ro - scene.bc
    b = oc @ cam.D
    c = (oc * oc).sum(-1) - scene.br ** 2
    disc = b * b - c
    miss = disc < 0
    sq = np.sqrt(np.maximum(disc, 0))
    t0 = np.maximum(-b - sq, 0)
    tmax = np.where(miss, -1.0, -b + sq)
    t, hit = march(scene, ro, rd, t0, tmax)
    gid = np.full(len(ro), -1)
    val = np.zeros(len(ro))
    nrm = np.zeros((len(ro), 3))
    P = ro[hit] + rd[hit] * t[hit, None]
    if len(P):
        D = scene.dist_all(P)
        g = D.argmin(0)
        gid[hit] = g
        e = 0.002
        n = np.zeros_like(P)
        for i in range(3):
            dv = np.zeros(3); dv[i] = e
            n[:, i] = scene.dist(P + dv) - scene.dist(P - dv)
        n /= np.maximum(norm(n)[:, None], 1e-9)
        two = np.array([gr.two_sided for gr in scene.groups])[g]
        flip = two & ((n @ cam.D) > 0)
        n[flip] *= -1
        if light.ao:
            ao = np.zeros(len(P)); w = 1.0
            for h in (0.04, 0.09, 0.16, 0.26):
                ao += w * np.clip(h - scene.dist_solid(P + n * h), 0, None)
                w *= 0.6
            ao = np.clip(1 - 3.2 * ao, 0, 1)
        else:
            ao = np.ones(len(P))
        sh = soft_shadow(scene, P + n * 0.01, light.L) if light.shadows else np.ones(len(P))
        wrap = np.clip((n @ light.L + 0.25) / 1.25, 0, 1)
        diff = wrap * (0.45 + 0.55 * sh)
        rim = np.clip(n @ light.RIM, 0, 1) * (1 - np.clip(-(n @ cam.D), 0, 1)) ** 2
        lv = light.ambient + 0.98 * diff * (0.62 + 0.38 * ao)
        lv = lv + light.rim_strength * rim * (wrap < 0.45)
        val[hit] = np.clip(lv, 0, 1)
        nrm[hit] = n
    depth = np.where(hit, t, np.inf)
    return gid.reshape(N, N), val.reshape(N, N), depth.reshape(N, N), nrm.reshape(N, N, 3)


def to_pixels(gid, val, depth, nrm, nG, cam):
    """Supersampled buffers -> size x size gid / val / depth / normal (majority coverage)."""
    S, k = cam.size, cam.ss

    def blk(a):
        sh = a.shape[2:]
        return a.reshape(S, k, S, k, *sh).swapaxes(1, 2).reshape(S, S, k * k, *sh)

    g, vv, dd, nn = blk(gid), blk(val), blk(depth), blk(nrm)
    out_g = np.full((S, S), -1); out_v = np.zeros((S, S)); out_d = np.full((S, S), np.inf)
    out_n = np.zeros((S, S, 3))
    hits = (g >= 0).sum(-1)
    if nG == 0:
        return out_g, out_v, out_d, out_n
    counts = np.stack([(g == j).sum(-1) for j in range(nG)], -1)
    best = counts.argmax(-1)
    filled = hits >= cam.cover
    m = (g == best[..., None]) & filled[..., None]
    cnt = np.maximum(m.sum(-1), 1)
    out_g[filled] = best[filled]
    out_v = np.where(filled, (vv * m).sum(-1) / cnt, 0)
    out_d = np.where(filled, np.where(m, dd, np.inf).min(-1), np.inf)
    ns = (nn * m[..., None]).sum(-2)
    ns /= np.maximum(np.linalg.norm(ns, axis=-1, keepdims=True), 1e-9)
    out_n = np.where(filled[..., None], ns, 0)
    return out_g, out_v, out_d, out_n
