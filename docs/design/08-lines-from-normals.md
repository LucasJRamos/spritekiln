# 08. Lines from normals, edge highlights

**Status:** done (stage 3) · **Track:** quality · **Stage:** 3 (release 0.3) · **Depends on:** 06

## Problem
Inner lines (step 2 of `compose`, `spritekiln/pixelize.py`) appear only where two **different** groups meet
with a depth jump over 0.06 (0.25 on diagonals). So:
- a crease inside one smooth-unioned part never gets a line: an elbow fold, the edge of a plate, a hood's
  rim over the face when hood and face are one part;
- a part that folds over itself (a cape seen from the side) gets no line either;
- convex edges facing the light get no highlight.

Lines and edge highlights from normals and depth are what make 3D-rendered pixel art look drawn rather than
blurred. t3ssel8r's 1 px outlines and convex highlights work this way, as do ProPixelizer's normal-edge colour
and PixelOver's "Normal line". The normal of every pixel is already computed; today it is only exported as the
normal map.

## Goal
Optional crease lines, self-overlap lines and edge highlights, set per material and per project style. They
never make lines thicker than 1 px.

## Proposal
Rules on 4-neighbouring pixels of the **same** group:
- **Crease:** the angle between the two normals is over `crease_angle` (default 50°) and the edge is
  concave → the pixel farther from the camera becomes a line (its material's `line_band`).
- **Convex edge:** the normals open apart (convex) and the edge faces the light → the brighter pixel goes one
  band up (`edge_highlight`).
  - Convexity sign: `(n_b - n_a) · d_ab`, with `d_ab` the screen direction from a to b, lifted to 3D in the
    camera plane.
- **Self-overlap:** the depth jumps over a threshold (default 0.06, as between parts) → line on the far side.

Fields:
- material: `crease: true|false` and `edge_highlight: true|false`. Default: from the project style, otherwise
  `false`, so existing specs render as today;
- style ([11](11-render-style.md)): `lines = "depth" | "depth+normal" | "none"`;
- spec: `render: {crease_angle: 50}`.

Clean-up:
- drop line runs shorter than `min_run` px (default 2): PixelOver's "Polish";
- keep the L-corner rule the outline already uses.

## Plan
1. Vectorised neighbour rules in `compose`, which is at most 5 % of a frame today.
2. Fixtures: a box (sharp edges, so lines and highlights), a sphere (no creases), a torus (a concave ring),
   and two primitives smooth-unioned at a sharp angle.
3. Fields, schema and validation; the hook for [11](11-render-style.md).
4. Docs: `docs/agent/modeling.md` on when to turn creases off (cloth, organic shapes).
5. Before/after on the templar's armour and the gargoyle's wings.

## Validation
- The fixtures above, as goldens.
- With the fields absent, the existing goldens are pixel-identical.
- Before/after sheets approved.

## Risks and open questions
- Smooth blends between primitives (joints) can produce noisy short lines. `crease_angle`, `min_run`, and
  `crease: false` on organic materials handle it. Tune the defaults on the showcase.
- Edge highlights and material highlights (07) can stack on the same pixel: material highlight wins.

## Outcome (2026-10-28): done
- `pixelize.folds`: on right and down neighbours of the same part, a concave fold sharper than `crease_angle`
  marks the farther pixel; a convex edge facing the light lifts the brighter pixel one tone (below a
  highlight's reserved tone); runs shorter than `min_run` are dropped. Material fields `crease`,
  `edge_highlight`; spec `render: {crease_angle, min_run}`.
- The self-overlap rule ("a jump in depth") first drew lines on a sphere's silhouette, where a grazing surface
  changes depth fast: it now compares the jump with the slope the normals predict (-s (n.d3) / (n.D)) and only
  between pixels that face the camera.
- On the Templar's armour and the gargoyle's stone the lines and edge lights add definition at the joints;
  the effect is moderate at 64-96 px. Tests: an L-shaped block gets a crease line, a sphere none, edge
  highlights only lighten. Off by default: goldens unchanged.

