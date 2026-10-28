# 13. Shape operators

**Status:** done (stage 2) · **Track:** forms · **Stage:** 2 (release 0.3) · **Depends on:** 12 (the compiled scene
comes first, so each new primitive is written once)

## Problem
Every form is built from rounded primitives (`sphere`, `ellipsoid`, `cone`, `chain`, `box`, `cylinder`,
`torus`, `tri`, `membrane`, `arc`) joined by smooth union, and shaped with cuts (`spritekiln/rig.py`,
`spritekiln/sdf.py`). This is the main limit on quality today.

**Forms look "inflated".** In the showcase:
- the templar's armour is a stack of rounded lumps;
- its hood is an egg;
- its tabard is a flat slab;
- the huntress's hat and coat read as one blob.

The splash arts have crisp plates, flat blades, brims and folds.

**Flat, sharp, thin and profiled shapes take workarounds:**
- the templar's `cape` is a thin open shell made as a cone minus a second cone, three boxes used as cutting
  planes and three spheres (7 cuts);
- its `cross_back` is a cone shell with 11 boxes cut away ([09](09-surface-paint.md) removes that one).

The workarounds cost render time (every cut is evaluated near the part), spec lines, and the AI's attention.

**Shapes pixel artists draw with crisp edges have no direct primitive:** blades, axe heads, shields, plates,
pauldrons, hat brims, hoods, capes, horns, hair locks, straps.

## Goal
Each common shape of characters and props takes **one primitive or one modifier**, that an AI writes from a
short description. Measured on the showcase:
- forms closer to the splash: `spritekiln ref compare` silhouette IoU goes up in `s` and `se`;
- fewer groups and cuts;
- before/after sheets approved by the maintainer.

## Proposal
### New primitives
| prim | fields | for |
|---|---|---|
| `extrude` | `profile` (2D shape), `depth`, `round`, `c`, `rot` or `align` | blades, axe heads, plates, shields, leaves, ears, buckles, flat straps |
| `revolve` | `profile` (2D shape in the r ≥ 0, y half-plane), `c`, `rot` or `align`, `angle: [a0, a1]` | helmets, hat crowns and brims, bottles, bells; partial: pauldrons, a hood's opening |
| `tube` | `pts` (Bézier control points), `r: [r0, r1]` | horns, tails, tentacles, straps, hair locks (a smooth curve, where `chain` shows its joints) |
| `plane` | `n`, `at` | a half-space (the side `n` points to, beyond `at`); as a cut it replaces the large boxes used as planes |

Profiles are 2D shapes:
- `polygon: [[x, y], ...]`, with `round`;
- `bezier`: a closed path of quadratic segments;
- `rect`, with `chamfer` or `round`;
- `circle`, `arc`, `moon`, `vesica`.

They lie in the primitive's local x-y plane. `extrude` pushes them along local z; `revolve` turns them about
local y. The formulas are Inigo Quilez's 2D distance functions, re-implemented: his site states no licence.

### Modifiers
A modifier goes on a primitive, or on a whole part.

| modifier | fields | effect |
|---|---|---|
| `shell` | thickness | hollow surface, centred on the original one: capes, hoods, sleeves, open helmets |
| `elongate` | `[x, y, z]` | stretches the middle of a shape and keeps its ends: long plates, belts |
| `round` | r | rounds every edge of any shape |
| `bend` | `k`, `axis` | curves a shape: a curved blade, a tail, the fall of a cape |
| `twist` | `k` | twisted horns, ropes |

### Blends inside a part
`blend: 0.05` stays the smooth union. `blend: {mode: smooth|chamfer|groove|stairs|round, k: 0.05, n: 3}` adds
hg_sdf's joints:
- chamfered armour joints;
- a groove between two plates;
- stepped edges.

These are re-implemented from the formulas and credited.

### Example: the templar's cape
```yaml
cape:                              # today: 1 cone and 7 cuts (inner cone, 3 boxes, 3 spheres)
  material: cape_linen
  space: capebase
  prims:
    - cone: {a: [0, 0, 0], b: [0, -1.12, -0.06], r: [0.31, 0.39], shell: 0.045}
  cut:
    - plane: {n: [0, 1, 0], at: 0.0}       # no dome on top
    - plane: {n: [0, 0, 1], at: -0.06}     # open at the front
    - plane: {n: [0, -1, 0], at: 1.12}     # hem
    - sphere: {c: [0.20, -1.13, -0.36], r: 0.07}     # torn notches, as today
    - sphere: {c: [-0.17, -1.13, -0.37], r: 0.065}
    - sphere: {c: [0.31, -1.13, -0.23], r: 0.06}
```

### Example: a sword blade, a brimmed hat
```yaml
blade:
  material: steel
  space: wrist_R
  prims:
    - extrude: {profile: {polygon: [[-0.03, 0], [0.03, 0], [0.03, 0.78], [0, 0.88], [-0.03, 0.78]]},
                depth: 0.012, round: 0.004, c: [0, 0, 0.05], rot: [1.571, 0, 0]}
hat:
  material: felt
  space: head
  prims:
    - revolve: {profile: {polygon: [[0, 0.22], [0.13, 0.2], [0.15, 0.05], [0.30, 0.03], [0.30, 0.0], [0, 0.0]]},
                round: 0.01, c: [0, 0.12, 0]}
```
(values are illustrative)

### Exactness and cost
- **Exact distances:** `extrude`, `revolve`, `plane`, `shell`, `elongate` and `round` give exact distances
  when their profile is exact. Ray marching is unchanged.
- **Bounds only:** `bend`, `twist` and tapered `tube`s give bounds. Their group gets a Lipschitz factor and
  its steps are scaled down by it (today every step is `0.85 × d`), and its bound is enlarged.
- **Bounds of new primitives** are computed analytically from the profile's box and the depth or radius.
  They feed the bounds of [02](02-tight-bounds-and-exact-soft-shading.md) and the culling of
  [12](12-compiled-scene-and-fast-backend.md).
- **No noise displacement**: see the README. Noise is a paint pattern ([09](09-surface-paint.md)).

### Mirroring
`_L` primitives are mirrored as today, by negating x in their part space: their local frame mirrors with
`rot (rx, -ry, -rz)`. Profiles live in that local frame, so they follow. Each new primitive gets a mirror test.

### Help for the AI
- **`validate` warns on likely mistakes:**
  - a profile that is not closed or crosses itself;
  - a `shell`, `depth` or radius thinner than 1 px at the spec's `camera.scale` (`th / camera.scale < 1`),
    which would vanish or flicker ([10](10-thin-parts-and-stability.md));
  - a `bend` strong enough to fold the shape onto itself.
- **`docs/agent/modeling.md`** gets a "which shape for what" table and eight short recipes: blade, axe head,
  shield, brimmed hat, hood, cape, pauldron, horn.
- **The templates** (`specs/templates/`) use the new shapes where they read better: hood, cape, belt.

## Plan
1. A 2D distance library: polygon, quadratic Bézier, rect with chamfer, circle, arc, moon, vesica.
2. `extrude`, `revolve`, `plane`, `shell`, `elongate`, `round`; then `tube`; then `bend` and `twist` with
   the step factor.
3. Blend modes.
4. Schema (`spritekiln/data/spec.schema.json`), errors with `file:line:column`, `validate` warnings.
5. Docs, recipes, templates; regenerate the adapters.
6. Port the showcase on a branch, with before/after sheets, group and cut counts, frame time, `ref compare`
   IoU, and the art director's review:
   - templar: cape, hood, pauldrons, hammer;
   - huntress: hat, coat;
   - gargoyle: wings, horns.

## Validation
- **Distances:** each primitive's distance is checked against a brute-force reference on random points.
  Exact ones are within 1e-6; bounds never overestimate.
- **Mirroring and schema:** tests for each new primitive.
- **Showcase:** IoU per direction, part and cut counts, frame time, and approved sheets.

## Risks and open questions
- **More vocabulary for the AI to learn.** The docs must teach by example, and `validate` must catch the
  common mistakes. Watch how often the AI picks the wrong primitive in the reference task of
  [15](15-agent-context-budget.md).
- **Thin plates and shells under 1 px vanish.** The `validate` warning and `priority`/`min_cover`
  ([10](10-thin-parts-and-stability.md)) handle them.
- **`align` for `extrude`:** should it set the profile's y axis (along the blade) instead of the extrusion
  axis? Decide on the first recipes.
- **Blends between parts of different materials** (a smooth joint between helmet and hood) are out of scope:
  groups are combined with a hard minimum, and each pixel has one part.

## Outcome (2026-10-27): done, showcase port pending
- Primitives `extrude`, `revolve` (with `offset` and `angle`), `tube`, `plane`; profiles `circle`, `rect`
  (`chamfer`, `round`), `polygon` (`round`), `bezier`; modifiers `shell`, `elongate`, `twist`, `bend`; joins
  `chamfer`, `round`, `stairs` and the `groove` cut. In numpy (sdf.py, the reference) and in the numba kernel,
  checked against each other and against known shapes (an extruded rectangle is a box, a revolved rectangle a
  cylinder, a revolved circle a torus, a straight tube a capsule, an elongated sphere a capsule: equal to
  1e-15), with distance gradients of length 1 for the exact ones.
- The generic `round` modifier was dropped: `box`, `cylinder`, `extrude` and the profiles have their own
  `round`, and every other primitive is already round. `moon` and `vesica` profiles were not added: a `bezier`
  profile draws them. A `revolve` profile is the whole cross-section through the axis (IQ's convention).
- Mirroring: `_R` twins are exact mirror images (tested on an asymmetric bent blade, a chamfered guard, a tube).
- `validate` warns about pieces under a pixel and crossing polygons; planes outside `cut:`, odd Bezier point
  counts, unknown join modes and modifiers on a `chain` or `membrane` are errors.
- Docs: the spec reference, a "which shape for what" table and eight recipes (sword, axe, shield, hat, hood,
  cape, pauldron, horn) checked on the humanoid template. Golden fixture `tests/fixtures/shapes`.
- Showcase port (branch `showcase/forms-port`, commit 83ae706, not merged: Hunt Tower uses these specs),
  modeled by character-modeler agents from the new docs and kept only where a part reads better:
  - Templar: cape and lining as revolve shells flaring at the hem, a hood with a soft tip, helm, pauldrons
    along the arm, tabard panels, capelet, chamfered hammer head. IoU s 0.701 -> 0.707, se 0.592 -> 0.605;
    cuts 25 -> 23.
  - Huntress: a tricorne (revolved crown, extruded brim plates), collar ring, coat skirt and lining shells with
    an extruded A-line cutter. IoU s 0.492 -> 0.500, se 0.479 -> 0.497; cuts 12 -> 9.
  - gargoyle: horns and tail as tapered tubes, a barbed spade; primitives 77 -> 70.
  - Tried and reverted where nothing changed at the sprite's size: chamfer joins on the ellipsoid torsos and
    heads, lapels, claws, fangs, pistol parts.
- What the port changed in the docs and tools: shells are centred on the surface, `extrude` depth is centred,
  `rot` applies after `align` (a profile along an aligned line needs `rot: [1.5708, 0, 0]`), Bezier curves bend
  towards their control points, tubes pass through the midpoints of inner points, `bend` curves an extrusion's
  outline (not the plate), cuts can be extrusions (an A-line opening), the hood recipe is a pinched dome (an
  ellipsoid shell reads as a ball), tips need an apex under about 104 degrees to stay on the silhouette at the
  38 degree pitch; `validate` counts primitives and cuts, checks profile widths and speaks in the spec's numbers
  under scaled bones; `ref compare -o` takes a folder.

