# 06. Geometry buffer and deferred shading

**Status:** done (stage 3) · **Track:** quality, speed · **Stage:** 3 (release 0.3) · **Depends on:** 02

## Problem
- **Light is baked into one number before the pixel stage.** `render()` (`spritekiln/render.py`) lights each
  sample (wrap diffuse × soft shadow × AO, plus rim) and `to_pixels` averages that value. The cache stores
  `(gid, val, depth, normal)`, and its key includes the whole `light` block (`spritekiln/cache.py`).
- **Changing light re-marches everything.** Any change to a light parameter re-marches every frame (3–6 s
  each).
- **The pixel stage cannot shade per material.** `compose` gets that one number and maps it onto a ramp.
- **What comes next is 2D work.** Highlights (07), lines from normals (08), paint (09), dithering and style
  presets (11) and a flat albedo for engine lighting ([ROADMAP 4](../ROADMAP.md)) are per-pixel shading.
  None of it should need ray marching.

## Goal
Split each frame in two passes:
- a **geometry pass**: ray marching, cached;
- a **shading and pixel-art pass**: 2D, at most 0.2 s per frame. `compose` takes 0.03–0.16 s today.

After a change to light intensities, materials, palette or style, a whole asset re-renders from the cache in
seconds.

## Proposal
**A geometry buffer per output pixel**, after the coverage vote as today, one `.npz` per pose:

| channel | type | content |
|---|---|---|
| `gid` | int16 | winning group |
| `paint` | int16 | winning paint layer ([09](09-surface-paint.md)), -1 for none |
| `depth` | float32 | ray distance |
| `normal` | 3 × float16 | world normal, averaged over the winner's samples |
| `local` | 3 × float32 | position in the part's own space, for paint, dithering and patterns |
| `shadow` | uint8 | soft shadow for the light direction, 0–255 |
| `ao` | uint8 | ambient occlusion, 0–255 |
| `cover` | uint8 | how many samples the winner had |

**Shading moves to the 2D pass.** Wrap diffuse, rim and highlights (07) are computed from the normal and the
light. Only shadow and AO are stored, because they need geometry.

**The cache key changes:**
- it keeps geometry, camera and the light **direction**, which shadows depend on;
- it drops ambient, rim strength and material parameters.

**What happens when the light direction changes:** only the shadow rays are re-marched, from the stored hit
points (`depth` gives them). The geometry is not re-marched.

**Averaging order:** components (normal, shadow, AO) are averaged over the winner's samples, then shaded. Today
each sample is shaded and then averaged. Band boundaries move slightly, so the goldens are updated once.

**`light: {mode: flat}`:** a fixed band per material (`flat_band`, default the middle of `bands`), for games
lit by the engine through the normal map.

## Plan
1. Split `render()` into `geometry(scene, cam, light_dir) -> GBuffer` and `shade(gbuf, light, materials)`.
   `to_pixels` works on components.
2. Cache format 6 (`cache.FORMAT`) with the new channels; the new key.
3. `pipeline.render_frame`: load the buffer or render it, then shade, then `compose`.
4. The default shading formula stays today's (the same wrap, ambient and rim), so the only visual change is the
   averaging order.
5. `light.mode: flat`; a re-trace of shadows only.
6. Benchmark: templar, full asset, warm cache, after a change of `light.ambient`.

## Validation
- **Goldens:** measure how many pixels the averaging order changes, with before/after sheets for the
  maintainer. If the change is too large, keep per-sample shading for the default formula and store
  per-sample components for the winning group only.
- **Speed:** a templar re-render from a warm cache after a light-intensity change takes at most 0.3 s per
  frame (today every frame is re-marched).
- **Cache size:** entries grow (more channels) but use float16 and uint8. The per-spec cap stays 1 GB; report
  the entry size before and after.

## Risks and open questions
- The order of averaging changes the look slightly everywhere. This is a one-time change.
- `local` needs each group to know its part frame (`rig` builds it). That is shared with
  [09](09-surface-paint.md).

## Outcome (2026-10-28): done
- Backends return `render.Samples` (part, depth, normal, soft shadow, AO per ray); `to_gbuffer` votes per pixel
  and averages the winner's normal, shadow and AO into a `GBuffer` (part int16, depth float32, normal float16,
  shadow, AO and cover uint8, quantised before caching so cached and fresh frames are identical); `shade`
  computes the light value in 2D. Cache format 6; the key keeps the light's `dir`, `shadows` and `ao` only.
- Averaging before shading changed 2-4 % of the opaque pixels (gargoyle 3.8 %, Templar 2.2 %, the minimal
  fixture 4.3 %), at band borders: goldens and showcase hashes updated once.
- Measured, gargoyle (192 frames, numba): 277 ms per frame cold, 50 ms per frame after an `ambient` change.
- `light.mode: flat` with `flat_band` per material.
- Not done: re-tracing only the shadows when `dir` changes (a `dir` change re-renders everything). The paint id
  and part-local position channels come with [09](09-surface-paint.md).

