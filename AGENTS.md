# Agent instructions

SpriteKiln generates animated 8-direction pixel-art sprites from procedural 3D models described in YAML.
This file serves two kinds of work: **making assets** with the toolkit (the generated block at the end, the
same one every AI adapter gets) and **developing the toolkit** (below).

## Developing SpriteKiln
- Python 3.10+, pure Python (numpy, pillow, pyyaml). The package is `spritekiln/`; `pxforge/` is a
  compatibility shim for projects that still call `python -m pxforge`.
- Set up with `pip install -e ".[dev]"`. Run `pytest` (unit, CLI and golden-image tests, about two minutes)
  after every change; `pytest -m slow` re-renders the showcase and checks it frame by frame (long).
- `ruff check .` and `ruff format --check .` must pass; `reuse lint` checks the per-path licensing.
- An intentional visual change updates the goldens (`pytest --update-golden`) and says why in the commit.
- The AI instructions (this block, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`,
  `.cursor/rules/`, `.claude/skills/`, `.claude/agents/`) are generated from `docs/agent/`: edit those files,
  then run `python -m spritekiln.agents` (CI runs it with `--check`).
- Contracts and decisions: `docs/format.md` (output format), `docs/decisions.md` (ADRs), `docs/ROADMAP.md`
  (what comes next).
- Everything in the repository is written in English; the only translations are the READMEs
  (`README.pt-BR.md`, `README.ko.md`, `README.ja.md`, `README.zh-CN.md`), which follow `README.md`.

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
