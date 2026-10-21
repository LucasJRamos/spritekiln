"""Load, mirror and sanity-check pxforge YAML specs."""
import copy
import os
import re
import yaml

from . import resources

DIRECTIONS8 = [('s', 0), ('se', 45), ('e', 90), ('ne', 135), ('n', 180), ('nw', -135), ('w', -90), ('sw', -45)]
DIRECTIONS4 = [('s', 0), ('e', 90), ('n', 180), ('w', -90)]

DEFAULT_CAMERA = dict(pitch=38.0, scale=0.048, center=[0.0, 1.0, 0.0], supersample=3, coverage=4)
DEFAULT_LIGHT = dict(dir=[-0.55, 1.0, 0.45], rim=[0.8, 0.35, -0.9], rim_strength=0.45,
                     ambient=0.12, shadows=True, ao=True)
DEFAULT_MATERIAL = dict(ramp=None, emissive=False, line=True, outline=True, two_sided=False,
                        band=None, bands=None, line_band=1, glow=None, gamma=1.05)

_SIDE = re.compile(r'_L(?![A-Za-z0-9])')


class SpecError(ValueError):
    pass


class _Loader(yaml.SafeLoader):
    """YAML 1.2-ish booleans: only true/false (so keys like `off`, `on`, `y`, `n` stay strings)."""


_Loader.yaml_implicit_resolvers = {k: [r for r in v if r[0] != 'tag:yaml.org,2002:bool']
                                   for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()}
_Loader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|True|TRUE|false|False|FALSE)$'),
                              list('tTfF'))


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
        path = resources.builtin_palette(ref) or path      # `palette: gothic` or a moved shared palette
    with open(path, encoding='utf-8') as fh:
        data = yload(fh)
    return data.get('ramps', data)


def load(path):
    with open(path, encoding='utf-8') as fh:
        raw = yload(fh)
    if not isinstance(raw, dict):
        raise SpecError(f'{path}: spec must be a YAML mapping')
    base = os.path.dirname(os.path.abspath(path))
    s = dict(raw)
    s['_path'] = os.path.abspath(path)
    s['_dir'] = base
    s.setdefault('name', os.path.splitext(os.path.basename(path))[0])
    s.setdefault('kind', 'character')
    s.setdefault('size', 64)
    cam = dict(DEFAULT_CAMERA); cam.update(s.get('camera') or {}); s['camera'] = cam
    if os.environ.get('PXFORGE_SIZE'):                     # render --size override keeps the framing
        new = int(os.environ['PXFORGE_SIZE'])
        cam['scale'] = cam['scale'] * s['size'] / new
        if new >= 128:
            cam['supersample'] = 2; cam['coverage'] = 2
        sh = dict(s.get('shadow') or {})
        if sh:
            k = new / s['size']; sh['rx'] = sh.get('rx', 13.5) * k; sh['ry'] = sh.get('ry', 4.5) * k
            s['shadow'] = sh
        s['size'] = new
    li = dict(DEFAULT_LIGHT); li.update(s.get('light') or {}); s['light'] = li

    d = s.get('directions', 8 if s['kind'] == 'character' else 1)
    if d == 8:
        s['directions'] = DIRECTIONS8
    elif d == 4:
        s['directions'] = DIRECTIONS4
    elif d == 1:
        s['directions'] = [('s', 0)]
    elif isinstance(d, list):
        lut = dict(DIRECTIONS8)
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
        mm = dict(DEFAULT_MATERIAL); mm.update(m or {})
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
        if isinstance(s['channels'][k], dict):     # mirrored twin of a vector default
            s['channels'][k] = s['channels'][k].get('value')
    s['bones'] = mirror_section(s.get('bones'))
    s['ik'] = mirror_section(s.get('ik'))
    s['parts'] = mirror_section(s.get('parts'))
    s.setdefault('animations', {})
    if 'shadow' not in s:
        s['shadow'] = {'rx': 13.5 * s['size'] / 64, 'ry': 4.5 * s['size'] / 64}
    return s


def validate(spec):
    """Return a list of human readable problems (empty = OK)."""
    from .rig import build, rest_env
    from .anim import frames_of
    problems = []
    frames_known = set(spec['bones']) | {'root'}
    for ik_name, ik in spec['ik'].items():
        frames_known |= {ik.get('joint'), ik.get('end')}
    for name, b in spec['bones'].items():
        par = b.get('parent', 'root')
        if par not in frames_known:
            problems.append(f'bones.{name}.parent: unknown frame "{par}"')
        if b.get('at') and b['at'] not in frames_known:
            problems.append(f'bones.{name}.at: unknown frame "{b["at"]}"')
    for name, ik in spec['ik'].items():
        for key in ('start', 'joint', 'end', 'lengths', 'target'):
            if key not in ik:
                problems.append(f'ik.{name}: missing "{key}"')
    for name, p in spec['parts'].items():
        mats = p.get('materials') or [p.get('material')]
        for m in mats:
            if m not in spec['materials']:
                problems.append(f'parts.{name}.material: unknown material "{m}" (define it under materials:)')
        if not p.get('prims'):
            problems.append(f'parts.{name}: no prims')
    if problems:
        return problems
    try:
        build(spec, rest_env(spec))
    except Exception as e:  # noqa
        problems.append(f'rest pose: {e}')
    for an in spec['animations']:
        try:
            fr = frames_of(spec, an)
            for i, (env, ms, ev) in enumerate(fr):
                build(spec, env)
        except Exception as e:  # noqa
            problems.append(f'animations.{an}: {e}')
    return problems
