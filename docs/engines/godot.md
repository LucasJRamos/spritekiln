# SpriteKiln in Godot 4

This guide takes a sprite from a spec to a moving character in a Godot 4 project. You need Godot 4.2 or
newer (tested on 4.7) and, for the command-line route, `pip install spritekiln`. A finished project is in
[`examples/godot`](../../examples/godot): a gargoyle that walks, attacks and lights up in 8 directions.

## 1. Set up the game project

In the folder that holds `project.godot`:

```
spritekiln init --engine godot --ai claude      # or codex, gemini, copilot, cursor; several with commas
```

This writes `spritekiln.toml` (specs in `art/specs/`, exports to `assets/spritekiln/`), the AI adapters and
a `.gitignore` entry for renders and caches. Specs and renders stay outside `res://` imports until you export.

## 2. Make and export a sprite

```
spritekiln new knight                       # art/specs/characters/knight/knight.yaml from the template
spritekiln pose art/specs/characters/knight/knight.yaml
spritekiln render art/specs/characters/knight/knight.yaml --export
```

`--export` (or a later `spritekiln export <spec>`) writes `assets/spritekiln/knight/`:

| File | What it is |
| --- | --- |
| `knight.png`, `knight.json` | atlas and metadata (Aseprite-compatible, plus the `spritekiln` block) |
| `knight_normal.png`, `knight_emissive.png` | normal map and emissive layer (when the spec has them) |
| `knight.tres` | `SpriteFrames`: one animation per `<anim>_<dir>`, exact per-frame durations |
| `knight_canvas.tres`, `knight_lit.tres` | `CanvasTexture` with the normal map, and `SpriteFrames` that use it |
| `knight_emissive.tres` | `SpriteFrames` over the emissive atlas |
| `knight.tscn` | a ready `KilnSprite2D` scene |

The first export also copies the addon to `addons/spritekiln/`. Enable it once in **Project > Project
Settings > Plugins** (the node works without the plugin; the plugin adds in-editor building). A render
made elsewhere with `render -o` is exported with `spritekiln godot <spec> --render-dir <folder>`.

Re-exporting rewrites these files, `knight.tscn` included: keep your own nodes and scripts in a scene that
instances `knight.tscn` (or inherits it) rather than in the exported scene itself.

## 3. Use it in a scene

Instance `knight.tscn` under your character. Its origin is the ground point under the feet, so turn on
`y_sort_enabled` on the parent to sort characters by depth.

```gdscript
extends CharacterBody2D

@onready var sprite: KilnSprite2D = $Knight

func _ready() -> void:
    sprite.anim_event.connect(_on_event)
    sprite.anim_finished.connect(func(anim): sprite.play_anim(&"idle"))

func _physics_process(_delta: float) -> void:
    var input := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
    velocity = input * 60.0
    move_and_slide()
    if Input.is_action_just_pressed("ui_accept"):
        sprite.play_anim(&"attack", true)
    elif sprite.anim != &"attack" or not sprite.is_playing():
        sprite.play_anim(&"walk" if input else &"idle")
    if input:
        sprite.face(input)          # nearest exported direction

func _on_event(anim: StringName, event: StringName) -> void:
    if event == &"hit":
        var tip := sprite.to_global(sprite.get_socket(&"strike"))
        # spawn the hitbox or a spark at `tip`
```

What the node gives you:

- `play_anim(name, restart = false)` plays `<name>_<facing>`; frame-0 events fire inside the call, once.
- `face(vector)`, `set_facing(&"ne")`, `facing_vector()`, `direction_names()`, `anim_names()`, `is_loop()`.
- `anim_event(anim, event)` when a frame with an event (`hit`, `windup`, `step_l`...) becomes visible, and
  `anim_finished(anim)` at the end of a clip that does not loop.
- `get_socket(name)`: a socket's position in the node's space for the current frame (`Vector2.INF` while
  hidden), plus `get_socket_depth()`, `has_socket()`, `socket_names()`.

Events and sockets are declared in the spec (`events:` and `sockets:`); see [the spec reference](../agent/spec.md).

## 4. Light and glow

- For `PointLight2D`/`DirectionalLight2D` shading, export with `--lit` (or set the node's `sprite_frames` to
  `knight_lit.tres`): the frames use the normal map through a `CanvasTexture`.
- Emissive parts (eyes, runes, lanterns) are a second sprite drawn with additive blending, so they keep
  glowing in dark scenes. The scene wires `knight_emissive.tres` into `emissive_frames`.

## 5. Mirrored directions and side view

- A top-down spec with `mirror: true` renders the eastern half only; the node plays west-facing
  directions with `flip_h` and mirrors the sockets. Half the atlas, same API.
- A side-view spec (`view: side`, or `spritekiln new hero --view side`) has the directions `e` and `w`;
  `face()` picks one from the vector's x. With `mirror: true` only `e` is rendered.

## 6. Without the command line

The plugin builds the same resources from a render dropped into the project: copy `<name>.png`,
`<name>.json` (and `_normal.png`, `_emissive.png`) anywhere under `res://`. When Godot imports the JSON the
plugin writes the `.tres` files next to it (and the scene, when there is none yet); **Project > Tools > SpriteKiln: build sprites from
render JSONs** rebuilds every render in the project. From a script, `KilnBuilder.build("res://...json")`
does the same.

## Notes

- Clip names are `<anim>_<dir>` with `speed = 1` and durations in seconds, so a plain `AnimatedSprite2D`
  can play them too; `KilnSprite2D` adds directions, events, sockets and the emissive layer.
- Projects made with the older `pxforge` command keep the `PxSprite2D` addon (`addons/pxforge/`), which
  the `pxforge` command still exports to.
- The JSON format is documented in [format.md](../format.md).
