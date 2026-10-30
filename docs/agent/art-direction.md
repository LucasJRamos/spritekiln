# Art direction checklist

The art director **does not edit files**: they analyse and recommend. Input: the spec, the
`preview/contact_*.png` sheets, `qa.json`, the project's art style (`spritekiln style`), and when available
the splash art, `out/compare_<dir>.png` and a `review` report.

## Numbers first
```
spritekiln review <spec> --bg <game floor.png> --tint <scene light> [--against <other asset>]
                  [--ref <splash> --ref-dir <dir>] [--anims <clip,clip>]
```
`review.json` and `review.png` (plus `clip_<anim>.png`) give, per direction:

| number | what it tells | Hunt Tower reference |
|---|---|---|
| L* median / p90 (under `--tint`) | overall value of the sprite as the player sees it | was 10–12 on a floor of 12–18; the target set was ≥ 20 |
| contrast | sprite median minus floor median | negative = the sprite sinks into the floor |
| pixels per material | whether a key material survives in every direction | targets set: accent lining ≥ 30 px, skin ≥ 12 px |
| bands per material | which ramp tones a material actually uses | the session tracked the share of the coat in band 2 |
| colours | palette discipline | QA warns above the palette size + 12 |
| IoU (camera-corrected) | silhouette fidelity to the splash | 0.65–0.69 on the shipped Huntress |
| against: area ratio, L* deltas | legibility next to an approved asset | compare with an asset the team already likes |

Recurring numbers can become targets in the spec (`review: {min_lstar: 20, materials: {...}}`) so that
every render's QA warns about them.

## Evaluate, in this order
1. **Silhouette** at 1× in every direction (s, se, e, ne, n and mirrors): is the character recognisable?
   Any "stick", hole or shapeless blob? Diagonals and `n` are where things break.
2. **Head and face** up close: `pose --focus head --dirs all` (12×; a face is a few pixels on a 2–4× sheet
   and no number sees it). The head is not a ball: a fringe, locks, a chin, a ponytail or headwear break the
   circle in every direction. No bump under 2 px on the face (a 1 px nose plus its outline reads as a big
   nose). The eyes show wherever the face does. The hair has locks and lines, not a cap. The face follows the
   style's `face` and the `brief.head`. A fix never adds a feature smaller than its part's `blend`: it swells
   into a lump.
3. **Fidelity to the reference** (if any): do the brief's `must_keep` show? Proportions (IoU and the band
   hints)? Is the palette coherent with the art?
4. **Pixel art:** banding or pillow-shading noise, contrast between materials, outline, emissives, colour
   count, details under 2 px. **Value against the game's floor** (`review` with `--bg`/`--tint`).
5. **Animation:** arcs, anticipation, impact (smear), follow-through, weight, seamless loops, timing in ms,
   consistency across directions, events and timing targets.
6. **The project's style** ([style.md](style.md)): density, view and pitch (`spritekiln style` lists specs
   that differ), outline, shading, proportions, palette and animation feel. A deviation is a high-priority
   fix unless the spec's `brief:` records it as an exception the user asked for.
7. **QA:** blocking errors and warnings.

## Output
A short verdict (approved / approved with reservations / redo) and at most 8 fixes, each with a priority
(high/medium/low), where (direction/frame), the problem, and the concrete change in the spec, e.g.
"parts.horn_L chain: raise the 2nd radius from 0.045 to 0.055", "attack keys[2]: ms 170 → 220",
"materials.coat: bands [1, 4] → [2, 5] (median L* 9 → ~16)".
