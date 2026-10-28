"""Design 09: surface paint colours regions of a part without new geometry."""

import numpy as np
import pytest

from spritekiln import pipeline
from spritekiln import spec as S
from spritekiln.pixelize import hx
from spritekiln.rig import rest_env

SPEC = """spritekiln: 1
name: painted
kind: character
size: 48
directions: 8
camera: {pitch: 38, scale: 0.05, center: [0, 0.7, 0]}
shadow: null
ramps:
  stone: ["#14121c", "#3a3f52", "#6b7390", "#a7b0c8", "#e6ebf5"]
  red: ["#2a0a10", "#7a1a28", "#c0303a", "#f06070"]
  glow: ["#2a0a00", "#ff5a1f", "#ffb070"]
materials:
  stone: {ramp: stone}
  red: {ramp: red}
  glow: {ramp: glow, emissive: true, band: 2}
bones:
  hips: {parent: root, pos: [0, 0.5, 0]}
  shoulder_L: {parent: hips, pos: [0.3, 0.3, 0]}
parts:
  column:
    material: stone
    space: hips
    prims: [{cylinder: {a: [0, -0.4, 0], b: [0, 0.6, 0], r: 0.18}}]
    paint:
%s
  arm_L:
    material: stone
    space: shoulder_L
    prims: [{sphere: {c: [0, 0, 0], r: 0.14}}]
    paint:
      - material: red
        prims: [{box: {c: [0.1, 0, 0], half: [0.06, 0.2, 0.2]}}]
"""
BANDS = """      - material: red
        stripes: {axis: y, at: [-0.1, 0.3], width: 0.1}"""


def _spec(tmp_path, layers=BANDS):
    p = tmp_path / 'painted.yaml'
    p.write_text(SPEC % layers, encoding='utf-8')
    return S.load(str(p))


def _frame(spec, yaw):
    return pipeline.render_frame(spec, rest_env(spec, yaw), yaw)


def _color_rows(spec, img, material):
    cols = {tuple(hx(c)) for c in spec['materials'][material]['colors']}
    m = np.array([[tuple(px[:3]) in cols and px[3] == 255 for px in row] for row in img])
    return m


def test_bands_stay_at_the_same_height_in_every_direction(tmp_path):
    spec = _spec(tmp_path)
    rows = []
    for _, yaw in spec['directions']:
        gb = pipeline.render_buffers(spec, rest_env(spec, yaw), yaw)[0]
        rows.append(set(np.nonzero((gb.paint == 0).any(1))[0]))  # layer 0: the column's bands
    assert rows[0] and all(r == rows[0] for r in rows)  # a band around a vertical column: same rows from all sides


def test_painting_adds_no_part(tmp_path):
    spec = _spec(tmp_path)
    assert {g.name for g in pipeline.render_buffers(spec, rest_env(spec, 0.0), 0.0)[1]} == {'column', 'arm_L', 'arm_R'}
    assert _frame(spec, 0.0).materials.get('red', 0) > 10


def test_paint_on_a_mirrored_part_is_mirrored(tmp_path):
    spec = _spec(tmp_path)
    gb = pipeline.render_buffers(spec, rest_env(spec, 0.0), 0.0)[0]
    painted_arms = gb.paint >= 1  # layer 0 is the column's, 1 and 2 the arms'
    assert painted_arms.any() and np.array_equal(painted_arms, painted_arms[:, ::-1])


@pytest.mark.parametrize(
    'layers',
    [
        '      - material: red\n        grid: {axes: [x, y], spacing: [0.12, 0.12], r: 0.03}',
        '      - material: red\n        spots: {scale: 0.08, density: 0.4, seed: 3}',
        '      - material: red\n        checker: {size: 0.12}',
        '      - material: red\n        rings: {axis: z, period: 0.2, width: 0.08}',
        '      - material: red\n        stripes: {axis: y, period: 0.2, width: 0.08}\n        edge: true',
    ],
    ids=['grid', 'spots', 'checker', 'rings', 'stripes with edge'],
)
def test_patterns_paint_part_of_the_surface(tmp_path, layers):
    spec = _spec(tmp_path, layers)
    counts = _frame(spec, 0.0).materials
    assert counts.get('red', 0) > 10 and counts.get('stone', 0) > 10


def test_emissive_paint_glows_in_the_emissive_map(tmp_path):
    spec = _spec(tmp_path, '      - material: glow\n        stripes: {axis: y, at: [0.1], width: 0.1}')
    assert (_frame(spec, 0.0).emissive[..., 3] > 0).sum() > 5


def test_paint_mistakes(tmp_path):
    errors, _ = S.check(_spec(tmp_path, '      - material: gold\n        rings: {axis: y, at: [0.1], width: 0.1}'))
    assert any('parts.column.paint[0].material: unknown material "gold"' in e for e in errors)
    _, warnings = S.check(
        _spec(tmp_path, '      - material: red\n        stripes: {axis: y, period: 0.2, width: 0.02}')
    )
    assert any('parts.column.paint[0].stripes: width 0.020' in w for w in warnings)
