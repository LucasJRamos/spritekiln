# SpriteKiln: notes for Claude Code

Development rules for this repository are in `AGENTS.md` ("Developing SpriteKiln"); the generated block
below is about making assets.

- For asset work, load the `spritekiln` skill (plus `spritekiln-splash-to-model` for a splash art and
  `spritekiln-animation` for animations), and delegate as in `docs/agent/recipe.md`: `character-modeler`,
  `pixel-art-director` (reviews, never edits), `animator`.
- Use this folder's virtual environment: `.venv/Scripts/python.exe -m spritekiln ...` (Windows) when the
  `spritekiln` command is not on the PATH.

## Maintainer notes (Hunt Tower)
The maintainer's game `D:/GameProjects/tower-hunt` runs this toolkit through its `tools/px.cmd` (this
folder's `.venv`, `python -m pxforge`, `PXFORGE_GODOT_PROJECT`) and links the skill folders
`.claude/skills/pxforge*` (generated alongside the `spritekiln*` ones). Keep those working until the game
migrates (Phase 6 of `docs/LAUNCH.md`), and never edit the game from here.

<!-- spritekiln:begin (generated from docs/agent by spritekiln; edit the sources, not this block) -->
## SpriteKiln assets
Sprites in this project are made with SpriteKiln: a YAML spec (skeleton, SDF primitives, materials, palette,
animations) is rendered into animated 8-direction pixel art (atlas + JSON + normal/emissive maps).

Read before working on an asset: `docs/agent/workflow.md` (commands and the working loop) and `docs/agent/spec.md` (the spec
format). Then, as needed: `docs/agent/modeling.md`, `docs/agent/splash-to-model.md`, `docs/agent/animation.md`,
`docs/agent/art-direction.md` and `docs/agent/recipe.md` (the modeler → art director → animator recipe).

Rules that matter:
- Run `spritekiln validate <spec>` after every edit; problems come with file:line:column.
- Iterate with `spritekiln pose <spec> --dirs all` (about 1 s per direction); `spritekiln render` only at the end.
- Never call something visual good without looking at the PNG. If you cannot see images, use the numbers of
  `spritekiln review` (value, contrast, pixels per material, IoU) and `qa.json`.
- Keep the camera pitch, light and `camera.scale` shared by every asset of the game.
- Outputs under `out/` are generated: never edit them.
- `spritekiln export <spec>` hands a render to the engine configured in `spritekiln.toml`.
- With an MCP client, `spritekiln mcp` serves these operations as tools that return images and JSON.

Claude Code: skills `spritekiln`, `spritekiln-splash-to-model`, `spritekiln-animation`; agents `character-modeler`, `animator`, `pixel-art-director` (see `recipe.md` for the order).
<!-- spritekiln:end -->
