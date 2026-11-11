# The recipe: from a splash art to an animated, reviewed sprite

This is the workflow that produced the Templar and the Huntress for Hunt Tower. It works with any coding AI:
the roles can be separate agents (subagents) or one AI changing hats, as long as each step's output is
saved and the next step reads it.

| step | role | does | reads | done when |
|---|---|---|---|---|
| 0 | main session (first asset of a project) | interviews the user about the art style and records it | [style.md](style.md) | `spritekiln style` shows the recorded style |
| 1 | modeler | brief, palette, blockout, striking shapes, `review.keep` for the `must_keep` traits | [splash-to-model.md](splash-to-model.md), [modeling.md](SKILL.md) | 8 directions look right; corrected IoU ≥ 0.65; `validate` clean |
| 2 | art director (model round) | critique + numbers, a line per `must_keep` trait, ≤ 8 fixes | [art-direction.md](art-direction.md) | verdict written |
| 3 | the same modeler, continued | applies the high-priority fixes | the director's list | fixes visible in `pose --changes` |
| 3b | the same director, continued (when a fix was high priority) | checks the fixes one by one | "Checking fixes" in art-direction.md | every high-priority fix done |
| 4 | main session | shows the user the model: `pose --dirs all` and `pose --focus head --dirs all` | | the user approves it (or asks for changes: back to 3) |
| 5 | animator | animations, events, timing targets, sockets | [animation.md](animation.md) | QA clean on the clips |
| 6 | art director (animation round) | critique of the clips | `arcs`, contact sheets, GIFs, `review --anims` | verdict written |
| 7 | the same animator, continued | applies the fixes | the director's list | QA clean |
| 8 | anyone | `render`, then `export` | | atlas, JSON and engine files in place |

In the Hunt Tower session the model round caught the overall value (the Huntress was too dark for the
floor), the wine-red lining as the accent colour, the face under the hat brim and an asymmetric hat; the
animation round caught the rifle and pistols vanishing in direction `s`, the weapon swap going over the
shoulder, and the mine placement.

## Hand-offs
- Subagents cannot ask the user anything: the main session runs the style interview (step 0) before it
  delegates, and every role follows the recorded style.
- The director never edits: they return a list of fixes with concrete spec changes.
- **Continue an agent instead of starting a new one for the same role.** The modeler that built the model
  applies the director's fixes (step 3), the animator that wrote the clips applies theirs (step 7), and the
  director that wrote a list checks it (step 3b): send the list to the agent that is already there (in Claude
  Code, `SendMessage` to it; elsewhere, the same conversation or thread). It still holds the instructions, the
  spec, the splash and what it tried, so it reads nothing again and repeats no dead end; a new agent starts by
  loading all of that and knows none of the reasons. Start a new one only when the earlier one is gone or went
  wrong.
- A hand-off to a **new** agent carries: the spec path, the splash path and which direction it shows, the
  user's own words about the character, the `brief` (it is in the spec), and for fixes the director's list
  as written. A director gets the image paths to open (`pose`, `pose --focus head`, the comparison or contact
  sheets) so it does not render them again.
- The user sees the model before anything is animated (step 4): a face or a hairstyle they dislike costs one
  model round there, and every clip after the animations.
- Hand-offs carry the splash, the user's description and the spec's `brief` (with `head`), not only paths:
  the face and the hair are where a generic answer slips in.
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
Quality comes first: none of this trades a look at the image for a number, or a strong model for a cheaper
one. It removes what is read or rendered twice.
- Iterate with `pose` (about a second per direction); render whole animations only when the model is
  approved, and only the animations that changed (`--anims`). That render's atlas holds only those clips:
  finish with a full `render` (fast, from the cache) before `export`.
- After an edit, `pose --dirs all --changes` returns only the directions whose pixels changed. A direction it
  calls identical is the image already seen; milestones (before a hand-off, before `render`) still get the
  full pose.
- Judge a clip's motion on its `arcs` sheet before opening the contact sheet: one image instead of frames ×
  directions, and it shows arcs and spacing better.
- Let `validate` and QA find what they can find exactly (floating parts, traits under their pixels, hidden
  parts, seams), so the images are spent on what only eyes can judge.
- Read a long spec by `spec outline` and `spec show`; continue agents instead of starting new ones.
- To measure a session, set `SPRITEKILN_USAGE=<file>` before it and run `spritekiln usage` after: the text
  and images the commands and MCP tools handed to the AI, per command, with a token estimate. Compare the
  same task before and after a change of workflow, and judge the result of both on the images.
- On a machine with little free memory, `render` sizes the worker pool automatically; `--jobs 1` is
  always safe and the cache resumes interrupted renders.
