# 19. Agent context by role (15, rewritten)

**Status:** done (2026-11-11), released in 0.4.0; the measurement on reference tasks
is still to run · **Track:** tokens · **Replaces:** [15](15-agent-context-budget.md) ·
**Depends on:** 03, 04, 17, 18

## Problem
[15](15-agent-context-budget.md) wanted the same work with much less context and was rejected for how it got
there: numbers before images, a 4k core with an index, drafts in four directions and hand-offs as paths all
let an AI lose visual detail without noticing. Its review left a list of what is safe. The cost it described
is still there, and larger (`docs/agent/` grew from 45 KB to 78 KB in 0.3):

| read before any work (0.3.0) | bytes |
|---|---|
| modeler: its prompt, `SKILL.md`, `SPEC.md`, `style.md`, the splash skill | 76,159 |
| art director: its prompt, `SPEC.md`, `style.md` | 44,377 |
| animator: its prompt, `SKILL.md`, `SPEC.md`, `style.md` | 47,605 |

A recipe run starts six agents (each role twice: the work, then the fixes): about 336 KB, some 84k tokens,
before a single pixel. Three things in it are waste by construction:
- `style.md` is mostly the interview, which a subagent cannot run (it cannot talk to the user);
- the animator reads the whole spec reference, two thirds of which is geometry it must not touch;
- the agent that applies a list of fixes is a new one: it reads everything again and knows none of the
  reasons behind the model it is fixing.

And during iteration, `pose --dirs all` returns eight directions after every edit, most of them identical to
the ones just seen.

## Goal
Remove what is read or rendered twice. Nothing an agent needs to see is taken away:
- the modeler keeps the whole modeling knowledge and the whole spec reference (15's review: unusual designs
  need the less obvious tools, and an agent that has not read about them falls back to generic shapes);
- images stay the judge; no check is routed to numbers alone;
- no weaker model (ADR-019 and the decision of 2026-10-27 stand).

## Proposal
1. **Knowledge by role.**
   - No agent reads `style.md`. Its prompt carries the section "What the style means for each asset" (the
     table of answers against modeling, animation and review) and tells it to run `spritekiln style` for the
     recorded answers.
   - The animator reads `SPEC-animation.md`: the sections of the spec reference it works with (units,
     expressions, channels, snap, mirroring, bones, IK, animations, sockets, timing), generated from `spec.md`
     by `spritekiln/agents.py`. The whole `SPEC.md` stays in its skill folder for the day a clip needs a part.
   - The modeler reads the splash skill only when it works from a splash.
   - The art director's prompt no longer says "top-down, 64-96 px, 8 directions": it judges at the project's
     view and size, and its table of numbers marks one game's values as an example.
2. **Continue an agent instead of starting a new one for the same role.** The recipe's fix steps go to the
   agent that did the work (in Claude Code, `SendMessage`); the agent prompts say that a continued agent does
   not read its files again. This is also a quality change: the agent that fixes knows what it tried.
3. **A second director round that checks fixes**, fix by fix, instead of reviewing from scratch (LL3M's
   verification agent: a critic's fixes are only worth something if someone checks they were applied).
4. **`pose --changes`.** The last pose of each kind is kept next to the render cache. With `--changes`, the
   image holds only the directions whose pixels differ from it, the earlier pose above the new one, and the
   text names the directions that are identical. Lossless: the renderer is deterministic, so an identical
   direction is the image already seen. It also answers "did my edit do anything" (a typo, an occluded part).
   Milestones (before a hand-off, before `render`) still take the full pose.
5. **Measure.** `SPRITEKILN_USAGE=<file>` makes every CLI command and MCP tool call append what it handed to
   the AI (bytes of text, images with their sizes); `spritekiln usage` sums it per command with a token
   estimate. This is step 1 of 15's plan, which never ran.

## What stays rejected from 15
Numbers before images; a core of 4k tokens with an index for the modeler; drafts in four directions as the
iteration default; hand-offs that carry paths without the splash and the `brief`.

## Validation
- Generated adapters: `python -m spritekiln.agents --check`, `tests/test_init.py`, `tests/test_update.py`
  (`update --files` keeps `SPEC-animation.md`).
- `tests/test_checks.py`: `pose --changes` (nothing to compare, nothing changed, an eye made bigger changes
  the front and not the back), the usage log.
- **Still to do, with the maintainer:** three reference tasks off the templates (a non-humanoid, an asymmetric
  detailed character such as the cyborg, a stylised splash), run before and after with `SPRITEKILN_USAGE`
  set, the results judged trait by trait on the images. Until then the numbers below are file sizes, not
  measured sessions.

## Risks and open questions
- **An animator that needs a part reads the slice and misses the rule.** The slice's introduction and the
  agent prompt point at `SPEC.md`; the animator's rules already forbid changing geometry beyond what a clip
  needs.
- **A continued agent carries a long context.** If it went wrong or ran out, the recipe says to start a new
  one with the full hand-off (spec, splash, the user's words, the list).
- **`--changes` could become a habit of never looking at the whole.** The loop, the modeler's rules and the
  MCP tool description all keep the full pose at milestones.

## Outcome (2026-11-11): done, measurement pending
| read before any work | 0.3.0 | now |
|---|---|---|
| modeler (with a splash) | 76,159 | 72,386 |
| modeler (from a brief) | 76,159 | 65,626 |
| art director | 44,377 | 38,816 |
| animator | 47,605 | 18,144 |
| a recipe run: six new agents before, three continued now (with a splash) | 336,282 | 129,346 |

The docs themselves grew by about 5 KB with designs 17 and 18 (new checks and commands), which is why the
modeler's figure moves little: its saving is the 11 KB of interview it no longer reads. The recipe figure
(about 84k tokens down to about 32k) is where continuing agents shows.
