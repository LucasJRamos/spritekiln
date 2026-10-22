"""Hand a rendered asset to the game engine: Godot resources, or the atlas + JSON copied where the engine wants it."""

import json
import os
import shutil

from . import config
from .errors import ExportError


def default_engine(cfg, legacy=False):
    """The project's engine; without spritekiln.toml, Godot when a Godot project is configured through the
    environment (Hunt Tower's px.cmd sets PXFORGE_GODOT_PROJECT) or for the legacy command, else generic."""
    if cfg.get('engine'):
        return cfg['engine']
    if legacy or os.environ.get('SPRITEKILN_GODOT_PROJECT') or os.environ.get('PXFORGE_GODOT_PROJECT'):
        return 'godot'
    return 'generic'


def export_asset(spec, cfg=None, engine=None, render_dir=None, dest=None, project=None, lit=False, legacy=False):
    """Export `spec`'s render (default: <spec dir>/out/<name>) for `engine` (default: see default_engine).
    `dest`: for Godot a folder inside the project; for the other engines a folder relative to the current
    one. spritekiln.toml's export.dir is used only for the project's own engine. Returns a dict with what was
    written, and `missing`: the spec's animations the render does not hold."""
    cfg = config.load(spec['_path']) if cfg is None else cfg
    engine = engine or default_engine(cfg, legacy)
    if engine not in config.ENGINES:
        raise ExportError(f'unknown engine {engine!r} (use {", ".join(config.ENGINES)})')
    name = spec['name']
    src = render_dir or os.path.join(spec['_dir'], 'out', name)
    jpath = os.path.join(src, f'{name}.json')
    if not os.path.exists(jpath):
        raise ExportError(f'render not found: {jpath}  (run `spritekiln render` first)')
    with open(jpath, encoding='utf-8') as fh:
        meta = json.load(fh)
    block = meta.get('spritekiln') or meta.get('pxforge') or {}
    missing = sorted(set(spec['animations']) - set(block.get('animations') or {}))
    own = cfg.get('engine') == engine  # the toml's export folder belongs to its engine
    if engine == 'godot':
        from .godot import _find_project, export_godot

        proj = _find_project(project, start=spec['_path'])
        addon = 'pxforge' if legacy else 'spritekiln'
        target = dest or (cfg.get('export_dir') if own else None)
        written = export_godot(spec, proj, target, lit=lit, render_dir=src, addon=addon)
        folder = os.path.join(proj, *written['res'][6:].split('/'))
        return dict(engine=engine, dir=folder, missing=missing, **written)
    if dest:
        base = os.path.abspath(dest)
    else:
        base = (cfg.get('export_dir') if own else None) or config.EXPORT_DIRS[engine]
        if not os.path.isabs(base):
            base = os.path.join(cfg.get('root') or os.getcwd(), base)
    target = os.path.join(base, name)
    os.makedirs(target, exist_ok=True)
    files = [meta['meta']['image'], block.get('normal_map'), block.get('emissive_map'), f'{name}.json']
    copied = []
    for f in filter(None, files):
        if os.path.exists(os.path.join(src, f)):
            # Unity imports .json as text: its importer (integrations/unity) reads the same JSON as .kiln
            out = f'{name}.kiln' if engine == 'unity' and f == f'{name}.json' else f
            shutil.copy2(os.path.join(src, f), os.path.join(target, out))
            copied.append(os.path.join(target, out))
    return dict(engine=engine, dir=target, files=copied, missing=missing)
