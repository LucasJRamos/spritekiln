"""Design 07: materials answer light differently (finish presets, highlights, rim, toon thresholds)."""

import numpy as np
import pytest

from spritekiln import pipeline
from spritekiln import spec as S
from spritekiln.pixelize import band_of, hx
from spritekiln.rig import rest_env

BALL = """spritekiln: 1
name: ball
kind: prop
size: 32
directions: 4
camera: {pitch: 38, scale: 0.05, center: [0, 0.4, 0]}
shadow: null
ramps:
  steel: ["#14121c", "#3a3f52", "#6b7390", "#a7b0c8", "#e6ebf5"]
materials:
  steel: {ramp: steel%s}
parts:
  ball:
    material: steel
    prims: [{sphere: {c: [0, 0.4, 0], r: 0.45}}]
"""


def _spec(tmp_path, extra=''):
    p = tmp_path / 'ball.yaml'
    p.write_text(BALL % extra, encoding='utf-8')
    return S.load(str(p))


def test_finish_presets_and_explicit_fields(tmp_path):
    m = _spec(tmp_path, ', finish: metal')['materials']['steel']
    assert m['highlight'] == S.FINISHES['metal']['highlight'] and m['rim'] == 0.6
    m = _spec(tmp_path, ', finish: metal, rim: 0.1, highlight: {size: 0.9}')['materials']['steel']
    assert m['rim'] == 0.1 and m['highlight'] == {'size': 0.9}  # what the material says wins
    assert _spec(tmp_path, ', finish: matte')['materials']['steel']['highlight'] is None


def _top_tone_pixels(spec, yaw):
    img = pipeline.render_frame(spec, rest_env(spec, yaw), yaw, force=True, maps=False).img
    top = hx(spec['materials']['steel']['colors'][-1])
    return (img[..., :3] == top).all(-1) & (img[..., 3] == 255)


@pytest.mark.parametrize('yaw', [0.0, 90.0, 180.0, -90.0])
def test_metal_has_one_small_highlight_in_every_direction(tmp_path, yaw):
    plain = _top_tone_pixels(_spec(tmp_path), yaw)
    metal = _top_tone_pixels(_spec(tmp_path, ', finish: metal'), yaw)
    assert plain.sum() > 8  # without a highlight the lit side uses the top tone broadly
    assert 1 <= metal.sum() <= 4  # with one, the top tone is a small cluster (max_px 4)
    ys, xs = np.nonzero(metal)
    assert ys.mean() < 16  # on the upper half, facing the light


def test_thresholds_make_hard_toon_steps():
    M = dict(
        colors=['#000', '#111', '#222', '#333', '#444'], emissive=False, bands=None, gamma=1.0, thresholds=[0.3, 0.7]
    )
    assert band_of(M, np.array([0.0, 0.29, 0.3, 0.69, 0.7, 1.0])).tolist() == [1, 1, 2, 2, 3, 3]


def test_rim_strength_per_material(tmp_path):
    def mean_value(extra):
        spec = _spec(tmp_path, extra)
        img = pipeline.render_frame(spec, rest_env(spec, 180.0), 180.0, force=True, maps=False).img
        return img[img[..., 3] == 255][:, :3].astype(float).mean()

    assert mean_value(', rim: 1.0') > mean_value(', rim: 0.0')


@pytest.mark.parametrize(
    'extra, message',
    [
        (', highlight: {band: 9}', 'highlight.band: 9 is outside its ramp'),
        (', thresholds: [0.7, 0.3]', 'thresholds: [0.7, 0.3]'),
    ],
)
def test_material_mistakes(tmp_path, extra, message):
    errors, _ = S.check(_spec(tmp_path, extra))
    assert any(message in e for e in errors), errors
