"""`spritekiln update`: how SpriteKiln was installed, the version check, and refreshing a project's AI files
without touching its settings or specs. No network: PyPI and the installers are replaced."""

import os
import shutil
import sys

import pytest

from spritekiln import __version__, agents, config, update
from spritekiln.cli import main
from spritekiln.errors import SpriteKilnError


@pytest.fixture
def game(tmp_path, monkeypatch):
    root = tmp_path / 'game'
    root.mkdir()
    main(['init', str(root), '--engine', 'generic', '--ai', 'claude,cursor', '--no-mcp'])
    monkeypatch.chdir(root)
    return root


def _as_old_project(root):
    """Turn a fresh project into one written by 0.1.0: no stamp, no `ai` list, older instructions."""
    os.remove(root / '.spritekiln' / 'version')
    toml = root / 'spritekiln.toml'
    toml.write_text(
        ''.join(ln for ln in toml.read_text(encoding='utf-8').splitlines(True) if not ln.startswith('ai =')),
        encoding='utf-8',
    )
    os.remove(root / '.spritekiln' / 'agent' / 'style.md')
    (root / '.spritekiln' / 'agent' / 'retired.md').write_text('old\n', encoding='utf-8')
    (root / '.claude' / 'skills' / 'spritekiln' / 'SKILL.md').write_text('old\n', encoding='utf-8')
    return toml.read_bytes()


def test_versions_sort():
    k = update.version_key
    assert k('0.2.0') > k('0.1.0') and k('0.10.0') > k('0.9.1') and k('1.0') == k('1.0.0')
    assert k('0.3.0rc1') < k('0.3.0') < k('0.3.0.post1') and k('v0.2.0') == k('0.2.0')


def test_installation_kinds(tmp_path, monkeypatch):
    monkeypatch.setattr(update, '_source_checkout', lambda: False)
    monkeypatch.setattr(update, '_pipx', lambda: ['pipx'])
    monkeypatch.setattr(update, '_launcher', lambda: None)  # pytest.exe is not SpriteKiln's launcher
    monkeypatch.setattr(sys, 'prefix', str(tmp_path))
    monkeypatch.setattr(sys, 'base_prefix', str(tmp_path))
    assert update.installation()['kind'] == 'system' and update.installation()['command'] is None
    monkeypatch.setattr(sys, 'base_prefix', str(tmp_path / 'base'))
    inst = update.installation()
    assert inst['kind'] == 'venv' and inst['command'][:5] == [sys.executable, '-m', 'pip', 'install', '--upgrade']
    (tmp_path / 'uv-receipt.toml').write_text('', encoding='utf-8')
    assert update.installation()['kind'] == 'uv'
    (tmp_path / 'pipx_metadata.json').write_text('{}', encoding='utf-8')
    assert update.installation()['command'] == ['pipx', 'upgrade', 'spritekiln']
    os.remove(tmp_path / 'pipx_metadata.json')
    monkeypatch.setattr(update.shutil, 'which', lambda name: name)
    monkeypatch.setattr(update, 'WINDOWS', False)
    assert update.installation()['command'] == ['uv', 'tool', 'upgrade', 'spritekiln']
    monkeypatch.setattr(update, 'WINDOWS', True)  # uv upgrades the package alone, never the running .exe
    assert update.installation()['command'][:5] == ['uv', 'pip', 'install', '--python', sys.executable]
    os.remove(tmp_path / 'uv-receipt.toml')
    monkeypatch.setattr(update, '_launcher', lambda: str(tmp_path / 'spritekiln.exe'))
    inst = update.installation()  # pip cannot replace the .exe it runs from: python -m spritekiln update
    assert inst['kind'] == 'venv' and inst['command'] is None and 'python -m spritekiln update' in inst['display']
    monkeypatch.setattr(update, '_source_checkout', lambda: True)
    assert update.installation()['kind'] == 'source'


def test_a_failed_upgrade_is_reported(game, monkeypatch):
    monkeypatch.setattr(update, 'latest', lambda: '99.0.0')
    monkeypatch.setattr(update, 'installation', lambda: dict(kind='uv', command=['uv'], display='uv tool upgrade'))
    monkeypatch.setattr(update, 'upgrade', lambda inst: (0, __version__))  # exit 0, but nothing changed
    with pytest.raises(SystemExit):
        main(['update'])


def test_this_checkout_is_a_source_install():
    assert update.installation()['kind'] == 'source'  # tests run on an editable install or the checkout


def test_refresh_an_old_project(game):
    toml = _as_old_project(game)
    assert update.files_version(str(game)) == '<0.2'
    assert 'refresh them with `spritekiln update --files`' in update.stale_note()
    res = update.refresh()
    assert res['ais'] == ['claude', 'cursor']  # found from the files 0.1.0 wrote
    assert (game / 'spritekiln.toml').read_bytes() == toml
    agent_dir = game / '.spritekiln' / 'agent'
    assert sorted(os.listdir(agent_dir)) == sorted(agents.DOCS)  # style.md back, retired.md gone
    assert 'Art style first' in (game / 'AGENTS.md').read_text(encoding='utf-8')
    skill = (game / '.claude' / 'skills' / 'spritekiln' / 'SKILL.md').read_text(encoding='utf-8')
    assert skill.startswith('---\nname: spritekiln') and (game / '.claude/skills/spritekiln/style.md').exists()
    assert update.files_version(str(game)) == __version__ and update.stale_note() is None


def test_commands_note_a_stale_project(game, capsys):
    (game / '.spritekiln' / 'version').write_text('0.1.0\n', encoding='utf-8')
    main(['style'])
    assert 'come from SpriteKiln 0.1.0' in capsys.readouterr().err
    (game / '.spritekiln' / 'version').write_text('99.0.0\n', encoding='utf-8')
    assert 'newer than this one' in update.stale_note()


def test_update_files_needs_a_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SpriteKilnError, match='spritekiln init'):
        update.refresh()


def test_update_runs_the_installer_then_the_new_version(game, monkeypatch, capsys):
    import subprocess

    calls = []

    class Done:
        returncode = 0

    monkeypatch.setattr(update, 'latest', lambda: '99.0.0')
    monkeypatch.setattr(update, 'installation', lambda: dict(kind='pipx', command=['pipx', 'upgrade', 'spritekiln']))
    monkeypatch.setattr(update, 'upgrade', lambda inst: calls.append(inst['command']) or (0, '99.0.0'))
    monkeypatch.setattr(subprocess, 'run', lambda cmd, **kw: calls.append(cmd) or Done())
    main(['update'])
    assert calls == [['pipx', 'upgrade', 'spritekiln'], [sys.executable, '-m', 'spritekiln', 'update', '--files']]
    assert 'the latest on PyPI is 99.0.0' in capsys.readouterr().out
    calls.clear()
    main(['update', '--check'])
    assert calls == [] and 'a new version is available' in capsys.readouterr().out


def test_update_when_up_to_date_refreshes_a_stale_project(game, monkeypatch, capsys):
    _as_old_project(game)
    monkeypatch.setattr(update, 'latest', lambda: __version__)
    main(['update'])
    out = capsys.readouterr().out
    assert 'SpriteKiln is up to date' in out and 'refreshed with SpriteKiln' in out
    main(['update'])
    assert 'AI files are up to date' in capsys.readouterr().out


def test_source_install_is_not_upgraded(game, monkeypatch, capsys):
    monkeypatch.setattr(update, 'latest', lambda: '99.0.0')
    main(['update'])  # this checkout: says how to update it, runs nothing
    assert 'upgrade it with: git pull' in capsys.readouterr().out


def test_godot_addon_follows_the_package(tmp_path, monkeypatch):
    root = tmp_path / 'g'
    root.mkdir()
    (root / 'project.godot').write_text('config_version=5\n', encoding='utf-8')
    main(['init', str(root), '--engine', 'godot', '--ai', 'codex', '--no-mcp'])
    from spritekiln.godot import install_addon

    install_addon(str(root))
    cfg = root / 'addons' / 'spritekiln' / 'plugin.cfg'
    cfg.write_text(cfg.read_text(encoding='utf-8').replace(f'version="{__version__}"', 'version="0.0.1"'), 'utf-8')
    res = update.refresh(str(root))
    assert res['addon']['was'] == '0.0.1' and f'version="{__version__}"' in cfg.read_text(encoding='utf-8')
    assert update.refresh(str(root))['addon'] is None
    assert config.load(str(root))['ai'] == ['codex']
    shutil.rmtree(root / 'addons')
    assert update.refresh(str(root))['addon'] is None  # not installed: left alone


def test_an_upgrade_keeps_the_extras(monkeypatch):
    import importlib.util

    from spritekiln import update

    present = {'mcp', 'numba'}
    monkeypatch.setattr(importlib.util, 'find_spec', lambda name, *a: object() if name in present else None)
    assert update.requirement() == 'spritekiln[mcp,fast]'
