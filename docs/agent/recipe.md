# The recipe: from a splash art to an animated, reviewed sprite

This is the workflow that produced the Templar and the Huntress for Hunt Tower. It works with any coding AI:
the roles can be separate agents (subagents) or one AI changing hats, as long as each step's output is
saved and the next step reads it.

| step | role | does | reads | done when |
|---|---|---|---|---|
| 0 | main session (first asset of a project) | interviews the user about the art style and records it | [style.md](style.md) | `spritekiln style` shows the recorded style |
| 1 | modeler | brief, palette, blockout, striking shapes | [splash-to-model.md](splash-to-model.md), [modeling.md](modeling.md) | 8 directions look right; corrected IoU ≥ 0.65 |
| 2 | art director (model round) | numbers + critique, ≤ 8 fixes | [art-direction.md](art-direction.md) | verdict written |
| 3 | modeler | applies the high-priority fixes | the director's list | fixes visible in `pose` |
| 4 | animator | animations, events, timing targets, sockets | [animation.md](animation.md) | QA clean on the clips |
| 5 | art director (animation round) | critique of the clips | contact sheets, GIFs, `review --anims` | verdict written |
| 6 | animator | applies the fixes | the director's list | QA clean |
| 7 | anyone | `render`, then `export` | | atlas, JSON and engine files in place |

In the Hunt Tower session the model round caught the overall value (the Huntress was too dark for the
floor), the wine-red lining as the accent colour, the face under the hat brim and an asymmetric hat; the
animation round caught the rifle and pistols vanishing in direction `s`, the weapon swap going over the
shoulder, and the mine placement.

## Hand-offs
- Subagents cannot ask the user anything: the main session runs the style interview (step 0) before it
  delegates, and every role follows the recorded style.
- The director never edits: they return a list of fixes with concrete spec changes.
- Every step reports the paths of the images it produced, so the next one can open them.
- Keep the spec's `brief:` up to date with decisions (what the reference does not show, cheats per
  direction), so a later session understands the choices.

## AIs that see images, and AIs that do not
The workflow is best with an AI that can **look at images**: silhouette, readability and animation feel are
judged on `pose` PNGs and contact sheets. An AI that cannot see images can still do the job with numbers:
`validate` (structure), `ref compare` (IoU and band hints), `review` (value, contrast, pixels per material,
bands, legibility against another asset) and `qa.json` (clipping, seams, identical frames, timing). Set
`review:` targets in the spec so the numbers say when something is off. A human should still glance at the
final contact sheets.

## Cost control
- Iterate with `pose` (about a second per direction); render whole animations only when the model is
  approved, and only the animations that changed (`--anims`). That render's atlas holds only those clips:
  finish with a full `render` (fast, from the cache) before `export`.
- On a machine with little free memory, `render` sizes the worker pool automatically; `--jobs 1` is
  always safe and the cache resumes interrupted renders.
