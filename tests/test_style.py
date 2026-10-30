"""The project's art style: `spritekiln style` records the interview's answers in spritekiln.toml, turns the
numeric ones into defaults for `new`, and keeps them through `init --force`."""

import datetime

import pytest

from spritekiln import config, style
from spritekiln.cli import main
from spritekiln.errors import SpriteKilnError

DAY = datetime.date(2026, 10, 25)


@pytest.fixture
def game(tmp_path, monkeypatch):
    root = tmp_path / 'game'
    root.mkdir()
    main(['init', str(root), '--engine', 'generic', '--ai', 'claude', '--no-mcp'])
    monkeypatch.chdir(root)
    return root


def test_density_and_frame_from_height():
    assert style.camera_scale('topdown', 44) == 0.04  # the template humanoid at the default density
    assert style.height_for('topdown', 0.04) == 44
    assert style.camera_scale('side', 50) == 0.04
    assert [style.frame_size(h) for h in (24, 32, 44, 48, 64, 96)] == [32, 48, 64, 64, 96, 128]
    with pytest.raises(SpriteKilnError):
        style.frame_size(500)


def test_nothing_recorded_after_init(game, capsys):
    st = style.status()
    assert not st['recorded'] and st['guide'] == '.spritekiln/agent/style.md'
    assert st['suggested']['height'] == 44 and st['suggested']['source'] == 'the project defaults'
    main(['style'])
    out = capsys.readouterr().out
    assert 'No art style is recorded' in out and '--height 44' in out
    main(['new', 'hero'])
    assert 'no art style recorded' in capsys.readouterr().err


def test_record_sets_defaults_for_new_specs(game, capsys):
    res = style.record(
        dict(height=48, outline='dark', references='Hyper Light Drifter', notes='no blood; "heroes" read far'),
        today=DAY,
    )
    assert res['recorded'] and 'shading' in res['defaulted'] and 'scale' not in res['defaulted']
    cfg = config.load()
    st = cfg['style']
    assert st['recorded'] == DAY and st['height'] == 48 and st['scale'] == 0.03667 and st['size'] == 64
    assert st['outline'] == 'dark' and st['shading'] == 'soft' and st['references'] == ['Hyper Light Drifter']
    assert st['notes'] == 'no blood; "heroes" read far'
    assert cfg['defaults']['camera'] == {'pitch': 38, 'scale': 0.03667} and cfg['defaults']['size'] == 64
    assert cfg['engine'] == 'generic' and cfg['ai'] == ['claude']  # the other tables stay
    text = (game / 'spritekiln.toml').read_text(encoding='utf-8')
    assert '# where `spritekiln new` creates specs' in text and text.count('[style]') == 1
    main(['new', 'hero'])
    assert 'no art style' not in capsys.readouterr().err
    from spritekiln import spec as S

    sp = S.load(str(game / 'art' / 'specs' / 'characters' / 'hero' / 'hero.yaml'))
    assert sp['camera']['scale'] == 0.03667 and sp['size'] == 64 and style.status()['off_style'] == []


def test_change_only_what_the_user_asks(game, capsys):
    main(['style', 'set', '--height', '48', '--palette', 'gothic'])
    main(['new', 'hero'])
    before = config.load()['style']
    main(['style', 'set', '--outline', 'none'])
    after = config.load()['style']
    assert after['outline'] == 'none'
    assert {k: v for k, v in after.items() if k not in ('outline', 'recorded')} == {
        k: v for k, v in before.items() if k not in ('outline', 'recorded')
    }
    capsys.readouterr()
    main(['style', 'set', '--height', '32'])
    out = capsys.readouterr().out
    st = config.load()['style']
    assert st['scale'] == 0.055 and st['size'] == 48
    assert '1 spec(s) do not match' in out and 'hero.yaml: scale 0.03667 (style: 0.055)' in out


def test_side_view_and_directions(game):
    style.record(dict(view='side', height=50))
    cfg = config.load()
    assert cfg['style']['directions'] == 2 and cfg['style']['scale'] == 0.04
    assert cfg['defaults']['view'] == 'side' and cfg['defaults']['camera']['pitch'] == 0
    assert 'directions' not in cfg['defaults']
    with pytest.raises(SpriteKilnError, match='a side view has 2'):
        style.record(dict(directions=8))
    style.record(dict(view='topdown', directions=4, mirror='yes'))
    d = config.load()['defaults']
    assert d['view'] == 'topdown' and d['camera']['pitch'] == 38 and d['directions'] == 4 and d['mirror'] is True


def test_existing_specs_suggest_the_answers(game):
    main(['new', 'old_hero'])  # made before the style existed: scale 0.04, size 64
    s = style.status()['suggested']
    assert s['source'] == '1 existing spec(s)' and s['height'] == 44 and s['scale'] == 0.04
    style.record(dict(height=44, outline='selective'))  # the suggested height keeps the existing density
    assert config.load()['style']['scale'] == 0.04 and style.status()['off_style'] == []


def test_bad_answers_are_refused(game):
    for answers, message in [
        (dict(outline='thick'), 'outline'),
        (dict(height=4), 'height 4'),
        (dict(mirror='maybe'), 'mirror'),
        (dict(colour='red'), 'unknown style field'),
    ]:
        with pytest.raises(SpriteKilnError, match=message):
            style.record(answers)
    assert not config.load()['style']  # nothing was written


def test_init_force_keeps_the_style(game):
    style.record(dict(height=48, proportions='chibi'))
    main(['init', str(game), '--engine', 'godot', '--ai', 'claude,cursor', '--force', '--no-mcp'])
    cfg = config.load()
    assert cfg['engine'] == 'godot' and cfg['ai'] == ['claude', 'cursor']
    assert cfg['style']['proportions'] == 'chibi' and cfg['defaults']['camera']['scale'] == 0.03667


def test_style_needs_a_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SpriteKilnError, match='spritekiln init'):
        style.status()
    assert style.missing_note() is None


def test_set_tables_keeps_the_rest_of_the_file(tmp_path):
    path = tmp_path / 'spritekiln.toml'
    path.write_text(
        '# my notes\n[project]\nengine = "godot"  # mine\n\n[defaults]\nsize = 96\n\n[defaults.camera]\n'
        'pitch = 38\n\n[extra]\ntext = """\n[style]\nnot a table\n"""\n',
        encoding='utf-8',
    )
    config.set_tables(str(path), {'defaults': {'size': 64, 'camera': {'pitch': 38, 'scale': 0.04}}, 'style': {}})
    text = path.read_text(encoding='utf-8')
    data = config.read(str(path))
    assert text.startswith('# my notes\n') and 'engine = "godot"  # mine' in text
    assert data['defaults'] == {'size': 64, 'camera': {'pitch': 38, 'scale': 0.04}}
    assert data['extra']['text'] == '[style]\nnot a table\n' and data['style'] == {}


def test_style_through_mcp(game):
    pytest.importorskip('mcp')
    from test_mcp import parts, run

    async def steps(s):
        made = parts(await s.call_tool('new', {'name': 'scout'}))[0][0]
        before = parts(await s.call_tool('style', {}))[0][0]
        answers = {'height': 48, 'outline': 'dark', 'mirror': 'no', 'references': ['Blasphemous']}
        after = parts(await s.call_tool('style', {'answers': answers}))[0][0]
        guide = parts(await s.call_tool('guide', {'topic': 'style'}))[0][0]
        return made, before, after, guide

    made, before, after, guide = run(game, steps)
    assert 'no art style recorded' in made['note']
    assert not before['recorded'] and 'interview the user' in before['next']
    assert after['recorded'] and after['style']['scale'] == 0.03667 and after['style']['recorded']
    assert after['off_style'][0]['spec'] == 'art/specs/characters/scout/scout.yaml'
    assert guide.startswith("# The project's art style")


def test_init_force_repairs_a_broken_file(tmp_path):
    root = tmp_path / 'g'
    root.mkdir()
    (root / 'spritekiln.toml').write_text('[project\nbroken', encoding='utf-8')
    main(['init', str(root), '--force', '--no-mcp'])
    assert config.load(str(root))['engine'] == 'generic'


def test_the_face_question(game):
    """Design 16: how much face a character shows; minimal is the default."""
    style.record(dict(height=48))
    assert config.load()['style']['face'] == 'minimal'
    style.record(dict(face='simple'))
    assert config.load()['style']['face'] == 'simple'
    assert any(line.split() == ['face', 'simple'] for line in style.describe(config.load()['style']))
    with pytest.raises(SpriteKilnError, match='face'):
        style.record(dict(face='photoreal'))
