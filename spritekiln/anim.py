"""Animation evaluation: expression cycles and pose-to-pose keys with tweens.

animations:
  idle:                      # cycle mode
    frames: 8
    ms: 130
    channels: {bob: "0.045*sin(p)", tail: "0.7*sin(p)"}
  attack:                    # key mode: one output frame per key (+ optional tweens)
    loop: false
    keys:
      - {ms: 90,  set: {bob: -0.03}}
      - {ms: 170, set: {...}, event: windup, tween: 1, ease: out}
"""

import re

import numpy as np

from .expr import ExprError, evaluate
from .spec import SpecError

EASE = {
    'linear': lambda x: x,
    'in': lambda x: x * x,
    'out': lambda x: 1 - (1 - x) ** 2,
    'inout': lambda x: x * x * (3 - 2 * x),
}


def is_loop(A):
    """Cycles (frames + channels) loop by default; key animations (attacks, hits) play once."""
    return bool(A.get('loop', 'keys' not in A))


def _base(spec, yaw):
    from .rig import rest_env

    return rest_env(spec, yaw)


def _interp(a, b, t):
    try:
        return np.asarray(a, float) * (1 - t) + np.asarray(b, float) * t
    except Exception:  # noqa
        return a if t < 0.5 else b


def _eval(v, env, where):
    try:
        return evaluate(v, env)
    except ExprError as e:
        raise ExprError(f'{where}: {e}') from None


def frames_of(spec, name, yaw=0.0):
    """-> list of (env, duration_ms, events) as seen from direction `yaw`: channel expressions can use `yaw`
    and `dir` to cheat per direction, as pixel artists do. The frame count never depends on the direction."""
    if name not in spec['animations']:
        raise SpecError(f'animation "{name}" not in spec (have: {", ".join(spec["animations"])})')
    A = spec['animations'][name]
    base = _base(spec, yaw)
    out = []
    if 'keys' in A:
        keys = A['keys']
        n_keys = len(keys)
        poses = []
        prev = dict(base)
        for i, k in enumerate(keys):
            env = dict(prev if k.get('carry', A.get('carry', False)) else base)
            env.update(p=i / n_keys * 2 * np.pi, t=i / max(n_keys - 1, 1), f=i, n=n_keys)
            for ch, v in (k.get('set') or {}).items():
                where = f'animations.{name}.keys[{i}].set.{ch}'
                if ch not in base:
                    raise SpecError(f'{where}: unknown channel "{ch}" (declare it under channels:)')
                env[ch] = _eval(v, env, where)
            poses.append((env, int(k.get('ms', A.get('ms', 100))), k.get('event')))
            prev = env
        loop = A.get('loop', False)
        for i, (env, ms, ev) in enumerate(poses):
            out.append((env, ms, [ev] if ev else []))
            tw = int(keys[i].get('tween', 0))
            if tw and (i + 1 < len(poses) or loop):
                nxt = poses[(i + 1) % len(poses)][0]
                ease = EASE[keys[i].get('ease', 'inout')]
                tms = int(keys[i].get('tween_ms', max(ms // (tw + 1), 40)))
                for j in range(1, tw + 1):
                    x = ease(j / (tw + 1))
                    e = {c: _interp(env[c], nxt[c], x) if c in nxt else env[c] for c in env}
                    out.append((e, tms, []))
        return out
    n = int(A.get('frames', 8))
    ms = A.get('ms', 100)
    events = A.get('events') or {}
    for i in range(n):
        env = dict(base)
        env.update(p=i / n * 2 * np.pi, t=i / n, f=i, n=n)
        for ch, v in (A.get('channels') or {}).items():
            where = f'animations.{name}.channels.{ch}'
            if ch not in base:
                raise SpecError(f'{where}: unknown channel "{ch}" (declare it under top-level channels:)')
            env[ch] = _eval(v, env, where)
        d = (
            ms[i]
            if isinstance(ms, list)
            else int(_eval(ms, env, f'animations.{name}.ms'))
            if isinstance(ms, str)
            else int(ms)
        )
        ev = events.get(i)
        out.append((env, int(d), [ev] if ev else []))
    return out


_DURATION = re.compile(r'^\s*([0-9]*\.?[0-9]+)\s*(f|ms)?\s*$')


def to_frames(value, fps):
    """A timing target in frames: 2 or '2f' (frames at `fps`), or '33ms'."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    m = _DURATION.match(str(value))
    if not m:
        raise SpecError(f'timing: cannot read {value!r} (use 2, "2f" or "33ms")')
    n = float(m.group(1))
    return n * fps / 1000 if m.group(2) == 'ms' else n


def timing_problems(spec, anims=None):
    """Check the `timing:` targets: when each event fires (docs/format.md, Timing) and each clip's total,
    in frames at `timing.fps` (60), within `timing.tolerance` frames (1)."""
    T = spec.get('timing') or {}
    fps = float(T.get('fps', 60))
    tol = float(T.get('tolerance', 1))
    found = {}
    for a, targets in T.items():
        if a in ('fps', 'tolerance') or (anims is not None and a not in anims):
            continue
        if a not in spec['animations']:
            found.setdefault(f'timing.{a}: unknown animation', [])
            continue
        for d, yaw in spec['directions']:
            frames = frames_of(spec, a, yaw)
            starts = np.concatenate([[0], np.cumsum([ms for _, ms, _ in frames])])
            for ev, target in (targets or {}).items():
                want = to_frames(target, fps)
                if ev == 'total':
                    got_ms = int(starts[-1])
                else:
                    hits = [i for i, (_, _, evs) in enumerate(frames) if ev in evs]
                    if not hits:
                        found.setdefault(f'timing.{a}.{ev}: the animation has no "{ev}" event', []).append(d)
                        continue
                    got_ms = int(starts[hits[0]])
                got = got_ms * fps / 1000
                if abs(got - want) > tol + 1e-9:
                    msg = (
                        f'timing.{a}.{ev}: at {got:.1f} f ({got_ms} ms) but the target is {want:g} f '
                        f'(+-{tol:g} f at {fps:g} fps)'
                    )
                    found.setdefault(msg, []).append(d)
    out = []
    for msg, dirs in found.items():
        every = len(dirs) == len(spec['directions'])
        out.append(msg if not dirs or every else f'{msg} in {", ".join(dirs)}')
    return out
