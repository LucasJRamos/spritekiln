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
brief: {...}             # free text: summary, head, must_keep, simplify, reference (ignored by the renderer)
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

## Bases and kits: `extends`, `remove`, `use`
A spec can start from another one and add kits (reusable parts with params), so that it states only what is its
own:
```yaml
spritekiln: 1
name: knight
extends: humanoid                 # a built-in template, <specs>/templates/<name>.yaml, or a path from this file
remove: [use.sword, parts.coat]   # paths of the base to drop; use.<as> drops all that one of its kits added
use:
  - {kit: helmet, at: head, with: {visor: true}}
  - {kit: shield, at: wrist_L}
  - {kit: sword, as: blade, at: wrist_R, with: {length: 0.5}, materials: {steel: iron}}
materials:
  cloth: {ramp: blood}            # merged into the base's cloth: only its ramp changes
parts:
  belt: {prims: [...]}            # replaces the base belt's prims: a list is replaced, never merged
```
- **`extends`**: the base is merged deeply and the spec's keys win; lists (`prims`, `cut`, `keys`...) are
  replaced whole. The base's `name` and `brief` are not inherited; its relative palette paths still work. A
  base can extend another one.
- **`remove`**: paths of the base to delete (`parts.cape`, `animations.dash`, `materials.fx_core`), or
  `use.<as>`: everything one of the base's kits added. A typo is an error with the closest path.
- **`use`**: a kit adds its parts, bones, IK chains, sockets and channels named `<as>_<name>` (`as` defaults to
  the kit's name; its item named like the kit is just `<as>`): the `sword` kit adds `sword_blade`,
  `sword_grip`..., the bone `sword` and the socket `sword_tip`. `at` is the frame it attaches to (default: the
  kit's). `with` sets its params (`spritekiln kits <name>` lists them with their comments). Its materials and
  ramps are used only where the spec has none of that name: define `steel` to recolour it, or map one with
  `materials: {steel: iron}`. An `as` ending in `_L` is mirrored like any `_L` item. A `use` with the `as` of
  one of the base's replaces it.
- Change what a base or a kit gave like your own item, by giving the keys that differ:
  `parts: {sword_blade: {material: gold}}`.
- `spritekiln spec outline` lists what the base and the kits add and where it comes from; `spritekiln spec show
  <path>` prints those lines from their file; `--resolved`, the merged result. Problems point at the file and
  line that wrote them.
- Part order: the base's parts, then the kits', then the spec's new ones. The order only decides which of two
  parts wins a pixel they share exactly.
- A spec that extends a template follows it: a fix to the template reaches it. Built-in templates and kits
  change only compatibly within a minor version; a visual change comes under a new name (`humanoid2`).

**Kit files** live in the project's `<specs>/kits/<name>.yaml` or ship with SpriteKiln (`spritekiln kits`
lists both; a project kit of the same name wins):
```yaml
spritekiln: 1
kit: club
license: CC0-1.0
summary: a wooden club held in the fist
host: humanoid                    # the base it is shown on by `pose` and `validate`
at: wrist_R                       # its default frame; inside the kit, the frame `at`
host_remove: [use.sword]          # what to hide on the host when the kit is shown
params:
  length: 0.45                    # haft length (comment every param: `spritekiln kits` prints them)
materials: {wood: {ramp: wood}}
ramps: {wood: ["#140c08", "#2f1d13", "#4d3120", "#6d4a2e", "#91683f", "#b88f5c"]}
bones:
  club: {parent: at, pos: [0, 0, 0.035], rot: [0.52, 0, 0]}
parts:
  haft: {material: wood, space: club, prims: [{cylinder: {a: [0, -0.05, 0], b: "[0, length, 0]", r: 0.03}}]}
sockets:
  tip: {bone: club, offset: "[0, length, 0]"}
```
Params are replaced by their values in the kit's expressions (a param alone becomes its value: `r: width`);
booleans work in `when:`. The kit's own channels are renamed with its prefix (`sway` → `cape_sway`), so a
host's animation can drive them. A kit's per-direction cheats (turning a weapon's profile to the camera)
go under one param, `cheat` (0 turns them off), and test the direction with `yaw*sx`, so that they stay right
on a mirrored `_L` use. `spritekiln pose <kit.yaml> --dirs all` and `validate` show a kit on its
host.

## Light
`light` sets the direction (`dir`), the rim light (`rim`, `rim_strength`), `ambient`, `shadows` and `ao`; its
keys win over the light preset of the project's style (below). The render cache keeps the geometry of each frame (parts, depth, normals, shadows, occlusion) and applies the light,
materials and palette afterwards, so changing `ambient`, `rim_strength`, a ramp or a material re-renders a whole
asset in seconds; changing `dir` traces the shadows again. `mode: flat` draws every material in one tone
(`flat_band`, default the upper middle of its `bands`) for games that light the sprite at run time through the
normal map.

## render (the look, from the project's style)
The project's style (`[style]` of `spritekiln.toml`, recorded with `spritekiln style set`, see style.md) decides
how every asset is drawn; a spec repeats none of it. A top-level `render:` block overrides it for one asset (an
exception: write why in `brief:`; `spritekiln style` lists such specs), and a material's own fields win over
both.
```yaml
render: {outline: none, crease_angle: 50, min_run: 2}
```
- `outline`: `selective` (each material outlined in its own darkest tone, the default), `dark` (one colour
  around the whole sprite: `outline_color`, default the darkest first tone of the ramps), `colored` (each
  material's line tone, `line_band`: a softer coloured outline) or `none`. A material's `line_color` sets its
  own outline colour; `outline: false` on a material leaves it out.
- `shading`: `soft` (every tone of the ramp, the default), `flat` (a material's two lightest tones) or `toon`
  (its three lightest, in hard steps at light 0.3 and 0.6). A material that sets `bands` or `thresholds`
  keeps them; a highlight keeps the top tone.
- `lines`: `depth` (inner lines where parts overlap, the default), `depth+normal` (also at folds inside a
  part: `crease: true` on every material that does not say otherwise) or `none` (`line: false` everywhere).
- `highlights`: `false` drops the highlights the finishes add (a material's own `highlight` stays).
- `dither`: `none`, `bayer2` (a checker) or `bayer4` (finer): an ordered pattern mixes two neighbouring tones
  near their border, only inside regions (edges and details of 1-2 px stay solid), anchored on each part so it
  moves with the part. `dither: false` on a material turns it off; `dither: true` turns it on (bayer2).
- `light`: a preset for the light; keys of the spec's `light:` win over it.

  | preset | |
  |---|---|
  | `classic` | the default: from the top left, in front |
  | `top` | from above: short shadows, a bit more ambient |
  | `dramatic` | low from the side: strong contrast, little ambient, strong rim |
  | `soft` | high ambient, low contrast |
  | `flat` | `mode: flat`: one tone per material, for games that light the sprite through the normal map |

- `snap: true`: `snap: [root, torso_rot]` (just `[root]` without that bone) when the spec has no `snap:` list.
- `crease_angle`, `min_run`: the fold lines (materials, below).

Everything here except `light` presets that move the light and `snap` is applied after the render cache:
switching the style re-renders a whole asset in seconds. `spritekiln style preview <spec>` shows each choice
side by side.

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

How a material answers light:
- `finish: matte | soft | metal | glossy`: a preset of the two fields below (a field the material sets wins).
  matte (cloth, stone, fur): no highlight, little rim; soft (skin, leather, wood): a wide highlight; metal
  (armour, blades, coins): a small hard highlight, strong rim; glossy (gems, lacquer, eyes): a tiny one.
- `highlight: {size: 0.95, max_px: 4, min_px: 1, band, color}`: where the surface faces halfway between the
  light and the camera (`size`, a cosine: 0.9 wide, 0.97 small) the pixels take the ramp's top tone (`band`, or
  a `color`), in clusters of at most `max_px` pixels. A material with a highlight keeps its top tone for it: the
  light uses the tones below.
- `rim: 0.6`: the rim light's strength on this material (default `light.rim_strength`).
- `thresholds: [0.35, 0.7]`: the light values where the tone steps up (hard toon shading) instead of `gamma`.
- `flat_band`: the tone used with `light: {mode: flat}`.
- `crease: true`: a line inside one part where its surface folds inwards (sharper than `render.crease_angle`,
  default 50°) or folds over itself (a cape seen from the side): armour plates, carved stone, folded cloth.
  Leave it off on soft organic shapes (it draws noise at blended joints).
- `edge_highlight: true`: one tone up along convex edges that face the light (the bevels of plates and blocks).
- A top-level `render: {crease_angle: 50, min_run: 2}` tunes both: line runs shorter than `min_run` pixels are
  dropped.
- `line_color: "#2a1a10"`: this material's outer outline colour (default: from the style's `outline`).
- `dither: false | true`: leave this material out of the style's dither, or dither it when the style does not.

Ramps come from `palette:`: a file path relative to the spec, a name in the project's palettes folder
(`<specs>/palettes/<name>.yaml` of `spritekiln.toml`), a built-in name (`gothic`), or a list of them (later
ones win). A top-level `ramps:` mapping adds or overrides ramps for this spec alone:
`ramps: {body: ["#1a1020", "#3b2a4a", "#5d4f6c", "#8a7a9a", "#c0b3cc"]}`.

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

## parts (geometry)
```yaml
parts:
  torso:
    material: stone
    space: pelvis          # primitive coordinates are in this frame (default root)
    blend: 0.09            # smooth union between the part's primitives
    line: true             # inner lines where this part overlaps another
    when: "smear_w > 0"    # conditional part
    priority: 3            # its samples weigh 3x in the pixel vote (default 1): thin weapons stay visible
    min_cover: 2           # 2 of its samples fill a pixel even below the camera's coverage (thin details)
    prims: [...]
    cut: [...]             # subtracted primitives (cut_blend)
```
A pixel is filled when enough of its samples (3×3 by default, `camera.coverage` = 4) hit, and the part with
the most samples wins it, so a blade or antenna thinner than about a third of a pixel disappears or breaks into
dots. `priority` and `min_cover` keep it: `min_cover: 1` or `2` for details outside the body's silhouette,
`priority: 2`–`3` for details crossing in front of it. Do not raise them on big parts: they would look fatter
than modelled.
Points can be `[x, y, z]` (in `space`), `"@frame"` (a frame's origin), `{at: frame, off: [x, y, z]}` or
`{between: ["@a", "@b"], t: 0.45}`.

Primitives (each item is a one-key mapping):

| type | fields |
|---|---|
| `sphere` | `c, r` |
| `ellipsoid` | `c, r: [rx, ry, rz], rot: [x, y, z]` or `align: [p0, p1]` (z axis from p0 to p1) |
| `cone` | `a, b, r: [r1, r2]` (tapered capsule: limbs, horns, claws) |
| `chain` | `pts: [...], r: [...]` (a run of cones through every point; for a smooth curve prefer `tube`) |
| `box` | `c, half: [hx, hy, hz], rot, round` (blades, armour, props) |
| `cylinder` | `a, b, r, round` |
| `torus` | `c, R, r, rot` (rings, halos, chains) |
| `tri` | `a, b, c, th` |
| `membrane` | `hub, ring: [...], th, scallop: [idx...], scallop_depth, fill_root` (wings, capes, sails) |
| `arc` | `c, r, a0, a1, width, fade, dip, segments`: smear VFX; use `materials: [tail, mid, core]` |
| `extrude` | `c, rot, align, profile, depth, round`: a 2D profile in the local x-y plane, `depth` thick along local z and centred on `c` (blades, axe heads, shields, plates, buckles); `round` rounds the edges of the front and back faces |
| `revolve` | `c, rot, align, profile, offset, angle: [a0, a1]`: a cross-section turned about local y (helmets, hat crowns, hoods, bottles, bells); `angle` (radians from local +z towards +x) for a partial turn (a collar open at the front) |
| `tube` | `pts: [...], r` or `r: [start, end]`: a smooth round tube (horns, tails, straps, hair locks); see below |
| `plane` | `n, at` or `n, c`: **only under `cut:`**; removes the side `n` points to, from the plane at distance `at` along `n` (normalised first) or through `c` (the hem of a cape, an open front) |

**The local frame** of `ellipsoid`, `box`, `torus`, `extrude`, `revolve`: `align: [p0, p1]` points local z from p0
to p1 (otherwise the part's space), then `rot` turns it further (Euler radians, applied after `align`). So a
profile or a revolve that must run **along** an aligned line needs `rot: [1.5708, 0, 0]`: local y then points
from p0 to p1 (a blade or a pauldron that follows the arm). `rot: [1.5708, 0, 0]` without `align` lays an
`extrude` flat: the profile in the ground plane, its y pointing forward, `depth` vertical (a hat brim, a
platform); a further `rot` z tilts that plate about its front-back line.

**Profiles** (`extrude`, `revolve`), in the primitive's local frame, scaled with the part's space:
- `{circle: r}`; `{rect: [hx, hy]}` (half sizes) with `chamfer: 0.02` (45° corners) or `round: 0.02` (both keep
  the size); `{polygon: [[x, y], ...]}` with `round` (rounds the corners by growing the outline that much);
- `{bezier: [P0, C0, P1, C1, ...]}`: quadratic segments from each P to the next, bending **towards** its C (a
  curve does not pass through C; for a straight segment put C at the midpoint); the last segment goes back
  to P0 (curves, leaves, cloth outlines, hoods).
- A `revolve` profile is the **whole cross-section through the axis**, both sides drawn (x = distance from the
  axis; only the x ≥ 0 half is used, but the outline must be closed), or one side with `offset` for a ring. A
  `revolve` turned about a vertical axis can only make round things; for an asymmetric brim use `extrude`
  plates.
- `validate` warns when a `rect` or `circle` profile is narrower than a pixel.

**Tubes**: the path starts at the first point and ends at the last; every point in between pulls the curve
towards it (it passes through the midpoints between inner points, not through the points). To copy a `chain`
with the same curl, push the inner points outwards. The radius goes linearly from `r` start to end.

**Modifiers** on any single primitive (not `chain`, `membrane`, `plane`), in its local frame: its `c` and
`rot`/`align`, or for a primitive without `c` (cone, cylinder, tube, tri) the centre of its bounds and the
part's space.
- `shell: 0.05` hollows it into a shell that thick, **centred on its surface**: the outside grows by half the
  shell. To keep an outer surface where it was, shrink the radii by half the shell (capes, sleeves, open
  helmets, coat skirts; open it with cuts). A 1 px shell is about 0.05 at `scale: 0.05`.
- `elongate: [x, y, z]` stretches its middle by those half lengths and keeps the ends (long plates, belts).
- `twist: 2` turns it about the local y axis through that centre, radians per unit along y: a round tube only
  twists if its centre line winds around that axis (ropes, a ram's horn made of a box or an ellipsoid).
- `bend: 1` curves it in the local x-y plane, radians per unit along x: both ends turn towards local +y for a
  positive value (towards -y for a negative one), symmetrically about the centre. On an `extrude` that plane
  is the profile's: it curves the outline (a scimitar), it cannot curl a flat plate (use a `revolve` or a
  `shell` for a curved plate).
- Twisted and bent parts take shorter ray-marching steps.

**Cuts**: any primitive can be a cutter, `extrude` and `revolve` included: an extruded triangle opens an A-line
front in a coat shell, where a `plane` would leave a sliver of the inner wall or open too wide at the hem.
`cut_blend` (default `0.01`, a smooth edge) softens the cut edges.

**Joins**: `blend: 0.05` is the smooth union (as before); `blend: {mode: chamfer|round|stairs, k: 0.04, n: 3}`
joins the primitives with a 45° bevel, a fillet or `n` steps. On round masses (ellipsoids) a small chamfer is
nearly invisible at 64-96 px and a large one fills concave corners like a smooth blend: it pays on flat-faced
primitives (boxes, extrusions). `cut_blend` takes the same, or `{mode: groove, depth: 0.02, width: 0.01}`: a
channel engraved where each cutter's surface crosses the part, which keeps its volume (a thin `box` or a
`plane` cutter draws a groove line across armour).

Inner lines are drawn only where two **parts** meet (and at folds inside a part whose material has `crease:
true`), so a step inside one part (a pauldron's lames) reads only through its shading: make it at least 1-1.5
px. `validate` warns when a shell, an extrusion, a tube or a
profile is thinner than one pixel at the spec's `camera.scale` (it can vanish or flicker), in the numbers the
spec uses, and when a polygon's edges cross. `validate` also counts the primitives and cuts the rest pose
builds.

**Paint**: `paint:` colours regions of a part's surface with another material, without new geometry (crosses,
bands, trims, rivets, stains). It cannot change the silhouette: a trim that sticks out still needs a part.
```yaml
  cape:
    material: cape_linen
    space: capebase
    prims: [...]
    paint:                          # later layers win
      - material: cross             # a volume: the surface inside these primitives
        prims:
          - box: {c: [0, -0.55, -0.4], half: [0.075, 0.4, 0.4]}
          - box: {c: [0, -0.38, -0.4], half: [0.24, 0.07, 0.4]}
      - material: gold
        stripes: {axis: y, at: [-1.05], width: 0.035}    # a band around the hem
        edge: true                  # a 1 px line where this paint meets the rest of the part
```
Each layer is a `material` plus one of these, all in the part's `space` (they move with the bone and stay in
place from frame to frame; an `_R` twin gets them mirrored):

| pattern | fields |
|---|---|
| `prims` | any primitives and modifiers: the part's surface inside them is painted, so make them thick enough to enclose it (a box through a cape shell paints both faces) |
| `stripes` | `axis`, `width` and `period` (repeating, `offset` shifts them) or `at: [...]` (positions along the axis): bands across the axis, e.g. around an arm or a column at some heights |
| `rings` | `axis`, `width`, `period` or `at`: concentric bands by distance from the axis (a target on a shield, the end of a log) |
| `grid` | `axes: [x, y]`, `spacing: [sx, sy]`, `r`, `offset`: dots on a lattice (rivets, studs) |
| `spots` | `scale`, `density` (about the share of the surface painted), `seed`: noise blotches (moss, stains, freckles) |
| `checker` | `size` |

A painted pixel keeps the part's light (normal, shadow, occlusion) and takes the paint material's ramp, outline
colour, emissive flag and pixel count in `review`. `edge: true` lines use the paint material's `line_band`.
`validate` warns when a stripe, ring or dot is narrower than one pixel.

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
