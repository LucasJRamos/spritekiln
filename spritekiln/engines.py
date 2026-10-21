"""Hand a rendered asset to the game engine: Godot resources, or the atlas + JSON copied where the engine wants it."""

import json
import os
import shutil

from . import config
from .errors import ExportError


def export_asset(spec, cfg=None, engine=None, render_dir=None, dest=None, project=None, lit=False):
    """Export `spec`'s render (default: <spec dir>/out/<name>) for `engine` (default: spritekiln.toml's, else
    generic). Returns a dict with what was written."""
    cfg = config.load(spec['_path']) if cfg is None else cfg
    engine = engine or cfg.get('engine') or 'generic'
    if engine not in config.ENGINES:
        raise ExportError(f'unknown engine {engine!r} (use {", ".join(config.ENGINES)})')
    name = spec['name']
    src = render_dir or os.path.join(spec['_dir'], 'out', name)
    jpath = os.path.join(src, f'{name}.json')
    if not os.path.exists(jpath):
        raise ExportError(f'render not found: {jpath}  (run `spritekiln render` first)')
    if engine == 'godot':
        from .godot import DEFAULT_DEST, _find_project, export_godot

        proj = _find_project(project, start=spec['_path'])
        written = export_godot(spec, proj, dest or cfg.get('export_dir') or DEFAULT_DEST, lit=lit, render_dir=src)
        return dict(engine=engine, dir=os.path.join(proj, *written['res'][6:].split('/')), **written)
    base = dest or cfg.get('export_dir') or config.EXPORT_DIRS[engine]
    if not os.path.isabs(base):
        base = os.path.join(cfg.get('root') or os.getcwd(), base)
    target = os.path.join(base, name)
    os.makedirs(target, exist_ok=True)
    with open(jpath, encoding='utf-8') as fh:
        meta = json.load(fh)
    block = meta.get('spritekiln') or meta.get('pxforge') or {}
    files = [meta['meta']['image'], block.get('normal_map'), block.get('emissive_map'), f'{name}.json']
    copied = []
    for f in filter(None, files):
        if os.path.exists(os.path.join(src, f)):
            shutil.copy2(os.path.join(src, f), os.path.join(target, f))
            copied.append(os.path.join(target, f))
    return dict(engine=engine, dir=target, files=copied)
