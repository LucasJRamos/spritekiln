"""Render cache, memory-aware job count, resume and the process pool."""

import io
import os
import time

import numpy as np
import pytest

from spritekiln import cache, pipeline, system
from spritekiln.cli import main

from conftest import FIXTURES, stage_spec

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')


def _buf():
    rng = np.random.default_rng(0)
    g = rng.integers(-1, 5, (8, 8))
    d = np.where(g >= 0, rng.random((8, 8)), np.inf)
    return g, rng.random((8, 8)), d, rng.random((8, 8, 3))


def test_cache_roundtrip_is_exact(tmp_path):
    path = str(tmp_path / 'a' / 'k.npz')
    buf = _buf()
    cache.save(path, buf)
    got = cache.load(path)
    for a, b in zip(buf, got):
        assert a.dtype == b.dtype
        np.testing.assert_array_equal(a, b)
    assert not [f for f in os.listdir(tmp_path / 'a') if f.endswith('.tmp')]


def test_cache_never_unpickles(tmp_path):
    path = str(tmp_path / 'evil.npz')
    np.savez(path, g=np.array([object()], dtype=object), v=np.zeros(1), d=np.zeros(1), n=np.zeros(1))
    assert cache.load(path) is None
    (tmp_path / 'junk.npz').write_bytes(b'not a zip')
    assert cache.load(str(tmp_path / 'junk.npz')) is None
    assert cache.load(str(tmp_path / 'missing.npz')) is None


def test_cache_key_follows_engine_and_pose(tmp_path, monkeypatch):
    from spritekiln import spec as S
    from spritekiln.rig import rest_env

    sp = S.load(stage_spec(tmp_path, MINIMAL))
    env = rest_env(sp)
    k = cache.key(sp, env, 0)
    assert k == cache.key(sp, dict(env), 0)
    assert k != cache.key(sp, env, 90)
    assert k != cache.key(sp, dict(env, bob=0.01), 0)
    monkeypatch.setattr(cache, 'ENGINE', 'changed')
    assert k != cache.key(sp, env, 0)


def test_prune_lru_and_age(tmp_path):
    now = time.time()
    for i in range(5):
        p = tmp_path / f'{i}.npz'
        p.write_bytes(b'x' * 2**20)  # 1 MB each, i = 0 is the oldest
        os.utime(p, (now - (5 - i) * 86400, now - (5 - i) * 86400))
    n, mb = cache.prune(str(tmp_path), max_mb=3)
    assert (n, round(mb)) == (2, 2)
    assert sorted(os.listdir(tmp_path)) == ['2.npz', '3.npz', '4.npz']
    n, _ = cache.prune(str(tmp_path), older_than_days=1.5)
    assert n == 2 and os.listdir(tmp_path) == ['4.npz']


def test_auto_jobs_fits_available_memory(monkeypatch):
    sp = {'size': 96, 'camera': {'supersample': 3}, 'parts': {str(i): {} for i in range(40)}}
    monkeypatch.setattr(system, 'cpu_count', lambda: 16)
    monkeypatch.setattr(system, 'memory_mb', lambda: (1500, 16000))  # the dev machine on a busy day
    assert pipeline.auto_jobs(sp, 500, 500)[0] == 1
    monkeypatch.setattr(system, 'memory_mb', lambda: (3000, 16000))
    jobs, why = pipeline.auto_jobs(sp, 500, 500)
    assert 2 <= jobs <= 10 and 'GB available' in why
    monkeypatch.setattr(system, 'memory_mb', lambda: (64000, 128000))
    assert pipeline.auto_jobs(sp, 500, 500)[0] == 8  # capped by CPUs / 2
    assert pipeline.auto_jobs(sp, 3, 500)[0] == 3  # and by the work left
    monkeypatch.setattr(system, 'memory_mb', lambda: (None, None))
    assert pipeline.auto_jobs(sp, 500, 500)[0] == 2


def test_memory_probe_reports_something():
    avail, total = system.memory_mb()
    assert avail is None or 0 < avail <= total


def test_resume_from_cache_and_pool_matches_in_process(tmp_path):
    path = stage_spec(tmp_path, MINIMAL)
    notes = []
    _, _, _, first = pipeline.render_all(path, ['idle'], ['s', 'e'], jobs=1, log=notes.append)
    assert not any('resuming' in n for n in notes)
    _, _, _, pooled = pipeline.render_all(path, ['idle'], ['s', 'e'], jobs=2, log=notes.append)
    assert 'resuming: 8 of 8 frames already in the cache' in notes
    _, _, _, fresh_pool = pipeline.render_all(path, ['idle'], ['s', 'e'], jobs=2, force=True)
    for k, fr in first.items():
        for other in (pooled, fresh_pool):
            np.testing.assert_array_equal(fr.img, other[k].img)
            np.testing.assert_array_equal(fr.normal, other[k].normal)
            assert (fr.ms, fr.events, fr.sockets, fr.materials) == other[k][3:]


def test_dead_worker_degrades_to_fewer_jobs(tmp_path, monkeypatch):
    path = stage_spec(tmp_path, MINIMAL)
    calls = []

    def flaky_pool(tasks, jobs, out, on_done):
        calls.append(jobs)
        if len(calls) == 1:  # first pool "dies" after one frame
            key, frame = pipeline._job(tasks[0])
            out[key] = frame
            on_done()
            return tasks[1:]
        for t in tasks:
            key, frame = pipeline._job(t)
            out[key] = frame
            on_done()
        return []

    monkeypatch.setattr(pipeline, '_run_pool', flaky_pool)
    notes = []
    _, _, _, out = pipeline.render_all(path, ['idle'], ['s'], jobs=4, log=notes.append)
    assert calls == [4, 2] and len(out) == 4
    assert any('worker died' in n and 'continuing with 2 job(s)' in n for n in notes)


def test_unknown_animation_or_direction(tmp_path):
    from spritekiln.spec import SpecError

    path = stage_spec(tmp_path, MINIMAL)
    with pytest.raises(SpecError, match='unknown animation'):
        pipeline.render_all(path, ['dance'], jobs=1)
    with pytest.raises(SpecError, match='no direction matches'):
        pipeline.render_all(path, ['idle'], ['ne'], jobs=1)  # the fixture has 4 directions


def test_progress_without_terminal():
    s = io.StringIO()
    p = pipeline.Progress(20, stream=s)
    for _ in range(20):
        p.step()
    lines = s.getvalue().splitlines()
    assert lines[-1] == '  20/20 frames (100%)' and 9 <= len(lines) <= 11


def test_cache_command(tmp_path, capsys):
    path = stage_spec(tmp_path, MINIMAL)
    pipeline.render_all(path, ['idle'], ['s'], jobs=1)
    (tmp_path / 'specs' / '.pxcache').mkdir()
    main(['cache', 'info', str(tmp_path)])
    out = capsys.readouterr().out
    assert '.kilncache' in out and 'old pxforge cache' in out
    main(['cache', 'prune', str(tmp_path), '--max-mb', '0'])
    assert 'removed 4 entries' in capsys.readouterr().out
    main(['cache', 'clear', str(tmp_path)])
    out = capsys.readouterr().out
    assert 'removed' in out and 'kept; add --legacy' in out
    assert (tmp_path / 'specs' / '.pxcache').exists()
    main(['cache', 'clear', str(tmp_path), '--legacy'])
    assert not (tmp_path / 'specs' / '.pxcache').exists()
