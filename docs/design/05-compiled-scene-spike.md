# 05. Compiled-scene spike (go / no-go)

**Status:** done: **go** (ADR-029) · **Track:** speed, memory · **Stage:** 1 (release 0.3) · **Depends on:** 02

## Problem
numpy is near its ceiling for this workload. Prototypes measured on 2026-10-27:

| change | speed-up |
|---|---|
| per-ray group culling | 0.9–1.3× |
| adaptive supersampling (3×3 only near part boundaries) | 1.0–2.0× |
| tight group bounds ([02](02-tight-bounds-and-exact-soft-shading.md)) | 1.45–2.7× |

What is left is the cost of many small array operations. A templar frame makes about 5,300 group calls over
thousands of points each, every one allocating temporaries, with all rays of a step moving in lockstep.

A compiled per-ray loop would remove the temporaries, stop each ray as soon as it is done, and use every core
inside one process. Research estimates 5–20× for this kind of code, but nobody has measured it on SpriteKiln
scenes. The fast backend ([12](12-compiled-scene-and-fast-backend.md)) is a large change; this spike decides
whether it is worth it.

## Goal
A decision based on numbers, in at most 2 days of work.

## Scope
- **Encode one frame's scene as flat arrays** after `rig.build`: primitive type codes, parameters, group
  ranges, blend k, cut ranges, bounds.
- **Write one numba kernel** (`@njit(parallel=True, cache=True)`) for ray marching, 4-tap normals, AO and soft
  shadows (with the exact-within rule of 02).
  - Primitives: those the showcase uses, namely sphere, ellipsoid, round cone, box, cylinder, torus and
    triangle.
  - Operations: smooth union and cuts.
- **Compare with the numpy renderer** on templar, huntress and gargoyle, rest pose, 8 directions.
- **Not in scope:** paint, new primitives, integration with the pipeline, packaging.

## What to measure
- Speed per frame, warm; compile time on the first run; load time of the cached compile.
- Peak memory of one process with N threads, against N numpy worker processes, for a full templar render
  (peak RSS of the whole process tree).
- Agreement with numpy: part ids and colours, against ADR-007's tolerance of 0.5 % of pixels.
- Installation: wheels on Windows, Linux and macOS arm64 for Python 3.10–3.15, and the size added.

## Go / no-go
**Go** if all of these hold:
- at least 5× faster per frame, warm, on templar and huntress;
- compile at most 15 s on the first run and 2 s when cached;
- at most 0.5 % of pixels differ;
- a full render's peak memory is no higher than today's at the same speed.

**Otherwise** keep numpy, take the numpy half of [12](12-compiled-scene-and-fast-backend.md) (screen tiles,
candidate culling, no groups × hits stack), and reconsider a Rust extension later.

## Constraints known from research (2026-10-27)
- **No numba for macOS Intel.** numba 0.63 and later ship no macOS Intel wheels, and 0.62 stops at Python 3.13.
  The extra must exclude that platform with a marker, and SpriteKiln must fall back to numpy there.
- **Size:** llvmlite adds about 40–60 MB to the installation.
- **One generic kernel.** numba's cache does not handle closures or functions generated at run time well, so
  the kernel reads arrays and no code is generated per scene.
- **Ruled out:** taichi (wheels stop at Python 3.13, none for macOS Intel) and JAX (Python 3.12 or later, no
  macOS Intel, large).

## Deliverable
A results table and an ADR with the decision in `docs/decisions.md`. The spike's code stays on a throwaway
branch; [12](12-compiled-scene-and-fast-backend.md) starts clean if the answer is go.

## Risks and open questions
- A spike that skips integration can hide costs: building the arrays every frame, Python overhead around the
  kernel. Measure end to end per frame, not only the kernel.

## Outcome (2026-10-27): go
Code and full results: branch `spike/compiled-scene`, `tools/spikes/compiled_scene/`. Decision: ADR-029.

| spec | numpy | numba, 16 threads, with per-ray culling | part ids | colour pixels differing |
|---|---|---|---|---|
| templar | 1.82 s | 0.31 s (5.8×) | identical | 12 of 73,728 |
| huntress | 1.05 s | 0.18 s (5.7×) | identical | 2 |
| gargoyle | 0.93 s | 0.14 s (6.6×) | identical | 3 |

- Compile: 8.7 s on the first run, 0.56 s cached. Memory: 114 MB peak for one process with 16 threads; numpy
  needs about 7 workers (about 480 MB) for the same speed.
- Without per-ray culling the compiled kernel gains only 2.1–3.7× (1.3–1.7× on one thread): culling is part of
  [12](12-compiled-scene-and-fast-backend.md), and so is moving the ray setup into the kernel.
- numba 0.68.1 and llvmlite 0.50.0 take about 150 MB on disk on Windows.
