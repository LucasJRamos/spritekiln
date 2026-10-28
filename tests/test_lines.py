"""Design 08: creases and edge highlights from normals inside one part."""

import numpy as np

from spritekiln import pipeline
from spritekiln import spec as S
from spritekiln.pixelize import hx
from spritekiln.rig import rest_env

PROP = """spritekiln: 1
name: prop
kind: prop
size: 32
directions: 4
camera: {pitch: 38, scale: 0.05, center: [0, 0.4, 0]}
shadow: null
ramps:
  stone: ["#14121c", "#3a3f52", "#6b7390", "#a7b0c8", "#e6ebf5"]
materials:
  stone: {ramp: stone%s}
parts:
  block:
    material: stone
    prims: [%s]
"""
L_SHAPE = '{box: {c: [0, 0.2, 0], half: [0.4, 0.2, 0.3]}}, {box: {c: [-0.25, 0.55, 0], half: [0.15, 0.2, 0.3]}}'
BALL = '{sphere: {c: [0, 0.4, 0], r: 0.4}}'


def _img(tmp_path, prims, extra=''):
    p = tmp_path / 'prop.yaml'
    p.write_text(PROP % (extra, prims), encoding='utf-8')
    spec = S.load(str(p))
    return spec, pipeline.render_frame(spec, rest_env(spec, 0.0), 0.0, force=True, maps=False).img


def _count(spec, img, index):
    col = hx(spec['materials']['stone']['colors'][index])
    return int(((img[..., :3] == col).all(-1) & (img[..., 3] == 255)).sum())


def test_a_concave_corner_gets_a_crease_line(tmp_path):
    spec, plain = _img(tmp_path, L_SHAPE)
    _, creased = _img(tmp_path, L_SHAPE, ', crease: true')
    line = spec['materials']['stone']['line_band']
    assert _count(spec, creased, line) >= _count(spec, plain, line) + 3  # a line along the inner corner


def test_a_round_surface_has_no_creases(tmp_path):
    _, plain = _img(tmp_path, BALL)
    _, creased = _img(tmp_path, BALL, ', crease: true')
    np.testing.assert_array_equal(plain, creased)


def test_convex_edges_facing_the_light_go_up_a_tone(tmp_path):
    spec, plain = _img(tmp_path, L_SHAPE)
    _, edged = _img(tmp_path, L_SHAPE, ', edge_highlight: true')
    changed = (plain != edged).any(-1)
    assert changed.any()
    # every changed pixel got lighter
    assert (edged[changed][:, :3].astype(int).sum(-1) > plain[changed][:, :3].astype(int).sum(-1)).all()
