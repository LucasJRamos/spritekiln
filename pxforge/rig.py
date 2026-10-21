"""Spec + channel values -> coordinate frames -> SDF groups.

Mirroring convention: every *_L bone/ik/part is authored on the +X side. Its *_R twin is
evaluated with the *_R channels and every local vector is mirrored (x -> -x), Euler
rotations become (rx, -ry, -rz). *_R channels therefore use the same (outward positive)
values as *_L for a symmetric pose.
"""
import numpy as np

from .expr import evaluate, ExprError
from .sdf import (sphere, ellipsoid, round_cone, triangle, box, cylinder, torus, Group,
                  rot_x, rot_y, rot_z)

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
    x = np.cross(up, z)
    if np.linalg.norm(x) < 1e-6:
        x = np.cross([1.0, 0, 0], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], 1)


def rest_env(spec):
    env = {}
    for k, v in spec['channels'].items():
        env[k] = evaluate(v, {}) if not isinstance(v, (int, float)) else float(v)
    env.update(p=0.0, t=0.0, f=0, n=1, yaw=0.0)
    return env


class Ctx:
    def __init__(self, spec, env):
        self.spec = spec
        self.env = env
        self.frames = {}

    def val(self, v, where, mirror=False, vec=False):
        try:
            out = evaluate(v, self.env)
        except ExprError as e:
            raise ExprError(f'{where}: {e}')
        if vec:
            out = np.broadcast_to(np.asarray(out, float), (3,)).copy()
            if mirror:
                out = out * MIRROR
        return out

    def rot(self, v, where, mirror=False):
        r = np.broadcast_to(np.asarray(self.val(v, where), float), (3,)).copy()
        if mirror:
            r[1] = -r[1]; r[2] = -r[2]
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
            self.frames['root'] = Frame(np.asarray(r, float))
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
        pos = self.val(b.get('pos', [0, 0, 0]), w + '.pos', m, vec=True)
        R = self.rot(b.get('rot', [0, 0, 0]), w + '.rot', m)
        sc = np.broadcast_to(np.asarray(self.val(b.get('scale', 1.0), w + '.scale'), float), (3,))
        Rp = par.R if b.get('inherit_rot', True) else np.eye(3)
        sp_ = par.s if b.get('inherit_scale', True) else np.ones(3)
        if b.get('at'):
            o = self.frame(b['at'], w + '.at').o + par.R @ (par.s * pos)
        else:
            o = par.apply(pos)
        self.frames[name] = Frame(o, Rp @ R, sp_ * sc)
        self._stack = self._stack - {name}

    def _ik(self, name, ik):
        m = ik.get('_mirror', False)
        w = f'ik.{name}'
        a = self.frame(ik['start'], w + '.start')
        space = self.frame(ik.get('space', 'root'), w + '.space')
        tgt = space.apply(self.val(ik['target'], w + '.target', m, vec=True))
        psp = self.frame(ik.get('pole_space', ik.get('space', 'root')), w + '.pole_space')
        pole = psp.dir(self.val(ik.get('pole', [0, 0, 1]), w + '.pole', m, vec=True))
        l1, l2 = [float(x) for x in self.val(ik['lengths'], w + '.lengths')]
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
        if 'up' in ik:      # reference for the end frame's y axis (in pole_space)
            up = psp.dir(self.val(ik['up'], w + '.up', m, vec=True))
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


def _prims(ctx, part_name, part, space, m, prim_list, where_base):
    out = []
    us = space.uscale
    for i, pr in enumerate(prim_list):
        if not isinstance(pr, dict) or len(pr) != 1:
            raise ExprError(f'{where_base}[{i}]: each prim is a one-key mapping like {{sphere: {{...}}}}')
        kind, a = next(iter(pr.items()))
        w = f'{where_base}[{i}].{kind}'
        P = lambda key, d=None: ctx.point(a.get(key, d), space, f'{w}.{key}', m)  # noqa
        V = lambda key, d=None, vec=False: ctx.val(a.get(key, d), f'{w}.{key}', m and vec, vec=vec)  # noqa

        def rotm():
            if 'align' in a:
                p0 = ctx.point(a['align'][0], space, w + '.align', m)
                p1 = ctx.point(a['align'][1], space, w + '.align', m)
                Rb = basis_z(p1 - p0, space.R @ np.array([0, 1.0, 0]))
            else:
                Rb = space.R
            return Rb @ ctx.rot(a.get('rot', [0, 0, 0]), w + '.rot', m)

        if kind == 'sphere':
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
                o = mid - hub; o /= max(np.linalg.norm(o), 1e-9)
                cuts.append(sphere(mid + o * r * 0.62, r))
            out.append(('cuts', cuts))
        else:
            raise ExprError(f'{w}: unknown prim type "{kind}" '
                            '(sphere, ellipsoid, cone, chain, box, cylinder, torus, tri, membrane, arc)')
    return out


def _arc_groups(ctx, name, part, space, m, a, mats, w):
    a0 = float(ctx.val(a['a0'], w + '.a0')); a1 = float(ctx.val(a['a1'], w + '.a1'))
    r = float(ctx.val(a['r'], w + '.r'))
    width = float(ctx.val(a.get('width', 0.08), w + '.width'))
    fade = float(ctx.val(a.get('fade', 1.0), w + '.fade'))
    dip = float(ctx.val(a.get('dip', 0.12), w + '.dip'))
    c = ctx.point(a.get('c', [0, 0, 0]), space, w + '.c', m)
    n = int(a.get('segments', 9))
    ang = np.linspace(a0, a1, n)
    pts = [c + space.R @ np.array([np.sin(t) * r, -dip * np.sin((t - a0) / (a1 - a0 + 1e-9) * np.pi), np.cos(t) * r])
           for t in ang]
    buckets = {mm: [] for mm in mats}
    for i in range(n - 1):
        f = (i + 0.5) / (n - 1)
        wd = width * (0.25 + 0.75 * np.sin(np.pi * min(f * 1.15, 1.0))) * fade
        mat = mats[min(int(f * len(mats)), len(mats) - 1)]
        if wd > 0.008:
            buckets[mat].append(round_cone(pts[i], pts[i + 1], wd, wd * 0.9))
    return buckets


def build(spec, env):
    """Return list of sdf Groups for the given channel values."""
    ctx = Ctx(spec, env)
    mats = spec['materials']
    groups = []
    for name, part in spec['parts'].items():
        w = f'parts.{name}'
        m = part.get('_mirror', False)
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
                    groups.append(Group(f'{name}:{mat}', mat, prs, k=float(part.get('blend', 0.02)),
                                        line=False, emissive=M['emissive'], two_sided=M['two_sided']))
            continue
        prims = _prims(ctx, name, part, space, m, plist, w + '.prims')
        cuts = [c for p in prims if isinstance(p, tuple) for c in p[1]]
        prims = [p for p in prims if not isinstance(p, tuple)]
        for i, c in enumerate(part.get('cut') or []):
            cuts += _prims(ctx, name, part, space, m, [c], w + '.cut')
        mat = part['material']
        M = mats[mat]
        groups.append(Group(name, mat, prims, k=float(part.get('blend', 0.0)), cut=cuts,
                            ck=float(part.get('cut_blend', 0.01)),
                            line=part.get('line', M['line']), emissive=M['emissive'],
                            two_sided=M['two_sided']))
    return groups, ctx.frames
