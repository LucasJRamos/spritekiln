# MonoGame example

A gargoyle made with SpriteKiln (`specs/characters/gargula/gargula.yaml`) walking and attacking in 8
directions with `KilnAnimator`, lit by a point light through its normal map (`KilnLit.fx`), with glowing
eyes and a spark at the `strike` socket on the `hit` event.

```
dotnet run
```

Arrow keys (or WASD) move, Space attacks, Esc quits. Needs the .NET 8 SDK; MonoGame comes from NuGet.

The runtime and the shader are linked from `integrations/monogame/` (see `KilnDemo.csproj` and
`Content/Content.mgcb`): copy them in when you move this project out of the repository. `sprites/gargula/`
was written by `spritekiln export specs/characters/gargula/gargula.yaml --engine monogame --to examples/monogame/sprites`.

The walkthrough is in [docs/engines/monogame.md](../../docs/engines/monogame.md).
