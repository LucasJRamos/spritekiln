"""Vectorized SDF primitives (numpy). p: (N,3) arrays."""

import numpy as np


def _dot(a, b):
    return np.einsum('ij,ij->i', a, b) if a.ndim == 2 and b.ndim == 2 else (a * b).sum(-1)


def norm(v):
    return np.sqrt((v * v).sum(-1))


def normalize(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def sphere(c, r):
    c = np.asarray(c, float)

    def f(p):
        return norm(p - c) - r

    f.bound = (c, r)
    return f


def ellipsoid(c, r, R=None):
    """R: rotation matrix (local->world). Approximate (iq) distance."""
    c = np.asarray(c, float)
    r = np.asarray(r, float)
    Rt = None if R is None else np.asarray(R).T

    def f(p):
        q = p - c
        if Rt is not None:
            q = q @ Rt.T  # world->local: q_local = R^T q  => q @ R
        k0 = norm(q / r)
        k1 = norm(q / (r * r))
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)

    f.bound = (c, r.max())
    return f


def round_cone(a, b, r1, r2):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    l2 = float(ba @ ba)
    if l2 < 1e-10:
        return sphere(a, max(r1, r2))
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2

    def f(p):
        pa = p - a
        y = pa @ ba
        z = y - l2
        w = pa * l2 - y[:, None] * ba
        x2 = (w * w).sum(-1)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        d1 = np.sqrt(x2 + z2) * il2 - r2
        d2 = np.sqrt(x2 + y2) * il2 - r1
        d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
        out = np.where(np.sign(y) * a2 * y2 < k, d2, d3)
        out = np.where(np.sign(z) * a2 * z2 > k, d1, out)
        return out

    f.bound = ((a + b) / 2, np.sqrt(l2) / 2 + max(r1, r2))
    return f


def triangle(a, b, c, th):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    c = np.asarray(c, float)
    ba = b - a
    cb = c - b
    ac = a - c
    nor = np.cross(ba, ac)
    n_ba = np.cross(ba, nor)
    n_cb = np.cross(cb, nor)
    n_ac = np.cross(ac, nor)
    dba = ba @ ba
    dcb = cb @ cb
    dac = ac @ ac
    dn = nor @ nor

    def f(p):
        pa = p - a
        pb = p - b
        pc = p - c
        s = np.sign(pa @ n_ba) + np.sign(pb @ n_cb) + np.sign(pc @ n_ac)
        e1 = ba * np.clip((pa @ ba) / dba, 0, 1)[:, None] - pa
        e2 = cb * np.clip((pb @ cb) / dcb, 0, 1)[:, None] - pb
        e3 = ac * np.clip((pc @ ac) / dac, 0, 1)[:, None] - pc
        edge = np.minimum(np.minimum((e1 * e1).sum(-1), (e2 * e2).sum(-1)), (e3 * e3).sum(-1))
        face = (pa @ nor) ** 2 / dn
        return np.sqrt(np.where(s < 2, edge, face)) - th

    cen = (a + b + c) / 3
    rad = max(np.linalg.norm(a - cen), np.linalg.norm(b - cen), np.linalg.norm(c - cen)) + th
    f.bound = (cen, rad)
    return f


def box(c, half, R=None, round_=0.0):
    """Rounded box. half: half-extents. R: local->world rotation."""
    c = np.asarray(c, float)
    half = np.asarray(half, float)
    RT = None if R is None else np.asarray(R)

    def f(p):
        q = p - c
        if RT is not None:
            q = q @ RT
        d = np.abs(q) - (half - round_)
        return norm(np.maximum(d, 0)) + np.minimum(d.max(-1), 0) - round_

    f.bound = (c, float(np.linalg.norm(half)))
    return f


def cylinder(a, b, r, round_=0.0):
    """Capped cylinder between a and b (optionally rounded edges)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    baba = float(ba @ ba)

    def f(p):
        pa = p - a
        paba = pa @ ba
        x = norm(pa * baba - paba[:, None] * ba) - (r - round_) * baba
        y = np.abs(paba - baba * 0.5) - baba * 0.5
        x2, y2 = x * x, y * y * baba
        d = np.where(np.maximum(x, y) < 0, -np.minimum(x2, y2), np.where(x > 0, x2, 0) + np.where(y > 0, y2, 0))
        return np.sign(d) * np.sqrt(np.abs(d)) / baba - round_

    f.bound = ((a + b) / 2, np.sqrt(baba) / 2 + r)
    return f


def torus(c, R_major, r_minor, R=None):
    """Torus lying in local XZ plane."""
    c = np.asarray(c, float)
    RT = None if R is None else np.asarray(R)

    def f(p):
        q = p - c
        if RT is not None:
            q = q @ RT
        qx = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - R_major
        return np.sqrt(qx**2 + q[:, 1] ** 2) - r_minor

    f.bound = (c, R_major + r_minor)
    return f


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


class Group:
    """A named part made of primitives smoothly unioned, optionally minus cutters."""

    def __init__(self, name, mat, prims, k=0.0, cut=None, ck=0.02, line=True, emissive=False, two_sided=False):
        self.name = name
        self.mat = mat
        self.prims = prims
        self.k = k
        self.cut = cut or []
        self.ck = ck
        self.line = line
        self.emissive = emissive
        self.two_sided = two_sided
        cs = [pr.bound for pr in prims]
        lo = np.min([c - r for c, r in cs], axis=0)
        hi = np.max([c + r for c, r in cs], axis=0)
        self.bc = (lo + hi) / 2
        self.br = np.linalg.norm(hi - lo) / 2 + k + 0.01

    def __call__(self, p):
        # cheap bounding-sphere skip
        db = norm(p - self.bc) - self.br
        out = db.copy()
        near = db < 0.05
        if near.any():
            q = p[near]
            d = self.prims[0](q)
            for pr in self.prims[1:]:
                d = smin(d, pr(q), self.k)
            for ct in self.cut:
                d = smax(d, -ct(q), self.ck)
            out[near] = d
        return out
