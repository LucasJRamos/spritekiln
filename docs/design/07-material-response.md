# 07. Material response: highlights, rim, thresholds

**Status:** done (stage 3) · **Track:** quality · **Stage:** 3 (release 0.3) · **Depends on:** 06

## Problem
Light reaches `compose` as one value, and `band_of` (`spritekiln/pixelize.py`) maps it onto the material's ramp
with `gamma` and `bands`. Every material answers light the same way.

So the templar's armour reads like matte stone next to its linen. And the main tool a pixel artist uses to say
"metal", a small hard highlight cluster, does not exist. Rim light is one global strength (`light.rim_strength`).

## Goal
Materials that read as what they are at 48–96 px:
- metal with a hard, small highlight;
- leather and skin with a soft one;
- cloth matte.

Each is chosen with one field an AI can pick from a table.

## Proposal
New material fields, all optional. Without them a material looks as it does today.

```yaml
materials:
  iron:  {ramp: iron, finish: metal}                                 # a preset
  gold:  {ramp: gold, highlight: {band: 5, size: 0.93, max_px: 3}}   # explicit
  linen: {ramp: linen, finish: matte}
  skin:  {ramp: skin, finish: soft, rim: 0.2}
  stone: {ramp: stone, thresholds: [0.25, 0.5, 0.75]}                # toon cut points instead of gamma
```

- **`highlight`:** Blinn-Phong `n·h` with the camera direction, thresholded. Pixels above `size` (a cosine)
  take ramp index `band`, or `color` when given.
  - `max_px` keeps highlight clusters small: the brightest pixels win.
  - `min_px` drops clusters smaller than it (default 1).
  - Never on outline or inner-line pixels.
- **`rim`:** the rim strength for this material (default: `light.rim_strength`).
- **`thresholds`:** explicit light-to-band cut points (toon shading). When given, they replace `gamma`.
- **`finish`:** presets that expand to the fields above:

  | finish | highlight | rim | for |
  |---|---|---|---|
  | `matte` | none | low | cloth, stone, fur |
  | `soft` | wide, top band | medium | skin, leather, wood |
  | `metal` | small, hard, top band | high | armour, blades, coins |
  | `glossy` | small, top band | medium | gems, lacquer, eyes |

  Fields given next to a `finish` override it.

## Plan
1. In the shading pass ([06](06-geometry-buffer.md)), compute `n·h`. In `compose`, map highlight pixels after
   the bands and before lines and outline.
2. Schema (`spritekiln/data/spec.schema.json`), defaults (`DEFAULT_MATERIAL` in `spritekiln/spec.py`) and
   validation: `band` inside the ramp, thresholds increasing, sizes in range.
3. Highlight clusters: `max_px` and `min_px`, reusing the cleanup helpers of `compose`.
4. Docs:
   - the finish table in `docs/agent/modeling.md`;
   - an art-direction check in `docs/agent/art-direction.md`: metal shows a highlight in the directions
     facing the light;
   - style ([11](11-render-style.md)) can turn highlights off for a whole project.
5. `review`: the share of each material's pixels in its highlight band.
6. Port the templar's iron and gold and the huntress's buckles on a branch; before/after sheets.

## Validation
- Fixture: a `metal` sphere has one highlight cluster at the expected place and size in all 8 directions.
- `review`: highlight pixels stay within 8 % of a material's pixels by default.
- Before/after sheets of the templar approved.

## Risks and open questions
- The light is fixed in the world and the model turns, so highlights move with the direction. This is
  consistent, but it can flicker in animation. Mitigated by `max_px`, `min_px` and
  [10](10-thin-parts-and-stability.md).
- Should `finish: metal` also lower the shadow side by one band (more contrast)? Decide on the before/after
  sheets.

## Outcome (2026-10-28): done
- `finish` presets (matte, soft, metal, glossy) expand into `highlight` and `rim`; explicit fields win.
  `highlight: {size, max_px, min_px, band, color}` uses `render.facing` (n.h, Blinn-Phong) and
  `pixelize.clusters` to keep clusters small; `rim` per material; `thresholds` for toon steps.
- Found on the Templar: a highlight in the ramp's top tone did not read, because the lit side already used that
  tone. A material with a highlight now keeps its top tone for it (the light uses the tones below), as pixel
  artists do: with `finish: metal` on iron and gold the armour reads darker and metallic, with small hard
  highlights on the pauldrons, arms and knees.
- Tests: a metal ball shows 1-4 top-tone pixels on its upper half in all 4 directions (a plain one shows more
  than 8); toon thresholds; rim per material; validation of highlight bands and thresholds.
- Without these fields every spec renders as before (goldens unchanged).

