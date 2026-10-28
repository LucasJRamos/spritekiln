# 03. Pixel-exact previews for AIs

**Status:** done (2f40ff7) · **Track:** tokens, quality · **Stage:** 1 (release 0.3) · **Depends on:** nothing

## Problem
- **The AI is shown distorted pixel art.** `_png` (`spritekiln/mcp_server.py`) shrinks any image larger than
  1600 px with nearest-neighbour by a non-integer factor (`k = max(size) / 1600`). The contact sheet of the
  templar's idle is 2358 × 2354 px and gets shrunk 1.47×. Each source pixel becomes one or two output pixels,
  unevenly, so outlines look broken and the AI sees jaggies that are not there. AI clients that read files
  directly also downscale large images themselves.
- **Previews are mostly empty.** The sprite covers 5–16 % of the frame area (huntress, templar and gargoyle
  at rest), yet an image costs tokens by its area: about 1.5k tokens for a 1600 px sheet.
- **No size budget.** `pose` uses a fixed scale of 4 and contact sheets a fixed 3, whatever the frame size and
  the number of directions.

## Goal
Every preview an AI receives is pixel-exact (integer scale), cropped to its content and within a size budget:
the same information for fewer tokens.

## Proposal
- One helper, `preview.fit(cells, max_side)`:
  - Crop every cell of a sheet to the union of the opaque bounding boxes of all its cells, plus a 2 px
    margin. The crop is the same for every cell, so motion stays comparable.
  - Use the largest integer scale that keeps the long side within `max_side`.
  - When even 1× is too large, split the sheet into several images rather than shrink it.
- **Budget: about 1500 px on the long side**, below the size at which AI clients shrink images themselves.
  Applied both to the files `pose`, `render` and `review` write and to MCP results.
- MCP results carry the crop box and the scale, so an AI can map a pixel it talks about back to frame
  coordinates.
- Labels stay outside the cells, as now.

## Plan
1. `preview.fit` with tests: integer scale; identical crop across cells; splitting.
2. Use it in `mcp_server._png` (replacing the resize), `api.pose`, `export.contact_sheet`, the review sheet
   and the `ref compare` sheet.
3. Tests in `tests/test_mcp.py` and `tests/test_preview.py`: a 2358 px sheet comes back at an integer scale,
   with no non-integer resize.
4. Measure the image area returned for the templar's `pose --dirs all` and its contact sheets, before and
   after.

## Validation
- Exactness: every output image is made of uniform k×k blocks.
- Size: the area of the images MCP `pose` and `review` return for the templar is at least 40 % smaller.

## Risks and open questions
- Cropping hides how much room is left in the frame, so a pose close to clipping could go unnoticed. QA already
  reports clipping in `qa.json`. Should the frame border also be drawn as a 1 px guide in the margin?

## Outcome (2026-10-27): done
Budget 1536 px and 1.15 MP. Templar: pose of 8 directions at scale 3 is 1536 × 186 (was 2304 × 288, then
shrunk by MCP); idle contact sheet 982 × 1138, 1.12 MP (was 2358 × 2354, 5.55 MP). MCP tools cut a still too
large image into pieces. `pose --no-crop` keeps whole frames (the golden pose tests use it).
