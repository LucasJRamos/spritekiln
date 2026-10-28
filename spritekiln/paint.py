"""Surface paint (design 09): colour regions on a part without new geometry.

A part's `paint:` layers recolour the surface points that ray marching hit: a volume (primitives, the surface
inside them is painted) or a pattern in the part's own coordinates (stripes, rings, a grid of dots, noise
spots, a checker), so it moves with the bone and stays put from frame to frame. Later layers win. Paint is
evaluated only on hit samples, after either backend, and voted per pixel like the parts.
"""

import numpy as np

AXES = {'x': 0, 'y': 1, 'z': 2}
PATTERNS = ('prims', 'stripes', 'rings', 'grid', 'spots', 'checker')


class Layer:
    """One paint layer of a part: `mask(p_model, q_local)` -> bool per point."""

    def __init__(self, material, mask, edge=False, thin=None):
        self.material = material
        self.mask = mask
        self.edge = bool(edge)  # a 1 px line where this paint meets another region of the part
        self.thin = thin  # its narrowest width, for validate's one-pixel warning


def _band(c, width, period=None, at=None, offset=0.0):
    if at is not None:
        at = np.atleast_1d(np.asarray(at, float))
        return np.abs(c[:, None] - at[None]).min(1) <= width / 2
    return np.mod(c - offset, period) < width


def stripes(axis='y', width=0.04, period=None, at=None, offset=0.0):
    a = AXES[axis]
    return lambda p, q: _band(q[:, a], width, period, at, offset)


def rings(axis='y', width=0.04, period=None, at=None, offset=0.0):
    """Concentric bands by distance from the part's `axis` (a target on a shield, the end of a log); a band
    around an arm or a column at some height is `stripes` along that axis."""
    others = [i for i in range(3) if i != AXES[axis]]
    return lambda p, q: _band(np.sqrt(q[:, others[0]] ** 2 + q[:, others[1]] ** 2), width, period, at, offset)


def grid(axes=('x', 'y'), spacing=(0.1, 0.1), r=0.015, offset=(0.0, 0.0)):
    """Dots of radius r on a lattice over two axes (rivets, studs)."""
    a, b = (AXES[x] for x in axes)
    sx, sy = (float(v) for v in spacing)
    ox, oy = (float(v) for v in offset)

    def mask(p, q):
        dx = np.mod(q[:, a] - ox + sx / 2, sx) - sx / 2
        dy = np.mod(q[:, b] - oy + sy / 2, sy) - sy / 2
        return dx * dx + dy * dy <= r * r

    return mask


def _hash(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0x1000000)


def noise3(q, seed=0):
    """Smooth value noise in 0..1 at points (n, 3), deterministic for a seed."""
    f = np.floor(q)
    t = q - f
    t = t * t * (3 - 2 * t)
    i = f.astype(np.int64)
    out = np.zeros(len(q))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (
                    (t[:, 0] if dx else 1 - t[:, 0])
                    * (t[:, 1] if dy else 1 - t[:, 1])
                    * (t[:, 2] if dz else 1 - t[:, 2])
                )
                out += w * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out


def spots(scale=0.1, density=0.3, seed=0):
    """Noise blotches about `scale` across covering about `density` of the surface (stains, moss, freckles)."""
    return lambda p, q: noise3(q / scale, int(seed)) > 1 - density


def checker(size=0.1):
    return lambda p, q: (np.floor(q / size).astype(np.int64).sum(-1) % 2) == 0


def volume(prims):
    """The surface inside any of these primitives (built in the part's space, like its own)."""
    return lambda p, q: np.min([f(p) for f in prims], 0) <= 0


def surface(scene, cam, samples):
    """The paint layer that colours each sample's hit: its index in the order of the groups' `paint` lists, all
    groups together (paint.layers_of); -1 for none."""
    from .render import camera_rays

    gid = samples.gid.reshape(-1)
    hit = np.flatnonzero(gid >= 0)
    paint = np.full(gid.shape, -1, np.int16)
    if hit.size == 0 or not layers_of(scene.groups):
        return paint.reshape(samples.gid.shape)
    ro = camera_rays(cam)[hit]
    P = scene.to_local(ro + cam.D * samples.depth.reshape(-1)[hit, None])  # model space
    first = 0
    for g_index, g in enumerate(scene.groups):
        layers = getattr(g, 'paint', None) or []
        sel = gid[hit] == g_index if layers else None
        if layers and g.frame is not None and sel.any():
            o, R, s = g.frame
            q = ((P[sel] - o) @ R) / s
            if g.mirror:  # the _R twin's space is mirrored: its patterns too
                q[:, 0] = -q[:, 0]
            for li, layer in enumerate(layers):
                on = layer.mask(P[sel], q)
                paint[hit[sel][on]] = first + li
        first += len(layers)
    return paint.reshape(samples.gid.shape)


def layers_of(groups):
    """Every paint layer of a frame's groups, in the order `surface` numbers them."""
    return [layer for g in groups for layer in (getattr(g, 'paint', None) or [])]
