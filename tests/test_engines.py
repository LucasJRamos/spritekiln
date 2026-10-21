"""Exports for engines without a dedicated exporter: files copied where the engine wants them."""

import os
import shutil

import pytest

from spritekiln import api

from conftest import FIXTURES, GOLDEN, stage_spec

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')


@pytest.fixture
def rendered(tmp_path):
    """The fixture's golden render placed where `render` would write it."""
    spec = stage_spec(tmp_path, MINIMAL)
    out = os.path.join(os.path.dirname(spec), 'out', 'minimal')
    os.makedirs(out)
    for suffix in ('.json', '.png', '_normal.png', '_emissive.png'):
        shutil.copy(os.path.join(GOLDEN, f'render_minimal{suffix}'), os.path.join(out, f'minimal{suffix}'))
    return spec


@pytest.mark.parametrize(
    'engine, meta', [('generic', 'minimal.json'), ('monogame', 'minimal.json'), ('unity', 'minimal.kiln')]
)
def test_export_copies_atlases_and_metadata(tmp_path, rendered, engine, meta):
    w = api.export(rendered, engine, dest=str(tmp_path / 'game'))
    files = sorted(os.listdir(w['dir']))
    assert files == sorted([meta, 'minimal.png', 'minimal_normal.png', 'minimal_emissive.png'])
    with open(os.path.join(GOLDEN, 'render_minimal.json'), 'rb') as a, open(os.path.join(w['dir'], meta), 'rb') as b:
        assert a.read() == b.read()  # the same JSON, only renamed for Unity
