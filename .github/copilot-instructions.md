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
<!-- spritekiln:end -->
