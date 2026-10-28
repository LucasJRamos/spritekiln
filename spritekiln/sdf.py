"""Vectorized SDF primitives (numpy). p: (N,3) arrays.

Every primitive closure also carries `ir = (code, params)`: the numbers the compiled backend (scene_ir.py,
fast.py) reads, in the order its formula uses them. These closures stay the reference.
"""

import numpy as np

SPHERE, ELLIPSOID, CONE, BOX, CYLINDER, TORUS, TRI, PLANE, EXTRUDE, REVOLVE, TUBE, MOD = range(12)
P_CIRCLE, P_RECT, P_POLYGON, P_BEZIER = range(4)  # 2D profiles of extrude and revolve
SMOOTH, CHAMFER, ROUND, STAIRS, GROOVE = range(5)  # how a part joins its primitives and removes its cuts
BLENDS = {'smooth': SMOOTH, 'chamfer': CHAMFER, 'round': ROUND, 'stairs': STAIRS, 'groove': GROOVE}


def _r9(R):
    """A rotation as 9 numbers, row by row (identity when None)."""
    return tuple(float(v) for v in (np.eye(3) if R is None else np.asarray(R, float)).ravel())


def _ir(*values):
    return tuple(float(v) for v in np.concatenate([np.ravel(v) for v in values]))


def _dot(a, b):
    return np.einsum('ij,ij->i', a, b) if a.ndim == 2 and b.ndim == 2 else (a * b).sum(-1)


def norm(v):
    if v.ndim == 2 and v.shape[1] == 3:
        x, y, z = v[:, 0], v[:, 1], v[:, 2]
        return np.sqrt(x * x + y * y + z * z)
    return np.sqrt((v * v).sum(-1))


def normalize(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def cross3(a, b):
    """np.cross for two 3-vectors (same arithmetic, ~20x less overhead)."""
    a0, a1, a2 = float(a[0]), float(a[1]), float(a[2])
    b0, b1, b2 = float(b[0]), float(b[1]), float(b[2])
    return np.array([a1 * b2 - a2 * b1, a2 * b0 - a0 * b2, a0 * b1 - a1 * b0])


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
    f.ir = (SPHERE, _ir(c, r))
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
    f.ir = (ELLIPSOID, _ir(c, r) + _r9(R))  # q = (p - c) @ R
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
    f.ir = (CONE, _ir(a, b, r1, r2))
    return f


def triangle(a, b, c, th):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    c = np.asarray(c, float)
    ba = b - a
    cb = c - b
    ac = a - c
    nor = cross3(ba, ac)
    n_ba = cross3(ba, nor)
    n_cb = cross3(cb, nor)
    n_ac = cross3(ac, nor)
    dba = ba @ ba
    dcb = cb @ cb
    dac = ac @ ac
    dn = nor @ nor

    def f(p):
        pa = p - a
        pb = p - b
        pc = p - c
        s = np.sign(pa @ n_ba) + np.sign(pb @ n_cb) + np.sign(pc @ n_ac)
        e1 = ba * _clip01((pa @ ba) / dba)[:, None] - pa
        e2 = cb * _clip01((pb @ cb) / dcb)[:, None] - pb
        e3 = ac * _clip01((pc @ ac) / dac)[:, None] - pc
        edge = np.minimum(np.minimum((e1 * e1).sum(-1), (e2 * e2).sum(-1)), (e3 * e3).sum(-1))
        face = (pa @ nor) ** 2 / dn
        return np.sqrt(np.where(s < 2, edge, face)) - th

    cen = (a + b + c) / 3
    rad = max(np.linalg.norm(a - cen), np.linalg.norm(b - cen), np.linalg.norm(c - cen)) + th
    f.bound = (cen, rad)
    f.ir = (TRI, _ir(a, b, c, th))
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
    f.ir = (BOX, _ir(c, half) + _r9(R) + (float(round_),))  # q = (p - c) @ R
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
    f.ir = (CYLINDER, _ir(a, b, r, round_))
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
    f.ir = (TORUS, _ir(c, R_major, r_minor) + _r9(R))  # q = (p - c) @ R
    return f


def _clip01(x):
    return np.minimum(np.maximum(x, 0.0), 1.0)  # np.clip(x, 0, 1) without its Python-level overhead


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = _clip01(0.5 + 0.5 * (b - a) / k)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


# ---------------------------------------------------------------- joins (hg_sdf, Mercury; IQ for smooth)

SQRT_HALF = np.sqrt(0.5)


def _mod(x, y):
    return x - y * np.floor(x / y)  # GLSL mod: the result has the sign of y


def join(a, b, mode, k, n=1):
    """Union of two distances: smooth (IQ's smooth minimum), chamfer (a 45 degree bevel), round (a fillet) or
    stairs (n steps), each over a radius k."""
    if mode == SMOOTH or k <= 0:
        return smin(a, b, k)
    if mode == CHAMFER:
        return np.minimum(np.minimum(a, b), (a - k + b) * SQRT_HALF)
    if mode == ROUND:
        u0, u1 = np.maximum(k - a, 0), np.maximum(k - b, 0)
        return np.maximum(k, np.minimum(a, b)) - np.sqrt(u0 * u0 + u1 * u1)
    if mode == STAIRS:
        s = k / max(n, 1)
        u = b - k
        return np.minimum(np.minimum(a, b), 0.5 * (u + a + np.abs(_mod(u - a + s, 2 * s) - s)))
    raise ValueError(f'blend mode {mode} cannot join')


def carve(d, c, mode, k, n=1, groove=(0.0, 0.0)):
    """`d` minus the cutter `c`: smooth, chamfer, round or stairs over a radius k, or groove: a channel
    (depth, width) engraved where the cutter's surface crosses the part, which keeps its volume."""
    if mode == GROOVE:
        depth, width = groove
        return np.maximum(d, np.minimum(d + depth, width - np.abs(c)))
    if mode == SMOOTH or k <= 0:
        return smax(d, -c, k)
    return -join(-d, c, mode, k, n)


# ---------------------------------------------------------------- 2D profiles (extrude, revolve)


def _norm2(v):
    return np.sqrt(v[:, 0] * v[:, 0] + v[:, 1] * v[:, 1])


def circle(r):
    def f(q):
        return _norm2(q) - r

    f.radius = float(r)
    f.ir = (P_CIRCLE, float(r))
    return f


def rect(hx, hy, chamfer=0.0, round_=0.0):
    """A rectangle of half sizes hx, hy, its corners cut at 45 degrees (`chamfer`) or rounded (`round_`),
    keeping its size."""
    hx, hy, chamfer, round_ = float(hx), float(hy), float(chamfer), float(round_)

    def f(q):
        if chamfer > 0:  # IQ's sdChamferBox
            p0, p1 = np.abs(q[:, 0]) - hx, np.abs(q[:, 1]) - hy
            sw = p1 > p0
            x, y = np.where(sw, p1, p0), np.where(sw, p0, p1) + chamfer
            k = 1.0 - np.sqrt(2.0)
            corner = np.where(x < y, (x + y) * SQRT_HALF, np.sqrt(x * x + y * y))
            return np.where((y < 0) & (y + x * k < 0), x, corner)
        d0, d1 = np.abs(q[:, 0]) - (hx - round_), np.abs(q[:, 1]) - (hy - round_)
        o0, o1 = np.maximum(d0, 0), np.maximum(d1, 0)
        return np.sqrt(o0 * o0 + o1 * o1) + np.minimum(np.maximum(d0, d1), 0) - round_

    f.radius = float(np.hypot(hx, hy))
    f.ir = (P_RECT, hx, hy, chamfer, round_)
    return f


def polygon(pts, round_=0.0):
    """A closed polygon (any winding; IQ's sdPolygon). `round_` rounds its corners by growing it by that much."""
    v = np.asarray(pts, float).reshape(-1, 2)
    round_ = float(round_)

    def f(q):
        d = ((q - v[0]) ** 2).sum(-1)
        s = np.ones(len(q))
        for i in range(len(v)):
            j = i - 1
            e = v[j] - v[i]
            w = q - v[i]
            b = w - e * _clip01((w @ e) / (e @ e))[:, None]
            d = np.minimum(d, (b * b).sum(-1))
            c1 = q[:, 1] >= v[i, 1]
            c2 = q[:, 1] < v[j, 1]
            c3 = e[0] * w[:, 1] > e[1] * w[:, 0]
            s = np.where((c1 & c2 & c3) | (~c1 & ~c2 & ~c3), -s, s)
        return s * np.sqrt(d) - round_

    f.radius = float(np.sqrt((v * v).sum(-1)).max()) + round_
    f.ir = (P_POLYGON, float(len(v)), round_, *(float(x) for x in v.ravel()))
    return f


def _bezier(pos, A, B, C):
    """(distance, t) from points `pos` (n, 2 or 3) to the quadratic Bezier A-B-C (IQ's exact sdBezier)."""
    a = B - A
    b = A - 2.0 * B + C
    if b @ b < 1e-12:  # a straight segment
        ac = C - A
        t = _clip01(((pos - A) @ ac) / max(ac @ ac, 1e-12))
        e = A + t[:, None] * ac - pos
        return np.sqrt((e * e).sum(-1)), t
    c = a * 2.0
    d = A - pos
    kk = 1.0 / (b @ b)
    kx = kk * (a @ b)
    ky = kk * (2.0 * (a @ a) + d @ b) / 3.0
    kz = kk * (d @ a)
    p = ky - kx * kx
    q = kx * (2.0 * kx * kx - 3.0 * ky) + kz
    h = q * q + 4.0 * p * p * p

    def d2(t):
        e = d + (c + b * t[:, None]) * t[:, None]
        return (e * e).sum(-1)

    hs = np.sqrt(np.maximum(h, 0))
    t1 = _clip01(np.cbrt((hs - q) / 2.0) + np.cbrt((-hs - q) / 2.0) - kx)
    z = np.sqrt(np.maximum(-p, 0))
    pz = p * z * 2.0
    v = np.arccos(np.clip(q / np.where(pz != 0, pz, 1.0), -1, 1)) / 3.0
    m, n = np.cos(v), np.sin(v) * 1.732050808
    ta, tb = _clip01((m + m) * z - kx), _clip01((-n - m) * z - kx)
    da, db = d2(ta), d2(tb)
    one = h >= 0
    t = np.where(one, t1, np.where(db < da, tb, ta))
    dd = np.where(one, d2(t1), np.minimum(da, db))
    return np.sqrt(dd), t


def bezier_path(pts):
    """A closed path of quadratic Bezier segments: points P0, C0, P1, C1... (segment i runs from P_i through
    the control point C_i to P_i+1, the last one back to P0)."""
    v = np.asarray(pts, float).reshape(-1, 2)
    segs = [(v[i], v[i + 1], v[(i + 2) % len(v)]) for i in range(0, len(v), 2)]

    def f(q):
        d = np.full(len(q), np.inf)
        crossings = np.zeros(len(q), int)
        for A, B, C in segs:
            d = np.minimum(d, _bezier(q, A, B, C)[0])
            # even-odd rule: where y(t) = q.y on [0, 1), count the crossings to the right of q
            a2 = A[1] - 2 * B[1] + C[1]
            a1 = 2 * (B[1] - A[1])
            a0 = A[1] - q[:, 1]
            if abs(a2) < 1e-12:
                roots = [-a0 / a1] if abs(a1) > 1e-12 else []
                ok = [np.ones(len(q), bool)] * len(roots)
            else:
                disc = a1 * a1 - 4 * a2 * a0
                sq = np.sqrt(np.maximum(disc, 0))
                roots = [(-a1 - sq) / (2 * a2), (-a1 + sq) / (2 * a2)]
                ok = [disc >= 0, disc > 0]  # a double root (a tangent) counts once
            for t, good in zip(roots, ok):
                x = (1 - t) ** 2 * A[0] + 2 * (1 - t) * t * B[0] + t * t * C[0]
                crossings += good & (t >= 0) & (t < 1) & (x > q[:, 0])
        return np.where(crossings % 2 == 1, -d, d)

    f.radius = float(np.sqrt((v * v).sum(-1)).max())
    f.ir = (P_BEZIER, float(len(segs)), *(float(x) for x in v.ravel()))
    return f


# ---------------------------------------------------------------- shapes beyond rounded primitives


def plane(c, n):
    """The half-space on the side `n` points to, from the plane through `c`. Only as a cut: it is unbounded."""
    c = np.asarray(c, float)
    n = normalize(n)

    def f(p):
        return (c - p) @ n

    f.bound = None
    f.ir = (PLANE, _ir(c, n))
    return f


def extrude(c, R, profile, depth, round_=0.0):
    """A 2D profile in the local x-y plane pushed `depth` along local z (IQ's opExtrusion); `round_` rounds every
    edge, keeping the size. R: local -> world rotation."""
    c = np.asarray(c, float)
    R = np.eye(3) if R is None else np.asarray(R, float)
    h, round_ = float(depth) / 2, float(round_)

    def f(p):
        q = (p - c) @ R
        wx = profile(q[:, :2]) + round_
        wz = np.abs(q[:, 2]) - (h - round_)
        o0, o1 = np.maximum(wx, 0), np.maximum(wz, 0)
        return np.minimum(np.maximum(wx, wz), 0) + np.sqrt(o0 * o0 + o1 * o1) - round_

    f.bound = (c, float(np.hypot(profile.radius, h)))
    f.ir = (EXTRUDE, _ir(c) + _r9(R) + (h, round_) + tuple(float(x) for x in profile.ir))
    return f


def _wedge(x, z, a0, a1):
    """Signed distance in the local x-z plane to the angles a0..a1 (radians from +z towards +x; IQ's sdPie
    without a radius)."""
    m, half = (a0 + a1) / 2, (a1 - a0) / 2
    cm, sm = np.cos(m), np.sin(m)
    px = np.abs(x * cm - z * sm)
    py = z * cm + x * sm
    s0, c0 = np.sin(half), np.cos(half)
    t = np.maximum(px * s0 + py * c0, 0)
    dist = np.sqrt((px - s0 * t) ** 2 + (py - c0 * t) ** 2)
    return dist * np.sign(c0 * px - s0 * py)


def revolve(c, R, profile, offset=0.0, angle=None):
    """A 2D profile in the (radius, height) half-plane turned about local y (IQ's opRevolution); `offset` moves
    it away from the axis; `angle`: [a0, a1] radians from local +z towards +x for a partial turn."""
    c = np.asarray(c, float)
    R = np.eye(3) if R is None else np.asarray(R, float)
    offset = float(offset)
    a0, a1 = (float(angle[0]), float(angle[1])) if angle is not None else (0.0, 2 * np.pi)
    partial = a1 - a0 < 2 * np.pi - 1e-9

    def f(p):
        q = (p - c) @ R
        r = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - offset
        d = profile(np.stack([r, q[:, 1]], -1))
        return np.maximum(d, _wedge(q[:, 0], q[:, 2], a0, a1)) if partial else d

    f.bound = (c, profile.radius + offset)
    f.ir = (REVOLVE, _ir(c) + _r9(R) + (offset, a0, a1, float(partial)) + tuple(float(x) for x in profile.ir))
    return f


def tube_segments(pts):
    """Quadratic segments of a smooth path that starts at the first point, ends at the last and bends towards
    the others (a clamped quadratic B-spline: each inner point is a control point)."""
    P = np.asarray(pts, float).reshape(-1, 3)
    if len(P) == 3:
        return [(P[0], P[1], P[2])]
    segs, A = [], P[0]
    for i in range(1, len(P) - 1):
        C = P[-1] if i == len(P) - 2 else (P[i] + P[i + 1]) / 2
        segs.append((A, P[i], C))
        A = C
    return segs


def tube(pts, r0, r1=None):
    """A smooth round tube along `pts` (tube_segments), its radius going from r0 to r1."""
    r0 = float(r0)
    r1 = r0 if r1 is None else float(r1)
    segs = tube_segments(pts)
    ns = len(segs)

    def f(p):
        d = np.full(len(p), np.inf)
        for i, (A, B, C) in enumerate(segs):
            dist, t = _bezier(p, A, B, C)
            d = np.minimum(d, dist - (r0 + (r1 - r0) * (i + t) / ns))
        return d

    P = np.asarray(pts, float).reshape(-1, 3)
    cen = P.mean(0)
    f.bound = (cen, float(np.linalg.norm(P - cen, axis=1).max()) + max(r0, r1))
    length = sum(float(np.linalg.norm(B - A) + np.linalg.norm(C - B)) for A, B, C in segs)
    f.lipschitz = float(np.sqrt(1 + ((r1 - r0) / max(length, 1e-9)) ** 2))  # a taper is not an exact distance
    f.ir = (TUBE, (float(ns), r0, r1) + tuple(float(x) for seg in segs for pt in seg for x in pt))
    return f


def modified(f, c, R, shell=0.0, elongate=None, twist=0.0, bend=0.0):
    """A primitive changed in its frame (centre c, rotation R local -> world): twisted about local y (`twist`
    radians per unit), bent in the local x-y plane (`bend` radians per unit along x), stretched in the middle
    (`elongate`: half lengths added along local x, y, z; IQ's opElongate) and hollowed into a shell `shell`
    thick around its surface (opOnion)."""
    c = np.asarray(c, float)
    R = np.eye(3) if R is None else np.asarray(R, float)
    h = np.zeros(3) if elongate is None else np.abs(np.asarray(elongate, float))
    shell, twist, bend = float(shell), float(twist), float(bend)

    def g(p):
        q = (p - c) @ R
        if twist:
            a = twist * q[:, 1]
            ca, sa = np.cos(a), np.sin(a)
            q = np.stack([ca * q[:, 0] - sa * q[:, 2], q[:, 1], sa * q[:, 0] + ca * q[:, 2]], -1)
        if bend:
            a = bend * q[:, 0]
            ca, sa = np.cos(a), np.sin(a)
            q = np.stack([ca * q[:, 0] - sa * q[:, 1], sa * q[:, 0] + ca * q[:, 1], q[:, 2]], -1)
        if h.any():
            q = q - np.clip(q, -h, h)
        d = f(c + q @ R.T)
        return np.abs(d) - shell / 2 if shell else d

    bc, br = f.bound
    hn = float(np.linalg.norm(h))
    if twist or bend:  # a turn about an axis through c keeps distances to c
        g.bound = (c, float(np.linalg.norm(np.asarray(bc) - c)) + br + hn + shell / 2)
    else:
        g.bound = (np.asarray(bc), br + hn + shell / 2)
    reach = g.bound[1]
    # twisting or bending stretches space by up to sqrt(1 + (k * reach)^2): steps shrink to match
    stretch = np.sqrt(1 + (twist * reach) ** 2) * np.sqrt(1 + (bend * reach) ** 2)
    g.lipschitz = getattr(f, 'lipschitz', 1.0) * float(stretch)
    code, params = f.ir
    g.ir = (MOD, _ir(c) + _r9(R) + (twist, bend, *(float(x) for x in h), shell, float(code)) + tuple(params))
    return g


class Group:
    """A named part made of primitives joined (smoothly by default), optionally minus cutters."""

    def __init__(
        self,
        name,
        mat,
        prims,
        k=0.0,
        cut=None,
        ck=0.02,
        line=True,
        emissive=False,
        two_sided=False,
        mode=SMOOTH,
        n=1,
        cut_mode=SMOOTH,
        cut_n=1,
        groove=(0.0, 0.0),
        priority=1.0,
        min_cover=None,
    ):
        self.name = name
        self.priority, self.min_cover = float(priority), min_cover  # the pixel vote (render.to_gbuffer)
        self.paint = []  # paint.Layer list (design 09)
        self.frame = None  # (origin, rotation, scale) of the part's space: paint patterns, dithering
        self.mirror = False  # an automatic _R twin: its space is mirrored
        self.mat = mat
        self.prims = prims
        self.k = k
        self.cut = cut or []
        self.ck = ck
        self.line = line
        self.emissive = emissive
        self.two_sided = two_sided
        self.mode, self.n, self.cut_mode, self.cut_n, self.groove = mode, n, cut_mode, cut_n, tuple(groove)
        cs = [pr.bound for pr in prims]
        lo = np.min([c - r for c, r in cs], axis=0)
        hi = np.max([c + r for c, r in cs], axis=0)
        self.bc = (lo + hi) / 2
        # a sphere around the primitives' spheres (around their box it would be up to sqrt(3) too large);
        # k: a join bulges out by less than its radius
        self.br = max(float(np.linalg.norm(np.asarray(c) - self.bc)) + r for c, r in cs) + k + 0.01
        self.lipschitz = max(getattr(pr, 'lipschitz', 1.0) for pr in [*prims, *self.cut])

    def __call__(self, p, exact_within=0.05):
        """Distance from each point to the part. Where the bounding sphere is at least `exact_within` away (a
        scalar, or one value per point), the distance to that sphere instead: a lower bound, enough for
        stepping. Callers that read the value itself (soft shadows, AO) pass how close it can matter."""
        db = norm(p - self.bc) - self.br
        idx = np.flatnonzero(db < exact_within)
        if idx.size:
            q = p[idx]
            d = self.prims[0](q)
            for pr in self.prims[1:]:
                d = smin(d, pr(q), self.k) if self.mode == SMOOTH else join(d, pr(q), self.mode, self.k, self.n)
            for ct in self.cut:
                if self.cut_mode == SMOOTH:
                    d = smax(d, -ct(q), self.ck)
                else:
                    d = carve(d, ct(q), self.cut_mode, self.ck, self.cut_n, self.groove)
            db[idx] = d if self.lipschitz == 1.0 else d / self.lipschitz
        return db
