# SpriteKiln in MonoGame

The MonoGame runtime is one C# file plus an optional shader, so it also works in FNA or any XNA-style
code with small changes. Tested with MonoGame 3.8.4 (DesktopGL) on .NET 8. A finished project is in
[`examples/monogame`](../../examples/monogame): a gargoyle that walks, attacks and is lit by a point light
through its normal map.

## 1. Add the runtime

Copy into your project:

- [`integrations/monogame/KilnSprite.cs`](../../integrations/monogame/KilnSprite.cs): `KilnSheet` (loads a
  render) and `KilnAnimator` (plays it).
- [`integrations/monogame/KilnLit.fx`](../../integrations/monogame/KilnLit.fx), only for dynamic lights: add
  it to `Content.mgcb` with the Effect importer and processor.

## 2. Export a sprite

[Install SpriteKiln](../tutorials/install.md) (Windows, macOS or Linux), then:

```
spritekiln init --engine monogame          # once, in the game folder: specs in art/specs, exports in Content/sprites
spritekiln new knight
spritekiln render art/specs/characters/knight/knight.yaml --export
```

`Content/sprites/knight/` receives `knight.png`, `knight_normal.png`, `knight_emissive.png` and `knight.json`.
They are loaded at run time, not through the content pipeline: copy them to the output folder.

```xml
<None Include="Content/sprites/**" CopyToOutputDirectory="PreserveNewest" />
```

## 3. Play it

```csharp
var sheet = KilnSheet.Load(GraphicsDevice, Path.Combine(AppContext.BaseDirectory, "Content/sprites/knight/knight.json"));
var knight = new KilnAnimator(sheet);
knight.OnEvent += (anim, ev) => { if (ev == "hit") DealDamage(); };
knight.OnFinished += anim => knight.Play("idle");

// Update
knight.Play(velocity == Vector2.Zero ? "idle" : "walk");   // restarts only when the animation changes
knight.FaceTowards(velocity);                               // screen vector, y down
knight.Update(gameTime);

// Draw (position = the ground point under the character; sort by Y for depth)
spriteBatch.Begin(samplerState: SamplerState.PointClamp);
knight.Draw(spriteBatch, position);
spriteBatch.End();
spriteBatch.Begin(blendState: BlendState.Additive, samplerState: SamplerState.PointClamp);
knight.DrawEmissive(spriteBatch, position);                 // eyes, magic: stays bright
spriteBatch.End();
```

- Frame-0 events fire inside `Play()`; the others when their frame becomes visible, from the exact
  per-frame durations. `Update(double ms)` advances by hand for fixed-step games.
- `TryGetSocket("strike", out var offset, out var depth)`: offset in pixels from the ground point (times your
  draw scale), `depth > 0` in front of the body.
- Specs with `mirror: true`: `Draw` flips the mirrored directions around the pivot and `TryGetSocket`
  mirrors the sockets.
- Draw at integer scales (`scale` argument) or into a small render target scaled up, as the example does.

## 4. Dynamic light with the normal map

`KilnLit.fx` shades sprites with up to 4 point lights and an ambient colour. Draw one sheet per batch, since
the normal map is an effect parameter:

```csharp
lit.Parameters["MatrixTransform"].SetValue(Matrix.CreateOrthographicOffCenter(0, width, height, 0, 0, 1));
lit.Parameters["NormalMap"].SetValue(sheet.NormalMap);
lit.Parameters["Ambient"].SetValue(new Vector3(0.42f, 0.4f, 0.52f));
lit.Parameters["LightPos"].SetValue(new[] { new Vector3(lightX, lightY, 40) });   // z = height in px
lit.Parameters["LightColor"].SetValue(new[] { new Vector3(1f, 0.86f, 0.68f) });
lit.Parameters["LightRadius"].SetValue(new[] { 110f });
lit.Parameters["LightCount"].SetValue(1);
spriteBatch.Begin(samplerState: SamplerState.PointClamp, effect: lit);
knight.Draw(spriteBatch, position);
spriteBatch.End();
```

Mirrored sprites get their normals mirrored by the shader. For the floor or other art without a normal map,
set `NormalMap` to a 1×1 texture of `(128, 128, 255)` (facing the viewer).

The JSON format is documented in [format.md](../format.md).
