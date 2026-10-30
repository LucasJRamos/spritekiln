"""Load, mirror and sanity-check SpriteKiln YAML specs."""

import copy
import json
import os
import re

import yaml

from . import resources, schema
from .errors import SpriteKilnError
from .pixelize import hx

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


def as_draft(sp):
    """Turn a loaded spec into its draft: one sample per pixel (`pose --draft`, `render --draft`). The camera
    is part of the render cache key, so draft frames never mix with full ones."""
    sp['camera'] = dict(sp['camera'], **DRAFT_CAMERA)
    return sp


DEFAULT_CAMERA = dict(pitch=38.0, scale=0.048, center=[0.0, 1.0, 0.0], supersample=3, coverage=4)
DRAFT_CAMERA = dict(supersample=1, coverage=1)  # one sample per pixel: about 6x faster, rougher edges
DEFAULT_LIGHT = dict(
    dir=[-0.55, 1.0, 0.45], rim=[0.8, 0.35, -0.9], rim_strength=0.45, ambient=0.12, shadows=True, ao=True, mode='baked'
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
    flat_band=None,
    finish=None,
    highlight=None,
    rim=None,
    thresholds=None,
    crease=None,
    edge_highlight=None,
    dither=None,
    line_color=None,
)
# `finish` presets (design 07): fields a material sets itself win over them
FINISHES = {
    'matte': dict(highlight=None, rim=0.15),
    'soft': dict(highlight=dict(size=0.9, max_px=8), rim=0.3),
    'metal': dict(highlight=dict(size=0.95, max_px=4), rim=0.6),
    'glossy': dict(highlight=dict(size=0.975, max_px=2), rim=0.45),
}
# The project style's render fields (design 11, `[style]` of spritekiln.toml) and the spec's `render:` block. A
# spec's own block wins over the style, a material's own fields over both; these defaults render as before.
RENDER = dict(
    outline='selective',
    outline_color=None,
    shading='soft',
    lines='depth',
    highlights=True,
    dither='none',
    light='classic',
    snap=False,
    crease_angle=50.0,
    min_run=2,
)
STYLE_RENDER = ('outline', 'outline_color', 'shading', 'lines', 'highlights', 'dither', 'light', 'snap')
RENDER_CHOICES = dict(
    outline=('selective', 'dark', 'colored', 'none'),
    shading=('soft', 'flat', 'toon'),
    lines=('depth', 'depth+normal', 'none'),
    dither=('none', 'bayer2', 'bayer4'),
    light=('classic', 'top', 'dramatic', 'soft', 'flat'),
)
# light presets: the fields of DEFAULT_LIGHT they change (keys of the spec's own `light:` win)
LIGHTS = {
    'classic': {},
    'top': dict(dir=[-0.2, 1.0, 0.25], rim_strength=0.3, ambient=0.16),
    'dramatic': dict(dir=[-1.0, 0.45, 0.3], rim_strength=0.7, ambient=0.03),
    'soft': dict(dir=[-0.45, 1.0, 0.6], rim_strength=0.25, ambient=0.32),
    'flat': dict(mode='flat'),
}
TOON = (0.3, 0.6)  # light values where `shading: toon` steps up a tone

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


def load_palette(ref, base_dir, used=None):
    """Ramps of a palette: a file relative to the spec, a name in the project's palettes folder
    (<specs>/palettes/<name>.yaml of spritekiln.toml) or a built-in name. `used` collects the file read."""
    if isinstance(ref, dict):
        return ref
    path = palette_path(ref, base_dir)
    if path is None:
        raise SpecError(
            f'palette: file not found: {ref} (relative to {base_dir}, in the project palettes folder, '
            'or a built-in palette)'
        )
    if used is not None:
        used.append(path)
    data = _read_yaml(path)
    return data.get('ramps', data)


def palette_path(ref, base_dir):
    path = ref if os.path.isabs(ref) else os.path.join(base_dir, ref)
    if os.path.exists(path):
        return path
    name = os.path.basename(ref) if ref.endswith('.yaml') else os.path.basename(ref) + '.yaml'
    from . import config

    cfg = config.load(base_dir)
    if cfg:
        shared = os.path.join(cfg['specs'], 'palettes', name)
        if os.path.exists(shared):
            return shared
    return resources.builtin_palette(ref)  # `palette: gothic` or a moved shared palette


def _read_yaml(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return yload(fh)
    except FileNotFoundError:
        raise SpecError(f'{path}: file not found') from None
    except yaml.MarkedYAMLError as e:
        m = e.problem_mark
        raise SpecError(f'{path}:{m.line + 1}:{m.column + 1}: YAML syntax: {e.problem}') from None


HEAD_KITS = ('head', 'hair', 'ponytail', 'bun')  # built-in kits of a character's head and hair (design 16)


def head_notes(own, resolved):
    """Warnings for a character over a built-in humanoid template: no `brief.head` (its head and hair are the
    template's neutral placeholders until the spec decides them), and a part of an inherited kit whose prims the
    spec replaces while the kit's other parts stay."""
    if 'kit' in own or own.get('name') == 'TEMPLATE':  # a kit file shown on its host, a template itself
        return []
    notes = []
    builtin = {os.path.normcase(os.path.abspath(resources.template(t))) for t in resources.templates()}
    over_template = any(os.path.normcase(f) in builtin for f in resolved.files)
    placeholder = over_template or any(u['kit'] in HEAD_KITS for u in resolved.uses.values())  # or a copy of one
    brief = own.get('brief') if isinstance(own.get('brief'), dict) else {}
    if placeholder and not str(brief.get('head') or '').strip():
        # (the hints name no other `path:`, so the warning points at this spec's brief)
        notes.append(
            "brief.head: describe this character's head, face and hair (hair style and length, fringe, jaw and "
            "chin, how much face the project's style shows), then model them: the template's head and hair are "
            "neutral placeholders. Fit the head and hair kits' params, swap the hair kit (ponytail, bun) or model "
            'them yourself as "Heads, faces and hair" in modeling.md shows; check them with `pose --focus head`'
        )
    mine = {str(u.get('as') or u.get('kit')) for u in own.get('use') or [] if isinstance(u, dict)}
    parts = own.get('parts') if isinstance(own.get('parts'), dict) else {}
    for name, use in resolved.uses.items():
        if name in mine:
            continue
        kit_parts = [p[1] for p in use['paths'] if len(p) == 2 and p[0] == 'parts']
        for p in kit_parts:
            if isinstance(parts.get(p), dict) and 'prims' in parts[p] and len(kit_parts) > 1:
                rest = ', '.join(q for q in kit_parts if q != p)
                notes.append(
                    f"parts.{p}.prims: replaces the shape of the {use['kit']} kit's {p}, but the kit's other parts "
                    f'stay ({rest}). To model all of it yourself, remove use.{name} too; to change it, give the '
                    f'kit other params in a `use` with as {name}'
                )
    return notes


def load(path, size=None, style=None):
    """Read a spec. `size` re-renders it at another frame size, keeping the framing (`render --size`). `style`:
    render fields that replace the project style's (`style preview`); the spec's `render:` block still wins."""
    raw = _read_yaml(path)
    if not isinstance(raw, dict):
        raise SpecError(f'{path}: spec must be a YAML mapping')
    resolved, own = None, raw
    if 'extends' in raw or 'use' in raw or 'kit' in raw:  # a base, kits, or a kit file shown on its host
        from .kits import resolve

        resolved = resolve(path, raw)
        raw = resolved.doc
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
    s['_files'] = list(resolved.files) if resolved else []  # files read (bases, kits, palettes, the style),
    # so long-running processes notice when they change
    s['_origins'] = resolved.origins if resolved else None  # where each item was written (bases and kits)
    s['_uses'] = resolved.uses if resolved else {}  # what each kit `use` added
    s.setdefault('name', os.path.splitext(os.path.basename(path))[0])
    s.setdefault('kind', 'character')
    if resolved and s['kind'] == 'character':
        warnings += head_notes(own, resolved)
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
            sh['rx'] = sh.get('rx', 13.5 * s['size'] / 64) * k  # the defaults scale with the spec's own size
            sh['ry'] = sh.get('ry', 4.5 * s['size'] / 64) * k
            s['shadow'] = sh
        s['size'] = new
    r = _render(s, base, style)
    li = dict(DEFAULT_LIGHT)
    li.update(LIGHTS[r['light']])
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
    s['mirrors'] = {}
    if s.get('mirror'):  # left-facing directions become flipped copies of their right-facing twins
        names = {y: n for n, y in s['directions']}
        s['mirrors'] = {n: names[-y] for n, y in s['directions'] if y < 0 and -y in names}
        s['mirrored_yaw'] = {n: y for n, y in s['directions'] if n in s['mirrors']}
        s['directions'] = [(n, y) for n, y in s['directions'] if n not in s['mirrors']]

    ramps = dict(resolved.kit_ramps) if resolved else {}  # the kits' own, where the palette has none
    for p in (s.get('palette') or []) if isinstance(s.get('palette'), list) else [s.get('palette')]:
        if p:
            ramps.update(load_palette(p, base, s['_files']))
    ramps.update(s.get('ramps') or {})
    s['ramps'] = ramps

    mats = {}
    for name, m in (s.get('materials') or {}).items():
        mm = dict(DEFAULT_MATERIAL)
        mm['outline'] = r['outline'] != 'none'
        mm['line'] = r['lines'] != 'none'
        mm['crease'] = True if r['lines'] == 'depth+normal' else None
        mm.update(m or {})
        for k, v in FINISHES.get(mm['finish'], {}).items():
            if not (m and k in m) and not (k == 'highlight' and not r['highlights']):
                mm[k] = copy.deepcopy(v)
        if mm['highlight'] is True:
            mm['highlight'] = dict(FINISHES['metal']['highlight'])
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
        _shading(mm, m or {}, r['shading'])
        mm['dither'] = None if mm['emissive'] else _dither(m or {}, r['dither'])
        mats[name] = mm
    _outline_colors(mats, r)
    s['materials'] = mats
    if r['snap'] and 'snap' not in raw:  # the style snaps root and the templates' torso
        s['snap'] = ['root'] + (['torso_rot'] if 'torso_rot' in (raw.get('bones') or {}) else [])

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
    elif isinstance(s['shadow'], dict):  # `shadow: {alpha: 90}`: the radii default to the frame size
        s['shadow'] = {'rx': 13.5 * s['size'] / 64, 'ry': 4.5 * s['size'] / 64, **s['shadow']}
    return s


def _render(s, base, override=None):
    """The spec's render settings: built-in defaults < the project style < `override` < its own `render:`."""
    from . import config

    r = dict(RENDER)
    cfg = config.load(base)
    if cfg:
        s['_files'].append(cfg['path'])
        st = cfg['style'] or {}
        r.update({k: st[k] for k in STYLE_RENDER if st.get(k) not in (None, '')})
    r.update({k: v for k, v in (override or {}).items() if v is not None})
    own = s.get('render') if isinstance(s.get('render'), dict) else {}
    r.update(own)
    for k, allowed in RENDER_CHOICES.items():
        if r[k] not in allowed:
            where = 'render' if k in own else "the project's style (spritekiln.toml)"
            raise SpecError(f'{k} {r[k]!r} in {where}: use one of {", ".join(allowed)}')
    s['render'] = r
    return r


def _shading(mm, own, shading):
    """A material's tones under `shading: flat` (its two lightest) or `toon` (three, in hard steps), unless it
    sets `bands` or `thresholds` itself. A highlight keeps the top tone."""
    if shading == 'soft' or mm['emissive'] or 'bands' in own or 'thresholds' in own:
        return
    n = len(mm['colors'])
    top = n - 1 - (1 if mm.get('highlight') and n > 3 else 0)
    lo = max(1 if n > 2 else 0, top - (1 if shading == 'flat' else 2))
    mm['bands'] = [lo, top]
    if shading == 'toon' and top > lo:
        mm['thresholds'] = list(TOON[: top - lo])


def _dither(own, style):
    """The dither pattern of a material: the style's, unless it says `dither: false`; `dither: true` asks for
    one when the style has none (bayer2)."""
    if own.get('dither') is False:
        return None
    if own.get('dither') is True:
        return style if style != 'none' else 'bayer2'
    return None if style == 'none' else style


def _darkness(color):
    """Sort key of the darkest colour: its brightest channel (a near-black beats a dark red), then luma."""
    r, g, b = hx(color)
    return max(r, g, b), 0.2126 * r + 0.7152 * g + 0.0722 * b


def _outline_colors(mats, r):
    """Each material's outline colour (`line_color`): its own when it sets one; under `outline: dark` one colour
    for all (the style's `outline_color`, or the darkest first tone of the spec's ramps, a near-black in most
    palettes); under `colored` its line tone (`line_band`); under `selective`, None: its darkest tone, as
    before."""
    if r['outline'] not in ('dark', 'colored'):
        return
    solid = [m for m in mats.values() if not m['emissive']]
    shared = r.get('outline_color') or min((m['colors'][0] for m in solid), key=_darkness, default=None)
    for m in mats.values():
        if m['line_color'] is None:
            line = m['colors'][min(m['line_band'], len(m['colors']) - 1)]
            m['line_color'] = shared if r['outline'] == 'dark' else line


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
    if not errors:
        warnings += geometry_notes(spec)
    marks = _marks_of(spec)
    return [_located(m, spec, marks) for m in errors], [_located(m, spec, marks) for m in warnings]


def _marks_of(spec):
    """{path: (file, line, column)}: where each item of the spec was written (its base or kit when it came from
    one)."""
    if spec.get('_origins') is not None:
        return {p: v[-1][:3] for p, v in spec['_origins'].items() if v}
    try:
        return {p: (spec['_path'], *lc) for p, lc in schema.marks(spec['_path'], _Loader).items()}
    except (OSError, yaml.YAMLError):
        return {}


def geometry_notes(spec):
    """Warnings found while building the rest pose: sizes under a pixel, polygons whose edges cross."""
    from .rig import build, rest_env

    notes = []
    try:
        build(spec, rest_env(spec, spec['directions'][0][1]), notes)
    except Exception:  # noqa: BLE001 - errors are reported by _problems
        return []
    seen, out = set(), []
    for n in notes:  # a mirrored _R twin repeats its _L source's note
        key = re.sub(r'_R(?![A-Za-z0-9])', '_L', n)
        if key not in seen:
            seen.add(key)
            out.append(n)
    return out


def quick_errors(spec):
    """The errors check() can find without building poses (what pose/render stop on before working)."""
    raw = spec.get('_raw')
    errors = [schema.describe_missing(p, k) for p, k in schema.scan(raw)[1]] if raw is not None else []
    errors = errors or _static_problems(spec)
    if not errors or raw is None:
        return errors
    marks = _marks_of(spec)
    return [_located(m, spec, marks) for m in errors]


def warnings_only(spec):
    """The warnings of check() without building every pose (what pose/render print before working)."""
    raw = spec.get('_raw')
    if raw is None:
        return []
    unknown, _ = schema.scan(raw)
    warnings = list(spec.get('_warnings', [])) + [schema.describe_unknown(*u) for u in unknown]
    if not warnings:
        return []
    marks = _marks_of(spec)
    return [_located(m, spec, marks) for m in warnings]


def _located(message, spec, marks):
    path, *pos = schema.locate(message, marks) or (spec['_path'], 1, 1)
    try:
        rel = os.path.relpath(path)
        path = rel if not rel.startswith('..') else path
    except ValueError:  # another drive on Windows
        pass
    return f'{path}:{pos[0]}:{pos[1]}: {message}'


def _problems(spec):
    return _static_problems(spec) or _pose_problems(spec)


def _static_problems(spec):
    """Problems found without building any pose (cheap: unknown frames, materials, empty parts...)."""
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
    for i, name in enumerate(spec.get('snap') or []):
        if name != 'root' and name not in spec['bones']:
            problems.append(f'snap[{i}]: "{name}" is not root or a bone (IK joints follow their bones)')
    for name, p in spec['parts'].items():
        mc = p.get('min_cover')
        if mc is not None and not (isinstance(mc, int) and 1 <= mc <= spec['camera']['supersample'] ** 2):
            problems.append(f"parts.{name}.min_cover: {mc!r} (a whole number of samples, 1 to the pixel's count)")
        if p.get('priority') is not None and not (isinstance(p['priority'], (int, float)) and p['priority'] > 0):
            problems.append(f'parts.{name}.priority: {p["priority"]!r} (a number above 0)')
    for name, p in spec['parts'].items():
        mats = p.get('materials') or [p.get('material')]
        for m in mats:
            if m not in spec['materials']:
                problems.append(f'parts.{name}.material: unknown material "{m}" (define it under materials:)')
        for i, layer in enumerate(p.get('paint') or []):
            m = layer.get('material') if isinstance(layer, dict) else None
            if m not in spec['materials']:
                problems.append(
                    f'parts.{name}.paint[{i}].material: unknown material "{m}" (define it under materials:)'
                )
        if not p.get('prims'):
            problems.append(f'parts.{name}: no prims')
    from .review import check_review_block

    problems += check_review_block(spec)
    for name, sk in spec['sockets'].items():
        if sk.get('bone') not in frames_known:
            problems.append(f'sockets.{name}.bone: unknown frame "{sk.get("bone")}"')
    for name, m in spec['materials'].items():
        for c in m.get('colors') or []:
            try:
                hx(c)
            except ValueError as e:
                problems.append(f'materials.{name}: {e}')
                break
    for name, A in spec['animations'].items():
        if 'keys' in A:
            if not A['keys']:
                problems.append(f'animations.{name}.keys: no keys')
            continue
        n = A.get('frames', 8)
        if not isinstance(n, int) or n < 1:
            problems.append(f'animations.{name}.frames: {n!r} (needs at least 1)')
            continue
        for k in A.get('events') or {}:
            if not str(k).lstrip('-').isdigit() or not 0 <= int(k) < int(n):
                problems.append(f'animations.{name}.events: frame {k} does not exist (frames 0..{int(n) - 1})')
    for name, m in spec['materials'].items():
        hl = m.get('highlight')
        if isinstance(hl, dict) and hl.get('band') is not None and not 0 <= hl['band'] < len(m.get('colors') or []):
            problems.append(
                f'materials.{name}.highlight.band: {hl["band"]} is outside its ramp (0..{len(m["colors"]) - 1})'
            )
        th = m.get('thresholds')
        if th is not None and (list(th) != sorted(th) or not all(0 <= t <= 1 for t in th)):
            problems.append(f'materials.{name}.thresholds: {th} (increasing light values between 0 and 1)')
        band = m.get('band')
        if m.get('emissive') and isinstance(band, int) and not 0 <= band < len(m.get('colors') or []):
            problems.append(f'materials.{name}.band: {band} is outside its ramp (0..{len(m["colors"]) - 1})')
    return problems


def _pose_problems(spec):
    """Problems found by building the rest pose and every frame (expressions, IK, sockets)."""
    from .anim import frames_of
    from .rig import build, rest_env, socket_points

    problems = []
    # every direction when channels or bones may depend on `yaw`/`dir`; otherwise one shows them all
    dirs = spec['directions']
    if not re.search(r'\b(yaw|dir)\b', json.dumps(spec.get('_raw') or {})):
        dirs = dirs[:1]
    for d, yaw in dirs:
        try:
            build(spec, rest_env(spec, yaw))
        except Exception as e:  # noqa: BLE001 - report any failure as a spec problem
            problems.append(f'rest pose ({d}): {e}')
            break
    for an in spec['animations']:
        count = None
        for d, yaw in dirs:
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
