# 16. Heads, faces and hair

**Status:** done (added to release 0.3 on 2026-10-30) · **Track:** quality · **Stage:** 4 (release 0.3) ·
**Depends on:** 14

## Problem
The maintainer tested the 0.3 build in two new game projects (a side-scroller at 48 px and a top-down game at
64 px). Both results were "far better than before", and both shared one flaw: the first female character of
each project had a **head that read as a ball** and a **"big nose"** nobody asked for. Fixing them took
another modeling round after the user pointed them out; the second attempt was good. So the tools could do
it, but the default path did not ask for it.

The evidence:
- **The template is the starting point, and its head is a ball.** `humanoid` and `side_humanoid` model the
  head as a near-sphere (0.15 × 0.16 × 0.15) with a jaw ellipsoid hidden inside it and a `sphere r 0.025`
  nose; the hair is three ellipsoids hugging the skull. The duelist's modeler read the template at 18:31 and
  wrote her head at 18:39 as the same three primitives with numbers changed by at most 0.005, nose and
  `# nose` comment included. The huntress's first spec did the same (nose `r 0.02`). With `extends`, a spec
  that writes nothing inherits that head without even seeing it.
- **The docs teach round heads and nothing else.** modeling.md's "Which shape for what" put the head with
  `ellipsoid, cone, sphere`; modeling.md's procedure and splash-to-model.md said "torso, head, hips, legs:
  ellipsoids and cones only" and "hair = blended ellipsoids". The new shapes of 0.3 got recipes for swords,
  hats, hoods and capes, none for a face or hair.
- **The side view asked for a nose.** modeling.md's "Side view" said the profile reads through "nose, hat
  brim...". The art director saw the problem ("the head reads as a bald round ball in profile") and fixed it
  with the tool the docs named: the nose went from `r 0.022` to `0.03`. At 48 px the head is about 9 px
  tall; the nose is 1.5 px, the part's `blend` (1.5 px) swells it instead of sharpening it, and the outline adds
  1 px: 2–3 px out of the face, about a quarter of it.
- **Reviews do not see faces.** The art-direction checklist had no item for the head; sheets are 2–4×, where
  a face is a few pixels; the numbers (IoU, pixels per material) are blind to the shape of a head, and a
  `hair: {min_px: 160}` target rewarded mass (the ponytail became a sausage). The orchestrating session put
  the face last of six `must_keep`s, though a stylized head is about a fifth of the sprite.

## Goal
A first generation whose head and hair read as the character, without the user having to name the problem:
the default head is not a ball, faces follow the project's style, and a review cannot pass a head it has not
looked at up close.

## Proposal
Three layers, from the one that changes most results to the safety net.

1. **A good starting point: the head and the hair are kits.**
   - `head` kit (`at: head`): one part named `head` (so `parts.head` overrides keep working) built from a
     cranium, a face plane and a jaw tapering to a chin, with params `jaw`, `chin`, `width`, `nose` (0 by
     default: none) and `ears`.
   - Hair kits: `hair` (crown, fringe, temple locks and back as separate parts, so the renderer draws lines
     between them; params `fringe`, `part`, `locks`, `length`, `volume`, `size`), `ponytail` (a chain with
     channels for the animator) and `bun`. Their `hair` material has no `bands`, so the style's shading
     applies, and a fallback `hair` ramp, so a palette with a `hair` ramp colours them.
   - Both templates `use` the head and hair kits instead of plain parts. `eye_L` stays a plain part (specs
     override it, sometimes only its material).
2. **Instructions that teach faces.**
   - modeling.md: a section "Heads, faces and hair" (rules in pixels, the kits, the recipe by hand); the
     shape table, the procedure and the side view no longer ask for round heads or noses. splash-to-model.md:
     the head and the hair get their own pass, first among the striking shapes.
   - The style interview gets a question **face**: `minimal` (eyes only, no nose: anime and most pixel art;
     recommended), `simple` (a brow or nose hint on heads of 14 px or more), `detailed` (heads of 20 px or
     more). `spritekiln style set --face`, MCP `style`.
   - `brief.head`: the hair, the jaw and chin and how much face, in the terms of the kits.
3. **Checks that catch it before the user does.**
   - `validate` warns when a character over a built-in template has no `brief.head` (its head and hair are
     placeholders until the spec decides them), and when a spec replaces the prims of an inherited kit's part
     while the kit's other parts stay (`parts.hair.prims` under the hair kit's fringe and locks).
   - `pose --focus <bone|parts>` (MCP `pose` `focus`): a close-up at up to 12× of a bone and everything below
     it; `--focus head` shows the head, hair, eyes and headwear in every direction.
   - The art-direction checklist gets "Head and face" as its second item, judged with `--focus head`; the
     recipe gets a step where the user sees the model (8 directions and the head close-up) before anything is
     animated, and hand-offs carry the splash, the description and the brief.

## Plan
1. `head` and `hair` kits and both templates (a `character-modeler` agent; checked in 8 directions top-down
   and e/w side, at the template density and at 48 px side and 64 px top-down).
2. `ponytail` and `bun` kits on the new head (a second modeler).
3. `pose --focus`, the `validate` warnings, `brief.head` in `new --extends`, the `face` style field.
4. Docs: modeling.md, splash-to-model.md, style.md, art-direction.md, recipe.md, workflow.md, spec.md.
5. `pixel-art-director` review of the head and hair kits; fixes.
6. Examples: the cacador and the knight state their `brief.head`; goldens refreshed for the new template
   head (cacador).

## Validation
- Before/after sheets of the template head (top-down 8 directions, side e/w, 1× and close-up) and of each
  kit's params at their extremes, approved by the maintainer.
- Headwear kits (`helmet`, `hood`, `hat`) still cover the new hair; the knight reads as before or better.
- The maintainer's next first generation in a test project: the head and the hair read as the character
  without a correction round.

## Risks and open questions
- **Specs that extend a template and wrote their own hair** (the two test projects) gain the hair kit's
  fringe and locks on top of theirs: `validate` warns and says to remove `use.hair`. Released specs are not
  affected (`extends` is new in 0.3), and Hunt Tower's specs are copies, not bases.
- The cacador example changes look (it inherits the template head); its goldens are refreshed on purpose.
- After 0.3 the head and hair kits are frozen like the others (design 14's rule): a visual change needs a new
  name.

## Outcome (2026-10-30): done
- Kits (CC0), each reviewed by a `pixel-art-director` agent and fixed:
  - `head`: a cranium, a face plane, cheeks and a jaw cone with `elongate`; params `width`, `jaw`, `chin`, `nose`
    (0 by default; a `line: false` wedge of at most a 1 px step at 40-64 px) and `ears`.
  - `hair`: the crown and back, a fringe of three strands, temple locks and a back piece as separate parts
    (`line: false` on the 1-2 px locks); params `fringe`, `part`, `locks`, `length`, `volume`, `size`. Its
    `hair` material is matte with no `bands`, so the style's shading applies; a brown fallback ramp.
  - `ponytail`: a tie, a pouf when high and three locks on a chain with the channels `swing`, `lift`, `sway`
    (prefixed by `as`); a `cheat` swings it aside near `s`, so a high tail does not stand up as a horn. The
    review found it popping between two shapes in the template's walk in `se` (the cheat's pulse was steepest
    at 45°): narrowed and tucked. `bun`: one bun or two (`double`), standing off the hair with a wrapped strand.
- The review of the head found the lower face reading as a beard in profile under soft shading (the shaded
  skin tone equalled the hair's): the templates' `skin` got `gamma: 0.75`. The side template's eye moved
  inside the face; the face plane stopped scaling with `width` (it buried the eyes).
- `pose --focus <bone|parts>`, the `brief.head` and kit-part warnings, the `face` style field, `kits <name>`
  printing a kit's channels, and the docs as proposed.
- **Dry run of the maintainer's case.** A fresh `character-modeler` agent, in a scratch side-view project
  with the cyberpunk test's style (48 px, toon, neon palette, `face: minimal`), got the same splash and
  description as the first duelist and no word about heads. On its first pass it wrote `brief.head`, fitted
  the head kit (`jaw: 0.1, chin: 1`), the hair kit (short back, a lock at one temple) and the ponytail kit,
  and delivered a head with no nose, a fringe, a chin and a ponytail in strands: the problem of the first
  test did not appear. Its own notes: the ponytail hangs straight at rest (the clips do not drive its
  channels yet), and a lot of silver at the hip in `w`.
- Found while packaging: the sdist did not include `specs/kits/`, so `python -m build` (what the release
  workflow runs) failed to build the wheel from it; fixed in `pyproject.toml`.
- Specs written with the unreleased 0.3 build that extend a template change: a spec that wrote its own hair
  gets the kit's fringe, locks and back until it removes `use.hair`; `remove: [materials.hair.bands]` fails
  (the templates no longer define `hair`; the kit does).
