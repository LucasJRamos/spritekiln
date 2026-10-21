"""`spritekiln init`: set up a game project for SpriteKiln and for the coding AI that will drive it."""

import os

from . import agents, config
from .errors import SpriteKilnError

DOCS_DIR = '.spritekiln/agent'


def init(
    root,
    engine='generic',
    ais=('generic',),
    specs='art/specs',
    export_dir=None,
    godot_project=None,
    mcp=True,
    force=False,
    view='topdown',
):
    """Write spritekiln.toml, the specs folder, the AI instructions and MCP client configs. Returns what was
    written (paths) and notes for the user."""
    if engine not in config.ENGINES:
        raise SpriteKilnError(f'--engine {engine}: use one of {", ".join(config.ENGINES)}')
    root = os.path.abspath(root)
    os.makedirs(root, exist_ok=True)
    toml = os.path.join(root, config.FILENAME)
    if os.path.exists(toml) and not force:
        raise SpriteKilnError(f'{toml} already exists (use --force to rewrite it; specs are never touched)')
    notes = []
    if engine == 'godot':
        godot_project = godot_project or '.'
        if not os.path.exists(os.path.join(root, godot_project, 'project.godot')):
            notes.append(
                f'no project.godot in {os.path.join(root, godot_project)} yet: set export.godot_project '
                f'in {config.FILENAME} if the Godot project lives elsewhere'
            )
    with open(toml, 'w', encoding='utf-8', newline='\n') as fh:
        defaults = {
            'view': view,
            'size': 64,
            'palette': 'gothic',
            'camera': {'pitch': 0 if view == 'side' else 38, 'scale': 0.04},
        }
        fh.write(config.render(engine, specs, export_dir, godot_project or '.', defaults))
    written = [toml]
    for sub in ('characters', 'props', 'palettes'):
        os.makedirs(os.path.join(root, specs, sub), exist_ok=True)
    agents.write_docs(os.path.join(root, DOCS_DIR))
    written.append(os.path.join(root, DOCS_DIR))
    ais = agents.install(root, ais, DOCS_DIR, specs_glob=f'{specs.rstrip("/")}/**/*.yaml')
    written += [os.path.join(root, f) for f in _adapter_files(ais) if os.path.exists(os.path.join(root, f))]
    if mcp:
        written += agents.write_mcp_configs(root, ais)
        if 'codex' in ais:
            notes.append(
                'Codex reads MCP servers from ~/.codex/config.toml: add [mcp_servers.spritekiln] with '
                'command = "spritekiln" and args = ["mcp"]'
            )
    written.append(_gitignore(root, specs))
    return dict(root=root, engine=engine, ais=ais, written=written, notes=notes)


def _adapter_files(ais):
    files = ['AGENTS.md']
    if 'claude' in ais:
        files += ['CLAUDE.md', '.claude/skills', '.claude/agents']
    if 'gemini' in ais:
        files.append('GEMINI.md')
    if 'copilot' in ais:
        files.append('.github/copilot-instructions.md')
    if 'cursor' in ais:
        files.append('.cursor/rules/spritekiln.mdc')
    return files


def _gitignore(root, specs):
    """Keep renders and caches out of the game's repository (only the exported files belong there)."""
    path = os.path.join(root, '.gitignore')
    base = specs.strip('/').replace(os.sep, '/')
    lines = [f'{base}/**/out/', f'{base}/**/.kilncache/', f'{base}/**/*_ref/']
    have = open(path, encoding='utf-8').read().splitlines() if os.path.exists(path) else []
    missing = [ln for ln in lines if ln not in have]
    if missing:
        with open(path, 'a', encoding='utf-8', newline='\n') as fh:
            if have and have[-1].strip():
                fh.write('\n')
            fh.write('# SpriteKiln: renders and caches are regenerated; exported files live in the engine folder\n')
            fh.write('\n'.join(missing) + '\n')
    return path
