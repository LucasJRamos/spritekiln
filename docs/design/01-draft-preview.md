# 01. Draft preview

**Status:** done (9b050a7) · **Track:** speed · **Stage:** 1 (release 0.3) · **Depends on:** nothing

## Problem
The working loop is edit → `validate` → `pose` → look ([`docs/agent/workflow.md`](../agent/workflow.md)). `pose`
renders every pixel with the spec's camera: 3×3 supersampling, with a pixel filled when 4 of its 9 samples hit
(`DEFAULT_CAMERA` in `spritekiln/spec.py`, `to_pixels` in `spritekiln/render.py`).

Measured on the templar (96 px, rest pose): 4.6 s of ray marching per direction with 9 samples per pixel,
0.69 s with one (6.7×). An 8-direction pose costs about 45 s uncached. Most iterations only ask "is the
silhouette right? is the arm in the right place?", and one sample per pixel answers that.

## Goal
An opt-in preview at least 5× faster than `pose`, for iterating on forms and poses. The final check before
`render` and `render` itself keep 3×3.

## Proposal
- `spritekiln pose --draft` and MCP `pose(draft=true)` render with `supersample: 1, coverage: 1`, whatever
  the spec says.
- The output is marked as a draft without touching its pixels: the file name gets `_draft`
  (`pose_idle_0_draft.png`) and the MCP JSON carries `"draft": true`.
- The camera is part of the render cache key (`spritekiln/cache.py`), so draft entries never mix with full
  ones.
- `render --draft` previews motion: GIFs and contact sheets only, written to `out/<name>/preview-draft/`. It
  writes no atlas, JSON or QA, so a draft can never reach an engine through `export`.
- Docs: iterate with `--draft`; run one full `pose --dirs all` before `render`.

## Plan
1. `api.pose(..., draft=False)` overrides `camera.supersample` and `camera.coverage` on a copy of the spec.
   `pipeline.get_spec` caches the spec dict, so it must not be mutated.
2. CLI flag, MCP parameter, `_draft` suffix, the JSON field.
3. `render --draft`: a path in `pipeline.render_all` and `export.export` that writes previews only.
4. `docs/agent/workflow.md` and `animation.md` (the loop); regenerate the adapters (`spritekiln/agents.py`).

## Validation
- Test: on the fixtures, draft and full poses agree on the part id of at least 95 % of the pixels opaque in
  both.
- A draft golden for the minimal fixture.
- Benchmark: templar `pose --dirs all`, uncached, before and after (target at least 5×).

## Risks and open questions
- Thin parts (antennae, blades under about 1/3 px) can vanish or flicker in a draft. That is why the docs
  require one full pose before `render`; [10](10-thin-parts-and-stability.md) addresses thin parts in
  general.
- Should MCP `pose` default to draft? Proposed: no. The AI asks for it explicitly, and the docs recommend it
  for silhouette and pose work.

## Outcome (2026-10-27): done
`pose --draft`, `render --draft` (previews only, `preview-draft/`, cannot be exported), MCP `draft=true`.
Measured, 8 directions, uncached: Templar 14.7 s → 5.1 s, Huntress 8.4 s → 3.9 s, gargoyle 8.3 s → 4.3 s.
That is 2–3× over the full pose **after** design 02 (7× over the pose before stage 1), short of the 5× goal:
once 02 made ray marching cheaper, the fixed costs (start-up, rig, compose) weigh more. The fast backend (12)
is where the rest comes from. Parts agree with the full render on at least 95 % of the pixels both fill.
