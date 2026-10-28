"""Design 13: shapes beyond rounded primitives (extrude, revolve, tube, plane), modifiers and joins."""

import os

import numpy as np
import pytest

from spritekiln import sdf
from spritekiln import spec as S
from spritekiln.cli import main
from spritekiln.rig import build, rest_env

from conftest import FIXTURES, assert_image_matches, stage_spec

SHAPES = os.path.join(FIXTURES, 'shapes', 'shapes.yaml')
RNG = np.random.default_rng(3)
PTS = RNG.uniform(-1.2, 1.2, (6000, 3))
R = sdf.rot_y(0.4) @ sdf.rot_x(0.3)
C = np.array([0.1, 0.2, -0.1])


@pytest.mark.parametrize(
    'name, shape, same',
    [
        ('extrude(rect) is a box', sdf.extrude(C, R, sdf.rect(0.4, 0.25), 0.3), sdf.box(C, [0.4, 0.25, 0.15], R)),
        (
            'extrude(rounded rect, round) is a rounded box',
            sdf.extrude(C, R, sdf.rect(0.4, 0.25, round_=0.05), 0.3, 0.05),
            sdf.box(C, [0.4, 0.25, 0.15], R, 0.05),
        ),
        (
            'extrude(square polygon) is a box',
            sdf.extrude(C, R, sdf.polygon([[-0.4, -0.25], [-0.4, 0.25], [0.4, 0.25], [0.4, -0.25]]), 0.3),
            sdf.box(C, [0.4, 0.25, 0.15], R),
        ),
        (
            'revolve(rect) is a cylinder',
            sdf.revolve(C, R, sdf.rect(0.35, 0.3)),
            sdf.cylinder(C + R @ [0, -0.3, 0], C + R @ [0, 0.3, 0], 0.35),
        ),
        (
            'revolve(circle, offset) is a torus',
            sdf.revolve(C, R, sdf.circle(0.1), offset=0.4),
            sdf.torus(C, 0.4, 0.1, R),
        ),
        (
            'a straight tube is a capsule',
            sdf.tube([[-0.5, 0.1, 0.2], [0.05, -0.05, 0.1], [0.6, -0.2, 0.0]], 0.2),
            sdf.round_cone([-0.5, 0.1, 0.2], [0.6, -0.2, 0.0], 0.2, 0.2),
        ),
        (
            'an elongated sphere is a capsule',
            sdf.modified(sdf.sphere(C, 0.2), C, R, elongate=[0.3, 0, 0]),
            sdf.round_cone(C + R @ [-0.3, 0, 0], C + R @ [0.3, 0, 0], 0.2, 0.2),
        ),
    ],
)
def test_shapes_equal_their_known_twins(name, shape, same):
    np.testing.assert_allclose(shape(PTS), same(PTS), atol=1e-9, err_msg=name)


def test_shell_and_plane():
    ball = sdf.sphere(C, 0.5)
    np.testing.assert_allclose(sdf.modified(ball, C, None, shell=0.1)(PTS), np.abs(ball(PTS)) - 0.05)
    np.testing.assert_allclose(sdf.plane([0, 0.3, 0], [0, 2, 0])(PTS), 0.3 - PTS[:, 1])


@pytest.mark.parametrize(
    'shape',
    [
        sdf.extrude(C, R, sdf.polygon([[0, 0.5], [0.3, -0.2], [-0.25, -0.3]]), 0.2),
        sdf.extrude(C, R, sdf.rect(0.4, 0.2, chamfer=0.08), 0.1),
        sdf.revolve(
            C, R, sdf.bezier_path([[-0.15, -0.08], [0, -0.12], [0.15, -0.08], [0.2, 0.1], [0, 0.18], [-0.2, 0.1]])
        ),
        sdf.tube([[-0.5, 0, 0], [0, 0.6, 0.2], [0.5, 0, -0.3], [0.6, -0.4, 0]], 0.1),
    ],
    ids=['extrude polygon', 'extrude chamfered rect', 'revolve bezier', 'tube'],
)
def test_exact_shapes_are_distances(shape):
    """Outside an exact distance field the gradient has length 1."""
    e = 1e-5
    grad = np.stack([(shape(PTS + e * np.eye(3)[i]) - shape(PTS - e * np.eye(3)[i])) / (2 * e) for i in range(3)], -1)
    out = shape(PTS) > 0.02
    assert np.percentile(np.linalg.norm(grad[out], axis=1), [1, 99]) == pytest.approx([1, 1], abs=2e-3)


def test_a_bezier_path_has_the_right_inside():
    pts = []
    for i in range(8):  # a circle of radius 0.5 from eight quadratic arcs
        a0, a1 = i * np.pi / 4, (i + 0.5) * np.pi / 4
        k = 0.5 / np.cos(np.pi / 8)
        pts += [[0.5 * np.cos(a0), 0.5 * np.sin(a0)], [k * np.cos(a1), k * np.sin(a1)]]
    q = PTS[:, :2]
    d, ci = sdf.bezier_path(pts)(q), sdf.circle(0.5)(q)
    assert np.abs(d - ci).max() < 0.005
    far = np.abs(ci) > 0.01
    assert (np.sign(d[far]) == np.sign(ci[far])).all()


def test_joins():
    a, b = np.array([0.0, 0.1, -0.05, 0.3]), np.array([0.05, 0.0, 0.2, -0.1])
    for mode in (sdf.CHAMFER, sdf.ROUND, sdf.STAIRS):
        np.testing.assert_allclose(sdf.join(a, b, mode, 0.0), np.minimum(a, b))  # no radius: a plain union
        assert (sdf.join(a, b, mode, 0.1, 3) <= np.minimum(a, b) + 1e-12).all()  # a join only adds material
    groove = sdf.carve(np.full(4, -0.3), np.array([0.0, 0.004, 0.02, -0.5]), sdf.GROOVE, 0, groove=(0.02, 0.01))
    assert groove[0] > -0.3 and groove[3] == -0.3  # carved where the cutter's surface crosses, untouched elsewhere


def _groups(path):
    spec = S.load(path)
    return {g.name: g for g in build(spec, rest_env(spec, 0.0))[0]}


@pytest.mark.parametrize('left', ['blade_L', 'guard_L', 'horn_L'])
def test_mirrored_twins_are_mirror_images(tmp_path, left):
    """_R parts are the mirror image of _L parts, even for an asymmetric profile and a bend."""
    groups = _groups(stage_spec(tmp_path, SHAPES))
    gl, gr = groups[left], groups[left.replace('_L', '_R')]
    p = gl.bc + RNG.uniform(-1, 1, (3000, 3)) * gl.br
    np.testing.assert_allclose(gr(p * [-1, 1, 1], exact_within=10), gl(p, exact_within=10), atol=1e-9)


def _write(tmp_path, parts):
    text = open(SHAPES, encoding='utf-8').read().split('parts:\n')[0] + 'parts:\n' + parts
    p = tmp_path / 'variant.yaml'
    p.write_text(text + 'animations:\n  idle: {frames: 1, ms: 100}\n', encoding='utf-8')
    return str(p)


def test_validate_warns_about_thin_and_crossing_shapes(tmp_path):
    path = _write(
        tmp_path,
        '  a:\n    material: steel\n    prims:\n      - sphere: {c: [0, 1, 0], r: 0.3, shell: 0.01}\n'
        '  b:\n    material: steel\n    prims:\n'
        '      - extrude: {profile: {polygon: [[0, 0], [0.2, 0.2], [0.2, 0], [0, 0.2]]}, depth: 0.1}\n',
    )
    errors, warnings = S.check(S.load(path))
    assert not errors
    text = '\n'.join(warnings)
    assert 'parts.a.prims[0].sphere.shell: shell thickness 0.010 is 0.2 px' in text
    assert 'parts.b.prims[0].extrude.profile.polygon: two edges cross' in text


@pytest.mark.parametrize(
    'part, message',
    [
        ('prims: [{plane: {n: [0, 1, 0]}}]', 'a plane has no end: use it under cut:'),
        ('prims: [{extrude: {profile: {bezier: [[0, 0], [1, 0], [1, 1]]}, depth: 0.1}}]', 'a bezier path is P0, C0'),
        ('prims: [{sphere: {c: [0, 1, 0], r: 0.2}}]\n    blend: {mode: groove}', "'groove' (use smooth, chamfer"),
        ('prims: [{chain: {pts: [[0, 0, 0], [0, 1, 0]], r: [0.1, 0.1], twist: 1}}]', 'change one primitive'),
    ],
)
def test_shape_mistakes_are_errors(tmp_path, part, message):
    errors, _ = S.check(S.load(_write(tmp_path, f'  a:\n    material: steel\n    {part}\n')))
    assert any(message in e for e in errors), errors


def test_shapes_pose_golden(tmp_path, update_golden):
    out = str(tmp_path / 'shapes.png')
    main(['pose', stage_spec(tmp_path, SHAPES), '--dirs', 'all', '--scale', '1', '--no-crop', '-o', out])
    assert_image_matches(out, 'shapes_pose_rest.png', update_golden)


def test_thin_warnings_speak_in_the_spec_numbers(tmp_path):
    """Under a scaled bone the warning gives the value written in the spec and the value it needs."""
    text = open(SHAPES, encoding='utf-8').read()
    text = text.replace('  hand_L: {parent: hips, pos: [0.36, 0.05, 0.12]}\n', '  big: {parent: hips, scale: 2}\n', 1)
    text = text.split('parts:\n')[0] + 'parts:\n'
    text += (
        '  a:\n    material: steel\n    space: big\n    prims:\n      - sphere: {c: [0, 0, 0], r: 0.1, shell: 0.02}\n'
    )
    p = tmp_path / 'scaled.yaml'
    p.write_text(text + 'animations:\n  idle: {frames: 1, ms: 100}\n', encoding='utf-8')
    _, warnings = S.check(S.load(str(p)))
    assert any('shell thickness 0.020 is 0.8 px' in w and 'at least 0.025' in w for w in warnings), warnings


def test_validate_counts_primitives_and_cuts(tmp_path):
    from spritekiln import api

    summary = api.validate(stage_spec(tmp_path, SHAPES))['summary']
    assert (summary['primitives'], summary['cuts']) == (13, 4)
