# 10. Thin parts and frame stability

**Status:** done (stage 2) · **Track:** quality · **Stage:** 2 (release 0.3) · **Depends on:** nothing

## Problem
**1. Thin parts vanish.** A pixel is filled when 4 of its 9 samples hit (`coverage`), and the group with the
most samples wins it (`to_pixels`, `spritekiln/render.py`). A blade, antenna or strap thinner than about 1/3 px
in front of the body loses every vote. It disappears, or breaks into dots that change from frame to frame.

**2. Pixels boil.** Parts move by fractions of a pixel between frames (bob, breathing, slow sways), so the same
surface lands on different pixel boundaries and bands, and clusters flicker even when the motion is small.
- Dead Cells' team still lists flickering pixels as unsolved in their 3D pipeline.
- t3ssel8r's renderer snaps the camera to the pixel grid.
- SpriteKiln has no snapping, and QA has no number for flicker.

## Goal
- Weapons and thin details survive in every direction and frame.
- Holds and slow loops do not boil.
- QA reports both.

## Proposal
**Weighted votes.** Part fields:
- `priority`: the weight of the part's samples in the vote (default 1). A sword gets 3.
- `min_cover`: a pixel where this part has at least N samples (default: the camera's `coverage`) is filled
  even below the global coverage, and goes to this part if it wins the weighted vote. Thin details get 2 or 1.

**Pixel snapping.** `snap: {frames: [root, torso_rot]}` (spec, or the project style of
[11](11-render-style.md)):
- for each listed rig frame, the screen projection of its translation **relative to the previous rest
  position** is rounded to whole pixels, and the remainder is removed from that frame (its children follow);
- small bobs become whole-pixel steps, the pixel-art convention;
- parts with their own sub-pixel motion (arms, a cape) are left free.

**A `boil` QA metric.** For each loop and each held pose, it counts pixels that change band or colour between
consecutive frames while their part, local position and normal barely moved. It is reported per animation and
direction in `qa.json`, with a warning threshold. `docs/agent/art-direction.md` explains how to read it.

## Plan
1. `to_pixels`: weighted votes and per-group `min_cover` (vectorised, as now).
2. Snapping. `rig.build` gets the camera projection, or a post-build pass moves the listed frames and their
   subtrees by the rounding remainder. Root motion (`root` channel) and the shadow stay consistent.
3. `boil` in `spritekiln/qa.py`, from the geometry buffer of consecutive frames ([06](06-geometry-buffer.md)
   gives local position and normal). Before 06, an approximation: band changes inside pixels whose part did
   not change.
4. Fixtures:
   - a thin blade crossing in front of a body, in 8 directions;
   - an idle with a 0.3 px bob.
5. Docs: when to raise `priority`, and when to snap.

## Validation
- The thin blade is visible in all 8 directions, at least 1 px wide along its length.
- The `boil` of the huntress and templar idles goes down with snapping; report it before and after.
- Without the new fields, goldens are pixel-identical.

## Risks and open questions
- **A high `priority` makes weapons look thicker than modeled.** The default stays 1; the docs suggest 2–3
  only for parts under 1 px.
- **Snapping changes the feel of slow motion** (steps instead of drift). It stays opt-in; the style interview
  asks for it with the animation question ("fluid" vs "snappy").
- Should the snap also round rotations of small parts? Not now.

## Outcome (2026-10-27): done
- `priority` and `min_cover` per part (`render.to_pixels` weights the vote; the default path is unchanged).
  Fixture `tests/fixtures/thin`: a staff of radius 0.007 at `scale: 0.05` showed 0-4 px per direction; with
  `priority: 3, min_cover: 2` it shows 6-26 px in every direction (`min_cover: 1` alone: 8-28 px).
- `snap: [frames]` (top level, `root` and bones; spelled as a list rather than `{frames: [...]}`): the frame's
  screen offset from the rest pose is rounded to whole pixels in the rig, so its children, the parts and the
  sockets follow; it is part of the render cache key.
- `boil` in QA is the share of inner pixels that change colour for one frame and change back (A B A, emissive
  pixels left out); a warning at 4 % when consecutive silhouettes overlap at least 95 %. Measured (8
  directions): idles 3.0-5.2 %, runs 8-14 % (silhouettes moving: no warning). With `snap: [root, torso_rot]`:
  Templar idle 3.0 % -> 1.6 %, Huntress idle 4.1 % -> 1.9 %, gargoyle idle 5.2 % -> 6.7 % (its wings move on
  their own): snapping stays opt-in and the docs say to check the number. A simple "share of pixels that
  change" was tried first and dropped: it counts real motion (20-55 % everywhere).
- The style question about snapping came with design 11 (stage 3).

