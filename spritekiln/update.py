"""`spritekiln update`: upgrade SpriteKiln the way it was installed, then refresh the project's AI files.

A game project keeps copies of SpriteKiln's instructions for its AI (`.spritekiln/agent/`, skills, agents,
the marked blocks of AGENTS.md and the like), written by `spritekiln init`. Upgrading the package does not
reach them, so `update` rewrites them with the new version, leaves spritekiln.toml, specs and renders alone,
and stamps `.spritekiln/version`; other commands then notice a project whose files come from another version.
"""

import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

from . import __version__, agents, config
from .errors import SpriteKilnError

PYPI = 'https://pypi.org/pypi/spritekiln/json'
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
# Windows keeps a running .exe locked (the console-script launchers keep their own file open, so it cannot even
# be renamed): an installer that rewrites spritekiln.exe while `spritekiln update` runs from it fails, and pip
# then leaves the environment half uninstalled. pipx copes; for uv only the package is upgraded, and a virtual
# environment is upgraded from `python -m spritekiln update`, which runs no launcher.
WINDOWS = os.name == 'nt'


def version_key(v):
    """Sortable form of a version: '0.2.0' -> (0, 2, 0, 0); a pre-release ('0.3.0rc1') sorts just below its
    release, a post-release just above."""
    m = re.match(r'\s*v?(\d+(?:\.\d+)*)(.*)', str(v))
    if not m:
        return (0, 0, 0, -1)
    nums = tuple(int(x) for x in m.group(1).split('.'))
    nums += (0,) * (3 - len(nums))
    rest = m.group(2).lstrip('.-_').lower()
    return nums + ((0,) if not rest else (1,) if rest.startswith('post') else (-1,))


def latest(timeout=15):
    """The newest SpriteKiln version on PyPI. SPRITEKILN_PYPI_URL points the check elsewhere (rehearsals)."""
    import urllib.request

    url = os.environ.get('SPRITEKILN_PYPI_URL', PYPI)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)['info']['version']
    except (OSError, ValueError, KeyError) as e:
        raise SpriteKilnError(f'could not read the latest version from {url} ({e}); check the connection') from None


def installation():
    """How this SpriteKiln was installed: {kind, command, display}. kind: source (a checkout or editable
    install: update it with git), pipx, uv, venv (pip in a virtual environment) or system (a Python of the
    system, which is not upgraded automatically). `command` is None when it cannot be run from here, and
    `display` then says what to run instead."""
    if _source_checkout():
        root = os.path.dirname(PACKAGE_DIR)
        return dict(kind='source', command=None, display=f'git pull in {root} (then pip install -e . if needed)')
    prefix = sys.prefix
    if os.path.isfile(os.path.join(prefix, 'pipx_metadata.json')):
        pipx = _pipx()
        display = 'pipx upgrade spritekiln'
        return dict(kind='pipx', command=pipx and [*pipx, 'upgrade', 'spritekiln'], display=display)
    req = requirement()
    if os.path.isfile(os.path.join(prefix, 'uv-receipt.toml')):
        uv = shutil.which('uv')
        cmd = [uv, 'tool', 'upgrade', 'spritekiln']
        if WINDOWS:  # `uv tool upgrade` would rewrite the running spritekiln.exe; the package alone is enough
            cmd = [uv, 'pip', 'install', '--python', sys.executable, '--upgrade', req]
        return dict(kind='uv', command=uv and cmd, display='uv tool upgrade spritekiln')
    if sys.prefix != sys.base_prefix:
        if _launcher():  # pip would have to replace the spritekiln.exe this runs from
            display = (
                'python -m spritekiln update (in the activated environment: Windows cannot replace '
                'spritekiln.exe while it runs)'
            )
            return dict(kind='venv', command=None, display=display)
        cmd = [sys.executable, '-m', 'pip', 'install', '--upgrade', req]
        return dict(kind='venv', command=cmd, display=f'python -m pip install --upgrade "{req}"')
    return dict(
        kind='system',
        command=None,
        display=f'pipx install --force "{req}" (see the install guide; pip refuses or misplaces system installs)',
    )


def requirement():
    """`spritekiln` with the extras this installation has, so an upgrade keeps them."""
    extras = [x for x, mod in (('mcp', 'mcp'), ('splash', 'rembg'), ('fast', 'numba')) if importlib.util.find_spec(mod)]
    return f'spritekiln[{",".join(extras)}]' if extras else 'spritekiln'


def _source_checkout():
    """True when this code is not the installed distribution's (a checkout run in place, or an editable
    install)."""
    if os.path.isfile(os.path.join(os.path.dirname(PACKAGE_DIR), 'pyproject.toml')):  # never in site-packages
        return True
    try:
        dist = importlib.metadata.distribution('spritekiln')
    except importlib.metadata.PackageNotFoundError:
        return True
    url = dist.read_text('direct_url.json')
    if url:
        try:
            if json.loads(url).get('dir_info', {}).get('editable'):
                return True
        except ValueError:
            pass
    installed = dist.locate_file(os.path.join('spritekiln', '__init__.py'))
    try:
        return not os.path.samefile(installed, os.path.join(PACKAGE_DIR, '__init__.py'))
    except OSError:
        return True


def _pipx():
    """The command that runs pipx: `pipx`, or `py -m pipx` / `python3 -m pipx` when pipx.exe is not on the
    PATH (the Windows install puts it in a user folder that often is not)."""
    exe = shutil.which('pipx')
    if exe:
        return [exe]
    for name in (['py'] if WINDOWS else []) + ['python3', 'python']:
        py = shutil.which(name)
        if not py:
            continue
        try:
            ok = subprocess.run([py, '-m', 'pipx', '--version'], capture_output=True, timeout=60).returncode == 0
        except (OSError, subprocess.SubprocessError):
            ok = False
        if ok:
            return [py, '-m', 'pipx']
    return None


def upgrade(inst):
    """Run the installer's upgrade (`inst` from installation()). Returns (exit code, the version installed
    afterwards or None when it cannot be read)."""
    rc = subprocess.run(inst['command']).returncode
    probe = 'import importlib.metadata as m; print(m.version("spritekiln"))'
    try:
        out = subprocess.run([sys.executable, '-c', probe], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return rc, None
    return rc, (out.stdout.strip() or None) if out.returncode == 0 else None


def _launcher():
    """The console-script .exe running this process on Windows (its path, without .exe, is sys.argv[0])."""
    if not WINDOWS:
        return None
    exe = sys.argv[0] if sys.argv[0].lower().endswith('.exe') else sys.argv[0] + '.exe'
    return os.path.abspath(exe) if os.path.isfile(exe) else None


# ---------------------------------------------------------------- the project's files


def detect_ais(root):
    """Assistants a project was set up for, from the files `init` wrote (projects from before 0.2 do not
    list them in spritekiln.toml). AGENTS.md serves Codex and any other agent."""

    def marked(rel):
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            return False
        with open(path, encoding='utf-8', errors='replace') as fh:
            return agents.BEGIN.split(' (')[0] in fh.read()

    found = []
    if os.path.isdir(os.path.join(root, '.claude', 'skills', 'spritekiln')) or marked('CLAUDE.md'):
        found.append('claude')
    if marked('GEMINI.md'):
        found.append('gemini')
    if marked(os.path.join('.github', 'copilot-instructions.md')):
        found.append('copilot')
    if os.path.isfile(os.path.join(root, '.cursor', 'rules', 'spritekiln.mdc')):
        found.append('cursor')
    return found or ['generic']


def refresh(start=None):
    """Rewrite the AI files of the project around `start` with this version: the knowledge files, the
    adapters of its assistants and, in a Godot project that has it, the addon. spritekiln.toml, specs,
    renders and MCP configs are left alone. Returns {root, ais, written, addon}."""
    from .scaffold import DOCS_DIR, adapter_files, stamp

    cfg = config.load(start)
    if not cfg:
        raise SpriteKilnError(
            'no spritekiln.toml here or above: run this in a game folder set up with `spritekiln init`'
        )
    root = cfg['root']
    ais = cfg['ai'] or detect_ais(root)
    docs = os.path.join(root, DOCS_DIR)
    _prune(docs, set(agents.DOCS))
    agents.write_docs(docs)
    specs = os.path.relpath(cfg['specs'], root).replace(os.sep, '/')
    ais = agents.install(root, ais, DOCS_DIR, specs_glob=f'{specs}/**/*.yaml')
    if 'claude' in ais:
        for name in agents.SKILLS:
            keep = {'SKILL.md', *(t for t, _ in agents.skill_files(name))}
            _prune(os.path.join(root, '.claude', 'skills', name), keep)
    written = [docs] + [os.path.join(root, f) for f in adapter_files(ais) if os.path.exists(os.path.join(root, f))]
    written.append(stamp(root))
    return dict(root=root, ais=ais, written=written, addon=_refresh_godot_addon(cfg))


def _prune(folder, keep):
    """Remove the .md files of a SpriteKiln-owned folder that this version no longer writes."""
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            if f.endswith('.md') and f not in keep and os.path.isfile(os.path.join(folder, f)):
                os.remove(os.path.join(folder, f))


def _refresh_godot_addon(cfg):
    """Update addons/spritekiln in the Godot project when it is installed there and older than this one."""
    if cfg['engine'] != 'godot':
        return None
    from .godot import install_addon

    cfg_file = os.path.join(cfg['godot_project'], 'addons', 'spritekiln', 'plugin.cfg')
    if not os.path.isfile(cfg_file):
        return None
    with open(cfg_file, encoding='utf-8') as fh:
        m = re.search(r'^version="([^"]+)"', fh.read(), re.M)
    have = m.group(1) if m else '0'
    if version_key(have) >= version_key(__version__):
        return None
    install_addon(cfg['godot_project'], True, 'spritekiln')
    return dict(path=os.path.dirname(cfg_file), was=have, now=__version__)


def files_version(root):
    """The SpriteKiln version that wrote a project's AI files: its stamp, '<0.2' for files written before
    stamps existed, None for a project without them."""
    from .scaffold import DOCS_DIR, STAMP

    try:
        with open(os.path.join(root, STAMP), encoding='utf-8') as fh:
            return fh.read().strip() or None
    except OSError:
        return '<0.2' if os.path.isdir(os.path.join(root, DOCS_DIR)) else None


def stale_note(start=None):
    """A one-line note when the project around `start` has AI files from another SpriteKiln version."""
    path = config.find(start)
    if not path:
        return None
    have = files_version(os.path.dirname(path))
    if have is None or have == __version__:
        return None
    if have != '<0.2' and version_key(have) > version_key(__version__):
        return (
            f"this project's AI files come from SpriteKiln {have}, newer than this one ({__version__}): "
            'run `spritekiln update`'
        )
    older = 'an older SpriteKiln' if have == '<0.2' else f'SpriteKiln {have}'
    return f"this project's AI instructions come from {older}: refresh them with `spritekiln update --files`"
