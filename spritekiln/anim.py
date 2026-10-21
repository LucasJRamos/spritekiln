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


def _base(spec):
    from .rig import rest_env
    return rest_env(spec)


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


def frames_of(spec, name):
    """-> list of (env, duration_ms, events)."""
    if name not in spec['animations']:
        raise SpecError(f'animation "{name}" not in spec (have: {", ".join(spec["animations"])})')
    A = spec['animations'][name]
    base = _base(spec)
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
        d = ms[i] if isinstance(ms, list) else int(_eval(ms, env, f'animations.{name}.ms')) if isinstance(ms, str)             else int(ms)
        ev = events.get(i)
        out.append((env, int(d), [ev] if ev else []))
    return out
