import glob
import os
import textwrap

import numpy as np
import pytest

from spritekiln import spec as S

from conftest import REPO

ALL_SPECS = sorted(glob.glob(os.path.join(REPO, 'specs', '*', '*', '*.yaml')))

BASE = """
pxforge: 1
name: t
ramps:
  body: ["#111111", "#444444", "#888888", "#cccccc"]
  glow: ["#220000", "#ff0000"]
materials:
  body: {}
  eye: {ramp: glow, emissive: true}
channels:
  bob: 0.0
  hand_L: [0.3, 0.5, 0.0]
bones:
  hips: {parent: root, pos: "[0, 0.6 + bob, 0]"}
  shoulder_L: {parent: hips, pos: [0.2, 0.3, 0]}
ik:
  arm_L: {start: shoulder_L, space: hips, target: hand_L, lengths: [0.2, 0.2], joint: elbow_L, end: wrist_L}
parts:
  torso: {material: body, space: hips, prims: [{sphere: {c: [0, 0, 0], r: 0.2}}]}
  arm_L: {material: body, prims: [{cone: {a: "@shoulder_L", b: "@wrist_L", r: [0.05, 0.04]}}]}
"""


def write(tmp_path, text, name='t.yaml'):
    p = tmp_path / name
    p.write_text(textwrap.dedent(text), encoding='utf-8')
    return str(p)


@pytest.mark.parametrize('path', ALL_SPECS, ids=lambda p: os.path.basename(p))
def test_every_repo_spec_validates(path):
    assert S.validate(S.load(path)) == []


def test_defaults(tmp_path):
    s = S.load(write(tmp_path, BASE))
    assert s['kind'] == 'character' and s['size'] == 64
    assert s['camera']['pitch'] == 38.0 and s['camera']['supersample'] == 3
    assert s['light']['shadows'] is True
    assert s['directions'] == S.DIRECTIONS8
    assert s['shadow'] == {'rx': 13.5, 'ry': 4.5}
    assert s['_dir'] == str(tmp_path)


def test_props_default_to_one_direction(tmp_path):
    s = S.load(write(tmp_path, BASE + 'kind: prop\n'))
    assert s['directions'] == [('s', 0)]


@pytest.mark.parametrize('value, expected', [
    (4, S.DIRECTIONS4),
    (1, [('s', 0)]),
    ('[s, ne]', [('s', 0), ('ne', 135)]),
])
def test_directions(tmp_path, value, expected):
    s = S.load(write(tmp_path, BASE + f'directions: {value}\n'))
    assert s['directions'] == expected


def test_bad_directions(tmp_path):
    with pytest.raises(S.SpecError):
        S.load(write(tmp_path, BASE + 'directions: 3\n'))


def test_mirroring_creates_right_twins(tmp_path):
    s = S.load(write(tmp_path, BASE))
    assert s['bones']['shoulder_R'] == {'parent': 'hips', 'pos': [0.2, 0.3, 0], '_mirror': True}
    ik = s['ik']['arm_R']
    assert (ik['target'], ik['joint'], ik['end'], ik['_mirror']) == ('hand_R', 'elbow_R', 'wrist_R', True)
    assert s['parts']['arm_R']['prims'][0]['cone']['b'] == '@wrist_R'
    assert s['channels']['hand_R'] == [0.3, 0.5, 0.0]
    assert '_mirror' not in s['bones']['shoulder_L']


def test_explicit_right_side_is_kept():
    sec = S.mirror_section({'a_L': {'x': 'b_L'}, 'a_R': {'x': 'custom'}})
    assert sec['a_R'] == {'x': 'custom'}


def test_side_suffix_must_end_the_token():
    sec = S.mirror_section({'arm_Long': 1, 'leg_L': {'expr': 'k_L + k_Lx + w_L*2'}})
    assert 'arm_Rong' not in sec
    assert sec['leg_R']['expr'] == 'k_R + k_Lx + w_R*2'


def test_yaml_keeps_on_off_yes_no_as_strings():
    data = S.yload('{on: 1, off: 2, y: 3, n: 4, a: true, b: False, c: yes}')
    assert data == {'on': 1, 'off': 2, 'y': 3, 'n': 4, 'a': True, 'b': False, 'c': 'yes'}


def test_materials(tmp_path):
    s = S.load(write(tmp_path, BASE))
    body, eye = s['materials']['body'], s['materials']['eye']
    assert body['colors'] == ['#111111', '#444444', '#888888', '#cccccc']
    assert body['outline'] and body['line'] and not body['emissive']
    assert eye['emissive'] and not eye['outline'] and not eye['line']


def test_inline_ramp_list(tmp_path):
    s = S.load(write(tmp_path, BASE.replace('body: {}', 'body: {ramp: ["#000000", "#ffffff"]}')))
    assert s['materials']['body']['colors'] == ['#000000', '#ffffff']


def test_unknown_ramp(tmp_path):
    with pytest.raises(S.SpecError, match='ramp "nope" not found'):
        S.load(write(tmp_path, BASE.replace('body: {}', 'body: {ramp: nope}')))


def test_palette_files_and_fallback(tmp_path):
    text = BASE.replace('  body: {}', '  body: {}\n  stone: {}') + 'palette: ../../palettes/gothic.yaml\n'
    s = S.load(write(tmp_path, text))        # path does not exist next to tmp: falls back to specs/palettes
    assert 'stone' in s['ramps'] and s['materials']['stone']['colors']


def test_size_override_keeps_framing(tmp_path, monkeypatch):
    monkeypatch.setenv('PXFORGE_SIZE', '32')
    s = S.load(write(tmp_path, BASE + 'size: 64\ncamera: {scale: 0.05}\nshadow: {rx: 10, ry: 4}\n'))
    assert s['size'] == 32
    assert s['camera']['scale'] == pytest.approx(0.1)
    assert s['shadow']['rx'] == pytest.approx(5) and s['shadow']['ry'] == pytest.approx(2)


def test_not_a_mapping(tmp_path):
    with pytest.raises(S.SpecError):
        S.load(write(tmp_path, '- 1\n- 2\n'))


@pytest.mark.parametrize('patch, message', [
    (('parent: root', 'parent: nowhere'), 'unknown frame "nowhere"'),
    (('torso: {material: body', 'torso: {material: cloth'), 'unknown material "cloth"'),
    (('lengths: [0.2, 0.2], ', ''), 'missing "lengths"'),
    (('prims: [{sphere: {c: [0, 0, 0], r: 0.2}}]', 'prims: []'), 'parts.torso: no prims'),
])
def test_validate_reports_problems(tmp_path, patch, message):
    s = S.load(write(tmp_path, BASE.replace(*patch)))
    probs = S.validate(s)
    assert any(message in p for p in probs), probs


def test_validate_reports_animation_errors(tmp_path):
    text = BASE + 'animations:\n  idle: {frames: 2, channels: {wobble: "sin(p)"}}\n'
    probs = S.validate(S.load(write(tmp_path, text)))
    assert probs and 'animations.idle' in probs[0] and 'wobble' in probs[0]


def test_validate_reports_expression_errors_with_location(tmp_path):
    s = S.load(write(tmp_path, BASE.replace('0.6 + bob', '0.6 + bobb')))
    probs = S.validate(s)
    assert probs and 'bones.hips.pos' in probs[0]


def test_rest_pose_builds_mirrored_ik(tmp_path):
    from spritekiln.rig import build, rest_env
    s = S.load(write(tmp_path, BASE))
    groups, frames = build(s, rest_env(s))
    assert {g.name for g in groups} == {'torso', 'arm_L', 'arm_R'}
    np.testing.assert_allclose(frames['wrist_L'].o * [-1, 1, 1], frames['wrist_R'].o, atol=1e-9)
    assert frames['wrist_L'].o[0] > 0
