"""Sockets: positions agree with the rendered pixels, mirror, hide with `when`, and reach the JSON."""

import json
import os

import numpy as np
import pytest

from spritekiln import spec as S
from spritekiln.anim import frames_of
from spritekiln.cli import main
from spritekiln.pipeline import render_frame
from spritekiln.render import Camera
from spritekiln.rig import rest_env

from conftest import FIXTURES, stage_spec

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')


@pytest.fixture(scope='module')
def spec(tmp_path_factory):
    return S.load(stage_spec(tmp_path_factory.mktemp('sockets'), MINIMAL))


def _pivot(sp):
    return np.array(Camera.from_spec(sp).project([0.0, 0.0, 0.0]))


def test_eye_sockets_sit_on_the_rendered_eyes(spec):
    fr = render_frame(spec, rest_env(spec, 0), 0)
    ys, xs = np.nonzero(fr.emissive[..., 3] > 0)  # both emissive eyes, facing the camera
    centroid = np.array([xs.mean() + 0.5, ys.mean() + 0.5]) - _pivot(spec)
    mid = (np.array(fr.sockets['eye_L'][:2]) + np.array(fr.sockets['eye_R'][:2])) / 2
    assert np.abs(centroid - mid).max() <= 1.0, (centroid, mid)


def test_mirrored_twin_and_depth(spec):
    s = render_frame(spec, rest_env(spec, 0), 0).sockets
    assert s['eye_L'][0] > 0 > s['eye_R'][0]  # +x (her left) shows on the screen's right
    assert s['eye_L'][0] == pytest.approx(-s['eye_R'][0], abs=0.02)
    assert s['eye_L'][2] > 0  # facing the viewer: eyes in front of the body axis
    n = render_frame(spec, rest_env(spec, 180), 180).sockets
    assert n['eye_L'][2] < 0  # facing away: behind


def test_when_hides_a_socket(spec):
    idle = render_frame(spec, frames_of(spec, 'idle', 0)[0][0], 0).sockets
    hit = render_frame(spec, frames_of(spec, 'attack', 0)[1][0], 0).sockets
    assert idle['smear'] is None and hit['smear'] is not None
    assert idle['staff_tip'] is not None


def test_sockets_in_the_json(tmp_path):
    main(['render', stage_spec(tmp_path, MINIMAL), '--jobs', '1', '-o', str(tmp_path / 'out' / 'minimal')])
    with open(tmp_path / 'out' / 'minimal' / 'minimal.json', encoding='utf-8') as fh:
        block = json.load(fh)['spritekiln']
    assert block['sockets'] == ['eye_L', 'staff_tip', 'smear', 'eye_R']
    clip = block['animations']['attack']['directions']['e']
    assert set(clip['sockets']) == set(block['sockets'])
    assert all(len(v) == len(clip['frames']) for v in clip['sockets'].values())
    assert clip['sockets']['smear'][0] is None and len(clip['sockets']['smear'][1]) == 3


def test_unknown_socket_bone_is_an_error(tmp_path):
    text = open(MINIMAL, encoding='utf-8').read().replace('bone: wrist_R', 'bone: wrist_X')
    p = tmp_path / 'bad.yaml'
    p.write_text(text, encoding='utf-8')
    errors = S.validate(S.load(str(p)))
    assert any('sockets.staff_tip.bone: unknown frame "wrist_X"' in e for e in errors)
