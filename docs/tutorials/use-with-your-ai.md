# Use SpriteKiln with your coding AI

SpriteKiln was built to be driven by a coding assistant: the AI writes and edits the YAML spec, runs the
commands, looks at the images and fixes what it sees. You describe the character (or hand over a splash
art) and review the result.

There are two ways to connect them, and you can use both:

- **Instructions in the project** (every assistant): files the assistant reads before it starts, so it
  knows the workflow, the spec format and the rules (validate after every edit, look at the PNGs).
- **MCP tools** (assistants with MCP support): `spritekiln mcp` serves the operations as tools that return
  images and JSON, so the assistant does not need a shell.

## 1. Set up the game project

[Install SpriteKiln](install.md) with the `[mcp]` extra (`pipx install "spritekiln[mcp]"`; the page has the
steps for Windows, macOS and Linux). Then, in your game folder:

```
cd my-game
spritekiln init --engine godot --ai claude,codex
```

`--engine` is `godot`, `unity`, `monogame` or `generic` (any other engine, or no game yet: exports go to
`sprites/`); `--ai` takes any of the names below, separated by commas, or `generic` for any other agent that
reads `AGENTS.md`. Without options, `init` uses `generic` for both. It writes:

| File | For |
|---|---|
| `spritekiln.toml` | project settings: specs folder, engine, assistants, export folder, defaults for new specs and, once recorded, the art style |
| `.spritekiln/agent/` | the knowledge files: workflow, art style, spec reference, modeling, splash to model, animation, art direction, recipe |
| `AGENTS.md` | the short version and pointers (read by Codex and most other agents) |
| `CLAUDE.md`, `.claude/skills/`, `.claude/agents/` | `--ai claude`: skills and the modeler, animator and art-director agents |
| `GEMINI.md` | `--ai gemini` |
| `.github/copilot-instructions.md` | `--ai copilot` |
| `.cursor/rules/spritekiln.mdc` | `--ai cursor` |
| `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, `.gemini/settings.json` | the MCP server for clients that read a project config |

Existing `AGENTS.md`/`CLAUDE.md` files keep their content: SpriteKiln only manages a marked block inside
them. `spritekiln update` keeps these files current when SpriteKiln is upgraded, without touching
`spritekiln.toml` ([Install SpriteKiln](install.md#upgrade)).

Codex reads MCP servers from `~/.codex/config.toml` (on Windows, `%USERPROFILE%\.codex\config.toml`):

```toml
[mcp_servers.spritekiln]
command = "spritekiln"
args = ["mcp"]
```

## 2. The art style interview

The first time you ask for an asset, the assistant does not start right away: it runs `spritekiln style`,
sees that the project has no art style yet, and asks you a few questions, at most four at a time:

1. **View:** top-down 3/4 or side view.
2. **Size on screen:** how many pixels tall a human-sized character is (24–32 retro, 40–48 classic,
   56–72 detailed, 96+ hi-bit), or your tile size. This sets the density every asset shares.
3. **Directions:** 8 or 4 (or 2 in a side view), and whether the engine mirrors the left-facing ones.
4. **Colours:** the mood of the palette, or a palette or image you already have.
5. **Outline and shading:** selective, dark or no outline; soft or flat shading.
6. **Proportions:** stylized, chibi or realistic.
7. **Animation:** fluid or snappy.
8. **References** (optional): games, artists or images to match, and any rule ("no blood").

It pushes back on vague answers ("retro" → how many pixels tall?), proposes answers from what it already
knows (your request, a splash art, the specs the project already has), shows you a summary and records it
with `spritekiln style set`. From then on:

- `spritekiln new` gives every spec the recorded view, density, frame size, directions and palette; the
  modeler, the animator and the art director follow the rest.
- `spritekiln style` shows the style at any time and lists the specs that no longer match it.
- The style changes only when you say so ("from now on characters are 32 px tall"). A request about one
  asset ("make this boss twice as big") stays an exception for that asset, noted in its spec.

Prefer to answer in the terminal? `spritekiln style set --view topdown --height 48 --outline dark ...`
(`spritekiln style set -h` lists every answer).

## 3. Ask for a sprite

Plain language works. Name what matters for the game:

> Make a goblin scout for this game: hooded, small, with a short sword and a backpack. 64 px, top-down.
> Start from the template, check all 8 directions, then render idle, walk and attack and export to Godot.

> Here is the splash art of our boss (`art/boss.png`). Model it faithfully, compare the silhouette with
> `ref compare`, and show me the pose sheet before you animate.

> The attack feels slow. Make the windup shorter and the impact land at 300 ms; keep the `hit` event on
> the impact frame.

A good assistant follows the loop in `workflow.md`: edit the spec, `validate`, `pose` in every direction,
look at the image, fix, and only then `render`, `review` and `export`.

## 4. What the MCP tools do

| Tool | Returns |
|---|---|
| `guide` | a knowledge file (for clients that cannot read the project's files) |
| `style` | the project's art style, or the questions to ask when none is recorded; records the answers |
| `style_preview` | a pose under each choice of the style's look (outline, shading, lines, dither, light) |
| `new` | a spec created from a template |
| `validate` | errors and warnings with `file:line:column` |
| `pose` | the pose sheet image in the chosen directions |
| `render` | the summary, QA report and contact sheets |
| `review` | the art-direction report and its image |
| `ref_compare` | silhouette IoU against a splash art, with hints and the comparison sheet |
| `export` | what was written for the engine |
| `schema` | the JSON Schema of the spec format |

Image tools return the picture next to the numbers, so an assistant that sees images can judge the art,
and one that cannot still gets the measurements.

## 5. Tips

- **Ask for the pose sheet before the render.** A render takes minutes; a pose takes seconds.
- **Keep one style.** `spritekiln.toml` holds the art style and the shared camera pitch, scale and
  palette; the assistant does not change them per asset unless you ask.
- **Review with your own eyes.** Open `out/<name>/preview/contact_<anim>.png` and the GIFs before you call
  an asset done; ask for a `review` when something feels off but you cannot say what.
- **Claude Code:** the recipe in `recipe.md` splits the work between the `character-modeler`,
  `pixel-art-director` and `animator` agents.
- **Edits are text.** The spec is YAML with comments that explain the model; ask the assistant to edit it
  in place rather than regenerate it with a script, so the comments survive.
- **The `spritekiln` command must be on the PATH** for the MCP configs above, which is what pipx and
  `uv tool` do. Installed in a virtual environment instead, put the full path to the command in them
  ([Install SpriteKiln](install.md#other-ways)).
- **Codex on Windows:** its sandbox cannot start the Microsoft Store build of Python, so a `spritekiln`
  installed with it fails with "Unable to create process". Install SpriteKiln with a python.org Python
  (`winget install Python.Python.3.13`), `pipx` or `uv tool install "spritekiln[mcp]"`.
