# Roadmap

**v0.1 (now):** characters and props from YAML specs in 8 directions (top-down 3/4) or a side view;
animation by expressions and by keys, with events, timing targets and smears; sockets; normal and emissive
maps; Aseprite-compatible JSON; automatic QA and an art-direction review; splash art → model workflow;
instructions for coding AIs and an MCP server; Godot, Unity and MonoGame runtimes.

Ideas for later versions, roughly in order. Open an issue to discuss one before working on it.

## 1. Environments and tiles (v0.2)
Same renderer, same camera and light, so floors and walls match the characters.
- `kind: tile` with `grid: {w: 1.0, d: 1.0}`: the camera is locked to the tile size (e.g. 32 px wide =
  1 unit), rendered in one direction.
- **Dual-grid floor tilesets (15/16 pieces):** the spec describes materials A and B (stone / dirt) and a
  border function; the generator renders the 16 corner combinations (4-bit mask) and lays out the sheet,
  with 3–4 variations per piece from `noise(seed)` to break repetition.
- **Modular walls** (top-down 3/4 shows top and face): straight, inner corner, outer corner, end, door,
  with a height in units; faces get the same light.
- **Seamless edges:** render with a margin and crop the centre; a QA check compares opposite edges.
- **Side view:** platforms, slopes and parallax backgrounds for side-scrollers.
- Export: atlas + JSON with autotile rules (optional Tiled `.tsx`, Godot TileSet).

## 2. Environment props
Already works with `kind: prop` and `directions: 1` (or 4/8 for props that turn). Next: a library of base
specs (torch, coffin, statue, door, gate, gravestone, candelabra, chest) and simple animations (a flame
flickering with `noise`, a door opening).

## 3. Effects (VFX)
- Particle primitives: `burst` (n seeded emissive spheres), `ring` (a growing torus), `trail` (a cone along
  a curve), `beam`.
- Stand-alone VFX animations (impact, magic, blood, footstep dust) exported as their own atlas with a pivot,
  for the game to spawn on events (`hit`, `step_l`) at sockets.
- Optional ordered dithering for translucent VFX only (smoke, fog).

## 4. Lighting
- Done in v0.1: dynamic 2D light through the normal map in MonoGame (`integrations/monogame/KilnLit.fx`),
  Godot (`CanvasTexture`) and Unity (`_NormalMap`).
- A "flat albedo" render (no baked light) for games lit entirely at run time.
- Local lights in the spec (a character's own torch) through `light.points`.

## 5. Tool and workflow
- `spritekiln watch`: re-render `pose` when the YAML is saved (a fast loop for hand editing).
- A local HTML viewer (animation, direction, zoom, background, onion skin) reading the exported JSON.
- Speed: per-part caching and optional numba (5–10×) for 128 px characters.
- More engines with ready runtimes (Phaser, Defold, Bevy) on top of the generic guide.
