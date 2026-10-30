"""The project's art style: the answers of the style interview, kept in the `[style]` table of spritekiln.toml.

The AI asks the user a few questions before the first asset of a project (docs/agent/style.md) and records
the answers with `spritekiln style set`. The numeric ones become `[defaults]` for `spritekiln new`: the view
and its camera pitch, `camera.scale` and `size` from the height of a character on screen, the directions,
mirroring and the palette. The rest (colours, outline, shading, proportions, face, animation, references, notes)
guides whoever models and animates. `spritekiln style` shows the record, or suggests answers from the
specs a project already has, and lists the specs that no longer match it.

The look fields (outline, outline_color, shading, lines, highlights, dither, light, snap) are applied by the
renderer to every spec of the project (spec.RENDER; a spec's `render:` block and a material's own fields win),
and `spritekiln style preview` shows their choices side by side.
"""

import datetime
import os
from collections import Counter

from . import config
from .errors import SpriteKilnError
from .spec import RENDER, RENDER_CHOICES, STYLE_RENDER

FIELDS = (
    'view',
    'height',
    'scale',
    'size',
    'directions',
    'mirror',
    'palette',
    'colors',
    'outline',
    'outline_color',
    'shading',
    'lines',
    'highlights',
    'dither',
    'light',
    'proportions',
    'face',
    'animation',
    'snap',
    'references',
    'notes',
)
CHOICES = {
    'view': ('topdown', 'side'),
    **RENDER_CHOICES,
    'proportions': ('stylized', 'chibi', 'realistic'),
    'face': ('minimal', 'simple', 'detailed'),
    'animation': ('fluid', 'snappy'),
}
YES_NO = ('mirror', 'highlights', 'snap')
RECOMMENDED = dict(
    outline='selective',
    outline_color='',
    shading='soft',
    lines='depth',
    highlights=True,
    dither='none',
    light='classic',
    proportions='stylized',
    face='minimal',
    animation='fluid',
    snap=False,
)
NOTES = {
    'height': 'px on screen of a human-sized character',
    'scale': 'camera.scale of every asset (from height)',
    'size': 'frame px for that character',
    'outline_color': 'with outline "dark"; empty: the darkest tone of the ramps',
    'snap': 'root and torso move in whole pixels',
    'face': 'minimal: eyes only, no nose; simple: + a hint of brow or nose on big heads; detailed',
}
PREVIEW_FIELDS = ('outline', 'shading', 'lines', 'highlights', 'dither', 'light')
PITCH = {'topdown': 38, 'side': 0}
# How tall the template humanoid stands on screen in world units (its height in pixels x camera.scale),
# measured on the templates; the 38 degree pitch of the top-down view shortens it.
SCREEN_HEIGHT = {'topdown': 1.76, 'side': 2.0}
SIZES = (16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512)
ROOM = 1.25  # frame size over character height: room for hats, weapons and big gestures
HEIGHTS = (12, 400)
DEFAULT_SCALE = 0.04


def camera_scale(view, height):
    """camera.scale that makes a human-sized character `height` pixels tall (4 significant digits)."""
    return float(f'{SCREEN_HEIGHT[view] / height:.4g}')


def height_for(view, scale):
    return round(SCREEN_HEIGHT[view] / scale)


def frame_size(height):
    """The smallest common frame size with room for a character `height` pixels tall."""
    for s in SIZES:
        if s >= height * ROOM:
            return s
    raise SpriteKilnError(f'height {height}: too tall for a frame of {SIZES[-1]} px')


def _project(start):
    cfg = config.load(start)
    if not cfg:
        raise SpriteKilnError(
            'no spritekiln.toml here or above: the art style belongs to a project set up with `spritekiln init`'
        )
    return cfg


def guide_path(root):
    """Where the project keeps style.md (relative to its root), or None."""
    from .scaffold import DOCS_DIR

    rel = f'{DOCS_DIR}/style.md'
    return rel if os.path.isfile(os.path.join(root, rel)) else None


def status(start=None):
    """The project's style: {recorded, style, defaults, ...}. Unrecorded: `suggested` answers (from the
    existing specs, or the project defaults) and what to do next. Recorded: `off_style` specs."""
    cfg = _project(start)
    st = dict(cfg['style'])
    if 'recorded' in st:
        st['recorded'] = str(st['recorded'])  # a TOML date; JSON wants text
    specs = _spec_facts(cfg['specs'], cfg['root'])
    out = dict(
        project=cfg['root'],
        file=cfg['path'],
        recorded=bool(st),
        style=st,
        defaults=cfg['defaults'],
        guide=guide_path(cfg['root']),
    )
    if st:
        out['off_style'] = off_style(specs, st, cfg['defaults'])
    else:
        out['suggested'] = suggest(specs, cfg)
        where = out['guide'] or "guide('style')"
        out['next'] = (
            f'No art style is recorded for this project yet. Before generating any asset, interview the user '
            f'with the style questions ({where}), confirm a summary, then record the answers with '
            '`spritekiln style set` (MCP: style with `answers`).'
        )
    return out


def missing_note(start=None):
    """A note for `new` when the project around `start` has no recorded style yet, else None."""
    cfg = config.load(start)
    if cfg and not cfg['style']:
        return (
            'no art style recorded for this project yet: before the first asset, the user answers the style '
            'questions (`spritekiln style`)'
        )
    return None


def record(answers, start=None, today=None):
    """Merge `answers` ({field: value}; None = unchanged) into the project's style and write it with the
    [defaults] that follow from it. The first record fills unanswered fields with the suggested and
    recommended values (listed in `defaulted`). Returns the new status plus `changed` and `defaulted`."""
    cfg = _project(start)
    given = {k: v for k, v in answers.items() if v is not None}
    unknown = sorted(set(given) - set(FIELDS))
    if unknown:
        raise SpriteKilnError(f'unknown style field(s) {", ".join(unknown)} (use {", ".join(FIELDS)})')
    given = _clean(given)
    old = dict(cfg['style'])
    first = not old
    base = {**_baseline(cfg), **old}  # a hand-edited record may lack fields
    new = {k: base.get(k) for k in FIELDS}
    new.update(given)
    view = new['view']
    height_changed = 'height' in given and given['height'] != base.get('height')
    view_changed = 'view' in given and view != base.get('view')
    if (height_changed or view_changed) and 'scale' not in given:
        new['scale'] = camera_scale(view, new['height'])  # the same pixels per character in the new view
    elif 'scale' in given and 'height' not in given:
        new['height'] = height_for(view, new['scale'])
    if height_changed and 'size' not in given:
        new['size'] = frame_size(new['height'])
    if view == 'side' and 'directions' not in given:
        new['directions'] = 2
    elif view == 'topdown' and new['directions'] not in (4, 8):
        new['directions'] = 8
    _check(new)
    values = {'recorded': today or datetime.date.today(), **{k: new[k] for k in FIELDS}}
    config.set_tables(cfg['path'], {'defaults': _defaults(cfg['defaults'], new), 'style': values}, {'style': NOTES})
    out = status(start)
    out['changed'] = [k for k in FIELDS if new[k] != old.get(k)] if not first else list(FIELDS)
    derived = {'scale', 'size'} if 'height' in given else {'height'} if 'scale' in given else set()
    out['defaulted'] = [k for k in FIELDS if k not in given and k not in derived] if first else []
    return out


def describe(st):
    """Readable lines of a recorded style (a record made before a field existed shows its default)."""
    refs = '; '.join(st.get('references') or []) or '-'
    dirs = st.get('directions')
    mirror = ', mirrored (the engine flips the left-facing ones)' if st.get('mirror') else ''
    view = st.get('view')
    r = {**RENDER, **{k: st[k] for k in STYLE_RENDER if st.get(k) not in (None, '')}}
    color = f' ({r["outline_color"]})' if r['outline'] == 'dark' and r['outline_color'] else ''
    snap = ', root and torso snapped to whole pixels' if r['snap'] else ''
    return [
        f'  view         {view} (camera pitch {PITCH.get(view, "?")})',
        f'  characters   {st.get("height")} px tall (camera.scale {st.get("scale")}), frame {st.get("size")} px',
        f'  directions   {dirs}{mirror}',
        f'  palette      {st.get("palette")}' + (f'   colours: {st["colors"]}' if st.get('colors') else ''),
        f'  outline      {r["outline"]}{color}',
        f'  shading      {r["shading"]}; lines {r["lines"]}; highlights {"yes" if r["highlights"] else "no"}; '
        f'dither {r["dither"]}',
        f'  light        {r["light"]}',
        f'  proportions  {st.get("proportions")}',
        f'  face         {st.get("face") or RECOMMENDED["face"] + " (not recorded: the default)"}',
        f'  animation    {st.get("animation")}{snap}',
        f'  references   {refs}',
        f'  notes        {st.get("notes") or "-"}',
    ]


def suggest_args(s):
    """`spritekiln style set` options for suggested answers."""
    keys = ('view', 'height', 'size', 'directions', 'palette')
    return ' '.join(f'--{k} {s[k]}' for k in keys if s.get(k) is not None)


# ---------------------------------------------------------------- internals


def _clean(given):
    """Answers as stored: numbers as numbers, yes/no as booleans, a single reference as a list."""
    out = dict(given)
    for k in ('height', 'size', 'directions'):
        if k in out:
            try:
                out[k] = int(out[k])
            except (TypeError, ValueError):
                raise SpriteKilnError(f'{k}: give a whole number (got {out[k]!r})') from None
    if 'scale' in out:
        try:
            out['scale'] = float(out['scale'])
        except (TypeError, ValueError):
            raise SpriteKilnError(f'scale: give a number (got {out["scale"]!r})') from None
    for k in YES_NO:
        if k in out and not isinstance(out[k], bool):
            text = str(out[k]).strip().lower()
            if text not in ('yes', 'no', 'true', 'false'):
                raise SpriteKilnError(f'{k}: yes or no (got {out[k]!r})')
            out[k] = text in ('yes', 'true')
    if 'references' in out:
        refs = out['references']
        out['references'] = [refs] if isinstance(refs, str) else [str(r) for r in refs]
        out['references'] = [r.strip() for r in out['references'] if r.strip()]
    for k in ('view', 'palette', 'colors', 'notes', 'outline_color', *CHOICES):
        if k in out:
            out[k] = str(out[k]).strip()
    if 'palette' in out:
        out['palette'] = out['palette'].replace('\\', '/')
    return out


def _check(st):
    for k, allowed in CHOICES.items():
        if st.get(k) not in allowed:
            raise SpriteKilnError(f'{k} {st.get(k)!r}: use one of {", ".join(allowed)}')
    lo, hi = HEIGHTS
    if not lo <= st['height'] <= hi:
        raise SpriteKilnError(f'height {st["height"]}: give the pixels of a character on screen, {lo} to {hi}')
    if not 8 <= st['size'] <= 512:
        raise SpriteKilnError(f'size {st["size"]}: a frame of 8 to 512 px')
    if not 0 < st['scale'] < 10:
        raise SpriteKilnError(f'scale {st["scale"]}: world units per pixel, e.g. 0.04')
    allowed = (2,) if st['view'] == 'side' else (4, 8)
    if st['directions'] not in allowed:
        raise SpriteKilnError(
            f'directions {st["directions"]}: a {st["view"]} view has {" or ".join(map(str, allowed))}'
        )
    if not st['palette']:
        raise SpriteKilnError('palette: give a palette name or file')
    if st.get('outline_color'):
        from .pixelize import hx

        try:
            hx(st['outline_color'])
        except ValueError:
            raise SpriteKilnError(f'outline_color {st["outline_color"]!r}: a colour like "#120d16"') from None


def _defaults(defaults, st):
    """The project's [defaults] with what the style decides; other keys stay."""
    d = dict(defaults)
    d['view'] = st['view']
    d['size'] = st['size']
    d['palette'] = st['palette']
    cam = dict(d.get('camera') or {})
    if 'pitch' not in cam or st['view'] != defaults.get('view', 'topdown'):  # a tilted side view keeps its pitch
        cam['pitch'] = PITCH[st['view']]
    cam['scale'] = st['scale']
    d['camera'] = cam
    if st['view'] == 'topdown' and st['directions'] == 4:
        d['directions'] = 4
    else:
        d.pop('directions', None)  # the view's own (8 top-down, e and w in a side view)
    if st['mirror']:
        d['mirror'] = True
    else:
        d.pop('mirror', None)
    return d


def _baseline(cfg):
    """First-record values for what the user did not answer: suggested ones plus the recommended look."""
    s = suggest(_spec_facts(cfg['specs'], cfg['root']), cfg)
    return {
        **{k: s[k] for k in ('view', 'height', 'scale', 'size', 'directions', 'mirror', 'palette')},
        'colors': '',
        **RECOMMENDED,
        'references': [],
        'notes': '',
    }


def suggest(specs, cfg):
    """Answers that keep what the project already has: the most common values of its character specs, or
    its [defaults] when it has none."""
    d = cfg['defaults']
    view = d.get('view', 'topdown')
    cam = d.get('camera') or {}
    scale = cam.get('scale', DEFAULT_SCALE)
    out = dict(view=view, scale=scale, size=d.get('size', 64), palette=d.get('palette', 'gothic'))
    out['directions'] = d.get('directions', 2 if view == 'side' else 8)
    out['mirror'] = bool(d.get('mirror', False))
    chars = [s for s in specs if s['kind'] == 'character'] or specs
    if chars:

        def common(key):
            vals = [s[key] for s in chars if s.get(key) is not None]
            return Counter(vals).most_common(1)[0][0] if vals else None

        for key in ('view', 'scale', 'size', 'palette', 'directions', 'mirror'):
            if common(key) is not None:
                out[key] = common(key)
        out['source'] = f'{len(chars)} existing spec(s)'
    else:
        out['source'] = 'the project defaults'
    if out['view'] == 'side':
        out['directions'] = 2
    elif out['directions'] not in (4, 8):
        out['directions'] = 8
    out['height'] = height_for(out['view'], out['scale'])
    return out


def off_style(specs, st, defaults):
    """Specs whose view, camera pitch or density differ from the style, or whose `render:` block sets a look
    field to something else: [{spec, differs: {key: [have, want]}}]."""
    out = []
    pitch = (defaults.get('camera') or {}).get('pitch', PITCH.get(st.get('view')))
    fixed = dict(view=st.get('view'), pitch=pitch, scale=st.get('scale'))
    look = {k: st.get(k, RENDER[k]) for k in STYLE_RENDER}
    for s in specs:
        have = dict(view=s['view'], pitch=s['pitch'], scale=s['scale'])
        own = {k: v for k, v in s['render'].items() if k in look}
        have.update(own)
        want = {**fixed, **{k: look[k] for k in own}}
        differs = {}
        for k, w in want.items():
            h = have[k]
            if w is None or h is None:
                continue
            if (abs(h - w) > 1e-6 * max(1, abs(w))) if isinstance(w, (int, float)) else h != w:
                differs[k] = [h, w]
        if differs:
            out.append(dict(spec=s['path'], differs=differs))
    return out


def _palette_name(value):
    """A spec's palette when it is a name every new spec can use (a path is relative to its own spec)."""
    path = not isinstance(value, str) or any(c in value for c in '/\\') or value.endswith(('.yaml', '.yml'))
    return None if path else value


def _spec_facts(folder, root):
    """Top-level facts of every spec under `folder`: path (relative to root), kind, view, camera pitch and
    scale, size, palette, directions, mirror. Renders, caches, palettes and splash cutouts are skipped."""
    import yaml

    from .spec import DEFAULT_CAMERA

    facts = []
    if not os.path.isdir(folder):
        return facts
    for d, dirs, files in os.walk(folder):
        dirs[:] = sorted(
            x for x in dirs if not x.startswith('.') and x not in ('out', 'palettes') and not x.endswith('_ref')
        )
        for f in sorted(files):
            if not f.endswith(('.yaml', '.yml')):
                continue
            path = os.path.join(d, f)
            try:
                with open(path, encoding='utf-8') as fh:
                    data = yaml.safe_load(fh)
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(data, dict) or not ({'spritekiln', 'pxforge'} & set(data)) or 'kit' in data:
                continue  # not a spec, or a kit
            if 'extends' in data or 'use' in data:  # what its base and kits give it
                from .kits import resolve

                try:
                    data = resolve(path, data).doc
                except Exception:  # noqa: BLE001 - a broken spec is validate's business, not the style's
                    continue
            if 'parts' not in data:
                continue
            view = data.get('view', 'topdown') if data.get('view') in PITCH else 'topdown'
            cam = data.get('camera') if isinstance(data.get('camera'), dict) else {}
            num = (int, float)
            pitch = cam.get('pitch', PITCH[view])
            scale = cam.get('scale', DEFAULT_CAMERA['scale'])
            dirs = data.get('directions')
            facts.append(
                dict(
                    path=os.path.relpath(path, root).replace(os.sep, '/'),
                    kind=data.get('kind', 'character'),
                    view=view,
                    pitch=pitch if isinstance(pitch, num) else None,
                    scale=scale if isinstance(scale, num) else None,
                    size=data.get('size') if isinstance(data.get('size'), int) else None,
                    palette=_palette_name(data.get('palette')),
                    directions=len(dirs) if isinstance(dirs, list) else dirs if dirs in (1, 4, 8) else None,
                    mirror=data.get('mirror') if isinstance(data.get('mirror'), bool) else None,
                    render=data.get('render') if isinstance(data.get('render'), dict) else {},
                )
            )
    return facts
