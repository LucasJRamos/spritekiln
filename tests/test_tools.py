"""Release helpers in tools/."""

import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import package_godot_addon  # noqa: E402


def test_godot_addon_zip(tmp_path):
    version, plugin = package_godot_addon.versions()
    assert version == plugin, 'plugin.cfg and spritekiln.__version__ must match'
    path = package_godot_addon.package(str(tmp_path))
    names = zipfile.ZipFile(path).namelist()
    top = f'spritekiln-godot-{version}/addons/spritekiln/'
    assert all(n.startswith(top) for n in names)
    for f in ('plugin.cfg', 'plugin.gd', 'kiln_sprite_2d.gd', 'kiln_builder.gd', 'LICENSE', 'README.md', 'icon.svg'):
        assert top + f in names
