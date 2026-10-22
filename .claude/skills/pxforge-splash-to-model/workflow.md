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
python -m pxforge new <name> [--template humanoid|side_humanoid] [--view side] [--ref splash.png]
python -m pxforge cache info|prune|clear                      # render cache (.kilncache/)
```
`pose` costs about 1 s per direction. A full `render` of 3 animations × 8 directions is about 190 frames
(minutes), so iterate with `pose` and render everything at the end. `render` picks the number of worker
processes from the free memory; pass `--jobs 1` on a busy machine.

If the `spritekiln` command is not on the PATH, use `python -m spritekiln` (or the project's wrapper).

## The loop (always)
1. **Read** the spec and its `brief:`. No spec yet: `python -m pxforge new <name>` (the humanoid template, or
   `side_humanoid` with platformer clips for a side view), or start from a similar spec (the gargoyle in
   SpriteKiln's repository, `specs/characters/gargula/gargula.yaml` on
   https://github.com/LucasJRamos/spritekiln, is a good base for creatures).
2. **Edit** a little at a time: one part or one key. Edit the YAML as text, in place: its comments explain
   the model and the compact `{...}` style keeps it readable. Never regenerate a spec with a YAML dumper
   or a script.
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
sockets; see the output format at https://github.com/LucasJRamos/spritekiln/blob/main/docs/format.md),
`<name>_normal.png`, `<name>_emissive.png`, `preview/<anim>_<n>dir.gif` (`_8dir`, `_2dir` for a side view),
`preview/contact_<anim>.png` and `qa.json`. Outputs are generated: never edit them by hand.

## Top-down or side-scroller
Specs are top-down 3/4 by default (`view: topdown`). For a platformer or side-scroller use `view: side`
(camera at 0°, directions `e` and `w`, no ground shadow): `python -m pxforge new <name> --view side`, or
`python -m pxforge init --view side` to make it the project's default. `pose` then shows the spec's directions.

## Keep a game consistent
All assets of a game share the `view`, the camera `pitch` (38 top-down, 0 side), the `light`, and the density
`camera.scale` (world units per pixel); a bigger character gets a bigger `size` (frame), not a different
scale. Shared palettes live in the project's palettes folder; `gothic` and `props` are built in.

## Projects
`python -m pxforge init` writes `spritekiln.toml` (specs folder, engine, export folder, defaults for new specs,
including the view).
Commands run anywhere inside the project find it. `python -m pxforge export <spec>` (or `render --export`) then
puts the files where the engine expects them (Godot: SpriteFrames, CanvasTexture and a ready scene).

## Tools for AIs
`python -m pxforge mcp` serves the same operations over the Model Context Protocol (validate, pose, render,
review, ref_compare, export, new), returning images and JSON. Use it when your AI client supports MCP.
