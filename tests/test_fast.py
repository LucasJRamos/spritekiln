"""The numba backend (spritekiln[fast]) against the numpy reference, and how a backend is chosen."""

import os

import numpy as np
import pytest

from spritekiln import backend, cache, pipeline, sdf
from spritekiln import spec as S
from spritekiln.errors import SpriteKilnError
from spritekiln.rig import rest_env

from conftest import FIXTURES, REPO, stage_spec

GARGOYLE = os.path.join(REPO, 'specs', 'characters', 'gargula', 'gargula.yaml')
MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')
SHAPES = os.path.join(FIXTURES, 'shapes', 'shapes.yaml')


def _rot(rng):
    q, r = np.linalg.qr(rng.normal(size=(3, 3)))
    return q * np.sign(np.diag(r))  # a random rotation (or reflection; both are valid frames here)


def _primitives(rng):
    v = lambda: rng.uniform(-0.6, 0.6, 3)  # noqa: E731
    return {
        'sphere': sdf.sphere(v(), 0.3),
        'ellipsoid': sdf.ellipsoid(v(), [0.3, 0.15, 0.22], _rot(rng)),
        'ellipsoid (no rotation)': sdf.ellipsoid(v(), [0.2, 0.35, 0.1]),
        'cone': sdf.round_cone(v(), v(), 0.2, 0.08),
        'cone (r2 > r1)': sdf.round_cone(v(), v(), 0.05, 0.25),
        'box': sdf.box(v(), [0.3, 0.1, 0.2], _rot(rng), 0.04),
        'cylinder': sdf.cylinder(v(), v(), 0.15, 0.03),
        'torus': sdf.torus(v(), 0.3, 0.07, _rot(rng)),
        'triangle': sdf.triangle(v(), v(), v(), 0.02),
        'plane': sdf.plane(v(), v()),
        'extrude polygon': sdf.extrude(
            v(), _rot(rng), sdf.polygon([[0, 0.5], [0.3, -0.2], [-0.25, -0.3]], 0.02), 0.2, 0.03
        ),
        'extrude chamfered rect': sdf.extrude(v(), _rot(rng), sdf.rect(0.4, 0.2, chamfer=0.08), 0.1),
        'extrude bezier': sdf.extrude(
            v(), _rot(rng), sdf.bezier_path([[0.1, -0.3], [0.5, 0], [0.1, 0.3], [-0.2, 0.1]]), 0.1
        ),
        'revolve circle': sdf.revolve(v(), _rot(rng), sdf.circle(0.1), offset=0.4),
        'revolve partial': sdf.revolve(v(), _rot(rng), sdf.rect(0.35, 0.3, round_=0.05), angle=[-1.0, 2.0]),
        'tube': sdf.tube([v(), v(), v(), v()], 0.1, 0.03),
        'twist, bend, shell': sdf.modified(
            sdf.box(v(), [0.3, 0.4, 0.1], _rot(rng)), v(), _rot(rng), 0.04, None, 1.5, 0.7
        ),
        'elongate': sdf.modified(
            sdf.ellipsoid(v(), [0.2, 0.1, 0.15], _rot(rng)), v(), _rot(rng), elongate=[0.2, 0, 0.1]
        ),
    }


fast = pytest.importorskip('spritekiln.fast', reason='the fast extra (numba) is not installed')


@pytest.mark.parametrize('name', list(_primitives(np.random.default_rng(0))))
def test_every_primitive_matches_the_reference(name):
    rng = np.random.default_rng(7)
    prim = _primitives(rng)[name]
    pts = rng.uniform(-1.2, 1.2, (4000, 3))
    np.testing.assert_allclose(fast.distances(prim, pts), prim(pts), rtol=0, atol=1e-9)


def _buffers(spec, yaw):
    """Pixel buffers (part ids, colour) of a rest pose with each backend."""
    from spritekiln.pixelize import compose
    from spritekiln.render import Camera, Light, Scene, render, shade, to_gbuffer
    from spritekiln.rig import build

    env = dict(rest_env(spec, yaw), yaw=yaw, dir='s')
    groups, _ = build(spec, env)
    cam, light = Camera.from_spec(spec), Light(**spec['light'])
    scene = Scene(groups, np.radians(yaw))
    out = []
    for fn in (render, fast.render):
        gb = to_gbuffer(fn(scene, cam, light), len(groups), cam)
        g = gb.gid.astype(int)
        out.append((g, compose(g, shade(gb, cam, light), gb.depth, groups, spec['materials'])))
    return out


@pytest.mark.parametrize('spec_path', [MINIMAL, GARGOYLE, SHAPES], ids=['minimal', 'gargoyle', 'shapes'])
def test_frames_agree_with_the_reference(tmp_path, spec_path):
    spec = S.load(stage_spec(tmp_path, spec_path))
    for yaw in (0.0, 135.0, -90.0):
        (ga, ia), (gb, ib) = _buffers(spec, yaw)
        assert (ga == gb).mean() >= 0.999, f'yaw {yaw}: part ids differ'
        assert (ia != ib).any(-1).mean() <= 0.005, f'yaw {yaw}: too many colour pixels differ'


def test_backend_choice(monkeypatch):
    monkeypatch.setenv(backend.ENV, 'numpy')
    assert backend.name() == 'numpy'
    monkeypatch.setenv(backend.ENV, 'numba')
    assert backend.name() == 'numba'
    monkeypatch.setenv(backend.ENV, 'auto')
    assert backend.name() == 'numba'
    monkeypatch.setenv(backend.ENV, 'gpu')
    with pytest.raises(SpriteKilnError, match='auto, numpy, numba'):
        backend.name()


def test_without_numba_auto_falls_back_and_numba_explains(monkeypatch):
    monkeypatch.setattr(backend, '_FAST', {'error': 'No module named numba'})
    monkeypatch.setenv(backend.ENV, 'auto')
    assert backend.name() == 'numpy'
    assert 'fast extra' in backend.note()
    with pytest.raises(SpriteKilnError, match='spritekiln\\[fast\\]'):
        backend.use('numba')


def test_the_cache_never_mixes_backends(tmp_path, monkeypatch):
    spec = S.load(stage_spec(tmp_path, MINIMAL))
    env = rest_env(spec, 0.0)
    monkeypatch.setenv(backend.ENV, 'numpy')
    a = cache.entry(spec, env, 0.0)
    monkeypatch.setenv(backend.ENV, 'numba')
    assert cache.entry(spec, env, 0.0) != a


def test_render_uses_one_process_with_numba(tmp_path, monkeypatch):
    monkeypatch.setenv(backend.ENV, 'numba')
    notes = []
    path = stage_spec(tmp_path, MINIMAL)
    spec, anims, dlist, out = pipeline.render_all(path, ['attack'], ['s', 'e'], log=notes.append)
    assert notes[0].startswith('renderer: numba')
    assert not [n for n in notes if n.startswith('jobs:')]  # no process pool sizing
    from spritekiln.anim import frames_of

    assert len(out) == 2 * len(frames_of(spec, 'attack', 0.0))
