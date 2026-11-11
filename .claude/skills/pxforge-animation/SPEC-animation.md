# Spec reference for animation

The sections of the spec reference ([SPEC.md](SPEC.md)) an animator works with: expressions, channels, snapping, mirroring, bones, IK, animations, sockets and timing targets. Geometry, materials, kits and paint are in SPEC.md: open it when a clip needs a new part (a smear arc) or a part to react.

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
- `sx` is -1 inside an automatic `_R` twin (its bones, IK, parts and sockets) and +1 elsewhere. A cheat in an
  `_L` item written with `yaw*sx` (`pulse(yaw*sx, 90, 50)`) happens in the mirrored direction for its twin;
  with a bare `yaw`, both sides cheat in the same direction.
- Functions: `sin cos tan abs min max sqrt clamp lerp/mix unit smoothstep pulse(x,c,w) pos(x)=max(0,x)
  neg(x) roty rotx rotz v(x,y,z) radians floor sign exp noise(x,seed)`, constants `pi tau`, operator `@`.

## channels
Animatable values with defaults, scalars or vectors. Everything an animation changes goes through a
channel. `root` (vector) is special: it moves the `root` frame (lunge, jump) and the shadow follows it.

## snap
`snap: [root, torso_rot]` (top level; `root` and bone names) rounds the on-screen movement of those frames
from the rest pose to whole pixels, frame by frame; their children follow. A bob of a fraction of a pixel then
becomes a clean 1 px step instead of shading that flickers. Arms, wings and capes that move on their own are
not rounded. QA reports `boil` (below); check it before and after: on the showcase idles snapping halves it,
on a gargoyle whose wings flap it did not help.

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
