# Output format

`spritekiln render <spec>` writes `out/<name>/` next to the spec. This document is the contract for
engines and tools that read it. **Output format version: 1.**

| File | Content |
|---|---|
| `<name>.png` | Color atlas, RGBA8888, straight alpha. |
| `<name>_normal.png` | Normal map with the same layout. |
| `<name>_emissive.png` | Emissive layer with the same layout (unlit pixels, for additive blending). |
| `<name>.json` | Frames, tags and the `spritekiln` block (below). |
| `qa.json` | Automatic checks: `ok`, `errors`, `warnings`, `info`. |
| `preview/` | `<anim>_<n>dir.gif` and `contact_<anim>.png` for human review. Not meant for engines. |

## Atlas layout
- Every cell is `frame_size × frame_size` pixels; frames are never trimmed or rotated.
- One row per (animation, direction), in the order of the `animations` and `directions` lists; one column
  per frame. Rows of short animations are padded with transparent cells.
- All three atlases (color, normal, emissive) share the layout, so one rectangle addresses all of them.

## JSON
The file is a valid **Aseprite "hash" sprite-sheet JSON**, so tools that read Aseprite exports load it
without changes:

- `frames`: one entry per cell, keyed `<anim>_<dir>_<index>` (e.g. `attack_ne_3`), with `frame`
  (`x, y, w, h`), `duration` (ms), `rotated: false`, `trimmed: false`, `spriteSourceSize`, `sourceSize`.
- `meta`: `app: "spritekiln"`, `version` (the spritekiln version), `image`, `format: "RGBA8888"`, `size`,
  `scale: "1"`, and `frameTags` with one tag per clip, named `<anim>_<dir>`, `direction: "forward"`.

The `spritekiln` block carries what Aseprite's format cannot express:

| Field | Type | Meaning |
|---|---|---|
| `format` | int | Output format version (1). |
| `generator` | string | `spritekiln <version>`. |
| `name` | string | Asset name (`name:` in the spec). |
| `frame_size` | int | Cell size in px. |
| `pivot` | `{x, y}` | Ground point under the model origin, in px from the top-left of a cell. Place the sprite so that this point sits on the entity's position; it is the right point for y-sorting. |
| `directions` | `[string]` | Exported directions, e.g. `["s", "se", "e", "ne", "n", "nw", "w", "sw"]`. |
| `direction_yaw` | `{dir: degrees}` | Model rotation per direction: `s` 0, `se` 45, `e` 90, `ne` 135, `n` 180, `nw` −135, `w` −90, `sw` −45. Includes mirrored directions. |
| `mirrors` | `{dir: dir}` | Only with `mirror: true` in the spec: directions that are not in the atlas and play their twin flipped horizontally (e.g. `{"w": "e", "sw": "se", "nw": "ne"}`). Flip around the pivot and negate socket `x`. |
| `view` | string | `topdown` (3/4, the default) or `side` (side-scroller profile). |
| `camera` | object | How world units map to pixels (below). |
| `normal_map`, `emissive_map` | string | File names of the other atlases. |
| `sockets` | `[string]` | Socket names, when the spec declares sockets (see [Sockets](#sockets)). |
| `animations` | object | Per animation: `loop` (bool) and `directions` → `{row, frames, durations, events, sockets}`. |

Per animation and direction:

- `row`: atlas row.
- `frames`: frame keys in play order.
- `durations`: ms per frame (integers), same length as `frames`.
- `events`: `{"<frame index>": ["event", ...]}`. The index is a string because JSON keys are strings.
- `sockets` (only when the spec has sockets): `{"<socket>": [point or null, one per frame]}`.

### Directions on screen
For direction yaw *y*, the facing vector on screen is `(sin y, cos y)` with x to the right and y down:
`s` faces the viewer (down), `e` faces right, `n` faces away (up). To pick a direction from a velocity
`v` in screen space, take `atan2(v.x, v.y)` and choose the exported direction with the nearest yaw.
Mirrored directions (`mirrors`) take part in this choice like the others. `KilnSprite2D.face()` (Godot),
`KilnAnimator.Face()` (Unity) and `PxAnimator.FaceTowards()` (MonoGame) do exactly this.

### Camera
The model is rendered with an orthographic top-down 3/4 camera:

| Field | Meaning |
|---|---|
| `projection` | Always `"orthographic"`. |
| `pitch_deg` | Camera tilt below the horizon (38 by default). |
| `world_units_per_px` | Width of one pixel in world units (the spec's `camera.scale`). |
| `px_per_unit` | Its inverse. |
| `ground_k` | `sin(pitch)`. A step of *d* world units along the ground toward the viewer (south) moves a point *d · ground_k · px_per_unit* px down on screen. |
| `height_k` | `cos(pitch)`. A height of *h* world units spans *h · height_k · px_per_unit* px on screen. |
| `center` | World point at the center of each cell (before the per-frame `root` offset). |

A side step of *d* world units moves *d · px_per_unit* px horizontally. A game that moves entities on a
ground plane in pixels should therefore scale vertical ground motion by `ground_k` to match the art
(Hunt Tower: `ground_k` = sin 38° ≈ 0.616). Assets that share `camera.scale` and `pitch` share these
numbers and look consistent side by side, whatever their `frame_size`.

### Timing and events
Durations are the source of truth; there is no fps in the file.

- In a clip with durations *d₀ … dₙ₋₁*, frame *i* is visible during [*Tᵢ*, *Tᵢ + dᵢ*) where
  *Tᵢ* = *d₀ + … + dᵢ₋₁* (so *T₀* = 0), measured from the moment the clip starts.
- **An event listed on frame *i* fires at *Tᵢ*, when frame *i* becomes visible.** Events on frame 0
  fire when the clip starts; in a looping clip they fire again at the start of every loop.
- A clip with `loop: false` ends at *Tₙ* = *d₀ + … + dₙ₋₁*; its last frame stays visible.
- Engines should advance clips with accumulated time, not frame counts. At 60 fps, the event on frame
  *i* belongs to tick ⌊*Tᵢ* · 60 / 1000⌋ counted from the tick that started the clip. The runtimes
  emit frame-0 events inside the call that starts the clip (`play_anim()`, `Play()`), in the same tick.
- Common event names: `step_l`, `step_r`, `windup`, `hit`, `release`. They are free-form strings set in
  the spec.

### Sockets
A socket is a point that follows a bone: a muzzle, a hand that holds an item, a foot, a hit point. The
spec declares it once (`sockets: {muzzle_L: {bone: pistol_L, offset: [0, 0.042, 0.50], when: "gun < 0.5"}}`,
with an automatic `_R` twin) and the exporter writes its position for every frame and direction:

- A point is `[x, y, depth]`. `x` and `y` are pixels from the pivot (x right, y down), so the socket
  sits at `entity position + (x, y)` (times the draw scale).
- `depth` is the ground distance in pixels from the character's vertical axis toward the viewer: `> 0`
  in front of the body, `< 0` behind it. Use it to draw an effect or an attached object in front of or
  behind the sprite.
- `null` means the socket is hidden in that frame (its `when` expression is false, e.g. the pistol
  muzzle while the rifle is drawn).

Runtimes: `KilnSprite2D.get_socket(name)` / `get_socket_depth(name)` / `has_socket(name)` in Godot (local
coordinates of the node, whose origin is the pivot), `KilnAnimator.TryGetSocket(name, out local, out depth)`
in Unity (local units) and `PxAnimator.TryGetSocket(name, out offset, out depth)` in MonoGame. In a mirrored
direction the runtimes negate `x`. Positions are exact to well under a pixel: on the Huntress, every muzzle socket is
within 0.3 px of the centre of the muzzle-flash pixels in all 8 directions.

### Normal and emissive maps
- **Normal map:** camera-space normals, encoded as RGB = *n* · 0.5 + 0.5, with x to the right on screen,
  y up on screen and z toward the viewer. Outline pixels take the normal of the nearest sprite pixel.
  Alpha is 255 on opaque sprite pixels and 0 elsewhere.
- **Emissive map:** the colors of emissive materials (eyes, magic, fire), unlit, alpha 255 where emissive
  and 0 elsewhere. Draw it on top with additive blending; it is fully transparent when the asset has no
  emissive material.

## Versioning
- `format` changes only on breaking changes (a field removed, renamed or changing meaning). New fields
  can appear in any version; readers must ignore fields they do not know.
- Files written by pxforge 0.1 have the block under the key `pxforge` and no `format`, `generator` or
  `camera`. Read them as format 1 without camera metadata. The `pxforge` command still writes the
  `pxforge` key, so projects whose runtime predates the rename keep working; the runtimes in
  `integrations/` read both keys.

## Spec files
Specs start with a version header: `spritekiln: 1` (or `pxforge: 1` in older files). The spec format is
described in [`docs/agent/spec.md`](agent/spec.md) and in the JSON Schema `spritekiln/data/spec.schema.json`.
