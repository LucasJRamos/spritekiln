"""The compiled backend (`spritekiln[fast]`): one numba kernel that renders a frame's buffers from a SceneIR.

It mirrors render.render (the numpy reference) formula by formula: the same rays, ray marching, nearest part,
6-tap normals, AO, soft shadows and light. Each camera ray, AO tap set and shadow ray evaluates only the parts
whose bounding sphere comes near it, with margins that keep every distance that can change a pixel exact; the
only difference left is where ray marching stops, within its epsilon, when a far part no longer shortens a
step (a handful of pixels per frame). ADR-029 has the measurements.

Importing this module imports numba; `available()` says whether that works.
"""

import math
import os
import sys

import numpy as np


def _cache_dir():
    """Where numba keeps the compiled kernel between runs: a user folder (the package may be read-only)."""
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~\\AppData\\Local')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Caches')
    else:
        base = os.environ.get('XDG_CACHE_HOME') or os.path.expanduser('~/.cache')
    return os.path.join(base, 'spritekiln', 'numba')


os.environ.setdefault('NUMBA_CACHE_DIR', _cache_dir())

from numba import njit, prange  # noqa: E402

from .scene_ir import compile_scene  # noqa: E402
from .sdf import (  # noqa: E402
    BOX,
    CHAMFER,
    CONE,
    CYLINDER,
    ELLIPSOID,
    EXTRUDE,
    GROOVE,
    MOD,
    P_CIRCLE,
    P_POLYGON,
    P_RECT,
    PLANE,
    REVOLVE,
    ROUND,
    SMOOTH,
    SPHERE,
    TORUS,
    TUBE,
)

SQRT_HALF = math.sqrt(0.5)

ONE = np.uint64(1)


def compiled_before():
    """True when a previous run left the compiled kernel in the cache (no compile pause this time)."""
    folder = os.environ['NUMBA_CACHE_DIR']
    for _, _, files in os.walk(folder):
        if any(f.startswith('fast.') and f.endswith('.nbi') for f in files):
            return True
    return False


# ---------------------------------------------------------------- distances


@njit(cache=True)
def _clip01(x):
    return min(max(x, 0.0), 1.0)


@njit(cache=True)
def _sgn(x):
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


@njit(cache=True)
def _smin(a, b, k):
    if k <= 0:
        return min(a, b)
    h = _clip01(0.5 + 0.5 * (b - a) / k)
    return b * (1 - h) + a * h - k * h * (1 - h)


@njit(cache=True)
def _local(P, o, x, y, z):
    """(p - c) @ R with c = P[o:o+3] and R = P[o+3:o+12] row by row."""
    px, py, pz = x - P[o], y - P[o + 1], z - P[o + 2]
    return (
        px * P[o + 3] + py * P[o + 6] + pz * P[o + 9],
        px * P[o + 4] + py * P[o + 7] + pz * P[o + 10],
        px * P[o + 5] + py * P[o + 8] + pz * P[o + 11],
    )


@njit(cache=True)
def base(code, P, o, x, y, z):
    """Distance from (x, y, z) to primitive `code` whose parameters start at P[o] (layouts: sdf.py `ir`)."""
    if code == SPHERE:
        dx, dy, dz = x - P[o], y - P[o + 1], z - P[o + 2]
        return math.sqrt(dx * dx + dy * dy + dz * dz) - P[o + 3]
    if code == ELLIPSOID:  # c, r, R
        px, py, pz = x - P[o], y - P[o + 1], z - P[o + 2]
        qx = px * P[o + 6] + py * P[o + 9] + pz * P[o + 12]
        qy = px * P[o + 7] + py * P[o + 10] + pz * P[o + 13]
        qz = px * P[o + 8] + py * P[o + 11] + pz * P[o + 14]
        rx, ry, rz = P[o + 3], P[o + 4], P[o + 5]
        k0 = math.sqrt((qx / rx) ** 2 + (qy / ry) ** 2 + (qz / rz) ** 2)
        k1 = math.sqrt((qx / (rx * rx)) ** 2 + (qy / (ry * ry)) ** 2 + (qz / (rz * rz)) ** 2)
        return k0 * (k0 - 1.0) / max(k1, 1e-9)
    if code == CONE:  # a, b, r1, r2
        ax, ay, az, bx, by, bz = P[o], P[o + 1], P[o + 2], P[o + 3], P[o + 4], P[o + 5]
        r1, r2 = P[o + 6], P[o + 7]
        bax, bay, baz = bx - ax, by - ay, bz - az
        l2 = bax * bax + bay * bay + baz * baz
        rr = r1 - r2
        a2 = l2 - rr * rr
        il2 = 1.0 / l2
        pax, pay, paz = x - ax, y - ay, z - az
        yy = pax * bax + pay * bay + paz * baz
        zz = yy - l2
        wx, wy, wz = pax * l2 - yy * bax, pay * l2 - yy * bay, paz * l2 - yy * baz
        x2 = wx * wx + wy * wy + wz * wz
        y2 = yy * yy * l2
        z2 = zz * zz * l2
        k = _sgn(rr) * rr * rr * x2
        if _sgn(zz) * a2 * z2 > k:
            return math.sqrt(x2 + z2) * il2 - r2
        if _sgn(yy) * a2 * y2 < k:
            return math.sqrt(x2 + y2) * il2 - r1
        return (math.sqrt(max(x2 * a2 * il2, 0.0)) + yy * rr) * il2 - r1
    if code == BOX:  # c, half, R, round
        px, py, pz = x - P[o], y - P[o + 1], z - P[o + 2]
        qx = px * P[o + 6] + py * P[o + 9] + pz * P[o + 12]
        qy = px * P[o + 7] + py * P[o + 10] + pz * P[o + 13]
        qz = px * P[o + 8] + py * P[o + 11] + pz * P[o + 14]
        rd = P[o + 15]
        dx, dy, dz = abs(qx) - (P[o + 3] - rd), abs(qy) - (P[o + 4] - rd), abs(qz) - (P[o + 5] - rd)
        ox, oy, oz = max(dx, 0.0), max(dy, 0.0), max(dz, 0.0)
        return math.sqrt(ox * ox + oy * oy + oz * oz) + min(max(dx, max(dy, dz)), 0.0) - rd
    if code == CYLINDER:  # a, b, r, round
        ax, ay, az, bx, by, bz = P[o], P[o + 1], P[o + 2], P[o + 3], P[o + 4], P[o + 5]
        r, rd = P[o + 6], P[o + 7]
        bax, bay, baz = bx - ax, by - ay, bz - az
        baba = bax * bax + bay * bay + baz * baz
        pax, pay, paz = x - ax, y - ay, z - az
        paba = pax * bax + pay * bay + paz * baz
        cx, cy, cz = pax * baba - paba * bax, pay * baba - paba * bay, paz * baba - paba * baz
        xx = math.sqrt(cx * cx + cy * cy + cz * cz) - (r - rd) * baba
        yy = abs(paba - baba * 0.5) - baba * 0.5
        x2, y2 = xx * xx, yy * yy * baba
        if max(xx, yy) < 0:
            d = -min(x2, y2)
        else:
            d = (x2 if xx > 0 else 0.0) + (y2 if yy > 0 else 0.0)
        return _sgn(d) * math.sqrt(abs(d)) / baba - rd
    if code == TORUS:  # c, R_major, r_minor, R
        px, py, pz = x - P[o], y - P[o + 1], z - P[o + 2]
        qx = px * P[o + 5] + py * P[o + 8] + pz * P[o + 11]
        qy = px * P[o + 6] + py * P[o + 9] + pz * P[o + 12]
        qz = px * P[o + 7] + py * P[o + 10] + pz * P[o + 13]
        a = math.sqrt(qx * qx + qz * qz) - P[o + 3]
        return math.sqrt(a * a + qy * qy) - P[o + 4]
    if code == PLANE:  # c, n
        return (P[o] - x) * P[o + 3] + (P[o + 1] - y) * P[o + 4] + (P[o + 2] - z) * P[o + 5]
    if code == EXTRUDE:  # c, R, half depth, round, profile
        qx, qy, qz = _local(P, o, x, y, z)
        rd = P[o + 13]
        wx = _profile(P, o + 14, qx, qy) + rd
        wz = abs(qz) - (P[o + 12] - rd)
        o0, o1 = max(wx, 0.0), max(wz, 0.0)
        return min(max(wx, wz), 0.0) + math.sqrt(o0 * o0 + o1 * o1) - rd
    if code == REVOLVE:  # c, R, offset, a0, a1, partial, profile
        qx, qy, qz = _local(P, o, x, y, z)
        d = _profile(P, o + 16, math.sqrt(qx * qx + qz * qz) - P[o + 12], qy)
        return max(d, _wedge(qx, qz, P[o + 13], P[o + 14])) if P[o + 15] > 0 else d
    if code == TUBE:  # segments, r0, r1, then A B C of each segment
        ns, r0, r1 = int(P[o]), P[o + 1], P[o + 2]
        d = 1e30
        for i in range(ns):
            s = o + 3 + 9 * i
            a0, a1, a2, b0, b1, b2 = P[s], P[s + 1], P[s + 2], P[s + 3], P[s + 4], P[s + 5]
            dist, t = _bez(x, y, z, a0, a1, a2, b0, b1, b2, P[s + 6], P[s + 7], P[s + 8])
            d = min(d, dist - (r0 + (r1 - r0) * (i + t) / ns))
        return d
    return _triangle(P, o, x, y, z)


@njit(cache=True)
def _triangle(P, o, x, y, z):  # a, b, c, thickness
    ax, ay, az, bx, by, bz = P[o], P[o + 1], P[o + 2], P[o + 3], P[o + 4], P[o + 5]
    cx, cy, cz, th = P[o + 6], P[o + 7], P[o + 8], P[o + 9]
    bax, bay, baz = bx - ax, by - ay, bz - az
    cbx, cby, cbz = cx - bx, cy - by, cz - bz
    acx, acy, acz = ax - cx, ay - cy, az - cz
    nx = bay * acz - baz * acy  # ba x ac
    ny = baz * acx - bax * acz
    nz = bax * acy - bay * acx
    pax, pay, paz = x - ax, y - ay, z - az
    pbx, pby, pbz = x - bx, y - by, z - bz
    pcx, pcy, pcz = x - cx, y - cy, z - cz
    s = (
        _sgn(pax * (bay * nz - baz * ny) + pay * (baz * nx - bax * nz) + paz * (bax * ny - bay * nx))
        + _sgn(pbx * (cby * nz - cbz * ny) + pby * (cbz * nx - cbx * nz) + pbz * (cbx * ny - cby * nx))
        + _sgn(pcx * (acy * nz - acz * ny) + pcy * (acz * nx - acx * nz) + pcz * (acx * ny - acy * nx))
    )
    if s < 2:
        t1 = _clip01((pax * bax + pay * bay + paz * baz) / (bax * bax + bay * bay + baz * baz))
        e1 = (bax * t1 - pax) ** 2 + (bay * t1 - pay) ** 2 + (baz * t1 - paz) ** 2
        t2 = _clip01((pbx * cbx + pby * cby + pbz * cbz) / (cbx * cbx + cby * cby + cbz * cbz))
        e2 = (cbx * t2 - pbx) ** 2 + (cby * t2 - pby) ** 2 + (cbz * t2 - pbz) ** 2
        t3 = _clip01((pcx * acx + pcy * acy + pcz * acz) / (acx * acx + acy * acy + acz * acz))
        e3 = (acx * t3 - pcx) ** 2 + (acy * t3 - pcy) ** 2 + (acz * t3 - pcz) ** 2
        return math.sqrt(min(min(e1, e2), e3)) - th
    return math.sqrt((pax * nx + pay * ny + paz * nz) ** 2 / (nx * nx + ny * ny + nz * nz)) - th


@njit(cache=True)
def _cbrt(x):
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


@njit(cache=True)
def _bez(px, py, pz, ax, ay, az, bx, by, bz, cx, cy, cz):
    """(distance, t) from a point to the quadratic Bezier A-B-C (sdf._bezier; z = 0 for 2D)."""
    a0, a1, a2 = bx - ax, by - ay, bz - az
    b0, b1, b2 = ax - 2.0 * bx + cx, ay - 2.0 * by + cy, az - 2.0 * bz + cz
    bb = b0 * b0 + b1 * b1 + b2 * b2
    if bb < 1e-12:
        e0, e1, e2 = cx - ax, cy - ay, cz - az
        ee = max(e0 * e0 + e1 * e1 + e2 * e2, 1e-12)
        t = _clip01(((px - ax) * e0 + (py - ay) * e1 + (pz - az) * e2) / ee)
        dx, dy, dz = ax + t * e0 - px, ay + t * e1 - py, az + t * e2 - pz
        return math.sqrt(dx * dx + dy * dy + dz * dz), t
    c0, c1, c2 = a0 * 2.0, a1 * 2.0, a2 * 2.0
    d0, d1, d2 = ax - px, ay - py, az - pz
    kk = 1.0 / bb
    kx = kk * (a0 * b0 + a1 * b1 + a2 * b2)
    ky = kk * (2.0 * (a0 * a0 + a1 * a1 + a2 * a2) + (d0 * b0 + d1 * b1 + d2 * b2)) / 3.0
    kz = kk * (d0 * a0 + d1 * a1 + d2 * a2)
    p = ky - kx * kx
    q = kx * (2.0 * kx * kx - 3.0 * ky) + kz
    h = q * q + 4.0 * p * p * p
    if h >= 0:
        hs = math.sqrt(h)
        t = _clip01(_cbrt((hs - q) / 2.0) + _cbrt((-hs - q) / 2.0) - kx)
        e0, e1, e2 = d0 + (c0 + b0 * t) * t, d1 + (c1 + b1 * t) * t, d2 + (c2 + b2 * t) * t
        return math.sqrt(e0 * e0 + e1 * e1 + e2 * e2), t
    z = math.sqrt(-p)
    pz2 = p * z * 2.0
    v = math.acos(min(max(q / pz2 if pz2 != 0 else q, -1.0), 1.0)) / 3.0
    m, n = math.cos(v), math.sin(v) * 1.732050808
    ta, tb = _clip01((m + m) * z - kx), _clip01((-n - m) * z - kx)
    e0, e1, e2 = d0 + (c0 + b0 * ta) * ta, d1 + (c1 + b1 * ta) * ta, d2 + (c2 + b2 * ta) * ta
    da = e0 * e0 + e1 * e1 + e2 * e2
    e0, e1, e2 = d0 + (c0 + b0 * tb) * tb, d1 + (c1 + b1 * tb) * tb, d2 + (c2 + b2 * tb) * tb
    db = e0 * e0 + e1 * e1 + e2 * e2
    if db < da:
        return math.sqrt(db), tb
    return math.sqrt(da), ta


@njit(cache=True)
def _profile(P, o, x, y):
    """Signed distance in the plane to the 2D profile whose parameters start at P[o] (sdf.circle, rect...)."""
    code = int(P[o])
    if code == P_CIRCLE:
        return math.sqrt(x * x + y * y) - P[o + 1]
    if code == P_RECT:
        hx, hy, chamfer, rd = P[o + 1], P[o + 2], P[o + 3], P[o + 4]
        if chamfer > 0:
            p0, p1 = abs(x) - hx, abs(y) - hy
            if p1 > p0:
                p0, p1 = p1, p0
            p1 += chamfer
            k = 1.0 - math.sqrt(2.0)
            if p1 < 0 and p1 + p0 * k < 0:
                return p0
            if p0 < p1:
                return (p0 + p1) * SQRT_HALF
            return math.sqrt(p0 * p0 + p1 * p1)
        d0, d1 = abs(x) - (hx - rd), abs(y) - (hy - rd)
        o0, o1 = max(d0, 0.0), max(d1, 0.0)
        return math.sqrt(o0 * o0 + o1 * o1) + min(max(d0, d1), 0.0) - rd
    if code == P_POLYGON:
        n = int(P[o + 1])
        v = o + 3
        dx, dy = x - P[v], y - P[v + 1]
        d = dx * dx + dy * dy
        s = 1.0
        for i in range(n):
            j = i - 1 if i > 0 else n - 1
            vix, viy, vjx, vjy = P[v + 2 * i], P[v + 2 * i + 1], P[v + 2 * j], P[v + 2 * j + 1]
            ex, ey = vjx - vix, vjy - viy
            wx, wy = x - vix, y - viy
            t = _clip01((wx * ex + wy * ey) / (ex * ex + ey * ey))
            bx, by = wx - ex * t, wy - ey * t
            d = min(d, bx * bx + by * by)
            c1, c2, c3 = y >= viy, y < vjy, ex * wy > ey * wx
            if (c1 and c2 and c3) or (not c1 and not c2 and not c3):
                s = -s
        return s * math.sqrt(d) - P[o + 2]
    # P_BEZIER: segments from P0 through C0 to P1..., the last back to P0
    ns = int(P[o + 1])
    v = o + 2
    npts = 2 * ns
    d = 1e30
    crossings = 0
    for i in range(ns):
        a = 2 * i
        c = (a + 2) % npts
        Ax, Ay, Bx, By = P[v + 2 * a], P[v + 2 * a + 1], P[v + 2 * a + 2], P[v + 2 * a + 3]
        Cx, Cy = P[v + 2 * c], P[v + 2 * c + 1]
        dist, _ = _bez(x, y, 0.0, Ax, Ay, 0.0, Bx, By, 0.0, Cx, Cy, 0.0)
        d = min(d, dist)
        a2, a1, a0 = Ay - 2 * By + Cy, 2 * (By - Ay), Ay - y
        if abs(a2) < 1e-12:
            if abs(a1) > 1e-12:
                t = -a0 / a1
                xt = (1 - t) ** 2 * Ax + 2 * (1 - t) * t * Bx + t * t * Cx
                if t >= 0 and t < 1 and xt > x:
                    crossings += 1
        else:
            disc = a1 * a1 - 4 * a2 * a0
            if disc >= 0:
                sq = math.sqrt(disc)
                for t, good in (((-a1 - sq) / (2 * a2), True), ((-a1 + sq) / (2 * a2), disc > 0)):
                    xt = (1 - t) ** 2 * Ax + 2 * (1 - t) * t * Bx + t * t * Cx
                    if good and t >= 0 and t < 1 and xt > x:
                        crossings += 1
    return -d if crossings % 2 == 1 else d


@njit(cache=True)
def _wedge(x, z, a0, a1):
    m, half = (a0 + a1) / 2, (a1 - a0) / 2
    cm, sm = math.cos(m), math.sin(m)
    px = abs(x * cm - z * sm)
    py = z * cm + x * sm
    s0, c0 = math.sin(half), math.cos(half)
    t = max(px * s0 + py * c0, 0.0)
    dist = math.sqrt((px - s0 * t) ** 2 + (py - c0 * t) ** 2)
    return dist * _sgn(c0 * px - s0 * py)


@njit(cache=True)
def _join(a, b, mode, k, n):
    """Union of two distances (sdf.join)."""
    if mode == SMOOTH or k <= 0:
        return _smin(a, b, k)
    if mode == CHAMFER:
        return min(min(a, b), (a - k + b) * SQRT_HALF)
    if mode == ROUND:
        u0, u1 = max(k - a, 0.0), max(k - b, 0.0)
        return max(k, min(a, b)) - math.sqrt(u0 * u0 + u1 * u1)
    s = k / max(n, 1.0)  # STAIRS
    u = b - k
    w = u - a + s
    return min(min(a, b), 0.5 * (u + a + abs(w - 2 * s * math.floor(w / (2 * s)) - s)))


@njit(cache=True)
def _carve(d, c, mode, k, n, depth, width):
    """`d` minus the cutter `c` (sdf.carve)."""
    if mode == GROOVE:
        return max(d, min(d + depth, width - abs(c)))
    if mode == SMOOTH or k <= 0:
        return -_smin(-d, c, k)
    return -_join(-d, c, mode, k, n)


@njit(cache=True)
def prim(code, P, o, x, y, z):
    """Distance from (x, y, z) to primitive `code` whose parameters start at P[o] (layouts: sdf.py `ir`). A MOD
    entry changes the point in its frame (twist, bend, elongate), evaluates the primitive after it and hollows
    the result (shell)."""
    if code != MOD:
        return base(code, P, o, x, y, z)
    qx, qy, qz = _local(P, o, x, y, z)
    twist, bend, shell = P[o + 12], P[o + 13], P[o + 17]
    if twist != 0:
        a = twist * qy
        ca, sa = math.cos(a), math.sin(a)
        qx, qz = ca * qx - sa * qz, sa * qx + ca * qz
    if bend != 0:
        a = bend * qx
        ca, sa = math.cos(a), math.sin(a)
        qx, qy = ca * qx - sa * qy, sa * qx + ca * qy
    hx, hy, hz = P[o + 14], P[o + 15], P[o + 16]
    qx -= min(max(qx, -hx), hx)
    qy -= min(max(qy, -hy), hy)
    qz -= min(max(qz, -hz), hz)
    # back to world: c + q @ R.T
    wx = P[o] + qx * P[o + 3] + qy * P[o + 4] + qz * P[o + 5]
    wy = P[o + 1] + qx * P[o + 6] + qy * P[o + 7] + qz * P[o + 8]
    wz = P[o + 2] + qx * P[o + 9] + qy * P[o + 10] + qz * P[o + 11]
    d = base(int(P[o + 18]), P, o + 19, wx, wy, wz)
    return abs(d) - shell / 2 if shell != 0 else d


@njit(cache=True)
def group(g, x, y, z, exact_within, codes, offs, data, gp, gc, gblend, gb, glip):
    """Distance to group g at a local point; the bounding sphere's distance where that is >= exact_within."""
    dx, dy, dz = x - gb[g, 0], y - gb[g, 1], z - gb[g, 2]
    db = math.sqrt(dx * dx + dy * dy + dz * dz) - gb[g, 3]
    if db >= exact_within:
        return db
    j = gp[g, 0]
    d = prim(codes[j], data, offs[j], x, y, z)
    mode, k, n = int(gblend[g, 0]), gblend[g, 1], gblend[g, 2]
    for j in range(gp[g, 0] + 1, gp[g, 1]):
        d = _join(d, prim(codes[j], data, offs[j], x, y, z), mode, k, n)
    mode, k, n = int(gblend[g, 3]), gblend[g, 4], gblend[g, 5]
    for j in range(gc[g, 0], gc[g, 1]):
        d = _carve(d, prim(codes[j], data, offs[j], x, y, z), mode, k, n, gblend[g, 6], gblend[g, 7])
    return d * glip[g]


@njit(cache=True)
def _to_local(W, x, y, z):
    px, py, pz = x - W[3, 0], y - W[3, 1], z - W[3, 2]
    return (
        px * W[0, 0] + py * W[0, 1] + pz * W[0, 2],
        px * W[1, 0] + py * W[1, 1] + pz * W[1, 2],
        px * W[2, 0] + py * W[2, 1] + pz * W[2, 2],
    )


@njit(cache=True)
def scene_m(x, y, z, masks, row, solid, exact_within, W, codes, offs, data, gp, gc, gblend, gb, flags, glip):
    """Scene distance at a world point over the groups set in masks[row] (`solid`: without emissive groups)."""
    lx, ly, lz = _to_local(W, x, y, z)
    d = 1e3
    for w in range(masks.shape[1]):
        m = masks[row, w]
        g = w * 64
        while m:
            if m & ONE:
                if not (solid and flags[g, 0]):
                    d = min(d, group(g, lx, ly, lz, exact_within, codes, offs, data, gp, gc, gblend, gb, glip))
            m >>= ONE
            g += 1
    return d


@njit(cache=True)
def nearest(x, y, z, W, codes, offs, data, gp, gc, gblend, gb, glip):
    """The group nearest a world point, as render.Scene.dist_all(...).argmin()."""
    lx, ly, lz = _to_local(W, x, y, z)
    best, bd = 0, 1e30
    for g in range(gb.shape[0]):
        d = group(g, lx, ly, lz, 0.05, codes, offs, data, gp, gc, gblend, gb, glip)
        if d < bd:
            best, bd = g, d
    return best


@njit(cache=True)
def line_mask(masks, row, ox, oy, oz, dx, dy, dz, C, BR, margin, ahead):
    """Set the groups whose bounding sphere comes within `margin` of the line o + s*d (s >= 0 when `ahead`)."""
    any_ = False
    for w in range(masks.shape[1]):
        masks[row, w] = 0
    for g in range(C.shape[0]):
        wx, wy, wz = C[g, 0] - ox, C[g, 1] - oy, C[g, 2] - oz
        along = wx * dx + wy * dy + wz * dz
        r = BR[g] + margin
        if ahead and along < -r:
            continue
        if wx * wx + wy * wy + wz * wz - along * along < r * r:
            masks[row, g // 64] |= ONE << np.uint64(g % 64)
            any_ = True
    return any_


@njit(cache=True)
def ball_mask(masks, row, x, y, z, C, BR, radius):
    for w in range(masks.shape[1]):
        masks[row, w] = 0
    for g in range(C.shape[0]):
        dx, dy, dz = C[g, 0] - x, C[g, 1] - y, C[g, 2] - z
        r = BR[g] + radius
        if dx * dx + dy * dy + dz * dz < r * r:
            masks[row, g // 64] |= ONE << np.uint64(g % 64)


# ---------------------------------------------------------------- the frame


@njit(parallel=True, cache=True)
def trace(
    ro, D, scene_c, scene_r, C, BR, L, use_ao, use_sh, W, codes, offs, data, gp, gc, gblend, gb, flags, glip, masks
):
    n = ro.shape[0]
    gid = np.full(n, -1, np.int64)
    depth = np.full(n, np.inf)
    nrm = np.zeros((n, 3))
    shadow = np.ones(n)
    occl = np.ones(n)
    cam, aom, shm = masks[0], masks[1], masks[2]
    for i in prange(n):
        ox, oy, oz = ro[i, 0], ro[i, 1], ro[i, 2]
        if not line_mask(cam, i, ox, oy, oz, D[0], D[1], D[2], C, BR, 0.05 + 1e-6, False):
            continue  # the ray passes no part (render.render's "never")
        cx, cy, cz = ox - scene_c[0], oy - scene_c[1], oz - scene_c[2]
        b = cx * D[0] + cy * D[1] + cz * D[2]
        disc = b * b - (cx * cx + cy * cy + cz * cz - scene_r * scene_r)
        if disc < 0:
            continue
        sq = math.sqrt(disc)
        t, tmax = max(-b - sq, 0.0), -b + sq
        if not t < tmax:
            continue
        hit = False
        for _ in range(110):
            x, y, z = ox + D[0] * t, oy + D[1] * t, oz + D[2] * t
            d = scene_m(x, y, z, cam, i, False, 0.05, W, codes, offs, data, gp, gc, gblend, gb, flags, glip)
            t += d * 0.85
            if d < 0.0015:
                hit = True
                break
            if t >= tmax:
                break
        if not hit:
            continue
        x, y, z = ox + D[0] * t, oy + D[1] * t, oz + D[2] * t
        g = nearest(x, y, z, W, codes, offs, data, gp, gc, gblend, gb, glip)
        e = 0.002
        a = (W, codes, offs, data, gp, gc, gblend, gb, flags, glip)
        nx = scene_m(x + e, y, z, cam, i, False, 0.05, *a) - scene_m(x - e, y, z, cam, i, False, 0.05, *a)
        ny = scene_m(x, y + e, z, cam, i, False, 0.05, *a) - scene_m(x, y - e, z, cam, i, False, 0.05, *a)
        nz = scene_m(x, y, z + e, cam, i, False, 0.05, *a) - scene_m(x, y, z - e, cam, i, False, 0.05, *a)
        ln = max(math.sqrt(nx * nx + ny * ny + nz * nz), 1e-9)
        nx, ny, nz = nx / ln, ny / ln, nz / ln
        if flags[g, 1] and nx * D[0] + ny * D[1] + nz * D[2] > 0:
            nx, ny, nz = -nx, -ny, -nz
        ao = 1.0
        if use_ao:
            ball_mask(aom, i, x, y, z, C, BR, 0.27)  # the taps reach 0.26 and matter below h
            acc, w = 0.0, 1.0
            for h in (0.04, 0.09, 0.16, 0.26):
                dd = scene_m(x + nx * h, y + ny * h, z + nz * h, aom, i, True, h, *a)
                acc += w * max(h - dd, 0.0)
                w *= 0.6
            ao = _clip01(1 - 3.2 * acc)
        sh = 1.0
        if use_sh:
            sx, sy, sz = x + nx * 0.01, y + ny * 0.01, z + nz * 0.01
            # farther than 0.6 from the shadow ray a part neither darkens it nor shortens a step
            line_mask(shm, i, sx, sy, sz, L[0], L[1], L[2], C, BR, 0.6, True)
            ts, res = 0.04, 1.0
            for _ in range(28):
                dd = scene_m(sx + L[0] * ts, sy + L[1] * ts, sz + L[2] * ts, shm, i, True, max(ts / 10, 0.2), *a)
                res = min(res, 10 * dd / ts)
                ts += min(max(dd, 0.02), 0.2)
                if not res > 0:
                    break
            sh = _clip01(res)
        gid[i] = g
        depth[i] = t
        nrm[i, 0], nrm[i, 1], nrm[i, 2] = nx, ny, nz
        shadow[i] = sh
        occl[i] = ao
    return gid, depth, nrm, shadow, occl


@njit(cache=True)
def _prim_at(code, data, pts):
    out = np.empty(pts.shape[0])
    for i in range(pts.shape[0]):
        out[i] = prim(code, data, 0, pts[i, 0], pts[i, 1], pts[i, 2])
    return out


def distances(primitive, pts):
    """A primitive closure's distances at points (n, 3), computed by the kernel (parity tests)."""
    code, params = primitive.ir
    return _prim_at(code, np.asarray(params, float), np.ascontiguousarray(pts, float))


def render(scene, cam, light):
    """render.Samples of a frame, as render.render."""
    from .render import Samples, camera_rays

    N = cam.size * cam.ss
    ro = camera_rays(cam)
    if not scene.groups:
        one = np.ones((N, N))
        return Samples(np.full((N, N), -1), np.full((N, N), np.inf), np.zeros((N, N, 3)), one, one.copy())
    ir = compile_scene(scene)
    masks = np.zeros((3, len(ro), (len(scene.groups) + 63) // 64), np.uint64)
    out = trace(
        ro,
        np.asarray(cam.D, float),
        np.asarray(scene.bc, float),
        float(scene.br),
        ir.C,
        ir.gb[:, 3].copy(),
        np.asarray(light.L, float),
        bool(light.ao),
        bool(light.shadows),
        ir.W,
        ir.codes,
        ir.offs,
        ir.data,
        ir.gp,
        ir.gc,
        ir.gblend,
        ir.gb,
        ir.flags,
        ir.glip,
        masks,
    )
    gid, depth, nrm, shadow, occl = out
    return Samples(
        gid.reshape(N, N), depth.reshape(N, N), nrm.reshape(N, N, 3), shadow.reshape(N, N), occl.reshape(N, N)
    )
