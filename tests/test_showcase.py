"""Showcase reproduction: a cache-less re-render of Templar and Huntress must match the shipped output.

The baseline is the `out/` that Hunt Tower ships (byte-identical to its `assets/pxforge/`). Only
hashes are versioned (tests/golden/showcase.json), never showcase pixels. A full run takes about an
hour on the dev machine:

    pytest -m slow tests/test_showcase.py                      # everything
    SHOWCASE_ANIMS=hurt pytest -m slow tests/test_showcase.py  # quick partial check
    SHOWCASE_JOBS=1 ...                                        # worker processes (default 2)

Rebuild the hashes from rendered folders (only when the baseline changes on purpose):

    python tests/test_showcase.py specs/characters/templar/out/templar specs/characters/huntress/out/huntress
"""
import hashlib
import json
import os
import sys

import numpy as np
import pytest
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HASHES = os.path.join(HERE, 'golden', 'showcase.json')
SHOWCASE = {'templar': 'specs/characters/templar/templar.yaml',
            'huntress': 'specs/characters/huntress/huntress.yaml'}


def _sha(data):
    return hashlib.sha1(data).hexdigest()[:16]


def hashes_of(out_dir):
    """Per-frame pixel hashes (color, normal, emissive) and per-animation metadata hashes."""
    name = os.path.basename(os.path.normpath(out_dir))
    with open(os.path.join(out_dir, f'{name}.json'), encoding='utf-8') as fh:
        meta = json.load(fh)
    px = meta['pxforge']
    atlases = [np.asarray(Image.open(os.path.join(out_dir, f)).convert('RGBA'))
               for f in (meta['meta']['image'], px['normal_map'], px['emissive_map'])]
    frames = {}
    for key, fr in meta['frames'].items():
        r = fr['frame']
        frames[key] = [_sha(a[r['y']:r['y'] + r['h'], r['x']:r['x'] + r['w']].tobytes()) for a in atlases]
    anims = {}
    for a, A in px['animations'].items():   # atlas rows depend on which animations were rendered
        dirs = {d: {k: v for k, v in D.items() if k != 'row'} for d, D in A['directions'].items()}
        anims[a] = _sha(json.dumps(dict(A, directions=dirs), sort_keys=True).encode())
    head = {k: v for k, v in px.items() if k != 'animations'}
    return dict(frame_size=px['frame_size'], header=_sha(json.dumps(head, sort_keys=True).encode()),
                animations=anims, frames=frames)


def _expected(name):
    with open(HASHES, encoding='utf-8') as fh:
        return json.load(fh)[name]


@pytest.mark.slow
@pytest.mark.parametrize('name', list(SHOWCASE))
def test_showcase_reproduces(tmp_path, name):
    from conftest import stage_spec
    from pxforge.export import export
    from pxforge.pipeline import render_all

    anims = os.environ.get('SHOWCASE_ANIMS')
    jobs = int(os.environ.get('SHOWCASE_JOBS', '2'))
    staged = stage_spec(tmp_path, os.path.join(REPO, SHOWCASE[name]))
    spec, anim_list, dlist, out = render_all(staged, anims.split(',') if anims else None, None, jobs, progress=None)
    dst = str(tmp_path / 'out' / name)
    export(spec, anim_list, dlist, out, dst)

    got, want = hashes_of(dst), _expected(name)
    assert got['frame_size'] == want['frame_size']
    assert got['header'] == want['header'], 'directions, pivot or map names changed'
    for a in anim_list:
        assert got['animations'][a] == want['animations'][a], f'{a}: frame list, durations or events changed'
    bad = [k for k, h in got['frames'].items() if h != want['frames'].get(k)]
    assert not bad, f'{len(bad)} of {len(got["frames"])} frame(s) differ, e.g. {bad[:8]}'
    if not anims:
        assert set(got['frames']) == set(want['frames'])


if __name__ == '__main__':
    data = {}
    for d in sys.argv[1:]:
        data[os.path.basename(os.path.normpath(d))] = hashes_of(d)
    with open(HASHES, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
        fh.write('\n')
    print(f'wrote {HASHES}: ' + ', '.join(f'{k} ({len(v["frames"])} frames)' for k, v in data.items()))
