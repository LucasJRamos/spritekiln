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


# ---------------------------------------------------------------- size: crop and whole zooms


def _frame(h, w, box=None, rng=None):
    f = np.zeros((h, w, 4), np.uint8)
    if box:
        y0, y1, x0, x1 = box
        f[y0:y1, x0:x1] = (rng or np.random.default_rng(0)).integers(1, 255, (y1 - y0, x1 - x0, 4))
        f[y0:y1, x0:x1, 3] = 255
    return f


def test_content_box_is_the_union_with_a_margin():
    frames = [_frame(32, 32, (10, 14, 5, 8)), _frame(32, 32, (12, 20, 6, 9))]
    assert preview.content_box(frames, margin=2) == (8, 22, 3, 11)
    assert preview.content_box([_frame(32, 32, (0, 3, 30, 32))], margin=2) == (0, 5, 28, 32)  # kept inside


def test_content_box_keeps_empty_and_opaque_frames_whole():
    assert preview.content_box([_frame(16, 24)]) == (0, 16, 0, 24)
    floor = _frame(16, 24, (0, 16, 0, 24))  # a preview drawn over a background
    assert preview.content_box([floor]) == (0, 16, 0, 24)


def test_fit_scale_takes_the_largest_whole_zoom_within_budget():
    assert preview.fit_scale(lambda k: (500 * k, 100 * k), 4) == 3  # 2000 px would be too long
    assert preview.fit_scale(lambda k: (900 * k, 900 * k), 3) == 1  # 1800 x 1800 is too many pixels
    assert preview.fit_scale(lambda k: (5000 * k, 10 * k), 3) == 1  # too large even at 1: callers split


def test_tiles_cut_without_resampling():
    rng = np.random.default_rng(3)
    big = Image.fromarray(rng.integers(0, 255, (300, 4000, 4), dtype=np.uint8))
    pieces = preview.tiles(big)
    assert len(pieces) > 1
    for p in pieces:
        assert max(p.size) <= preview.MAX_SIDE and p.size[0] * p.size[1] <= preview.MAX_AREA
    rebuilt = np.concatenate([np.asarray(p) for p in pieces], 1)  # one row of pieces here
    assert np.array_equal(rebuilt, np.asarray(big))
    small = Image.new('RGBA', (100, 50))
    assert len(preview.tiles(small)) == 1


def _blocks_are_uniform(img, k):
    h, w = img.shape[:2]
    assert h % k == 0 and w % k == 0
    return np.array_equal(img, np.repeat(np.repeat(img[::k, ::k], k, 0), k, 1))


def test_contact_sheet_is_cropped_and_pixel_exact():
    from spritekiln.export import contact_sheet

    rng = np.random.default_rng(1)
    rows = [[_frame(96, 96, (30, 80, 40, 60), rng) for _ in range(12)] for _ in range(8)]
    sheet = np.asarray(contact_sheet(rows, list('abcdefgh'), 12, 3))
    assert max(sheet.shape[:2]) <= preview.MAX_SIDE and sheet.shape[0] * sheet.shape[1] <= preview.MAX_AREA
    # first cell: 18 * 3 px of labels on the left, 18 px on top; cropped to 20 + 2 * 2 px wide
    k = (sheet.shape[1] - 54) // (12 * 24)
    cell = sheet[18 : 18 + 54 * k, 54 : 54 + 24 * k]
    assert k >= 1 and _blocks_are_uniform(cell, k)
    assert np.array_equal(cell[::k, ::k][2:52, 2:22], rows[0][0][30:80, 40:60])  # the sprite, unchanged


def test_pose_is_cropped_and_zoomed_by_whole_steps(tmp_path):
    from spritekiln import api

    spec = stage_spec(tmp_path, os.path.join(FIXTURES, 'minimal', 'minimal.yaml'))
    out, dirs, view = api.pose(spec, dirs='all', scale=4, out=str(tmp_path / 'p.png'))
    img = np.asarray(Image.open(out).convert('RGBA'))
    k, (x0, y0, x1, y1) = view['scale'], view['crop']
    assert img.shape[:2] == ((y1 - y0) * k, len(dirs) * (x1 - x0) * k)
    assert _blocks_are_uniform(img, k)
    assert (x1 - x0, y1 - y0) != (32, 32)  # cropped around the sprite
    full = api.pose(spec, dirs='s', scale=1, out=str(tmp_path / 'f.png'), crop=False)[2]
    assert full['crop'] == [0, 0, 32, 32]


def test_pose_focus_is_a_close_up_of_a_bone_and_what_hangs_below_it(tmp_path):
    """Design 16: `pose --focus head` crops to the head, hair, eyes and headwear, zoomed up to 12x."""
    from spritekiln import api

    spec = tmp_path / 'hero.yaml'
    spec.write_text('spritekiln: 1\nname: hero\nextends: humanoid\nbrief: {head: the template head}\n', 'utf-8')
    body = api.pose(str(spec), dirs='s,e', out=str(tmp_path / 'b.png'))[2]
    out, dirs, head = api.pose(str(spec), dirs='s,e', focus='head', out=str(tmp_path / 'h.png'))
    (by0, by1), (hx0, hy0, hx1, hy1) = body['crop'][1::2], head['crop']
    assert dirs == ['s', 'e'] and head['scale'] > body['scale']
    assert (hy1 - hy0) < (by1 - by0) / 2 and hy0 <= by0 + 3  # the top of the sprite, not the body
    img = np.asarray(Image.open(out).convert('RGBA'))
    assert img.shape[:2] == ((hy1 - hy0) * head['scale'], 2 * (hx1 - hx0) * head['scale'])
    eyes = api.pose(str(spec), dirs='s', focus='eye_L', out=str(tmp_path / 'e.png'))[2]['crop']  # parts, with twins
    assert eyes[2] - eyes[0] < hx1 - hx0
    with pytest.raises(SpriteKilnError, match='did you mean head'):
        api.pose(str(spec), dirs='s', focus='haed')
