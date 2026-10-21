# SpriteKiln for Godot 4

Plays sprites made with [SpriteKiln](https://github.com/LucasJRamos/spritekiln): animated 8-direction
top-down (or side-view) pixel art rendered from procedural 3D models.

## Getting sprites in
- With the CLI: `spritekiln export <spec>` (or `spritekiln render <spec> --export`) in a project set up with
  `spritekiln init --engine godot` writes `assets/spritekiln/<name>/` with the atlas, JSON, SpriteFrames,
  a CanvasTexture with the normal map, and a ready scene.
- Without the CLI: copy a render's `<name>.png`, `<name>.json` (and `_normal.png`, `_emissive.png`) into the
  project. The plugin builds the same resources when the JSON is imported; run
  **Project > Tools > SpriteKiln: build sprites from render JSONs** to rebuild everything.

## KilnSprite2D (extends AnimatedSprite2D)
- `sheet: JSON`: the render JSON (pivot, directions, loops, events, sockets).
- `emissive_frames: SpriteFrames`: optional emissive layer, drawn with additive blending.
- `play_anim(&"walk", restart = false)`: frame-0 events fire inside the call.
- `face(velocity)`, `set_facing(&"ne")`, `facing_vector()`, `direction_names()`.
- `get_socket(&"muzzle_R")` (local position, `Vector2.INF` when hidden), `get_socket_depth()`,
  `has_socket()`, `socket_names()`.
- Signals: `anim_event(anim, event)` (hit, windup, step_l...) and `anim_finished(anim)`.
- The node's origin is the ground point under the character: enable `y_sort_enabled` on the parent.
- Mirrored directions (specs with `mirror: true`) play their twin's frames with `flip_h`; sockets follow.

Clips are named `<anim>_<dir>` (e.g. `attack_ne`) with `speed = 1` and per-frame durations in seconds.
`<name>_lit.tres` uses a CanvasTexture with the normal map for `PointLight2D`/`DirectionalLight2D`.

MIT licensed.
