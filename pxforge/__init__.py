"""Compatibility shim: pxforge is now SpriteKiln (`spritekiln`).

`import pxforge`, `import pxforge.<module>` and `python -m pxforge` keep working for existing projects
(Hunt Tower) until they migrate. New code should import `spritekiln`.
"""
import importlib
import sys

from spritekiln import __version__, system  # noqa: F401

system.limit_blas_threads()               # the shim serves the CLI: load numpy with one BLAS thread

_MODULES = ('anim', 'cli', 'export', 'expr', 'godot', 'palette', 'pipeline', 'pixelize', 'qa', 'ref',
            'render', 'rig', 'sdf', 'spec')

for _name in _MODULES:
    _mod = importlib.import_module(f'spritekiln.{_name}')
    sys.modules[f'{__name__}.{_name}'] = _mod
    globals()[_name] = _mod


def main(argv=None):
    """`pxforge` command: the spritekiln CLI under its old name."""
    from spritekiln.cli import main as _main
    _main(argv, prog='pxforge')
