"""Golden image tests: the full pipeline (rig -> SDF render -> pixelize -> export) against versioned PNGs.

Every test renders a staged copy of the spec, so the render cache starts empty. Refresh the goldens
after an intentional visual change with `pytest --update-golden` and say why in the commit message.
"""

import json
import os

import numpy as np
import pytest
from PIL import Image

from spritekiln.cli import main

from conftest import FIXTURES, GOLDEN, REPO, assert_image_matches, golden_is_native, stage_spec

GARGOYLE = os.path.join(REPO, 'specs', 'characters', 'gargula', 'gargula.yaml')
MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')


@pytest.mark.parametrize(
    'spec, args, golden',
    [
        (GARGOYLE, [], 'gargula_pose_rest.png'),
        (MINIMAL, [], 'minimal_pose_rest.png'),
        (MINIMAL, ['--anim', 'attack', '--frame', '1'], 'minimal_pose_attack_1.png'),
    ],
    ids=['gargoyle-rest', 'minimal-rest', 'minimal-attack-hit'],
)
def test_pose_all_directions(tmp_path, update_golden, spec, args, golden):
    out = str(tmp_path / golden)
    main(['pose', stage_spec(tmp_path, spec), '--dirs', 'all', '--scale', '1', '-o', out, *args])
    assert_image_matches(out, golden, update_golden)


def _versionless(data):
    """Drop the fields that change with every release."""
    data = json.loads(json.dumps(data))
    data.get('meta', {}).pop('version', None)
    data.get('spritekiln', {}).pop('generator', None)
    return data


def test_render_minimal(tmp_path, update_golden):
    out = tmp_path / 'out'
    main(['render', stage_spec(tmp_path, MINIMAL), '--jobs', '1', '-o', str(out)])
    for name in ('minimal.png', 'minimal_normal.png', 'minimal_emissive.png'):
        assert_image_matches(str(out / name), f'render_{name}', update_golden)
    for name in ('minimal.json', 'qa.json'):
        actual = json.loads((out / name).read_text(encoding='utf-8'))
        path = os.path.join(GOLDEN, f'render_{name}')
        if update_golden:
            with open(path, 'w', encoding='utf-8', newline='\n') as fh:
                json.dump(actual, fh, indent=1, ensure_ascii=False)
                fh.write('\n')
            continue
        with open(path, encoding='utf-8') as fh:
            expected = json.load(fh)
        if name == 'qa.json' and not golden_is_native():  # colour counts may move with float noise
            actual, expected = [{k: d[k] for k in ('ok', 'errors')} for d in (actual, expected)]
        assert _versionless(actual) == _versionless(expected), f'{name} differs from tests/golden/render_{name}'
    assert (out / 'preview' / 'idle_4dir.gif').exists()
    assert (out / 'preview' / 'contact_attack.png').exists()


def test_comparison_catches_a_single_pixel(tmp_path, monkeypatch):
    import conftest

    monkeypatch.setattr(conftest, 'golden_is_native', lambda: True)  # exact mode on any platform
    img = np.asarray(Image.open(os.path.join(GOLDEN, 'minimal_pose_rest.png')).convert('RGBA')).copy()
    img[10, 10] = (255, 0, 255, 255)
    path = str(tmp_path / 'changed.png')
    Image.fromarray(img).save(path)
    with pytest.raises(pytest.fail.Exception, match='1 pixel'):
        assert_image_matches(path, 'minimal_pose_rest.png')
