# From a splash art to a model

Goal: capture the character's **identity** (silhouette, proportions, striking shapes, palette), not the
brush strokes. At 64 px only what is big and contrasted survives. Read [workflow.md](SKILL.md),
[modeling.md](SKILL.md) and [spec.md](SPEC.md) first.

## 1. Prepare the reference
```
spritekiln new <name> --extends --ref <path/splash.png>   # <specs>/characters/<name>/ with splash.png; a humanoid
                                                      #    extends the template (drop --extends to copy it)
spritekiln ref prep <specs>/characters/<name>/splash.png    # -> splash_ref/: cutout.png, cutout_pitch38.png,
                                                      #    palette.yaml, ref.json (proportions)
```
- Look at the original splash **and** `cutout.png`. The background is removed from the border inwards, so
  flat, gradient and vignetted backgrounds work, and openings such as the gap between the legs stay
  transparent. If it cut wrong: try `--tol` 4–15 (colour step, default 9), ask for a PNG with
  transparency, or install the `splash` extra (rembg) for busy backgrounds.
- Decide which **direction** the art shows (front = `s`, 3/4 front = `se`/`sw`, profile = `e`/`w`).

## 2. Write the brief (top of the spec)
Before any geometry, fill `brief:` while looking at the image:
```yaml
brief:
  summary: one sentence on who this is and how they carry themselves
  reference: splash.png (seen from se)
  proportions: "head = 1/4 of the height; shoulders 1.6x the hips; short legs"
  head: "high ponytail past the shoulders, side-swept fringe, soft jaw, pointed chin; eyes only (face: minimal)"
  must_keep: [3-6 traits that identify the character from afar]
  simplify: [what will vanish or merge at 64 px]
  palette_notes: [dominant materials and colours]
```
At most 5–6 `must_keep`. Small ornaments become a colour spot or vanish. Exaggerate what is iconic (hat,
weapon, hair, cape): at 64 px, exaggeration is fidelity. The head is never a detail to drop: with stylized
proportions it is about a fifth of the sprite. `head` says what the splash's hair and face are, in the terms
of the head and hair kits, and how much face the project's style (`face`) shows.

## 3. Palette
`splash_ref/palette.yaml` has colour families with hue-shifted ramps ready (`fam1`, `fam2`...). Copy it to
the project's palettes folder as `<name>.yaml`, **rename** the ramps (skin, cloth, hair, metal...), drop
background or noise families and merge near-identical ones. Adjust with
`spritekiln palette ramp "#hex" --steps 5`. 3–6 materials plus one emissive is ideal. In the spec:
`palette: [gothic, ../../palettes/<name>.yaml]` (gothic brings the `fx_*` ramps and basics).

## 4. Blockout
Start from a template (`humanoid`, or `side_humanoid` for a side view) or a similar spec. Over a base, give
only the keys that change (`bones: {torso_rot: {pos: ...}}`, `ik: {leg_L: {lengths: [...]}}`):
1. **World scale:** total height 1.6–2.0; adjust the pelvis height (`torso_rot.pos`) and the IK lengths.
2. **Big masses:** torso, hips and legs as ellipsoids and cones; the head's size with the `head` bone
   scale (its shape and the hair come in step 5).
3. `pose --dirs all` and `ref compare <spec> <splash> --dir <dir>`.
4. Iterate until the **camera-corrected IoU ≥ 0.65** in the art's direction and no band hint is large.
   Each silhouette is scaled to its own bounding box, so a hat tip, a raised weapon or a flared hem moves
   the whole comparison: when an extremity changes, read the overlay on the sheet, not only the number.
   `ref compare` squashes the splash by cos(pitch) like the game camera sees a front view; against the raw
   splash the IoU tops out near 0.56, so do not chase raw numbers. The hints say at which height the sprite
   is too wide or too narrow: fix the part at that height. Do not chase IoU above ~0.85; the splash has its
   own perspective and pose, and legibility matters more.

## 5. Striking shapes and materials
First the **head and the hair**, as `brief.head` says: fit the `head` kit (`jaw`, `chin`, `width`) and a
hair kit (`hair`, `ponytail`, `bun`) with their params, or model them yourself ([modeling.md](SKILL.md),
"Heads, faces and hair"). Look at them with `pose --focus head --dirs all` next to the splash's face.

Then one `must_keep` at a time (horns = `tube`). A weapon, shield, helmet, hood, hat, cape, belt or pouch
starts from a kit (`spritekiln kits`; `use:` with its params, recoloured through materials); model your own
only when no kit comes close. After each one: `pose --dirs all`. Check the **8 directions**, not only the
art's; invent what the splash does not show, coherently, and record the decision in `brief`.

## 6. Final comparison and review
```
spritekiln ref compare <spec> <splash> --dir <dir>          # -> out/compare_<dir>.png + .json
spritekiln review <spec> --ref <splash> --ref-dir <dir> [--bg <game floor>] [--tint <scene light>]
```
Open the comparison sheet (reference | sprite | silhouette overlay | 8 directions | palettes) and the review
sheet. Then an art-direction pass ([art-direction.md](art-direction.md)); apply the high-priority fixes.

## 7. Animate
With the model approved, follow [animation.md](animation.md). The personality of the splash (heavy, agile,
arrogant) must show in the idle and in the timing of the attack.

## Pitfalls
- A splash with a dynamic pose (raised leg, raised weapon): compare against a similar animation frame
  (`--anim attack --frame 2`) instead of the rest pose.
- A cropped splash (no feet): the IoU is meaningless; compare only the proportions of the visible part and
  say so.
- A weapon bigger than the body: keep it out of the comparison (note it in the brief) and check margins in
  QA.
