"""Load, mirror and sanity-check SpriteKiln YAML specs."""

import copy
import os
import re

import yaml

from . import resources, schema
from .errors import SpriteKilnError

DIRECTIONS8 = [('s', 0), ('se', 45), ('e', 90), ('ne', 135), ('n', 180), ('nw', -135), ('w', -90), ('sw', -45)]
DIRECTIONS4 = [('s', 0), ('e', 90), ('n', 180), ('w', -90)]

# `view` presets: defaults a spec gets unless it sets the value itself
VIEWS = {
    'topdown': dict(pitch=38.0, directions=8, shadow=True),  # top-down 3/4 (RPG, twin-stick, tactics)
    'side': dict(pitch=0.0, directions=['e', 'w'], shadow=False),  # side-scroller / platformer profile
}


def direction_name(yaw):
    """Name of the direction nearest to `yaw` degrees ('s' for 0, 'e' for 90...)."""
    return min(DIRECTIONS8, key=lambda d: abs((float(yaw) - d[1] + 180) % 360 - 180))[0]


DEFAULT_CAMERA = dict(pitch=38.0, scale=0.048, center=[0.0, 1.0, 0.0], supersample=3, coverage=4)
DEFAULT_LIGHT = dict(
    dir=[-0.55, 1.0, 0.45], rim=[0.8, 0.35, -0.9], rim_strength=0.45, ambient=0.12, shadows=True, ao=True
)
DEFAULT_MATERIAL = dict(
    ramp=None,
    emissive=False,
    line=True,
    outline=True,
    two_sided=False,
    band=None,
    bands=None,
    line_band=1,
    glow=None,
    gamma=1.05,
)

_SIDE = re.compile(r'_L(?![A-Za-z0-9])')


class SpecError(SpriteKilnError, ValueError):
    pass


class _Loader(yaml.SafeLoader):
    """YAML 1.2-ish booleans: only true/false (so keys like `off`, `on`, `y`, `n` stay strings)."""


_Loader.yaml_implicit_resolvers = {
    k: [r for r in v if r[0] != 'tag:yaml.org,2002:bool'] for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver(
    'tag:yaml.org,2002:bool', re.compile(r'^(?:true|True|TRUE|false|False|FALSE)$'), list('tTfF')
)


def yload(fh):
    return yaml.load(fh, Loader=_Loader)


def _rename(obj):
    """Deep-rename _L -> _R in every string (keys and values)."""
    if isinstance(obj, str):
        return _SIDE.sub('_R', obj)
    if isinstance(obj, list):
        return [_rename(o) for o in obj]
    if isinstance(obj, dict):
        return {_rename(k): _rename(v) for k, v in obj.items()}
    return obj


def _is_left(name):
    return bool(_SIDE.search(name))


def mirror_section(sec):
    """For every entry named *_L create its *_R twin (unless explicitly defined)."""
    out = {}
    for name, val in (sec or {}).items():
        out[name] = val
    for name, val in (sec or {}).items():
        if _is_left(name):
            r = _SIDE.sub('_R', name)
            if r in out:
                continue
            twin = _rename(copy.deepcopy(val))
            if isinstance(twin, dict):
                twin['_mirror'] = True
            out[r] = twin
    return out


def load_palette(ref, base_dir):
    if isinstance(ref, dict):
        return ref
    path = ref if os.path.isabs(ref) else os.path.join(base_dir, ref)
    if not os.path.exists(path):
        path = resources.builtin_palette(ref) or path  # `palette: gothic` or a moved shared palette
    if not os.path.exists(path):
        raise SpecError(f'palette: file not found: {ref} (relative to {base_dir}, and not a built-in palette)')
    data = _read_yaml(path)
    return data.get('ramps', data)


def _read_yaml(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return yload(fh)
    except FileNotFoundError:
        raise SpecError(f'{path}: file not found') from None
    except yaml.MarkedYAMLError as e:
        m = e.problem_mark
        raise SpecError(f'{path}:{m.line + 1}:{m.column + 1}: YAML syntax: {e.problem}') from None


def load(path, size=None):
    """Read a spec. `size` re-renders it at another frame size, keeping the framing (`render --size`)."""
    raw = _read_yaml(path)
    if not isinstance(raw, dict):
        raise SpecError(f'{path}: spec must be a YAML mapping')
    base = os.path.dirname(os.path.abspath(path))
    version = raw.get('spritekiln', raw.get('pxforge'))
    warnings = []
    if version is None:
        warnings.append('no version header: add `spritekiln: 1` as the first line')
    elif version != 1:
        raise SpecError(f'{path}: spec version {version!r} is not supported (this spritekiln reads version 1)')
    s = dict(raw)
    s['_raw'] = raw
    s['_warnings'] = warnings
    s['_path'] = os.path.abspath(path)
    s['_dir'] = base
    s.setdefault('name', os.path.splitext(os.path.basename(path))[0])
    s.setdefault('kind', 'character')
    s.setdefault('size', 64)
    s.setdefault('view', 'topdown')
    if s['view'] not in VIEWS:
        raise SpecError(f'view: must be one of {", ".join(VIEWS)} (got {s["view"]!r})')
    preset = VIEWS[s['view']]
    cam = dict(DEFAULT_CAMERA, pitch=preset['pitch'])
    cam.update(s.get('camera') or {})
    s['camera'] = cam
    if size:
        new = int(size)
        cam['scale'] = cam['scale'] * s['size'] / new
        if new >= 128:
            cam['supersample'] = 2
            cam['coverage'] = 2
        sh = dict(s.get('shadow') or {})
        if sh:
            k = new / s['size']
            sh['rx'] = sh.get('rx', 13.5) * k
            sh['ry'] = sh.get('ry', 4.5) * k
            s['shadow'] = sh
        s['size'] = new
    li = dict(DEFAULT_LIGHT)
    li.update(s.get('light') or {})
    s['light'] = li

    d = s.get('directions', preset['directions'] if s['kind'] == 'character' else 1)
    if d == 8:
        s['directions'] = DIRECTIONS8
    elif d == 4:
        s['directions'] = DIRECTIONS4
    elif d == 1:
        s['directions'] = [('s', 0)]
    elif isinstance(d, list):
        lut = dict(DIRECTIONS8)
        bad = [x for x in d if x not in lut]
        if bad:
            raise SpecError(f'directions: unknown direction(s) {bad} (use {", ".join(lut)})')
        s['directions'] = [(x, lut[x]) for x in d]
    else:
        raise SpecError('directions must be 1, 4, 8 or a list like [s, e, n, w]')

    ramps = {}
    for p in (s.get('palette') or []) if isinstance(s.get('palette'), list) else [s.get('palette')]:
        if p:
            ramps.update(load_palette(p, base))
    ramps.update(s.get('ramps') or {})
    s['ramps'] = ramps

    mats = {}
    for name, m in (s.get('materials') or {}).items():
        mm = dict(DEFAULT_MATERIAL)
        mm.update(m or {})
        if mm['ramp'] is None:
            mm['ramp'] = name
        if isinstance(mm['ramp'], str):
            if mm['ramp'] not in ramps:
                raise SpecError(f'materials.{name}: ramp "{mm["ramp"]}" not found in palette ({", ".join(ramps)})')
            mm['colors'] = ramps[mm['ramp']]
        else:
            mm['colors'] = mm['ramp']
        if mm['emissive']:
            mm['outline'] = m.get('outline', False) if m else False
            mm['line'] = m.get('line', False) if m else False
        mats[name] = mm
    s['materials'] = mats

    s['channels'] = mirror_section(s.get('channels'))
    for k in list(s['channels']):
        if isinstance(s['channels'][k], dict):  # mirrored twin of a vector default
            s['channels'][k] = s['channels'][k].get('value')
    s['bones'] = mirror_section(s.get('bones'))
    s['ik'] = mirror_section(s.get('ik'))
    s['parts'] = mirror_section(s.get('parts'))
    s['sockets'] = mirror_section(s.get('sockets'))
    s.setdefault('animations', {})
    if 'shadow' not in s:  # a ground ellipse reads in top-down; a side view has the ground edge-on
        s['shadow'] = {'rx': 13.5 * s['size'] / 64, 'ry': 4.5 * s['size'] / 64} if preset['shadow'] else None
    return s


def validate(spec):
    """Problems that stop the spec from rendering (empty = OK), each prefixed with file:line:column."""
    return check(spec)[0]


def check(spec):
    """(errors, warnings): errors stop the spec from rendering; warnings flag likely mistakes such as unknown
    keys, which are otherwise ignored. Messages start with file:line:column when the place is known."""
    raw = spec.get('_raw')
    if raw is None:  # a spec dict built by hand
        return _problems(spec), []
    unknown, missing = schema.scan(raw)
    errors = [schema.describe_missing(p, k) for p, k in missing]
    warnings = list(spec.get('_warnings', [])) + [schema.describe_unknown(*u) for u in unknown]
    if not errors:
        errors = _problems(spec)
    if not errors:
        from .anim import timing_problems

        errors = timing_problems(spec)
    try:
        marks = schema.marks(spec['_path'], _Loader)
    except (OSError, yaml.YAMLError):
        marks = {}
    return [_located(m, spec, marks) for m in errors], [_located(m, spec, marks) for m in warnings]


def _located(message, spec, marks):
    pos = schema.locate(message, marks) or (1, 1)
    path = spec['_path']
    try:
        rel = os.path.relpath(path)
        path = rel if not rel.startswith('..') else path
    except ValueError:  # another drive on Windows
        pass
    return f'{path}:{pos[0]}:{pos[1]}: {message}'


def _problems(spec):
    from .anim import frames_of
    from .rig import build, rest_env, socket_points

    problems = []
    frames_known = set(spec['bones']) | {'root'}
    for ik in spec['ik'].values():
        frames_known |= {ik.get('joint'), ik.get('end')}
    for name, b in spec['bones'].items():
        par = b.get('parent', 'root')
        if par not in frames_known:
            problems.append(f'bones.{name}.parent: unknown frame "{par}"')
        if b.get('at') and b['at'] not in frames_known:
            problems.append(f'bones.{name}.at: unknown frame "{b["at"]}"')
    for name, p in spec['parts'].items():
        mats = p.get('materials') or [p.get('material')]
        for m in mats:
            if m not in spec['materials']:
                problems.append(f'parts.{name}.material: unknown material "{m}" (define it under materials:)')
        if not p.get('prims'):
            problems.append(f'parts.{name}: no prims')
    from .review import check_review_block

    problems += check_review_block(spec)
    for name, sk in spec['sockets'].items():
        if sk.get('bone') not in frames_known:
            problems.append(f'sockets.{name}.bone: unknown frame "{sk.get("bone")}"')
    if problems:
        return problems
    # every direction: channels and bones may depend on `yaw`/`dir`
    for d, yaw in spec['directions']:
        try:
            build(spec, rest_env(spec, yaw))
        except Exception as e:  # noqa: BLE001 - report any failure as a spec problem
            problems.append(f'rest pose ({d}): {e}')
            break
    for an in spec['animations']:
        count = None
        for d, yaw in spec['directions']:
            try:
                fr = frames_of(spec, an, yaw)
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                problems.append(msg if msg.startswith(f'animations.{an}') else f'animations.{an} ({d}): {msg}')
                break
            if count is not None and len(fr) != count:
                problems.append(f'animations.{an}: {len(fr)} frames in direction {d} but {count} in the others')
                break
            count = len(fr)
            failed = False
            for i, (env, _ms, _ev) in enumerate(fr):
                try:
                    socket_points(spec, env, build(spec, env)[1])
                except Exception as e:  # noqa: BLE001
                    problems.append(f'animations.{an} ({d}, frame {i}): {e}')
                    failed = True
                    break
            if failed:
                break
    return problems
