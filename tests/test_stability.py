"""Design 10: thin parts survive the pixel vote; snapped frames move in whole pixels; QA measures boil."""

import copy
import os

import numpy as np
import pytest

from spritekiln import pipeline, qa
from spritekiln import spec as S
from spritekiln.anim import frames_of
from spritekiln.rig import rest_env

from conftest import FIXTURES, stage_spec

THIN = os.path.join(FIXTURES, 'thin', 'thin.yaml')


def _staff_pixels(spec):
    return [
        pipeline.render_frame(spec, rest_env(spec, yaw), yaw, force=True, maps=False).materials.get('wood', 0)
        for _, yaw in spec['directions']
    ]


def test_a_thin_staff_survives_with_priority_and_min_cover(tmp_path):
    spec = S.load(stage_spec(tmp_path, THIN))
    assert min(_staff_pixels(spec)) <= 1  # the plain vote loses a staff thinner than a third of a pixel
    tuned = copy.deepcopy(spec)
    tuned['parts']['staff'].update(priority=3, min_cover=2)
    assert min(_staff_pixels(tuned)) >= 5  # visible in every direction


def _variant(tmp_path, text):
    p = tmp_path / 'variant.yaml'
    p.write_text(text, encoding='utf-8')
    return str(p)


def test_snapped_frames_move_in_whole_pixels(tmp_path):
    text = open(THIN, encoding='utf-8').read().replace('0.012*sin(p)', '0.03*sin(p)')
    plain = S.load(_variant(tmp_path, text))
    snapped = S.load(_variant(tmp_path, text.replace('\nbones:\n', '\nsnap: [hips]\nbones:\n')))

    def alphas(spec):
        return [
            pipeline.render_frame(spec, env, 0.0, force=True, maps=False).img[..., 3] > 0
            for env, _, _ in frames_of(spec, 'idle', 0.0)
        ]

    def whole_pixel_shift(a, b):
        return any(np.array_equal(np.roll(a, dy, 0), b) for dy in range(-3, 4))

    rest = alphas(snapped)
    assert all(whole_pixel_shift(rest[0], f) for f in rest[1:])
    assert not all(whole_pixel_shift(f0, f) for f0, f in zip(alphas(plain)[:1] * 3, alphas(plain)[1:]))


def test_snap_takes_root_and_bones_only(tmp_path):
    text = open(THIN, encoding='utf-8').read().replace('\nbones:\n', '\nsnap: [root, elbow]\nbones:\n')
    errors, _ = S.check(S.load(_variant(tmp_path, text)))
    assert any('snap[1]: "elbow" is not root or a bone' in e for e in errors)


@pytest.mark.parametrize('value', [0, 99, 1.5])
def test_min_cover_is_a_sample_count(tmp_path, value):
    text = (
        open(THIN, encoding='utf-8')
        .read()
        .replace('    material: wood\n', f'    material: wood\n    min_cover: {value}\n')
    )
    errors, _ = S.check(S.load(_variant(tmp_path, text)))
    assert any('parts.staff.min_cover' in e for e in errors)


def _frame(img, emissive=None):
    return pipeline.Frame(img, None, emissive)


def test_boil_counts_pixels_that_blink():
    base = np.zeros((12, 12, 4), np.uint8)
    base[2:10, 2:10] = (90, 80, 100, 255)
    blink = base.copy()
    blink[5, 5, :3] = (200, 0, 0)  # one inner pixel changes for one frame and comes back
    still = [_frame(base), _frame(blink), _frame(base)]
    share, iou = qa.boil(still, loop=False)
    assert iou == 1.0 and share == pytest.approx(1 / 36)  # 6 x 6 inner pixels (the outline is left out)
    glow = np.zeros_like(base)
    glow[5, 5] = blink[5, 5]
    assert qa.boil([_frame(base), _frame(blink, glow), _frame(base)], loop=False)[0] == 0  # emissive flicker is fine


def test_qa_reports_boil(tmp_path):
    path = stage_spec(tmp_path, THIN)
    spec, anims, dlist, out = pipeline.render_all(path, ['idle'], ['s', 'e'], jobs=1)
    rep = qa.check(spec, anims, dlist, out)
    assert set(rep['info']['boil']) == {'idle/s', 'idle/e'}
