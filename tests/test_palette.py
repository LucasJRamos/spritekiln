import colorsys
import re

import numpy as np
import pytest
import yaml

from pxforge import palette as P
from pxforge.pixelize import hx

HEX = re.compile(r'^#[0-9a-f]{6}$')


def lightness(c):
    return colorsys.rgb_to_hls(*[v / 255 for v in hx(c)])[1]


def test_ramp_snapshot():
    # Pins the ramp algorithm: changing it changes every palette made with `palette ramp`.
    assert P.ramp('#5d4f6c', 6) == ['#0c0b0e', '#322e3d', '#574b66', '#7d688c', '#a08ca8', '#bfb1c2']
    assert P.ramp('#c0392b', 4, 30) == ['#12070c', '#8a2229', '#d67655', '#e9d4ba']


@pytest.mark.parametrize('base', ['#5d4f6c', '#c0392b', '#2e8b57', '#f1c40f', '#808080'])
@pytest.mark.parametrize('steps', [3, 5, 8])
def test_ramp_shape(base, steps):
    r = P.ramp(base, steps)
    assert len(r) == steps
    assert all(HEX.match(c) for c in r)
    ls = [lightness(c) for c in r]
    assert ls == sorted(ls), 'ramp must go from dark (outline, index 0) to light'
    assert ls[0] < 0.1


def test_shadows_shift_toward_violet_and_lights_toward_yellow():
    r = P.ramp('#2e8b57', 6)                       # green: blue-violet is "up" the hue wheel, yellow "down"
    hue = lambda c: colorsys.rgb_to_hls(*[v / 255 for v in hx(c)])[0]  # noqa: E731
    base = hue('#2e8b57')
    assert hue(r[1]) > base
    assert hue(r[-1]) < base


def test_to_hex_clips():
    assert P.to_hex((1.2, -0.1, 0.5)) == '#ff0080'


def test_oklab_reference_points():
    np.testing.assert_allclose(P.oklab([255, 255, 255]), [1, 0, 0], atol=1e-6)
    np.testing.assert_allclose(P.oklab([0, 0, 0]), [0, 0, 0], atol=1e-9)
    L, a, b = P.oklab([255, 0, 0])
    assert L == pytest.approx(0.628, abs=1e-3) and a > 0.2 and b > 0.1


def two_colour_image():
    img = np.zeros((40, 40, 4), np.uint8)
    img[..., 3] = 255
    img[:30] = (200, 40, 40, 255)          # 75 % red
    img[30:] = (40, 60, 200, 255)          # 25 % blue
    return img


def test_extract_dominant_colours():
    out = P.extract(two_colour_image(), k=2)
    assert [c['hex'] for c in out] == ['#c82828', '#283cc8']
    assert out[0]['share'] == pytest.approx(0.75)
    assert out[1]['share'] == pytest.approx(0.25)


def test_extract_respects_alpha():
    img = two_colour_image()
    img[30:, :, 3] = 0
    out = P.extract(img, k=1)
    assert [c['hex'] for c in out] == ['#c82828']


@pytest.mark.xfail(strict=True, raises=ValueError,
                   reason='known bug (LAUNCH.md audit #20): k-means++ init divides by zero when the image '
                          'has fewer distinct colours than k; fix in Phase 1')
def test_extract_with_fewer_colours_than_k():
    img = two_colour_image()
    img[30:, :, 3] = 0
    out = P.extract(img, k=2)
    assert [c['hex'] for c in out] == ['#c82828']


def test_families_group_by_hue_and_neutrals():
    cols = [dict(hex='#c82828', share=0.4, L=0.5, chroma=0.2, hue=30.0),
            dict(hex='#e04040', share=0.2, L=0.6, chroma=0.2, hue=40.0),
            dict(hex='#283cc8', share=0.2, L=0.4, chroma=0.2, hue=265.0),
            dict(hex='#777777', share=0.1, L=0.5, chroma=0.0, hue=0.0),
            dict(hex='#999999', share=0.1, L=0.7, chroma=0.01, hue=90.0)]
    fams = P.families(cols)
    assert [len(f['members']) for f in fams] == [2, 1, 2]
    assert fams[0]['share'] == pytest.approx(0.6) and fams[0]['base'] == '#c82828'
    assert fams[2]['neutral']


def test_palette_yaml_is_valid_yaml():
    fams = P.families(P.extract(two_colour_image(), k=2))
    data = yaml.safe_load(P.palette_yaml(fams))
    assert list(data['ramps']) == ['fam1', 'fam2']
    assert len(data['ramps']['fam1']) == 6          # > 8 % of the image: full ramp
    assert all(HEX.match(c) for r in data['ramps'].values() for c in r)
