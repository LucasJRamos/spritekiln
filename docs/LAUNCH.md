# Launch plan: pxforge → SpriteKiln v0.1.0

> **Status:** Phases 0-2 approved. Phase 3 done on 2026-10-21, awaiting the maintainer's review
> (checkpoint). Next: Phase 4.
> Internal working document. It is trimmed or removed before the public v0.1.0 release.

## Goal
Open-source the toolkit so any indie dev can generate animated 8-direction top-down pixel art
(characters, monsters, props) from procedural SDF models described in YAML, driven by whatever coding
AI they already use (Claude, Codex, Cursor, Copilot, Gemini...), and integrate the output in any engine
(Godot, Unity, MonoGame, or anything that reads atlas + JSON). Tutorials must be simple enough for a dev
to do the integrations alone. The Hunt Tower game (Templar, Huntress) is the showcase and the source of
requirements.

## Ground rules
- **One phase at a time.** Each phase ends with a review package (what changed, how to test, images,
  risks) and waits for the maintainer's OK.
- **Hunt Tower keeps working until Phase 6.** Do not rename or move this folder; keep
  `python -m pxforge`, the current CLI, the `pxforge: 1` spec header and `PxSprite2D` working (alias or
  shim); **never edit anything in `D:\GameProjects\tower-hunt`** (read-only). The game depends on
  `tools/px.cmd` (this folder's `.venv`), the skill junctions in `tower-hunt/.claude/skills/`, the spec
  paths `specs/characters/<name>/<name>.yaml` and the exported `assets/pxforge/<name>/`.
- **Memory:** `--jobs 1` or `2` on the dev machine (16 GB, often < 1.5 GB free) until automatic job
  sizing exists.
- **Git:** local commits per task; no remote and no push until the maintainer asks. History may be
  squashed before the first push.
- **Rendered output** (`out/`, `.pxcache/`) never goes into git. Exception: curated images for the
  showcase and docs, copied to `docs/media/` or `showcase/` with controlled size.
- **Language:** everything in the repository is English; `README.pt-BR.md` is the translation.
- **Visual claims** are only made after opening the PNGs. Iterate with `pose`; full `render` at the end.
- **Regression:** every engine change runs the golden tests (and the gargoyle pose). An intentional
  visual change updates the goldens with the reason in the commit message.
- **Anti-loop:** at most 2 attempts per failure; on the 3rd, stop and report symptom, hypotheses,
  evidence and a proposal.
- **Decisions** go to [`docs/decisions.md`](decisions.md) as short ADRs. Open maintainer questions are
  asked, never assumed.

## Decisions already taken (do not reopen)
- License: MIT for code; CC0 for the generic examples (gargoyle, cacador, props, humanoid template).
- English first, `README.pt-BR.md` translation; translate comments, docs, skills and CLI messages.
- Templar and Huntress are the showcase, including models, animations and the original splash arts
  ("From this → to this").
- Name: **SpriteKiln** (package/CLI `spritekiln`), confirmed 2026-10-21. Rechecked
  2026-10-21: `spritekiln` and `sprite-kiln` are free on PyPI; no GitHub repo named spritekiln.

## Answered on 2026-10-21 (see `docs/decisions.md`)
Name **SpriteKiln** (ADR-001) · owner **LucasJRamos** (ADR-002) · showcase **all rights reserved,
demonstration only** (ADR-003) · Unity validation on **6000.3** (ADR-005) · **Python 3.10+** (ADR-004).

Also answered on 2026-10-21: private repository `LucasJRamos/spritekiln` created and pushed (public at
launch); the `mine` prop moved to the showcase license; the old `.pxcache/` folders (1.37 GB) deleted.

Answered later on 2026-10-21: `legacy/` deleted from disk; the cacador's `splash_teste.jpg` is the
toolkit's own output (CC0).

## Open questions (maintainer)
- None.

## Audit (2026-10-21)
State: ~2,270 lines of Python (`pxforge/`), no git, no tests, no CI, no license. Code untouched since
2026-10-19; every `out/` is newer than its spec, and the 8 exported assets in Hunt Tower are
byte-identical to `specs/**/out/` (empty emissive maps are deleted by the exporter, as designed).

**P0: blocks packaging, safety or the launch**
1. *Resources resolved from the source checkout.* `new` reads `specs/templates/` (`cli.py:163`), the
   palette fallback reads `specs/palettes/` (`spec.py:74`), the Godot exporter copies
   `integrations/godot/addons/` (`godot.py:17`). All break under `pipx install`. They must become
   package data.
2. *Render cache.* Pickle files (`pipeline.py:47`): opening a project with a planted `.pxcache` runs
   arbitrary code. The key ignores the engine version (manual `v=3`, `pipeline.py:31`), so an engine
   change silently reuses stale buffers. Unbounded size: the Templar and Huntress caches hold 1.4 GB.
3. *Memory.* Default `--jobs` = CPU count − 1 (15 here, `pipeline.py:101`) exhausts RAM. A dead worker
   raises `BrokenProcessPool` and all in-memory frames are lost (finished buffers survive in the
   cache, so a re-run resumes, but nothing says so).
4. *No safety net.* No tests, CI, lint, license, or output format versioning.
5. *Licensing is mixed by path.* Showcase material (Templar, Huntress, their splash arts and palettes,
   game captures in `research/`) sits next to CC0 examples in `specs/`. It needs per-path licensing
   before any push.

**P1: correctness and format**
6. `yaw` is not available in animation channel expressions: `rest_env` fixes `yaw=0` (`rig.py:55`) and
   `frames_of` evaluates channels before the direction is known (`anim.py`). Bones and parts do see
   `yaw`. `SPEC.md` documents `yaw` as available everywhere, which is misleading.
7. The output JSON has no format version (`meta.version: '1'` is Aseprite's slot) and no camera
   metadata (pitch, scale, px per unit, ground factor K = sin 38°). Event timing semantics are
   undocumented. The `loop` default is re-derived in three places (`export.py:86`, `qa.py:44`,
   `PxSprite2D`).
8. `PxSprite2D.play_anim` fires frame-0 events synchronously, other frames on `frame_changed`; the game
   measured a 1-tick offset. QA cannot check declared event timings.
9. Library code calls `sys.exit` / raises `SystemExit` (`cli._spec`, `godot._find_project`,
   `export_godot`); user errors surface as raw tracebacks (e.g. an unknown `--anim` raises `KeyError`).
   This blocks an MCP server and hurts UX.
10. `render --size` reaches the spec loader through a hidden env var (`PXFORGE_SIZE`, `spec.py:95`).
11. Validation errors have no YAML line/column; unknown keys are silently ignored (a typo such as
    `materail:` passes); there is no JSON Schema.
12. `ref compare` scores IoU against the raw splash (ceiling ≈ 0.56 because of the 38° pitch); `ref prep`
    fills holes (`_fill_holes`), closing the gap between the legs.

**P2: quality, performance, hygiene**
13. User-facing text is Portuguese (CLI help, QA messages, docs, skills, addon, `plugin.cfg`).
14. Performance: `compose()` loops per pixel in Python (`pixelize.py`); each worker job recomputes the
    whole animation with `frames_of` for a single frame (`pipeline.py:85`). Uncached cost measured on
    2026-10-21: Templar 9.5 s/frame, Huntress 3.3 s/frame (96 px), ~85 MB peak per process.
15. File handles left open (`json.dump(..., open(...))` in `cli.py`, `open().write` in `cli.py` and
    `godot.py`).
16. Dead or derived files: `legacy/` (first prototype, imported by nothing), `requirements.txt`
    (duplicates `pyproject.toml`), `pxforge.egg-info/`, `*_ref/` folders (output of `ref prep`), two cache
    locations (root `.pxcache/` and per-spec `.pxcache/`). No `.gitattributes` for line endings.
17. MonoGame runtime has no sample project and has never been compiled here; the Godot addon has no
    automated test.
18. Agents are pinned to `model: opus`; skills and agents exist only for Claude Code.
19. Expressions are sandboxed (AST whitelist, no attributes, no builtins), but `**` can still burn CPU on
    hostile input. Acceptable for local specs; note it for the MCP server.

**Found by the Phase 0 tests**
20. `palette.kmeans` crashes (`ValueError: Probabilities contain NaN`) when the image has fewer distinct
    colours than `k`: `palette extract` and `ref prep` fail on flat-colour art. Pinned by a strict
    `xfail` in `tests/test_palette.py`; fix in Phase 1. *(Fixed in Phase 1.)*

**Found in Phase 1**
21. `PxSprite2D` emits frame-0 events twice when `play_anim()` runs before the node enters the tree:
    `_ready()` then replays the clip because of `auto_play` (found in Phase 4; the first guess,
    `frame_changed`, was wrong). Reproduced headless in Godot 4.7.2 with the addon copy Hunt Tower ships
    (`windup` arrives twice before `hit`). Likely the "1 tick" event offset the game saw. *(Fixed in
    `KilnSprite2D`, Phase 4; the game keeps its own `PxSprite2D` copy until Phase 6.)*
22. The OOM kills during Hunt Tower renders came from numpy: OpenBLAS commits ~500 MB per process at
    import on a 16-thread CPU. Fixed in Phase 1 (ADR-012).
23. QA told the user to *reduce* `camera.scale` for a clipped sprite; zooming out means increasing it.
    Fixed in Phase 1.
24. `spritekiln godot` only exports from `<spec dir>/out/<name>/`; it has no option for a render made with
    `render -o`. *(Fixed in Phase 4: `--render-dir`.)*

**Found in Phase 4**
25. In `PxSprite2D`, when a listener of `px_event`/`px_finished` starts another clip, the listeners after
    it receive the new clip's name: Godot passes the `anim` member itself, not a copy. *(Fixed in
    `KilnSprite2D`; `PxSprite2D` unchanged until Phase 6.)*
26. On Windows, text outputs (render JSON, Godot `.tres`/`.tscn`) are written with CRLF line endings. Godot
    and the importers read both, and git normalizes them, but the bytes differ between platforms. Decide
    in Phase 6 together with the Hunt Tower re-export check (switching to LF changes the files the game has).

**What leaves the repository:** `legacy/` (not versioned; delete when the maintainer agrees),
`research/` (not versioned: raw session material with game captures and scratchpad paths; Phase 2 ports
the scripts into `review`, Phase 5 copies chosen images into `showcase/`), `KICKOFF.md` (superseded by
this file), `requirements.txt` (Phase 1, after `pyproject` is complete).

---

## Phase 0: foundation (no behavior change)
- [x] 0.1 `git init` (branch `main`), `.gitignore` (`.venv/`, `.pxcache/`, `out/`, `*.egg-info/`,
      `__pycache__/`, `ref prep` outputs). Local-only paths in `.git/info/exclude` (`KICKOFF.md`,
      `legacy/`, `research/`).
- [x] 0.2 Audit (section above).
- [x] 0.3 Licensing: root `LICENSE` (MIT + scope note), `LICENSES/` with the full texts (MIT, CC0-1.0,
      showcase license), and a [REUSE](https://reuse.software) `REUSE.toml` that maps paths to licenses
      (`reuse lint` passes). Showcase files stay where they are until Phase 5/6 (the game uses the
      paths). See ADR-003.
- [x] 0.4 pytest baseline (`[project.optional-dependencies] dev`): unit tests for `expr`, `spec`,
      `palette`.
- [x] 0.5 Golden images: `pose --dirs all` of the gargoyle and of a minimal fixture spec, plus a full
      `render` (atlas, normal, emissive, JSON) of the fixture. Each test uses a fresh temporary cache,
      so a stale cache cannot hide a regression. Tolerance: exact on the platform that produced the
      goldens (recorded next to them); elsewhere ≤ 0.5 % of pixels may differ.
- [x] 0.6 Showcase reproduction: a cache-less re-render of Templar and Huntress must match the current
      `out/` (identical to the game's assets). Pixel hashes per atlas and per frame go to
      `tests/golden/showcase.json` (no showcase pixels in `tests/`); opt-in slow test (`pytest -m slow`).
      Result 2026-10-21: atlases, normal and emissive maps, JSON and `qa.json` are **byte-identical**
      for both (`--jobs 2`, empty cache: Templar 456 frames in 2,557 s, Huntress 536 frames in
      1,091 s, main process peak 250 MB).
- [x] 0.7 `docs/decisions.md` with the ADRs taken so far.

**Done when:** `pytest` is green, golden images are versioned, this plan is approved.

## Phase 1: robust, packageable core
- [x] Rename to `spritekiln` (rechecked free on PyPI and GitHub on 2026-10-21). `pxforge` shim package
      and command; specs accept `spritekiln: 1` and `pxforge: 1` (ADR-009).
- [x] Templates, palettes and the Godot addon ship in the wheel (audit #1, ADR-010).
- [x] Full `pyproject.toml` (hatchling): metadata, classifiers, extras `splash` / `mcp` / `dev`.
      `requirements.txt` dropped.
- [x] JSON Schema for the spec (`spritekiln/data/spec.schema.json`, VS Code mapping in `.vscode/`);
      every problem with file:line:column; unknown keys are warnings with suggestions; `validate --strict`
      (audit #11, ADR-013).
- [x] Spec version header and **output format 1** in `docs/format.md`: Aseprite-compatible JSON +
      `spritekiln` block with format, generator, camera metadata (pitch, px per unit, `ground_k`,
      `height_k`), exact event timing; integrations read both block keys (audit #7, #8, ADR-014).
- [x] Memory-aware render: one BLAS thread, `--jobs` from available RAM, progress, resume message, dead
      worker → pool restarts with half the jobs; out of memory or Ctrl+C explain how to resume
      (audit #3, #22, ADR-012).
- [x] Safe, versioned cache: `.npz` without pickle, engine hash in the key, atomic writes, 1 GB LRU cap
      per spec, `spritekiln cache info|prune|clear [--legacy]` (audit #2, ADR-011).
- [x] Errors as exceptions in the library, one-line messages in the CLI, no `PXFORGE_SIZE` side
      channel; CLI, QA and `ref` text in English (audit #9, #10, #13 partly, #23).
- [x] `palette.kmeans` with fewer distinct colours than `k` (audit #20).
- [x] ruff (lint + format) and `.github/workflows/ci.yml`: lint + REUSE; Windows, Ubuntu, macOS ×
      Python 3.10–3.13 with tests, goldens and a small render; packaging job with `pipx` in an empty
      folder.

**Done when:** `pipx install .` works in a clean folder, CI is green, Hunt Tower still works unchanged
(checked by reading/running only), and the goldens did not change.

Results (2026-10-21):
- `pipx install .` (isolated `PIPX_HOME`) then, from an empty folder: `new`, `validate --strict`,
  `render`, the `pxforge` alias and `cache info` work; the wheel carries `data/` (template, palettes,
  addon, schema).
- CI: the first run on GitHub (private repo `LucasJRamos/spritekiln`) was green on all 15 jobs: lint +
  REUSE, Windows/Ubuntu/macOS × Python 3.10–3.13, packaging with `pipx`. Locally too: Windows with Python
  3.10 (numpy 2.2), 3.11 (numpy 2.4), 3.12 and 3.13; Ubuntu 24.04 (WSL, fresh clone), where the golden
  images match pixel for pixel.
- Hunt Tower: `tools/px.cmd validate` works. In scratch Godot 4.7.2 projects (headless), the scene
  exported by `pxforge render --godot` plays with the **addon copy the game ships**, and the new addon
  plays both block keys: same clip, directions, pivot and events. Nothing in `D:\GameProjects\tower-hunt`
  was written.
- Goldens: images and Godot resources unchanged. The render JSON golden changed on purpose (additive
  format-1 fields). Showcase partial re-runs (hurt, dash, death; pool of 4, new cache) still match the
  shipped frames bit for bit.

## Phase 2: features Hunt Tower proved missing
- [x] **Sockets:** `sockets: {muzzle_L: {bone: pistol_L, offset: [...], when: ...}}` with automatic `_R`
      twins; per frame and direction `[x, y, depth]` in px from the pivot, depth > 0 in front of the body
      (ADR-016); `null` while hidden. Godot `get_socket()` / `get_socket_depth()` / `has_socket()`,
      MonoGame `TryGetSocket()` (Unity in Phase 4). The Huntress declares muzzles, hands, mine and feet.
- [x] **`yaw` / `dir` in channel expressions** (ADR-015); old specs render identically.
- [x] **`spritekiln review`:** JSON + PNG with L* median/p90 under the scene light and against the floor,
      pixels per material and direction, band usage, camera-corrected IoU, legibility next to another
      asset (`--against`), zoomed sheets per clip; `review:` targets as QA warnings (ADR-017).
- [x] **Background preview:** `--bg` / `--tint` in `pose`, `render` (previews only) and `review`.
- [x] **Timing targets:** `timing: {shoot_r: {release: 2f, total: 7f}}` (frames or ms, 60 fps, ±1 f) are
      errors in `validate` and QA; the showcase specs declare the targets their comments described.
- [x] **Better `ref prep`:** background grown from the border (gradients work), gaps kept open,
      `cutout_pitch38.png`; `ref compare` squashes the reference by cos(pitch) (ADR-018).

Results (2026-10-21):
- **Muzzle criterion (≤ 1 px):** the centre of the pixels the muzzle flash adds is within **0.29 px** of the
  socket in all 8 directions, for both pistols and the rifle (slow test). Hunt Tower's hand-measured table
  (`huntress_rig.tscn`) differs from the sockets by 0.5–1.3 px.
- **`yaw` proof:** the Huntress no longer has the helper channels `gyaw_s`, `rpitch_s`, `ryaw_s`; the cheats
  live in the keys. A cache-less re-render of the six affected clips (232 frames) matches the shipped
  frames bit for bit.
- **Cutouts:** against the hand-made alpha cutouts, Huntress IoU 0.745 → 0.925 and Templar 0.664 → 0.914.
  `ref compare` on the Huntress idle: 0.594 raw → 0.687 corrected.
- **Review** of the Huntress over the game floor under the night light: L* 7–14 on a floor of L* 13,
  ~0.4× the Templar's area and 7–23 L* darker, the session's diagnosis in numbers.
- **Integrations:** `get_socket()` checked headless in Godot 4.7.2; the MonoGame runtime compiles against
  MonoGame 3.8.2 (first time).
- **Timing:** Huntress shots, mine, dash, hurt and Templar hits meet their declared targets.
- Tests: 175 fast (unit, golden, CLI, review, sockets, timing) plus slow showcase and muzzle tests.

## Phase 3: any AI
- [x] Single source of knowledge in `docs/agent/` (English): workflow, spec reference, modeling,
      splash → model, animation (timing, events, sockets), art-direction checklist with the `review`
      numbers, the multi-agent recipe; includes how an AI without image input works from numbers.
- [x] `AGENTS.md` and generated adapters (`spritekiln/agents.py`, `--check` in the tests): `CLAUDE.md`,
      `.claude/skills` and `.claude/agents` (model recommended, not pinned), `.cursor/rules/spritekiln.mdc`,
      `.github/copilot-instructions.md`, `GEMINI.md`. Existing files only get a marked block. The
      `.claude/skills/pxforge*` folders Hunt Tower links are generated too, with `python -m pxforge`.
- [x] MCP server `spritekiln mcp` (stdio, `mcp` extra, SDK 2.x): guide, new, validate, pose, render, review,
      ref_compare, export, schema; JSON plus images.
- [x] `spritekiln init --engine ... --ai ...`: `spritekiln.toml` (specs, engine, export folder, Godot project,
      defaults for new specs), specs folders, knowledge in `.spritekiln/agent`, AI adapters, MCP client
      configs, `.gitignore` entries. `spritekiln export` and `render --export` use it.
- [x] Image-capable vs. text-only AIs documented (`docs/agent/recipe.md`).

**Done when:** an empty project with `init` + an AI other than Claude (or a script that simulates use
through MCP) generates a character from the template and exports it.

Results (2026-10-21):
- `tests/test_init.py::test_phase3_criterion_codex_project_through_mcp`: an empty Godot project, `init
  --engine godot --ai codex`, then a real MCP client over stdio calls guide → new (template) → validate →
  pose (image) → render (QA ok) → export, ending with `assets/spritekiln/hero/hero.tscn` and the addon.
- The MCP server worked on the first run against the SDK 2.3 client; tests pass on Python 3.10 too.
- Real Codex run (2026-10-21, Codex CLI 0.163, `codex exec -s workspace-write`, maintainer's OK): in an empty
  Godot project set up with `init --engine godot --ai codex`, the one-line request "a hooded goblin scout,
  64 px, top-down" ended with an original goblin (hood, ears, pack, blade) in 8 directions, idle/walk/attack
  rendered (176 frames, QA clean) and exported with the addon, ~64k tokens. Codex read AGENTS.md and the
  knowledge files and followed the loop (validate, pose in all directions, contact sheets). Findings, both
  addressed: it regenerated the spec with `yaml.safe_dump` (comments and flow style lost; `workflow.md` now
  says to edit in place), and the Microsoft Store Python of the test venv cannot be started from Codex's
  sandbox (it built its own venv with uv; the AI tutorial now says so). Earlier attempts failed only because
  the project lived under `AppData\Local\Temp`, which the sandbox denies.

## Side-scroller (`view: side`), added 2026-10-21 at the maintainer's request
Users choose top-down 3/4 (default) or side-scroller with the same engine and workflow. The evaluation
showed the renderer needed no change: a side view is the same 3D model with the camera at 0°, profile
directions `e`/`w` and no ground ellipse.

Done now:
- [x] `view: topdown | side` spec preset (pitch, directions, shadow; explicit values win), in the schema and
      in the JSON (`view`); `new --view`, `init --view` (project default), MCP `new(view=...)`; `pose` and
      `review` show the spec's own directions in a side view.
- [x] Docs: views table in `spec.md`, side-view notes in workflow, modeling and animation.
- [x] Tests: preset, explicit overrides, side project, JSON, golden of the fixture in profile.

Next, in the phases below (marked **[side]**):
- Phase 4: engines handle two-direction clips and offer mirroring (`flip_h`) as an option.
- Phase 4: a `mirror` export option: render one profile and let engines flip it (half the atlas; the light
  comes from the other side, so it is opt-in).
- Phase 5: a side-view template (`--template side_humanoid`: idle, run, jump/rise/fall/land, crouch,
  attack, hurt, death) and a side-scroller example asset made with the recipe; tutorial "a platformer
  character".
- v0.2: side-view tiles (platforms, slopes) and parallax backgrounds, with the tiles work in the ROADMAP.

## Phase 4: engines
- [x] **Godot 4:** new addon `addons/spritekiln` (`KilnSprite2D`, `KilnBuilder`, editor plugin that builds
      SpriteFrames and scenes from render JSONs without the CLI, icon, README); `spritekiln godot
      --render-dir`; Asset Library zip (`tools/package_godot_addon.py`, "Custom" download URL);
      `examples/godot` (gargoyle with light, emissive, events and the `strike` socket); headless tests
      with Godot 4.7.2 (addon behaviour + the example driven by simulated input). The old addon stays
      for Hunt Tower (audit #21, #25).
- [x] **Unity** (`integrations/unity`, UPM by git URL): `.kiln` ScriptedImporter (ADR-024) with sprites
      (`_NormalMap` secondary texture), AnimationClips with AnimationEvents and flipX; `KilnAnimator`;
      sample "Gargoyle demo". Validated in Unity 6000.3.6f1 batch mode (`tests/test_unity_runtime.py`:
      import, timing, events, mirroring with a pixel-exact render, sockets, side view) and compiled
      against its assemblies with warnings as errors. Emissive is an unlit child renderer rather than
      `_MaskTex`, which URP uses for light blending, not emission.
- [x] **MonoGame:** `integrations/monogame/KilnSprite.cs` (replaces `PxSprite.cs`; mirroring, emissive
      pass, sockets) and `KilnLit.fx` (up to 4 point lights through the normal map, mirrored normals by
      `ddx`); `examples/monogame` (DesktopGL, MonoGame 3.8.4). `tests/test_monogame_runtime.py` runs the
      animator headless and the example with a scripted run that saves a frame.
- [x] **[side]** Two-direction (e/w) clips play in every runtime; `mirror: true` renders one profile and
      the runtimes flip the other (ADR-025).
- [x] **Generic:** `docs/engines/generic.md` (Phaser, LÖVE, Defold, GameMaker), marked as untested sketches.
- [x] Tutorials: `docs/engines/godot.md`, `unity.md`, `monogame.md`, `generic.md`.
- Engine tests are opt-in (`SPRITEKILN_GODOT_BIN`, `SPRITEKILN_UNITY_BIN`, `SPRITEKILN_MONOGAME=1`). CI runs
  the Godot ones headless on Linux (job `godot`, added in Phase 5); Unity needs a license and MonoGame a
  window, so they stay local.
- Asset Library listing: icon, screenshots and form text in `integrations/godot/assetlib/` (Phase 5).

**Done when:** each integration has a minimal example that runs and a tutorial.

## Phase 5: showcase, docs, launch
- [ ] English README: Huntress 8-direction turnaround GIF and "From this → to this" at the top; what it
      is; features; 3-command quick start; YAML → SDF → render → pixelize → atlas diagram; the AI recipe;
      engine and AI matrices; showcase, roadmap, licenses.
- [ ] `README.pt-BR.md`.
- [ ] `showcase/`: Templar and Huntress (spec, splash, turnaround/GIFs, contact sheets) and game images
      (copied from `tower-hunt/captures/` and `research/.../images/`; optional short Movie Maker clip,
      reading the game project without changing it).
- [ ] Tutorials in `docs/`: first character in 10 minutes; from your splash art with an AI; animations
      and events; Godot; Unity; MonoGame/generic; use with your AI (MCP and AGENTS.md); spec reference
      (from `SPEC.md`).
- [ ] **[side]** Side-view template (`side_humanoid`), a side-scroller example asset and the tutorial "a
      platformer character".
- [ ] Translate the comments of the humanoid template and the example specs to English.
- [ ] `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates, `CHANGELOG.md`; optional MkDocs
      Material site on GitHub Pages.
- [ ] Release v0.1.0: PyPI via trusted publishing in Actions; tag + release notes; Godot Asset Library
      submission; announcement text (r/godot, r/gamedev, r/PixelArt, itch.io devlog, X).
- Scope of v0.1: characters and props. Tiles and VFX are v0.2 (see `docs/ROADMAP.md`).

## Phase 6: Hunt Tower migration (only with the maintainer's OK, in a game-project session)
- [ ] The game uses the installed package at a pinned version: `spritekiln.toml` replaces `px.cmd`.
- [ ] Junctions/skills replaced by the adapters generated by `init`.
- [ ] `PxSprite2D` kept or aliased.
- [ ] Re-export of the assets identical to the current ones.
- [ ] A ready-to-run migration script is delivered at the end of Phase 5.
