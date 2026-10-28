"""`spec outline` and `spec show`: read only the blocks you edit."""

import os

import pytest

from spritekiln import outline
from spritekiln.cli import main
from spritekiln.errors import SpriteKilnError

from conftest import REPO, stage_spec

GARGOYLE = os.path.join(REPO, 'specs', 'characters', 'gargula', 'gargula.yaml')
HUNTRESS = os.path.join(REPO, 'specs', 'characters', 'huntress', 'huntress.yaml')

SMALL = """\
spritekiln: 1
name: thing
materials:
  stone: {ramp: stone}   # flow style on one line
parts:
  # the body: a comment above an item belongs to it
  body:
    material: stone
    prims:
      - sphere: {c: [0, 1, 0], r: 0.3}
      - cone: {a: [0, 0.5, 0], b: [0, 1, 0],
               r: [0.2, 0.1]}

  # the arm
  arm_L:
    material: stone
    prims: [{sphere: {c: [0.3, 1, 0], r: 0.1}}]
"""


def _write(tmp_path, text=SMALL):
    p = tmp_path / 'thing.yaml'
    p.write_text(text, encoding='utf-8')
    return str(p)


def test_ranges_cover_comments_above_and_stop_at_content(tmp_path):
    r = outline.ranges(_write(tmp_path))
    assert r[('name',)] == (2, 2)
    assert r[('materials', 'stone')] == (4, 4)
    assert r[('parts', 'body')] == (6, 12)  # the comment above, not the blank line and comment after
    assert r[('parts', 'body', 'prims', 1)] == (11, 12)  # a flow mapping over two lines
    assert r[('parts', 'arm_L')] == (14, 17)
    assert r[('parts',)] == (5, 17)


def test_show_prints_the_file_lines(tmp_path):
    path = _write(tmp_path)
    lines = SMALL.split('\n')
    text = outline.show(path, ['parts.body'])
    head, *body = text.split('\n')
    assert head == '# parts.body: lines 6-12'
    assert [b.split('| ', 1)[1] if '| ' in b else '' for b in body] == lines[5:12]


def test_show_a_mirrored_item_shows_its_source(tmp_path):
    text = outline.show(_write(tmp_path), ['parts.arm_R'])
    assert text.startswith('# parts.arm_R: lines 14-17, mirrored from parts.arm_L')


def test_show_suggests_paths(tmp_path):
    with pytest.raises(SpriteKilnError, match='did you mean parts.body'):
        outline.show(_write(tmp_path), ['parts.bdy'])


def test_show_resolved_is_what_the_renderer_reads(tmp_path):
    text = outline.show(stage_spec(tmp_path, GARGOYLE), ['parts.arm_R'], resolved=True)
    assert text.startswith('# parts.arm_R (resolved)')
    assert '@shoulder_R' in text and '_mirror' not in text


def test_outline_lists_parts_and_animations_with_ranges(tmp_path):
    path = stage_spec(tmp_path, GARGOYLE)
    items = {i['path']: i for i in outline.outline(path)}
    assert items['parts.arm_L']['summary'].endswith('+ mirror arm_R')
    assert items['animations.walk']['summary'] == 'cycle, 8 frames, 840 ms, loop'
    assert items['materials']['summary'].startswith('8: stone, wing')
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().split('\n')
    a, _ = items['parts.torso']['lines']
    assert lines[a - 1].strip().startswith(('torso:', '#'))


def test_outline_is_a_fraction_of_the_spec():
    text = outline.outline_text(HUNTRESS)
    assert len(text.encode()) <= 6 * 1024
    assert len(text.encode()) < os.path.getsize(HUNTRESS) / 6


def test_cli(tmp_path, capsys):
    path = stage_spec(tmp_path, GARGOYLE)
    main(['spec', 'outline', path])
    assert '  arm_L' in capsys.readouterr().out
    main(['spec', 'show', path, 'parts.head', 'animations.idle'])
    out = capsys.readouterr().out
    assert '# parts.head: lines' in out and '# animations.idle: lines' in out
