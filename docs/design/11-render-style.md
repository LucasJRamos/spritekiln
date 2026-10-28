# 11. Render style presets

**Status:** proposed · **Track:** quality, tokens · **Stage:** 3 (release 0.3) · **Depends on:** 06, 07, 08, 09, 10

## Problem
The project style (`[style]` in `spritekiln.toml`, `spritekiln/style.py`) records `outline` (selective, dark,
none) and `shading` (soft, flat), but the renderer never reads them. `docs/agent/style.md` tells the AI to apply
them by hand to every material:
- a shared near-black at index 0 of every ramp for `dark`;
- `outline: false` everywhere for `none`;
- ramps of 3–4 tones with `bands: [2, 3]` for `flat`.

That costs tokens, drifts between assets, and changing the style means editing every spec. There is also no
way to choose line style, highlights, dithering or the character of the light per project. The style range of
SpriteKiln is fixed by the renderer's single look.

## Goal
Style as render parameters:
- the project style drives every asset's look at render time;
- a spec or a material can override it;
- switching the style re-renders a whole asset from the geometry cache ([06](06-geometry-buffer.md)) in
  seconds.

## Proposal
`[style]` gains render fields, recorded by `spritekiln style set` and by the interview:

```toml
[style]
outline = "selective"       # selective | dark | colored | none   (now applied by the renderer)
outline_color = "#120d16"   # for dark
shading = "soft"            # soft | flat | toon   -> default bands or thresholds per material (07)
lines = "depth"             # depth | depth+normal | none   (inner lines, 08)
highlights = true           # material finishes produce highlights (07)
dither = "none"             # none | bayer2 | bayer4   (between neighbouring bands, in part space)
light = "classic"           # classic | top | dramatic | soft | flat
snap = false                # whole-pixel snapping of root and torso (10)
```

- **Precedence:** material field > the spec's `render:` block > project style > built-in defaults. A project
  without these fields renders exactly as today.
- **Outline modes:**
  - `dark`: one shared colour around the silhouette;
  - `colored`: each material's own line colour (`line_color`);
  - `none`: no outer outline.
- **Dither:** ordered Bayer between two neighbouring bands, near band borders only, indexed by part-local
  coordinates. The pattern sticks to the surface instead of crawling under it. It can be turned off per
  material (`dither: false`).
- **Light presets:** a table of light direction, ambient, rim and shadow softness:
  - `classic`: today's top-left;
  - `top`: overhead, short shadows;
  - `dramatic`: low side light, high contrast;
  - `soft`: high ambient, low contrast;
  - `flat`: albedo for engine lighting.

  A preset that changes the direction re-traces shadows only ([06](06-geometry-buffer.md)).
- **`spritekiln style preview <spec>`:** the same pose under 3–4 presets side by side, from the geometry cache,
  so the user can choose with the AI by looking.
- **The interview** (`docs/agent/style.md`) gets one question about finish and light: lines, highlights,
  dither, light preset, with the recommended answer first. `outline` and `shading` stop being manual
  instructions.

## Plan
1. Style fields, choices and validation (`spritekiln/style.py`); `style set` flags; the MCP `style` answers.
2. `spec.load` merges the style's render defaults into materials and light; the spec's `render:` block and
   material fields override.
3. Outline modes and dither in `compose` (dither needs `local` from 06); light preset table.
4. `style preview`.
5. Docs:
   - rewrite the table "What the style means for each asset" in `docs/agent/style.md`: the AI no longer edits
     materials for outline and shading;
   - regenerate the adapters.
6. `style` keeps listing specs whose explicit fields contradict the project style.

## Validation
- A project with no new fields: goldens pixel-identical.
- The minimal fixture rendered under each preset, as small goldens.
- Switching the style of the templar re-renders all its frames from a warm cache in at most 0.3 s per frame
  (presets that change the light direction re-trace shadows).

## Risks and open questions
- **Hunt Tower's specs carry hand-applied style.** The precedence (spec values win) keeps their look.
- **Too many knobs.** Presets come first; single fields are for experts. Should there be named bundles?
  For example, `preset = "crisp-16bit"` setting several fields at once, inspired by dddpix's "Clean Pixel",
  "Dithered Retro" and "Strong Outline". Decide after trying the fields on the showcase.
