"""Spec + channel values -> coordinate frames -> SDF groups.

Mirroring convention: every *_L bone/ik/part is authored on the +X side. Its *_R twin is
evaluated with the *_R channels and every local vector is mirrored (x -> -x), Euler
rotations become (rx, -ry, -rz). *_R channels therefore use the same (outward positive)
values as *_L for a symmetric pose.
"""

import numpy as np

from .expr import ExprError, evaluate
from .sdf import (
    BLENDS,
    GROOVE,
    SMOOTH,
    Group,
    bezier_path,
    box,
    circle,
    cross3,
    cylinder,
    ellipsoid,
    extrude,
    modified,
    normalize,
    plane,
    polygon,
    rect,
    revolve,
    rot_x,
    rot_y,
    rot_z,
    round_cone,
    sphere,
    torus,
    triangle,
    tube,
)

MIRROR = np.array([-1.0, 1.0, 1.0])


class Frame:
    __slots__ = ('o', 'R', 's')

    def __init__(self, o=None, R=None, s=None):
        self.o = np.zeros(3) if o is None else np.asarray(o, float)
        self.R = np.eye(3) if R is None else np.asarray(R, float)
        self.s = np.ones(3) if s is None else np.asarray(s, float)

    def apply(self, v):
        return self.o + self.R @ (self.s * np.asarray(v, float))

    def dir(self, v):
        return self.R @ np.asarray(v, float)

    @property
    def uscale(self):
        return float(np.prod(self.s) ** (1 / 3))


def euler(r):
    r = np.broadcast_to(np.asarray(r, float), (3,))
    return rot_y(r[1]) @ rot_z(r[2]) @ rot_x(r[0])


def basis_z(z, up):
    z = z / max(np.linalg.norm(z), 1e-9)
    x = cross3(up, z)
    if np.linalg.norm(x) < 1e-6:
        x = cross3([1.0, 0, 0], z)
    x /= np.linalg.norm(x)
    y = cross3(z, x)
    return np.stack([x, y, z], 1)


def rest_env(spec, yaw=0.0):
    """Channel defaults, plus the variables every expression sees: p, t, f, n, yaw (degrees) and dir ('s'...)."""
    from .spec import direction_name

    env = {}
    for k, v in spec['channels'].items():
        env[k] = evaluate(v, {}) if not isinstance(v, (int, float)) else float(v)
    env.update(p=0.0, t=0.0, f=0, n=1, yaw=float(yaw), dir=direction_name(yaw))
    return env


class Ctx:
    def __init__(self, spec, env, notes=None, snap=True):
        self.spec = spec
        self.env = dict(env, sx=1.0)  # sx: -1 while an automatic _R twin is evaluated (see side)
        self.frames = {}
        self.notes = notes  # a list to collect geometry warnings in (thin shells...), or None
        self.snap = set(spec.get('snap') or []) if snap else set()
        self.rest = None  # the rest pose's frames, for snapping

    def snapped(self, name, frame):
        """A frame listed in the spec's `snap`, moved so that its screen offset from the rest pose is a whole
        number of pixels: small bobs become whole-pixel steps and the sprite stops boiling."""
        if name not in self.snap:
            return frame
        from .render import Camera

        yaw = float(self.env.get('yaw', 0.0))
        if self.rest is None:
            self.rest = Ctx(self.spec, rest_env(self.spec, yaw), snap=False)
        cam = Camera.from_spec(self.spec)
        Ry = rot_y(np.radians(yaw))  # model -> world, as render.Scene
        w = Ry @ (frame.o - self.rest.frame(name, f'snap: {name}').o)
        sx, sy = (w @ cam.R) / cam.scale, -(w @ cam.U) / cam.scale
        fix = cam.R * (np.floor(sx + 0.5) - sx) * cam.scale - cam.U * (np.floor(sy + 0.5) - sy) * cam.scale
        return Frame(frame.o + Ry.T @ fix, frame.R, frame.s)

    def side(self, mirror):
        """Set `sx` for the item being evaluated (-1 in an automatic _R twin, +1 otherwise); returns the previous
        value to restore. `yaw*sx` is then the direction as the item's _L source sees it."""
        old = self.env.get('sx', 1.0)
        self.env['sx'] = -1.0 if mirror else 1.0
        return old

    def thin(self, value, where, what, us=1.0):
        """Note a size under one pixel at the spec's camera scale: it can vanish or flicker. `value` is in world
        units; `us` is the part space's scale, so the note speaks in the numbers written in the spec."""
        scale = float(self.spec.get('camera', {}).get('scale', 0.05))
        if self.notes is not None and value < scale:
            self.notes.append(
                f'{where}: {what} {value / us:.3f} is {value / scale:.1f} px at camera.scale {scale:g}: it can vanish '
                f'or flicker (make it at least {scale / us:.3f})'
            )

    def val(self, v, where, mirror=False, vec=False):
        try:
            out = evaluate(v, self.env)
        except ExprError as e:
            raise ExprError(f'{where}: {e}') from None
        if vec:
            out = np.asarray(out, float)
            out = out.copy() if out.shape == (3,) else np.broadcast_to(out, (3,)).copy()
            if mirror:
                out = out * MIRROR
        return out

    def rot(self, v, where, mirror=False):
        r = np.broadcast_to(np.asarray(self.val(v, where), float), (3,)).copy()
        if mirror:
            r[1] = -r[1]
            r[2] = -r[2]
        return euler(r)

    def frame(self, name, where):
        self._ensure(name)
        if name not in self.frames:
            raise ExprError(f'{where}: unknown frame "{name}"')
        return self.frames[name]

    # ---------------- frames ----------------
    def _ensure(self, name):
        if name in self.frames:
            return
        sp = self.spec
        if name == 'root':
            r = self.env.get('root', [0, 0, 0])
            self.frames['root'] = self.snapped('root', Frame(np.asarray(r, float)))
            return
        if name in sp['bones']:
            self._bone(name, sp['bones'][name])
            return
        for ik_name, ik in sp['ik'].items():
            if name in (ik.get('joint'), ik.get('end')):
                self._ik(ik_name, ik)
                return

    def _bone(self, name, b):
        if name in getattr(self, '_stack', set()):
            raise ExprError(f'bones.{name}: circular parent chain')
        self._stack = getattr(self, '_stack', set()) | {name}
        m = b.get('_mirror', False)
        w = f'bones.{name}'
        par = self.frame(b.get('parent', 'root'), w + '.parent')
        at = self.frame(b['at'], w + '.at') if b.get('at') else None
        old = self.side(m)
        pos = self.val(b.get('pos', [0, 0, 0]), w + '.pos', m, vec=True)
        R = self.rot(b.get('rot', [0, 0, 0]), w + '.rot', m)
        sc = np.broadcast_to(np.asarray(self.val(b.get('scale', 1.0), w + '.scale'), float), (3,))
        self.env['sx'] = old
        Rp = par.R if b.get('inherit_rot', True) else np.eye(3)
        sp_ = par.s if b.get('inherit_scale', True) else np.ones(3)
        if at is not None:
            o = at.o + par.R @ (par.s * pos)
        else:
            o = par.apply(pos)
        self.frames[name] = self.snapped(name, Frame(o, Rp @ R, sp_ * sc))
        self._stack = self._stack - {name}

    def _ik(self, name, ik):
        m = ik.get('_mirror', False)
        w = f'ik.{name}'
        a = self.frame(ik['start'], w + '.start')
        space = self.frame(ik.get('space', 'root'), w + '.space')
        psp = self.frame(ik.get('pole_space', ik.get('space', 'root')), w + '.pole_space')
        old = self.side(m)
        tgt = space.apply(self.val(ik['target'], w + '.target', m, vec=True))
        pole = psp.dir(self.val(ik.get('pole', [0, 0, 1]), w + '.pole', m, vec=True))
        l1, l2 = [float(x) for x in self.val(ik['lengths'], w + '.lengths')]
        up_v = self.val(ik['up'], w + '.up', m, vec=True) if 'up' in ik else None
        self.env['sx'] = old
        A = a.o
        dvec = tgt - A
        d = np.clip(np.linalg.norm(dvec), abs(l1 - l2) + 1e-3, (l1 + l2) * 0.999)
        u = dvec / max(np.linalg.norm(dvec), 1e-9)
        x = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
        h = np.sqrt(max(l1 * l1 - x * x, 0))
        v = pole - (pole @ u) * u
        v /= max(np.linalg.norm(v), 1e-9)
        joint = A + u * x + v * h
        end = A + u * d
        if up_v is not None:  # reference for the end frame's y axis (in pole_space)
            up = psp.dir(up_v)
        else:
            up = a.R @ np.array([0, 1.0, 0])
        self.frames[ik['joint']] = Frame(joint, basis_z(end - joint, up))
        self.frames[ik['end']] = Frame(end, basis_z(end - joint, up))

    # ---------------- points ----------------
    def point(self, v, space, where, m):
        if isinstance(v, str) and v.startswith('@'):
            return self.frame(v[1:].strip(), where).o
        if isinstance(v, dict):
            if 'at' in v:
                f = self.frame(v['at'], where + '.at')
                return f.apply(self.val(v.get('off', [0, 0, 0]), where + '.off', m, vec=True))
            if 'between' in v:
                p0 = self.point(v['between'][0], space, where, m)
                p1 = self.point(v['between'][1], space, where, m)
                t = float(self.val(v.get('t', 0.5), where + '.t'))
                return p0 + (p1 - p0) * t
            raise ExprError(f'{where}: point dict needs "at" or "between"')
        return space.apply(self.val(v, where, m, vec=True))


MODIFIERS = ('shell', 'elongate', 'twist', 'bend')
PROFILES = ('circle', 'rect', 'polygon', 'bezier')


def _crossing(pts):
    """True when two edges of a closed polygon cross (it then has no clear inside)."""

    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if (j + 1) % n == i:
                continue
            c, d = pts[j], pts[(j + 1) % n]
            if side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0:
                return True
    return False


def _profile(ctx, a, where, m, us):
    """A 2D profile from its mapping: {circle: r}, {rect: [hx, hy], chamfer|round}, {polygon: [[x, y]...], round}
    or {bezier: [P0, C0, P1, C1...]}. Lengths scale with the part's space; x is mirrored for _R twins."""
    kinds = [k for k in PROFILES if isinstance(a, dict) and k in a]
    if len(kinds) != 1:
        raise ExprError(
            f'{where}: a profile is one of {{circle: r}}, {{rect: [hx, hy]}}, {{polygon: [[x, y], ...]}} '
            'or {bezier: [[x, y], ...]}'
        )
    kind = kinds[0]
    w = f'{where}.{kind}'
    if kind == 'circle':
        r = float(ctx.val(a['circle'], w)) * us
        ctx.thin(2 * r, w, 'diameter', us)
        return circle(r)
    if kind == 'rect':
        hx, hy = (float(v) for v in np.broadcast_to(np.asarray(ctx.val(a['rect'], w), float), (2,)))
        ctx.thin(2 * min(hx, hy) * us, w, 'width', us)
        chamfer = float(ctx.val(a.get('chamfer', 0.0), where + '.chamfer'))
        return rect(hx * us, hy * us, chamfer * us, float(ctx.val(a.get('round', 0.0), where + '.round')) * us)
    pts = []
    for i, p in enumerate(a[kind]):
        v = np.asarray(ctx.val(p, f'{w}[{i}]'), float)
        if v.shape != (2,):
            raise ExprError(f'{w}[{i}]: a profile point is [x, y]')
        pts.append(v)
    pts = np.array(pts).reshape(-1, 2) * us * [(-1.0 if m else 1.0), 1.0]
    if kind == 'polygon':
        if len(pts) < 3:
            raise ExprError(f'{w}: a polygon needs at least 3 points')
        if ctx.notes is not None and _crossing(pts):
            ctx.notes.append(f'{w}: two edges cross, so the inside is not what it looks like: reorder the points')
        return polygon(pts, float(ctx.val(a.get('round', 0.0), where + '.round')) * us)
    if len(pts) < 4 or len(pts) % 2:
        raise ExprError(f'{w}: a bezier path is P0, C0, P1, C1... (an even number of points, at least 4)')
    return bezier_path(pts)


def _prims(ctx, part_name, part, space, m, prim_list, where_base):
    out = []
    us = space.uscale
    for i, pr in enumerate(prim_list):
        if not isinstance(pr, dict) or len(pr) != 1:
            raise ExprError(f'{where_base}[{i}]: each prim is a one-key mapping like {{sphere: {{...}}}}')
        kind, a = next(iter(pr.items()))
        w = f'{where_base}[{i}].{kind}'
        P = lambda key, d=None, a=a, w=w: ctx.point(a.get(key, d), space, f'{w}.{key}', m)  # noqa: E731
        V = lambda key, d=None, vec=False, a=a, w=w: ctx.val(a.get(key, d), f'{w}.{key}', m and vec, vec=vec)  # noqa: E731

        def rotm(a=a, w=w):
            if 'align' in a:
                p0 = ctx.point(a['align'][0], space, w + '.align', m)
                p1 = ctx.point(a['align'][1], space, w + '.align', m)
                Rb = basis_z(p1 - p0, space.R @ np.array([0, 1.0, 0]))
            else:
                Rb = space.R
            return Rb @ ctx.rot(a.get('rot', [0, 0, 0]), w + '.rot', m)

        if kind == 'plane':
            if not where_base.endswith('.cut'):
                raise ExprError(f'{w}: a plane has no end: use it under cut: to slice the part')
            n = ctx.val(a.get('n', [0, 1, 0]), w + '.n', m, vec=True)
            c = P('c') if 'c' in a else space.apply(normalize(n) * float(V('at', 0.0)))
            out.append(plane(c, space.dir(n)))
        elif kind == 'extrude':
            prof = _profile(ctx, a.get('profile'), w + '.profile', m, us)
            depth = float(V('depth')) * us
            ctx.thin(depth, w + '.depth', 'depth', us)
            out.append(extrude(P('c', [0, 0, 0]), rotm(), prof, depth, float(V('round', 0.0)) * us))
        elif kind == 'revolve':
            prof = _profile(ctx, a.get('profile'), w + '.profile', m, us)
            ang = a.get('angle')
            if ang is not None:
                a0, a1 = (float(v) for v in ctx.val(ang, w + '.angle'))
                ang = (-a1, -a0) if m else (a0, a1)
            out.append(revolve(P('c', [0, 0, 0]), rotm(), prof, float(V('offset', 0.0)) * us, ang))
        elif kind == 'tube':
            pts = [ctx.point(p, space, f'{w}.pts[{j}]', m) for j, p in enumerate(a.get('pts') or [])]
            if len(pts) < 3:
                raise ExprError(f'{w}.pts: a tube needs at least 3 points (2 points: use a cone)')
            r = np.broadcast_to(np.asarray(ctx.val(a['r'], w + '.r'), float), (2,)) * us
            ctx.thin(2 * float(r.max()), w + '.r', 'diameter', us)  # a thin tip is intended; a thin tube is not
            out.append(tube(pts, float(r[0]), float(r[1])))
        elif kind == 'sphere':
            out.append(sphere(P('c'), float(V('r')) * us))
        elif kind == 'ellipsoid':
            r = np.abs(np.asarray(V('r', vec=True), float)) * space.s
            out.append(ellipsoid(P('c'), r, rotm()))
        elif kind == 'cone':
            r = V('r')
            r1, r2 = (float(r[0]), float(r[1])) if np.ndim(r) else (float(r), float(r))
            out.append(round_cone(P('a'), P('b'), r1 * us, r2 * us))
        elif kind == 'chain':
            pts = [ctx.point(p, space, f'{w}.pts[{j}]', m) for j, p in enumerate(a['pts'])]
            rs = [float(x) * us for x in ctx.val(a['r'], w + '.r')]
            for j in range(len(pts) - 1):
                out.append(round_cone(pts[j], pts[j + 1], rs[j], rs[j + 1]))
        elif kind == 'box':
            half = np.abs(np.asarray(V('half', vec=True), float)) * space.s
            out.append(box(P('c'), half, rotm(), float(V('round', 0.0))))
        elif kind == 'cylinder':
            out.append(cylinder(P('a'), P('b'), float(V('r')) * us, float(V('round', 0.0))))
        elif kind == 'torus':
            out.append(torus(P('c'), float(V('R')) * us, float(V('r')) * us, rotm()))
        elif kind == 'tri':
            out.append(triangle(P('a'), P('b'), P('c'), float(V('th', 0.012))))
        elif kind == 'membrane':
            hub = P('hub')
            ring = [ctx.point(p, space, f'{w}.ring[{j}]', m) for j, p in enumerate(a['ring'])]
            th = float(V('th', 0.012))
            for j in range(len(ring) - 1):
                out.append(triangle(hub, ring[j], ring[j + 1], th))
            if a.get('fill_root'):
                b0, b1 = ring[0], ring[-1]
                out.append(triangle(b0, b1, (b0 + b1) / 2 + (hub - b0) * 0.3, th))
            cuts = []
            for j in a.get('scallop', []):
                e0, e1 = ring[j], ring[j + 1]
                mid = (e0 + e1) / 2
                L = np.linalg.norm(e1 - e0)
                r = float(a.get('scallop_depth', 0.34)) * L
                o = mid - hub
                o /= max(np.linalg.norm(o), 1e-9)
                cuts.append(sphere(mid + o * r * 0.62, r))
            out.append(('cuts', cuts))
        else:
            raise ExprError(
                f'{w}: unknown prim type "{kind}" (sphere, ellipsoid, cone, chain, box, cylinder, torus, tri, '
                'membrane, arc, extrude, revolve, tube, plane)'
            )
        if any(k in a for k in MODIFIERS):
            if kind in ('chain', 'membrane', 'plane'):
                raise ExprError(f'{w}: shell, elongate, twist and bend change one primitive, not a {kind}')
            f = out.pop()
            shell = float(V('shell', 0.0)) * us
            if shell:
                ctx.thin(shell, w + '.shell', 'shell thickness', us)
            twist = float(V('twist', 0.0)) / us
            elong = np.abs(np.asarray(ctx.val(a['elongate'], w + '.elongate'), float)) * us if 'elongate' in a else None
            centre = P('c') if 'c' in a else np.asarray(f.bound[0])
            out.append(modified(f, centre, rotm(), shell, elong, -twist if m else twist, float(V('bend', 0.0)) / us))
    return out


def _paint(ctx, part_name, part, space, m, where):
    """The part's `paint:` layers (paint.Layer), in order (later ones win)."""
    from . import paint as P

    out = []
    us = space.uscale
    for i, item in enumerate(part.get('paint') or []):
        w = f'{where}.paint[{i}]'
        kinds = [k for k in P.PATTERNS if isinstance(item, dict) and k in item]
        if not isinstance(item, dict) or 'material' not in item or len(kinds) != 1:
            raise ExprError(f'{w}: a paint layer is a material plus one of {", ".join(P.PATTERNS)}')
        kind = kinds[0]
        a = item[kind]
        thin = None
        if kind == 'prims':
            prims = [p for p in _prims(ctx, part_name, part, space, m, a, w + '.prims') if not isinstance(p, tuple)]
            mask = P.volume(prims)
        else:
            a = a or {}

            def v(key, d=None, a=a, w=w, kind=kind):
                return ctx.val(a[key], f'{w}.{kind}.{key}') if key in a else d

            if kind in ('stripes', 'rings'):
                if v('period') is None and v('at') is None:
                    raise ExprError(f'{w}.{kind}: give `period` (repeating) or `at` (positions)')
                width = float(v('width', 0.04))
                mask = getattr(P, kind)(a.get('axis', 'y'), width, v('period'), v('at'), float(v('offset', 0.0)))
                thin = width
            elif kind == 'grid':
                r = float(v('r', 0.015))
                mask = P.grid(a.get('axes', ('x', 'y')), v('spacing', (0.1, 0.1)), r, v('offset', (0.0, 0.0)))
                thin = 2 * r
            elif kind == 'spots':
                mask = P.spots(float(v('scale', 0.1)), float(v('density', 0.3)), int(v('seed', 0)))
            else:
                mask = P.checker(float(v('size', 0.1)))
        if thin is not None:
            ctx.thin(thin * us, f'{w}.{kind}', 'width', us)
        out.append(P.Layer(item['material'], mask, item.get('edge', False), thin))
    return out


def _blend(v, where, cut=False):
    """(mode, k, n, groove) of `blend` / `cut_blend`: a number (smooth) or {mode, k, n} ({mode: groove, depth,
    width} for a cut)."""
    if not isinstance(v, dict):
        return SMOOTH, float(v), 1, (0.0, 0.0)
    mode = v.get('mode', 'smooth')
    allowed = [b for b in BLENDS if cut or b != 'groove']
    if mode not in allowed:
        raise ExprError(f'{where}.mode: {mode!r} (use {", ".join(allowed)})')
    if BLENDS[mode] == GROOVE:
        return GROOVE, 0.0, 1, (float(v.get('depth', 0.02)), float(v.get('width', 0.01)))
    return BLENDS[mode], float(v.get('k', 0.0)), max(1, int(v.get('n', 1))), (0.0, 0.0)


def _arc_groups(ctx, name, part, space, m, a, mats, w):
    a0 = float(ctx.val(a['a0'], w + '.a0'))
    a1 = float(ctx.val(a['a1'], w + '.a1'))
    r = float(ctx.val(a['r'], w + '.r'))
    width = float(ctx.val(a.get('width', 0.08), w + '.width'))
    fade = float(ctx.val(a.get('fade', 1.0), w + '.fade'))
    dip = float(ctx.val(a.get('dip', 0.12), w + '.dip'))
    c = ctx.point(a.get('c', [0, 0, 0]), space, w + '.c', m)
    n = int(a.get('segments', 9))
    ang = np.linspace(a0, a1, n)
    side = MIRROR if m else 1.0  # the _R twin of an _L arc sweeps the other way
    pts = [
        c
        + space.R
        @ (side * np.array([np.sin(t) * r, -dip * np.sin((t - a0) / (a1 - a0 + 1e-9) * np.pi), np.cos(t) * r]))
        for t in ang
    ]
    buckets = {mm: [] for mm in mats}
    for i in range(n - 1):
        f = (i + 0.5) / (n - 1)
        wd = width * (0.25 + 0.75 * np.sin(np.pi * min(f * 1.15, 1.0))) * fade
        mat = mats[min(int(f * len(mats)), len(mats) - 1)]
        if wd > 0.008:
            buckets[mat].append(round_cone(pts[i], pts[i + 1], wd, wd * 0.9))
    return buckets


def build(spec, env, notes=None):
    """Return list of sdf Groups for the given channel values. `notes`: a list that collects geometry warnings
    (sizes under a pixel, crossing polygons)."""
    ctx = Ctx(spec, env, notes)
    mats = spec['materials']
    groups = []
    for name, part in spec['parts'].items():
        w = f'parts.{name}'
        m = part.get('_mirror', False)
        ctx.side(m)
        if 'when' in part and not ctx.val(part['when'], w + '.when'):
            continue
        space = ctx.frame(part.get('space', 'root'), w + '.space')
        plist = part.get('prims') or []
        # arcs (VFX smears) can spread over several materials
        if len(plist) == 1 and 'arc' in plist[0]:
            ml = part.get('materials') or [part['material']]
            for mat, prs in _arc_groups(ctx, name, part, space, m, plist[0]['arc'], ml, w + '.prims[0].arc').items():
                if prs:
                    M = mats[mat]
                    groups.append(
                        Group(
                            f'{name}:{mat}',
                            mat,
                            prs,
                            k=float(part.get('blend', 0.02)),
                            line=False,
                            emissive=M['emissive'],
                            two_sided=M['two_sided'],
                        )
                    )
            continue
        prims = _prims(ctx, name, part, space, m, plist, w + '.prims')
        cuts = [c for p in prims if isinstance(p, tuple) for c in p[1]]
        prims = [p for p in prims if not isinstance(p, tuple)]
        cuts += _prims(ctx, name, part, space, m, part.get('cut') or [], w + '.cut')
        mat = part['material']
        M = mats[mat]
        mode, k, n, _ = _blend(part.get('blend', 0.0), w + '.blend')
        cmode, ck, cn, groove = _blend(part.get('cut_blend', 0.01), w + '.cut_blend', cut=True)
        groups.append(
            Group(
                name,
                mat,
                prims,
                k=k,
                cut=cuts,
                ck=ck,
                line=part.get('line', M['line']),
                emissive=M['emissive'],
                two_sided=M['two_sided'],
                mode=mode,
                n=n,
                cut_mode=cmode,
                cut_n=cn,
                groove=groove,
                priority=float(part.get('priority', 1.0)),
                min_cover=part.get('min_cover'),
            )
        )
        g = groups[-1]
        g.paint = _paint(ctx, name, part, space, m, w)
        g.frame = (space.o, space.R, space.s)
        g.mirror = bool(m)
    return groups, ctx.frames


def socket_points(spec, env, frames=None):
    """Model-space position of every socket ({name: xyz, or None while its `when` is false}).

    `frames` are the frames already built for this pose; any other frame a socket needs is built here.
    """
    ctx = Ctx(spec, env)
    ctx.frames = dict(frames or {})
    out = {}
    for name, sk in (spec.get('sockets') or {}).items():
        w = f'sockets.{name}'
        ctx.side(sk.get('_mirror', False))
        if 'when' in sk and not ctx.val(sk['when'], w + '.when'):
            out[name] = None
            continue
        frame = ctx.frame(sk['bone'], w + '.bone')
        ctx.side(sk.get('_mirror', False))
        off = ctx.val(sk.get('offset', [0, 0, 0]), w + '.offset', sk.get('_mirror', False), vec=True)
        out[name] = frame.apply(off)
    return out
