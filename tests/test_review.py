"""`spritekiln review`: L*, materials, bands, legibility, reference IoU and spec targets."""

import json
import os

import numpy as np
import pytest
from PIL import Image

from spritekiln import spec as S
from spritekiln.cli import main
from spritekiln.pipeline import render_frame
from spritekiln.review import frame_stats, lstar, run, target_warnings
from spritekiln.rig import rest_env

from conftest import FIXTURES, stage_spec

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')


def test_lstar_reference_values():
    np.testing.assert_allclose(lstar([[255, 255, 255], [0, 0, 0], [119, 119, 119]]), [100, 0, 50.0], atol=0.1)


def test_frame_stats(tmp_path):
    sp = S.load(stage_spec(tmp_path, MINIMAL))
    st = frame_stats(render_frame(sp, rest_env(sp), 0), sp)
    assert st['area'] > 100 and 0 < st['lstar_median'] <= st['lstar_p90'] < 100
    assert {'body', 'trim', 'eye'} <= set(st['materials'])
    assert set(st['bands']['body']) <= {0, 1, 2, 3, 4} and sum(st['bands']['body'].values()) > 0
    darker = frame_stats(render_frame(sp, rest_env(sp), 0), sp, tint=(0.5, 0.5, 0.5))
    assert darker['lstar_median'] < st['lstar_median']


def test_target_warnings():
    spec = {'review': {'min_lstar': 20, 'materials': {'lining': {'min_px': 30}, 'skin': {'max_px': 50}}}}
    s = lambda L, lining, skin: dict(lstar_median=L, materials={'lining': lining, 'skin': skin})  # noqa: E731
    stats = {('idle', 's'): [s(25, 40, 10)], ('idle', 'n'): [s(12, 10, 60), s(14, 12, 60), s(30, 50, 60)]}
    assert target_warnings(spec, stats) == [
        'review.materials.lining: idle below 30 px in n (12)',
        'review.materials.skin: idle above 50 px in n (60)',
        'review.min_lstar: idle below 20 in n (14)',
    ]


def test_review_run(tmp_path):
    spec = stage_spec(tmp_path, MINIMAL)
    floor = tmp_path / 'floor.png'
    Image.new('RGB', (8, 8), (35, 30, 50)).save(floor)
    ref = tmp_path / 'ref.png'
    sp = S.load(spec)
    Image.fromarray(render_frame(sp, rest_env(sp), 0).img).save(ref)  # the sprite itself as the "splash"
    rep = run(
        spec,
        anims=['attack'],
        bg_path=str(floor),
        tint=(0.7, 0.7, 1.0),
        against=spec,
        ref=str(ref),
        out_dir=str(tmp_path / 'review'),
        jobs=1,
    )
    assert set(rep['directions']) == {'s', 'se', 'e', 'ne', 'n', 'nw', 'w', 'sw'}
    assert rep['background']['lstar_median'] < 25 and 'contrast' in rep['directions']['s']
    assert rep['against']['directions']['s']['area_ratio'] == 1.0
    assert rep['reference']['iou_raw'] > 0.95 and rep['reference']['iou'] < rep['reference']['iou_raw']
    assert len(rep['poses']['attack']['e']['frames']) == 4
    for p in (rep['files']['json'], rep['files']['sheet'], rep['files']['clips']['attack']):
        assert os.path.exists(p)
    with open(rep['files']['json'], encoding='utf-8') as fh:
        assert json.load(fh)['spec'] == 'minimal'


def test_review_targets_reach_qa_and_validate(tmp_path):
    text = open(MINIMAL, encoding='utf-8').read() + 'review:\n  min_lstar: 99\n  materials:\n    trim: {min_px: 9999}\n'
    p = tmp_path / 'specs' / 'fixtures' / 'minimal.yaml'
    p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')
    main(['render', str(p), '--anims', 'idle', '--dirs', 's', '--jobs', '1', '-o', str(tmp_path / 'out')])
    with open(tmp_path / 'out' / 'qa.json', encoding='utf-8') as fh:
        warnings = json.load(fh)['warnings']
    assert any(w.startswith('review.min_lstar: idle below 99 in s') for w in warnings)
    assert any(w.startswith('review.materials.trim: idle below 9999 px in s') for w in warnings)
    p.write_text(text.replace('trim: {min_px', 'lining: {min_px'), encoding='utf-8')
    errors = S.validate(S.load(str(p)))
    assert any('review.materials.lining: unknown material "lining"' in e for e in errors)


@pytest.mark.parametrize('flag', ['--against', '--ref'])
def test_cli_review(tmp_path, capsys, flag):
    spec = stage_spec(tmp_path, MINIMAL)
    extra = [flag, spec] if flag == '--against' else []
    main(['review', spec, '--dirs', 's,e', '-o', str(tmp_path / 'r'), *extra])
    out = capsys.readouterr().out
    assert 'dir   L*med' in out and 'report:' in out
