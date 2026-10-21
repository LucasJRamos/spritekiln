"""Files that ship with the package: built-in palettes, spec templates and the Godot addon.

An installed wheel carries them in `spritekiln/data/` (see `force-include` in pyproject.toml). In a
source checkout or an editable install they are read from their place in the repository.
"""

import os

_PKG = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_PKG, 'data')
_REPO = os.path.dirname(_PKG)

# kind -> folder in the source tree
_SOURCE = {
    'palettes': os.path.join(_REPO, 'specs', 'palettes'),
    'templates': os.path.join(_REPO, 'specs', 'templates'),
    'godot_addon': os.path.join(_REPO, 'integrations', 'godot', 'addons', 'pxforge'),
}
_PACKAGED = {
    'palettes': os.path.join(_DATA, 'palettes'),
    'templates': os.path.join(_DATA, 'templates'),
    'godot_addon': os.path.join(_DATA, 'godot', 'addons', 'pxforge'),
}


def data_dir(kind):
    """Folder holding the built-in resources of `kind` (palettes, templates, godot_addon)."""
    packaged = _PACKAGED[kind]
    return packaged if os.path.isdir(packaged) else _SOURCE[kind]


def builtin_palette(name):
    """Path of a built-in palette by name ('gothic', 'gothic.yaml'), or None."""
    base = os.path.basename(name)
    if not base.endswith('.yaml'):
        base += '.yaml'
    path = os.path.join(data_dir('palettes'), base)
    return path if os.path.exists(path) else None


def template(name):
    """Path of a spec template by name ('humanoid'), or None."""
    path = os.path.join(data_dir('templates'), f'{name}.yaml')
    return path if os.path.exists(path) else None


def templates():
    return sorted(os.path.splitext(f)[0] for f in os.listdir(data_dir('templates')) if f.endswith('.yaml'))
