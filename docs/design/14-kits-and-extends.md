# 14. Kits and `extends`

**Status:** proposed · **Track:** forms, tokens · **Stage:** 4 (release 0.3) · **Depends on:** 13

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
