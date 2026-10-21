"""`spritekiln init`, the AI adapters, and the Phase 3 criterion: an empty project + init + an AI other than
Claude (simulated through MCP) makes a character from the template and exports it."""

import json
import os

import pytest

from spritekiln import agents, config
from spritekiln.cli import main


def _project(tmp_path, godot=True):
    game = tmp_path / 'game'
    game.mkdir()
    if godot:
        (game / 'project.godot').write_text('config_version=5\n', encoding='utf-8')
    return game


def test_init_for_codex(tmp_path):
    game = _project(tmp_path)
    main(['init', str(game), '--engine', 'godot', '--ai', 'codex'])
    cfg = config.load(str(game))
    assert cfg['engine'] == 'godot' and cfg['export_dir'] == 'assets/spritekiln'
    assert os.path.samefile(cfg['specs'], game / 'art' / 'specs')
    assert sorted(os.listdir(game / '.spritekiln' / 'agent')) == sorted(agents.DOCS)
    text = (game / 'AGENTS.md').read_text(encoding='utf-8')
    assert agents.BEGIN in text and '.spritekiln/agent/workflow.md' in text
    assert not (game / 'CLAUDE.md').exists() and not (game / '.mcp.json').exists()
    assert 'art/specs/**/out/' in (game / '.gitignore').read_text(encoding='utf-8')
    with pytest.raises(SystemExit):
        main(['init', str(game), '--engine', 'godot'])  # already initialised


def test_init_keeps_existing_files(tmp_path):
    game = _project(tmp_path, godot=False)
    (game / 'AGENTS.md').write_text('# My game\n\nOur own rules.\n', encoding='utf-8')
    (game / '.mcp.json').write_text(json.dumps({'mcpServers': {'other': {'command': 'x'}}}), encoding='utf-8')
    for _ in range(2):  # idempotent
        main(['init', str(game), '--ai', 'all', '--force'])
    text = (game / 'AGENTS.md').read_text(encoding='utf-8')
    assert text.startswith('# My game') and 'Our own rules.' in text and text.count(agents.BEGIN) == 1
    mcp = json.loads((game / '.mcp.json').read_text(encoding='utf-8'))
    assert set(mcp['mcpServers']) == {'other', 'spritekiln'}
    vscode = json.loads((game / '.vscode' / 'mcp.json').read_text(encoding='utf-8'))
    assert vscode['servers']['spritekiln'] == {'type': 'stdio', 'command': 'spritekiln', 'args': ['mcp']}
    for f in (
        'CLAUDE.md',
        'GEMINI.md',
        '.github/copilot-instructions.md',
        '.cursor/rules/spritekiln.mdc',
        '.claude/skills/spritekiln/SKILL.md',
        '.claude/skills/spritekiln/SPEC.md',
        '.claude/agents/pixel-art-director.md',
        '.gemini/settings.json',
        '.cursor/mcp.json',
    ):
        assert (game / f).exists(), f
    assert 'globs: art/specs/**/*.yaml' in (game / '.cursor' / 'rules' / 'spritekiln.mdc').read_text(encoding='utf-8')
    front = (game / '.claude' / 'agents' / 'animator.md').read_text(encoding='utf-8').split('---')[1]
    assert 'model:' not in front  # recommended in the text, never pinned


def test_new_uses_project_defaults(tmp_path, monkeypatch):
    game = _project(tmp_path, godot=False)
    main(['init', str(game)])
    toml = (game / 'spritekiln.toml').read_text(encoding='utf-8')
    toml = toml.replace('size = 64', 'size = 96').replace('scale = 0.04 }', 'scale = 0.05 }')
    (game / 'spritekiln.toml').write_text(toml, encoding='utf-8')
    monkeypatch.chdir(game)
    main(['new', 'hero'])
    from spritekiln import spec as S

    sp = S.load(str(game / 'art' / 'specs' / 'characters' / 'hero' / 'hero.yaml'))
    assert sp['size'] == 96 and sp['camera']['scale'] == 0.05 and sp['camera']['center'] == [0, 0.95, 0]
    assert S.validate(sp) == []


def test_repository_adapters_are_up_to_date():
    assert agents.check_repo() == []


def test_with_cli_rewrites_only_commands():
    text = 'run `spritekiln validate x`, read spritekiln.toml, or `python -m spritekiln` and SpriteKiln'
    assert agents.with_cli(text, 'python -m pxforge') == (
        'run `python -m pxforge validate x`, read spritekiln.toml, or `python -m spritekiln` and SpriteKiln'
    )


mcp = pytest.importorskip('mcp')


def test_phase3_criterion_codex_project_through_mcp(tmp_path):
    """An empty Godot project, `init --ai codex`, then MCP calls as a non-Claude AI would make them."""
    from test_mcp import parts, run

    game = _project(tmp_path)
    main(['init', str(game), '--engine', 'godot', '--ai', 'codex'])

    async def steps(s):
        guide = parts(await s.call_tool('guide', {'topic': 'workflow'}))[0][0]
        spec = parts(await s.call_tool('new', {'name': 'hero'}))[0][0]['spec']
        ok = parts(await s.call_tool('validate', {'spec': spec}))[0][0]['ok']
        pose = parts(await s.call_tool('pose', {'spec': spec, 'dirs': 's', 'scale': 1}))[1]
        rendered = parts(await s.call_tool('render', {'spec': spec, 'anims': 'idle', 'dirs': 's,e', 'jobs': 1}))[0][0]
        exported = parts(await s.call_tool('export', {'spec': spec}))[0][0]
        return guide, spec, ok, pose, rendered, exported

    guide, spec, ok, pose, rendered, exported = run(game, steps)
    assert guide.startswith('# Working with SpriteKiln')
    assert spec.replace('\\', '/').endswith('art/specs/characters/hero/hero.yaml') and ok
    assert pose and pose[0].startswith(b'\x89PNG')
    assert rendered['qa']['ok'] and rendered['frames'] == 12
    assert exported['engine'] == 'godot' and exported['res'] == 'res://assets/spritekiln/hero'
    assert (game / 'assets' / 'spritekiln' / 'hero' / 'hero.tscn').exists()
    assert (game / 'addons' / 'spritekiln' / 'kiln_sprite_2d.gd').exists()
