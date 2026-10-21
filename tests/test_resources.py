import os

from spritekiln import resources
from spritekiln import spec as S
from spritekiln.cli import main


def test_builtin_palettes_and_templates():
    assert resources.builtin_palette('gothic').endswith('gothic.yaml')
    assert resources.builtin_palette('gothic.yaml') == resources.builtin_palette('gothic')
    assert resources.builtin_palette('../../palettes/props.yaml').endswith('props.yaml')
    assert resources.builtin_palette('nope') is None
    assert 'humanoid' in resources.templates()
    assert os.path.exists(os.path.join(resources.data_dir('godot_addon'), 'px_sprite_2d.gd'))


def test_new_spec_from_template_is_valid_anywhere(tmp_path):
    main(['new', 'hero', '--dir', str(tmp_path)])
    path = tmp_path / 'hero' / 'hero.yaml'
    text = path.read_text(encoding='utf-8')
    assert 'name: hero' in text and 'palette: gothic' in text
    assert S.validate(S.load(str(path))) == []
