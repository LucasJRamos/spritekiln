"""Splash-art reference tools: cutout on gradient backgrounds, gaps kept open, pitch correction."""

import numpy as np
from PIL import Image

from spritekiln import ref as R


def figure(gradient=True):
    """A dark character with two legs on a light, vignetted background (like an AI splash)."""
    H, W = 300, 200
    y, x = np.mgrid[0:H, 0:W]
    bg = 235 - 60 * np.hypot((x - W / 2) / W, (y - H / 2) / H) if gradient else np.full((H, W), 220.0)
    img = np.stack([bg, bg, bg + 5], -1)
    body = (abs(x - 100) < 40) & (y > 40) & (y < 170)
    legs = ((abs(x - 78) < 14) | (abs(x - 122) < 14)) & (y >= 170) & (y < 280)
    head = np.hypot(x - 100, y - 30) < 22
    img[body | legs | head] = (40, 30, 45)
    eye = np.hypot(x - 108, y - 28) < 3  # background-coloured detail inside the head
    img[eye] = (230, 230, 235)
    rgba = np.dstack([np.clip(img, 0, 255), np.full((H, W), 255)]).astype(np.uint8)
    truth = body | legs | head
    gap = (abs(x - 100) < 6) & (y > 200) & (y < 270)
    return Image.fromarray(rgba), truth, gap, eye


def test_cutout_follows_a_gradient_and_keeps_the_gap_between_the_legs():
    img, truth, gap, eye = figure()
    cut, mask, used = R.cutout(img)
    assert used == 'border'
    full = np.zeros(truth.shape, bool)
    ys, xs = np.nonzero(truth)
    full[ys.min() : ys.min() + mask.shape[0], xs.min() : xs.min() + mask.shape[1]] = mask
    iou = (full & truth).sum() / (full | truth).sum()
    assert iou > 0.97
    assert not full[gap].any()  # the opening between the legs stays transparent
    assert full[eye].all()  # a small light detail inside is filled


def test_alpha_input_is_used_as_is():
    img, truth, _, _ = figure()
    a = np.asarray(img).copy()
    a[..., 3] = np.where(truth, 255, 0)
    _, mask, used = R.cutout(Image.fromarray(a))
    assert used == 'alpha' and mask.sum() == truth.sum()


def test_pitch_correction_squashes_the_height():
    m = np.ones((100, 40), bool)
    assert R.pitch_corrected(m, 38).shape == (79, 40)
    assert R.pitch_corrected(m, 0).shape == (100, 40)


def test_compare_with_pitch_correction():
    tall = np.zeros((100, 100), bool)
    tall[0:100, 40:60] = True  # front view: 100 tall
    seen = np.zeros((100, 100), bool)
    seen[21:100, 40:60] = True  # the camera sees it 79 tall
    raw = R.compare_masks(tall, seen)[0]
    fixed = R.compare_masks(tall, seen, 38)[0]
    assert fixed['iou'] > raw['iou'] and fixed['iou'] > 0.95 and fixed['pitch'] == 38
