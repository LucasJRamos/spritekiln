"""Frame rendering with on-disk cache and multiprocessing (Windows-safe)."""
import hashlib
import json
import os
import pickle
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from . import spec as specmod
from .anim import frames_of
from .rig import build, rest_env
from .render import Camera, Light, Scene, render, to_pixels
from .pixelize import compose, aux_maps, hx

_SPEC_CACHE = {}


def get_spec(path):
    m = os.path.getmtime(path)
    if path not in _SPEC_CACHE or _SPEC_CACHE[path][0] != m:
        _SPEC_CACHE[path] = (m, specmod.load(path))
    return _SPEC_CACHE[path][1]


def _geom_key(spec, env, yaw):
    """Hash of everything that changes geometry/lighting (not palette)."""
    payload = dict(bones=spec['bones'], ik=spec['ik'], parts=spec['parts'], camera=spec['camera'],
                   light=spec['light'], size=spec['size'],
                   mats={k: (v['emissive'], v['two_sided']) for k, v in spec['materials'].items()},
                   env={k: np.asarray(v).round(6).tolist() for k, v in env.items()}, yaw=yaw, v=3)
    return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:20]


def cache_dir(spec):
    d = os.path.join(spec['_dir'], '.pxcache', spec['name'])
    os.makedirs(d, exist_ok=True)
    return d


def render_buffers(spec, env, yaw, force=False):
    cam = Camera.from_spec(spec)
    key = _geom_key(spec, env, yaw)
    path = os.path.join(cache_dir(spec), key + '.pkl')
    groups, frames = build(spec, env)
    if os.path.exists(path) and not force:
        with open(path, 'rb') as fh:
            buf = pickle.load(fh)
    else:
        sc = Scene(groups, np.radians(yaw))
        buf = to_pixels(*render(sc, cam, Light(**spec['light'])), len(groups), cam)
        with open(path, 'wb') as fh:
            pickle.dump(buf, fh)
    return buf, groups, frames, cam


def shadow_for(spec, env, yaw, cam):
    sh = spec.get('shadow')
    if not sh:
        return None
    from .sdf import rot_y
    r = np.asarray(env.get('root', [0, 0, 0]), float)
    off = np.asarray(sh.get('offset', [0, 0, 0]), float)
    w = rot_y(np.radians(yaw)) @ (r + off)
    w[1] = 0.0
    cx, cy = cam.project(w)
    rgba = tuple(hx(sh.get('color', '#0b0712'))) + (int(sh.get('alpha', 120)),)
    lift = float(np.clip(1 - r[1] * 0.8, 0.4, 1.0))       # shrink when airborne
    return (cx, cy + 0.5, sh.get('rx', 13.5) * lift, sh.get('ry', 4.5) * lift, rgba)


def frame_image(spec, env, yaw, force=False, maps=True):
    env = dict(env, yaw=float(yaw))          # expressions may cheat per direction with `yaw`
    (G, V, D, N), groups, frames, cam = render_buffers(spec, env, yaw, force)
    img = compose(G, V, D, groups, spec['materials'], shadow_for(spec, env, yaw, cam))
    if not maps:
        return img, None, None
    nm, em = aux_maps(img, G, N, groups, spec['materials'], cam)
    return img, nm, em


def _job(args):
    path, anim, d_name, yaw, i, force = args
    spec = get_spec(path)
    env, ms, ev = frames_of(spec, anim)[i] if anim else (rest_env(spec), 100, [])
    img, nm, em = frame_image(spec, env, yaw, force)
    return (anim, d_name, i), img, nm, em, ms, ev


def render_all(path, anims=None, dirs=None, jobs=None, force=False, progress=print):
    spec = get_spec(path)
    anims = anims or list(spec['animations'])
    dlist = [(n, y) for n, y in spec['directions'] if not dirs or n in dirs]
    tasks = []
    for a in anims:
        n = len(frames_of(spec, a))
        for d, y in dlist:
            for i in range(n):
                tasks.append((path, a, d, y, i, force))
    out = {}
    jobs = jobs or max(1, (os.cpu_count() or 2) - 1)
    done = 0
    if jobs == 1:
        it = map(_job, tasks)
        for r in it:
            out[r[0]] = r[1:]; done += 1
            if progress and done % 8 == 0:
                progress(f'  {done}/{len(tasks)} frames')
    else:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            for r in ex.map(_job, tasks, chunksize=1):
                out[r[0]] = r[1:]; done += 1
                if progress and done % 8 == 0:
                    progress(f'  {done}/{len(tasks)} frames')
    return spec, anims, dlist, out
