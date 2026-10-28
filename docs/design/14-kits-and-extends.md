# 14. Kits and `extends`

**Status:** done (stage 4) · **Track:** forms, tokens · **Stage:** 4 (release 0.3) · **Depends on:** 13

## Problem
Every character spec is a full copy:

| spec | lines |
|---|---|
| cacador | 215 |
| cyborg | 471 |
| templar | 496 |
| wren | 530 |
| huntress | 742 |

Their skeleton, IK, channels and base animations are mostly the humanoid template's, edited; weapons, hats
and capes are modeled again for each character. The AI reads, writes and re-reads all of it. A fix to the
template, or a better sword, never reaches the characters made before.

## Goal
- A new humanoid states only what differs from its base: at most 250 lines for a character of the templar's
  complexity.
- Shared pieces (weapons, hats, capes) are reused with parameters.
- Each piece is good once, built with the shapes of [13](13-shape-operators.md).

## Proposal
**`extends`:**
```yaml
spritekiln: 1
name: knight
extends: humanoid            # a built-in template, a path relative to the spec, or a project template
remove: [parts.cape, animations.dash]
parts:
  helm: {...}                # new or replacing the base's helm
```
- The base is merged deeply, and the child's keys win. Lists are replaced, never merged: simple and
  predictable. `remove` deletes paths.
- Merging happens before mirroring, so `_L` items of the base still get their `_R` twins.

**Kits:** reusable bundles of parts, with their materials, sockets and channels, taking parameters.
```yaml
use:
  - kit: sword                # built-in, or <specs>/kits/sword.yaml of the project
    as: sword                 # prefix of the parts it adds (sword_blade, sword_guard...)
    at: wrist_R               # the space it attaches to
    with: {length: 0.85, width: 0.06, guard: true, material: steel}
```
- A kit file is a spec fragment with `params:` and their defaults. Params are variables in its expressions
  (`"[0, 0, length]"`), like channels.
- Built-in kits, built with 13 and reviewed like showcase assets:
  - weapons: sword, axe, mace, hammer, spear, bow, staff, pistol, rifle;
  - armour and headwear: shield, hood, wide-brim hat, helmet;
  - clothing: cape, belt, pouch.

**Seeing through the indirection:**
- `spec outline` and `spec show --resolved` ([04](04-spec-outline-and-show.md)) show what a base or a kit
  adds, and where it comes from.
- Errors inside a kit or a base point to that file's line.

**The render cache and hot reload follow the base and kit files.** Their modification stamps join the spec's
own, as palette files already do (`_files` in `spritekiln/spec.py`).

## Plan
1. `extends` and `remove` in `spec.load`; the stamps of base files.
2. Kits: loader, params in the expression environment, name prefixes, mirroring, sockets.
3. The kit library and its docs (`docs/agent/modeling.md`); templates that use it.
4. Rewrite one example with `extends` and kits (the cacador, CC0) and measure its lines.

## Validation
- **The rewrite renders pixel-identical:** the rewritten example, resolved, matches the original.
- **Line counts** before and after.
- **Errors point to the right file:** an error inside a kit names the kit file and its line.
- **The library renders and validates:** every built-in kit has a fixture.

## Risks and open questions
- **The AI may not see what a kit adds.** The outline marks kit-provided items with their origin, and
  `--resolved` shows the whole.
- **Changes to a template reach its children.** That is wanted for fixes, unwanted for a finished game. A
  version pin, `extends: humanoid@0.3`? Proposed: built-in templates and kits keep backwards-compatible
  changes within a minor version; a visual change bumps the template's name (`humanoid2`).
- **Kits from other projects or the community** raise licence questions: the kit file carries a `license:`
  field, and the built-in ones are CC0.

## Outcome (2026-10-28): done
- `spritekiln/kits.py` resolves `extends`, `remove` and `use` into one document before `spec.load` reads it, and
  keeps, for every item, the files and lines that wrote it (`_origins`). `check`, `quick_errors` and the
  warnings locate problems through it, so a thin blade in a kit points at the kit's line. Bases: a built-in
  template, `<specs>/templates/<name>.yaml` or a path; merged deeply, lists replaced, `name` and `brief` not
  inherited, relative palettes made absolute, loops reported. `remove` takes paths or `use.<as>`, with the
  closest path on a typo.
- Kits: params are replaced in the kit's expressions through the AST (a param alone becomes its value, so
  `r: width` is a number and `when: guard` a boolean); names get `<as>_`, the frame `at` maps to the attachment,
  kit channels are renamed in expressions; materials, ramps and `host_channels` apply only where the spec has
  none of that name; a `use` with the `as` of a base's replaces it. A plane's `at:` is a distance, not a frame
  (found by the modelers). A kit file opened as a spec is the kit on its `host`, so `pose`, `validate` and the
  schema test cover every kit.
- `sx`: documented in `expr.py` since 0.1 but never set; now -1 inside an automatic `_R` twin, so kits write
  their per-direction cheats with `yaw*sx` and stay right when used `as: x_L`. Changing what `yaw` means in
  twins was rejected: existing specs (Hunt Tower's) would change.
- `spec outline` lists inherited and kit items with their origin; `spec show` prints them from their file
  (`(as parts.blade)` for a renamed kit item). `spritekiln kits [name]` and MCP `kits`; `new --extends`
  writes a 10-line spec over the template; the style's spec facts read through bases and skip kit files.
- The library (16 kits, 1004 lines, CC0): four `character-modeler` agents built it in parallel, two
  `pixel-art-director` agents reviewed it (weapons: 3 of 9 ship as is; gear: 2 of 7), two modelers applied the
  fixes: per-direction `cheat`s for the axe, hammer, spear, staff, bow, pistol, rifle and shield, so that no two
  weapons are the same grey bar in `s`; a lighter wood (tones 2-5) off the dark robe; the hat tipped up so the
  eyes show; the hood's own material; the pouch pair moved off the buckle. Before 0.3 freezes them, the names
  were made consistent: widths are full widths, `thick` is a diameter, `length` runs from the fist, `size`
  scales, `tilt` leans (negative: front up), sockets `hit` (impact), `tip` (points), `muzzle`, `orb`, `rest`.
- Templates: the humanoid and side templates hold the sword kit (the side one with `roll: 1.5708` and `pitch:
  sword_pitch`), and their `steel` is `finish: metal` (the reviewers found the plain steel turned a helmet white).
- The cacador extends the humanoid: 215 → 30 lines, its 552 frames (colour, normal and emissive images of
  every animation and direction) identical to the copy's; the goldens `cacador_pose_rest.png` and
  `cacador_pose_attack_4.png` were rendered from the copy before the rewrite. It drops the base's sword kit and
  metal finish for its own boxes, and re-declares the smear after them: the order of parts decides ties.
- A new example, `specs/characters/knight/knight.yaml`: 21 lines (helmet, cape, shield, belt, a pair of pouches,
  the template's sword, a grey tunic). It meets the "≤ 250 lines" target, but it is simpler than the Templar
  (its three clips are the template's, the Templar has ten and its own skeleton); the showcase specs stay as
  Hunt Tower uses them.
- Decided: built-in templates and kits change only compatibly within a minor version; a visual change comes
  under a new name (`humanoid2`). 0.3 is where the templates got the sword kit and metal steel.
- Open: `when:` works on whole parts only (kits move a prim away with an expression to switch it); the
  template's attack is a sword slash, so spears, staves, bows and guns need their own clips (each kit says so).

