"""How a clip moves, without judging frames one by one: where the hands, feet and sockets travel (`spritekiln arcs`:
a sheet with every frame as a ghost and each track as a dotted path) and the ground speed a walk implies.

Tracks come from the rig alone, so the numbers cost no render; only the sheet's ghosts are rendered (cached).
"""

import os

import numpy as np

from . import spec as specmod
from .anim import frames_of, is_loop
from .errors import SpriteKilnError
from .render import Camera
from .rig import Ctx, rest_env, socket_points
from .sdf import rot_y

# track colours: distinct on the dark preview background and from each other
COLORS = [
    (255, 205, 60),
    (80, 220, 255),
    (255, 110, 150),
    (140, 255, 130),
    (200, 150, 255),
    (255, 150, 70),
    (255, 255, 255),
    (120, 170, 255),
]
GROUND = 0.25  # an IK end below this share of the model's height (rest pose) is a foot
CONTACT = 0.25  # a foot is planted while it is within this share of its lift from its lowest point


def _env(env, yaw):
    return dict(env, yaw=float(yaw), dir=specmod.direction_name(yaw))  # as pipeline.render_frame


def _points(spec, env, names):
    """Model-space origin of each frame or socket in `names` for one pose ({name: xyz or None})."""
    ctx = Ctx(spec, env)
    sockets = socket_points(spec, env) if any(n in spec['sockets'] for n in names) else {}
    out = {}
    for n in names:
        out[n] = sockets[n] if n in spec['sockets'] else ctx.frame(n, f'track {n}').o
    return out


def default_tracks(spec):
    """What a clip's arcs show unless told otherwise: every socket, the IK ends (hands, feet) and the head."""
    names = list(spec['sockets'])
    names += [ik['end'] for ik in spec['ik'].values() if ik.get('end') and ik['end'] not in names]
    if 'head' in spec['bones'] and 'head' not in names:
        names.append('head')
    return names


def known_tracks(spec):
    frames = set(spec['bones']) | {'root'} | set(spec['sockets'])
    for ik in spec['ik'].values():
        frames |= {ik.get('joint'), ik.get('end')} - {None}
    return frames


def tracks(spec, anim, yaw, names):
    """{name: [(x, y) in frame pixels, or None while a socket is off]} for every frame of `anim` seen from `yaw`."""
    cam = Camera.from_spec(spec)
    R = rot_y(np.radians(yaw))
    out = {n: [] for n in names}
    for env, _, _ in frames_of(spec, anim, yaw):
        for n, p in _points(spec, _env(env, yaw), names).items():
            out[n].append(None if p is None else tuple(float(v) for v in cam.project(R @ np.asarray(p, float))))
    return out


def feet(spec):
    """IK ends that rest near the ground: the feet of whatever walks."""
    yaw = spec['directions'][0][1]
    ends = [ik['end'] for ik in spec['ik'].values() if ik.get('end')]
    if not ends:
        return []
    pts = _points(spec, rest_env(spec, yaw), ends)
    top = max((float(np.asarray(Ctx(spec, rest_env(spec, yaw)).frame(b, b).o)[1]) for b in spec['bones']), default=0)
    return [n for n in ends if float(pts[n][1]) < GROUND * max(top, 1e-6)]


def ground_speed(spec, anim):
    """The speed at which the ground passes under the planted feet of a looping clip: {px_per_s, units_per_s,
    uneven, feet}, or None when the clip does not loop or no foot lifts. Move the character at this speed in the
    game and its feet do not skate. `uneven`: the spread of the planted feet's speed between frames (0 = constant;
    the sine-wave stance of a simple walk gives about 0.8)."""
    A = spec['animations'][anim]
    names = feet(spec)
    if not is_loop(A) or not names:
        return None
    yaw = spec['directions'][0][1]
    frames = frames_of(spec, anim, yaw)
    n = len(frames)
    if n < 3:
        return None
    scale = float(spec['camera']['scale'])
    pos = {f: [] for f in names}
    for env, _, _ in frames:
        for f, p in _points(spec, _env(env, yaw), names).items():
            pos[f].append(np.asarray(p, float))
    ms = [m for _, m, _ in frames]
    steps, walked, dist, secs = [], [], 0.0, 0.0
    for f in names:
        P = np.array(pos[f])
        lift = float(np.ptp(P[:, 1]))
        if lift < 0.5 * scale:  # this foot never leaves the ground: not a step
            continue
        down = P[:, 1] <= P[:, 1].min() + CONTACT * lift
        for i in range(n):
            j = (i + 1) % n
            if down[i] and down[j]:
                d = float(np.hypot(*(P[j] - P[i])[[0, 2]]))
                steps.append(d / (ms[i] / 1000.0))
                dist, secs = dist + d, secs + ms[i] / 1000.0
        walked.append(f)
    if len(steps) < 2:
        return None
    v = dist / secs  # the whole stance: what the game has to match
    if v < scale:  # under a pixel per second: the feet lift in place
        return None
    return dict(
        px_per_s=round(v / scale, 1),
        units_per_s=round(v, 3),
        uneven=round((max(steps) - min(steps)) / v, 2),
        feet=walked,
    )


def sheet(path, anim, dirs=None, track=None, scale=6, out=None, draft=False, jobs=None, log=None):
    """Write the arcs sheet of one clip: per direction, every frame as a ghost under the last one, and each track
    (default: sockets, IK ends, head) as a path with one dot per frame, bigger where an event fires. Dots close
    together are slow, far apart fast: arcs, anticipation and follow-through show at a glance.
    Returns {sheet, directions, tracks, frames, ground_speed}."""
    from PIL import Image, ImageDraw

    from . import preview
    from .export import BG, label, upscale
    from .pipeline import render_all

    spec = specmod.load(path)
    if anim not in spec['animations']:
        raise SpriteKilnError(f'animation "{anim}" not in spec (have: {", ".join(spec["animations"])})')
    names = list(track) if track else default_tracks(spec)
    unknown = [n for n in names if n not in known_tracks(spec)]
    if unknown:
        import difflib

        near = difflib.get_close_matches(unknown[0], sorted(known_tracks(spec)), n=1)
        hint = f' (did you mean {near[0]}?)' if near else ''
        raise SpriteKilnError(f'track: no bone, IK joint or socket {", ".join(unknown)}{hint}')
    if not names:
        raise SpriteKilnError('nothing to track: the spec has no sockets or IK chains; name bones with --track')
    spec, _, dlist, frames = render_all(os.path.abspath(path), [anim], dirs, jobs, log=log, draft=draft)
    n = len([k for k in frames if k[1] == dlist[0][0]])
    events = [bool(frames[(anim, dlist[0][0], i)].events) for i in range(n)]
    S = spec['size']
    cells, paths = [], []
    for d, yaw in dlist:
        ghost = np.zeros((S, S, 4), float)
        for i in range(n):
            img = frames[(anim, d, i)].img.astype(float)
            a = (img[..., 3:] / 255.0) * (1.0 if i == n - 1 else 0.28)
            ghost[..., :3] = ghost[..., :3] * (1 - a) + img[..., :3] * a
            ghost[..., 3:] = np.maximum(ghost[..., 3:], a * 255)
        cells.append(ghost.round().astype(np.uint8))
        paths.append(tracks(spec, anim, yaw, names))
    pts = [p for t in paths for line in t.values() for p in line if p]
    y0, y1, x0, x1 = preview.content_box(cells)
    if pts:  # a hand that leaves the body still shows
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x0, x1 = max(0, min(x0, int(min(xs)) - 2)), min(S, max(x1, int(max(xs)) + 3))
        y0, y1 = max(0, min(y0, int(min(ys)) - 2)), min(S, max(y1, int(max(ys)) + 3))
    cells = preview.crop(cells, (y0, y1, x0, x1))
    h, w = cells[0].shape[:2]
    head, foot = 16, 16 * (1 + (len(names) - 1) // 4)

    def size_at(k):
        return len(cells) * w * k, head + h * k + foot

    k = preview.fit_scale(size_at, scale)
    im = Image.new('RGBA', size_at(k), BG)
    draw = ImageDraw.Draw(im)
    r = max(1, k // 3)
    for c, ((d, _), cell) in enumerate(zip(dlist, cells)):
        ox = c * w * k
        im.alpha_composite(upscale(cell, k, None), (ox, head))
        label(im, d, (ox + 3, 1))
        for t, name in enumerate(names):
            col = COLORS[t % len(COLORS)] + (255,)
            line = [
                None if p is None else (ox + (p[0] - x0 + 0.5) * k, head + (p[1] - y0 + 0.5) * k)
                for p in paths[c][name]
            ]
            order = list(range(n)) + ([0] if is_loop(spec['animations'][anim]) else [])
            for a, b in zip(order, order[1:]):
                if line[a] and line[b]:
                    draw.line([line[a], line[b]], fill=col[:3] + (150,), width=1)
            for i, p in enumerate(line):
                if p:
                    q = r + 1 if events[i] else r
                    draw.ellipse([p[0] - q, p[1] - q, p[0] + q, p[1] + q], fill=col, outline=(0, 0, 0, 255))
            first = next((i for i, p in enumerate(line) if p), None)
            if first is not None:
                label(im, str(first), (line[first][0] + r + 2, line[first][1] - 6), fill=col)
    per_row = max(1, -(-len(names) // (foot // 16)))
    for t, name in enumerate(names):
        col = COLORS[t % len(COLORS)] + (255,)
        x = 4 + (t % per_row) * max(90, im.width // per_row)
        label(im, f'o {name}', (x, head + h * k + 2 + 16 * (t // per_row)), fill=col)
    out = out or os.path.join(spec['_dir'], 'out', f'arcs_{anim}{"_draft" if draft else ""}.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out)
    return dict(
        sheet=out,
        directions=[d for d, _ in dlist],
        tracks=names,
        frames=n,
        zoom=k,
        ground_speed=ground_speed(spec, anim),
    )
