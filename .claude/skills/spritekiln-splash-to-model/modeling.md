# Modeling for legible pixel art

The renderer can draw anything; what survives at 64 px (top-down 3/4, pitch 38°) is a short list.

## Legibility rules
- **Big head** (1.2–1.4× real proportions) and a silhouette with **2–3 striking shapes** (horns, wings, a
  weapon, a cape, a hat). Details smaller than about 2 px (0.1 world units at `scale: 0.05`) vanish or turn
  into noise.
- **Thin parts:** a radius of at least ~0.025 at `scale: 0.05` (claws, blades); thinner breaks into dots.
  When a detail must stay thinner (a staff, a rapier, antennae), give its part `min_cover: 1` or `2` and,
  when it crosses in front of the body, `priority: 2`–`3` ([spec.md](SPEC.md)).
- **Materials read through their finish:** give armour and blades `finish: metal`, skin and leather `soft`,
  cloth and stone `matte`, gems and eyes `glossy` (SPEC.md). A ramp for a metal needs 5–6 tones: the top one
  becomes its highlight.
- **Crisp forms inside a part:** `crease: true` on armour, plates and stone draws the inward folds inside one
  part, and `edge_highlight: true` lights its convex edges (SPEC.md); inner lines otherwise appear only between
  two parts.
- **Colours:** one ramp per material, 4–6 tones; few materials (3–6). Emissives (eyes, magic) are the
  accent. Value contrast between neighbouring materials matters more than hue.
- **Perspective:** things that stick out backwards or away rise on the screen. Check the diagonals: a thin
  piece seen edge-on becomes a stick; change its angle, or cheat per direction with `yaw`/`dir` in an
  expression.
- **Margins:** keep ≥ 2 px free around every frame (QA warns). If a frame clips, move `camera.center`,
  raise `size`, or reduce that gesture; change `camera.scale` only for the whole game.
- **Consistency:** never change one asset's camera `pitch`, `light` or density (`camera.scale`); the
  whole game shares them. A bigger creature gets a bigger `size`.

## Which shape for what
Pixel artists draw plates, blades and brims with crisp edges. Rounded primitives blended together make
"inflated" forms, so pick the primitive that already has the shape ([spec.md](SPEC.md) has the fields):

| what | use |
|---|---|
| limbs, torso, round masses | `ellipsoid`, `cone`, `sphere` with `blend` |
| a head, a face, hair | the `head` and hair kits, or the recipe in "Heads, faces and hair" below (never one blended ball) |
| a blade, an axe head, a shield, a plate, a buckle, a leaf | `extrude` of a `polygon`, `rect` (`chamfer`) or `bezier` profile |
| a helmet, a round hat crown, a bottle, a bell, a mantle | `revolve` of the cross-section |
| a hood | `revolve` of a dome that pinches into a soft tip, the face cut open by a tilted `plane` (an ellipsoid shell reads as a ball) |
| a pauldron | `revolve` along the arm (`align` + `rot: [1.5708, 0, 0]`), or a dome over the shoulder |
| a cape, a sleeve, a coat skirt | a `cone` or `revolve` with `shell`, cut by `plane`s (top, hem) and an extruded triangle (an A-line front) |
| an asymmetric or cocked brim (a tricorne) | flat `extrude` plates (`rot: [1.5708, 0, 0]`, then tilted with `rot` z) |
| a horn, a tail, a tentacle, a strap, a hair lock | `tube` (tapered with `r: [start, end]`; push the inner points outwards for a tight curl) |
| a curved blade, a scimitar | `extrude` with `bend` (it curves the outline, not the plate) |
| armour joints, a stepped pedestal | `blend: {mode: chamfer}` or `{mode: stairs}` on flat-faced primitives |
| a line engraved on armour | `cut` with `cut_blend: {mode: groove}` |
| a cross, a band, a flat trim, rivets, stains | `paint:` on the part that carries it (below) |

What the showcase port taught:
- **Change a part only if it reads better** at the sprite's size in all 8 directions; at 64-96 px lapels,
  pistol grips and belt buckles already have their shape, and a 1 px detail gains nothing from a new primitive.
- **A tip stays on the silhouette at the 38° pitch** only if its sides fall steeper than about 38° from
  horizontal (an apex under about 104°): a gothic-arch hood tip vanishes. Check the back views.
- **Shells are centred on the surface** (SPEC.md): shrink the radii by half the shell to keep an outer surface
  (a cross painted on a cloak sits on it).
- A hood or hat must cover the corners of a helm under it, or they poke through in the back views.

Recipes, checked on the humanoid template (`spritekiln new`): its frames `wrist_R`, `wrist_L`, `head`,
`shoulder_L` and `pelvis`, `scale: 0.048`. Adapt the sizes; keep the idea.
```yaml
sword:         # the blade along the hand frame's y, tilted like the template's sword
  material: steel
  space: wrist_R
  prims:
    - extrude: {c: [0, 0.26, 0.19], rot: [0.52, 0, 0], depth: 0.05, round: 0.012,
                profile: {polygon: [[-0.03, -0.24], [0.03, -0.24], [0.03, 0.17], [0, 0.26], [-0.03, 0.17]]}}
    - extrude: {c: [0, 0.048, 0.068], rot: [0.52, 0, 0], depth: 0.05, profile: {rect: [0.075, 0.018], chamfer: 0.012}}
axe:           # a haft and a curved head turned to face sideways
  material: steel
  space: wrist_R
  prims:
    - cylinder: {a: [0, -0.05, 0.05], b: [0, 0.5, 0.33], r: 0.022}
    - extrude: {c: [0, 0.44, 0.3], rot: [0.52, 1.5708, 0], depth: 0.05, round: 0.012,
                profile: {bezier: [[0, -0.06], [0.08, -0.16], [0.17, -0.12], [0.21, 0], [0.17, 0.12], [0.08, 0.16],
                                   [0, 0.06], [-0.03, 0]]}}
shield:        # a heater shield on the outside of the left forearm
  material: steel
  space: wrist_L
  prims:
    - extrude: {c: [0.07, 0, -0.08], rot: [0, 1.5708, 0], depth: 0.05, round: 0.015,
                profile: {polygon: [[-0.2, 0.22], [0.2, 0.22], [0.2, -0.04], [0, -0.28], [-0.2, -0.04]], round: 0.02}}
hat:           # a brim and a crown in one cross-section through the axis
  material: leather
  space: head
  prims:
    - revolve: {c: [0, 0.2, 0], profile: {polygon: [[-0.25, 0], [0.25, 0], [0.25, 0.02], [0.16, 0.035], [0.14, 0.24],
                                                     [-0.14, 0.24], [-0.16, 0.035], [-0.25, 0.02]], round: 0.006}}
hood:          # a cowl: a dome pinched into a soft tip, leaning back, open at the face
  material: cloth
  space: head
  prims:
    - revolve: {c: [0, 0.02, -0.02], rot: [-0.1, 0, 0],
                profile: {bezier: [[0.21, -0.12], [0.225, 0.12], [0.12, 0.3], [0.04, 0.37], [0, 0.43], [-0.04, 0.37],
                                   [-0.12, 0.3], [-0.225, 0.12], [-0.21, -0.12], [0, -0.12]]}}
  cut:
    - plane: {n: [0, -0.25, 1], at: 0.06}
cape:          # a cone shell from the shoulders, open at the front, flat top and hem
  material: cloth
  space: pelvis
  prims:
    - cone: {a: [0, 0.6, -0.04], b: [0, -0.35, -0.14], r: [0.21, 0.34], shell: 0.05}
  cut:
    - plane: {n: [0, 0, 1], at: 0.0}
    - plane: {n: [0, 1, 0], at: 0.6}
    - plane: {n: [0, -1, 0], at: 0.35}
pauldron_L:    # a flat dome over the shoulder, tilted outwards (mirrored to the right one)
  material: steel
  space: shoulder_L
  prims:
    - revolve: {c: [0.02, 0.03, 0], rot: [0, 0, -0.5], profile: {bezier: [[-0.15, 0], [0, 0.12], [0.15, 0], [0, 0.07]]}}
horn_L:        # tapered and curling back
  material: leather
  space: head
  prims:
    - tube: {pts: [[0.09, 0.22, 0], [0.2, 0.3, -0.02], [0.24, 0.42, -0.1], [0.18, 0.5, -0.2]], r: [0.04, 0.01]}
```
Keep every piece at least a pixel thick (`validate` warns), look at a full `pose --dirs all`, and prefer one
shaped primitive to a stack of blended ellipsoids plus cuts.

## Kits
Weapons, shields, headwear, capes, belts, heads and hair come from kits before you model your own: each is
built with the shapes above and checked in 8 directions on the humanoid template ([spec.md](SPEC.md), "Bases
and kits").
`spritekiln kits <name>` prints a kit's params with their comments.

| kit | at | params worth knowing | sockets |
|---|---|---|---|
| `sword` | `wrist_R` | `length`, `width`, `thick`, `guard`, `tilt`, `roll` (1.5708 in a side view), `pitch` (a channel) | `tip`, `hit` |
| `axe` | `wrist_R` | `length`, `reach` (the bit), `head`, `double` | `hit` |
| `mace` | `wrist_R` | `length` (to the head's middle), `head` (radius to the spike tips), `spike` (one on top) | `hit` |
| `hammer` | `wrist_R` | `length`, `head`, `width` (the face), `beak` (a pick instead of the back face) | `hit` |
| `spear` | `wrist_R` | `length` (fist to point), `butt`, `head`, `width`, `splay` | `tip` |
| `staff` | `wrist_R` | `length` (fist to top), `butt`, `thick`, `orb` (an emissive `magic` orb) | `orb` |
| `bow` | `wrist_L` | `length` (tip to tip), `depth` (the curve), `thick` | `nock`, `rest` |
| `pistol` | `wrist_R` | `length` (fist to muzzle), `thick`, `flare` (a bell muzzle) | `muzzle` |
| `rifle` | `wrist_R` | `length` (fist to muzzle), `stock`, `thick` | `muzzle` |
| `shield` | `wrist_L` | `shape` (0 heater, 1 round, 2 kite), `width`, `height`, `boss`, `turn`, `side` (-1 on `wrist_R`) | `block` |
| `helmet` | `head` | `size`, `visor`, `nasal`, `crest` (0: none), `trim` | `top` |
| `hood` | `head` | `size`, `depth` (how deep the cowl), `tip`, `tilt`, `mantle`; its own `hood` material | `top` |
| `hat` | `head` | `size`, `brim`, `crown`, `droop`, `tilt` (- shows the eyes) | `top` |
| `head` | `head` | `jaw` (0 soft .. 1 square), `chin` (0 round .. 1 pointed), `width`, `nose` (0: none), `ears` (1 round, 2 pointed); the templates use it | |
| `hair` | `head` | `fringe` (0 bare forehead .. 1 bangs), `part` (-1..1), `locks` (0 .. 2 to the collarbone), `length` (0 nape .. 2 down the back), `volume`, `size`; the templates use it | |
| `ponytail` | `head` | `height` (0 nape .. 1 crown), `length`, `volume`, `band`, `cheat`; channels `swing`, `lift`, `sway` for the animator (`ponytail_swing`...); with the hair kit's `length: 0` | |
| `bun` | `head` | `height` (0 nape .. 1 top), `size`, `double` (two buns at the sides), `wrap` | |
| `cape` | `pelvis` | `length`, `width`, `flare`, `drape`, `collar`, `clasp`; channel `cape_sway` | |
| `belt` | `pelvis` | `radius`, `height`, `y`, `tilt`, `buckle` (remove the template's `parts.belt`) | |
| `pouch` | `pelvis` | `width`, `angle` (around the waist), `flap`, `stud`; a pair: `as: pouch_L, with: {angle: 1.15}` | |

Widths are full widths, `thick` is a shaft's, barrel's or limb's diameter, `size` scales a whole piece, `tilt`
leans it (negative: front up), and `cheat` is the strength of a kit's per-direction cheats (0: off).

- Hand weapons hang from the fist like the template's sword (`at: wrist_R`, `tilt` about the hand's x): swap
  one with `remove: [use.sword]` and a `use` of another, or `use: [{kit: axe, as: sword}]` to replace the
  base's sword in place. A right-hand kit in the left hand (`at: wrist_L`) negates its `cheat` (and `splay`
  or `roll` where it has them: each kit's comments say); a shield on the right arm takes `side: -1`.
- A kit's colours come from its materials by name (`steel`, `wood`, `leather`, `cloth`, `gold`, and its own
  such as `cape`, `plume`, `magic`): the spec's material of that name wins, so define `cape: {ramp: ...}` or
  map one: `materials: {cloth: robe}`.
- Fit a kit with its params first (`size` for a bigger head, `radius` for a wider waist), then, if a part
  still needs it, change that part in the spec like any inherited item.
- A project's own kits go in `<specs>/kits/`; write one when the same piece appears on two assets.

## Heads, faces and hair
With stylized proportions a character's head is 8–14 px tall, about a fifth of the sprite: it is one of the
big masses, not a detail. Rounded primitives blended together read as a ball at that size, and a small
feature on a face swells into a lump. What reads:
- **Decide it first, in `brief.head`:** the hair (style, length, fringe, locks, ponytail or bun), the jaw and
  chin, and how much face the project's style shows (`spritekiln style`, `face`). `validate` warns about a
  character over a template until it is written.
- **Start from the kits.** The templates `use` the `head` kit (`jaw`, `chin`, `width`, `nose`, `ears`) and the
  `hair` kit (`fringe`, `part`, `locks`, `length`, `volume`); `ponytail` and `bun` attach to the head for
  those styles. Fit the params first: `use: [{kit: hair, as: hair, with: {fringe: 0.4, locks: 2, length:
  1}}]` replaces the template's hair in place (a `use` with the same `as`), and `{kit: head, as: head, with:
  {jaw: 0.2, chin: 0.8}}` its head. To write a hair of your own, add `remove: [use.hair]` and your parts: a
  spec that only replaces `parts.hair.prims` keeps the kit's fringe and locks (`validate` says so). A
  ponytail goes with the hair kit's `length: 0`; under a hood or a hat, tie it or the bun low (their kits'
  headers say how low). The ponytail's channels (`ponytail_swing`, `_lift`, `_sway`) are the animator's.
- **Break the circle.** In every direction at least two things change the outline of the head: a fringe over
  the brow, locks at the temples, a chin, a ponytail or a bun, a hat or a hood.
- **Faces follow the style's `face`.** `minimal`: eyes only, no nose, no mouth (anime and most pixel art).
  `simple`: also a 1 px hint of a brow or a nose (`nose` param), only on heads of 14 px or more. `detailed`:
  nose, brows, mouth, on heads of 20 px or more. The side view is no exception: a profile reads through the
  slope from brow to chin, not through a nose.
- **No feature smaller than its part's `blend`.** A sphere of r 0.025 in a part with `blend: 0.05` swells
  into a soft lump, and the outline adds a pixel around it: a 1.5 px nose on a 9 px face becomes 2–3 px, a
  big nose. Give a small feature its own part with a small or no blend, paint it, or leave it out.
- **Hair in several parts.** Inner lines appear only between parts (or with `crease`), so one blended mass
  of hair reads as a helmet or a sausage. Separate parts for the crown, the fringe, the locks and the strands
  of a ponytail draw the lines that read as hair. Tubes (`r: [root, tip]`) make locks and strands; extrudes
  make flat, sharp fringes.
- **Eyes show.** An eye sunk in the skin disappears: let it sit on the face's surface, at least 1 px in
  every direction where the face shows, with the template's dark `ink` or the project's eye colour.
- **Colour.** The hair kits' material `hair` takes the palette's `hair` ramp (a fallback brown otherwise) and
  no `bands`, so the style's shading applies.
- **Judge it up close.** `pose --focus head --dirs all` shows the head, hair and headwear at 12×; on a 2–4×
  sheet a face is a few pixels and no number (IoU, pixels per material) sees it. Never raise a hair
  `min_px` target to get "more hair": it rewards mass, not locks.

## Paint before geometry
A colour on a surface is `paint:` on that part ([spec.md](SPEC.md)), not a new part: a cross on a tabard, a gold
band, a belt drawn on a coat, rivets, moss. A painted region costs nothing to ray-march, cannot poke through the
surface when it moves, gets no stray inner line from a depth offset and does not lose the pixel vote like a
thin overlay. On the Templar, its three crosses as paint (box volumes through the cloth) replaced 3 parts
and 11 cuts with the same picture, and frames trace 12 % faster (numba) to 26 % (numpy).

Detail still needs geometry when it changes the silhouette or casts a shadow: a buckle or a trim that sticks
out, a belt that rides over folds, a raised rim. Paint follows the part's surface only: it cannot be wider than
the part, and a volume must enclose the surface it paints (a box through a cape shell paints its inside too).

## Side view (`view: side`)
- The silhouette is the **profile**: what reads is the outline seen from the side (the slope from brow to
  chin, the fringe and a ponytail, a hat brim, weapon length, cape, tail). Thickness along the line of sight
  (z) does not show; extend shapes along x and y instead. A face in profile is a line and a chin, not a nose
  (see "Heads, faces and hair").
- Only `e` and `w` are rendered, but the model is still 3D: both profiles must work, and the far arm and
  leg sit behind the body (darker, partly hidden). Check `pose` in both directions.
- No ground shadow by default (the ground is edge-on); the game usually draws its own.

## Procedure
1. Start from a base: `spritekiln new <name> --extends` for a humanoid (it inherits the template's skeleton,
   body and animations), or the closest existing spec. Fill `brief:` first (see
   [splash-to-model.md](SKILL.md)), `head` included. Weapons, shields, headwear, capes, belts,
   heads and hair come from kits ("Kits" above) before you model your own.
2. **Big masses first**: world scale (total height 1.6–2.0 for a human), pelvis height, IK lengths, then
   torso, hips and legs as ellipsoids and cones; the head's size through the `head` bone's `scale`.
3. **The head and the hair**, as `brief.head` says ("Heads, faces and hair"): fit the kits' params or model
   them, then `pose --focus head --dirs all` and look.
4. Add the striking shapes one at a time with the primitive that has their form (see "Which shape for
   what": `extrude` blades and plates, `revolve` helmets and hats, `tube` horns and tails, `shell` capes and
   hoods, `membrane` wings). After each: `validate`, `pose --dirs all` (`--draft` while shaping), look.
5. Check **all 8 directions**, not only the reference's: the back and the profiles must make sense. Invent
   what the reference does not show, coherently, and write the decision in `brief`.
6. Materials and palette last-but-not-least: 3–6 materials plus one emissive; tune ramps with
   `spritekiln palette ramp "#hex" --steps 5`.

## Rules for a modeler (human or AI)
- Run `spritekiln style` first and model in the project's style: outline, shading, proportions, palette
  and colours ([style.md](style.md)). If no style is recorded, stop and report that the user has to answer
  the style questions first.
- Work only in the asked asset's spec. Iterate in small steps: edit → `validate` → `pose --dirs all` →
  **look at the PNG** → fix. Never call a model done without having seen the 8 directions.
- With a splash art: `ref prep` once, `ref compare` after every proportion change (targets in
  [splash-to-model.md](SKILL.md)).
- Keep the skeleton, channels and names the animations use. If you rename something, update the
  animations too and `validate`.
- Do not change `camera.pitch`, `camera.scale`, `light`, shared palettes or the project's style unless
  asked; an exception for this asset goes in its `brief:`.
- Do not render every animation while modeling; at most `render --anims idle --dirs s,e,n,se`.
- Report: what changed (parts, materials), IoU and hints left, image paths for review, and the design
  decisions taken where the reference shows nothing.
