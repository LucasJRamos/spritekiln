# Roadmap

**v0.4 (now):** characters and props from YAML specs in 8 directions (top-down 3/4) or a side view;
animation by expressions and by keys, with events, timing targets and smears; sockets; normal and emissive
maps; Aseprite-compatible JSON; automatic QA and an art-direction review; splash art → model workflow;
instructions for coding AIs and an MCP server; an art-style interview before a project's first asset,
recorded in `spritekiln.toml`; `spritekiln update`; Godot, Unity and MonoGame runtimes. New in v0.3: tight
bounds and exact soft shading; an optional numba backend (`spritekiln[fast]`); shape operators and new
primitives (`extrude`, `revolve`, `tube`, `plane`); thin parts and frame stability (`priority`, `snap`, a
`boil` QA metric); a geometry buffer, so light and material changes re-render from the cache; material
finishes; creases and edge highlights; surface paint; the art style applied by the renderer, with
`spritekiln style preview`; draft and pixel-exact previews; `spec outline` and `spec show`; bases
(`extends`) and kits, 20 of them built in; a head and hair kit set, with `pose --focus head` and a face
question in the style interview.

New in v0.4: `review.keep` (a `must_keep` trait tied to its parts and
checked by QA), parts hidden in some frames of a clip, a warning for floating parts, colour against the splash
in `ref compare`; `spritekiln arcs` and the ground speed of a walk; `pose --changes`; agents that read by role
and are continued for fixes; `spritekiln usage` (designs [17](design/17-traits-and-geometry-checks.md),
[18](design/18-motion-on-one-sheet.md), [19](design/19-agent-context-by-role.md)).

Ideas for later versions, roughly in order. Open an issue to discuss one before working on it.

## 1. Environments and tiles (v0.5)
Same renderer, camera, light, materials and art style, so floors and walls match the characters.
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
- Done in v0.1: dynamic 2D light through the normal map in MonoGame (`integrations/monogame/KilnLit.fx`)
  and Godot (`CanvasTexture`); Unity gets the normal map as `_NormalMap` for URP 2D lights (not tested
  yet with URP).
- Done in v0.3: a "flat albedo" render (no baked light) for games lit entirely at run time:
  `light: {mode: flat}`, or `light = "flat"` in the project style.
- Local lights in the spec (a character's own torch) through `light.points`.

## 5. Tool and workflow
- Measure the agent workflow on reference tasks off the templates (a non-humanoid, an asymmetric detailed
  character, a stylised splash) with `SPRITEKILN_USAGE`, before and after design 19, judged trait by trait.
- More clips in the top-down `humanoid` template (run, hurt, death), so `extends` brings them as it does for
  `side_humanoid`; clips for weapons other than the sword.
- A linear-stance option for walks (even ground speed) for big sprites.
- `spritekiln style ask`: the art-style questions in the terminal, for users who work without an AI.
- `spritekiln watch`: re-render `pose` when the YAML is saved (a fast loop for hand editing).
- A local HTML viewer (animation, direction, zoom, background, onion skin) reading the exported JSON.
- Speed: per-part caching for 128 px characters (the optional numba backend came in v0.3).
- More engines with ready runtimes (Phaser, Defold, Bevy) on top of the generic guide.
