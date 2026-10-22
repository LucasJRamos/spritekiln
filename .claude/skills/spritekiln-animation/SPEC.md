# Spec reference

A character or prop is **one YAML file** (`<specs>/characters/<name>/<name>.yaml`). SpriteKiln reads the
spec, builds a skeleton, generates SDF geometry (smooth primitives), renders it with a top-down 3/4 camera
and turns the result into pixel art. Editors with a YAML language server (VS Code's YAML extension, for
example) autocomplete and check specs from the JSON Schema when the spec carries the line the templates start
with: `# yaml-language-server: $schema=https://raw.githubusercontent.com/LucasJRamos/spritekiln/main/spritekiln/data/spec.schema.json`.

```yaml
spritekiln: 1            # spec format version (first line)
name: gargoyle           # names the exported files
kind: character          # character | prop
view: topdown            # topdown (3/4, 8 directions) | side (side-scroller profile, e and w)
size: 64                 # frame size in px (32/48/64/96/128); `render --size` rescales without editing
directions: 8            # 1 | 4 | 8 | [s, e, n, w]
mirror: false            # true: render only the right-facing half; engines flip it for the left (optional)
palette: gothic          # built-in name, file path(s) relative to the spec, or a list
camera: {pitch: 38, scale: 0.050, center: [0, 1.0, 0]}   # scale = world units per pixel
shadow: {rx: 13.5, ry: 4.5, alpha: 120}                  # ground ellipse in px; `shadow: null` turns it off
light:  {dir: [-0.55, 1, 0.45], rim: [0.8, 0.35, -0.9], rim_strength: 0.45, ambient: 0.12}
brief: {...}             # free text: summary, must_keep, simplify, reference (ignored by the renderer)
materials: {...}
channels: {...}
bones: {...}
ik: {...}
parts: {...}
animations: {...}
sockets: {...}           # attachment points exported per frame (optional)
timing: {...}            # timing targets checked by validate and QA (optional)
review: {...}            # art-direction targets, QA warnings (optional)
```

## Views
`view` picks a camera preset; anything the spec sets explicitly wins over it.

| view | camera pitch | directions (characters) | ground shadow | for |
|---|---|---|---|---|
| `topdown` (default) | 38° | 8 | ellipse | RPGs, action games, tactics |
| `side` | 0° (profile) | `[e, w]` | none | platformers, side-scrollers, fighting games |

Everything else (modeling, animation, sockets, timing, review, export) works the same way. A small tilt
(`camera: {pitch: 10}`) gives a side view that shows a little of the top. Keep one view per game.

## Mirrored directions
`mirror: true` renders only the directions that face right or straight up/down (`s, se, e, ne, n`, or `e`
in a side view) and exports the left-facing ones (`sw, w, nw`) as flipped copies of their twins: about
40% less atlas and render time. The engine runtimes flip the sprite and the sockets. Use it only for
symmetric designs: a sword in the right hand switches hands in the mirrored directions, and the light
comes from the other side.

## Units and axes
- The world is in "game metres": a human is 1.6–1.9 tall. The ground is `y = 0`.
- **+Y is up, +Z is the character's front** (direction `s` faces the camera), **+X is the character's
  left** (it shows on the screen's right in direction `s`).
- With `scale: 0.05`, 1 pixel = 0.05 units: 1 px of breathing is about 0.05 of `bob`.
- Directions `s, se, e, ne, n, nw, w, sw` = yaw 0, 45, 90, 135, 180, -135, -90, -45 degrees. The light is
  fixed in the world and the model turns, so shading is coherent across directions.

## Expressions
Any number or vector can be an expression string: `"[0, 0.78 + bob, 0]"`, `"0.045*sin(p)"`.
- Lists are numpy vectors (`[1,0,0] + [0,1,0]` adds).
- Variables: every channel, `p` (phase 0..2π in a cycle), `t` (0..1), `f` (frame), `n` (frame count),
  `yaw` (direction being rendered, degrees) and `dir` (`"s"`, `"se"`...). They work **everywhere**,
  including animation channels, so cheat per direction right in the key, as pixel artists do:
  `rifle_pitch: "-0.08 + -0.2*pulse(yaw, 0, 70)"`, `bob: "0.02*(dir == 'n')"`. The frame count may not
  depend on the direction.
- Functions: `sin cos tan abs min max sqrt clamp lerp/mix unit smoothstep pulse(x,c,w) pos(x)=max(0,x)
  neg(x) roty rotx rotz v(x,y,z) radians floor sign exp noise(x,seed)`, constants `pi tau`, operator `@`.

## materials
```yaml
materials:
  stone: {ramp: stone}                         # palette ramp; index 0 = outline
  wing:  {ramp: wing, two_sided: true}         # thin membranes: lit from both sides
  eye:   {ramp: eye, emissive: true, band: 3, glow: {color: "#ff5a1f", mix: 0.55, radius: 1}}
  mouth: {ramp: mouth, bands: [1, 2], line: false}
```
Fields: `ramp` (name or list of hex colours; default: the material's name), `emissive` (unlit, no outline;
uses `band`), `bands: [lo, hi]` (index range the light uses), `line` (takes part in inner lines),
`line_band` (colour of inner lines, default 1), `outline` (outer outline), `two_sided`, `glow`, `gamma`
(light → band curve, default 1.05).

Ramps come from `palette:`: a file path relative to the spec, a name in the project's palettes folder
(`<specs>/palettes/<name>.yaml` of `spritekiln.toml`), a built-in name (`gothic`), or a list of them (later
ones win). A top-level `ramps:` mapping adds or overrides ramps for this spec alone:
`ramps: {body: ["#1a1020", "#3b2a4a", "#5d4f6c", "#8a7a9a", "#c0b3cc"]}`.

## channels
Animatable values with defaults, scalars or vectors. Everything an animation changes goes through a
channel. `root` (vector) is special: it moves the `root` frame (lunge, jump) and the shadow follows it.

## Mirroring `_L` / `_R`
Write **only the `_L` side (positive x)**. Every bone, IK chain, part, channel and socket whose name has
`_L` gets an automatic `_R` twin (renaming `_L` → `_R` everywhere, expressions included). In the twin, local
vectors have x negated and Euler rotations become `(rx, -ry, -rz)`.
- **`_R` channels use the same convention as `_L`**: positive x = away from the body. A symmetric pose has
  the same values on both sides; the right hand crossing to the left side is a negative x in `hand_R`.
- **Do not use global asymmetric channels (`twist`, `roll`, `head_yaw`) inside expressions of `_L` items**:
  they would be mirrored. Put them on a central bone and make the `_L` bone inherit from it (see `legyaw`,
  `wingbase` in the examples).
- For something on one side only (a sword in the right hand), use a name without `_L`, e.g. `sword` with
  `space: wrist_R`.

## bones
```yaml
bones:
  torso_rot: {parent: root, pos: "[0, 0.78 + bob, 0]", rot: "[lean, twist, roll]"}
  pelvis:    {parent: torso_rot, scale: "[1/sqrt(squash), squash, 1/sqrt(squash)]"}
  head:      {parent: headbase, rot: "[head_pitch, head_yaw, 0]", scale: 1.3}
  sole_L:    {parent: footyaw, at: ankle_L, rot: "[pitch_foot_L, 0.15, 0]"}
```
- `pos` is in the parent's space; `rot` is Euler radians `[x, y, z]` applied as Ry·Rz·Rx (yaw, roll, pitch).
- `scale` is a scalar or a vector (squash and stretch); primitive radii scale with it.
- `inherit_rot: false` / `inherit_scale: false`: only the position follows the parent.
- `at: <frame>`: the origin comes from another frame (e.g. a foot placed at the IK ankle) and the rotation
  from `parent`.

## ik (two bones)
```yaml
ik:
  arm_L: {start: shoulder_L, space: torso_rot, target: hand_L, lengths: [0.36, 0.36],
          pole: [0.5, -0.1, -1.0], pole_space: torso_rot, up: [0, 0, 1], joint: elbow_L, end: wrist_L}
```
Creates the frames `joint` and `end` (local z axis = forearm direction). `target` is a point in `space`
(usually a channel). `pole` is where the elbow or knee points. `up` (optional) sets the end frame's y axis;
use `[0, 0, 1]` for arms hanging down.

## parts (geometry)
```yaml
parts:
  torso:
    material: stone
    space: pelvis          # primitive coordinates are in this frame (default root)
    blend: 0.09            # smooth union between the part's primitives
    line: true             # inner lines where this part overlaps another
    when: "smear_w > 0"    # conditional part
    prims: [...]
    cut: [...]             # subtracted primitives (cut_blend)
```
Points can be `[x, y, z]` (in `space`), `"@frame"` (a frame's origin), `{at: frame, off: [x, y, z]}` or
`{between: ["@a", "@b"], t: 0.45}`.

Primitives (each item is a one-key mapping):

| type | fields |
|---|---|
| `sphere` | `c, r` |
| `ellipsoid` | `c, r: [rx, ry, rz], rot: [x, y, z]` or `align: [p0, p1]` (z axis from p0 to p1) |
| `cone` | `a, b, r: [r1, r2]` (tapered capsule: limbs, horns, claws) |
| `chain` | `pts: [...], r: [...]` (a run of cones: tails, tentacles, curved horns) |
| `box` | `c, half: [hx, hy, hz], rot, round` (blades, armour, props) |
| `cylinder` | `a, b, r, round` |
| `torus` | `c, R, r, rot` (rings, halos, chains) |
| `tri` | `a, b, c, th` |
| `membrane` | `hub, ring: [...], th, scallop: [idx...], scallop_depth, fill_root` (wings, capes, sails) |
| `arc` | `c, r, a0, a1, width, fade, dip, segments`: smear VFX; use `materials: [tail, mid, core]` |

## animations
**Expression cycles** (loops: idle, walk, run, fly):
```yaml
idle:
  frames: 8
  ms: 130                    # or a list per frame, or an expression
  events: {0: step_l}        # go to the JSON for gameplay code
  channels: {bob: "0.045*sin(p) - 0.01", tail: "0.7*sin(p)"}
```
**Pose to pose** (attacks, hits, deaths): one key = one frame; channels a key does not set go back to their
defaults (`carry: true` inherits from the previous key instead).
```yaml
attack:
  loop: false
  keys:
    - {ms: 170, event: windup, set: {...}}          # held anticipation
    - {ms: 55, set: {..., smear_w: 0.11}}           # fast strike with a smear
    - {ms: 120, set: {...}, tween: 1, ease: out}    # adds 1 interpolated frame toward the next key
```
An event on frame *i* fires when frame *i* becomes visible: at the sum of the durations before it.

## sockets (attachment points)
```yaml
sockets:
  muzzle_L: {bone: pistol_L, offset: [0, 0.042, 0.50], when: "gun < 0.5"}   # automatic muzzle_R twin
  hand_L: {bone: wrist_L}
  hit: {bone: hammer, offset: [0, 0, 0.6]}
```
`bone` is any frame (a bone, an IK joint or end, `root`); `offset` is in its space; while `when` is false
the socket is `null` in that frame. The JSON gives `[x, y, depth]` per animation, direction and frame:
pixels from the pivot, and depth (> 0 in front of the body, < 0 behind). In Godot: `get_socket(&"muzzle_R")`.
Put a socket at the centre of the effect the game will spawn (flash, impact), not at the tip of the weapon.

## timing (targets)
```yaml
timing: {shoot_r: {release: 2f, total: 7f}, attack: {hit: 150ms}}   # 60 fps, 1 frame of tolerance
```
`validate` and QA fail when an event (or a clip's total) misses its target. Optional:
`timing: {fps: 30, tolerance: 2, ...}`.

## review (art-direction targets)
```yaml
review: {min_lstar: 20, tint: [0.68, 0.71, 1.02], background: floor.png, materials: {lining: {min_px: 30}}}
```
They become QA warnings. `spritekiln review` measures everything and writes sheets: L* (median/p90) under
the `tint` light, contrast with the floor, pixels per material and direction, bands used, IoU against the
camera-corrected splash, comparison with another asset (`--against`). See [art-direction.md](art-direction.md).
