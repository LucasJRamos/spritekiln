"""The pxforge name keeps working (Hunt Tower calls `python -m pxforge` until it migrates)."""

import os
import subprocess
import sys

import spritekiln
import spritekiln.cli
import spritekiln.spec

from conftest import REPO


def test_shim_aliases_every_module():
    import pxforge.cli
    from pxforge.spec import load

    assert pxforge.cli is spritekiln.cli
    assert load is spritekiln.spec.load
    assert pxforge.palette is sys.modules['spritekiln.palette']
    assert pxforge.__version__ == spritekiln.__version__


def test_python_dash_m_pxforge_runs_the_cli():
    gargoyle = os.path.join(REPO, 'specs', 'characters', 'gargula', 'gargula.yaml')
    for module in ('pxforge', 'spritekiln'):
        r = subprocess.run(
            [sys.executable, '-m', module, 'validate', gargoyle],
            cwd=REPO,
            capture_output=True,
            text=True,
            encoding='utf-8',
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.startswith('OK: gargula')
