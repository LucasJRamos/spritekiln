"""JSON Schema: every spec conforms; typos and missing keys are reported with file:line:column."""

import glob
import json
import os
import textwrap

import jsonschema
import pytest

from spritekiln import schema
from spritekiln import spec as S
from spritekiln.cli import main

from conftest import FIXTURES, REPO

SPECS = sorted(
    f
    for f in glob.glob(os.path.join(REPO, 'specs', '**', '*.yaml'), recursive=True)
    if 'palettes' not in f and '_ref' not in f
) + [os.path.join(FIXTURES, 'minimal', 'minimal.yaml')]


def test_schema_is_valid_draft_2020_12():
    jsonschema.Draft202012Validator.check_schema(schema.schema())


@pytest.mark.parametrize('path', SPECS, ids=lambda p: os.path.basename(p))
def test_every_spec_conforms(path):
    with open(path, encoding='utf-8') as fh:
        doc = json.loads(json.dumps(S.yload(fh), default=str))  # YAML int keys -> JSON strings
    errors = list(jsonschema.Draft202012Validator(schema.schema()).iter_errors(doc))
    assert not errors, [f'{"/".join(map(str, e.absolute_path))}: {e.message[:120]}' for e in errors]
    assert S.check(S.load(path)) == ([], [])


TYPOS = """\
spritekiln: 1
name: typo
ramps:
  body: ["#111111", "#444444", "#888888", "#cccccc"]
camera: {pich: 38, scale: 0.05}
materials:
  body: {ramp: body, outlne: false}
channels:
  bob: 0.0
bones:
  hips: {parent: root, pos: "[0, 0.6 + bob, 0]"}
parts:
  torso:
    material: body
    space: hips
    prims:
      - sphere: {c: [0, 0, 0], radius: 0.2}
      - blob: {c: [0, 0, 0]}
animations:
  idle: {frames: 4, chanels: {bob: "0.03*sin(p)"}}
"""


def _write(tmp_path, text, name='spec.yaml'):
    p = tmp_path / name
    p.write_text(textwrap.dedent(text), encoding='utf-8')
    return str(p)


def test_typos_are_warnings_with_positions(tmp_path):
    errors, warnings = S.check(S.load(_write(tmp_path, TYPOS)))
    text = '\n'.join(warnings)
    assert 'spec.yaml:5:10: camera.pich: unknown key "pich" (did you mean "pitch"?)' in text
    assert 'spec.yaml:7:22: materials.body.outlne: unknown key "outlne" (did you mean "outline"?)' in text
    assert 'spec.yaml:20:21: animations.idle.chanels: unknown key "chanels" (did you mean "channels"?)' in text
    assert 'spec.yaml:18:9: parts.torso.prims[1].blob: unknown key "blob" (expected one of: arc, box, chain' in text
    assert 'spec.yaml:17:32: parts.torso.prims[0].sphere.radius: unknown key "radius" (expected one of: c, r)' in text
    assert 'spec.yaml:17:9: parts.torso.prims[0].sphere: missing required key "r"' in '\n'.join(errors)


def test_problems_point_at_the_line(tmp_path):
    text = TYPOS.replace('pich', 'pitch').replace('outlne', 'outline').replace('radius', 'r')
    text = text.replace('      - blob: {c: [0, 0, 0]}\n', '').replace('chanels', 'channels')
    text = text.replace('parent: root', 'parent: nowhere')
    errors, warnings = S.check(S.load(_write(tmp_path, text)))
    assert warnings == [] and len(errors) == 1
    assert errors[0].endswith('spec.yaml:11:10: bones.hips.parent: unknown frame "nowhere"')


def test_mirrored_twins_point_at_the_left_side(tmp_path):
    text = TYPOS.split('animations:')[0].replace('pich', 'pitch').replace('outlne', 'outline')
    text = text.replace('radius', 'r').replace('      - blob: {c: [0, 0, 0]}\n', '')
    text = text.replace('bones:\n', 'bones:\n  shoulder_L: {parent: nowhere}\n')
    errors, _ = S.check(S.load(_write(tmp_path, text)))
    assert len(errors) == 2  # shoulder_L and its automatic shoulder_R twin
    assert errors[0].endswith(':11:16: bones.shoulder_L.parent: unknown frame "nowhere"')
    assert errors[1].endswith(':11:16: bones.shoulder_R.parent: unknown frame "nowhere"')


def test_version_header(tmp_path):
    _, warnings = S.check(S.load(_write(tmp_path, TYPOS.replace('spritekiln: 1\n', ''))))
    assert any('no version header' in w for w in warnings)
    _, warnings = S.check(S.load(_write(tmp_path, TYPOS.replace('spritekiln: 1', 'pxforge: 1'))))
    assert not any('version header' in w for w in warnings)
    with pytest.raises(S.SpecError, match='spec version 2 is not supported'):
        S.load(_write(tmp_path, TYPOS.replace('spritekiln: 1', 'spritekiln: 2')))


def test_cli_validate_warnings_and_strict(tmp_path, capsys):
    text = TYPOS.replace('radius', 'r').replace('      - blob: {c: [0, 0, 0]}\n', '')
    path = _write(tmp_path, text)
    main(['validate', path])
    out = capsys.readouterr().out
    assert out.count('warning:') == 3 and 'OK: typo' in out
    with pytest.raises(SystemExit) as e:
        main(['validate', path, '--strict'])
    assert e.value.code == 1
