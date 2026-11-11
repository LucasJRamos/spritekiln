# 17. Checks for what an AI's eyes miss: traits, hidden and floating parts, colour

**Status:** done (2026-11-11), released in 0.4.0 · **Track:** quality ·
**Depends on:** 09 (paint counts for its material), 10 (QA metrics)

## Problem
The loop relies on an AI looking at small images, and three kinds of defect get past it:
- **A `must_keep` trait that stops reading.** `brief.must_keep` is free text that no code reads. The numbers of
  `review` are aggregates (area, IoU, pixels per material): a 3 px lens, a feather or an emblem changes none of
  them, which is why design 15's "numbers first" was rejected. The only check was the art director's eye, once
  per round, and a later edit or a new clip could lose the trait again without anyone looking.
- **A part that vanishes for a few frames.** In the Hunt Tower session the rifle and the pistols disappeared
  in direction `s` during an attack; the animation round caught it by looking at a contact sheet of
  frames × directions. QA said nothing.
- **A part that floats.** A hand off its arm or a pauldron above the shoulder is a few pixels of gap at 64 px.
  It is also the typical defect of procedural models written by language models: 3DCodeBench (arXiv
  2606.01057) finds that renders that succeed "still suffer from disconnected or floating 3D geometric
  components", and LL3M (arXiv 2508.08228) notes that a visual critic "may miss subtle spatial artifacts".

And one gap in the comparison with a splash art: `ref compare` scores the silhouette only. A coat in the wrong
colour, or a sprite far darker than the art, scores a perfect IoU.

## Goal
Exact, cheap checks that point at the place to fix, so the images are spent on what only eyes can judge. They
add to looking, never replace it: every visual decision and every final check is still made on the images.

## Proposal
1. **Pixels per part.** Every rendered frame counts the opaque pixels of each part (`Frame.parts`), beside
   the count per material it already has.
2. **`review.keep`: a `must_keep` trait as a check.**
   ```yaml
   review:
     keep:
       amber_lens: {parts: [lens], min_px: 4, dirs: [s, se, e, ne]}
       red_core: {materials: [core], min_px: 6}
   ```
   A trait names the parts and/or materials that show it, the fewest pixels at which it reads (default 4) and
   the directions where it must show (default: all; a lens on the left half of a face is hidden from the
   right). QA and `review` warn where the median over a pose's frames is below `min_px`, and QA warns where a
   trait that shows in a clip has no pixel at all in some of its frames. `review.json` lists each trait's
   pixels per pose and direction. The names are validated (unknown part, with a "did you mean").
3. **Hidden parts.** For every clip and direction, QA lists the parts that show at least 8 px in some frame
   and none in others (`qa.json` `info.hidden`), and the QA summary names them. Information, not a warning: a
   hand passing behind the body is often right. Parts with a `when` are left out.
4. **Floating parts.** `validate` warns about a solid part of the rest pose that is more than 1.5 px away from
   every other solid part. `floating: true` on a part silences it (an orb, a halo). Emissive parts, smear arcs
   and parts with a `when` are skipped.
5. **Colour by height in `ref compare`.** The typical colour of each of the ten height bands (the ones the
   width profile uses) of the splash and of the sprite; a hint where the sprite is much darker, much lighter or
   another colour (OKLab), neighbouring bands with the same finding merged. `review --ref` reports the same.

## Validation
- Tests: `tests/test_checks.py` (per-part counts, `keep` targets and name checks, hidden parts, floating
  parts with and without `floating: true`, band colours and hints, `ref compare` on a recoloured splash).
- No false positive of the floating check on the repository's specs (templates, examples, showcase,
  fixtures); a hand moved 0.16 units off its wrist is reported at 2 px.
- The full test suite and the goldens pass unchanged: no pixel changes.

## Risks and open questions
- **Hints on colour can mislead.** A splash is painted under its own light. The hints are worded as places to
  look and the docs say so; at most four are printed.
- **`keep` needs someone to write it.** The modeler's procedure, the splash-to-model steps, the recipe and the
  art director's checklist all ask for it; a `must_keep` without an entry is a fix the director requests.
  Tying them automatically (matching trait text to part names) was not attempted: it would guess.
- **The floating check looks at the rest pose only.** A part that separates in an animation is not seen; the
  hidden-parts list and the images cover clips.

## Outcome (2026-11-11): done
- `Frame.parts`; `review.frame_stats` carries `parts`; `review.keep` in the schema, `validate`, `review`
  (`keep` table) and QA (median below `min_px`; hidden in single frames).
- `qa.json` `info.hidden` and its line in the QA summary.
- `spritekiln/checks.py`: a seeded search (600 points in the part's bounding sphere, four refinements around
  the point nearest to the other parts), about 0.1 s for the Templar's 36 groups; `parts.<name>.floating`.
- `ref.band_colors` and `ref.color_hints`; `colors` and `color_hints` in the result of `ref compare`.
- `pipeline.py` is part of the render cache key (ADR-011), so caches made before this change are rendered
  again once.
- Not done: clips as kits. `extends` already brings a template's clips (idle, walk and attack top-down; ten
  clips in `side_humanoid`); more top-down clips (run, hurt, death) are template work that needs the
  maintainer's eye and is listed in the roadmap.
