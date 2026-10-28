"""Renderer invariants: bounding spheres are tight and never change the shading."""

import os

import numpy as np
import pytest

from spritekiln import pipeline, sdf
from spritekiln.rig import rest_env

from conftest import REPO, stage_spec

GARGOYLE = os.path.join(REPO, 'specs', 'characters', 'gargula', 'gargula.yaml')


def test_one_primitive_group_is_bounded_by_its_own_sphere():
    g = sdf.Group('p', 'm', [sdf.round_cone([0, 0, 0], [0, -1.12, -0.06], 0.31, 0.39)])
    c, r = g.prims[0].bound
    np.testing.assert_allclose(g.bc, c)
    assert g.br == pytest.approx(r + 0.01)  # was r * sqrt(3) around the box of the sphere


def test_group_bound_contains_every_primitive():
    rng = np.random.default_rng(1)
    prims = [sdf.sphere(rng.uniform(-1, 1, 3), rng.uniform(0.05, 0.4)) for _ in range(6)]
    g = sdf.Group('p', 'm', prims, k=0.05)
    for p in prims:
        c, r = p.bound
        assert np.linalg.norm(np.asarray(c) - g.bc) + r <= g.br - 0.05 + 1e-9


def _image(spec, yaw, inflate):
    """Colour of the rest pose with every group bound grown by `inflate` (no cache)."""
    init = sdf.Group.__init__

    def grown(self, *a, **k):
        init(self, *a, **k)
        self.br += inflate

    sdf.Group.__init__ = grown
    try:
        return pipeline.render_frame(spec, rest_env(spec, yaw), yaw, force=True, maps=False).img
    finally:
        sdf.Group.__init__ = init


def test_shading_does_not_depend_on_bounding_spheres(tmp_path):
    """Soft shadows and AO read real distances wherever they can matter, so larger bounds change nothing but
    where ray marching stops (within eps of the same surface): a handful of pixels. Trusting the bound
    distance used to change about 10 % of the gargoyle's pixels ("phantom shadows")."""
    spec = pipeline.get_spec(stage_spec(tmp_path, GARGOYLE))
    a, b = _image(spec, 135.0, 0.0), _image(spec, 135.0, 0.3)
    changed = int((a != b).any(-1).sum())
    assert changed <= 0.01 * (a[..., 3] > 0).sum(), f'{changed} pixels changed with larger bounds'
