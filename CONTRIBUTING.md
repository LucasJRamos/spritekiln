# Contributing to SpriteKiln

Thanks for helping. Bug reports, sprites made with SpriteKiln, engine integrations and docs fixes are all
welcome. Everything in the repository is written in English; the READMEs in Portuguese, Korean, Japanese and
Chinese are the only translations, and follow `README.md` when it changes.

## Set up

Python 3.10 or newer (see [Install SpriteKiln](docs/tutorials/install.md) to get it) and git. The core is
pure Python (numpy, Pillow, PyYAML).

macOS and Linux:

```bash
git clone https://github.com/LucasJRamos/spritekiln.git
cd spritekiln
python3 -m venv .venv                     # Debian/Ubuntu: sudo apt install python3-venv first
source .venv/bin/activate
pip install -e ".[dev]" "reuse[charset-normalizer]"
pytest                                    # unit, CLI and golden-image tests, about two minutes
```

Windows (PowerShell):

```powershell
git clone https://github.com/LucasJRamos/spritekiln.git
cd spritekiln
py -m venv .venv
.venv\Scripts\Activate.ps1                # cmd: .venv\Scripts\activate.bat
pip install -e ".[dev]" "reuse[charset-normalizer]"
pytest                                    # unit, CLI and golden-image tests, about two minutes
```

## Before you open a pull request

- `pytest` passes. `pytest -m slow` also re-renders the showcase and compares it frame by frame; run it
  when you touch the renderer.
- `ruff check .` and `ruff format --check .` pass; `reuse lint` passes if you added files (licensing is
  per path, see `REUSE.toml`).
- **Visual changes are deliberate.** If your change alters pixels, update the goldens with
  `pytest --update-golden`, look at the new images, and say in the commit message why they changed.
- The AI instructions (`AGENTS.md`'s generated block, `CLAUDE.md`, `GEMINI.md`, `.claude/`, `.cursor/`,
  `.github/copilot-instructions.md`) are generated from `docs/agent/`. Edit those sources and run
  `python -m spritekiln.agents`; CI checks that they are in sync.
- Changes to the output JSON follow `docs/format.md`: new fields are fine, removing or changing the meaning
  of one is a new format version. Architectural choices go to `docs/decisions.md` as a short ADR.

## Engine integrations

Each runtime (`integrations/godot`, `integrations/unity`, `integrations/monogame`) follows the same
behaviour ([ADR-023](docs/decisions.md)): exact per-frame durations, frame-0 events inside the call that starts a clip, sockets,
mirrored directions. Their tests run inside the engine and are opt-in:

| Engine | Enable with |
|---|---|
| Godot 4 | `SPRITEKILN_GODOT_BIN=/path/to/godot` |
| Unity 6 | `SPRITEKILN_UNITY_BIN=/path/to/Unity` (an activated license that allows batch mode) |
| MonoGame | `SPRITEKILN_MONOGAME=1` (the .NET 8 SDK) |

Set them for the session before `pytest`: `export SPRITEKILN_GODOT_BIN=/path/to/godot` on macOS and Linux,
`$env:SPRITEKILN_GODOT_BIN = "C:\path\to\godot.exe"` in PowerShell, `set SPRITEKILN_GODOT_BIN=C:\path\to\godot.exe`
in cmd.

## Sprites and specs

Example specs you contribute are released under CC0 1.0 (add them to the CC0 list in `REUSE.toml`). Only
contribute art you made or have the right to give away; do not add splash art from other games or artists.

## Reporting bugs

Include the spec (or a minimal one that shows the problem), the command, the output, `spritekiln --version`
and your OS. For visual problems, attach the PNG (`pose`, `review` or the contact sheet).

By contributing you agree that your code is released under the MIT license and that you follow the
[code of conduct](CODE_OF_CONDUCT.md).
