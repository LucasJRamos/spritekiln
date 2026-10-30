"""Design 14: a spec `extends` a base and `use`s kits; problems point at the file that wrote them."""

import os

import numpy as np
import pytest

from spritekiln import api, kits, outline, pipeline, resources, style
from spritekiln import spec as S
from spritekiln.cli import main
from spritekiln.errors import SpriteKilnError
from spritekiln.rig import rest_env

from conftest import REPO, assert_image_matches, stage_spec

CACADOR = os.path.join(REPO, 'specs', 'characters', 'cacador', 'cacador.yaml')

BASE = """spritekiln: 1
name: base
brief: {summary: the base}
palette: pal/mine.yaml
size: 32
camera: {pitch: 38, scale: 0.075, center: [0, 0.8, 0]}
materials:
  stone: {ramp: stone}
  moss: {ramp: moss}
channels: {bob: 0}
bones:
  hips: {parent: root, pos: "[0, 0.6 + bob, 0]"}
  shoulder_L: {parent: hips, pos: [0.25, 0.3, 0]}
parts:
  body:
    material: stone
    space: hips
    prims: [{sphere: {c: [0, 0, 0], r: 0.25}}, {sphere: {c: [0, 0.3, 0], r: 0.15}}]
  cap:
    material: moss
    space: hips
    prims: [{sphere: {c: [0, 0.45, 0], r: 0.1}}]
animations:
  idle: {frames: 4, channels: {bob: "0.02*sin(p)"}}
"""
PALETTE = """ramps:
  stone: ["#14121c", "#3a3f52", "#6b7390", "#a7b0c8", "#e6ebf5"]
  moss: ["#0e1a0c", "#2c4a22", "#4f7a3a", "#8ab85c"]
"""
KIT = """spritekiln: 1
kit: club
license: CC0-1.0
summary: a club
at: shoulder_L
params:
  length: 0.4
  head: 0.08
  spikes: false
  offset: [0, 0, 0]
channels: {swing: 0}
host_channels: {bob: 1, gust: 0.5}   # the host's bob wins; gust is added
materials:
  wood: {ramp: wood}
  stone: {ramp: wood}
ramps:
  wood: ["#1c1006", "#4d2f0e", "#8a5a16", "#c48c22"]
bones:
  club: {parent: at, pos: offset, rot: "[swing*0.5, 0, 0]"}
parts:
  haft:
    material: wood
    space: club
    prims: [{cylinder: {a: [0, 0, 0], b: "[0, length, 0]", r: 0.035}}]
  club:
    material: wood
    space: club
    prims: [{sphere: {c: "@club", r: head}}]
  spike:
    material: stone
    space: club
    when: spikes
    prims: [{sphere: {c: "[head, length, 0]", r: 0.03}}]
    cut: [{plane: {n: [0, 1, 0], at: length}}]   # a plane's `at` is a distance, not a frame
sockets:
  tip: {bone: club, offset: "[0, length + head, 0]"}
"""


def _line(text, start, needle):
    """1-based number of the first line of `text` at or after a line starting with `start` that holds `needle`."""
    lines = text.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith(start))
    return next(i for i in range(first, len(lines)) if needle in lines[i]) + 1


def _files(tmp_path, child, kit=KIT):
    (tmp_path / 'lib' / 'pal').mkdir(parents=True)
    (tmp_path / 'lib' / 'base.yaml').write_text(BASE, encoding='utf-8')
    (tmp_path / 'lib' / 'pal' / 'mine.yaml').write_text(PALETTE, encoding='utf-8')
    (tmp_path / 'lib' / 'club.yaml').write_text(kit, encoding='utf-8')
    (tmp_path / 'me').mkdir()
    p = tmp_path / 'me' / 'me.yaml'
    p.write_text(child, encoding='utf-8')
    return str(p)


def test_extends_merges_the_base_and_the_spec_wins(tmp_path):
    path = _files(
        tmp_path,
        'spritekiln: 1\nextends: ../lib/base.yaml\nparts:\n  body: {material: moss}\n'
        '  cap: {prims: [{sphere: {c: [0, 0.5, 0], r: 0.12}}]}\n  tail:\n    material: stone\n    space: hips\n'
        '    prims: [{sphere: {c: [0, 0, -0.3], r: 0.08}}]\n',
    )
    sp = S.load(path)
    assert sp['name'] == 'me' and 'brief' not in sp['_raw']  # the name and the brief are the spec's own
    assert sp['parts']['body']['material'] == 'moss' and len(sp['parts']['body']['prims']) == 2  # merged
    assert sp['parts']['cap']['prims'] == [{'sphere': {'c': [0, 0.5, 0], 'r': 0.12}}]  # a list is replaced
    assert list(sp['parts']) == ['body', 'cap', 'tail']
    assert sp['ramps']['moss'][0] == '#0e1a0c'  # the base's palette file, relative to the base
    assert os.path.join(tmp_path, 'lib', 'base.yaml') in sp['_files']
    assert S.check(sp) == ([], [])


def test_remove_and_its_mistakes(tmp_path):
    sp = S.load(_files(tmp_path, 'spritekiln: 1\nextends: ../lib/base.yaml\nremove: [parts.cap, materials.moss]\n'))
    assert list(sp['parts']) == ['body'] and list(sp['materials']) == ['stone']
    with pytest.raises(SpriteKilnError, match=r'me\.yaml:3:\d+: remove: path "parts.cp" not found \(did you mean'):
        S.load(_files(tmp_path / 'b', 'spritekiln: 1\nextends: ../lib/base.yaml\nremove: [parts.cp]\n'))


def test_a_missing_base_and_a_loop(tmp_path):
    missing = r'me\.yaml:2:\d+: extends: base "humanoyd" not found \(did you mean humanoid'
    with pytest.raises(SpriteKilnError, match=missing):
        S.load(_files(tmp_path, 'spritekiln: 1\nextends: humanoyd\n'))
    loop = tmp_path / 'loop'
    loop.mkdir()
    (loop / 'a.yaml').write_text('spritekiln: 1\nextends: b.yaml\n', encoding='utf-8')
    (loop / 'b.yaml').write_text('spritekiln: 1\nextends: a.yaml\n', encoding='utf-8')
    with pytest.raises(SpriteKilnError, match='a loop'):
        S.load(str(loop / 'a.yaml'))


def test_a_kit_is_renamed_and_its_params_replaced(tmp_path):
    child = (
        'spritekiln: 1\nextends: ../lib/base.yaml\n'
        'use: [{kit: ../lib/club.yaml, as: club_L, with: {length: 0.5, spikes: true, offset: [0, 0.1, 0]}}]\n'
    )
    sp = S.load(_files(tmp_path, child))
    raw = sp['_raw']
    assert set(raw['parts']) == {'body', 'cap', 'club_L_haft', 'club_L', 'club_L_spike'}  # the kit's own name: `as`
    assert raw['bones']['club_L'] == {'parent': 'shoulder_L', 'pos': [0, 0.1, 0], 'rot': '[club_L_swing * 0.5, 0, 0]'}
    assert raw['parts']['club_L_haft']['prims'][0]['cylinder']['b'] == [0, 0.5, 0]  # a param alone: its value
    assert raw['parts']['club_L']['prims'][0]['sphere'] == {'c': '@club_L', 'r': 0.08}
    assert raw['parts']['club_L_spike']['when'] is True
    assert raw['channels'] == {'bob': 0, 'club_L_swing': 0, 'gust': 0.5}
    assert raw['parts']['club_L_spike']['cut'][0]['plane']['at'] == 0.5
    assert sp['channels']['bob'] == 0 and sp['channels']['gust'] == 0.5  # host channels the kit reads
    assert raw['sockets']['club_L_tip'] == {'bone': 'club_L', 'offset': '[0, 0.5 + 0.08, 0]'}
    assert {'club_R', 'club_R_haft', 'club_R_spike'} <= set(sp['parts'])  # `as` ending in _L: mirrored
    assert sp['bones']['club_R']['parent'] == 'shoulder_R'
    assert sp['materials']['stone']['ramp'] == 'stone'  # the spec's own material wins
    assert sp['materials']['wood']['ramp'] == 'wood' and sp['ramps']['wood'][0] == '#1c1006'  # the kit's defaults
    assert S.check(sp) == ([], [])
    groups = pipeline.render_buffers(sp, rest_env(sp, 45.0), 45.0)[1]
    assert {'club_L', 'club_R_haft'} <= {g.name for g in groups}


def test_sx_makes_direction_cheats_mirror_safe(tmp_path):
    """`yaw*sx` is the direction as an _L item's source sees it: its automatic _R twin cheats in the mirrored
    direction (a kit used `as: x_L` keeps its cheats on the right side)."""
    from spritekiln.rig import Ctx

    child = (
        'spritekiln: 1\nextends: ../lib/base.yaml\nbones:\n'
        '  hand_L: {parent: shoulder_L, pos: "[0, 0.2*pulse(yaw*sx, 90, 30), 0]"}\n'
    )
    sp = S.load(_files(tmp_path, child))
    lift = {}
    for yaw in (90.0, -90.0):
        ctx = Ctx(sp, rest_env(sp, yaw))
        lift[yaw] = {
            s: round(float(ctx.frame(f'hand_{s}', '').o[1] - ctx.frame(f'shoulder_{s}', '').o[1]), 3) for s in 'LR'
        }
    assert lift[90.0] == {'L': 0.2, 'R': 0.0} and lift[-90.0] == {'L': 0.0, 'R': 0.2}


def test_kit_materials_can_be_mapped(tmp_path):
    child = 'spritekiln: 1\nextends: ../lib/base.yaml\nuse: [{kit: ../lib/club.yaml, materials: {wood: moss}}]\n'
    sp = S.load(_files(tmp_path, child))
    assert sp['parts']['club_haft']['material'] == 'moss' and 'wood' not in sp['materials']


def test_a_use_with_the_same_as_replaces_the_bases(tmp_path):
    (tmp_path / 'lib').mkdir()
    (tmp_path / 'lib' / 'club.yaml').write_text(KIT, encoding='utf-8')
    (tmp_path / 'lib' / 'pal').mkdir()
    (tmp_path / 'lib' / 'pal' / 'mine.yaml').write_text(PALETTE, encoding='utf-8')
    (tmp_path / 'lib' / 'base.yaml').write_text(BASE + 'use: [{kit: club.yaml, with: {spikes: true}}]\n', 'utf-8')
    (tmp_path / 'a.yaml').write_text(
        'spritekiln: 1\nextends: lib/base.yaml\nuse: [{kit: lib/club.yaml, with: {length: 0.7}}]\n', 'utf-8'
    )
    sp = S.load(str(tmp_path / 'a.yaml'))
    assert sp['parts']['club_spike']['when'] is False  # the base's use (with spikes) is gone, not merged
    assert sp['parts']['club_haft']['prims'][0]['cylinder']['b'] == [0, 0.7, 0]
    (tmp_path / 'b.yaml').write_text('spritekiln: 1\nextends: lib/base.yaml\nremove: [use.club]\n', 'utf-8')
    sp = S.load(str(tmp_path / 'b.yaml'))
    assert set(sp['parts']) == {'body', 'cap'} and 'club' not in sp['bones'] and not sp['sockets']


@pytest.mark.parametrize(
    'use, message',
    [
        ('{kit: clubb}', r'use\[0\]\.kit: kit "clubb" not found'),
        ('{kit: ../lib/club.yaml, with: {lenght: 1}}', r'kit club has no param "lenght" \(did you mean "length"\?\)'),
        ('{kit: ../lib/club.yaml, wiht: {}}', r'unknown key "wiht" \(did you mean "with"\?\)'),
        ('{kit: ../lib/club.yaml, as: cap}', r'adds parts\.cap, which the spec already has'),
    ],
)
def test_kit_mistakes(tmp_path, use, message):
    with pytest.raises(SpriteKilnError, match=r'me\.yaml:3:\d+: .*' + message):
        S.load(_files(tmp_path, f'spritekiln: 1\nextends: ../lib/base.yaml\nuse: [{use}]\n'))


def test_problems_point_at_the_kit_file(tmp_path):
    thin = KIT.replace('r: head}}', 'r: head, shell: 0.01}}')
    sp = S.load(_files(tmp_path, 'spritekiln: 1\nextends: ../lib/base.yaml\nuse: [{kit: ../lib/club.yaml}]\n', thin))
    errors, warnings = S.check(sp)
    assert not errors and any(
        f'club.yaml:{_line(thin, "  club:", "shell")}:' in w and 'parts.club.prims[0].sphere.shell' in w
        for w in warnings
    )
    bad = KIT.replace('summary: a club', 'summary: a club\ncolour: red')
    with pytest.raises(SpriteKilnError, match=r'club\.yaml:5:1: unknown key "colour" in a kit'):
        S.load(
            _files(tmp_path / 'b', 'spritekiln: 1\nextends: ../lib/base.yaml\nuse: [{kit: ../lib/club.yaml}]\n', bad)
        )


def test_outline_and_show_see_through_the_base_and_kits(tmp_path):
    child = (
        'spritekiln: 1\nextends: ../lib/base.yaml\nuse: [{kit: ../lib/club.yaml}]\n'
        + 'parts:\n  body: {material: moss}\n'
    )
    path = _files(tmp_path, child)
    items = {i['path']: i for i in outline.outline(path)}
    assert items['parts.body']['lines'] == [5, 5] and items['parts']['summary'] == '5 items (1 here)'
    assert items['parts.cap']['lines'] is None and items['parts.cap']['summary'].startswith('from base.yaml:')
    assert items['parts.club_haft']['summary'].startswith('from kit club;')
    text = outline.show(path, ['parts.club_haft', 'parts.body'])
    a, b = _line(KIT, '  haft:', 'haft'), _line(KIT, '  haft:', 'prims')
    assert f'club.yaml lines {a}-{b} (as parts.haft)' in text and 'base.yaml lines 15-18' in text
    assert text.rstrip().endswith('5|   body: {material: moss}')


def test_a_kit_file_shows_on_its_host():
    sp = S.load(resources.kit('sword'))
    assert sp['name'] == 'sword' and sp['_raw']['extends'] == 'humanoid'
    assert {'sword_blade', 'sword_grip', 'torso', 'arm_R'} <= set(sp['parts'])


@pytest.mark.parametrize('name', resources.kits())
def test_every_built_in_kit_renders(tmp_path, name):
    """Each kit on its host shows its parts in s, e, n and w (a draft render of a copy: no cache lands next to
    the kits)."""
    path = tmp_path / f'{name}.yaml'
    path.write_text(open(resources.kit(name), encoding='utf-8').read(), encoding='utf-8')
    sp = S.as_draft(S.load(str(path)))
    mine = {n for n in sp['_raw']['parts'] if n == name or n.startswith(name + '_')}
    assert mine, name
    seen = 0
    for _, yaw in sp['directions'][::2]:
        gb, groups = pipeline.render_buffers(sp, rest_env(sp, yaw), yaw)[:2]
        ids = [i for i, g in enumerate(groups) if g.name.split(':')[0] in mine]
        seen += int(np.isin(gb.gid, ids).sum())
    assert seen > 30, f'kit {name}: {seen} px over 4 directions'


@pytest.mark.parametrize(
    'args, golden', [([], 'cacador_pose_rest.png'), (['--anim', 'attack', '--frame', '4'], 'cacador_pose_attack_4.png')]
)
def test_the_cacador_extends_the_template(tmp_path, update_golden, args, golden):
    """215 lines that copied the humanoid template became 31 that extend it (rendering exactly as the copy did);
    since design 16 it has the template's head and hair kits, and the goldens show them."""
    out = str(tmp_path / golden)
    main(['pose', stage_spec(tmp_path, CACADOR), '--dirs', 'all', '--scale', '1', '--no-crop', '-o', out, *args])
    assert_image_matches(out, golden, update_golden)
    with open(CACADOR, encoding='utf-8') as fh:
        assert len(fh.read().splitlines()) <= 31


def test_new_extends_and_the_kits_command(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'game'
    root.mkdir()
    main(['init', str(root), '--engine', 'generic', '--ai', 'claude', '--no-mcp'])
    monkeypatch.chdir(root)
    style.record(dict(height=48, palette='gothic'))
    main(['new', 'hero', '--extends'])
    path = root / 'art' / 'specs' / 'characters' / 'hero' / 'hero.yaml'
    text = path.read_text(encoding='utf-8')
    assert 'extends: humanoid' in text and len(text.splitlines()) <= 17
    sp = S.load(str(path))
    errors, warnings = S.check(sp)
    assert sp['camera']['scale'] == 0.03667 and 'sword_blade' in sp['parts'] and errors == []
    assert [w.split(': ')[1] for w in warnings] == ['brief.head']  # the head is decided next (design 16)
    assert style.status()['off_style'] == []
    capsys.readouterr()
    main(['kits'])
    assert 'sword' in capsys.readouterr().out
    main(['kits', 'sword'])
    out = capsys.readouterr().out
    assert 'length: 0.44' in out and 'use: [{kit: sword' in out
    assert api.kits()[0]['name'] in resources.kits()
    with pytest.raises(SpriteKilnError, match='did you mean sword'):
        api.kits('swrod')


def test_the_style_reads_specs_through_their_base(tmp_path, monkeypatch):
    root = tmp_path / 'game'
    root.mkdir()
    main(['init', str(root), '--engine', 'generic', '--ai', 'claude', '--no-mcp'])
    monkeypatch.chdir(root)
    main(['new', 'hero', '--extends'])
    (root / 'art' / 'specs' / 'kits').mkdir()
    (root / 'art' / 'specs' / 'kits' / 'club.yaml').write_text(KIT, encoding='utf-8')
    s = style.status()['suggested']
    assert s['source'] == '1 existing spec(s)' and s['scale'] == 0.04  # the kit is not a spec
    assert [k['name'] for k in kits.catalogue() if k['origin'] == 'project'] == ['club']


HERO = """spritekiln: 1
name: hero
extends: humanoid
brief:
  summary: a test hero
{head}
{rest}
"""


def _hero(tmp_path, head='', rest=''):
    p = tmp_path / 'hero.yaml'
    p.write_text(HERO.format(head=head, rest=rest), encoding='utf-8')
    return str(p)


def _head_warnings(path):
    return [w for w in S.check(S.load(path))[1] if 'brief.head' in w or 'use.hair' in w]


def test_a_character_over_the_template_says_how_its_head_looks(tmp_path):
    """Design 16: the template's head and hair are placeholders until `brief.head` decides them."""
    path = _hero(tmp_path)
    (warning,) = _head_warnings(path)
    assert warning.startswith(path) and ':4:1: brief.head: describe' in warning  # at the spec's brief
    assert _head_warnings(_hero(tmp_path, head='  head: short hair, a fringe, soft jaw; eyes only')) == []
    assert not [w for w in S.check(S.load(resources.kit('hood')))[1] if 'brief.head' in w]  # a kit on its host


def test_replacing_a_kit_part_keeps_the_kits_other_parts(tmp_path):
    hair = """parts:
  hair:
    prims:
      - ellipsoid: {c: [0, 0.2, -0.03], r: [0.16, 0.12, 0.16]}"""
    head = '  head: my own cap of hair'
    (warning,) = _head_warnings(_hero(tmp_path, head, hair))
    assert 'parts.hair.prims: replaces the shape of the hair kit' in warning and 'remove use.hair' in warning
    own = hair.replace('    prims:', '    material: hair\n    space: head\n    prims:')
    path = _hero(tmp_path, head, 'remove: [use.hair]\n' + own)
    assert _head_warnings(path) == []
    sp = S.load(path)
    assert not [p for p in sp['parts'] if p.startswith('hair_')]
