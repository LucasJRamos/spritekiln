"""`spritekiln.toml`: per-project settings, written by `spritekiln init` and found by searching upwards.

[project]  specs folder, engine and the AI assistants set up by `init`
[export]   where `spritekiln export` (and `render --export`) puts the files for the engine
[defaults] size, palette, camera and light given to specs created by `spritekiln new`
[style]    the project's art style, recorded by `spritekiln style set` (see style.py)
"""

import datetime
import os
import re
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
TABLE_COMMENTS = {
    'defaults': 'given to specs created by `spritekiln new`',
    'style': 'the art style every asset follows (`spritekiln style`); change it only when asked',
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


def read(path):
    """The raw tables of a spritekiln.toml."""
    try:
        with open(path, 'rb') as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise SpriteKilnError(f'{path}: {e}') from None


def load(start=None):
    """Settings of the project around `start` ({} when there is none). Paths come back absolute."""
    path = find(start)
    if not path:
        return {}
    data = read(path)
    root = os.path.dirname(path)
    project = data.get('project', {})
    export = data.get('export', {})
    engine = project.get('engine', 'generic')
    if engine not in ENGINES:
        raise SpriteKilnError(f'{path}: project.engine must be one of {", ".join(ENGINES)} (got {engine!r})')
    ai = project.get('ai')
    return dict(
        path=path,
        root=root,
        engine=engine,
        specs=os.path.normpath(os.path.join(root, project.get('specs', 'specs'))),
        export_dir=export.get('dir', EXPORT_DIRS[engine]),
        godot_project=os.path.normpath(os.path.join(root, export.get('godot_project', '.'))),
        ai=[a for a in ai if isinstance(a, str)] if isinstance(ai, list) else None,  # None: set up before 0.2
        defaults=data.get('defaults', {}),
        style=data.get('style', {}),
    )


def _toml_value(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        escaped = v.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
        return '"' + re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', lambda m: f'\\u{ord(m.group()):04x}', escaped) + '"'
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(_toml_value(x) for x in v) + ']'
    if isinstance(v, dict):
        return '{ ' + ', '.join(f'{k} = {_toml_value(x)}' for k, x in v.items()) + ' }'
    return repr(v)


def _path(p):
    return p.replace('\\', '/')


def table(name, values, notes=None):
    """Lines of a [name] table; `notes` maps keys to end-of-line comments."""
    head = f'[{name}]'
    lines = [head.ljust(26) + f'# {TABLE_COMMENTS[name]}' if name in TABLE_COMMENTS else head]
    for k, v in values.items():
        line = f'{k} = {_toml_value(v)}'
        note = (notes or {}).get(k)
        lines.append(line.ljust(26) + f'# {note}' if note else line)
    return lines


def render(engine, specs='art/specs', export_dir=None, godot_project='.', defaults=None, ais=None, style=None):
    """Text of a new spritekiln.toml."""
    defaults = defaults or {'size': 64, 'palette': 'gothic', 'camera': {'pitch': 38, 'scale': 0.04}}
    lines = [
        '# SpriteKiln project settings (https://github.com/LucasJRamos/spritekiln).',
        '# Commands run anywhere inside this folder find this file.',
        '',
        '[project]',
        f'specs = {_toml_value(_path(specs))}        # where `spritekiln new` creates specs',
        f'engine = {_toml_value(engine)}       # {" | ".join(ENGINES)}',
    ]
    if ais:
        lines.append(f'ai = {_toml_value(list(ais))}       # assistants whose files `spritekiln update` refreshes')
    lines += [
        '',
        '[export]',
        '# `spritekiln export <spec>` (or `render --export`) copies the atlas, JSON and maps here;',
        '# for Godot it also writes SpriteFrames, a CanvasTexture and a ready scene.',
        f'dir = {_toml_value(_path(export_dir or EXPORT_DIRS[engine]))}',
    ]
    if engine == 'godot':
        lines.append(f'godot_project = {_toml_value(_path(godot_project))}   # folder with project.godot')
    lines += ['', *table('defaults', defaults)]
    if style:
        from .style import NOTES

        lines += ['', *table('style', style, NOTES)]
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------- editing a project's file in place

_HEADER = re.compile(r'\s*\[\s*([^\[\]#]+?)\s*\]\s*(#.*)?$')


def _tables(lines):
    """[(name, first line, end line)] of the tables in `lines`; the part before the first one is named ''."""
    found, name, start, quote = [], '', 0, None
    for i, line in enumerate(lines):
        if quote:  # inside a multi-line string: a line that looks like a header is text
            if line.count(quote) % 2:
                quote = None
            continue
        quote = next((q for q in ('"""', "'''") if line.count(q) % 2), None)
        m = None if quote or line.lstrip().startswith('[[') else _HEADER.match(line)
        if m:
            found.append((name, start, i))
            name, start = m.group(1).replace(' ', ''), i
    found.append((name, start, len(lines)))
    return found


def set_tables(path, tables, notes=None):
    """Rewrite whole tables of a spritekiln.toml ({name: values}) and leave the rest of the file (comments,
    other tables) as it is. A table the file lacks is added at the end; dotted sub-tables of a rewritten
    table ([defaults.camera]) are folded into it. `notes`: {table: {key: end-of-line comment}}."""
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().splitlines()
    spans = _tables(lines)
    edits = []  # (start, end, new lines)
    for name, values in tables.items():
        body = table(name, values, (notes or {}).get(name))
        mine = [(s, e) for n, s, e in spans if n == name or n.startswith(name + '.')]
        if not mine:
            edits.append((len(lines), len(lines), ([''] if lines and lines[-1].strip() else []) + body))
            continue
        for k, (s, e) in enumerate(mine):
            while e > s + 1 and not lines[e - 1].strip():  # keep the blank lines before the next table
                e -= 1
            edits.append((s, e, body if k == 0 else []))
    for s, e, new in sorted(edits, key=lambda x: x[0], reverse=True):
        lines[s:e] = new
    text = '\n'.join(lines).rstrip('\n') + '\n'
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:  # never leave a broken file behind
        raise SpriteKilnError(f'{path}: could not update it ({e}); edit it by hand') from None
    for name, values in tables.items():
        if parsed.get(name) != values:
            raise SpriteKilnError(f'{path}: could not update [{name}]; edit it by hand')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
