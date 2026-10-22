<p align="center">
  <img src="showcase/huntress/from_this_to_this.png" alt="A splash art of a gunslinger next to her pixel-art sprite in 8 directions" width="100%">
</p>

# SpriteKiln

**English** | [Português (BR)](README.pt-BR.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

**Animated pixel-art sprites from procedural 3D models, made to be driven by coding AIs.**

A character is a small YAML file: a skeleton, smooth 3D shapes, materials and animations. SpriteKiln renders
it into pixel art in 8 directions (top-down 3/4) or in profile (side view), with exact frame timing,
gameplay events, attachment points, a normal map for dynamic light and an emissive layer, ready for Godot,
Unity, MonoGame or any engine that reads Aseprite sheets.

You do not have to write the YAML. Your coding assistant (Claude Code, Codex, Gemini, Copilot, Cursor) does,
from a description or a splash art: it edits the spec, renders, **looks at the images** and fixes what it
sees. You direct.

<p align="center">
  <img src="showcase/huntress/turnaround.gif" alt="The Huntress idling in 8 directions" height="220">
  <img src="showcase/templar/turnaround.gif" alt="The Templar idling in 8 directions" height="220">
  <img src="docs/images/tutorials/platformer-run.gif" alt="Wren, a side-view platformer character, running in both profiles" height="220">
</p>

## Why
- **Consistent by construction.** One camera, one light and one palette for every asset, in every
  direction and frame. No drift between the north-east walk and the south-west attack.
- **Cheap to change.** "Make the hat bigger" or "slow down the windup" is a one-line edit, not a redraw of
  300 frames.
- **Game-ready.** Per-frame durations, events (`hit`, `step_l`, `windup`) on the right frame, sockets
  (muzzles, hands, impact points), the pivot on the ground for y-sorting, normal and emissive maps.
- **Made for AIs.** One set of instructions for every assistant, an MCP server whose tools return images,
  a JSON Schema for the spec, errors with `file:line:column`, and an art-direction review in numbers for
  assistants that cannot see.
- **Pure Python, any OS.** numpy, Pillow and PyYAML; no GPU, no Blender. Tested on Windows, macOS and
  Linux.

## Install

Python 3.10 or newer. Install the `spritekiln` command with [pipx](https://pipx.pypa.io), which keeps it
isolated and on your PATH:

**Windows** (PowerShell; no Python yet? `winget install Python.Python.3.13`, then open a new terminal)

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
py -m pipx install "spritekiln[mcp]"
```

**macOS** (Terminal, with [Homebrew](https://brew.sh))

```bash
brew install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

**Linux** (Debian/Ubuntu shown; Fedora: `sudo dnf install pipx`, Arch: `sudo pacman -S python-pipx`)

```bash
sudo apt install pipx
pipx ensurepath
pipx install "spritekiln[mcp]"
```

Then open a new terminal and check with `spritekiln --version`. `[mcp]` adds the tools for AI assistants;
`pipx install spritekiln` is enough for the command line alone. uv, a virtual environment, upgrading and
troubleshooting: [Install SpriteKiln](docs/tutorials/install.md).

## Quick start

The same on every system:

```
spritekiln new knight                                   # specs/characters/knight/knight.yaml, from the template
spritekiln render specs/characters/knight/knight.yaml   # atlas, JSON, maps, GIFs -> specs/characters/knight/out/knight/
```

Then hand it to your assistant: *"Turn this knight into a hooded goblin scout with a short sword. Check
all 8 directions before rendering."* To set up a game project, run
`spritekiln init --engine godot --ai claude` in its folder; see
[Use SpriteKiln with your AI](docs/tutorials/use-with-your-ai.md).

## How it works

```
spec.yaml ──► skeleton + IK ──► SDF shapes ──► raymarched render ──► pixelize ──► atlas + JSON
 (bones,      (expressions per   (spheres,      (colour, normals,     (palette ramps,   + normal map
  shapes,      frame: cycles,     capsules,      depth, materials;     outlines, clean   + emissive map
  materials,   keys, events)      boxes, cones,  3x supersampled,      single pixels)    + GIFs, QA
  animations)                     smooth unions) fixed world light)                      -> your engine
```

The light is fixed in the world and the model turns, so shading stays coherent across directions. Every
render writes a QA report (clipping, palette, silhouette stability) and contact sheets to review.

## Features
- **Modeling:** bones with expressions (`"0.045*sin(p)"`), 2-bone IK, smooth SDF primitives, mirrored
  `_L`/`_R` parts, materials with palette ramps, emissive and glow, two-sided membranes, conditional parts.
- **Animation:** cycles from expressions or keyframes with per-frame timing, tweens and easing, smears,
  per-direction cheats, events, timing targets checked by `validate` (e.g. "impact at 300 ms").
- **Views:** top-down 3/4 in 8 (or 4, or 1) directions, or a side view for platformers (`view: side`, with
  a template that has run, jump, rise, fall and land); `mirror: true` renders only the right-facing
  directions (the engine flips the rest) for symmetric designs.
- **From a splash art:** `ref prep` cuts the character out and extracts its palette; `ref compare` scores
  the silhouette against the model (pitch-corrected IoU) and says what to change.
- **Review:** `spritekiln review` measures value range, contrast, pixels per material and legibility, and
  previews the sprite over your game's floor (`--bg`) under its light (`--tint`).
- **Output:** atlas, normal and emissive maps, Aseprite-compatible JSON ([format](docs/format.md)), sockets
  per frame, GIFs and contact sheets.

## Engines

| Engine | What you get | Guide |
|---|---|---|
| **Godot 4** | `KilnSprite2D` node, SpriteFrames and a ready scene; an editor plugin builds them from a dropped JSON | [godot.md](docs/engines/godot.md) · [example](examples/godot) |
| **Unity 2022.3+** | UPM package: `.kiln` importer (sprites, normal map, AnimationClips) and `KilnAnimator` | [unity.md](docs/engines/unity.md) |
| **MonoGame** | `KilnSprite.cs` runtime and the `KilnLit.fx` normal-mapped light shader | [monogame.md](docs/engines/monogame.md) · [example](examples/monogame) |
| **Anything else** | Aseprite-compatible JSON: Phaser, LÖVE, Defold, GameMaker... | [generic.md](docs/engines/generic.md) |

All runtimes play the same way: exact durations, events on the frame they belong to, sockets, the direction
nearest to a velocity, mirrored directions.

## AI assistants

| Assistant | Instructions | MCP tools |
|---|---|---|
| Claude Code | `CLAUDE.md`, skills, and modeler / animator / art-director agents | `.mcp.json` |
| Codex | `AGENTS.md` | `~/.codex/config.toml` |
| Gemini CLI | `GEMINI.md` | `.gemini/settings.json` |
| GitHub Copilot | `.github/copilot-instructions.md` | `.vscode/mcp.json` |
| Cursor | `.cursor/rules/spritekiln.mdc` | `.cursor/mcp.json` |

`spritekiln init --ai claude,codex,...` writes them from one source ([`docs/agent/`](docs/agent)). The
recipe for a new character from a splash art: a modeler builds the shape, an art director reviews it
against the art, the modeler fixes, an animator animates, the director reviews again
([recipe.md](docs/agent/recipe.md)).

## Showcase
The Templar and the Huntress were made with SpriteKiln for the game **Hunt Tower**, from their splash arts,
by Claude Code following the recipe above. Their specs are in `specs/characters/`; more images, animations
and in-game captures are in [`showcase/`](showcase).

## Learn more
- [Install SpriteKiln](docs/tutorials/install.md) (Windows, macOS, Linux; pipx, uv or a virtual environment)
- [Your first character in 10 minutes](docs/tutorials/first-character.md)
- [From your splash art, with an AI](docs/tutorials/splash-art.md)
- [Animations and events](docs/tutorials/animations.md)
- [A platformer character (side view)](docs/tutorials/platformer.md)
- [Use SpriteKiln with your AI](docs/tutorials/use-with-your-ai.md) (instructions files and MCP tools)
- [Spec reference](docs/agent/spec.md) · [Output format](docs/format.md) · [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · Translations: [Português (BR)](README.pt-BR.md), [한국어](README.ko.md), [日本語](README.ja.md),
  [简体中文](README.zh-CN.md)

## License
Code, docs and integrations: [MIT](LICENSE). Example assets (the gargoyle, the hunter, Wren, the crates, gas lamp
and training dummy props, the templates, the gothic and props palettes, the examples' sprites):
[CC0 1.0](LICENSES/CC0-1.0.txt). Showcase assets (Templar and Huntress from Hunt Tower, with the Huntress's
mine: specs, splash arts, palettes, renders and game captures): © 2026 Lucas Ramos / PlayRPG, all rights
reserved, included for demonstration only ([terms](LICENSES/LicenseRef-Showcase.txt)).
[`REUSE.toml`](REUSE.toml) maps every path to its license.
