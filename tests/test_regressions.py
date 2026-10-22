"""Bugs found in the pre-launch review, each pinned by a test."""

import json
import os
import shutil
import time

import pytest
import yaml

from spritekiln import api, cache, engines, pipeline, scaffold
from spritekiln import spec as S
from spritekiln.cli import main
from spritekiln.errors import ExportError, SpriteKilnError

from conftest import FIXTURES, GOLDEN, stage_spec

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')


def _variant(tmp_path, edit, name='variant'):
    """A staged copy of the minimal fixture with its YAML changed by `edit(dict)`."""
    stage_spec(tmp_path, MINIMAL)
    data = yaml.safe_load(open(MINIMAL, encoding='utf-8'))
    data['name'] = name
    edit(data)
    path = tmp_path / 'specs' / 'characters' / name / f'{name}.yaml'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    return str(path)


def test_cache_key_follows_the_order_of_parts(tmp_path):
    a = S.load(_variant(tmp_path, lambda d: None, 'a'))
    b = S.load(_variant(tmp_path, lambda d: d.update(parts=dict(reversed(list(d['parts'].items())))), 'b'))
    env = {'bob': 0.0}
    assert cache.key(a, env, 0) != cache.key(b, env, 0)


def test_events_as_lists_and_quoted_keys(tmp_path):
    from spritekiln.anim import frames_of

    def edit(d):
        d['animations']['idle']['events'] = {'0': ['step_l', 'dust'], 2: 'step_r'}

    sp = S.load(_variant(tmp_path, edit))
    events = [ev for _, _, ev in frames_of(sp, 'idle')]
    assert events[0] == ['step_l', 'dust'] and events[2] == ['step_r']


def test_an_event_on_a_missing_frame_is_an_error(tmp_path):
    sp = S.load(_variant(tmp_path, lambda d: d['animations']['idle'].update(events={9: 'late'})))
    assert any('frame 9 does not exist' in e for e in S.validate(sp))


def test_partial_shadow_radii_follow_the_frame_size(tmp_path):
    sp = S.load(_variant(tmp_path, lambda d: d.update(shadow={'alpha': 90})))  # the fixture is 32 px
    assert sp['shadow']['rx'] == pytest.approx(13.5 * 32 / 64) and sp['shadow']['alpha'] == 90


def test_project_palettes_folder(tmp_path):
    scaffold.init(str(tmp_path / 'game'), mcp=False)
    pal = tmp_path / 'game' / 'art' / 'specs' / 'palettes' / 'mygame.yaml'
    shutil.copy(os.path.join(os.path.dirname(MINIMAL), '..', '..', '..', 'specs', 'palettes', 'gothic.yaml'), pal)
    spec = api.new('hero', start=str(tmp_path / 'game'), folder=str(tmp_path / 'game' / 'art' / 'specs' / 'characters'))
    text = open(spec, encoding='utf-8').read().replace('palette: gothic', 'palette: mygame')
    open(spec, 'w', encoding='utf-8').write(text)
    sp = S.load(spec)
    assert sp['_files'] == [str(pal)]


def test_in_process_spec_cache_sees_palette_edits(tmp_path):
    path = _variant(tmp_path, lambda d: d.update(palette='pal.yaml', ramps=None))
    pal = os.path.join(os.path.dirname(path), 'pal.yaml')
    ramps = yaml.safe_load(open(MINIMAL, encoding='utf-8'))['ramps']
    open(pal, 'w', encoding='utf-8').write(yaml.safe_dump({'ramps': ramps}))
    first = pipeline.get_spec(path)
    time.sleep(0.05)
    ramps['body'][-1] = '#00ff00'
    open(pal, 'w', encoding='utf-8').write(yaml.safe_dump({'ramps': ramps}))
    os.utime(pal, (time.time() + 5, time.time() + 5))
    second = pipeline.get_spec(path)
    assert second is not first and second['ramps']['body'][-1] == '#00ff00'


def test_side_view_pose_all_means_its_own_directions(tmp_path):
    path = api.new('runner', folder=str(tmp_path), view='side')
    _, dirs = api.pose(path, dirs='all', out=str(tmp_path / 'p.png'))
    assert dirs == ['e', 'w']


def test_invalid_spec_stops_pose_with_a_message(tmp_path, capsys):
    path = _variant(tmp_path, lambda d: d['parts'][next(iter(d['parts']))].update(material='nosuch'))
    with pytest.raises(SystemExit):
        main(['pose', path])
    assert 'unknown material "nosuch"' in capsys.readouterr().err


def test_new_keeps_a_template_made_for_another_view(tmp_path):
    scaffold.init(str(tmp_path / 'g'), mcp=False)  # a top-down project
    folder = str(tmp_path / 'g' / 'art' / 'specs' / 'characters')
    sp = S.load(api.new('runner', template='side_humanoid', folder=folder))
    assert sp['view'] == 'side' and sp['camera']['pitch'] == 0
    with pytest.raises(SpriteKilnError, match='is a side view'):
        api.new('other', template='side_humanoid', folder=folder, view='topdown')


def test_init_normalizes_specs_and_keeps_godot_out_of_specs(tmp_path):
    game = tmp_path / 'g'
    game.mkdir()
    (game / 'project.godot').write_text('config_version=5\n', encoding='utf-8')
    scaffold.init(str(game), engine='godot', specs='./art\\specs', mcp=False)
    assert (game / 'art' / 'specs' / '.gdignore').exists()
    assert 'art/specs/**/out/' in (game / '.gitignore').read_text(encoding='utf-8')


def test_init_reads_mcp_configs_with_a_bom_and_skips_broken_ones(tmp_path):
    pytest.importorskip('mcp')
    game = tmp_path / 'g'
    game.mkdir()
    (game / '.mcp.json').write_bytes(b'\xef\xbb\xbf{"mcpServers": {"other": {"command": "x"}}}')
    (game / '.cursor').mkdir()
    (game / '.cursor' / 'mcp.json').write_text('{"mcpServers": {}, // a comment\n}', encoding='utf-8')
    res = scaffold.init(str(game), ais=['claude', 'cursor'])
    data = json.loads((game / '.mcp.json').read_text(encoding='utf-8'))
    assert set(data['mcpServers']) == {'other', 'spritekiln'}
    assert any('.cursor' in n and 'not plain JSON' in n for n in res['notes'])


def _rendered(tmp_path):
    """The fixture's golden render placed where `render` would write it."""
    spec = stage_spec(tmp_path, MINIMAL)
    out = os.path.join(os.path.dirname(spec), 'out', 'minimal')
    os.makedirs(out)
    for suffix in ('.json', '.png', '_normal.png', '_emissive.png'):
        shutil.copy(os.path.join(GOLDEN, f'render_minimal{suffix}'), os.path.join(out, f'minimal{suffix}'))
    return spec


def test_export_uses_the_project_folder_only_for_its_own_engine(tmp_path, monkeypatch):
    scaffold.init(str(tmp_path / 'u'), engine='unity', mcp=False)
    folder = str(tmp_path / 'u' / 'art' / 'specs' / 'characters')
    spec = os.path.join(folder, 'minimal', 'minimal.yaml')
    shutil.copytree(os.path.dirname(_rendered(tmp_path / 'r')), os.path.dirname(spec))
    shutil.copytree(
        os.path.join(tmp_path, 'r', 'specs', 'palettes'),
        tmp_path / 'u' / 'art' / 'specs' / 'palettes',
        dirs_exist_ok=True,
    )
    w = api.export(spec, 'monogame')
    assert w['dir'].replace('\\', '/').endswith('/Content/sprites/minimal')  # not Unity's Assets/SpriteKiln
    monkeypatch.chdir(tmp_path)
    w = api.export(spec, 'generic', dest='here')
    assert os.path.normcase(w['dir']) == os.path.normcase(str(tmp_path / 'here' / 'minimal'))  # --to is cwd-relative


def test_legacy_export_without_a_project_file_goes_to_godot(monkeypatch):
    monkeypatch.setenv('PXFORGE_GODOT_PROJECT', 'x')
    assert engines.default_engine({}) == 'godot'
    monkeypatch.delenv('PXFORGE_GODOT_PROJECT')
    monkeypatch.delenv('SPRITEKILN_GODOT_PROJECT', raising=False)
    assert engines.default_engine({}) == 'generic' and engines.default_engine({}, legacy=True) == 'godot'


def test_godot_export_folder_must_stay_inside_the_project(tmp_path):
    from spritekiln.godot import _project_path

    project = str(tmp_path / 'game')
    assert _project_path(project, 'res://assets/x/') == 'assets/x'
    assert _project_path(project, os.path.join(project, 'assets', 'y')) == 'assets/y'
    for bad in ('../escaped', str(tmp_path / 'elsewhere')):
        with pytest.raises(ExportError):
            _project_path(project, bad)


def test_partial_render_json_has_no_mirror_without_its_twin(tmp_path):
    path = _variant(tmp_path, lambda d: d.update(mirror=True))
    res = api.render(path, ['idle'], ['s'], jobs=1, out=str(tmp_path / 'out'))
    block = json.loads(open(res['json'], encoding='utf-8').read())['spritekiln']
    assert 'mirrors' not in block and set(block['direction_yaw']) == {'s'}
