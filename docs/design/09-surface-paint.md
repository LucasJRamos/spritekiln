# 09. Surface paint

**Status:** done (stage 3) · **Track:** quality, speed, tokens · **Stage:** 3 (release 0.3) · **Depends on:** 06

## Problem
Surface detail is modeled as geometry. In the templar, 13 of its 36 groups exist mainly to put a colour on a
surface. Their parts take about 70 of the spec's 496 lines:
- the three crosses (`cross_chest`, `cross_flap`, `cross_back`);
- the gold trims (`helm_gold`, `pauldron_trim_L/R`, `hammer_bands`);
- `cuff_L/R`, `belt`, `buckle`, `visor`, `haft_iron`.

`cross_back` alone is a cone shell with 11 boxes cut away to leave a cross.

What it costs:
- **Render time:** every group is evaluated at every ray-march step near its bound. A thin shell with 11 cuts
  is one of the most expensive parts of the frame for one colour.
- **Tokens:** the AI writes and re-reads those blocks.
- **Quality:**
  - an overlay shell must sit slightly above the surface, so it either gets inner lines from the depth offset
    or needs `line: false`;
  - thin overlays lose the pixel vote ([10](10-thin-parts-and-stability.md));
  - overlays can poke through the surface they cover when it moves.

## Goal
Colour regions on a part without new geometry: a paint layer evaluated only on the surface points that were
hit. It costs nothing during ray marching.

## Proposal
```yaml
parts:
  cape:
    material: cape_linen
    space: capebase
    prims: [...]
    paint:
      - material: cross                   # a volume: paints the surface inside it
        prims:
          - box: {c: [0, -0.45, -0.4], half: [0.05, 0.32, 0.3]}
          - box: {c: [0, -0.30, -0.4], half: [0.21, 0.05, 0.3]}
      - material: gold
        stripes: {axis: y, at: [-1.05], width: 0.035}     # one band near the hem
      - material: iron_dk
        grid: {axes: [x, y], spacing: [0.08, 0.1], r: 0.012, seed: 3}   # rivets
```
(values are illustrative)

- **Volumes:** `prims` reuse every primitive (and the operators of [13](13-shape-operators.md)), written in
  the part's `space`. A surface point inside the volume (distance ≤ 0) is painted.
- **Patterns**, all in part-local coordinates, so they move with the bone and stay put across frames:
  - `stripes`: an axis with a period or explicit positions, and a width;
  - `rings`: around an axis;
  - `grid`: dots such as rivets and studs, with spacing and radius;
  - `spots`: noise, with a seed and a density;
  - `checker`.
- **Order:** later layers win over earlier ones.
- **Pixel decision:** each hit sample gets its paint material. A pixel takes the majority among the winning
  group's samples (the same vote as parts), stored as the `paint` channel ([06](06-geometry-buffer.md)).
- **Lighting:** paint keeps the part's lighting (normal, shadow, AO) and uses its own ramp.
- **Borders:** `edge: true` draws a 1 px line between paint regions, in the darker material's `line_band`.
- **Mirroring:** paint on `_L` parts is mirrored like prims.
- **Validation:** `validate` warns when a paint region is thinner than 1 px at the spec's `camera.scale`.

## Plan
1. Each `Group` keeps the inverse transform of its part frame (`rig.build` has it), so hit points map to
   part-local coordinates. This is shared with `local` in [06](06-geometry-buffer.md).
2. Evaluate paint on hit samples in the geometry pass; vote per pixel; the `paint` channel.
3. `compose` uses the paint material for ramp, lines and outline colour (selout takes the painted material).
4. Schema and validation; mirroring; an `outline` summary line for paint layers ([04](04-spec-outline-and-show.md)).
5. Port the templar's crosses, gold trims and bands, and the huntress's belts, on a branch. Count groups, lines
   and frame time before and after; before/after sheets.
6. Docs: a "paint before geometry" section in `docs/agent/modeling.md`, saying when detail needs geometry (it
   changes the silhouette or casts a shadow) and when paint is enough.

## Validation
- Fixture: a sphere with stripes; the stripes sit at the same local positions in all 8 directions and across
  the frames of a rotation.
- Templar port (estimates to verify): groups 36 → at most 28; spec lines down by at least 10 %; frame time
  down by at least 15 %.
- Mirroring and schema tests.

## Risks and open questions
- **Paint cannot change the silhouette.** A raised trim or a buckle that sticks out still needs geometry; the
  docs say so.
- **Thin paint regions alias like thin parts.** The width warning and `priority` of
  [10](10-thin-parts-and-stability.md) help.
- **Should paint also offer `normal` tweaks?** For example, a painted groove that darkens like a crease.
  Not now; [08](08-lines-from-normals.md) covers real creases.

## Outcome (2026-10-28): done
- `spritekiln/paint.py`: layers of a volume (`prims`) or a pattern (`stripes`, `rings`, `grid`, `spots`,
  `checker`) evaluated on hit samples after either backend, in the part's own space (`Group.frame`, mirrored
  for `_R` twins). The geometry buffer gains `paint`, the majority layer among the winner's samples (cache
  format 7). A per-pixel part-local position was tried for [11](11-render-style.md)'s dithering and dropped:
  dither anchors on the part's projected origin instead, which keeps the pattern a clean pixel grid.
- `compose` takes the paint's material for ramp, highlight, lines, selout and the orphan-pixel cleanup (which
  now needs the same part and the same material); `aux_maps` makes emissive paint glow; `review` counts
  painted pixels for the paint's material; `spec outline` lists a part's paint layers.
- `edge: true` lines use the paint material's `line_band` (not the darker of the two materials: the line sits
  on the painted side, which is the region the layer outlines).
- `rings` are concentric by distance from the axis; a band around an arm or a column at some height is
  `stripes` along that axis (the first test confused the two).
- Templar demo (crosses only, a box volume through the cloth for each): 40 → 37 parts, 25 → 14 cuts, 496 →
  482 lines, the same picture in the 8 directions; geometry pass 0.463 → 0.407 s/frame with numba (-12 %),
  2.35 → 1.74 s with numpy (-26 %). The estimate of 36 → 28 groups assumed porting the trims and bands too:
  the showcase stays as Hunt Tower ships it, so the port of the rest waits for a showcase update.
- Tests (`tests/test_paint.py`): bands at the same rows in all 8 directions, no new group, mirroring, every
  pattern, emissive paint, unknown material and the 1 px width warning. No paint, no change: goldens and the
  showcase hashes unchanged.

