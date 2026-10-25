# Modeling for legible pixel art

The renderer can draw anything; what survives at 64 px (top-down 3/4, pitch 38°) is a short list.

## Legibility rules
- **Big head** (1.2–1.4× real proportions) and a silhouette with **2–3 striking shapes** (horns, wings, a
  weapon, a cape, a hat). Details smaller than about 2 px (0.1 world units at `scale: 0.05`) vanish or turn
  into noise.
- **Thin parts:** a radius of at least ~0.025 at `scale: 0.05` (claws, blades); thinner breaks into dots.
- **Colours:** one ramp per material, 4–6 tones; few materials (3–6). Emissives (eyes, magic) are the
  accent. Value contrast between neighbouring materials matters more than hue.
- **Perspective:** things that stick out backwards or away rise on the screen. Check the diagonals: a thin
  piece seen edge-on becomes a stick; change its angle, or cheat per direction with `yaw`/`dir` in an
  expression.
- **Margins:** keep ≥ 2 px free around every frame (QA warns). If a frame clips, move `camera.center`,
  raise `size`, or reduce that gesture; change `camera.scale` only for the whole game.
- **Consistency:** never change one asset's camera `pitch`, `light` or density (`camera.scale`); the
  whole game shares them. A bigger creature gets a bigger `size`.

## Side view (`view: side`)
- The silhouette is the **profile**: what reads is the outline seen from the side (nose, hat brim,
  weapon length, cape, tail). Thickness along the line of sight (z) does not show; extend shapes along x
  and y instead.
- Only `e` and `w` are rendered, but the model is still 3D: both profiles must work, and the far arm and
  leg sit behind the body (darker, partly hidden). Check `pose` in both directions.
- No ground shadow by default (the ground is edge-on); the game usually draws its own.

## Procedure
1. Start from a template (`spritekiln new <name>`) or the closest existing spec. Fill `brief:` first (see
   [splash-to-model.md](splash-to-model.md)).
2. **Big masses first**: world scale (total height 1.6–2.0 for a human), pelvis height, IK lengths, then
   torso, head, hips and legs as ellipsoids and cones only.
3. Add the striking shapes one at a time (`chain` horns, `membrane` capes and wings, `box`/`cylinder`
   weapons in a hand frame, hair as blended ellipsoids). After each: `validate`, `pose --dirs all`, look.
4. Check **all 8 directions**, not only the reference's: the back and the profiles must make sense. Invent
   what the reference does not show, coherently, and write the decision in `brief`.
5. Materials and palette last-but-not-least: 3–6 materials plus one emissive; tune ramps with
   `spritekiln palette ramp "#hex" --steps 5`.

## Rules for a modeler (human or AI)
- Run `spritekiln style` first and model in the project's style: outline, shading, proportions, palette
  and colours ([style.md](style.md)). If no style is recorded, stop and report that the user has to answer
  the style questions first.
- Work only in the asked asset's spec. Iterate in small steps: edit → `validate` → `pose --dirs all` →
  **look at the PNG** → fix. Never call a model done without having seen the 8 directions.
- With a splash art: `ref prep` once, `ref compare` after every proportion change (targets in
  [splash-to-model.md](splash-to-model.md)).
- Keep the skeleton, channels and names the animations use. If you rename something, update the
  animations too and `validate`.
- Do not change `camera.pitch`, `camera.scale`, `light`, shared palettes or the project's style unless
  asked; an exception for this asset goes in its `brief:`.
- Do not render every animation while modeling; at most `render --anims idle --dirs s,e,n,se`.
- Report: what changed (parts, materials), IoU and hints left, image paths for review, and the design
  decisions taken where the reference shows nothing.
