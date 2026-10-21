# Godot example

A gargoyle made with SpriteKiln (`specs/characters/gargula/gargula.yaml`) walking and attacking in 8
directions with `KilnSprite2D`: exact frame timing, the `hit` event spawning a spark at the `strike`
socket, the normal map under a `PointLight2D` and the emissive eyes.

Open `project.godot` in Godot 4.2 or newer and press F5. Arrow keys move, Space attacks.

`assets/spritekiln/gargula/` was written by SpriteKiln. To rebuild it from the spec, from the repository root:

```
spritekiln render specs/characters/gargula/gargula.yaml
spritekiln godot specs/characters/gargula/gargula.yaml --project examples/godot --lit --update-addon
```

The walkthrough is in [docs/engines/godot.md](../../docs/engines/godot.md).
