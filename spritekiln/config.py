"""`spritekiln.toml`: per-project settings, written by `spritekiln init` and found by searching upwards.

[project]  specs folder and engine
[export]   where `spritekiln export` (and `render --export`) puts the files for the engine
[defaults] size, palette, camera and light given to specs created by `spritekiln new`
"""

import os
import sys

from .errors import SpriteKilnError

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10
    import tomli as tomllib

FILENAME = 'spritekiln.toml'
ENGINES = ('godot', 'unity', 'monogame', 'generic')
EXPORT_DIRS = {
    'godot': 'assets/spritekiln',
    'unity': 'Assets/SpriteKiln',
    'monogame': 'Content/sprites',
    'generic': 'sprites',
}


def find(start=None):
    """Path of the nearest spritekiln.toml at or above `start` (a file or folder; default: cwd), or None."""
    d = os.path.abspath(start or os.getcwd())
    if os.path.isfile(d):
        d = os.path.dirname(d)
    while True:
        p = os.path.join(d, FILENAME)
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def load(start=None):
    """Settings of the project around `start` ({} when there is none). Paths come back absolute."""
    path = find(start)
    if not path:
        return {}
    try:
        with open(path, 'rb') as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise SpriteKilnError(f'{path}: {e}') from None
    root = os.path.dirname(path)
    project = data.get('project', {})
    export = data.get('export', {})
    engine = project.get('engine', 'generic')
    if engine not in ENGINES:
        raise SpriteKilnError(f'{path}: project.engine must be one of {", ".join(ENGINES)} (got {engine!r})')
    return dict(
        path=path,
        root=root,
        engine=engine,
        specs=os.path.join(root, project.get('specs', 'specs')),
        export_dir=export.get('dir', EXPORT_DIRS[engine]),
        godot_project=os.path.join(root, export.get('godot_project', '.')),
        defaults=data.get('defaults', {}),
    )


def _toml_value(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        return '"' + v.replace('\\', '/').replace('"', '\\"') + '"'
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(_toml_value(x) for x in v) + ']'
    if isinstance(v, dict):
        return '{ ' + ', '.join(f'{k} = {_toml_value(x)}' for k, x in v.items()) + ' }'
    return repr(v)


def render(engine, specs='art/specs', export_dir=None, godot_project='.', defaults=None):
    """Text of a new spritekiln.toml."""
    defaults = defaults or {'size': 64, 'palette': 'gothic', 'camera': {'pitch': 38, 'scale': 0.04}}
    lines = [
        '# SpriteKiln project settings (https://github.com/LucasJRamos/spritekiln).',
        '# Commands run anywhere inside this folder find this file.',
        '',
        '[project]',
        f'specs = {_toml_value(specs)}        # where `spritekiln new` creates specs',
        f'engine = {_toml_value(engine)}       # {" | ".join(ENGINES)}',
        '',
        '[export]',
        '# `spritekiln export <spec>` (or `render --export`) copies the atlas, JSON and maps here;',
        '# for Godot it also writes SpriteFrames, a CanvasTexture and a ready scene.',
        f'dir = {_toml_value(export_dir or EXPORT_DIRS[engine])}',
    ]
    if engine == 'godot':
        lines.append(f'godot_project = {_toml_value(godot_project)}   # folder with project.godot')
    lines += ['', '[defaults]                # given to specs created by `spritekiln new`']
    lines += [f'{k} = {_toml_value(v)}' for k, v in defaults.items()]
    return '\n'.join(lines) + '\n'
