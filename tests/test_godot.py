"""Godot exporter: generated resources against goldens, and both JSON block keys."""

import json
import os

import pytest

import pxforge
from spritekiln import spec as S
from spritekiln.cli import main
from spritekiln.errors import ExportError
from spritekiln.godot import block, export_godot

from conftest import FIXTURES, GOLDEN, stage_spec

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')
GODOT_FILES = ('minimal.tres', 'minimal_lit.tres', 'minimal_canvas.tres', 'minimal_emissive.tres', 'minimal.tscn')


@pytest.fixture(scope='module')
def rendered(tmp_path_factory):
    """The fixture rendered twice: by `spritekiln` and by the legacy `pxforge` command."""
    tmp = tmp_path_factory.mktemp('godot')
    spec = stage_spec(tmp, MINIMAL)
    main(['render', spec, '--jobs', '1', '-o', str(tmp / 'new' / 'minimal')])
    pxforge.main(['render', spec, '--jobs', '1', '-o', str(tmp / 'legacy' / 'minimal')])
    return tmp, spec


def _project(path):
    path.mkdir(parents=True)
    (path / 'project.godot').write_text('config_version=5\n', encoding='utf-8')
    return str(path)


def test_legacy_command_writes_the_old_block_key(rendered):
    tmp, _ = rendered
    with open(tmp / 'new' / 'minimal' / 'minimal.json', encoding='utf-8') as fh:
        new = json.load(fh)
    with open(tmp / 'legacy' / 'minimal' / 'minimal.json', encoding='utf-8') as fh:
        old = json.load(fh)
    assert 'spritekiln' in new and 'pxforge' not in new
    assert 'pxforge' in old and 'spritekiln' not in old
    assert new['spritekiln'] == old['pxforge']
    assert new['spritekiln']['format'] == 1
    assert new['spritekiln']['camera']['ground_k'] == 0.6157


@pytest.mark.parametrize('variant', ['new', 'legacy'])
def test_export_matches_goldens(tmp_path, rendered, update_golden, variant):
    tmp, spec_path = rendered
    project = _project(tmp_path / 'game')
    w = export_godot(S.load(spec_path), project, render_dir=str(tmp / variant / 'minimal'))
    out = os.path.join(project, 'assets', 'pxforge', 'minimal')
    assert w['res'] == 'res://assets/pxforge/minimal' and w['addon_installed']
    assert os.path.exists(os.path.join(project, 'addons', 'pxforge', 'px_sprite_2d.gd'))
    for name in GODOT_FILES:
        with open(os.path.join(out, name), encoding='utf-8') as fh:
            text = fh.read()
        golden = os.path.join(GOLDEN, 'godot', name)
        if update_golden and variant == 'new':
            os.makedirs(os.path.dirname(golden), exist_ok=True)
            with open(golden, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
            continue
        with open(golden, encoding='utf-8') as fh:
            assert text == fh.read(), f'{name} differs from tests/golden/godot/{name}'


def test_block_and_errors(tmp_path):
    assert block({'spritekiln': {'a': 1}}) == {'a': 1}
    assert block({'pxforge': {'a': 2}}) == {'a': 2}
    assert block({'meta': {}}) is None
    with pytest.raises(ExportError, match='render not found'):
        export_godot(S.load(MINIMAL), _project(tmp_path / 'g'), render_dir=str(tmp_path / 'nothing'))
