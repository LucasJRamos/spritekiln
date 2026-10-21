# Decision records

Short ADRs for the open-source preparation. Newest last. Status is *accepted* unless noted.

## ADR-001: Name the project SpriteKiln (2026-10-21)
The rename happens in Phase 1: package and CLI become `spritekiln`. "pxforge" collides with PxForge/pxForge
repositories on GitHub and with several "PixelForge" pixel-art tools. `spritekiln` and `sprite-kiln` were
free on PyPI and GitHub on 2026-10-21; recheck right before renaming. Until Phase 6, a `pxforge` shim
keeps `python -m pxforge`, the `pxforge: 1` spec header and `PxSprite2D` working for Hunt Tower.

## ADR-002: Repository owner is LucasJRamos (2026-10-21)
The public repository lives under the personal account `LucasJRamos`, not the `PlayRPG` org. No remote is
configured until the maintainer asks.

## ADR-003: Licensing by path with REUSE (2026-10-21)
- Code, docs and integrations: MIT.
- Example assets (gargoyle, cacador, props, humanoid template, gothic/props palettes, test goldens):
  CC0 1.0.
- Showcase assets (Templar, Huntress, their splash arts and palettes, future `showcase/`): © Lucas Ramos /
  PlayRPG, all rights reserved, demonstration only (`LICENSES/LicenseRef-Showcase.txt`).

`REUSE.toml` maps paths to licenses and `LICENSES/` holds the texts; `reuse lint` passes (REUSE 3.3). The
root `LICENSE` is the MIT text followed by a scope note, as the maintainer asked. Trade-off: GitHub's
license detector may label the repository with several licenses instead of a single "MIT" badge. If that
matters at launch, move the scope note to the README and keep `LICENSE` as plain MIT.

Amended 2026-10-21: the `mine` prop moves to the showcase. It belongs to the Huntress's kit and uses her
palette, so it could not be reused as CC0 anyway.

The cacador's `splash_teste.jpg` looks like an upscaled render of the cacador spec itself, so it follows
the example license (CC0). Confirm before launch.

## ADR-004: Python 3.10+ (2026-10-21)
`requires-python = ">=3.10"`; CI covers 3.10 to 3.13. Python 3.10 reaches end of life in October 2026;
revisit for v0.2.

## ADR-005: Unity validation target is 6000.3 (2026-10-21)
Unity 6000.3.6f1 and 6000.4.0f1 are installed on the dev machine. The UPM package is validated on 6000.3
(Unity 6.3, LTS line); if that fails, the integration ships as "experimental".

## ADR-006: What stays out of the repository (2026-10-21)
- `legacy/` (first prototype, imported by nothing) and `research/` (raw Hunt Tower session material with
  game captures and scratchpad paths) are local-only, via `.git/info/exclude`. Phase 2 ports the research
  scripts into `review`; Phase 5 copies chosen images into `showcase/`. Deleting `legacy/` is the
  maintainer's call.
- `out/`, `.pxcache/` and `ref prep` output folders (`specs/**/*_ref/`) are ignored.
- Showcase files stay at their current paths (`specs/characters/{templar,huntress}`) until Phase 5/6,
  because Hunt Tower's workflow refers to them.
- The splash arts (~9 MB of PNG) are in the local history. Since nothing is pushed yet, the history can be
  squashed before the first push if they are resized for the showcase.

## ADR-007: Golden testing strategy (2026-10-21)
- Golden tests render a staged copy of the spec (spec + shared palettes in a temp folder), so the render
  cache always starts empty. A stale cache can never mask a regression: the cache key does not include the
  engine version (audit #2).
- Exact pixel match on the platform recorded in `tests/golden/meta.json` (OS, CPU, numpy); elsewhere up
  to 0.5 % of pixels may differ (float noise across BLAS/numpy builds).
- Showcase reproduction is checked by per-frame hashes (`tests/golden/showcase.json`), so no showcase
  pixels land in `tests/`. It is an opt-in slow test (`pytest -m slow`), and it can run partially with
  `SHOWCASE_ANIMS`.
- An intentional visual change updates the goldens (`pytest --update-golden`) and says why in the commit.

## ADR-008: LF line endings (2026-10-21)
`.gitattributes` sets `* text=auto eol=lf` (Godot resources were already LF). The working tree is LF on
every platform; Python, YAML and the engines read it fine on Windows.

## ADR-009: Compatibility through the `pxforge` name (2026-10-21)
The package is `spritekiln`; `pxforge/` is a shim that aliases every module and keeps `python -m pxforge`
and the `pxforge` command. The command name selects the JSON block key: `spritekiln render` writes the
`spritekiln` block, `pxforge render` keeps writing `pxforge`, because Hunt Tower's installed copy of
PxSprite2D only reads that key. The runtimes in `integrations/` read both. Godot names (`addons/pxforge`,
`PxSprite2D`, default destination `assets/pxforge`) stay until the addon is reworked in Phase 4.

## ADR-010: hatchling, resources kept where the repository uses them (2026-10-21)
The build backend is hatchling. The humanoid template, the CC0 palettes and the Godot addon stay at
`specs/templates`, `specs/palettes` and `integrations/godot` (Hunt Tower and the docs point there) and are
`force-include`d into `spritekiln/data/` in the wheel; `spritekiln/resources.py` reads either place. Specs
can name a built-in palette (`palette: gothic`). Showcase files never enter the wheel or the sdist.

## ADR-011: Render cache format (2026-10-21)
`.kilncache/<name>/<key>.npz`, compressed, read with `allow_pickle=False`. The key includes a hash of the
engine sources (expr, rig, sdf, render), so any engine edit, even formatting, starts a fresh cache.
Writes are atomic; entries are touched on use and each spec cache is pruned to 1 GB (least recently used
first) after a render. The old `.pxcache/` pickles are never read; `spritekiln cache clear --legacy`
removes them.

## ADR-012: Job count from available memory, one BLAS thread (2026-10-21)
Measured on the dev machine: importing numpy commits ~500 MB per process (an OpenBLAS buffer per thread,
16 threads), which explains the out-of-memory kills during Hunt Tower renders; with one BLAS thread a
Templar frame commits 85 MB at the same speed. Workers and the CLI therefore set `OPENBLAS_NUM_THREADS`,
`OMP_NUM_THREADS` and `MKL_NUM_THREADS` to 1 unless the user already set them. Without `--jobs`, the job
count is `(available - max(1 GB, 10 % of RAM) - coordinator) / per-worker estimate`, capped at half the
logical CPUs (8 and 15 jobs render at the same speed on a 16-thread CPU) and at the work left. A dead
worker restarts the pool with half the jobs; finished frames stay in the cache.

## ADR-013: The JSON Schema is the source for spec structure (2026-10-21)
`spritekiln/data/spec.schema.json` serves editors, AIs and the runtime. Unknown keys are warnings (old
specs keep working; typos get a "did you mean"), missing required keys are errors, and every problem
carries file:line:column. The runtime walks the schema with the stdlib; `jsonschema` is a dev dependency
used by the tests to validate every spec.

## ADR-014: Output format 1 (2026-10-21)
`docs/format.md` is the contract. Format 1 = everything pxforge 0.1 wrote plus `format`, `generator` and
`camera`. Additive fields never bump the number; readers must ignore unknown fields. An event on frame i
fires when frame i becomes visible.
