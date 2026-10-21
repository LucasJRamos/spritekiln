# SpriteKiln for Unity

Imports sprites made with [SpriteKiln](https://github.com/LucasJRamos/spritekiln): animated 8-direction
top-down (or side-view) pixel art rendered from procedural 3D models.

## Install
**Window > Package Manager > + > Install package from git URL**:

```
https://github.com/LucasJRamos/spritekiln.git?path=/integrations/unity
```

Tested on Unity 6000.3; requires 2022.3 or newer.

## Getting sprites in
- With the CLI: `spritekiln export <spec> --engine unity` (or `spritekiln init --engine unity` once, then
  `spritekiln render <spec> --export`) writes `Assets/SpriteKiln/<name>/`: the atlases and `<name>.kiln`.
- By hand: copy a render's `<name>.png`, `_normal.png`, `_emissive.png` and `<name>.json` into `Assets/`,
  renaming the JSON to `<name>.kiln` (Unity keeps `.json` for itself).

The `.kiln` importer creates, as sub-assets:
- a `KilnSheet` (the main asset): directions, animations, durations, events and sockets;
- point-filtered textures and one sprite per frame, pivot on the ground point under the character, with
  the normal map as the `_NormalMap` secondary texture (URP 2D lights use it with `Sprite-Lit-Default`);
- an `AnimationClip` per animation and direction (`attack_ne`) with AnimationEvents that call
  `OnKilnEvent(string)`, for projects that drive sprites with an Animator. Turn them off in the importer.

Importer settings: **Pixels Per Unit** (32), **Animation Clips**, **Event Function**.

## KilnAnimator
Add a `SpriteRenderer` and a `KilnAnimator`, and drop the `.kiln` asset on **Sheet**.

```csharp
var kiln = GetComponent<KilnAnimator>();
kiln.Play("walk");                         // frame-0 events fire inside the call
kiln.Face(velocity);                       // world vector (x right, y up) -> nearest direction
kiln.EventFired += (anim, ev) => { if (ev == "hit") DealDamage(); };
kiln.Finished += anim => kiln.Play("idle");
if (kiln.TryGetSocket("strike", out var local, out var depth))
    Instantiate(spark, transform.TransformPoint(local), Quaternion.identity);
```

- `Play(anim, restart)`, `Face(vector)`, `SetFacing("ne")`, `FacingVector`, `CurrentAnimation`, `Facing`,
  `Frame`, `IsPlaying`, `Flipped`, `Tick(seconds)` (called from `Update`; call it yourself for a fixed step).
- Events as C# events (`EventFired`, `Finished`) and as UnityEvents in the inspector (`onEvent`, `onFinished`).
- `TryGetSocket(name, out local, out depth)`: the socket in local units for the current frame; `depth > 0`
  is in front of the body.
- Mirrored directions (specs with `mirror: true`) play their twin with `flipX`; sockets follow.
- Emissive parts (eyes, magic) are drawn by a child `Emissive` SpriteRenderer with an unlit material, so
  they glow in dark scenes. Set **Emissive Material** to use your own (an additive one, for example).

For depth sorting in a top-down game, set **Project Settings > Graphics > Transparency Sort Mode** to
Custom Axis (0, 1, 0) (or the same on the URP 2D Renderer): the sprites' pivot is the ground point.

MIT licensed.
