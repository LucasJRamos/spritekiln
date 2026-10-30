# Working with SpriteKiln

SpriteKiln turns a **spec** (one YAML file: skeleton, SDF primitives, materials, palette, animations) into
clean pixel art: a limited palette with hue shifting, selective outlines, inner lines, pixel cleanup, and 8
coherent directions (the same 3D model, rotated). Read [spec.md](SPEC.md) before editing a spec.

## Commands
```
spritekiln style                                      # the project's art style (first: interview the user)
spritekiln style set --view topdown --height 48 ...   # record the answers (see style.md)
spritekiln style preview [<spec.yaml>] [--field light]   # the style's look choices side by side
spritekiln validate <spec.yaml>                       # after every edit; problems come with file:line:column
spritekiln spec outline <spec.yaml>                   # map of the file: each part/animation with its lines
spritekiln spec show <spec.yaml> parts.helm animations.walk   # numbered lines of the blocks you edit
spritekiln pose <spec.yaml> [--anim walk --frame 3] [--dirs all|s,se,e] [--draft]   # cheap preview PNG
spritekiln pose <spec.yaml> --focus head --dirs all     # close-up (12x) of the head, hair and face
spritekiln render <spec.yaml> [--anims idle,walk] [--dirs s,e] [--size 48] [--draft]   # atlas, JSON, GIFs, QA
spritekiln review <spec.yaml> [--bg floor.png --tint 0.7,0.7,1.0] [--against other.yaml] [--ref splash.png]
spritekiln export <spec.yaml>                          # hand the render to the engine in spritekiln.toml
spritekiln ref prep <splash.png>                       # cutout, palette and proportions of a splash art
spritekiln ref compare <spec.yaml> <splash.png> --dir se   # silhouette IoU (camera-corrected) + hints
spritekiln palette ramp "#5d4f6c" --steps 6            # hue-shifted ramp
spritekiln palette extract <image>                     # palette YAML from an image
spritekiln new <name> [--extends] [--template humanoid|side_humanoid] [--view side] [--ref splash.png]
spritekiln kits [<name>]                                # kits a spec can `use` (weapons, headwear, capes...)
spritekiln cache info|prune|clear                      # render cache (.kilncache/)
spritekiln update [--check | --files]                  # upgrade SpriteKiln, refresh the project's AI files
```
`pose` costs about 1 s per direction. A full `render` of 3 animations × 8 directions is about 190 frames
(minutes), so iterate with `pose` and render everything at the end. `render` picks the number of worker
processes from the free memory; pass `--jobs 1` on a busy machine. With the `[fast]` extra installed, the
log says `renderer: numba`: about 6× faster, in one process (the first run compiles it for about 10 s).

`--draft` traces one ray per pixel instead of nine: several times faster, with rougher edges and thin parts
that may break. Use it while shaping silhouettes and poses (`pose --draft`) or checking motion (`render
--draft` writes only GIFs and contact sheets, in `preview-draft/`, and cannot be exported). Never judge
final quality on a draft: look at a full `pose --dirs all` before `render`.

If the `spritekiln` command is not on the PATH, use `python -m spritekiln` (or the project's wrapper).

## The loop (always)
0. **Art style.** Once per session, before any asset: `spritekiln style`. If it says no style is recorded,
   stop and interview the user with the questions of [style.md](style.md), confirm a summary and record
   it with `spritekiln style set`; only then go on. Every asset follows the recorded style; it changes
   only when the user explicitly asks.
1. **Read** the spec and its `brief:`. A long spec: `spec outline` first (a fraction of the file), then
   `spec show` the blocks you will edit (or read those line ranges); a mirrored `_R` item is edited in its
   `_L` source; an item from a base or a kit (`spec outline` says where from) is changed by giving the keys
   that differ in the spec, never by editing the base or the kit. No spec yet: `spritekiln new <name>
   --extends` for a humanoid (a short spec over the humanoid template, or `side_humanoid` with platformer
   clips for a side view: it states only what differs), weapons and gear from `spritekiln kits`; a plain
   `spritekiln new <name>` copies the template to reshape everything; or start from a similar spec (the
   gargoyle in SpriteKiln's repository, `specs/characters/gargula/gargula.yaml` on
   https://github.com/LucasJRamos/spritekiln, is a good base for creatures).
2. **Edit** a little at a time: one part or one key. Edit the YAML as text, in place: its comments explain
   the model and the compact `{...}` style keeps it readable. Never regenerate a spec with a YAML dumper
   or a script.
3. **`validate`** and fix until OK. Warnings matter too: an unknown key ("did you mean pitch?") is ignored
   by the renderer, so a typo silently does nothing.
4. **`pose --dirs all` and look at the image** (`--draft` while the shape is still changing). Check the
   silhouette in s, e, n and a diagonal. A character's head and face: `pose --focus head --dirs all`, since a
   face is a few pixels on a normal preview. If you cannot see images, run `review` and read the numbers
   instead (see [art-direction.md](art-direction.md)).
5. Repeat 2–4. For an animation, `pose --anim X --frame i` on the key frames. Before rendering, one full
   (not draft) `pose --dirs all` to check edges and thin parts.
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

Previews (`pose`, contact sheets, GIFs, `review` and `ref compare` sheets) are cropped to what the sprite
shows and zoomed by whole factors that fit an AI's image budget (about 1500 px and 1.15 megapixels), so every
sprite pixel is a clean square. `--scale` is the largest zoom. `pose --no-crop` shows the whole frame; over a
`--bg` the whole frame always shows. `pose --focus <bone>` crops to a bone and everything attached below it
(`head`: the head, hair, eyes and headwear), or to parts by name, at up to 12x. Atlases are never cropped.

## Top-down or side-scroller
Specs are top-down 3/4 by default (`view: topdown`). For a platformer or side-scroller use `view: side`
(camera at 0°, directions `e` and `w`, no ground shadow): `spritekiln new <name> --view side`, or
`spritekiln init --view side` to make it the project's default. `pose` then shows the spec's directions.

## Keep a game consistent
All assets of a game share the `view`, the camera `pitch` (38 top-down, 0 side), the `light`, and the density
`camera.scale` (world units per pixel); a bigger character gets a bigger `size` (frame), not a different
scale. Shared palettes live in the project's palettes folder; `gothic` and `props` are built in. The
project's art style (`spritekiln style`, [style.md](style.md)) records these choices with the user's answers
about outline, shading, proportions and animation; `spritekiln new` applies its numbers.

## Projects
`spritekiln init` writes `spritekiln.toml` (specs folder, engine, export folder, defaults for new specs,
including the view; the art style once recorded). Commands run anywhere inside the project find it. `spritekiln export <spec>` (or `render --export`) then
puts the files where the engine expects them (Godot: SpriteFrames, CanvasTexture and a ready scene).
After SpriteKiln is upgraded, `spritekiln update --files` rewrites the project's copies of these
instructions; commands print a note when they come from another version.

## Tools for AIs
`spritekiln mcp` serves the same operations over the Model Context Protocol (style, validate, pose,
render, review, ref_compare, export, new, kits, style_preview), returning images and JSON. Use it when your AI client supports MCP.
