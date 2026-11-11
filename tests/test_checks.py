"""Design 17 and 18: traits the QA can check (`review.keep`), parts hidden in some frames, floating parts, colour
against the splash, `pose --changes`, the arcs sheet and the ground speed of a walk, and the usage log."""

import json
import os

import numpy as np
import pytest
from PIL import Image

from spritekiln import api, checks, motion, qa, usage
from spritekiln import ref as R
from spritekiln import spec as S
from spritekiln.cli import main
from spritekiln.pipeline import render_all, render_frame
from spritekiln.review import check_review_block, keep_table, target_warnings, trait_px
from spritekiln.rig import build, rest_env

from conftest import FIXTURES, REPO, stage_spec

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')
HUMANOID = os.path.join(REPO, 'specs', 'templates', 'humanoid.yaml')


def _variant(tmp_path, old, new, name='variant.yaml'):
    text = open(stage_spec(tmp_path, MINIMAL), encoding='utf-8').read()
    assert old in text
    p = tmp_path / 'specs' / 'fixtures' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.replace(old, new), encoding='utf-8')
    return str(p)


# ---------------------------------------------------------------- pixels per part, review.keep


def test_a_frame_counts_the_pixels_of_each_part(tmp_path):
    sp = S.load(stage_spec(tmp_path, MINIMAL))
    fr = render_frame(sp, rest_env(sp), 0)
    assert {'torso', 'head', 'leg_L', 'leg_R'} <= set(fr.parts)
    assert sum(fr.parts.values()) <= int((fr.img[..., 3] == 255).sum())
    back = render_frame(sp, rest_env(sp, 180), 180)
    assert 'eye_L' in fr.parts and 'eye_L' not in back.parts  # the eyes do not show from behind


def test_keep_targets_warn_where_a_trait_does_not_read():
    spec = {'review': {'keep': {'horns': {'parts': ['horn_L', 'horn_R'], 'min_px': 6}, 'eyes': {'materials': ['eye']}}}}
    s = lambda horns, eye: dict(lstar_median=30, parts={'horn_L': horns, 'horn_R': 0}, materials={'eye': eye})  # noqa: E731
    stats = {('rest', 's'): [s(9, 5)], ('rest', 'n'): [s(4, 0)]}
    assert trait_px(stats[('rest', 's')][0], spec['review']['keep']['horns']) == 9
    assert target_warnings(spec, stats) == [
        'review.keep.eyes: rest below 4 px in n (0)',
        'review.keep.horns: rest below 6 px in n (4)',
    ]
    spec['review']['keep']['eyes']['dirs'] = ['s']  # the eyes only have to show from the front
    assert target_warnings(spec, stats) == ['review.keep.horns: rest below 6 px in n (4)']
    assert keep_table(spec, stats) == {'horns': {'rest': {'s': 9, 'n': 4}}, 'eyes': {'rest': {'s': 5}}}


def test_keep_names_are_checked(tmp_path):
    sp = S.load(stage_spec(tmp_path, MINIMAL))
    sp['review'] = {
        'keep': {'a': {'parts': ['hornn_L']}, 'b': {'min_px': 3}, 'c': {'materials': ['eye'], 'dirs': ['x']}}
    }
    found = check_review_block(sp)
    assert any('unknown part "hornn_L" (did you mean horn_L?)' in f for f in found)
    assert any(f.startswith('review.keep.b: name the parts') for f in found)
    assert any('unknown direction "x"' in f for f in found)


def test_review_reports_kept_traits_and_validate_accepts_them(tmp_path, capsys):
    path = _variant(
        tmp_path, '\nchannels:\n', '\nreview: {keep: {horns: {parts: [horn_L, horn_R], min_px: 900}}}\nchannels:\n'
    )
    assert not main(['validate', path, '--strict'])
    assert 'OK' in capsys.readouterr().out
    from spritekiln.review import run

    rep = run(path, out_dir=str(tmp_path / 'review'))
    assert {'s', 'e', 'n', 'w'} <= set(rep['keep']['horns']['rest'])  # review looks at all 8
    assert any(w.startswith('review.keep.horns: rest below 900 px') for w in rep['warnings'])
    assert rep['poses']['rest']['s']['frames'][0]['parts']['torso'] > 0


def test_qa_lists_parts_hidden_in_some_frames_and_kept_traits_lost():
    spec = {'parts': {'sword': {}, 'smear': {'when': 'x'}, 'cape': {}}, 'review': None}
    shown = [{'sword': 20, 'smear': 0, 'cape': 30}, {'cape': 28, 'smear': 40}, {'sword': 3, 'cape': 30}]
    assert qa._hidden(spec, shown) == {'sword': [1]}  # the smear comes and goes on purpose


def test_qa_warns_when_a_kept_trait_vanishes_in_a_frame(tmp_path):
    path = _variant(
        tmp_path, '\nchannels:\n', '\nreview: {keep: {eyes: {parts: [eye_L, eye_R], min_px: 1}}}\nchannels:\n'
    )
    sp, anims, dlist, out = render_all(path, ['idle'], ['s', 'n'], jobs=1)
    rep = qa.check(sp, anims, dlist, out)
    assert any(w.startswith('review.keep.eyes: idle below 1 px in n') for w in rep['warnings'])
    assert not any('hidden in idle/s' in w for w in rep['warnings'])


# ---------------------------------------------------------------- floating parts


def test_a_part_that_touches_nothing_is_reported(tmp_path):
    sp = S.load(HUMANOID)
    groups = build(sp, rest_env(sp, 0))[0]
    assert checks.floating_parts(sp, groups) == []
    sp['parts']['hand_L']['prims'] = [{'sphere': {'c': [0, 0, 0.30], 'r': 0.055}}]
    groups = build(sp, rest_env(sp, 0))[0]
    found = dict(checks.floating_parts(sp, groups))
    assert set(found) == {'hand_L'} and found['hand_L'] > 2
    assert any('parts.hand_L: floats' in w for w in S.check(sp)[1])
    sp['parts']['hand_L']['floating'] = True  # an orb that is meant to hang in the air
    assert checks.floating_parts(sp, build(sp, rest_env(sp, 0))[0]) == []


def test_floating_is_a_known_part_key(tmp_path):
    path = _variant(tmp_path, '  head:\n    material: body\n', '  head:\n    floating: true\n    material: body\n')
    assert not [w for w in api.validate(path)['warnings'] if 'unknown key' in w]


# ---------------------------------------------------------------- colour against the splash


def test_band_colors_and_hints():
    img = np.zeros((20, 10, 4), np.uint8)
    img[..., 3] = 255
    img[:10, :, :3] = (200, 40, 40)  # red above
    img[10:, :, :3] = (40, 40, 60)  # dark below
    cols = R.band_colors(img)
    assert cols[0] == '#c82828' and cols[-1] == '#28283c' and len(cols) == 10
    other = img.copy()
    other[:10, :, :3] = (40, 60, 200)  # blue above: another colour
    other[10:, :, :3] = (200, 200, 215)  # light below: much lighter
    hints = R.color_hints(cols, R.band_colors(other))
    assert any('another colour' in h for h in hints) and any('much lighter' in h for h in hints)
    assert R.color_hints(cols, cols) == []
    empty = np.zeros((4, 4, 4), np.uint8)
    assert R.band_colors(empty) == [None] * 10


def test_ref_compare_reports_colour(tmp_path):
    spec = stage_spec(tmp_path, MINIMAL)
    sp = S.load(spec)
    splash = render_frame(sp, rest_env(sp), 0).img.copy()
    splash[..., :3] = np.where(splash[..., 3:] > 0, (235, 235, 240), 0)  # the same shape, much lighter
    ref = tmp_path / 'ref.png'
    Image.fromarray(splash).save(ref)
    res = api.ref_compare(spec, str(ref), 's')
    assert len(res['colors']['ref']) == 10 and any('much darker' in h for h in res['color_hints'])


# ---------------------------------------------------------------- pose --changes


def test_pose_changes_shows_only_what_changed(tmp_path, capsys):
    spec = stage_spec(tmp_path, MINIMAL)
    _, _, view = api.pose(spec, dirs='all', changes=True)
    assert view['changes'] is None  # nothing to compare with yet
    _, dirs, view = api.pose(spec, dirs='all', changes=True)
    assert view['changes'] == dict(changed={}, same=dirs, sheet=None)
    text = open(spec, encoding='utf-8').read()
    assert 'c: [0.05, 0.09, 0.1], r: 0.05' in text  # the eye, seen from the front only
    open(spec, 'w', encoding='utf-8').write(
        text.replace('c: [0.05, 0.09, 0.1], r: 0.05', 'c: [0.05, 0.09, 0.1], r: 0.08')
    )
    _, dirs, view = api.pose(spec, dirs='all', changes=True)
    ch = view['changes']
    assert 's' in ch['changed'] and ch['changed']['s'] > 0 and set(ch['changed']) | set(ch['same']) == set(dirs)
    assert ch['same'], 'a bigger eye does not change the back view'
    sheet = Image.open(ch['sheet'])
    whole = Image.open(os.path.join(os.path.dirname(spec), 'out', 'pose_rest_0.png'))
    assert sheet.width < whole.width  # fewer directions than the whole pose
    assert main(['pose', spec, '--dirs', 'all', '--changes']) is None
    assert 'changes: none' in capsys.readouterr().out


# ---------------------------------------------------------------- arcs and ground speed


def test_arcs_sheet_and_tracks(tmp_path, capsys):
    spec = stage_spec(tmp_path, MINIMAL)
    sp = S.load(spec)
    names = motion.default_tracks(sp)
    assert 'wrist_L' in names and 'head' in names and set(sp['sockets']) <= set(names)
    t = motion.tracks(sp, 'attack', 0, ['wrist_L'])['wrist_L']
    assert len(t) == len(render_all(spec, ['attack'], ['s'], jobs=1)[3]) and len(set(t)) > 1  # the hand moves
    res = motion.sheet(spec, 'idle', ['s', 'e'], jobs=1)
    assert res['directions'] == ['s', 'e'] and res['frames'] == 4 and os.path.exists(res['sheet'])
    assert Image.open(res['sheet']).width <= 1536
    with pytest.raises(Exception, match='did you mean wrist_L'):
        motion.sheet(spec, 'idle', track=['wirst_L'])
    assert main(['arcs', spec, '--anim', 'idle', '--dirs', 's', '--track', 'wrist_L,head']) is None
    assert 'tracks: wrist_L, head' in capsys.readouterr().out


def test_ground_speed_of_the_template_walk():
    sp = S.load(HUMANOID)
    assert sorted(motion.feet(sp)) == ['ankle_L', 'ankle_R']
    g = motion.ground_speed(sp, 'walk')
    # the stance covers 0.48 units in half of an 800 ms cycle: 1.2 units/s, 30 px/s at 0.040 units per pixel
    assert g['units_per_s'] == pytest.approx(1.2, abs=0.02) and g['px_per_s'] == pytest.approx(30, abs=0.5)
    assert sorted(g['feet']) == ['ankle_L', 'ankle_R'] and g['uneven'] > 0.5
    assert motion.ground_speed(sp, 'idle') is None  # no foot lifts
    assert motion.ground_speed(sp, 'attack') is None  # not a loop


# ---------------------------------------------------------------- usage log


def test_usage_log(tmp_path, monkeypatch, capsys):
    spec = stage_spec(tmp_path, MINIMAL)
    log = tmp_path / 'usage.jsonl'
    assert main(['validate', spec]) is None and not log.exists()  # off by default
    monkeypatch.setenv(usage.ENV, str(log))
    assert main(['pose', spec, '--dirs', 's,e']) is None
    assert main(['validate', spec]) is None
    capsys.readouterr()
    entries = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
    assert [e['name'] for e in entries] == ['pose', 'validate']
    ((_, w, h),) = entries[0]['images']
    assert w > 0 and h > 0 and entries[1]['images'] == [] and entries[1]['text_bytes'] > 0
    total = usage.summary(str(log))
    assert total['calls'] == 2 and total['images'] == 1
    assert total['tokens'] == sum(usage.tokens(e['text_bytes'], e['images']) for e in entries)
    assert main(['usage']) is None
    assert 'cli pose' in capsys.readouterr().out
    assert len(log.read_text(encoding='utf-8').splitlines()) == 2  # `usage` does not log itself
    assert main(['usage', '--clear']) is None and not log.exists()
