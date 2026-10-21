"""Compatibility shim: pxforge is now SpriteKiln (`spritekiln`).

`import pxforge`, `import pxforge.<module>` and `python -m pxforge` keep working for existing projects
(Hunt Tower) until they migrate. New code should import `spritekiln`.
"""
import importlib
import sys

from spritekiln import __version__  # noqa: F401

_MODULES = ('anim', 'cli', 'export', 'expr', 'godot', 'palette', 'pipeline', 'pixelize', 'qa', 'ref',
            'render', 'rig', 'sdf', 'spec')

for _name in _MODULES:
    _mod = importlib.import_module(f'spritekiln.{_name}')
    sys.modules[f'{__name__}.{_name}'] = _mod
    globals()[_name] = _mod
