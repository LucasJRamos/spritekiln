"""Design 06: the cache keeps a geometry buffer; light, materials and palette are applied in 2D."""

import copy
import os

import numpy as np

from spritekiln import backend, pipeline
from spritekiln import spec as S
from spritekiln.rig import rest_env

from conftest import FIXTURES, stage_spec

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')


def _count_renders(monkeypatch):
    calls = []
    real = backend.render

    def counted(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(backend, 'render', counted)
    return calls


def test_light_intensities_reuse_the_geometry(tmp_path, monkeypatch):
    spec = S.load(stage_spec(tmp_path, MINIMAL))
    calls = _count_renders(monkeypatch)
    env = rest_env(spec, 0.0)
    first = pipeline.render_frame(spec, env, 0.0).img
    brighter = copy.deepcopy(spec)
    brighter['light'].update(ambient=0.4, rim_strength=0.1)
    second = pipeline.render_frame(brighter, env, 0.0).img
    assert len(calls) == 1  # one ray march: the second frame came from the cache
    assert (first != second).any()  # and it is lit differently
    moved = copy.deepcopy(spec)
    moved['light']['dir'] = [0.5, 1.0, 0.45]  # the shadows change: a new geometry pass
    pipeline.render_frame(moved, env, 0.0)
    assert len(calls) == 2


def test_cached_and_fresh_frames_are_identical(tmp_path):
    spec = S.load(stage_spec(tmp_path, MINIMAL))
    env = rest_env(spec, 45.0)
    fresh = pipeline.render_frame(spec, env, 45.0, force=True)
    cached = pipeline.render_frame(spec, env, 45.0)
    for a, b in zip(fresh[:3], cached[:3]):
        np.testing.assert_array_equal(a, b)


def test_flat_light_ignores_the_light(tmp_path):
    """light.mode flat: one tone per material, whatever the light; the normal map stays for the engine."""
    spec = S.load(stage_spec(tmp_path, MINIMAL))
    spec['light']['mode'] = 'flat'
    env = rest_env(spec, 0.0)
    dark = pipeline.render_frame(spec, env, 0.0)
    bright = copy.deepcopy(spec)
    bright['light'].update(ambient=0.6, rim_strength=0.0)
    lit = pipeline.render_frame(bright, env, 0.0)
    np.testing.assert_array_equal(dark.img, lit.img)
    baked = copy.deepcopy(spec)
    baked['light']['mode'] = 'baked'
    assert len(np.unique(pipeline.render_frame(baked, env, 0.0).img.reshape(-1, 4), axis=0)) > len(
        np.unique(dark.img.reshape(-1, 4), axis=0)
    )  # fewer tones when flat
    assert dark.normal is not None
