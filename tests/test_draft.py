"""Draft previews: one sample per pixel for fast iteration, never mixed with full renders or exported."""

import os

import pytest

from spritekiln import api, pipeline
from spritekiln import spec as S
from spritekiln.cli import main
from spritekiln.rig import rest_env

from conftest import FIXTURES, REPO, stage_spec

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')
GARGOYLE = os.path.join(REPO, 'specs', 'characters', 'gargula', 'gargula.yaml')


@pytest.mark.parametrize('yaw', [0.0, 135.0])
def test_draft_finds_the_same_parts(tmp_path, yaw):
    path = stage_spec(tmp_path, GARGOYLE)
    full, draft = S.load(path), S.as_draft(S.load(path))
    env = rest_env(full, yaw)
    g_full = pipeline.render_buffers(full, env, yaw)[0][0]
    g_draft = pipeline.render_buffers(draft, env, yaw)[0][0]
    both = (g_full >= 0) & (g_draft >= 0)
    assert both.sum() > 0.9 * (g_full >= 0).sum()  # same silhouette but for edge pixels
    assert (g_full[both] == g_draft[both]).mean() >= 0.95


def test_draft_and_full_poses_do_not_share_cache_entries(tmp_path):
    path = stage_spec(tmp_path, MINIMAL)
    full, draft = S.load(path), S.as_draft(S.load(path))
    env = rest_env(full, 0.0)
    from spritekiln import cache

    assert cache.entry(full, env, 0.0) != cache.entry(draft, env, 0.0)


def test_pose_draft_file_name(tmp_path):
    path = stage_spec(tmp_path, MINIMAL)
    out, dirs, _ = api.pose(path, dirs='s', draft=True)
    assert os.path.basename(out) == 'pose_rest_0_draft.png'
    assert os.path.basename(api.pose(path, dirs='s')[0]) == 'pose_rest_0.png'


def test_render_draft_writes_previews_only(tmp_path):
    path = stage_spec(tmp_path, MINIMAL)
    out = tmp_path / 'out'
    main(['render', path, '--draft', '--anims', 'attack', '--jobs', '1', '-o', str(out)])
    assert (out / 'preview-draft' / 'contact_attack.png').exists()
    assert (out / 'preview-draft' / 'attack_4dir.gif').exists()
    assert not (out / 'minimal.png').exists() and not (out / 'minimal.json').exists()
    assert not (out / 'qa.json').exists()


def test_a_draft_cannot_be_exported(tmp_path, capsys):
    path = stage_spec(tmp_path, MINIMAL)
    with pytest.raises(SystemExit):
        main(['render', path, '--draft', '--export'])
    assert 'cannot be exported' in capsys.readouterr().err


def test_draft_pose_is_faster(tmp_path):
    """Not a benchmark: a draft traces 1 ray per pixel instead of 9, so it must not be slower."""
    import time

    path = stage_spec(tmp_path, GARGOYLE)
    full, draft = S.load(path), S.as_draft(S.load(path))
    env = rest_env(full, 0.0)
    times = []
    for sp in (full, draft):
        t = time.perf_counter()
        pipeline.render_buffers(sp, env, 0.0, force=True)
        times.append(time.perf_counter() - t)
    assert times[1] < times[0], times
