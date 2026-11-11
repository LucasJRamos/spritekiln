# 18. Motion on one sheet: arcs and ground speed

**Status:** done (2026-11-11), released in 0.4.0 · **Track:** quality,
tokens · **Depends on:** 03 (pixel-exact previews)

## Problem
An animation is judged on a contact sheet: rows of directions, columns of frames. It shows every frame and
hides the motion. Whether a strike travels on an arc, whether the frames bunch up in the anticipation and
spread in the strike, whether a path overshoots and settles: the reader has to rebuild that from a grid of
64 px cells, and an AI does it poorly. The sheet is also the most expensive image of the workflow (frames ×
directions).

A walk has a second, invisible problem: the cycle is animated in place and the game moves the character. If
the game's speed is not the speed at which the planted feet slide back, the feet skate. Nothing told the user
(or the AI) what that speed is.

## Goal
One image per clip that shows the motion itself, and one number that makes a walk match the game.

## Proposal
1. **`spritekiln arcs <spec> --anim <clip> [--dirs s,e] [--track a,b] [--draft]`** (MCP: `arcs`). Per
   direction: every frame of the clip as a ghost (28 % opacity) under the last frame, and the path of each
   tracked point: one dot per frame, bigger where an event fires, joined by a line, the first frame numbered.
   Tracked by default: every socket, the IK ends (hands, feet) and the head; `--track` names bones, IK joints
   or sockets. Paths come from the rig (no render); only the ghosts are rendered, from the cache.
2. **Ground speed.** For a looping clip, the feet are the IK ends that rest near the ground. A foot is planted
   while it is within a quarter of its lift from its lowest point; the ground speed is the distance the planted
   feet travel divided by the time they take. `arcs` prints it; QA writes `info.ground_speed` (`px_per_s`,
   `units_per_s`, `uneven`, `feet`) and the summary says "move the character at that speed". `uneven` is the
   spread of the speed between frames of the stance: information, not a warning (a sine-wave stance gives
   about 0.8 and is what the templates use).

## Validation
- Tests: `tests/test_checks.py` (default tracks, tracks of a clip, the sheet within the image budget, an
  unknown track with a "did you mean", the template walk: 0.48 units of stance in 400 ms = 1.2 units/s = 30
  px/s at 0.040 units per pixel; no speed for an idle or an attack).
- Looked at: the hunter's walk and attack sheets (the sword hand's arc and the bunching of the windup read at
  a glance).

## Risks and open questions
- **A ghost sheet of a clip that barely moves is a blur of one pose.** That is what an idle is; its paths
  still show the bob. The contact sheet stays for frame-level problems.
- **Feet are guessed** (IK ends under a quarter of the model's height). A creature that walks on something
  else gets no ground speed rather than a wrong one.
- Not written to the exported JSON: the speed is advice for the game's code, and the output format (ADR-014)
  stays as it is. It could become a field if engines want to read it.

## Outcome (2026-11-11): done
- `spritekiln/motion.py` (`tracks`, `default_tracks`, `feet`, `ground_speed`, `sheet`), the `arcs` command and
  MCP tool, `info.ground_speed` in `qa.json` and in the QA summary.
- The animation docs put the arcs sheet between the key poses and the contact sheet, and tell the animator to
  report the ground speed.
