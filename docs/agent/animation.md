# Animation

Animations only move **channels** (see [spec.md](spec.md), `animations`). If a degree of freedom is
missing (a cape that should sway), add a channel, use it in the bone or part expression, and animate it.

## Pick the mode
- **Cycles** (idle, walk, run, hover): `frames` + `channels` with expressions of `p` (0..2π). They loop
  seamlessly when everything is periodic in `p` (sin/cos of `p`, `2*p`...). Never use `t` in a loop.
- **Actions** (attack, hit, death, cast, dash): `keys`, one key = one frame, `ms` per key. Pose to pose.

## Frame counts and timing (reference for 64 px)
| animation | frames | ms per frame |
|---|---|---|
| idle | 4–8 | 120–180 |
| walk | 8 | 90–110 |
| run | 6–8 | 70–90 |
| light attack | 5–7 | anticipation 100–170, strike 40–60, recovery 100–130 |
| heavy attack | 7–10 | held anticipation 170–250 |
| hit | 3–4 | 60–90 |
| death | 6–10 | 90–140, last frame long (400+) |

## Principles applied to channels
- **Anticipation:** 1–2 keys moving against the strike (opposite twist, hand back, `squash` < 1, negative
  `bob`). The most extreme key is the longest.
- **Strike:** one short frame with a smear (`arc`) and stretch (`squash` > 1), `root` moving forward
  (lunge). In pixel art the impact frame beats interpolation: do not smooth the strike with tweens.
- **Follow-through:** the body overshoots (more twist), the smear fades (`smear_fade` 0.6–0.7), appendages
  (tail, cape, wings) lag in phase.
- **Overlap:** secondary parts at the same frequency with a delayed phase: `tail: "0.7*sin(p - 0.8)"`.
- **Amplitude in pixels:** with `camera.scale` s, 1 px = s units. Idle: 1–2 px (`bob` ≈ 0.05). Motions under
  0.5 px flicker; more than 3 px in an idle looks nervous.
- **Walk:** feet at `[x, lift*pos(-sin(p)), z0 + stride*cos(p)]` (the R side with the signs flipped), `bob`
  in `cos(2p)` (lowest at contacts), shoulders twisting against the hips, arms against the legs. Cycles are
  in place (the game moves the character); the planted foot slides back on screen, as expected.
- **Cheat per direction** when a pose reads badly from one side: `yaw` and `dir` work in key values, e.g.
  `rifle_pitch: "-0.08 + -0.2*pulse(yaw, 0, 70)"` raises a barrel only near `s`, where it would point at
  the camera and vanish.

## Side view (`view: side`)
- Typical clips: idle, run, jump (take-off), rise and fall (loops or single frames), land, crouch, attack,
  hurt, death; wall-slide and climb when the game has them.
- Jumps are **in place**: the game moves the character; the clip shows the body (anticipation, stretch on
  take-off, tuck at the apex, squash on landing). Use `root` only for a small offset inside the frame.
- Mark gameplay moments as events: `takeoff`, `land`, `step_l`/`step_r`, `hit`.

## Events, timing and sockets (gameplay contract)
- Mark events: `windup` on the anticipation, `hit` on the impact, `release` when a projectile or item
  leaves, `step_l`/`step_r` on contacts. They go to the JSON; the runtimes emit them (`anim_event` in
  Godot, or `px_event` in the older `PxSprite2D`; `EventFired` in Unity; `OnEvent` in MonoGame).
- **When an event fires:** at the start of its frame, i.e. the sum of the durations before it. An event on
  frame 0 fires when the clip starts.
- **Timing targets:** when the game expects a moment (`release` at 2 frames, total 7 frames at 60 fps),
  write it in `timing:`; `validate` and QA fail beyond ±1 frame.
- **Sockets:** where the game spawns something (muzzle flash, thrown item, footstep dust), declare a socket
  at the centre of that effect; the engine reads its position per frame instead of measuring sprites.

## Check
1. `pose --anim <a> --frame <i> --dirs s,e,n,se` on the key frames before rendering.
2. `render --anims <a>` → open `preview/contact_<a>.png` (rows = directions, columns = frames) and the GIF.
3. QA: "loop seam" (last → first jumps) = a non-periodic channel; "identical frames" = a key that changes
   nothing; "clipped at the edge" = a gesture too big for the frame; a timing error = durations off target.
4. Check the **diagonals and `n`**: a strike that reads in `s` can vanish behind the body in `n`; sometimes
   the smear arc must grow or the hand rise.

## Rules for an animator (human or AI)
- Run `spritekiln style` first: its `animation` answer (fluid or snappy, [style.md](style.md)) sets the
  frame counts and the feel. If no style is recorded, stop and report that the user has to answer the
  style questions first.
- Touch `animations:` (and, for a new degree of freedom, `channels:` plus the expression using it). Do not
  change the model's geometry beyond what the animation needs.
- Look at the key frames before rendering; after rendering, fix QA errors (clipping, loop seams, identical
  frames, timing).
- Report: animations created or changed, frames and ms, events, timing targets, QA warnings left, and the
  paths of the GIFs and contact sheets.
