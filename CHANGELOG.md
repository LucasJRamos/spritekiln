# Changelog

All notable changes to SpriteKiln. The output format has its own version (`docs/format.md`).

## Unreleased (0.3)

### Faster renders, correct soft shading
- Each part is bounded by a tight sphere: frames render 1.5–2.7× faster (the Templar, 6.6 s → 2.2 s per frame
  on the development machine), with the same part in every pixel.
- Soft shadows and ambient occlusion no longer darken surfaces near a part's bounding sphere: shading
  depends on the geometry only. Assets rendered again are lighter where those false shadows used to fall,
  so they do not match renders of 0.2 pixel for pixel.

### Draft previews
- `pose --draft` (MCP `pose(draft=true)`) traces one ray per pixel instead of nine: an 8-direction pose of the
  Templar takes 5 s instead of 15 s, for shaping silhouettes and poses. Files end in `_draft`.
- `render --draft` writes only GIFs and contact sheets, in `preview-draft/`, to check motion; it writes no atlas,
  JSON or QA and cannot be exported.

### Pixel-exact previews
- Previews are cropped to what the sprite shows and zoomed by whole factors that fit an AI's image budget
  (about 1500 px and 1.15 megapixels): `pose`, contact sheets, GIFs, the `review` and `ref compare` sheets. AI
  clients used to receive them shrunk by fractions, which made pixels uneven. The Templar's idle contact sheet
  goes from 2358 × 2354 px to 982 × 1138 px.
- `pose --scale` is now the largest zoom; `pose --no-crop` keeps whole frames. MCP `pose` returns the `zoom` and
  the `crop` box; MCP tools cut an image that is still too large into pieces instead of shrinking it.

## 0.2.0 (2026-10-25)

### Upgrading from 0.1.0
0.1.0 has no `update` command yet: upgrade once with `pipx upgrade spritekiln` (or `uv tool upgrade
spritekiln`), then run `spritekiln update --files` in each game folder to refresh the instructions your AI
reads. From 0.2.0 on, `spritekiln update` does both.

### The art style, asked before the first asset
- Before the first asset of a project, the assistant interviews you about the art style: view, how many
  pixels tall a character is on screen, directions and mirroring, colours, outline and shading,
  proportions, the feel of the animation and references. It pushes back on vague answers, proposes answers
  from what it already knows (the request, a splash art, existing specs) and confirms a summary.
- `spritekiln style set` records the answers in the `[style]` table of `spritekiln.toml` and turns the
  numeric ones into defaults for `spritekiln new` (`camera.scale` and the frame `size` come from the
  character height). Every later asset follows the style; it changes only when you ask, one answer at a
  time.
- `spritekiln style` shows the style, suggests answers from the specs a project already has, and lists the
  specs that no longer match it. MCP tool `style`; knowledge file `style.md`, read by the modeler, animator
  and art-director roles. `spritekiln new` reminds you when a project has no style yet.

### Updating
- `spritekiln update` upgrades SpriteKiln the way it was installed (pipx, uv or a virtual environment,
  keeping its extras) and refreshes the current game folder's AI files (knowledge files, skills, agents,
  marked blocks, the Godot addon when it is installed and older) without touching `spritekiln.toml`,
  specs or renders. `--check` only looks; `--files` only refreshes. In a virtual environment on Windows,
  run it as `python -m spritekiln update` (Windows cannot replace the running `spritekiln.exe`).
- `spritekiln init` records the project's assistants (`ai` in `spritekiln.toml`) and stamps the version of
  its AI files; commands note a project whose files come from another version. `init --force` keeps a
  recorded art style.

## 0.1.0 (2026-10-22)

First public release. SpriteKiln started as `pxforge`, the sprite toolkit of the game Hunt Tower.

### Making sprites
- Characters and props as YAML specs: skeleton with expressions and 2-bone IK, smooth SDF primitives,
  materials with palette ramps, emissive and glow, mirrored `_L`/`_R` parts.
- Animations from cycles or keys with per-frame timing, tweens and easing, events (`hit`, `step_l`...),
  per-direction cheats, smears, and timing targets checked by `validate` and QA.
- Top-down 3/4 view in 8 directions, or a side view (`view: side`) with a platformer template
  (`side_humanoid`: run, jump, rise, fall, land, crouch, attack, hurt, death); `mirror: true` renders
  only the right-facing directions (5 of 8, or 1 of 2 in a side view) for symmetric designs.
- Sockets: attachment points (muzzles, hands, impact points) exported per frame.
- Output: atlas, normal map and emissive map, Aseprite-compatible JSON (output format 1), GIFs, contact
  sheets and `qa.json`.
- `spritekiln review`: art-direction report (value, contrast, pixels per material, silhouette IoU).
- `spritekiln ref prep|compare`: model from a splash art, with a pitch-corrected silhouette comparison.
- Render cache, memory-aware worker pool, `--size` to rescale.

### Working with AIs
- `docs/agent/`: one source of knowledge, generated into AGENTS.md, CLAUDE.md, GEMINI.md, Copilot and
  Cursor rules, Claude Code skills and agents.
- `spritekiln init --engine ... --ai ...` sets up a game project; `spritekiln mcp` serves the operations
  as MCP tools that return images and JSON.
- JSON Schema for specs, with editor autocompletion and `file:line:column` errors.

### Engines
- Godot 4: `KilnSprite2D` addon (exact timing, events, sockets, emissive layer, mirroring) and an editor
  plugin that builds SpriteFrames and scenes from render JSONs.
- Unity 2022.3+ (tested on 6000.3): UPM package with a `.kiln` importer and `KilnAnimator`.
- MonoGame 3.8: `KilnSprite.cs` runtime and the `KilnLit.fx` normal-mapped light shader.
- Example projects for Godot and MonoGame, a package sample for Unity; a guide for Phaser, LÖVE, Defold
  and GameMaker.

### Examples and docs
- Example characters (CC0): a gargoyle, a hunter, Wren (side view), and props; the Huntress and the
  Templar of Hunt Tower as a showcase.
- Tutorials: install (Windows, macOS, Linux), first character, from your splash art, animations and
  events, a platformer character, use with your AI; engine guides.

### Compatibility
- Windows, macOS (Apple Silicon and Intel) and Linux, Python 3.10 to 3.15. CI installs it with the README's
  commands on clean machines of each, and checks the published package every week.
- `python -m pxforge`, the `pxforge` command, `pxforge: 1` spec headers and the `PxSprite2D` Godot addon
  keep working for projects made with pxforge.
