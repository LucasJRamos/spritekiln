# 02. Tight bounds and exact soft shading

**Status:** done (4c366dd, 4b2e999) · **Track:** speed, quality · **Stage:** 1 (release 0.3) · **Depends on:** nothing

## Problem
**1. Loose bounds.** `Group.__init__` (`spritekiln/sdf.py`) bounds a group with a sphere around the
axis-aligned box of its primitives' bounding spheres. For a single primitive of radius r, that sphere has
radius r·√3. Measured on the templar at rest:
- `cape`, `cape_lining` and `cross_back` (one cone each) get bounding radii of 1.55–1.68, about the height of
  the whole character.
- 64 % of the camera rays pass within some group bound, while 13 % of the pixels are hit. With
  per-primitive spheres it would be 27 %.
- Rays near a bound are marched and evaluated step after step for nothing: the templar needs 1.5 M ray steps
  per frame, the huntress 0.46 M.

**2. Shading depends on the bounds.** Outside its bound a group returns the distance to the bounding sphere.
That is a valid lower bound for stepping, but:
- `soft_shadow` (`spritekiln/render.py`) uses it in the penumbra term `10 * d / t`;
- the AO loop uses it in `h - d`.

Both treat that bound distance as if it were the surface, so a large bounding sphere darkens what is near it
("phantom shadows"). Measured on the templar at yaw 0, tightening only the bounds changes:

| shading enabled | colour pixels that change (of about 1,450 opaque) |
|---|---|
| shadows and AO | 324 |
| AO only (no shadows) | 37 |
| neither | 4 |

The part ids do not change at all.

## Goal
- **Speed with identical forms:** tight bounds make renders 1.4–2.7× faster with identical part ids.
  Measured with a prototype: templar 2.7× (yaw 0) and 2.5× (yaw 135), huntress 1.45×, gargoyle 1.7×.
- **Geometry-only shading:** inflating every bound must not change a single pixel.

## Proposal
- **Group bound:** keep the centre (the box centre). The radius becomes
  `max_i(|c_i - centre| + r_i) + blend k + margin`. A minimal enclosing sphere (Ritter) can come later.
- **Primitive bounds stay as they are** (they are already tight spheres). Cuts never enlarge a bound.
- **Trust the bound only when the caller cannot use a closer value.** `Group.__call__(p, exact_within=x)`
  evaluates the real distance for every point whose bound distance is below `x`:
  - ray marching: `x = 0.05`, as today;
  - AO: `x` = its largest radius plus a margin (0.3);
  - soft shadows, per point: `x = t / 10 + margin`, where the penumbra term can still darken.

  Beyond `x`, the bound distance is used for stepping only.
- The render cache key includes a hash of the engine sources (`spritekiln/cache.py`), so old buffers are
  never reused.

## Plan
1. Write the invariance test first; it fails today. Render the fixtures with every group bound inflated by
   0.3, and require pixels identical to a normal render.
2. Add `exact_within` and use it in `soft_shadow`, the AO loop and `march`.
3. Tighten the group radius.
4. Benchmark templar, huntress and gargoyle (rest pose, 8 directions).
5. Make before/after contact sheets of the showcase; update the goldens and the showcase hashes
   (`tests/golden/showcase.json`), giving the reason in the commit.

## Validation
- The invariance test passes.
- Part ids are identical to the current renderer on the fixtures and the showcase poses.
- At least 1.4× faster on every showcase character.
- Shading changes where big bounds used to darken surfaces (cape, coat skirt, wings). The maintainer reviews
  the before/after sheets; `review` reports the change in value contrast.

## Risks and open questions
- **Showcase shading changes.** Assets re-rendered from it will be lighter in places. Hunt Tower keeps its
  exported assets until it re-exports; the CHANGELOG says so.
- **Decided (2026-10-27): no flag to keep the old look.** The shadows that came from bounding spheres were a
  bug; exact soft shading replaces them for every spec.
- **Exact evaluation for shadow rays near surfaces costs more.** Shadows are about 10 % of a frame today;
  measure the cost.

## Outcome (2026-10-27): done
Templar frame 6.6 s → 2.2 s; 8-direction poses: Templar 37.9 s → 14.7 s, Huntress 12.8 s → 8.4 s, gargoyle
12.7 s → 8.3 s. Part ids identical. Inflating every bound by 0.3 now changes 0–4 pixels (where marching
stops) instead of 83–228. Goldens and showcase hashes rebuilt; every showcase frame is lighter where the
false shadows fell.
