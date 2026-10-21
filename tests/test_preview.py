"""Previews over a game background under the scene light (--bg / --tint)."""

import os

import numpy as np
import pytest
from PIL import Image

from spritekiln import preview
from spritekiln.cli import main
from spritekiln.errors import SpriteKilnError

from conftest import FIXTURES, stage_spec


@pytest.mark.parametrize(
    'text, rgb',
    [('0.5,0.6,1.0', (0.5, 0.6, 1.0)), ('0.8', (0.8, 0.8, 0.8)), ('#ff8000', (1.0, 128 / 255, 0.0)), (None, None)],
)
def test_parse_tint(text, rgb):
    assert preview.parse_tint(text) == (pytest.approx(rgb) if rgb else None)


@pytest.mark.parametrize('text', ['red', '1,2', '-1,1,1', '#12'])
def test_bad_tint(text):
    with pytest.raises(SpriteKilnError, match='--tint'):
        preview.parse_tint(text)


def test_tint_spares_emissive_and_transparent_pixels():
    img = np.zeros((2, 2, 4), np.uint8)
    img[0, 0] = (200, 100, 50, 255)  # lit
    img[0, 1] = (200, 100, 50, 255)  # emissive
    em = np.zeros_like(img)
    em[0, 1] = img[0, 1]
    out = preview.tint(img, (0.5, 0.5, 2.0), em)
    assert tuple(out[0, 0]) == (100, 50, 100, 255)
    assert tuple(out[0, 1]) == (200, 100, 50, 255)
    assert tuple(out[1, 1]) == (0, 0, 0, 0)


def test_over_tiles_the_background():
    bg = np.zeros((2, 3, 4), np.uint8)
    bg[..., 0] = np.arange(3)
    bg[..., 3] = 255
    out = preview.over(np.zeros((5, 7, 4), np.uint8), bg)
    assert out.shape == (5, 7, 4) and (out[..., 3] == 255).all()
    assert list(out[0, :, 0]) == [0, 1, 2, 0, 1, 2, 0]


def test_pose_over_a_background(tmp_path):
    floor = tmp_path / 'floor.png'
    Image.new('RGB', (16, 16), (40, 30, 60)).save(floor)
    out = tmp_path / 'pose.png'
    spec = stage_spec(tmp_path, os.path.join(FIXTURES, 'minimal', 'minimal.yaml'))
    main(['pose', spec, '--dirs', 's,e', '--scale', '1', '--bg', str(floor), '--tint', '0.7,0.7,1.0', '-o', str(out)])
    img = np.asarray(Image.open(out).convert('RGBA'))
    assert img.shape == (32, 64, 4) and (img[..., 3] == 255).all()
    assert tuple(img[0, 0, :3]) == (40, 30, 60)  # the floor, untinted, shows around the sprite
