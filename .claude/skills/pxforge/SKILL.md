---
name: pxforge
description: Create and edit characters, monsters and props as animated 8-direction pixel art (top-down 3/4) with SpriteKiln (procedural SDF model in YAML -> render -> pixel art). Use for any request about a sprite, animation, spritesheet, pose, direction, palette or visual fix of an asset made with it. (Folder name kept for projects that link to it; same as the spritekiln skill.)
---

# Working with SpriteKiln

SpriteKiln turns a **spec** (one YAML file: skeleton, SDF primitives, materials, palette, animations) into
clean pixel art: a limited palette with hue shifting, selective outlines, inner lines, pixel cleanup, and 8
coherent directions (the same 3D model, rotated). Read [spec.md](SPEC.md) before editing a spec.

## Commands
```
python -m pxforge validate <spec.yaml>                       # after every edit; problems come with file:line:column
python -m pxforge pose <spec.yaml> [--anim walk --frame 3] [--dirs all|s,se,e]   # cheap preview PNG
python -m pxforge render <spec.yaml> [--anims idle,walk] [--dirs s,e] [--size 48]   # atlas, JSON, GIFs, QA
python -m pxforge review <spec.yaml> [--bg floor.png --tint 0.7,0.7,1.0] [--against other.yaml] [--ref splash.png]
python -m pxforge export <spec.yaml>                          # hand the render to the engine in spritekiln.toml
python -m pxforge ref prep <splash.png>                       # cutout, palette and proportions of a splash art
python -m pxforge ref compare <spec.yaml> <splash.png> --dir se   # silhouette IoU (camera-corrected) + hints
python -m pxforge palette ramp "#5d4f6c" --steps 6            # hue-shifted ramp
python -m pxforge palette extract <image>                     # palette YAML from an image
python -m pxforge new <name> [--template humanoid] [--ref splash.png]
python -m pxforge cache info|prune|clear                      # render cache (.kilncache/)
```
`pose` costs about 1 s per direction. A full `render` of 3 animations × 8 directions is about 190 frames
(minutes), so iterate with `pose` and render everything at the end. `render` picks the number of worker
processes from the free memory; pass `--jobs 1` on a busy machine.

If the `spritekiln` command is not on the PATH, use `python -m spritekiln` (or the project's wrapper).

## The loop (always)
1. **Read** the spec and its `brief:`. No spec yet: `python -m pxforge new <name>` (humanoid template), or start
   from a similar spec (the gargoyle in this repository is a good base for creatures).
2. **Edit** a little at a time: one part or one key.
3. **`validate`** and fix until OK. Warnings matter too: an unknown key ("did you mean pitch?") is ignored
   by the renderer, so a typo silently does nothing.
4. **`pose --dirs all` and look at the image.** Check the silhouette in s, e, n and a diagonal. If you
   cannot see images, run `review` and read the numbers instead (see [art-direction.md](art-direction.md)).
5. Repeat 2–4. For an animation, `pose --anim X --frame i` on the key frames.
6. **`render`**, then read the QA summary and the `preview/contact_<anim>.png` sheets. QA errors (sprite
   clipped at the edge, empty frame, timing target missed) block the asset.
7. **Report**: what changed, the paths of the GIFs and contact sheets, the QA warnings left.

Never call something visual "good" without having looked at the PNG (or read `review` numbers).

## Outputs
`out/<name>/` next to the spec: `<name>.png` (atlas: one row per animation × direction), `<name>.json`
(Aseprite-compatible, plus the `spritekiln` block with directions, pivot, camera, durations, events and
sockets; see `docs/format.md`), `<name>_normal.png`, `<name>_emissive.png`, `preview/<anim>_8dir.gif`,
`preview/contact_<anim>.png` and `qa.json`. Outputs are generated: never edit them by hand.

## Keep a game consistent
All assets of a game share the camera `pitch` (38 by default), the `light`, and the density
`camera.scale` (world units per pixel); a bigger character gets a bigger `size` (frame), not a different
scale. Shared palettes live in the project's palettes folder; `gothic` and `props` are built in.

## Projects
`python -m pxforge init` writes `spritekiln.toml` (specs folder, engine, export folder, defaults for new specs).
Commands run anywhere inside the project find it. `python -m pxforge export <spec>` (or `render --export`) then
puts the files where the engine expects them (Godot: SpriteFrames, CanvasTexture and a ready scene).

## Tools for AIs
`python -m pxforge mcp` serves the same operations over the Model Context Protocol (validate, pose, render,
review, ref_compare, export, new), returning images and JSON. Use it when your AI client supports MCP.

The renderer can draw anything; what survives at 64 px (top-down 3/4, pitch 38°) is a short list.

## Legibility rules
- **Big head** (1.2–1.4× real proportions) and a silhouette with **2–3 striking shapes** (horns, wings, a
  weapon, a cape, a hat). Details smaller than about 2 px (0.1 world units at `scale: 0.05`) vanish or turn
  into noise.
- **Thin parts:** a radius of at least ~0.025 at `scale: 0.05` (claws, blades); thinner breaks into dots.
- **Colours:** one ramp per material, 4–6 tones; few materials (3–6). Emissives (eyes, magic) are the
  accent. Value contrast between neighbouring materials matters more than hue.
- **Perspective:** things that stick out backwards or away rise on the screen. Check the diagonals: a thin
  piece seen edge-on becomes a stick; change its angle, or cheat per direction with `yaw`/`dir` in an
  expression.
- **Margins:** keep ≥ 2 px free around every frame (QA warns). If a frame clips, increase `camera.scale`
  (zoom out) for the whole asset, raise `size`, or reduce that gesture.
- **Consistency:** never change one asset's camera `pitch`, `light` or density (`camera.scale`); the
  whole game shares them. A bigger creature gets a bigger `size`.

## Procedure
1. Start from a template (`python -m pxforge new <name>`) or the closest existing spec. Fill `brief:` first (see
   [splash-to-model.md](splash-to-model.md)).
2. **Big masses first**: world scale (total height 1.6–2.0 for a human), pelvis height, IK lengths, then
   torso, head, hips and legs as ellipsoids and cones only.
3. Add the striking shapes one at a time (`chain` horns, `membrane` capes and wings, `box`/`cylinder`
   weapons in a hand frame, hair as blended ellipsoids). After each: `validate`, `pose --dirs all`, look.
4. Check **all 8 directions**, not only the reference's: the back and the profiles must make sense. Invent
   what the reference does not show, coherently, and write the decision in `brief`.
5. Materials and palette last-but-not-least: 3–6 materials plus one emissive; tune ramps with
   `python -m pxforge palette ramp "#hex" --steps 5`.

## Rules for a modeler (human or AI)
- Work only in the asked asset's spec. Iterate in small steps: edit → `validate` → `pose --dirs all` →
  **look at the PNG** → fix. Never call a model done without having seen the 8 directions.
- With a splash art: `ref prep` once, `ref compare` after every proportion change (targets in
  [splash-to-model.md](splash-to-model.md)).
- Keep the skeleton, channels and names the animations use. If you rename something, update the
  animations too and `validate`.
- Do not change `camera.pitch`, `light` or shared palettes unless asked.
- Do not render every animation while modeling; at most `render --anims idle --dirs s,e,n,se`.
- Report: what changed (parts, materials), IoU and hints left, image paths for review, and the design
  decisions taken where the reference shows nothing.

## More
Reference files in this folder: [SPEC.md](SPEC.md), [splash-to-model.md](splash-to-model.md), [animation.md](animation.md), [art-direction.md](art-direction.md), [recipe.md](recipe.md).
