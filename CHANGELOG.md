# Changelog

All notable changes to SpriteKiln. The output format has its own version (`docs/format.md`).

## 0.3.0 (2026-10-30)

### Upgrading from 0.2
- `spritekiln update` in a game folder installs 0.3 and refreshes the AI instructions there; run
  `spritekiln update --files` in your other game folders. It keeps the extras you installed: for the compiled
  renderer (about 6× faster), install it once with `pipx install --force "spritekiln[mcp,fast]"` (or
  `uv tool install --force "spritekiln[mcp,fast]"`).
- Renders change: soft shadows no longer come from bounding spheres, and a recorded style's look is applied
  by the renderer. Re-render an asset before you compare it with a 0.2 export.
- Specs keep working. Copies of the 0.2 templates keep their head and sword; new specs and specs that
  `extends` a template get the 0.3 ones (below).

### Heads, faces and hair
- The templates' head and hair are kits now: `head` (a cranium, a face plane and a jaw down to a chin; params
  `jaw`, `chin`, `width`, `nose` (none by default) and `ears`) and `hair` (crown, fringe, temple locks and back
  as separate parts, so lines between them read as hair; params `fringe`, `part`, `locks`, `length`,
  `volume`). `ponytail` and `bun` attach to the head for those styles. The old head was a ball with a small
  sphere for a nose, which first generations copied (a round head with a big nose).
- The style interview asks how much face a character shows: `face` minimal (eyes only, recommended), simple
  or detailed (`spritekiln style set --face`).
- `brief.head` says how a character's head, face and hair look; `validate` warns when a character over a
  built-in template has none, and when a spec replaces a kit part's shape while the kit's other parts stay
  (its own `parts.hair` under the hair kit's fringe and locks: add `remove: [use.hair]`).
- `spritekiln pose --focus head` (MCP `pose` with `focus`): a close-up, up to 12×, of a bone and everything
  attached below it, or of parts by name. The art director's checklist judges every head with it, and the
  recipe shows the user the model before anything is animated.
- The templates' `skin` has `gamma: 0.75`: under soft shading the side of a face turned from the light no
  longer drops to a tone as dark as the hair (it read as a beard in profile).
- Specs that extend a template change where they inherit its head, hair or skin: the cacador example looks
  different (its goldens were refreshed), and a spec that wrote its own hair over the template now also gets
  the kit's fringe and locks until it removes `use.hair`.

### Bases and kits: specs that state only what is their own
- `extends: humanoid` merges a base spec under a spec (a built-in template, a project template in
  `<specs>/templates/` or a path): the spec's keys win, lists are replaced, `remove: [parts.cape, use.sword]`
  drops what it does not want. A fix to a template reaches every spec that extends it.
- `use: [{kit: sword, as: sword, at: wrist_R, with: {length: 0.5}}]` adds a kit: parts, bones, sockets and
  channels with params, named `<as>_<name>`, mirrored when `as` ends in `_L`. Its materials and ramps apply
  only where the spec has none of that name, or map to the spec's (`materials: {steel: iron}`).
- 20 built-in kits (CC0), made with the shapes of 0.3: sword, axe, mace, hammer, spear, staff, bow, pistol,
  rifle, shield, helmet, hood, hat, cape, belt, pouch, and head, hair, ponytail and bun (below). `spritekiln
  kits` (MCP `kits`) lists them, and a kit's params and channels; `spritekiln pose <kit.yaml>` shows a kit on
  its host. A project's own kits go in
  `<specs>/kits/`.
- `spritekiln new <name> --extends` writes a short spec over the template instead of a copy.
  `spec outline` lists what comes from the base and the kits, `spec show` prints it from their files, and
  problems point at the file and line that wrote them.
- The humanoid and side templates hold their sword through the sword kit (a shaped blade with a guard and a
  pommel instead of two boxes), and their `steel` is `finish: metal`. The cacador now extends the humanoid:
  30 lines instead of 215, rendering exactly as before. A new example, the knight, is 21 lines of kits.
- `sx` in expressions is -1 inside an automatic `_R` twin: a cheat written with `yaw*sx` happens in the
  mirrored direction for the twin (kits use it for their `cheat` param).

### Faster renders, correct soft shading
- Each part is bounded by a tight sphere: frames render faster with the same part in every pixel (on the
  development machine, a Templar frame 6.6 s → 2.2 s; poses in 8 directions 1.5–2.6× faster).
- Soft shadows and ambient occlusion no longer darken surfaces near a part's bounding sphere: shading
  depends on the geometry only. Assets rendered again are lighter where those false shadows used to fall,
  so they do not match renders of 0.2 pixel for pixel.

### The project's style drives the render
- The look of the art style is applied by the renderer to every asset of the project: `outline` (selective,
  dark, and new: colored, with `outline_color` for dark), `shading` (soft, flat, and new: toon), and new fields
  `lines` (depth, depth+normal, none), `highlights`, `dither` (none, bayer2, bayer4: ordered, inside regions,
  anchored on each part), `light` (presets classic, top, dramatic, soft, flat) and `snap`. Specs no longer
  repeat it in their materials; a spec's `render:` block overrides it for one asset and a material's own
  fields win over both. `spritekiln style` lists the specs whose `render:` block differs.
- Projects whose style says `outline = "dark"` or `shading = "flat"` now get them from the renderer: materials
  that set `bands` or `outline` themselves keep them, the others change. A project without a recorded style,
  or with selective outlines and soft shading, renders as before.
- `spritekiln style preview [spec]` (MCP: `style_preview`): a pose under each choice side by side, from the
  render cache (the Templar switches style in 0.03-0.04 s per frame), for choosing with the user by looking.
  The interview gets a question about lines, highlights, dither and light, and one about snapping.
- `style set` takes `--outline-color`, `--lines`, `--highlights`, `--dither`, `--light` and `--snap`.

### Surface paint
- `paint:` on a part colours regions of its surface with other materials, without new geometry: a volume of
  primitives, or `stripes`, `rings`, `grid` (rivets), `spots` (noise) and `checker` patterns in the part's own
  space; `edge: true` draws a line around a region. A painted pixel keeps the part's light and takes the
  paint's ramp, outline colour and emissive flag. The Templar's three crosses as paint: 3 parts and 11 cuts
  fewer, the same picture, frames traced 12 % (numba) to 26 % (numpy) faster.
- The render cache format goes to 7 (the geometry buffer keeps each pixel's paint layer): caches of earlier
  versions are rendered again.

### Lines and edge lights inside a part
- `crease: true` on a material draws a line where a part folds inwards or over itself, and `edge_highlight:
  true` lights its convex edges facing the light; inner lines used to appear only between two parts. A spec's
  `render: {crease_angle, min_run}` tunes them.

### Materials that read as what they are
- `finish: matte | soft | metal | glossy` on a material: metal gets a small hard highlight and a strong rim,
  cloth stays matte. `highlight` (size, pixels per cluster, tone or colour), `rim` per material and `thresholds`
  (hard toon steps) can be set one by one. A material with a highlight keeps its ramp's top tone for it.

### Light and materials applied after the cache
- The render cache keeps each frame's geometry (part, depth, normal, soft shadow and occlusion per pixel) and
  the light, materials and palette are applied to it: after a change of `ambient`, `rim_strength`, a ramp or
  a material the gargoyle's 192 frames re-render in 10 s (50 ms per frame) instead of being traced again.
- Shading now comes from each pixel's averaged normal, shadow and occlusion: 2-4 % of pixels change tone at
  band borders compared with 0.2.
- `light: {mode: flat}`: one tone per material (`flat_band`), for games lit by the engine through the normal
  map.

### Shapes beyond rounded primitives
- New primitives: `extrude` (a 2D profile pushed along local z: blades, axe heads, shields, plates), `revolve`
  (a cross-section turned about local y, fully or partly: helmets, hats, bottles, pauldrons), `tube` (a smooth
  tapered tube through control points: horns, tails, straps, hair) and `plane` (a flat cut, under `cut:`).
- Profiles for `extrude` and `revolve`: `circle`, `rect` with `chamfer` or `round`, `polygon` and `bezier`
  (closed quadratic curves).
- Modifiers on a primitive (not on a `chain` or a `membrane`): `shell` (hollow: capes, hoods, sleeves),
  `elongate`, `twist` and `bend`.
- Joins: `blend: {mode: chamfer|round|stairs, k, n}` and `cut_blend: {mode: groove, depth, width}` (a line
  engraved where a cutter crosses the part). The smooth union stays the default and renders as before.
- `_L` parts with these shapes mirror correctly to `_R`, asymmetric profiles and bends included.
- `validate` warns about a shell, an extrusion, a tube or a profile thinner than one pixel (in the numbers the
  spec uses, under scaled bones too) and about polygons whose edges cross, and counts the primitives and cuts.
  The knowledge files have a "which shape for what" table, notes from porting the showcase, and eight recipes
  checked on the humanoid template.
- `ref compare -o` takes a folder.

### Thin parts and steady pixels
- Parts take `priority` (the weight of their samples in the pixel vote) and `min_cover` (how many samples fill
  a pixel even below the camera's coverage): a staff thinner than a third of a pixel, which used to vanish, now
  shows in all 8 directions. Defaults keep every existing spec as it was.
- `snap: [root, torso_rot]` rounds the on-screen movement of those frames to whole pixels: it halves the shading
  that blinks from frame to frame on the Templar's and the Huntress's idles (not on the gargoyle's, whose wings
  move on their own: check `boil`).
- QA measures that blinking (`boil` in `qa.json`, per animation and direction) and warns when it passes 4 % of
  the inside while the silhouette barely moves.

### A compiled renderer: the `[fast]` extra
- `pipx install "spritekiln[mcp,fast]"` adds a numba renderer that SpriteKiln uses whenever it is installed:
  whole frames about 4-6× faster (the Templar's full render, 456 frames: 194 s in one process), using every
  core in one process instead of several numpy processes. It agrees with the numpy renderer on every part and
  on all but a handful of pixels per frame; the render cache keeps the two apart. `--backend numpy|numba|auto`
  on `pose`, `render`, `review` and `ref`, or `SPRITEKILN_BACKEND`. The first run compiles it (about 10 s,
  once). No Intel Mac build: there the numpy renderer stays. `spritekiln update` keeps the extra.

### Draft previews
- `pose --draft` (MCP `pose(draft=true)`) traces one ray per pixel instead of nine: an 8-direction pose of the
  Templar takes 5 s instead of 15 s, for shaping silhouettes and poses. Files end in `_draft`.
- `render --draft` writes only GIFs and contact sheets, in `preview-draft/`, to check motion; it writes no atlas,
  JSON or QA and cannot be exported.

### Pixel-exact previews
- Previews are cropped to what the sprite shows and zoomed by whole factors that fit an AI's image budget
  (about 1500 px and 1.15 megapixels): `pose`, contact sheets, GIFs, the `review` and `ref compare` sheets. AI
  clients used to receive them shrunk by fractions, which made pixels uneven. The Templar's idle contact sheet
  goes from 2358 × 2354 px to 982 × 1138 px.
- `pose --scale` is now the largest zoom; `pose --no-crop` keeps whole frames. MCP `pose` returns the `zoom` and
  the `crop` box; MCP tools cut an image that is still too large into pieces instead of shrinking it.

### Read only what you edit
- `spritekiln spec outline <spec>` maps a spec file: each part, animation, IK chain and socket with its line
  range and a summary, the other sections as one line of names. The Huntress's outline is 6.1 KB; its spec
  is 41 KB. `--json` gives the same as data.
- `spritekiln spec show <spec> parts.helm animations.walk.keys[2]` prints the numbered source lines of those
  blocks, comments kept; a mirrored `_R` item shows its `_L` source; `--resolved` shows a block as the
  renderer reads it. MCP tools `spec_outline` and `spec_show`.

## 0.2.0 (2026-10-25)

### Upgrading from 0.1.0
0.1.0 has no `update` command yet: upgrade once with `pipx upgrade spritekiln` (or `uv tool upgrade
spritekiln`), then run `spritekiln update --files` in each game folder to refresh the instructions your AI
reads. From 0.2.0 on, `spritekiln update` does both.

### The art style, asked before the first asset
- Before the first asset of a project, the assistant interviews you about the art style: view, how many
  pixels tall a character is on screen, directions and mirroring, colours, outline and shading,
  proportions, the feel of the animation and references. It pushes back on vague answers, proposes answers
  from what it already knows (the request, a splash art, existing specs) and confirms a summary.
- `spritekiln style set` records the answers in the `[style]` table of `spritekiln.toml` and turns the
  numeric ones into defaults for `spritekiln new` (`camera.scale` and the frame `size` come from the
  character height). Every later asset follows the style; it changes only when you ask, one answer at a
  time.
- `spritekiln style` shows the style, suggests answers from the specs a project already has, and lists the
  specs that no longer match it. MCP tool `style`; knowledge file `style.md`, read by the modeler, animator
  and art-director roles. `spritekiln new` reminds you when a project has no style yet.

### Updating
- `spritekiln update` upgrades SpriteKiln the way it was installed (pipx, uv or a virtual environment,
  keeping its extras) and refreshes the current game folder's AI files (knowledge files, skills, agents,
  marked blocks, the Godot addon when it is installed and older) without touching `spritekiln.toml`,
  specs or renders. `--check` only looks; `--files` only refreshes. In a virtual environment on Windows,
  run it as `python -m spritekiln update` (Windows cannot replace the running `spritekiln.exe`).
- `spritekiln init` records the project's assistants (`ai` in `spritekiln.toml`) and stamps the version of
  its AI files; commands note a project whose files come from another version. `init --force` keeps a
  recorded art style.

## 0.1.0 (2026-10-22)

First public release. SpriteKiln started as `pxforge`, the sprite toolkit of the game Hunt Tower.

### Making sprites
- Characters and props as YAML specs: skeleton with expressions and 2-bone IK, smooth SDF primitives,
  materials with palette ramps, emissive and glow, mirrored `_L`/`_R` parts.
- Animations from cycles or keys with per-frame timing, tweens and easing, events (`hit`, `step_l`...),
  per-direction cheats, smears, and timing targets checked by `validate` and QA.
- Top-down 3/4 view in 8 directions, or a side view (`view: side`) with a platformer template
  (`side_humanoid`: run, jump, rise, fall, land, crouch, attack, hurt, death); `mirror: true` renders
  only the right-facing directions (5 of 8, or 1 of 2 in a side view) for symmetric designs.
- Sockets: attachment points (muzzles, hands, impact points) exported per frame.
- Output: atlas, normal map and emissive map, Aseprite-compatible JSON (output format 1), GIFs, contact
  sheets and `qa.json`.
- `spritekiln review`: art-direction report (value, contrast, pixels per material, silhouette IoU).
- `spritekiln ref prep|compare`: model from a splash art, with a pitch-corrected silhouette comparison.
- Render cache, memory-aware worker pool, `--size` to rescale.

### Working with AIs
- `docs/agent/`: one source of knowledge, generated into AGENTS.md, CLAUDE.md, GEMINI.md, Copilot and
  Cursor rules, Claude Code skills and agents.
- `spritekiln init --engine ... --ai ...` sets up a game project; `spritekiln mcp` serves the operations
  as MCP tools that return images and JSON.
- JSON Schema for specs, with editor autocompletion and `file:line:column` errors.

### Engines
- Godot 4: `KilnSprite2D` addon (exact timing, events, sockets, emissive layer, mirroring) and an editor
  plugin that builds SpriteFrames and scenes from render JSONs.
- Unity 2022.3+ (tested on 6000.3): UPM package with a `.kiln` importer and `KilnAnimator`.
- MonoGame 3.8: `KilnSprite.cs` runtime and the `KilnLit.fx` normal-mapped light shader.
- Example projects for Godot and MonoGame, a package sample for Unity; a guide for Phaser, LÖVE, Defold
  and GameMaker.

### Examples and docs
- Example characters (CC0): a gargoyle, a hunter, Wren (side view), and props; the Huntress and the
  Templar of Hunt Tower as a showcase.
- Tutorials: install (Windows, macOS, Linux), first character, from your splash art, animations and
  events, a platformer character, use with your AI; engine guides.

### Compatibility
- Windows, macOS (Apple Silicon and Intel) and Linux, Python 3.10 to 3.15. CI installs it with the README's
  commands on clean machines of each, and checks the published package every week.
- `python -m pxforge`, the `pxforge` command, `pxforge: 1` spec headers and the `PxSprite2D` Godot addon
  keep working for projects made with pxforge.
