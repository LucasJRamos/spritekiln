# SpriteKiln in Unity

This guide takes a sprite from a spec to a moving character in Unity 2022.3 or newer. The package is
tested in Unity 6000.3 (import, timing, events, mirroring, sockets) with the built-in renderer; URP 2D
lighting with the normal map has not been tested yet.

## 1. Install the package

**Window > Package Manager > + > Install package from git URL**:

```
https://github.com/LucasJRamos/spritekiln.git?path=/integrations/unity
```

## 2. Set up the project for SpriteKiln

In the Unity project folder (the one with `Assets/`):

```
pip install "spritekiln[mcp]"
spritekiln init --engine unity --ai claude      # or codex, gemini, copilot, cursor
```

Specs go to `art/specs/`, exports to `Assets/SpriteKiln/`.

## 3. Make and export a sprite

```
spritekiln new knight
spritekiln pose art/specs/characters/knight/knight.yaml
spritekiln render art/specs/characters/knight/knight.yaml --export
```

`Assets/SpriteKiln/knight/` receives the atlases and `knight.kiln` (the render JSON; Unity keeps `.json`
for itself). The importer turns `knight.kiln` into a `KilnSheet` with point-filtered textures, a sprite per
frame (pivot on the ground point, normal map attached as `_NormalMap`) and an `AnimationClip` per animation
and direction. Without the CLI, copy a render's PNGs and JSON and rename the JSON to `.kiln`.

## 4. Use it in a scene

Create a GameObject with a `SpriteRenderer` and a `KilnAnimator`, and drop `knight.kiln` on **Sheet**.

```csharp
using SpriteKiln;
using UnityEngine;

public class Knight : MonoBehaviour
{
    KilnAnimator kiln;

    void Start()
    {
        kiln = GetComponent<KilnAnimator>();
        kiln.EventFired += (anim, ev) =>
        {
            if (ev == "hit" && kiln.TryGetSocket("strike", out var local, out _))
                Debug.Log($"hit at {transform.TransformPoint(local)}");
        };
        kiln.Finished += anim => kiln.Play("idle");
    }

    public void Move(Vector2 velocity)       // world units, y up
    {
        if (kiln.CurrentAnimation == "attack" && kiln.IsPlaying) return;
        kiln.Play(velocity == Vector2.zero ? "idle" : "walk");
        kiln.Face(velocity);                  // nearest exported direction
    }

    public void Attack() => kiln.Play("attack", true);
}
```

- Frame-0 events fire inside `Play()`; later ones when their frame becomes visible, from the exact
  per-frame durations of the render. `Tick(seconds)` advances by hand (for a fixed-step game, disable the
  component and call it yourself).
- `TryGetSocket(name, out local, out depth)` gives the socket in local units for the current frame;
  `depth > 0` is in front of the body.
- Specs with `mirror: true` render half the directions; `KilnAnimator` plays the others with `flipX` and
  mirrors the sockets.

The package sample **Gargoyle demo** (Package Manager > SpriteKiln > Samples) is a playable version: add
`GargoyleDemo` to an empty GameObject, drop `gargula.kiln` on **Sheet** and press Play.

## 5. Sorting, light and glow

- Top-down games: set **Transparency Sort Mode** to Custom Axis (0, 1, 0) (Graphics settings, or the URP 2D
  Renderer asset). `KilnAnimator` sets the renderer's Sprite Sort Point to Pivot, the ground point, so
  characters sort by where they stand; with an emissive layer it adds a Sorting Group so the glow sorts
  with its sprite.
- URP 2D lights: the sprites carry the normal map as `_NormalMap`; with `Sprite-Lit-Default` and a light set
  to use normal maps, they shade by the light's position.
- Emissive parts are a child `Emissive` SpriteRenderer drawn with an unlit material over the sprite (the
  exact colours of the emissive map), so they glow in dark scenes. Set **Emissive Material** for another
  look (additive, as the Godot and MonoGame runtimes draw it, for example).

## 6. With an Animator instead

Each animation and direction also comes as an `AnimationClip` (`attack_ne`) that sets the sprite, the
emissive child's sprite (path `Emissive`) and `flipX`, with AnimationEvents calling `OnKilnEvent(string)`
on the GameObject. Build an Animator Controller from them if you prefer the state machine; `KilnAnimator`
does not need them (turn **Animation Clips** off in the importer to skip them).

The JSON format is documented in [format.md](../format.md).
