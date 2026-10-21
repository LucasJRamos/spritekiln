"""Shared helpers: staging specs in a clean folder and comparing images with goldens."""

import json
import os
import platform
import shutil
import sys

import numpy as np
import pytest
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(REPO, 'tests', 'golden')
FIXTURES = os.path.join(REPO, 'tests', 'fixtures')

# Off the platform that produced the goldens, float differences may flip a few pixels.
TOLERANCE = 0.005


def pytest_addoption(parser):
    parser.addoption(
        '--update-golden',
        action='store_true',
        help='rewrite tests/golden/ from the current output instead of comparing',
    )


@pytest.fixture
def update_golden(request):
    return request.config.getoption('--update-golden')


def stage_spec(tmp_path, spec_path):
    """Copy a spec (and every shared palette) into tmp_path, keeping the specs/ layout.

    The render cache lives next to the spec, so a staged spec always renders from scratch:
    a stale `.pxcache` can never hide a regression.
    """
    spec_path = os.path.abspath(spec_path)
    rel = os.path.relpath(spec_path, REPO)
    if rel.startswith('..'):
        rel = os.path.join('specs', 'fixtures', os.path.basename(spec_path))
    dst = tmp_path / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(spec_path, dst)
    shutil.copytree(os.path.join(REPO, 'specs', 'palettes'), tmp_path / 'specs' / 'palettes', dirs_exist_ok=True)
    return str(dst)


def platform_tag():
    return dict(platform=sys.platform, machine=platform.machine(), numpy=np.__version__)


def _meta_path():
    return os.path.join(GOLDEN, 'meta.json')


def golden_is_native():
    """True when running on the platform/numpy that produced the goldens (exact match expected)."""
    try:
        with open(_meta_path(), encoding='utf-8') as fh:
            return json.load(fh) == platform_tag()
    except FileNotFoundError:
        return False


def write_golden_meta():
    os.makedirs(GOLDEN, exist_ok=True)
    with open(_meta_path(), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(platform_tag(), fh, indent=1)
        fh.write('\n')


def load_rgba(path):
    return np.asarray(Image.open(path).convert('RGBA'))


def assert_image_matches(actual_path, golden_name, update=False):
    """Compare a PNG with tests/golden/<golden_name>; exact on the native platform."""
    golden_path = os.path.join(GOLDEN, golden_name)
    if update:
        os.makedirs(GOLDEN, exist_ok=True)
        shutil.copy2(actual_path, golden_path)
        write_golden_meta()
        return
    assert os.path.exists(golden_path), f'missing golden {golden_name}; run pytest --update-golden'
    a, g = load_rgba(actual_path), load_rgba(golden_path)
    assert a.shape == g.shape, f'{golden_name}: size {a.shape} != golden {g.shape}'
    diff = (a != g).any(-1)
    n = int(diff.sum())
    if n == 0:
        return
    limit = 0 if golden_is_native() else int(TOLERANCE * diff.size)
    if n > limit:
        report = os.path.splitext(actual_path)[0] + '_diff.png'
        vis = np.zeros_like(a)
        vis[..., 3] = 255
        vis[diff] = (255, 0, 255, 255)
        Image.fromarray(np.concatenate([g, a, vis], 1)).save(report)
        pytest.fail(f'{golden_name}: {n} pixel(s) differ (limit {limit}); golden | actual | diff -> {report}')
