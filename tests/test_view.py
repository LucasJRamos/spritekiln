"""`view`: top-down 3/4 (default) or side-scroller profile, with the same engine and workflow."""

import json
import os

import pytest

from spritekiln import config
from spritekiln import spec as S
from spritekiln.cli import main

from conftest import FIXTURES, assert_image_matches

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')


def side_fixture(tmp_path):
    """The minimal fixture switched to `view: side`, letting the preset choose camera, directions and shadow."""
    text = open(MINIMAL, encoding='utf-8').read()
    text = text.replace('directions: 4\n', 'view: side\n').replace('camera: {pitch: 38, ', 'camera: {')
    text = text.replace('shadow: {rx: 7, ry: 2.5, alpha: 120}\n', '')
    p = tmp_path / 'specs' / 'fixtures' / 'minimal_side.yaml'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.replace('name: minimal', 'name: minimal_side'), encoding='utf-8')
    return str(p)


def test_side_preset(tmp_path):
    sp = S.load(side_fixture(tmp_path))
    assert sp['view'] == 'side' and sp['camera']['pitch'] == 0
    assert sp['directions'] == [('e', 90), ('w', -90)] and sp['shadow'] is None
    assert S.validate(sp) == []


def test_topdown_is_the_default_and_explicit_values_win(tmp_path):
    sp = S.load(MINIMAL)
    assert sp['view'] == 'topdown' and sp['camera']['pitch'] == 38 and sp['shadow']
    text = open(side_fixture(tmp_path), encoding='utf-8').read().replace('camera: {', 'camera: {pitch: 10, ')
    p = tmp_path / 'tilted.yaml'
    p.write_text(text + 'directions: [e, w, s]\n', encoding='utf-8')
    sp = S.load(str(p))
    assert sp['camera']['pitch'] == 10 and [d for d, _ in sp['directions']] == ['e', 'w', 's']


def test_unknown_view(tmp_path):
    p = tmp_path / 'bad.yaml'
    p.write_text(open(MINIMAL, encoding='utf-8').read() + 'view: iso\n', encoding='utf-8')
    with pytest.raises(S.SpecError, match='view: must be one of topdown, side'):
        S.load(str(p))


def test_side_pose_golden(tmp_path, update_golden):
    out = str(tmp_path / 'side.png')
    main(['pose', side_fixture(tmp_path), '--scale', '1', '-o', out])  # default: the spec's directions (e, w)
    assert_image_matches(out, 'minimal_side_pose_rest.png', update_golden)


def test_side_render_json(tmp_path):
    main(['render', side_fixture(tmp_path), '--anims', 'idle', '--jobs', '1', '-o', str(tmp_path / 'out')])
    block = json.loads((tmp_path / 'out' / 'minimal_side.json').read_text(encoding='utf-8'))['spritekiln']
    assert block['view'] == 'side' and block['directions'] == ['e', 'w']
    assert block['camera']['pitch_deg'] == 0 and block['camera']['ground_k'] == 0 and block['camera']['height_k'] == 1


def test_side_project(tmp_path, monkeypatch):
    game = tmp_path / 'platformer'
    main(['init', str(game), '--view', 'side'])
    assert config.load(str(game))['defaults']['view'] == 'side'
    monkeypatch.chdir(game)
    main(['new', 'runner'])
    sp = S.load(str(game / 'art' / 'specs' / 'characters' / 'runner' / 'runner.yaml'))
    assert sp['view'] == 'side' and sp['camera']['pitch'] == 0 and [d for d, _ in sp['directions']] == ['e', 'w']
    assert sp['shadow'] is None and S.validate(sp) == []
    main(['new', 'boss', '--view', 'topdown'])
    sp = S.load(str(game / 'art' / 'specs' / 'characters' / 'boss' / 'boss.yaml'))
    assert sp['view'] == 'topdown' and len(sp['directions']) == 8
