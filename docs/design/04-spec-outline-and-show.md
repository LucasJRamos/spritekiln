# 04. `spec outline` and `spec show`

**Status:** done (05d303d) · **Track:** tokens · **Stage:** 1 (release 0.3) · **Depends on:** nothing

## Problem
To change one part, an AI reads the whole spec, and the recipe's agents (modeler, art director, animator)
each read it again:

| spec | lines | size | about |
|---|---|---|---|
| cacador | 215 | 8 KB | 2k tokens |
| templar | 496 | 24 KB | 6k tokens |
| huntress | 742 | 41 KB | 10k tokens |

Validation errors already point to `file:line:column`, but nothing gives the AI a map of the file to jump to
the block it needs.

## Goal
An AI finds and reads only the blocks it edits. The map of the largest showcase spec fits in about 1.5k
tokens, and any block can be printed by its path.

## Proposal
- `spritekiln spec outline <spec>`: one line per item of each section, with its line range and a short
  summary. `--json` gives the same as data. For example:
  ```
  materials   33-41   iron iron_dk linen cape_linen lining cross gold leather holy holy_core
  parts.helm  239-243 material iron, space head, 2 prims
  parts.cape  152-164 material cape_linen, space capebase, 1 prim, 7 cuts
  parts.arm_R         mirror of parts.arm_L
  animations.walk 400-452  8 frames, loop, 640 ms
  ```
- `spritekiln spec show <spec> <path>...` prints the source text of those blocks with their line numbers:
  comments kept, a slice of the file and never a re-dump. Paths look like `parts.helm` or
  `animations.walk.keys[2]`.
  - `--resolved` prints the block as the renderer sees it: mirrored, and expanded once
    [14](14-kits-and-extends.md) exists.
- MCP tools `spec_outline` and `spec_show`.
- Line ranges come from the YAML node marks the loader already keeps for `file:line:column` errors
  (`spritekiln/schema.py`, `spritekiln/spec.py`).
- Docs: step 1 of the loop becomes "outline, then show what you will edit". Reading the file with an
  offset and a limit is also fine.

## Plan
1. A map from node path to start and end line, built while composing the YAML.
2. The outline summariser and the `show` slicer.
3. CLI, MCP and docs (`docs/agent/workflow.md`; regenerate the adapters).
4. Tests on the fixtures: the ranges match, and `show` returns exactly the file's lines.

## Validation
- The outline of the huntress is at most 6 KB.
- Bytes read to change one prim of the templar's helm (outline + show) are at most 25 % of reading the file.

## Risks and open questions
- Mirrored `_R` items have no lines of their own: the outline names their `_L` source.
- Flow-style blocks (`{...}` on one line) are shown whole, so that line's neighbours are not split.

## Outcome (2026-10-27): done
Outline sizes: Huntress 6.1 KB (spec 40.6 KB), Templar 4.0 KB (23.9 KB), gargoyle 2.3 KB (13.5 KB). Items of
an itemized section are listed by name under it; `spec outline --json` gives full paths. MCP tools
`spec_outline` and `spec_show`.
