# 12. Compiled scene and fast backend

**Status:** done (stage 2) · **Track:** speed, memory · **Stage:** 2 (release 0.3) · **Depends on:** 05 (go: ADR-029), 02

## Problem
- **Ray marching dominates, even after 02.** numpy pays for every operation: temporaries for every group at
  every step, and all rays of a step moving in lockstep until the slowest finishes. Prototypes inside numpy
  gave at most 2× ([05](05-compiled-scene-spike.md)).
- **Memory goes to interpreters.** Parallelism comes from processes, each with an interpreter and numpy:
  - ADR-012 measured about 85 MB committed per worker, so weak machines run few jobs;
  - `Scene.dist_all` stacks a groups × hits array;
  - everything is float64.
- **Shapes are closures.** Each SDF primitive is a numpy closure (`spritekiln/sdf.py`). A faster evaluator
  would need every primitive written again, and every new primitive ([13](13-shape-operators.md)) twice.

## Goal
If the spike says go:
- a compiled backend at least 5× faster per frame than numpy;
- running in one process with threads;
- the peak memory of a full render no higher than today's, with all cores busy.

The numpy backend stays the reference and the fallback.

## Proposal
**Scene IR** (`spritekiln/scene_ir.py`), built once per pose after `rig.build` as flat arrays that both
backends read:
- primitives: a type code, up to 16 float parameters, a bound (a sphere, or an oriented box for long or flat
  shapes);
- groups: primitive range, cut range, blend k, cut blend, blend mode, material id, flags (emissive,
  two-sided, line), a Lipschitz factor for bent or twisted shapes (13), and the inverse part frame;
- paint layers ([09](09-surface-paint.md)).

A new primitive is added to the IR once, then implemented in both evaluators against a shared test.

**numpy evaluator over the IR**, worth having even without numba:
- screen tiles (for example 16 × 16 output pixels);
- per tile, candidate groups from the projected bounds, for camera rays and for shadow rays (both are
  parallel);
- a running argmin instead of the groups × hits stack;
- 4-tap normals instead of 6;
- optional float32.

**numba evaluator** (the spike, ADR-029: 5.7–6.6× per frame, identical parts):
- one generic kernel with `cache=True`;
- per-ray group culling is required, not optional: without it the spike gained only 2.1–3.7×;
- the ray setup (scene bounds, the "never" test) runs inside the kernel: outside it cost 170 ms per Templar frame;
- `prange` over tiles, a per-ray loop with early exit, per-tile candidate lists;
- normals, AO and soft shadows with the exact-within rule of [02](02-tight-bounds-and-exact-soft-shading.md).

**Choosing a backend:**
- `--backend auto|numpy|numba`, or `SPRITEKILN_BACKEND`;
- `auto` picks numba when it imports, otherwise numpy, and logs the choice once;
- with numba, `render_all` runs one process with a thread pool sized from cores and memory (`auto_jobs`
  counts threads and buffers, not interpreters).

**Packaging:**
- an extra, `spritekiln[fast]`, requiring
  `numba; sys_platform != "darwin" or platform_machine != "x86_64"`;
- `spritekiln update` already keeps extras;
- the first run says "compiling the renderer (first run only)".

## Plan
1. IR plus the numpy evaluator, behind the current API. Goldens stay exact.
2. Tiles, candidate culling, running argmin, 4-tap normals; keep each if it is at least 1.2× faster or saves
   memory.
3. The numba kernel, the backend switch and the extra; CI jobs with the extra on Linux, Windows and macOS
   arm64, and one without it.
4. Memory: peak RSS of a full templar render for numpy with 1, 2, 4 and 8 jobs, against numba in one process
   with 8 threads; on a machine limited to 8 GB.
5. Docs: the extra in the install tutorials; an ADR.

## Validation
- **Accuracy:**
  - numba against numpy, at most 0.5 % of pixels differ on fixtures and showcase poses (ADR-007);
  - numpy goldens stay exact;
  - a per-primitive test compares both evaluators on random points (distances within 1e-5).
- **Speed:** a table per spec, warm; compile time cold and cached.
- **Install:** the install workflow (`.github/workflows/install.yml`) with and without the extra on clean
  machines.

## Risks and open questions
- **Two evaluators to maintain.** The shared per-primitive test is the guard.
- **JIT compile on weak machines** takes seconds on the first run; it is cached afterwards.
- **numba lags new Python versions.** The numpy fallback keeps SpriteKiln working on day one.
- **macOS Intel stays on numpy.** If that becomes a real complaint, revisit a Rust extension (pyo3, one abi3
  wheel per platform).

## Outcome (2026-10-27): done
- `scene_ir.py` (flat arrays with variable-length parameters per primitive), `fast.py` (the numba kernel with
  per-ray culling of camera rays, AO taps and shadow rays, the ray setup inside), `backend.py` (`auto`,
  `numpy`, `numba`; `--backend` and `SPRITEKILN_BACKEND`), the `[fast]` extra, `spritekiln update` keeping it.
- The numpy closures stay the reference; every primitive is checked against the kernel on random points
  (`tests/test_fast.py`, differences under 1e-9), and whole frames agree on every part.
- With numba, `render` uses one process (threads); with `--jobs N` each worker gets cores / N threads. The
  backend is part of the render cache key.
- Measured, the Templar's full render (456 frames, uncached) on the development machine with 1-2 GB free:
  numba 194 s in one process (peak 250 MB); numpy took 1372 s, limited by the free memory to one worker
  (the machine was also running tests; about 870 s without them, 456 frames x 1.9 s).
- Not done: the numpy evaluator over the IR with screen tiles (the numpy closures were kept as they are: the
  goldens stay exact and numba is the fast path), 4-tap normals and float32 (they would change pixels).

