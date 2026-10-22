# Changelog

All notable changes to SpriteKiln. The output format has its own version (`docs/format.md`).

## 0.1.0 (unreleased)

First public release. SpriteKiln started as `pxforge`, the sprite toolkit of the game Hunt Tower.

### Making sprites
- Characters and props as YAML specs: skeleton with expressions and 2-bone IK, smooth SDF primitives,
  materials with palette ramps, emissive and glow, mirrored `_L`/`_R` parts.
- Animations from cycles or keys with per-frame timing, tweens and easing, events (`hit`, `step_l`...),
  per-direction cheats, smears, and timing targets checked by `validate` and QA.
- Top-down 3/4 view in 8 directions, or a side view (`view: side`); `mirror: true` renders half the
  directions for symmetric designs.
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
- Examples for Godot, Unity and MonoGame; a guide for Phaser, LÖVE, Defold and GameMaker.

### Compatibility
- `python -m pxforge`, the `pxforge` command, `pxforge: 1` spec headers and the `PxSprite2D` Godot addon
  keep working for projects made with pxforge.
