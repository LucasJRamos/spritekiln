"""Instructions for coding AIs, generated from one source: docs/agent/*.md.

Adapters: AGENTS.md (Codex, Cursor, Copilot, Gemini CLI, Aider...), CLAUDE.md + .claude/skills + .claude/agents
(Claude Code), GEMINI.md, .github/copilot-instructions.md and .cursor/rules/spritekiln.mdc. Files a project
already has only get a marked block (`<!-- spritekiln:begin -->` ... `<!-- spritekiln:end -->`); files that
belong to SpriteKiln (skills, agents, the Cursor rule) are written whole.

    python -m spritekiln.agents          # regenerate this repository's adapters
    python -m spritekiln.agents --check  # fail if they are out of date (CI)
"""

import json
import os
import re
import shutil
import sys

from . import resources

DOCS = ['workflow.md', 'spec.md', 'modeling.md', 'splash-to-model.md', 'animation.md', 'art-direction.md', 'recipe.md']
AIS = ('claude', 'codex', 'cursor', 'copilot', 'gemini', 'generic')
BEGIN = '<!-- spritekiln:begin (generated from docs/agent by spritekiln; edit the sources, not this block) -->'
END = '<!-- spritekiln:end -->'
_COMMANDS = 'validate|pose|render|review|export|ref|palette|new|cache|init|mcp|godot'

SKILLS = {
    'spritekiln': dict(
        description='Create and edit characters, monsters and props as animated 8-direction pixel art (top-down 3/4) '
        'with SpriteKiln (procedural SDF model in YAML -> render -> pixel art). Use for any request about a sprite, '
        'animation, spritesheet, pose, direction, palette or visual fix of an asset made with it.',
        body=['workflow.md', 'modeling.md'],
    ),
    'spritekiln-splash-to-model': dict(
        description='Turn an original splash or concept art into a SpriteKiln model (spec YAML) faithful to the art '
        'and legible at 64 px in 8 directions. Use when the user provides a character image and asks for its model, '
        'sprite or animations.',
        body=['splash-to-model.md'],
    ),
    'spritekiln-animation': dict(
        description='Write and tune SpriteKiln animations (idle, walk, run, attack, hit, death, cast) with sound '
        'principles for small pixel art in 8 directions: per-frame timing, anticipation, smears, seamless loops, '
        'gameplay events, timing targets and sockets. Use for any animation of a SpriteKiln spec.',
        body=['animation.md'],
    ),
}
LEGACY_SKILLS = {
    'pxforge': 'spritekiln',
    'pxforge-splash-to-model': 'spritekiln-splash-to-model',
    'pxforge-animation': 'spritekiln-animation',
}
AGENT_ROLES = {
    'character-modeler': dict(
        description='Models characters, monsters and props in SpriteKiln from a brief or a splash art: writes the '
        'spec geometry, skeleton, materials and palette and iterates with pose/ref compare until the silhouette '
        'is faithful and legible in 8 directions. Use to create a model or change how an asset looks.',
        tools='Read, Write, Edit, Bash, Glob, Grep',
        role='You are the character modeler. You work only on the spec YAML of the requested asset.',
        read=['SKILL.md', 'SPEC.md', '../spritekiln-splash-to-model/SKILL.md'],
        skill='spritekiln',
        section=('modeling.md', '## Rules for a modeler'),
    ),
    'animator': dict(
        description='Creates and refines SpriteKiln animations (idle, walk, run, attack, hit, death, cast...) with '
        'per-frame timing, anticipation, smears, overlap, gameplay events and timing targets, checked in 8 '
        'directions. Use for movement, timing or a new animation of an existing spec.',
        tools='Read, Write, Edit, Bash, Glob, Grep',
        role='You are the animator. You change `animations:` (and, for a new degree of freedom, `channels:` and the '
        'expression that uses it).',
        read=['SKILL.md', 'SPEC.md'],
        skill='spritekiln-animation',
        section=('animation.md', '## Rules for an animator'),
    ),
    'pixel-art-director': dict(
        description='Pixel-art director. Reviews contact sheets, GIFs, splash comparison sheets, review reports and '
        'qa.json of a SpriteKiln asset and returns a prioritised list of concrete fixes (which part/channel/key to '
        'change and how). Does not edit files. Use after a render or a ref compare, before calling an asset done.',
        tools='Read, Bash, Glob, Grep',
        role='You are a demanding art director for top-down pixel art (64-96 px, 8 directions). You never edit '
        'files: you analyse and recommend.',
        read=['SPEC.md'],
        skill='spritekiln',
        section=('art-direction.md', None),
    ),
}


# ---------------------------------------------------------------- text helpers


def source(name):
    with open(os.path.join(resources.data_dir('agent'), name), encoding='utf-8') as fh:
        return fh.read()


def with_cli(text, cli):
    """Use another command than `spritekiln` (e.g. `python -m pxforge`) in examples."""
    return text if cli == 'spritekiln' else re.sub(rf'\bspritekiln (?=(?:{_COMMANDS})\b)', cli + ' ', text)


def _drop_title(text):
    return re.sub(r'\A# .*\n+', '', text)


def _section(text, heading):
    """The part of a markdown text from `heading` to the next heading of the same level (or the end)."""
    i = text.index(heading)
    level = heading.split(' ')[0]
    m = re.search(rf'^{level} ', text[i + len(heading) :], re.M)
    return text[i : i + len(heading) + m.start()] if m else text[i:]


def _skill_links(text):
    """Links between docs, as seen from a skill folder (the spec reference is SPEC.md there)."""
    return text.replace('(spec.md)', '(SPEC.md)')


def essentials(docs, cli='spritekiln', engine_note=True):
    """The short block every AI gets: what SpriteKiln is, the rules that matter, where the knowledge lives."""
    d = docs.rstrip('/')
    text = f"""## SpriteKiln assets
Sprites in this project are made with SpriteKiln: a YAML spec (skeleton, SDF primitives, materials, palette,
animations) is rendered into animated 8-direction pixel art (atlas + JSON + normal/emissive maps).

Read before working on an asset: `{d}/workflow.md` (commands and the working loop) and `{d}/spec.md` (the spec
format). Then, as needed: `{d}/modeling.md`, `{d}/splash-to-model.md`, `{d}/animation.md`,
`{d}/art-direction.md` and `{d}/recipe.md` (the modeler → art director → animator recipe).

Rules that matter:
- Run `spritekiln validate <spec>` after every edit; problems come with file:line:column.
- Iterate with `spritekiln pose <spec> --dirs all` (about 1 s per direction); `spritekiln render` only at the end.
- Never call something visual good without looking at the PNG. If you cannot see images, use the numbers of
  `spritekiln review` (value, contrast, pixels per material, IoU) and `qa.json`.
- Keep the camera pitch, light and `camera.scale` shared by every asset of the game.
- Outputs under `out/` are generated: never edit them.
"""
    if engine_note:
        text += '- `spritekiln export <spec>` hands a render to the engine configured in `spritekiln.toml`.\n'
    text += '- With an MCP client, `spritekiln mcp` serves these operations as tools that return images and JSON.\n'
    return with_cli(text, cli)


def upsert(path, block, title=None):
    """Write `block` between the markers in `path`, keeping everything else; create the file when missing."""
    content = f'{BEGIN}\n{block.rstrip()}\n{END}\n'
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        if BEGIN.split(' (')[0] in text and END in text:
            start = text.index(BEGIN.split(' (')[0])
            end = text.index(END) + len(END)
            text = text[:start] + content.rstrip('\n') + text[end:]
        else:
            text = text.rstrip('\n') + '\n\n' + content
    else:
        text = (f'# {title}\n\n' if title else '') + content
    _write(path, text)


def _write(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


# ---------------------------------------------------------------- adapters


def write_docs(target):
    """Copy the knowledge files (docs/agent) to `target` (used in game projects by `init`)."""
    for name in DOCS:
        _write(os.path.join(target, name), source(name))


def _skill_files(base):
    """Reference files copied next to a skill's SKILL.md: every doc its body does not already contain, so the
    folder is self-contained (projects may link to the folder alone)."""
    return [('SPEC.md' if n == 'spec.md' else n, n) for n in DOCS if n not in SKILLS[base]['body']]


def write_claude(root, docs, cli='spritekiln', names=None, extra_note='', agents=True, claude_md=True):
    """Claude Code: skills (self-contained folders), agents and a CLAUDE.md block."""
    names = names or {k: k for k in SKILLS}
    for out_name, base in names.items():
        meta = SKILLS[base]
        folder = os.path.join(root, '.claude', 'skills', out_name)
        body = '\n\n'.join(_drop_title(source(n)).strip() for n in meta['body'])
        title = source(meta['body'][0]).splitlines()[0]
        desc = meta['description'] + extra_note
        others = ', '.join(f'[{t}]({t})' for t, _ in _skill_files(base))
        skill = (
            f'---\nname: {out_name}\ndescription: {desc}\n---\n\n{title}\n\n{body}\n\n'
            f'## More\nReference files in this folder: {others}.\n'
        )
        _write(os.path.join(folder, 'SKILL.md'), with_cli(_skill_links(skill), cli))
        for target, n in _skill_files(base):
            _write(os.path.join(folder, target), with_cli(_skill_links(source(n)), cli))
    if not agents:
        return
    for name, meta in AGENT_ROLES.items():
        skill_dir = f'.claude/skills/{meta["skill"]}'
        reads = ', '.join(
            f'`{os.path.normpath(os.path.join(skill_dir, r)).replace(os.sep, "/")}`' for r in meta['read']
        )
        doc, heading = meta['section']
        rules = _section(source(doc), heading) if heading else _drop_title(source(doc))
        text = (
            f'---\nname: {name}\ndescription: {meta["description"]}\ntools: {meta["tools"]}\n---\n\n'
            f'{meta["role"]}\n\nRead {reads} before starting.\n\n'
            'Recommended model: the strongest one available to you, with image input; this work rewards '
            'visual judgement.\n\n'
            f'{_skill_links(rules).strip()}\n'
        )
        _write(os.path.join(root, '.claude', 'agents', f'{name}.md'), with_cli(text, cli))
    if not claude_md:
        return
    block = essentials(docs, cli) + (
        '\nClaude Code: skills `spritekiln`, `spritekiln-splash-to-model`, `spritekiln-animation`; agents '
        '`character-modeler`, `animator`, `pixel-art-director` (see `recipe.md` for the order).\n'
    )
    upsert(os.path.join(root, 'CLAUDE.md'), with_cli(block, cli))


def write_agents_md(root, docs, cli='spritekiln'):
    upsert(os.path.join(root, 'AGENTS.md'), essentials(docs, cli), title='Agent instructions')


def write_gemini(root, docs, cli='spritekiln'):
    upsert(os.path.join(root, 'GEMINI.md'), essentials(docs, cli))


def write_copilot(root, docs, cli='spritekiln'):
    upsert(os.path.join(root, '.github', 'copilot-instructions.md'), essentials(docs, cli))


def write_cursor(root, docs, cli='spritekiln', specs_glob='**/*.yaml'):
    text = (
        f'---\ndescription: Making and editing SpriteKiln sprites (YAML specs -> 8-direction pixel art)\n'
        f'globs: {specs_glob}\nalwaysApply: false\n---\n\n{essentials(docs, cli)}'
    )
    _write(os.path.join(root, '.cursor', 'rules', 'spritekiln.mdc'), text)


def install(root, ais, docs, cli='spritekiln', specs_glob='**/*.yaml'):
    """Write the adapters for `ais` (any of AIS; 'all' for every one). AGENTS.md is always written."""
    ais = list(AIS) if 'all' in ais else list(ais)
    unknown = [a for a in ais if a not in AIS]
    if unknown:
        from .errors import SpriteKilnError

        raise SpriteKilnError(f'unknown AI {unknown} (use {", ".join(AIS)} or all)')
    write_agents_md(root, docs, cli)
    if 'claude' in ais:
        write_claude(root, docs, cli)
    if 'gemini' in ais:
        write_gemini(root, docs, cli)
    if 'copilot' in ais:
        write_copilot(root, docs, cli)
    if 'cursor' in ais:
        write_cursor(root, docs, cli, specs_glob)
    return ais


MCP_CONFIGS = {
    'claude': ('.mcp.json', 'mcpServers'),
    'cursor': (os.path.join('.cursor', 'mcp.json'), 'mcpServers'),
    'copilot': (os.path.join('.vscode', 'mcp.json'), 'servers'),
    'gemini': (os.path.join('.gemini', 'settings.json'), 'mcpServers'),
}


def write_mcp_configs(root, ais, command='spritekiln'):
    """Register `spritekiln mcp` in the project-level MCP config of each AI client that has one."""
    written = []
    for ai in ais:
        if ai not in MCP_CONFIGS:
            continue
        rel, key = MCP_CONFIGS[ai]
        path = os.path.join(root, rel)
        data = {}
        if os.path.exists(path):
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
        entry = {'command': command, 'args': ['mcp']}
        if key == 'servers':
            entry = {'type': 'stdio', **entry}
        data.setdefault(key, {})['spritekiln'] = entry
        _write(path, json.dumps(data, indent=2) + '\n')
        written.append(path)
    return written


# ---------------------------------------------------------------- this repository

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_repo(root=REPO):
    """This repository's adapters: docs live in docs/agent; the legacy pxforge skill folders (linked by Hunt
    Tower until it migrates) keep the `python -m pxforge` command."""
    docs = 'docs/agent'
    install(root, ['claude', 'gemini', 'copilot', 'cursor'], docs, specs_glob='specs/**/*.yaml')
    write_claude(
        root,
        docs,
        'python -m pxforge',
        names=LEGACY_SKILLS,
        extra_note=' (Folder name kept for projects that link to it; same as the spritekiln skill.)',
        agents=False,
        claude_md=False,
    )


def check_repo():
    """Names of this repository's adapter files that differ from a fresh generation."""
    import tempfile

    tmp = tempfile.mkdtemp()
    try:
        for rel in _repo_files():
            src = os.path.join(REPO, rel)
            if os.path.exists(src):
                os.makedirs(os.path.dirname(os.path.join(tmp, rel)), exist_ok=True)
                shutil.copy2(src, os.path.join(tmp, rel))
        write_repo(tmp)
        stale = []
        for rel in _repo_files():
            a, b = os.path.join(REPO, rel), os.path.join(tmp, rel)
            if not os.path.exists(a) or open(a, encoding='utf-8').read() != open(b, encoding='utf-8').read():
                stale.append(rel)
        return stale
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _repo_files():
    files = ['AGENTS.md', 'CLAUDE.md', 'GEMINI.md', '.github/copilot-instructions.md', '.cursor/rules/spritekiln.mdc']
    files += [f'.claude/agents/{n}.md' for n in AGENT_ROLES]
    for folder in list(SKILLS) + list(LEGACY_SKILLS):
        base = LEGACY_SKILLS.get(folder, folder)
        files.append(f'.claude/skills/{folder}/SKILL.md')
        files += [f'.claude/skills/{folder}/{t}' for t, _ in _skill_files(base)]
    return files


if __name__ == '__main__':
    if '--check' in sys.argv:
        stale = check_repo()
        if stale:
            print('out of date (run `python -m spritekiln.agents`):', *stale, sep='\n  ')
            sys.exit(1)
        print('agent instructions are up to date')
    else:
        write_repo()
        print('wrote', len(_repo_files()), 'files')
