# Install SpriteKiln

SpriteKiln is a command-line tool written in Python. It runs on Windows, macOS and Linux, needs
**Python 3.10 or newer** and no GPU.

The recommended way is [pipx](https://pipx.pypa.io): it installs the `spritekiln` command in an environment
of its own and puts it on your PATH, so it works from any folder, and AI assistants can start its MCP server
(`spritekiln mcp`) without knowing about virtual environments. Pick your system below; after that, every
`spritekiln` command in these docs is the same everywhere.

## Windows

In **PowerShell** (Windows Terminal opens it by default):

1. Check Python with `py --version`. If the command is missing or shows a version older than 3.10, install
   Python and open a new terminal:

   ```powershell
   winget install Python.Python.3.13      # or the installer from python.org
   ```

2. Install pipx and SpriteKiln:

   ```powershell
   py -m pip install --user pipx
   py -m pipx ensurepath
   py -m pipx install "spritekiln[mcp]"
   ```

3. Open a new terminal (`ensurepath` changed the PATH) and check: `spritekiln --version`.

Prefer the Python from python.org or `winget` to the Microsoft Store one: Codex's sandbox cannot start the
Store build ("Unable to create process").

## macOS

In **Terminal**, with [Homebrew](https://brew.sh):

```bash
brew install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

Open a new terminal and check: `spritekiln --version`. Homebrew's pipx brings its own Python.

Without Homebrew, install Python from python.org (the `python3` that comes with Apple's command-line tools
is 3.9, too old), then:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
python3 -m pipx install "spritekiln[mcp]"
```

## Linux

Install pipx from your distribution, then SpriteKiln:

```bash
sudo apt install pipx            # Debian, Ubuntu, Mint
sudo dnf install pipx            # Fedora
sudo pacman -S python-pipx       # Arch, Manjaro
sudo zypper install python3-pipx # openSUSE
```

```bash
pipx ensurepath
pipx install "spritekiln[mcp]"
```

Open a new terminal and check: `spritekiln --version`. pipx uses the system's `python3`, which must be 3.10 or
newer (`python3 --version`; Ubuntu 22.04, Debian 12 and Fedora 36 or later have it). On an older system,
use uv (below): it downloads a recent Python for you.

## Other ways

**uv**, on any system, if you already use it ([install uv](https://docs.astral.sh/uv/getting-started/installation/)):

```
uv tool install "spritekiln[mcp]"
uv tool update-shell             # once, if the spritekiln command is not found; then open a new terminal
```

**A virtual environment with pip**, to pin a SpriteKiln version per project. Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1       # cmd: .venv\Scripts\activate.bat
pip install "spritekiln[mcp]"
```

macOS and Linux:

```bash
python3 -m venv .venv            # Debian/Ubuntu: sudo apt install python3-venv first
source .venv/bin/activate
pip install "spritekiln[mcp]"
```

The command exists only while the environment is active (run the activation line again in every new
terminal). AI assistants started elsewhere, such as VS Code, Cursor or a desktop app, will not find it: in
the MCP configs that `spritekiln init` writes, replace `"command": "spritekiln"` with the full path to
`.venv\Scripts\spritekiln.exe` (Windows) or `.venv/bin/spritekiln` (macOS, Linux).

Do not `pip install` into the system Python: recent macOS (Homebrew) and Linux systems refuse it with
`externally-managed-environment`, and on Windows the command may land in a folder that is not on the PATH.

## The `[mcp]` extra

`[mcp]` adds the MCP server that AI assistants use as tools (`spritekiln mcp`). If you only use the command
line, `pipx install spritekiln` is enough; the instructions files that `spritekiln init` writes work
without it. Keep the quotes around `"spritekiln[mcp]"`: zsh, the default shell on macOS, reads the brackets
as a file pattern otherwise.

## Upgrade and uninstall

| | pipx | uv | virtual environment |
|---|---|---|---|
| Upgrade | `pipx upgrade spritekiln` | `uv tool upgrade spritekiln` | `pip install -U "spritekiln[mcp]"` |
| Uninstall | `pipx uninstall spritekiln` | `uv tool uninstall spritekiln` | delete the `.venv` folder |

After an upgrade, run `spritekiln init` again in your game project with the same options and `--force` to
refresh the knowledge files your AI reads (it also rewrites `spritekiln.toml`: keep a copy if you edited it).

## Troubleshooting

- **`spritekiln: command not found`** (macOS, Linux) or **`'spritekiln' is not recognized`** (Windows):
  open a new terminal after `pipx ensurepath`. If it is still missing, run `pipx ensurepath` again (Windows:
  `py -m pipx ensurepath`) and read what it says.
- **`pipx: command not found` right after installing it:** use `python3 -m pipx` (macOS, Linux) or
  `py -m pipx` (Windows) until you open a new terminal.
- **`error: externally-managed-environment`:** `pip install` was run on the system Python. Use pipx, uv or a
  virtual environment, as above.
- **PowerShell says running scripts is disabled** when activating a virtual environment: run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use pipx, which needs no activation.
- **Paths:** the docs write them with `/` (`specs/characters/knight/knight.yaml`); that works as-is in
  PowerShell and cmd too.

Next: [your first character in 10 minutes](first-character.md), or
[set up SpriteKiln for your AI assistant](use-with-your-ai.md).
