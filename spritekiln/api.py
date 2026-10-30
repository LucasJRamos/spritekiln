"""High-level operations shared by the CLI and the MCP server. Every function takes paths, returns plain data
(dicts, numpy images) and raises SpriteKilnError for problems the user can fix."""

import difflib
import json
import os
import re
import shutil

import numpy as np

from . import config, resources
from . import spec as specmod
from .errors import SpriteKilnError


def new(name, template=None, folder=None, ref=None, start=None, view=None, extends=False):
    """Create <folder>/<name>/<name>.yaml from a template; `folder` defaults to spritekiln.toml's specs folder
    + /characters (or specs/characters). Project defaults (view, size, palette, camera, light) are applied;
    `view` ('topdown' or 'side') overrides the project's. Without a template, a side view starts from
    `side_humanoid` and a top-down one from `humanoid`. `extends`: a short spec that extends the template
    (design 14) instead of a full copy of it; it states only what differs."""
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name or ''):
        raise SpriteKilnError(f'name {name!r}: use letters, digits, - and _ only')
    if view and view not in specmod.VIEWS:
        raise SpriteKilnError(f'view {view!r}: use one of {", ".join(specmod.VIEWS)}')
    if ref and not os.path.isfile(ref):
        raise SpriteKilnError(f'splash art not found: {ref}')
    cfg = config.load(start or folder)  # the project around the target folder (or the current one)
    defaults = dict(cfg.get('defaults') or {})
    project_view = defaults.pop('view', None) or 'topdown'
    if template is None:
        side = (view or project_view) == 'side'
        template = 'side_humanoid' if side and resources.template('side_humanoid') else 'humanoid'
    tpl = resources.template(template)
    if not tpl:
        raise SpriteKilnError(f'template not found: {template} (available: {", ".join(resources.templates())})')
    folder = folder or (os.path.join(cfg['specs'], 'characters') if cfg else os.path.join('specs', 'characters'))
    dst_dir = os.path.join(folder, name)
    dst = os.path.normpath(os.path.join(dst_dir, f'{name}.yaml'))
    if os.path.exists(dst):
        raise SpriteKilnError(f'already exists: {dst}')
    with open(tpl, encoding='utf-8') as fh:
        txt = fh.read().replace('name: TEMPLATE', f'name: {name}')
    import yaml

    base = yaml.safe_load(txt) or {}  # what the template already says: keys it satisfies stay as written
    if extends:
        from .kits import resolve

        base = resolve(tpl).doc
        txt = _EXTENDS.format(name=name, template=template)
    made_for = base.get('view')  # a template made for one view (side_humanoid) keeps it
    view = view or made_for or project_view
    if made_for and made_for != view:
        raise SpriteKilnError(f'template {template} is a {made_for} view; use --view {made_for} or another template')
    if view != project_view and isinstance(defaults.get('camera'), dict):
        defaults['camera'] = {k: v for k, v in defaults['camera'].items() if k != 'pitch'}  # the view's pitch wins
    if view != 'topdown' and made_for != view:
        preset = specmod.VIEWS[view]
        txt = _set_top_level(txt, 'view', view)
        txt = _set_top_level(txt, 'directions', preset['directions'])
        txt = _set_top_level(txt, 'camera', {'pitch': preset['pitch']})
        txt = _set_top_level(txt, 'shadow', None)
    for key, value in defaults.items():
        if not _satisfies(base, key, value):
            txt = _set_top_level(txt, key, value)
    os.makedirs(dst_dir, exist_ok=True)
    with open(dst, 'w', encoding='utf-8') as fh:
        fh.write(txt)
    if ref:
        shutil.copy(ref, os.path.join(dst_dir, 'splash' + os.path.splitext(ref)[1]))
    return dst


_EXTENDS = """spritekiln: 1
# yaml-language-server: $schema=https://raw.githubusercontent.com/LucasJRamos/spritekiln/main/spritekiln/data/spec.schema.json
name: {name}
extends: {template}   # its skeleton, body, kits and animations: write here only what differs
# `spritekiln spec outline` lists what comes from the base; `spritekiln spec show <path>` prints its lines,
# `--resolved` the result. Keys given here merge into the base's (parts.belt.prims replaces its prims);
# `remove: [parts.cape, use.sword]` drops a part or a kit of the base.

brief:
  summary: ""
  head: ""        # hair (style, length, fringe), jaw and chin, how much face: then fit the head and hair kits
  must_keep: []
  simplify: []
"""


def _satisfies(base, key, value):
    """True when the template's top-level `key` already gives `value` (a camera without a pitch takes its
    view's)."""
    have = base.get(key)
    if key == 'camera' and isinstance(have, dict) and base.get('view') in specmod.VIEWS:
        have = {'pitch': specmod.VIEWS[base['view']]['pitch'], **have}
    if isinstance(value, dict) and isinstance(have, dict):
        return {**have, **value} == have
    return have == value


def _set_top_level(text, key, value):
    """Replace (or add after `name:`) a top-level `key: value` line, keeping the rest of the template intact."""
    if isinstance(value, dict) and key in ('camera', 'light'):
        m = re.search(rf'^{key}:\s*(\{{.*\}})', text, re.M)
        if m:  # merge into the template's flow mapping, e.g. keep camera.center
            import yaml

            merged = dict(yaml.safe_load(m.group(1)) or {}, **value)
            value = merged
    line = f'{key}: {json.dumps(value)}'
    if re.search(rf'^{key}:.*$', text, re.M):
        return re.sub(rf'^{key}:.*$', lambda _: line, text, count=1, flags=re.M)
    return re.sub(r'^name:.*$', lambda m: m.group(0) + '\n' + line, text, count=1, flags=re.M)


def validate(path):
    """{'ok', 'errors', 'warnings', 'summary'} for a spec."""
    from .anim import frames_of

    sp = specmod.load(path)
    errors, warnings = specmod.check(sp)
    summary = None
    if not errors:
        from .rig import build, rest_env

        groups = build(sp, rest_env(sp, sp['directions'][0][1]))[0]
        summary = dict(
            name=sp['name'],
            parts=len(sp['parts']),
            primitives=sum(len(g.prims) for g in groups),
            cuts=sum(len(g.cut) for g in groups),
            bones=len(sp['bones']),
            directions=[d for d, _ in sp['directions']],
            animations={k: len(frames_of(sp, k)) for k in sp['animations']},
            sockets=list(sp['sockets']),
        )
    return dict(ok=not errors, errors=errors, warnings=warnings, summary=summary)


def kits(name=None, start=None):
    """The kits a spec can use: [{name, origin, file, summary, at, host, license, params, materials}]; with a
    `name`, that kit, plus `params_text` and `channels_text` (its params and channels blocks with comments; the
    channels an animator drives, named `<as>_<name>` in a spec)."""
    from . import kits as K
    from .outline import ranges

    found = K.catalogue(start)
    if not name:
        return found
    for k in found:
        if k['name'] == name:
            spans = ranges(k['file'])
            with open(k['file'], encoding='utf-8') as fh:
                lines = fh.read().split('\n')
            text = {}
            for key in ('params', 'channels'):
                r = spans.get((key,))
                text[key] = '\n'.join(lines[r[0] - 1 : r[1]]) if r else ''
            return dict(k, params_text=text['params'], channels_text=text['channels'])
    import difflib

    near = difflib.get_close_matches(name, [k['name'] for k in found], n=1)
    hint = f' (did you mean {near[0]}?)' if near else ''
    raise SpriteKilnError(f'kit {name!r} not found{hint}; `spritekiln kits` lists them')


def pose_env(sp, anim, frame, yaw=0.0):
    from .anim import frames_of
    from .rig import rest_env

    if not anim:
        return rest_env(sp, yaw)
    frames = frames_of(sp, anim, yaw)
    if not -len(frames) <= frame < len(frames):
        raise SpriteKilnError(f'frame {frame}: animation "{anim}" has {len(frames)} frames (0..{len(frames) - 1})')
    return frames[frame][0]


def pose(
    path, anim=None, frame=0, dirs=None, scale=None, bg=None, tint=None, out=None, draft=False, crop=True, focus=None
):
    """Render one pose in several directions side by side (zoomed PNG). Returns (png path, directions, view):
    `view` holds the zoom used and the crop box [x0, y0, x1, y1] in frame pixels.
    `scale` is the largest zoom (4; 12 with `focus`): it is lowered, by whole steps, until the image fits an AI's
    image budget (preview.MAX_SIDE, MAX_AREA). `crop`: keep only what the sprite shows, plus a margin (the same box
    in every direction; over a `bg` the whole frame shows). `focus`: a close-up of a bone and everything attached
    below it (`head`: the head, hair, eyes and headwear), or of parts by name; comma-separated. `draft`: one sample
    per pixel, about 6x faster, for silhouettes and poses (rougher edges, thin parts may break); the default file
    name ends in `_draft` (`_<focus>` with a focus)."""
    from . import preview
    from .export import BG, upscale
    from .pipeline import frame_image, parts_mask

    sp = _checked(specmod.load(path))
    if draft:
        specmod.as_draft(sp)
    pose_env(sp, anim, frame)  # fails early on a bad anim/frame
    focus_parts = _focus_parts(sp, focus) if focus else None
    if scale is None:
        scale = 12 if focus else 4
    wanted = [w.strip() for w in dirs.split(',')] if isinstance(dirs, str) else dirs
    pool = _viewable(sp)
    if wanted == ['all']:
        dl = pool
    elif wanted:
        unknown = [w for w in wanted if w not in dict(pool)]
        if unknown:
            raise SpriteKilnError(f'dirs: no direction {", ".join(unknown)} here (use {", ".join(dict(pool))} or all)')
        dl = [d for d in pool if d[0] in wanted]
    elif sp['view'] == 'topdown' and len(sp['directions']) < 8 and sp['kind'] == 'character':
        dl = pool  # a top-down character shows all 8 by default
    else:
        dl = sp['directions']
    look = preview.viewer(preview.load_background(bg) if bg else None, preview.parse_tint(tint))
    shots = [frame_image(sp, pose_env(sp, anim, frame, y), y, maps=look is not None) for _, y in dl]
    imgs = [look(img, em) if look else img for img, _, em in shots]
    h, w = imgs[0].shape[:2]
    if focus_parts:
        masks = [parts_mask(sp, pose_env(sp, anim, frame, y), y, focus_parts) for _, y in dl]
        if not any(m.any() for m in masks):
            shown = ', '.join(sorted(focus_parts))
            raise SpriteKilnError(f'focus {focus}: none of its parts shows in this pose ({shown})')
        y0, y1, x0, x1 = preview.content_box([np.dstack([m] * 4) for m in masks], margin=0)
        grow = max(preview.MARGIN, round(0.2 * max(y1 - y0, x1 - x0)))  # some of what is around it
        box = (max(0, y0 - grow), min(h, y1 + grow), max(0, x0 - grow), min(w, x1 + grow))
    else:
        box = preview.content_box(imgs) if crop else (0, h, 0, w)
    strip = np.concatenate(preview.crop(imgs, box), 1)
    k = preview.fit_scale(lambda k: (strip.shape[1] * k, strip.shape[0] * k), scale)
    tag = f'_{focus.replace(",", "+")}' if focus else ''
    out = out or os.path.join(sp['_dir'], 'out', f'pose_{anim or "rest"}_{frame}{tag}{"_draft" if draft else ""}.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    upscale(strip, k, None if look else BG).save(out)
    y0, y1, x0, x1 = box
    return out, [d for d, _ in dl], dict(scale=k, crop=[x0, y0, x1, y1])


def style_preview(path=None, fields=None, direction='se', anim=None, frame=0, scale=4, out=None, start=None):
    """The same pose under every choice of the style's look fields, one row per field, the project's style (or the
    defaults) for the other fields: to choose a style by looking. Without a spec, the humanoid template. Renders
    come from the geometry cache except for light presets that move the light (their shadows are traced). Returns
    (png path, rows: [{field, choices, current}]); the current choice is marked with * in the image."""
    import tempfile

    from PIL import Image

    from . import preview
    from . import style as S
    from .export import BG, font, label, upscale
    from .pipeline import render_frame

    fields = list(fields or S.PREVIEW_FIELDS)
    unknown = [f for f in fields if f not in S.PREVIEW_FIELDS]
    if unknown:
        raise SpriteKilnError(f'fields: {", ".join(unknown)} (use {", ".join(S.PREVIEW_FIELDS)})')
    if direction not in dict(specmod.DIRECTIONS8):
        raise SpriteKilnError(f'direction {direction!r}: use one of {", ".join(dict(specmod.DIRECTIONS8))}')
    cfg = config.load(start or path)
    st = cfg.get('style') or {} if cfg else {}
    current = {**specmod.RENDER, **{k: st[k] for k in specmod.STYLE_RENDER if st.get(k) not in (None, '')}}
    tmp = None
    if path is None:  # a copy, so that its render cache does not land in the installed package
        tmp = tempfile.mkdtemp(prefix='spritekiln-style-')
        path = shutil.copy(resources.template('humanoid'), os.path.join(tmp, 'humanoid.yaml'))
    yaw = dict(specmod.DIRECTIONS8)[direction]
    rows, cells = [], []
    try:
        for field in fields:
            choices = [True, False] if field == 'highlights' else list(S.CHOICES[field])
            for c in choices:
                sp = _checked(specmod.load(path, style={**current, field: c}))
                cells.append(render_frame(sp, pose_env(sp, anim, frame, yaw), yaw, maps=False).img)
            rows.append(dict(field=field, choices=choices, current=current[field]))
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    box = preview.content_box(cells)
    cells = preview.crop(cells, box)
    h, w = cells[0].shape[:2]

    def name(r, c):
        return (('yes' if c else 'no') if isinstance(c, bool) else c) + (' *' if c == r['current'] else '')

    names = [[name(r, c) for c in r['choices']] for r in rows]
    widest = max(font().getlength(n) for row in names for n in row) + 8
    left, head, gap = 76, 16, 6
    ncol = max(len(r['choices']) for r in rows)

    def col(k):
        return max(w * k, int(widest)) + gap

    def size_at(k):
        return left + ncol * col(k), gap + len(rows) * (head + h * k + gap)

    k = preview.fit_scale(size_at, scale)
    im = Image.new('RGBA', size_at(k), BG)
    i = 0
    for r, row in enumerate(rows):
        y = gap + r * (head + h * k + gap)
        label(im, row['field'], (4, y + head + 2))
        for c, name in enumerate(names[r]):
            x = left + c * col(k)
            label(im, name, (x, y + 1))
            im.alpha_composite(upscale(cells[i], k, None), (x, y + head))
            i += 1
    if out is None:
        where = os.path.join(os.path.dirname(os.path.abspath(path)), 'out') if tmp is None else None
        where = where or os.path.join(cfg['specs'] if cfg else os.getcwd(), 'out')
        out = os.path.join(where, 'style_preview.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out)
    return out, rows


def _checked(sp):
    """The spec, or SpriteKilnError with the problems found without building poses."""
    errors = specmod.quick_errors(sp)
    if errors:
        listed = ''.join(f'\n  - {e}' for e in errors)
        raise SpriteKilnError(f'the spec has errors (run `spritekiln validate` for all of them):{listed}')
    return sp


def _focus_parts(sp, focus):
    """The part names a `focus` shows: parts named in it, and the parts whose space is a bone named in it or a bone
    below one (through `parent`)."""
    names = [f.strip() for f in focus.split(',')] if isinstance(focus, str) else [str(f) for f in focus]
    names = [n for n in names if n]
    bones = sp['bones']
    unknown = [n for n in names if n not in bones and n not in sp['parts'] and n != 'root']
    if unknown or not names:
        near = difflib.get_close_matches(unknown[0], [*bones, *sp['parts']], n=1) if unknown else []
        hint = f' (did you mean {near[0]}?)' if near else ' (a bone such as head, or part names)'
        raise SpriteKilnError(f'focus: no bone or part {", ".join(unknown) or repr(focus)}{hint}')

    def under(frame):
        seen = set()
        while frame and frame not in seen:
            if frame in names:
                return True
            seen.add(frame)
            frame = (bones.get(frame) or {}).get('parent', 'root') if frame != 'root' else None
        return False

    names += [n[:-2] + '_R' for n in names if n.endswith('_L')]  # a part's mirrored twin too
    return {p for p, part in sp['parts'].items() if p in names or under(part.get('space', 'root'))}


def _viewable(sp):
    """Directions a pose can show: any of the 8 for a top-down model, the view's own otherwise."""
    if sp['view'] == 'topdown':
        return specmod.DIRECTIONS8
    names = specmod.VIEWS[sp['view']]['directions']
    return [d for d in specmod.DIRECTIONS8 if d[0] in names]


def render(
    path,
    anims=None,
    dirs=None,
    jobs=None,
    force=False,
    size=None,
    out=None,
    block='spritekiln',
    bg=None,
    tint=None,
    progress=None,
    log=None,
    draft=False,
):
    """Render animations and write atlases, JSON, previews and qa.json. Returns a summary dict.
    `draft`: one sample per pixel, and only the previews (GIFs and contact sheets in `preview-draft/`): no
    atlas, JSON or QA, so a draft can never reach an engine."""
    from . import preview, qa
    from .export import export, previews
    from .pipeline import render_all

    look = preview.viewer(preview.load_background(bg) if bg else None, preview.parse_tint(tint))  # fail early
    _checked(specmod.load(path, size=size))
    sp, anims, dlist, frames = render_all(
        os.path.abspath(path), anims, dirs, jobs, force, progress=progress, size=size, log=log, draft=draft
    )
    dst = out or os.path.join(sp['_dir'], 'out', sp['name'] + (f'_{size}' if size else ''))
    if draft:
        sheets = previews(sp, anims, dlist, frames, os.path.join(dst, 'preview-draft'), look=look)
        return dict(
            spec=sp,
            dir=dst,
            frames=len(frames),
            animations=anims,
            directions=[d for d, _ in dlist],
            draft=True,
            contact_sheets=sheets,
        )
    export(sp, anims, dlist, frames, dst, block=block, look=look)
    rep = qa.check(sp, anims, dlist, frames)
    with open(os.path.join(dst, 'qa.json'), 'w', encoding='utf-8') as fh:
        json.dump(rep, fh, indent=1, ensure_ascii=False)
    return dict(
        spec=sp,
        dir=dst,
        frames=len(frames),
        animations=anims,
        directions=[d for d, _ in dlist],
        qa=rep,
        contact_sheets={a: os.path.join(dst, 'preview', f'contact_{a}.png') for a in anims},
        json=os.path.join(dst, f'{sp["name"]}.json'),
    )


def export(path, engine=None, render_dir=None, dest=None, project=None, lit=False, legacy=False):
    """Export a rendered spec to the engine of spritekiln.toml (or `engine`). `legacy`: Godot scenes use the
    old PxSprite2D addon (projects driven by the `pxforge` command)."""
    from .engines import export_asset

    sp = specmod.load(path)
    return export_asset(sp, engine=engine, render_dir=render_dir, dest=dest, project=project, lit=lit, legacy=legacy)


def ref_compare(path, image, direction='s', anim=None, frame=0, pitch_correction=True, tol=None, out=None):
    """Silhouette IoU of the model against a splash art, with hints and a comparison sheet."""
    from . import ref as R
    from .pipeline import frame_image

    sp = specmod.load(path)
    if direction not in dict(specmod.DIRECTIONS8):
        raise SpriteKilnError(f'direction {direction!r}: use one of {", ".join(dict(specmod.DIRECTIONS8))}')
    cut, mask, used = R.cutout(R.load(image), tol=tol)
    yaw = dict(specmod.DIRECTIONS8)[direction]
    spr = frame_image(sp, pose_env(sp, anim, frame, yaw), yaw, maps=False)[0]
    pitch = float(sp['camera']['pitch']) if pitch_correction else None
    raw = R.compare_masks(mask, spr[..., 3] == 255)[0]['iou']
    res, ga, gb = R.compare_masks(mask, spr[..., 3] == 255, pitch)
    res['iou_raw'] = raw
    turn = [frame_image(sp, pose_env(sp, anim, frame, y), y, maps=False)[0] for _, y in specmod.DIRECTIONS8]
    out = out or os.path.join(sp['_dir'], 'out', f'compare_{direction}.png')
    if os.path.isdir(out) or not os.path.splitext(out)[1]:  # a folder: the sheet goes inside
        out = os.path.join(out, f'compare_{direction}.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    R.sheet(
        cut, spr, turn, (ga, gb), R.ref_palette(cut, mask), sp['materials'], out, f'{sp["name"]} ({anim or "rest"})'
    )
    with open(os.path.splitext(out)[0] + '.json', 'w', encoding='utf-8') as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False)
    res['sheet'] = out
    return res
