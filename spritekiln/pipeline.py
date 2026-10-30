"""Frame rendering with an on-disk cache and a memory-aware process pool (Windows-safe)."""

import os
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from typing import NamedTuple

import numpy as np

from . import backend, cache, system
from . import spec as specmod
from .anim import frames_of
from .errors import RenderError
from .paint import layers_of, surface
from .pixelize import aux_maps, compose, hx
from .render import Camera, Light, Scene, facing, shade, to_gbuffer
from .rig import build, rest_env, socket_points
from .sdf import rot_y

_SPEC_CACHE = {}
_FRAMES_CACHE = {}


def _stamp(files):
    return tuple(os.path.getmtime(f) if os.path.exists(f) else None for f in files)


def get_spec(path, size=None, draft=False):
    """The loaded spec, reused while neither the spec nor its palette files change. `draft`: one sample per
    pixel (spec.as_draft)."""
    key = (path, size, draft)
    hit = _SPEC_CACHE.get(key)
    if hit and hit[0] == _stamp([path] + hit[1].get('_files', [])):
        return hit[1]
    spec = specmod.load(path, size=size)
    if draft:
        specmod.as_draft(spec)
    _SPEC_CACHE[key] = (_stamp([path] + spec.get('_files', [])), spec)
    _FRAMES_CACHE.clear()  # keyed by the spec object; old entries are stale
    return spec


def _frames(path, size, anim, yaw, draft=False):
    """frames_of() memoized per worker: a job renders one frame but the animation is evaluated once."""
    spec = get_spec(path, size, draft)
    key = (path, size, anim, yaw, id(spec))
    if key not in _FRAMES_CACHE:
        _FRAMES_CACHE[key] = frames_of(spec, anim, yaw)
    return spec, _FRAMES_CACHE[key]


def _votes(groups, cam):
    """(weight, min_cover) of the pixel vote: None when every part keeps the defaults (priority 1, the camera's
    coverage), so the usual path stays exactly as it was."""
    w = np.array([g.priority for g in groups], float)
    mc = np.array([g.min_cover or cam.cover for g in groups], int)
    return (None if (w == 1).all() else w), (None if (mc >= cam.cover).all() else mc)


def render_buffers(spec, env, yaw, force=False):
    """(GBuffer, groups, rig frames, camera) of a pose, from the render cache when it has it."""
    cam = Camera.from_spec(spec)
    path = cache.entry(spec, env, yaw)
    groups, frames = build(spec, env)
    buf = None if force else cache.load(path)
    if buf is None:
        sc = Scene(groups, np.radians(yaw))
        samples = backend.render(sc, cam, Light(**spec['light']))
        buf = to_gbuffer(samples, len(groups), cam, *_votes(groups, cam), surface(sc, cam, samples))
        cache.save(path, buf)
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
    lift = float(np.clip(1 - r[1] * 0.8, 0.4, 1.0))  # shrink when airborne
    return (cx, cy + 0.5, sh.get('rx', 13.5) * lift, sh.get('ry', 4.5) * lift, rgba)


def anchors(groups, yaw, cam):
    """Each part's origin on screen in whole pixels (x, y): where its dither pattern starts."""
    R = rot_y(np.radians(yaw))  # model -> world, as render.Scene
    pts = [cam.project(R @ (g.frame[0] if getattr(g, 'frame', None) else np.zeros(3))) for g in groups]
    return np.round(np.array(pts, float).reshape(-1, 2)).astype(int)


class Frame(NamedTuple):
    """One rendered frame of one direction."""

    img: np.ndarray  # RGBA color
    normal: np.ndarray | None
    emissive: np.ndarray | None
    ms: int = 100
    events: list = []
    sockets: dict = {}  # name -> [x, y, depth] px from the pivot, or None while hidden
    materials: dict = {}  # material -> opaque pixels


def sockets_2d(spec, env, yaw, frames, cam):
    """Sockets in frame pixels relative to the pivot, plus depth: signed ground distance (px) from the
    character's vertical axis toward the viewer (> 0 in front of the body, < 0 behind)."""
    pts = socket_points(spec, env, frames)
    if not pts:
        return {}
    R = rot_y(np.radians(yaw))
    px, py = cam.project([0.0, 0.0, 0.0])
    axis_z = (R @ frames['root'].o)[2] if 'root' in frames else 0.0
    out = {}
    for name, p in pts.items():
        if p is None:
            out[name] = None
            continue
        w = R @ p
        x, y = cam.project(w)
        out[name] = [round(float(x - px), 2), round(float(y - py), 2), round(float((w[2] - axis_z) / cam.scale), 2)]
    return out


def render_frame(spec, env, yaw, force=False, maps=True):
    """Render one pose seen from `yaw` -> Frame (without timing; see _job)."""
    env = dict(env, yaw=float(yaw), dir=specmod.direction_name(yaw))  # per-direction cheats in bones/parts
    gb, groups, frames, cam = render_buffers(spec, env, yaw, force)
    G = gb.gid.astype(int)
    light = Light(**spec['light'])
    flat = spec['light'].get('mode') == 'flat'
    mats = spec['materials']
    rim = None
    if groups and any(mats[g.mat].get('rim') is not None for g in groups):  # rim strength per material
        per = [mats[g.mat]['rim'] if mats[g.mat].get('rim') is not None else light.rim_strength for g in groups]
        rim = np.array([*per, 0.0])[np.where(G >= 0, G, -1)]
    ndh = facing(gb, cam, light) if any(mats[g.mat].get('highlight') for g in groups) else None
    img = compose(
        G,
        shade(gb, cam, light, rim),
        gb.depth,
        groups,
        mats,
        shadow_for(spec, env, yaw, cam),
        flat,
        ndh,
        gb.normal.astype(float),
        cam,
        light.L,
        spec.get('render'),
        gb.paint.astype(int),
        layers_of(groups),
        anchors(groups, yaw, cam) if any(m.get('dither') for m in mats.values()) else None,
    )
    layers = layers_of(groups)
    P = gb.paint.astype(int)
    nm, em = aux_maps(img, G, gb.normal.astype(float), groups, mats, cam, P, layers) if maps else (None, None)
    mats = {}
    if groups:
        names = np.array([g.mat for g in groups] + [''])[np.where(G >= 0, G, -1)]
        if layers:  # painted pixels count for the paint's material
            names = np.where(P >= 0, np.array([lay.material for lay in layers] + [''])[np.where(P >= 0, P, -1)], names)
        visible = names[(G >= 0) & (img[..., 3] == 255)]
        u, c = np.unique(visible, return_counts=True)
        mats = {str(k): int(v) for k, v in zip(u, c)}
    return Frame(img, nm, em, sockets=sockets_2d(spec, env, yaw, frames, cam), materials=mats)


def frame_image(spec, env, yaw, force=False, maps=True):
    """(color, normal, emissive) of one pose seen from `yaw`."""
    f = render_frame(spec, env, yaw, force, maps)
    return f.img, f.normal, f.emissive


def parts_mask(spec, env, yaw, parts):
    """The pixels of one pose (seen from `yaw`) that show any of the `parts` (part names): a bool array the size
    of the frame. Reads the render cache that render_frame filled."""
    env = dict(env, yaw=float(yaw), dir=specmod.direction_name(yaw))
    gb, groups, _, _ = render_buffers(spec, env, yaw)
    if not groups:
        return np.zeros(gb.gid.shape, bool)
    G = gb.gid.astype(int)
    hit = np.array([g.name.split(':')[0] in parts for g in groups] + [False])
    return hit[np.where(G >= 0, G, -1)]


def _job(args):
    path, size, anim, d_name, yaw, i, force, draft = args
    if anim:
        spec, frames = _frames(path, size, anim, yaw, draft)
        env, ms, ev = frames[i]
    else:
        spec = get_spec(path, size, draft)
        env, ms, ev = rest_env(spec, yaw), 100, []
    return (anim, d_name, i), render_frame(spec, env, yaw, force)._replace(ms=ms, events=ev)


# ---------------------------------------------------------------- memory-aware pool


def worker_mb(spec):
    """Conservative peak memory of one render worker, calibrated on Templar/Huntress/gargoyle (1.5x margin)."""
    rays = (spec['size'] * int(spec['camera'].get('supersample', 3))) ** 2
    groups = len(spec['parts']) + 8  # smear arcs add a few groups
    return 1.5 * (40 + rays * (groups + 30) * 8 / system.MB)


def main_mb(spec, n_frames):
    """Memory of the coordinating process: finished frames (color, normal, emissive) and the atlases."""
    return 60 + n_frames * spec['size'] ** 2 * 4 * 3 * 3.5 / system.MB


def auto_jobs(spec, n_tasks, n_frames):
    """Worker count that fits the available RAM, keeping a reserve for the rest of the machine."""
    avail, total = system.memory_mb()
    cpus = max(1, system.cpu_count() // 2)  # beyond the physical cores renders get no faster
    if avail is None:
        return min(2, cpus, max(n_tasks, 1)), 'available memory unknown'
    reserve = max(1024, 0.10 * total)
    budget = avail - reserve - main_mb(spec, n_frames)
    jobs = int(max(1, min(cpus, n_tasks, budget // worker_mb(spec))))
    return jobs, f'{avail / 1024:.1f} GB available, ~{worker_mb(spec):.0f} MB per worker'


class Progress:
    """One-line progress on stderr (a bar on a terminal, a line every ~10% otherwise)."""

    def __init__(self, total, cached=0, stream=None):
        self.total, self.cached, self.done = total, cached, 0
        self.stream = stream or sys.stderr
        self.tty = hasattr(self.stream, 'isatty') and self.stream.isatty()
        self.t0 = time.time()
        self.next_mark = 0.1

    def step(self):
        self.done += 1
        frac = self.done / max(self.total, 1)
        rendered = max(self.done - self.cached, 0)
        rate = rendered / max(time.time() - self.t0, 1e-6)
        left = (self.total - self.done) / rate if rate > 0 else 0
        eta = f'{int(left // 60)}m{int(left % 60):02d}s'
        if self.tty:
            bar = '#' * int(frac * 24)
            self.stream.write(f'\r  [{bar:<24}] {self.done}/{self.total} frames  eta {eta} ')
            if self.done == self.total:
                self.stream.write('\n')
            self.stream.flush()
        elif frac >= self.next_mark or self.done == self.total:
            self.stream.write(f'  {self.done}/{self.total} frames ({frac:.0%})\n')
            self.stream.flush()
            while self.next_mark <= frac:
                self.next_mark += 0.1


def _run_pool(tasks, jobs, out, on_done):
    """Run tasks in `jobs` processes; returns the tasks left when a worker died (e.g. out of memory)."""
    pending = list(tasks)
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futures = {ex.submit(_job, t): t for t in pending}
        try:
            while futures:
                finished, _ = wait(futures, return_when=FIRST_COMPLETED)
                for fu in finished:
                    futures.pop(fu)
                    key, frame = fu.result()
                    out[key] = frame
                    on_done()
        except BrokenProcessPool:
            done = set(out)
            return [t for t in tasks if (t[2], t[3], t[5]) not in done]
        except BaseException:  # a frame failed (or Ctrl+C): do not render the rest before reporting it
            for fu in futures:
                fu.cancel()
            raise
    return []


def render_all(
    path,
    anims=None,
    dirs=None,
    jobs=None,
    force=False,
    progress=None,
    size=None,
    cache_max_mb=cache.DEFAULT_MAX_MB,
    log=None,
    draft=False,
):
    """Render every (animation, direction, frame). `progress`: True for the stderr bar, or a Progress-like
    object; `log`: callable for one-line notes (job count, resume, degraded pool); `draft`: one sample per
    pixel."""
    spec = get_spec(path, size, draft)
    anims = anims or list(spec['animations'])
    missing = [a for a in anims if a not in spec['animations']]
    if missing:
        raise specmod.SpecError(f'unknown animation(s) {missing} (have: {", ".join(spec["animations"])})')
    dlist = [(n, y) for n, y in spec['directions'] if not dirs or n in dirs]
    if not dlist:
        raise specmod.SpecError(f'no direction matches {dirs} (have: {", ".join(n for n, _ in spec["directions"])})')
    tasks, cached = [], 0
    for a in anims:
        for d, y in dlist:
            for i, (env, _, _) in enumerate(frames_of(spec, a, y)):
                tasks.append((path, size, a, d, y, i, force, draft))
                if not force and os.path.exists(cache.entry(spec, dict(env, yaw=float(y)), y)):
                    cached += 1
    log = log or (lambda msg: None)
    log(backend.note())
    if cached:
        log(f'resuming: {cached} of {len(tasks)} frames already in the cache')
    if jobs is None and backend.name() == 'numba':
        jobs = 1  # one process: the kernel already uses every core, at the memory of one interpreter
    elif jobs is None:
        jobs, why = auto_jobs(spec, len(tasks) - cached, len(tasks))
        log(f'jobs: {jobs} (auto: {why}; use --jobs to override)')
    if jobs > 1 and backend.name() == 'numba':  # share the cores among the worker processes
        os.environ.setdefault('NUMBA_NUM_THREADS', str(max(1, system.cpu_count() // jobs)))
    bar = Progress(len(tasks), cached) if progress is True else progress
    on_done = bar.step if bar else (lambda: None)

    system.limit_blas_threads()  # before the pool spawns its workers
    out = {}
    remaining = tasks
    try:
        while remaining:
            if jobs <= 1:
                for t in remaining:
                    key, frame = _job(t)
                    out[key] = frame
                    on_done()
                remaining = []
            else:
                remaining = _run_pool(remaining, jobs, out, on_done)
                if remaining:
                    jobs = max(1, jobs // 2)
                    log(
                        f'a render worker died (probably out of memory); {len(out)} frames done and cached, '
                        f'continuing with {jobs} job(s)'
                    )
    except MemoryError:
        raise RenderError(
            f'out of memory after {len(out)} of {len(tasks)} frames (finished frames are cached: '
            f'free some memory and run the same command to resume)'
        ) from None
    except KeyboardInterrupt:
        log(
            f'interrupted after {len(out)} of {len(tasks)} frames; finished frames are cached, '
            f'run the same command to resume'
        )
        raise
    if cache_max_mb:
        cache.prune(cache.spec_dir(spec), max_mb=cache_max_mb)
    return spec, anims, dlist, out
