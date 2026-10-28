# 15. Agent context budget

**Status:** proposed · **Track:** tokens · **Stage:** not scheduled yet · **Depends on:** 03, 04

## Problem
An asset session loads a lot of context before any useful work, and the recipe loads it again:

| what | size | about |
|---|---|---|
| the knowledge files, `docs/agent/*.md` (`spec.md` 11 KB, `style.md` 9 KB, `workflow.md` 6 KB...) | 45 KB | 11k tokens |
| one showcase spec | 24–41 KB | 6–10k tokens |
| one preview image | up to 1600 px | up to about 1.5k tokens |

On top of that:
- the recipe runs three agents (`docs/agent/recipe.md`: modeler, art director, animator), and each loads the
  knowledge and the spec again;
- the skills tell the agent to read whole reference files (`SPEC.md`, `style.md`) even for a one-line change;
- the art director looks at images even when numbers would answer.

## Goal
The same work with much less context:
- at most 4k tokens of knowledge on an agent's first turn, with the rest loaded when the task needs it;
- numbers before images;
- images pixel-exact and cropped ([03](03-pixel-exact-previews.md));
- specs read by outline and block ([04](04-spec-outline-and-show.md)).

## Proposal
1. **Layered knowledge.**
   - `docs/agent/core.md`, at most 4k tokens, is always loaded: the loop, the commands, the hard rules
     (style first, validate, look before calling it good, outputs are generated) and an index of what to
     read for which task.
   - `spec.md` is split by section (`spec/parts.md`, `spec/materials.md`, `spec/animation.md`...), and the
     index points to sections.
   - The generated adapters (`spritekiln/agents.py`, ADR-019) embed `core.md` and link the rest. The hard
     rules stay in `core.md`, so no adapter can drop them.
2. **Numbers first.**
   - `review --summary` (and MCP `review(summary=true)`) returns at most 40 lines of JSON: per direction,
     silhouette area and IoU, value contrast between materials, material shares, QA problems.
   - The docs say: read the summary, then ask for an image when it points to a problem.
   - Every visual decision and the final check still look at the images: numbers save tokens during
     iteration, never in place of looking.
3. **An image policy in the docs.**
   - Iterate with `pose --draft --dirs s,se,e,n` (4 views; [01](01-draft-preview.md)).
   - Look at all 8 directions only before `render`.
   - At the end, one contact sheet per animation.
4. **Recipe hand-offs carry paths, not files.**
   - The modeler hands the art director the outline, the changed blocks and the summary.
   - The art director returns fixes keyed by spec path (`parts.helm.prims[0]: lower 0.02`), so the next
     agent opens only those blocks.
5. **A reference task to measure with.** "Make a goblin with a spear, idle and walk, from this brief", run
   before and after.
   - Measure the input tokens of the session (from the client's usage report, or by counting the bytes of
     files and images the tools returned).
   - Have the maintainer review the result.

## Plan
1. Write the reference task and measure the baseline with the current files.
2. `core.md` and the split of `spec.md`; generator changes in `spritekiln/agents.py`; tests that every
   generated adapter contains the hard rules.
3. `review --summary`.
4. The image policy and recipe hand-offs in `workflow.md`, `recipe.md` and `art-direction.md`.
5. Measure again; repeat after [04](04-spec-outline-and-show.md), [09](09-surface-paint.md) and
   [14](14-kits-and-extends.md) land, since smaller specs also count.

## Validation
- **Tokens:** input tokens of the reference task down by at least 40 %.
- **Quality:** the result of the reference task is no worse, judged by the maintainer on the sheets and by
  QA.
- **Adapters:** generated adapters still pass `tests/test_tools.py` and `tests/test_update.py`.

## Risks and open questions
- **Agents may miss a rule they no longer see.** `core.md` keeps every hard rule; the reference task is the
  check.
- **Decided (2026-10-27): no model routing.** Every agent and every check, numeric ones included, keeps the
  model chosen for the session; ADR-019 ("the strongest model with image input") stands. Quality is the main
  goal: this proposal saves tokens only by reading less, never by using a weaker model.
