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

The cacador's `splash_teste.jpg` is the toolkit's own output (confirmed by the maintainer on 2026-10-21),
so it follows the example license (CC0).

## ADR-004: Python 3.10+ (2026-10-21)
`requires-python = ">=3.10"`; CI covers 3.10 to 3.13. Python 3.10 reaches end of life in October 2026;
revisit for v0.2.

## ADR-005: Unity validation target is 6000.3 (2026-10-21)
Unity 6000.3.6f1 and 6000.4.0f1 are installed on the dev machine. The UPM package is validated on 6000.3
(Unity 6.3, LTS line); if that fails, the integration ships as "experimental".

## ADR-006: What stays out of the repository (2026-10-21)
- `legacy/` (first prototype, imported by nothing) and `research/` (raw Hunt Tower session material with
  game captures and scratchpad paths) are local-only, via `.git/info/exclude`. Phase 2 ports the research
  scripts into `review`; Phase 5 copies chosen images into `showcase/`. `legacy/` was deleted from
  disk on 2026-10-21 at the maintainer's request.
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

## ADR-015: Channels see the direction (2026-10-21)
Animation channels are evaluated once per direction, with `yaw` and `dir` in scope, like bones and parts.
The alternative (helper channels multiplied by `pulse(yaw)` inside bones, as the Huntress's animator had
to do) leaked rig plumbing into every spec. Frame counts may not depend on the direction (validate checks
it); durations may, and per-direction durations are already exported.

## ADR-016: Socket depth is measured from the body's vertical axis (2026-10-21)
A socket exports `[x, y, depth]`; `depth` is the ground distance, in px, from the character's vertical axis
(through the `root` frame) toward the viewer. It answers the question games actually ask (draw the effect
in front of or behind the sprite?) without an occlusion test, which would misfire for points inside the
geometry (a hand inside its own fist). Exact pixel visibility can be added later as a separate flag.
Muzzle sockets go at the centre of the flash the game spawns, not at the barrel tip.

## ADR-017: Art-direction targets are warnings (2026-10-21)
`review:` targets (L*, pixels per material) are QA warnings, never errors: they encode taste and depend on
the scene (`tint`, background) more than on correctness. Timing targets (`timing:`) are errors in both
`validate` and QA, because gameplay code depends on them. `review` (the command) always reports every
number; the targets only decide what is flagged.

## ADR-018: Splash cutout grows the background from the border (2026-10-21)
`ref prep` finds the background as everything the image border reaches through small colour steps (a magic
wand), instead of a global distance to the median border colour, which failed on gradient backgrounds
(the whole Templar splash was kept). Enclosed openings stay transparent when they are big and as flat as
the background (the gap between the legs); small or textured ones are filled. Measured against the
hand-made cutouts: Huntress IoU 0.745 → 0.925, Templar 0.664 → 0.914. `rembg` remains the option for busy
backgrounds.

## ADR-019: Generated AI adapters from one source (2026-10-21)
The knowledge lives once, in `docs/agent/`. Every AI-specific file is generated from it by
`spritekiln/agents.py` (repository) or `spritekiln init` (game projects), so the adapters cannot drift. Files a
project already has (AGENTS.md, CLAUDE.md, GEMINI.md, copilot-instructions.md) only get a block between
`spritekiln:begin`/`spritekiln:end` markers; files SpriteKiln owns (skills, agents, the Cursor rule) are
written whole. Claude Code skill folders are self-contained (copies of the reference files) because projects
link skill folders individually. Agents recommend "the strongest model with image input" instead of pinning
`model: opus`. The legacy `pxforge*` skill folders stay, generated with `python -m pxforge`, until Hunt Tower
migrates (Phase 6); they are removed then.

## ADR-020: MCP tools return images and JSON (2026-10-21)
`spritekiln mcp` exposes the same operations as the CLI through `spritekiln/api.py`. Visual tools return the
image (scaled to at most 1600 px) next to the JSON, so image-capable clients judge the art and text-only
ones still get the numbers. User errors become tool errors, never crashes. Paths are relative to the folder
the client starts the server in. A `guide` tool serves the knowledge files to clients that cannot read the
project's files. The `mcp` dependency is an extra and targets SDK 2.x (`MCPServer`).

## ADR-021: spritekiln.toml replaces wrappers and environment variables (2026-10-21)
A project describes itself in `spritekiln.toml` (found by searching upwards): specs folder, engine, export
folder, Godot project, defaults for new specs. Environment variables (`SPRITEKILN_GODOT_PROJECT`, the old
`PXFORGE_GODOT_PROJECT`) still win when set, so Hunt Tower's `px.cmd` keeps working until Phase 6. New
projects export Godot assets to `assets/spritekiln/`; projects without a toml keep `assets/pxforge/`.

## ADR-022: Side-scroller as a view preset (2026-10-21)
A side-scroller sprite is the same 3D model seen from the side, so `view: side` is a preset rather than a
second pipeline: camera pitch 0, directions `[e, w]` for characters, no ground ellipse. Explicit spec values
win over the preset (a tilted side view is `camera: {pitch: 10}`). Everything else (rig, animation,
sockets, timing, review, export, MCP) is shared; the JSON says which view produced it. A project picks its
default with `init --view`; a game should keep one view. Mirroring one profile in the engine is left as an
opt-in export option for Phase 4, because the fixed world light makes a flipped sprite lit from the wrong
side.

## ADR-023: Engine runtimes share one API and the Kiln prefix (2026-10-21)
Godot (`KilnSprite2D`), Unity (`KilnAnimator`) and MonoGame (`KilnAnimator`) expose the same behaviour,
pinned by tests in each engine: clips named `<anim>_<dir>`, exact per-frame durations, frame-0 events inside
the call that starts a clip (and once), events of later frames when they become visible, a finish event
for clips that do not loop, the direction nearest to a vector, sockets for the current frame, mirrored
directions drawn flipped around the pivot with socket `x` negated, and the emissive layer drawn over the
sprite unaffected by the scene's light. Listeners receive the name of the clip that fired even when an
earlier listener started another one. The old Godot addon (`PxSprite2D`, `addons/pxforge`) stays as it is
for Hunt Tower until Phase 6; the old MonoGame file (`PxSprite.cs`) had no users and was replaced.

## ADR-024: Unity reads renders as .kiln files (2026-10-21)
Unity imports every `.json` as a TextAsset and a ScriptedImporter cannot take the extension over without
the user picking it per file, so `spritekiln export --engine unity` writes the same JSON as `<name>.kiln`.
The importer reads the PNGs itself (point filter, no compression) and makes everything a sub-asset of the
`.kiln`: the `KilnSheet`, the sprites (normal map as the `_NormalMap` secondary texture for URP 2D lights)
and optional AnimationClips for Animator users. The package is installed by git URL, so its `.meta` files
are versioned.

## ADR-025: `mirror: true` is opt-in (2026-10-21)
A spec can render only the right-facing half of its directions and let the engine flip the rest: about 40%
less atlas and render time. The JSON lists the flipped directions in `mirrors`, and `direction_yaw` keeps
all of them so direction picking does not change. It stays opt-in because SpriteKiln's light is fixed in
the world: a flipped sprite is lit from the other side, and asymmetric designs swap hands.

## ADR-026: Every runtime keeps its own clock (2026-10-22)
The first `KilnSprite2D` let AnimatedSprite2D advance the frames. When consecutive frames have different
durations, AnimatedSprite2D spends the rest of a tick on the new frame at the previous frame's speed, so
events and the end of a clip drifted by up to three ticks (a 40/130/40/130 ms clip ended 50 ms early). Like
the Unity and MonoGame runtimes, it now accumulates time from the JSON's durations and only uses
AnimatedSprite2D to show the frame (playing at speed 0 so `is_playing()` still works). The three runtimes
share the rules in `docs/format.md`: an event fires on the first tick whose accumulated time reaches its
frame's start, a clip started from inside an event or finish handler starts fresh, and a direction tie
keeps the current direction.

## ADR-027: The art style is an interview recorded in spritekiln.toml (2026-10-25)
Assets of one game must share a look, and the user knows it better than any default. Before the first asset
of a project, the AI interviews the user with eight short questions (`docs/agent/style.md`) and records the
answers with `spritekiln style set` in a `[style]` table of `spritekiln.toml`, next to the `[defaults]` that
`spritekiln new` already applied, rather than in a separate document: one file, already found by every
command, and the numeric answers (view, height on screen → `camera.scale` and `size`, directions, mirroring,
palette) become defaults in code instead of relying on the AI's memory. The descriptive answers (outline,
shading, proportions, animation, references, notes) map to concrete spec choices in `style.md`. The
interview is driven by the AI instructions (the generated block, step 0 of the loop, the MCP server
instructions) and `new` only warns when no style is recorded, so scripts and manual use are never blocked.
The style changes only when the user explicitly asks; `init --force` keeps it. A project without
`spritekiln.toml` (Hunt Tower until Phase 6) has no style and is not interviewed. A terminal questionnaire
for users without an AI is left for later.

## ADR-028: `spritekiln update` upgrades through the original installer (2026-10-25)
The update command detects how SpriteKiln was installed (pipx and uv leave a receipt in the environment,
a virtual environment differs from the base Python, a checkout or editable install has the sources) and
runs that installer's upgrade, keeping the extras; it never upgrades a system Python or a checkout, it says
how. Windows keeps the running `spritekiln.exe` locked, and its launchers hold their own file open, so it
cannot even be renamed: `uv tool upgrade` then fails to copy the new launcher, and pip leaves a virtual
environment half uninstalled. So on Windows uv upgrades only the package in the tool environment (`uv pip
install --python`), a virtual environment is upgraded from `python -m spritekiln update` (no launcher
running), and pipx, which copes, runs as everywhere; success is judged by the version installed
afterwards, not by the installer's exit code alone. All routes were tested on Windows with a local index. The version check reads PyPI's JSON API with the standard library, only in `update`. Upgrading the
package does not reach a project's copies of the AI instructions, so `update` then starts the new version
(`python -m spritekiln update --files`) to rewrite them, leaving `spritekiln.toml`, specs, renders and MCP
configs alone. `init` now records the assistants in `spritekiln.toml` and stamps `.spritekiln/version`;
projects from 0.1.0 have their assistants detected from the files `init` wrote, and commands note a
project whose files come from another version.

## ADR-029: A compiled numba backend is worth building (2026-10-27)
Design 05's spike (branch `spike/compiled-scene`, `tools/spikes/compiled_scene/`) captured one frame's scene
as flat arrays and rendered it with one numba kernel that mirrors `spritekiln.render`. Measured on the dev
machine (16 threads), rest pose, 8 directions, whole frames: the Templar 1.82 s → 0.31 s (5.8×), the Huntress
1.05 s → 0.18 s (5.7×), the gargoyle 0.93 s → 0.14 s (6.6×); part ids identical, at most 12 of 73,728 colour
pixels different (where marching stops, within its epsilon); compile 8.7 s on the first run, 0.56 s cached;
one process peaks at 114 MB, where numpy workers need about 480 MB for the same speed. That meets every
go criterion, so design 12 is built: an optional `spritekiln[fast]` extra, numpy stays the reference and the
fallback. Two findings shape it. A compiled per-ray loop alone gains only 1.3–1.7× per thread (the work is
rays × steps × groups either way): per-ray group culling (camera ray, AO taps, shadow ray) is what pays, so
it is part of the design, not an option. And the ray setup outside the kernel cost as much as the kernel
(170 ms per Templar frame), so it moves inside. Costs accepted: numba and llvmlite take about 150 MB on disk,
there are no macOS Intel wheels (numpy there), and the first run compiles for about 9 s.

## ADR-030: Release 0.3 ships the whole plan; its stages are milestones on a branch (2026-10-27)
The quality, forms and speed plan (`docs/design/`, proposals 01–14) is developed on the branch
`plan/quality-forms-performance` in four stages: quick wins and the spike (01–05), forms and speed (12, 13,
10), surface and style (06–09, 11), reuse (14). The stages are milestones, not releases: `main` gets no
release per stage, and release 0.3 ships everything, complete, when the maintainer decides it is ready. The
proposals build on each other: the compiled scene comes first so each new primitive is written once for both
backends, forms come before surface and style so finishes, lines, paint and style are tuned on the final
forms, and the kits are built with all of them. A release per stage was rejected: it would have shipped looks
that the next stage changes again (02 and 06 change pixels on purpose). Each proposal is still decided on its
own, with its own ADR (ADR-029 for 05, ADR-031 to ADR-043 for the others). Cost accepted: nothing reaches
users until the whole plan is done, and the branch carries every stage until then.

## ADR-031: Draft previews trace one ray per pixel and cannot be exported (2026-10-27)
Most iterations of the loop only ask whether a silhouette or a pose is right, and one sample per pixel instead
of 3×3 renders the Templar 6.7× faster. `pose --draft` and MCP `pose(draft=true)` render with
`supersample: 1, coverage: 1` on a copy of the spec; files end in `_draft`, the MCP JSON says `"draft": true`,
and the camera is in the render cache key, so draft and full entries never mix. `render --draft` writes only
GIFs and contact sheets, to `preview-draft/`, and no atlas, JSON or QA, so a draft cannot reach an engine
through `export`. Measured, 8 directions, uncached: Templar 14.7 s → 5.1 s, Huntress 8.4 s → 3.9 s, gargoyle
8.3 s → 4.3 s; parts agree with the full render on at least 95 % of the pixels both fill. That is 2–3× over
the full pose after ADR-032 (7× over the pose before stage 1), short of the 5× goal: once ray marching got
cheaper, start-up, rig and `compose` weigh more, and the rest comes from the numba backend (ADR-035). Drafts
are not MCP `pose`'s default; the AI asks for one. Cost accepted: thin parts can vanish or flicker in a draft,
so the docs ask for one full `pose --dirs all` before `render`.

## ADR-032: Group bounds are tight and soft shading reads only the geometry; no legacy flag (2026-10-27)
A group was bounded by a sphere around the box of its primitives' bounding spheres (radius r·√3 for one
primitive of radius r), and soft shadows and AO read the distance to that sphere as if it were the surface:
big bounds made rays march for nothing and darkened what lay near them (tightening only the bounds changed 324
colour pixels of the Templar, with identical part ids). A group's radius is now the farthest reach of its
primitives from its centre, plus the blend and a margin, and it evaluates its real distance wherever the
caller can still use a closer value (marching, AO taps, a shadow's penumbra); beyond that the bound only sets
the step. Measured: a Templar frame 6.6 s → 2.2 s; 8-direction poses Templar 37.9 s → 14.7 s, Huntress
12.8 s → 8.4 s, gargoyle 12.7 s → 8.3 s; part ids identical; inflating every bound by 0.3 changes 0–4 pixels
(where marching stops) instead of 83–228. No flag keeps the old look: the shadows that came from bounding
spheres were a bug. Cost accepted: every showcase frame is lighter where the false shadows fell, the goldens
and showcase hashes were rebuilt (ADR-007), and assets rendered again do not match 0.2 pixel for pixel; Hunt
Tower keeps its exported assets until it re-exports.

## ADR-033: Previews are cropped and zoomed by whole factors within an image budget (2026-10-27)
AI clients were shown pixel art shrunk by non-integer factors (MCP scaled any image over 1600 px down,
ADR-020, and clients shrink large images themselves), so outlines looked broken, and most of each image was
empty frame. One helper, `preview.fit`, crops every cell of a sheet to the union of the cells' content plus a
margin (the same crop for all, so motion stays comparable), zooms by the largest whole factor within a budget
of 1536 px and 1.15 MP, and splits a sheet rather than shrink it. It serves `pose`, contact sheets, GIFs and
the `review` and `ref compare` sheets, on disk and through MCP, whose results also carry the crop box and the
zoom. Supersedes ADR-020 in part: no preview is scaled down to 1600 px any more, and MCP tools cut a still too
large image into pieces. Measured on the Templar: an 8-direction pose at scale 3 is 1536 × 186 (was
2304 × 288, then shrunk by MCP); the idle contact sheet is 982 × 1138, 1.12 MP (was 2358 × 2354, 5.55 MP).
`pose --no-crop` keeps whole frames (the golden pose tests use it). Cost accepted: a crop hides how much room
is left in the frame; QA still reports clipping in `qa.json`.

## ADR-034: An AI reads a spec through its outline and the blocks it edits (2026-10-27)
Specs are 8–41 KB (the Huntress: 742 lines, about 10k tokens), and to change one part an AI read the whole
file, then each agent of the recipe read it again. `spritekiln spec outline` maps a spec: each part,
animation, IK chain and socket with its line range and a summary, the other sections as one line of names
(`--json` gives full paths). `spec show <spec> <path>...` prints the numbered source lines of those blocks,
comments kept: a slice of the file, never a re-dump. A mirrored `_R` item shows its `_L` source, and
`--resolved` shows a block as the renderer reads it. MCP tools `spec_outline` and `spec_show`. Line ranges
come from the YAML node marks the loader already keeps for `file:line:column` errors. Measured: outlines of
6.1 KB for the Huntress (spec 40.6 KB), 4.0 KB for the Templar (23.9 KB) and 2.3 KB for the gargoyle
(13.5 KB). The docs tell an AI to outline a long spec first; reading the file with an offset and a limit stays
fine. Cost accepted: flow-style blocks (`{...}` on one line) are shown whole.

## ADR-035: The numba backend ships as the optional `[fast]` extra; numpy stays the reference (2026-10-27)
Extends ADR-029. `scene_ir.py` captures a pose as flat arrays, `fast.py` is the numba kernel with per-ray
culling of camera rays, AO taps and shadow rays and the ray setup inside, and `backend.py` chooses `auto`,
`numpy` or `numba` (`--backend`, `SPRITEKILN_BACKEND`); `auto` takes numba when it imports, and
`spritekiln update` keeps the extra. The numpy closures stay the reference: every primitive is checked against
the kernel on random points (differences under 1e-9), whole frames agree on every part, the goldens are
rendered with numpy (ADR-007), and the backend is part of the render cache key. Supersedes ADR-012 in part:
with numba, `render` runs one process with threads, and `--jobs N` gives each worker cores / N threads; numpy
keeps ADR-012's pool. Measured, the Templar's full render (456 frames, uncached) on the development machine
with 1–2 GB free: numba 194 s in one process (peak 250 MB); numpy 1372 s, held to one worker by the free
memory (about 870 s without the tests it was also running). Not done: a numpy evaluator over the IR with
screen tiles (the closures keep the goldens exact, and numba is the fast path), 4-tap normals and float32
(they would change pixels). Costs accepted: ADR-029's, and two evaluators kept in step by a shared test.

## ADR-036: Forms get extrusions, revolutions, tubes, planes and modifiers, in both backends (2026-10-27)
Forms were limited to rounded primitives with smooth union, so plates, blades and brims came out inflated and
the Templar's cape was a cone with 7 cuts. New primitives `extrude`, `revolve`, `tube` and `plane` (in `cut:`
only); profiles `circle`, `rect` (`chamfer`, `round`), `polygon` and `bezier`; modifiers `shell`, `elongate`,
`twist` and `bend`; joins `chamfer`, `round`, `stairs` and the `groove` cut. Each is written in numpy (the
reference) and in the numba kernel, checked against each other and against known shapes (an extruded rectangle
is a box) to 1e-15; bends, twists and tapered tubes give bounds, and their group's steps shrink by a Lipschitz
factor. Formulas are re-implemented from Inigo Quilez and hg_sdf, credited. Rejected: a generic `round`
modifier (shapes with edges have their own `round`), `moon` and `vesica` profiles (a `bezier` draws them) and
noise displacement (speckle at 64 px; noise is a paint pattern). The showcase port (branch
`showcase/forms-port`, not merged: Hunt Tower uses these specs) kept new shapes only where a part read better:
Templar IoU s 0.701 → 0.707 and se 0.592 → 0.605, cuts 25 → 23; Huntress IoU s 0.492 → 0.500 and se
0.479 → 0.497, cuts 12 → 9; gargoyle primitives 77 → 70. Cost accepted: more vocabulary for the AI, taught by
a "which shape for what" table and eight recipes; `validate` warns about pieces under a pixel.

## ADR-037: Thin parts win pixels by weight; frames can snap to whole pixels; QA measures boil (2026-10-27)
A thin part in front of the body lost every vote and vanished or broke into dots, and parts moving by
fractions of a pixel made shading boil, with no QA number for it. Parts take `priority` (the weight of their
samples in the vote) and `min_cover` (how many samples fill a pixel below the camera's coverage); the defaults
keep the old path. A thin staff fixture showed 0–4 px per direction, and 6–26 px in every direction with
`priority: 3, min_cover: 2`. `snap: [frames]` rounds those rig frames' screen offset from the rest pose to
whole pixels, so children, parts and sockets follow; it is in the cache key. QA's `boil` is the share of inner
pixels that change colour for one frame and change back (emissive pixels left out), a warning at 4 % when
consecutive silhouettes overlap at least 95 %; a plain share of changed pixels was dropped because it counts
real motion (20–55 % everywhere). Idles measured 3.0–5.2 %; `snap: [root, torso_rot]` took the Templar's idle
from 3.0 to 1.6 % and the Huntress's from 4.1 to 1.9 %, but the gargoyle's from 5.2 to 6.7 % (its wings move
on their own), so snapping stays opt-in and the docs say to check the number. Cost accepted: a high `priority`
makes a part look thicker than modeled, and snapped motion steps instead of drifting.

## ADR-038: Each frame's geometry is cached per pixel and shaded in 2D (2026-10-28)
Light was baked into one value per sample before the pixel stage: any light change re-marched every frame, and
`compose` could not shade per material, while finishes, lines from normals, paint and style are per-pixel
work. The backends now return per-ray samples; `to_gbuffer` votes per pixel and averages the winner's normal,
shadow and AO into a `GBuffer` (part int16, depth float32, normal float16, shadow, AO and cover uint8),
quantised before caching so cached and fresh frames are identical, and `shade` computes the light in 2D.
Extends ADR-011: cache format 6 (7 with paint, ADR-041), and the key keeps only the light's `dir`, `shadows`
and `ao`, so intensities, ramps and materials apply after the cache. Measured on the gargoyle (192 frames,
numba): 277 ms per frame cold, 50 ms after an `ambient` change. Averaging before shading changed 2–4 % of the
opaque pixels, at band borders (gargoyle 3.8 %, Templar 2.2 %, the minimal fixture 4.3 %): accepted as a
one-time change, goldens and showcase hashes updated once (ADR-007). `light: {mode: flat}` gives one tone per
material (`flat_band`) for games lit by the engine through the normal map. Not done: re-tracing only the
shadows when `dir` changes.

## ADR-039: Materials pick a finish that sets their highlight and rim (2026-10-28)
Light was one scalar mapped onto a ramp, with no highlight term, so metal, cloth and stone read alike. A
material takes `finish: matte | soft | metal | glossy`, a preset that expands into `highlight` and `rim`;
fields given next to it win. `highlight: {size, max_px, min_px, band, color}` thresholds the Blinn-Phong term
`n·h` and keeps its clusters small, `rim` is per material, and `thresholds` sets toon steps instead of
`gamma`. Found on the Templar: a highlight in the ramp's top tone did not read, because the lit side already
used that tone; a material with a highlight now keeps its top tone for it and the light uses the tones below,
as pixel artists do. With `finish: metal` on iron and gold the armour reads darker and metallic, with small
hard highlights on the pauldrons, arms and knees; a metal ball shows 1–4 top-tone pixels on its upper half in
all 4 directions tested, a plain one more than 8. Without these fields every spec renders as before (goldens
unchanged). Cost accepted: the light is fixed in the world and the model turns, so highlights move between
directions; `max_px` and `min_px` keep them small.

## ADR-040: Creases and edge highlights come from normals inside a part, off by default (2026-10-28)
Inner lines appeared only where two different parts met with a depth jump, so a fold inside one part or a cape
seen from the side got none, and convex edges got no light, though every pixel's normal was computed.
`pixelize.folds` compares right and down neighbours of the same part: a concave fold sharper than
`crease_angle` marks the farther pixel as a line, a convex edge facing the light lifts the brighter pixel one
tone (below a highlight's reserved tone), and runs shorter than `min_run` are dropped. The material fields are
`crease` and `edge_highlight`, a spec tunes `render: {crease_angle, min_run}`, and the style's
`lines = "depth+normal"` turns creases on everywhere (ADR-042). The self-overlap rule first drew lines on a
sphere's silhouette, where a grazing surface changes depth fast; it now compares the jump with the slope the
normals predict, only between pixels that face the camera. On the Templar's armour and the gargoyle's stone
the lines and edge lights add definition at the joints; the effect is moderate at 64–96 px. Off by default, so
goldens are unchanged. Cost accepted: smooth joins can give short noisy lines, which `min_run` and
`crease: false` on organic materials keep down.

## ADR-041: Surface paint colours regions of a part without new geometry (2026-10-28)
About a third of the Templar's groups existed only to put a colour on a surface; the cross on its back was a
cone shell with 11 boxes cut out. A part's `paint:` layers are a volume (`prims`) or a pattern (`stripes`,
`rings`, `grid`, `spots`, `checker`) in the part's own space (`Group.frame`, mirrored for `_R` twins),
evaluated on hit samples after either backend, so they cost nothing while marching. The geometry buffer gains
`paint`, the majority layer among the winner's samples (cache format 7), and `compose` takes the paint's
material for ramp, highlight, lines, selout and the orphan cleanup. An `edge: true` line uses the paint
material's `line_band`, not the darker of the two as proposed: it sits on the side the layer outlines. Templar
demo, crosses only: 40 → 37 parts, 25 → 14 cuts, 496 → 482 lines, the same picture, geometry pass
0.463 → 0.407 s per frame with numba (−12 %) and 2.35 → 1.74 s with numpy (−26 %). The estimate of 36 → 28
groups assumed porting the trims and bands too; that waits for a showcase update. A per-pixel part-local
position channel was tried and dropped (ADR-042). No paint, no change. Cost accepted: paint cannot change the
silhouette; a raised trim still needs geometry.

## ADR-042: The project's style is applied by the renderer (2026-10-28)
The `[style]` of ADR-027 recorded outline and shading, but the renderer never read them: the AI copied them
into every material, costing tokens and drifting between assets. `spec.load` now resolves `render` as built-in
defaults < project style < `style preview`'s choice < the spec's `render:` block and turns it into material
defaults, the light preset and `snap`; a material's own fields win. The style gains `colored` outlines, an
`outline_color` for `dark`, `toon` shading, `lines`, `highlights`, `dither` (Bayer), `light` presets and
`snap`. Supersedes ADR-027 in part: outline and shading are no longer spec choices the AI writes, and the
interview also asks about lines, highlights, dither, light and snapping. Dither is indexed by screen pixels
from each part's projected origin, not by part-local coordinates as proposed: a 3D pattern sampled on the
pixel grid aliases on slanted surfaces, and the origin already moves it with the part. `style preview` (MCP
`style_preview`) shows a pose under each choice; switching the Templar's style re-renders its 64 idle frames
from a warm cache in 0.03–0.04 s per frame. Defaults equal the old look, so no golden changed. Named bundles
of fields were left out: with the preview, the fields are few enough. Cost accepted: a project whose style
says `outline = "dark"` or `shading = "flat"` now gets it on every material that does not set its own.

## ADR-043: Specs extend bases and use kits, which change only compatibly within a minor version (2026-10-28)
Every character spec was an edited copy of the template, with its weapons and hats modeled again, so a
template fix never reached earlier characters. `extends` merges a base (a built-in or project template, or a
path) deeply under the spec: the spec's keys win, lists are replaced, and `remove` deletes paths. `use` adds
kits, spec fragments with params, named `<as>_<name>` and attached `at` a frame; their materials and ramps
apply only where the spec has none of that name. Problems point at the kit's or base's line; `spec outline`
and `show` name every item's origin. `sx` is -1 inside an `_R` twin, so a kit's per-direction cheats stay
right on either side (redefining `yaw` there would change Hunt Tower's specs). 16 built-in kits (CC0, shipped
like the templates, ADR-010) were built by modeler agents and fixed after art-director reviews passed 3 of 9
weapons and 2 of 7 gear kits as built. The cacador extends the humanoid in 30 lines instead of 215, its 552
frames identical; the knight is 21 lines, under the plan's 250, though simpler than the Templar. Decided:
built-in templates and kits change only compatibly within a minor version, and a visual change comes under a
new name (`humanoid2`), not a version pin (`humanoid@0.3`); in 0.3 the templates got the sword kit and metal
steel. Cost accepted: `when:` switches whole parts only; weapons other than the sword need their own clips.

## ADR-044: The head and the hair are kits, and a character decides them in its brief (2026-10-30)
In the maintainer's two test projects of the 0.3 build, the first character of each came out with a head
that read as a ball and an unrequested "big nose". The templates modeled the head as a near-sphere with a
jaw inside it and a 1.5 px nose sphere, which the part's blend swelled and the outline doubled; every
modeler copied that recipe, the docs put heads with the round masses and asked for a nose in profile, and
no review looked at a face up close. Design 16 fixes the starting point, the instructions and the checks
together: the templates `use` a `head` kit (cranium, face plane, cheeks, a jaw down to the chin; `jaw`,
`chin`, `width`, `ears`, and `nose` 0 by default) and a `hair` kit in separate parts so strand lines show
(`fringe`, `part`, `locks`, `length`, `volume`), with `ponytail` and `bun` kits beside them; the style
interview records `face` (minimal, simple, detailed); `brief.head` states the head, and `validate` warns
while a character over a template has none; `pose --focus head` shows it at up to 12×, and the art
director judges every head there. `eye_L` stays a plain template part, since specs override it. Rejected:
keeping plain template parts with better numbers (no params, and nothing would make the AI decide), and a
`humanoid2` (0.3 is the release where templates may still change, ADR-043). Cost accepted: the cacador
example changes look, and a spec that extends a template with hair of its own also gets the kit's fringe
and locks until it removes `use.hair` (`validate` says so).
