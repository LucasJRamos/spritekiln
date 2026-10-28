"""Design 11: the project style drives every asset's look at render time; a spec or a material can override it."""

import os

import numpy as np
import pytest
from PIL import Image

from spritekiln import config, pipeline, style
from spritekiln import spec as S
from spritekiln.cli import main
from spritekiln.errors import SpriteKilnError
from spritekiln.pixelize import hx
from spritekiln.rig import rest_env

from conftest import FIXTURES, assert_image_matches, stage_spec

MINIMAL = os.path.join(FIXTURES, 'minimal', 'minimal.yaml')
BALL = """spritekiln: 1
name: ball
kind: prop
size: 40
camera: {pitch: 38, scale: 0.05, center: [0, 0.5, 0]}
shadow: null
ramps:
  stone: ["#14121c", "#2e3040", "#4c5068", "#6b7390", "#8d96b0", "#b3bbd0", "#dfe4f0"]
materials:
  stone: {ramp: stone}
channels:
  x: 0
bones:
  body: {parent: root, pos: "[x, 0.5, 0]"}
parts:
  ball:
    material: stone
    space: body
    prims: [{sphere: {c: [0, 0, 0], r: 0.6}}]
"""


@pytest.fixture
def game(tmp_path, monkeypatch):
    root = tmp_path / 'game'
    root.mkdir()
    main(['init', str(root), '--engine', 'generic', '--ai', 'claude', '--no-mcp'])
    monkeypatch.chdir(root)
    return root


def _write(folder, text, name='ball'):
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f'{name}.yaml'
    p.write_text(text, encoding='utf-8')
    return str(p)


def _img(sp, yaw=0.0, **env):
    e = dict(rest_env(sp, yaw), **env)
    return pipeline.render_frame(sp, e, yaw, maps=False).img


def test_without_a_style_nothing_changes(tmp_path):
    sp = S.load(stage_spec(tmp_path, MINIMAL))
    assert sp['render'] == S.RENDER and sp['light'] == S.DEFAULT_LIGHT
    body = sp['materials']['body']
    assert body['outline'] and body['line'] and body['crease'] is None
    assert body['dither'] is None and body['line_color'] is None and body['bands'] is None


def test_the_project_style_reaches_every_spec_and_the_spec_wins(game):
    style.record(dict(outline='none', lines='none', light='dramatic', shading='flat'))
    folder = game / 'art' / 'specs' / 'props' / 'ball'
    sp = S.load(_write(folder, BALL))
    stone = sp['materials']['stone']
    assert not stone['outline'] and not stone['line'] and stone['bands'] == [5, 6]
    assert sp['light']['dir'] == S.LIGHTS['dramatic']['dir'] and sp['light']['ambient'] == 0.03
    assert str(game / 'spritekiln.toml') in sp['_files']  # a long-running server notices a new style
    own = BALL.replace('shadow: null', 'shadow: null\nrender: {outline: dark}\nlight: {ambient: 0.2}')
    own = own.replace('stone: {ramp: stone}', 'stone: {ramp: stone, bands: [1, 5], line: true}')
    sp = S.load(_write(folder, own))
    stone = sp['materials']['stone']
    assert stone['outline'] and stone['line_color'] == '#14121c'  # the spec's render: block wins
    assert stone['line'] and stone['bands'] == [1, 5]  # the material's own fields win
    assert sp['light']['ambient'] == 0.2 and sp['light']['dir'] == S.LIGHTS['dramatic']['dir']
    off = style.status()['off_style']
    assert off[0]['spec'] == 'art/specs/props/ball/ball.yaml' and off[0]['differs']['outline'] == ['dark', 'none']


def test_shading_presets_pick_tones():
    ramp = ['#000000', '#222222', '#444444', '#666666', '#888888', '#aaaaaa']
    own = dict(a={}, b={'finish': 'metal'}, c={'bands': [1, 2]})

    def load(shading):
        out = {}
        for name, m in own.items():
            mm = dict(S.DEFAULT_MATERIAL, **m, colors=ramp)
            mm['highlight'] = S.FINISHES['metal']['highlight'] if m.get('finish') else None
            S._shading(mm, m, shading)
            out[name] = (mm['bands'], mm['thresholds'])
        return out

    assert load('soft') == {'a': (None, None), 'b': (None, None), 'c': ([1, 2], None)}
    assert load('flat') == {'a': ([4, 5], None), 'b': ([3, 4], None), 'c': ([1, 2], None)}  # b: highlight on top
    assert load('toon') == {'a': ([3, 5], [0.3, 0.6]), 'b': ([2, 4], [0.3, 0.6]), 'c': ([1, 2], None)}


def test_outline_modes(tmp_path):
    red = BALL.replace('ramps:', 'ramps:\n  red: ["#2a0408", "#7a1a28", "#c0303a"]')  # darker than stone by luma
    path = _write(tmp_path / 'ball', red.replace('materials:', 'materials:\n  red: {ramp: red}'))
    sel = _img(S.load(path))
    none = _img(S.load(path, style={'outline': 'none'}))
    ring = (sel[..., 3] > 0) & (none[..., 3] == 0)
    assert ring.sum() > 40 and (none[..., 3] > 0).sum() < (sel[..., 3] > 0).sum()
    assert {tuple(c) for c in sel[ring][:, :3]} == {hx('#14121c')}
    dark = _img(S.load(path, style={'outline': 'dark'}))
    assert {tuple(c) for c in dark[ring][:, :3]} == {hx('#14121c')}  # the near-black, not the dark red
    dark = _img(S.load(path, style={'outline': 'dark', 'outline_color': '#050505'}))
    assert {tuple(c) for c in dark[ring][:, :3]} == {(5, 5, 5)}
    colored = _img(S.load(path, style={'outline': 'colored'}))
    assert {tuple(c) for c in colored[ring][:, :3]} == {hx('#2e3040')}  # the line tone (line_band 1)


def test_dither_mixes_tones_and_moves_with_the_part(tmp_path):
    sp = S.load(_write(tmp_path / 'ball', BALL), style={'dither': 'bayer2'})
    plain = _img(S.load(_write(tmp_path / 'plain', BALL)))
    a = _img(sp)
    changed = (a != plain).any(-1)
    assert 10 < changed.sum() < 0.4 * (a[..., 3] > 0).sum()  # only near the borders between tones
    b = _img(sp, x=0.1)  # the ball 2 px to the right: the same picture, pattern included
    assert np.array_equal(b[:, 2:], a[:, :-2])


def test_snap_from_the_style(game):
    style.record(dict(snap='yes'))
    main(['new', 'hero'])
    sp = S.load(str(game / 'art' / 'specs' / 'characters' / 'hero' / 'hero.yaml'))
    assert sp['snap'] == ['root', 'torso_rot']
    folder = game / 'art' / 'specs' / 'props' / 'ball'
    assert S.load(_write(folder, BALL))['snap'] == ['root']
    assert S.load(_write(folder, BALL + 'snap: [body]\n'))['snap'] == ['body']


def test_record_the_look_fields(game, capsys):
    res = style.record(
        dict(
            outline='dark',
            outline_color='#101018',
            shading='toon',
            lines='depth+normal',
            highlights='no',
            dither='bayer4',
            light='top',
            snap='yes',
        )
    )
    st = config.load()['style']
    assert st['highlights'] is False and st['snap'] is True and st['light'] == 'top'
    assert 'lines' not in res['defaulted'] and 'proportions' in res['defaulted']
    text = '\n'.join(style.describe(st))
    assert 'dark (#101018)' in text and 'toon; lines depth+normal; highlights no; dither bayer4' in text
    assert 'snapped to whole pixels' in text
    for answers, message in [
        (dict(light='neon'), 'light'),
        (dict(outline_color='black'), 'outline_color'),
        (dict(snap='maybe'), 'snap'),
    ]:
        with pytest.raises(SpriteKilnError, match=message):
            style.record(answers)
    main(['style', 'set', '--dither', 'none', '--outline', 'colored'])
    st = config.load()['style']
    assert st['dither'] == 'none' and st['outline'] == 'colored' and st['light'] == 'top'


def test_a_style_recorded_before_the_look_fields(game):
    (game / 'spritekiln.toml').write_text(
        (game / 'spritekiln.toml').read_text(encoding='utf-8')
        + '\n[style]\nview = "topdown"\nheight = 44\nscale = 0.04\nsize = 64\ndirections = 8\nmirror = false\n'
        'palette = "gothic"\noutline = "dark"\nshading = "soft"\nproportions = "stylized"\nanimation = "fluid"\n',
        encoding='utf-8',
    )
    sp = S.load(_write(game / 'art' / 'specs' / 'props' / 'ball', BALL))
    assert sp['render']['outline'] == 'dark' and sp['render']['lines'] == 'depth'
    assert 'lines depth' in '\n'.join(style.describe(config.load()['style']))
    style.record(dict(light='soft'))
    st = config.load()['style']
    assert st['outline'] == 'dark' and st['light'] == 'soft' and st['lines'] == 'depth' and st['highlights'] is True


def test_a_bad_value_names_where_it_comes_from(game):
    path = _write(game / 'art' / 'specs' / 'props' / 'ball', BALL + 'render: {shading: gouache}\n')
    with pytest.raises(SpriteKilnError, match="shading 'gouache' in render: use one of soft, flat, toon"):
        S.load(path)


def test_style_preview(game, capsys):
    path = _write(game / 'art' / 'specs' / 'props' / 'ball', BALL)
    out = str(game / 'preview.png')
    main(['style', 'preview', path, '--field', 'outline', '--field', 'light', '--dir', 's', '-o', out])
    text = capsys.readouterr().out
    assert 'outline     selective *, dark, colored, none' in text and 'light       classic *, top' in text
    w, h = Image.open(out).size
    assert w < 1536 and h < 1536 and w * h <= 1_150_000
    with pytest.raises(SystemExit):
        main(['style', 'show', path])
    assert 'only `style preview` takes a spec' in capsys.readouterr().err


def test_each_choice_renders_like_its_golden(tmp_path, update_golden):
    """The minimal fixture under every choice of the look fields, one row per field (se, rest pose)."""
    path = stage_spec(tmp_path, MINIMAL)
    rows = []
    for field in style.PREVIEW_FIELDS:
        choices = [True, False] if field == 'highlights' else style.CHOICES[field]
        rows.append(np.concatenate([_img(S.load(path, style={field: c}), 45.0) for c in choices], 1))
    width = max(r.shape[1] for r in rows)
    sheet = np.concatenate([np.pad(r, ((0, 0), (0, width - r.shape[1]), (0, 0))) for r in rows], 0)
    out = str(tmp_path / 'minimal_styles.png')
    Image.fromarray(sheet).save(out)
    assert_image_matches(out, 'minimal_styles.png', update_golden)
