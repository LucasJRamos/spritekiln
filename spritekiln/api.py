"""High-level operations shared by the CLI and the MCP server. Every function takes paths, returns plain data
(dicts, numpy images) and raises SpriteKilnError for problems the user can fix."""

import json
import os
import re
import shutil

import numpy as np

from . import config, resources
from . import spec as specmod
from .errors import SpriteKilnError


def new(name, template='humanoid', folder=None, ref=None, start=None, view=None):
    """Create <folder>/<name>/<name>.yaml from a template; `folder` defaults to spritekiln.toml's specs folder
    + /characters (or specs/characters). Project defaults (view, size, palette, camera, light) are applied;
    `view` ('topdown' or 'side') overrides the project's."""
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name or ''):
        raise SpriteKilnError(f'name {name!r}: use letters, digits, - and _ only')
    tpl = resources.template(template)
    if not tpl:
        raise SpriteKilnError(f'template not found: {template} (available: {", ".join(resources.templates())})')
    cfg = config.load(start or folder)  # the project around the target folder (or the current one)
    folder = folder or (os.path.join(cfg['specs'], 'characters') if cfg else os.path.join('specs', 'characters'))
    dst_dir = os.path.join(folder, name)
    dst = os.path.join(dst_dir, f'{name}.yaml')
    if os.path.exists(dst):
        raise SpriteKilnError(f'already exists: {dst}')
    with open(tpl, encoding='utf-8') as fh:
        txt = fh.read().replace('name: TEMPLATE', f'name: {name}')
    defaults = dict(cfg.get('defaults') or {})
    project_view = defaults.pop('view', None)
    if view and view != (project_view or 'topdown') and isinstance(defaults.get('camera'), dict):
        defaults['camera'] = {k: v for k, v in defaults['camera'].items() if k != 'pitch'}  # the view's pitch wins
    view = view or project_view
    if view and view != 'topdown':
        if view not in specmod.VIEWS:
            raise SpriteKilnError(f'view {view!r}: use one of {", ".join(specmod.VIEWS)}')
        preset = specmod.VIEWS[view]
        txt = _set_top_level(txt, 'view', view)
        txt = _set_top_level(txt, 'directions', preset['directions'])
        txt = _set_top_level(txt, 'camera', {'pitch': preset['pitch']})
        txt = _set_top_level(txt, 'shadow', None)
    for key, value in defaults.items():
        txt = _set_top_level(txt, key, value)
    os.makedirs(dst_dir, exist_ok=True)
    with open(dst, 'w', encoding='utf-8') as fh:
        fh.write(txt)
    if ref:
        shutil.copy(ref, os.path.join(dst_dir, 'splash' + os.path.splitext(ref)[1]))
    return dst


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
        summary = dict(
            name=sp['name'],
            parts=len(sp['parts']),
            bones=len(sp['bones']),
            directions=[d for d, _ in sp['directions']],
            animations={k: len(frames_of(sp, k)) for k in sp['animations']},
            sockets=list(sp['sockets']),
        )
    return dict(ok=not errors, errors=errors, warnings=warnings, summary=summary)


def pose_env(sp, anim, frame, yaw=0.0):
    from .anim import frames_of
    from .rig import rest_env

    if not anim:
        return rest_env(sp, yaw)
    frames = frames_of(sp, anim, yaw)
    if not -len(frames) <= frame < len(frames):
        raise SpriteKilnError(f'frame {frame}: animation "{anim}" has {len(frames)} frames (0..{len(frames) - 1})')
    return frames[frame][0]


def pose(path, anim=None, frame=0, dirs=None, scale=4, bg=None, tint=None, out=None):
    """Render one pose in several directions side by side (zoomed PNG). Returns (png path, directions)."""
    from . import preview
    from .export import BG, upscale
    from .pipeline import frame_image

    sp = specmod.load(path)
    pose_env(sp, anim, frame)  # fails early on a bad anim/frame
    wanted = dirs.split(',') if isinstance(dirs, str) else dirs
    dl = [d for d in sp['directions'] if not wanted or d[0] in wanted]
    top = sp['view'] == 'topdown'  # top-down characters show all 8 by default (a side view shows its own)
    if wanted == ['all'] or (not wanted and top and len(sp['directions']) < 8 and sp['kind'] == 'character'):
        dl = specmod.DIRECTIONS8
    if not dl:
        raise SpriteKilnError(f'dirs {dirs}: no such direction (have: {", ".join(d for d, _ in sp["directions"])})')
    look = preview.viewer(preview.load_background(bg) if bg else None, preview.parse_tint(tint))
    shots = [frame_image(sp, pose_env(sp, anim, frame, y), y, maps=look is not None) for _, y in dl]
    imgs = [look(img, em) if look else img for img, _, em in shots]
    out = out or os.path.join(sp['_dir'], 'out', f'pose_{anim or "rest"}_{frame}.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    upscale(np.concatenate(imgs, 1), scale, None if look else BG).save(out)
    return out, [d for d, _ in dl]


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
):
    """Render animations and write atlases, JSON, previews and qa.json. Returns a summary dict."""
    from . import preview, qa
    from .export import export
    from .pipeline import render_all

    sp, anims, dlist, frames = render_all(
        os.path.abspath(path), anims, dirs, jobs, force, progress=progress, size=size, log=log
    )
    dst = out or os.path.join(sp['_dir'], 'out', sp['name'] + (f'_{size}' if size else ''))
    look = preview.viewer(preview.load_background(bg) if bg else None, preview.parse_tint(tint))
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


def export(path, engine=None, render_dir=None, dest=None, project=None, lit=False):
    """Export a rendered spec to the engine of spritekiln.toml (or `engine`)."""
    from .engines import export_asset

    return export_asset(specmod.load(path), engine=engine, render_dir=render_dir, dest=dest, project=project, lit=lit)


def ref_compare(path, image, direction='s', anim=None, frame=0, pitch_correction=True, tol=None, out=None):
    """Silhouette IoU of the model against a splash art, with hints and a comparison sheet."""
    from . import ref as R
    from .pipeline import frame_image

    sp = specmod.load(path)
    cut, mask, used = R.cutout(R.load(image), tol=tol)
    yaw = dict(specmod.DIRECTIONS8)[direction]
    spr = frame_image(sp, pose_env(sp, anim, frame, yaw), yaw, maps=False)[0]
    pitch = float(sp['camera']['pitch']) if pitch_correction else None
    raw = R.compare_masks(mask, spr[..., 3] == 255)[0]['iou']
    res, ga, gb = R.compare_masks(mask, spr[..., 3] == 255, pitch)
    res['iou_raw'] = raw
    turn = [frame_image(sp, pose_env(sp, anim, frame, y), y, maps=False)[0] for _, y in specmod.DIRECTIONS8]
    out = out or os.path.join(sp['_dir'], 'out', f'compare_{direction}.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    R.sheet(
        cut, spr, turn, (ga, gb), R.ref_palette(cut, mask), sp['materials'], out, f'{sp["name"]} ({anim or "rest"})'
    )
    with open(os.path.splitext(out)[0] + '.json', 'w', encoding='utf-8') as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False)
    res['sheet'] = out
    return res
