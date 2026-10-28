# 11. Render style presets

**Status:** done (stage 3) · **Track:** quality, tokens · **Stage:** 3 (release 0.3) · **Depends on:** 06, 07, 08, 09, 10

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

## Outcome (2026-10-28): done
- `spec.load` resolves `render` = built-in defaults < the project style < (`style preview`'s choice) < the
  spec's `render:` block, and turns it into material defaults (`outline`, `line`, `crease`, the finishes'
  highlights, `bands`/`thresholds`, `dither`, `line_color`), the light preset and `snap`. A material's own fields
  win. Defaults equal the old look: no golden changed.
- Outline modes: `dark` takes `outline_color` or the darkest first tone of the spec's ramps, chosen by its
  brightest channel (by luma a dark red beat the palette's near-black on the Templar); `colored` takes each
  material's `line_band` tone; a material's `line_color` wins in every mode.
- `shading: flat` takes a material's two lightest tones, `toon` its three lightest with steps at 0.3 and 0.6;
  the top tone stays a highlight's. On 5-6 tone ramps flat lightens the shadow side: contrast moves between
  materials, as flat pixel art has it.
- Dither: ordered Bayer (2x2, 4x4) with an amplitude of half a tone (values within a quarter tone of a border
  mix), after the orphan cleanup (which would take a checker for noise), only on pixels whose four neighbours
  are the same part and material (dithering 1 px gold trims made them dotted). The pattern is indexed by
  screen pixels from each part's projected origin, not by part-local coordinates as proposed: a pattern in 3D
  coordinates sampled on the pixel grid aliases on slanted surfaces, and anchoring on the origin already makes
  it move with the part (a ball moved 2 px renders identical, dither included). The `local` channel planned
  for it in [09](09-surface-paint.md) was dropped.
- Light presets are a table of `dir`, `rim_strength`, `ambient` and `mode`; the spec's `light:` keys win.
- `snap = true` gives specs without a `snap:` list `[root, torso_rot]` (`[root]` without that bone).
- `spritekiln style preview [spec] [--field ...]` and the MCP tool `style_preview`: one row per field, a column
  per choice, the current one marked; the humanoid template (copied to a temporary folder, so no cache lands
  in the package) without a spec. Switching the Templar's style re-renders its 64 idle frames from a warm cache
  in 0.03-0.04 s per frame (target 0.3).
- `style` lists specs whose `render:` block sets a look field to another value than the style's.
- Tests (`tests/test_render_style.py`): no style no change, precedence, shading tones, outline colours, dither
  near borders only and moving with the part, snap, recording the new fields, a record made before them, and a
  golden of the minimal fixture under every choice.
- Open: named bundles (`preset = "crisp-16bit"`) were not added; the fields are few enough with the preview.

