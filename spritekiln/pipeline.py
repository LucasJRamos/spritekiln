"""Frame rendering with an on-disk cache and a memory-aware process pool (Windows-safe)."""
import os
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool

import numpy as np

from . import cache
from . import spec as specmod
from . import system
from .anim import frames_of
from .errors import RenderError
from .pixelize import aux_maps, compose, hx
from .render import Camera, Light, Scene, render, to_pixels
from .rig import build, rest_env

_SPEC_CACHE = {}
_FRAMES_CACHE = {}


def get_spec(path, size=None):
    m = os.path.getmtime(path)
    key = (path, size)
    if key not in _SPEC_CACHE or _SPEC_CACHE[key][0] != m:
        _SPEC_CACHE[key] = (m, specmod.load(path, size=size))
    return _SPEC_CACHE[key][1]


def _frames(path, size, anim):
    """frames_of() memoized per worker: a job renders one frame but the animation is evaluated once."""
    spec = get_spec(path, size)
    key = (path, size, anim, id(spec))
    if key not in _FRAMES_CACHE:
        _FRAMES_CACHE[key] = frames_of(spec, anim)
    return spec, _FRAMES_CACHE[key]


def render_buffers(spec, env, yaw, force=False):
    cam = Camera.from_spec(spec)
    path = cache.entry(spec, env, yaw)
    groups, frames = build(spec, env)
    buf = None if force else cache.load(path)
    if buf is None:
        sc = Scene(groups, np.radians(yaw))
        buf = to_pixels(*render(sc, cam, Light(**spec['light'])), len(groups), cam)
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
    path, size, anim, d_name, yaw, i, force = args
    if anim:
        spec, frames = _frames(path, size, anim)
        env, ms, ev = frames[i]
    else:
        spec = get_spec(path, size)
        env, ms, ev = rest_env(spec), 100, []
    img, nm, em = frame_image(spec, env, yaw, force)
    return (anim, d_name, i), img, nm, em, ms, ev


# ---------------------------------------------------------------- memory-aware pool

def worker_mb(spec):
    """Conservative peak memory of one render worker, calibrated on Templar/Huntress/gargoyle (1.5x margin)."""
    rays = (spec['size'] * int(spec['camera'].get('supersample', 3))) ** 2
    groups = len(spec['parts']) + 8                       # smear arcs add a few groups
    return 1.5 * (40 + rays * (groups + 30) * 8 / system.MB)


def main_mb(spec, n_frames):
    """Memory of the coordinating process: finished frames (color, normal, emissive) and the atlases."""
    return 60 + n_frames * spec['size'] ** 2 * 4 * 3 * 3.5 / system.MB


def auto_jobs(spec, n_tasks, n_frames):
    """Worker count that fits the available RAM, keeping a reserve for the rest of the machine."""
    avail, total = system.memory_mb()
    cpus = max(1, system.cpu_count() // 2)                # beyond the physical cores renders get no faster
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
                    t = futures.pop(fu)
                    r = fu.result()
                    out[r[0]] = r[1:]
                    on_done()
        except BrokenProcessPool:
            done = set(out)
            return [t for t in tasks if (t[2], t[3], t[5]) not in done]
    return []


def render_all(path, anims=None, dirs=None, jobs=None, force=False, progress=None, size=None,
               cache_max_mb=cache.DEFAULT_MAX_MB, log=None):
    """Render every (animation, direction, frame). `progress`: True for the stderr bar, or a Progress-like
    object; `log`: callable for one-line notes (job count, resume, degraded pool)."""
    spec = get_spec(path, size)
    anims = anims or list(spec['animations'])
    missing = [a for a in anims if a not in spec['animations']]
    if missing:
        raise specmod.SpecError(f'unknown animation(s) {missing} (have: {", ".join(spec["animations"])})')
    dlist = [(n, y) for n, y in spec['directions'] if not dirs or n in dirs]
    if not dlist:
        raise specmod.SpecError(f'no direction matches {dirs} (have: {", ".join(n for n, _ in spec["directions"])})')
    tasks, cached = [], 0
    for a in anims:
        frames = frames_of(spec, a)
        for d, y in dlist:
            for i, (env, _, _) in enumerate(frames):
                tasks.append((path, size, a, d, y, i, force))
                if not force and os.path.exists(cache.entry(spec, dict(env, yaw=float(y)), y)):
                    cached += 1
    log = log or (lambda msg: None)
    if cached:
        log(f'resuming: {cached} of {len(tasks)} frames already in the cache')
    if jobs is None:
        jobs, why = auto_jobs(spec, len(tasks) - cached, len(tasks))
        log(f'jobs: {jobs} (auto: {why}; use --jobs to override)')
    bar = Progress(len(tasks), cached) if progress is True else progress
    on_done = bar.step if bar else (lambda: None)

    system.limit_blas_threads()                       # before the pool spawns its workers
    out = {}
    remaining = tasks
    try:
        while remaining:
            if jobs <= 1:
                for t in remaining:
                    r = _job(t)
                    out[r[0]] = r[1:]
                    on_done()
                remaining = []
            else:
                remaining = _run_pool(remaining, jobs, out, on_done)
                if remaining:
                    jobs = max(1, jobs // 2)
                    log(f'a render worker died (probably out of memory); {len(out)} frames done and cached, '
                        f'continuing with {jobs} job(s)')
    except MemoryError:
        raise RenderError(f'out of memory after {len(out)} of {len(tasks)} frames (finished frames are cached: '
                          f'free some memory and run the same command to resume)') from None
    except KeyboardInterrupt:
        log(f'interrupted after {len(out)} of {len(tasks)} frames; finished frames are cached, '
            f'run the same command to resume')
        raise
    if cache_max_mb:
        cache.prune(cache.spec_dir(spec), max_mb=cache_max_mb)
    return spec, anims, dlist, out
