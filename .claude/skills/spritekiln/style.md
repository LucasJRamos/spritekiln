# The project's art style

Every asset of a game shares one look. SpriteKiln records it once per project, in the `[style]` table of
`spritekiln.toml`, from a short interview with the user. `spritekiln new` applies its numeric part (view,
density, frame size, directions, palette) to every new spec; the renderer applies its look (outline, shading,
lines, highlights, dither, light, snap) to every asset at render time; the rest (colours, proportions,
faces, animation, references) is how you model and animate every asset of the project.

## Before the first asset: interview the user
Run `spritekiln style` (MCP: `style`) before you create or change an asset in a project, once per session.
- **A style is recorded:** follow it for every asset. Do not ask the questions again.
- **No style is recorded yet:** **stop and interview the user before generating anything**, even when the
  request looks complete ("make a goblin" says nothing about the size of the characters on screen). The
  interview takes a minute; redoing a dozen assets in another style takes days.
- **No `spritekiln.toml`** (`style` says so): the project was not set up with `spritekiln init` and has no
  place for a style. Suggest `spritekiln init` to the user; do not interview.

Subagents cannot talk to the user: the main session runs the interview, and an agent that finds no style
recorded stops and reports that.

### How to interview: grill the user, briefly
- Ask the ten questions below in your own words and in the user's language, **at most four at a time**
  (three rounds). Give each one its options with the recommended one first; "I don't know" takes the
  recommendation. In Claude Code use the question tool (AskUserQuestion), one question per item, options
  with short descriptions; elsewhere, a numbered list in the chat that the user can answer in one line
  ("1a 2: 32 3a ...").
- **Do not accept vague answers.** Turn each one into a value, with one follow-up question when needed:
  "retro" → 16-bit or 8-bit, and how many pixels tall is a character? "Like Stardew Valley" → so about 32 px
  tall, top-down, dark outline, saturated colours: right? "Big sprites" → 64 or 96 px tall? Name the
  trade-off when it matters (below 32 px, details under 2 px vanish; `realistic` proportions need 64 px or
  more to read).
- **Use what you already know.** Answers given in the request ("a 48 px knight for my platformer") are not
  asked again: confirm them in the summary. With a splash art, propose answers from it (colours from
  `spritekiln ref prep`, proportions, outline). A project that already has specs gets suggested answers from
  `spritekiln style` (view, height, size, palette): present them as the proposal to confirm or change.
- **Summarize and confirm.** Show the answers in a short block and get a yes before recording them.
- **Record** them, then go on with the original request:

```
spritekiln style set --view topdown --height 48 --directions 8 --mirror no --palette gothic \
    --colors "dark, desaturated, one warm accent" --outline selective --shading soft \
    --lines depth --highlights yes --dither none --light classic \
    --proportions stylized --face minimal --animation fluid --snap no --references "Hyper Light Drifter" "art/refs/mood.png" \
    --notes "enemies glow red; no blood"
```

MCP: `style` with `answers: {view: topdown, height: 48, ...}`. `--size` (frame) follows the height unless
given; `--scale` sets the density directly for an expert who knows it.

## The questions
1. **View.** Top-down 3/4 (RPGs, action, tactics; the player sees the top and the front) or side view
   (platformers, side-scrollers, fighting games)? → `--view topdown|side` (recommended: topdown, or what
   the user said about the game).
2. **Size on screen (the resolution of the models).** How many pixels tall is a human-sized character in
   the game? Guide the answer: 24–32 px small retro (16-bit consoles, phones), 40–48 px classic detailed
   (recommended: 48), 56–72 px detailed, 96 px and more hi-bit. If the user only knows the tile size, a
   character is usually 1 to 1.5 tiles tall (32 px tiles → 40–48 px). Below 32 px SpriteKiln still works,
   but faces and small props turn into one or two pixels. → `--height N`; SpriteKiln derives
   `camera.scale` (the density every asset shares) and the frame `size` (48 → 64). A bigger creature later
   gets a bigger `size` with the same density.
3. **Directions.** Top-down: 8 (recommended, free movement) or 4 (grid movement, n e s w). Side view: e and
   w. And mirrored? Only the right-facing half is rendered and the engine flips it: about 40% less work,
   for symmetric designs only (a sword in the right hand swaps hands, the light comes from the other side).
   → `--directions 8|4|2 --mirror yes|no` (recommended: no).
4. **Colours.** The mood of the palette: dark and desaturated (the built-in `gothic`, recommended when the
   user has no idea), vivid, pastel, earthy, neon...? Or does the user have a palette or a reference image?
   → `--colors "<the mood in a few words>"` and `--palette <name>`: `gothic` (dark, desaturated) and `props`
   are built in; for another mood make a project palette `<specs>/palettes/<name>.yaml` (ramps of 4–6 tones
   from `spritekiln palette ramp "#hex" --steps 5`, or `spritekiln palette extract <image> -o
   <specs>/palettes/<name>.yaml`) and record its name.
5. **Outline and shading.** Outline: selective (each part outlined in its own darkest tone; recommended),
   dark (one near-black line around the whole sprite, the classic look; `--outline-color` picks the colour),
   colored (each material outlined in a lighter tone of its own colour: soft, modern) or none (painterly).
   Shading: soft (all the tones of a ramp, smooth light; recommended), flat (two tones per material, clean
   areas) or toon (three tones in hard steps, cel shading). → `--outline selective|dark|colored|none
   --shading soft|flat|toon`.
6. **Proportions.** Stylized (head 1.2–1.4× real size, 2–3 striking shapes; recommended), chibi (head
   1.6–2×, short limbs, few details) or realistic (head about 1×, slender; needs 64 px or more)? →
   `--proportions stylized|chibi|realistic`.
7. **Faces.** How much face does a character show? Minimal: eyes only, no nose or mouth; the shape of the head
   and the hair carry the character (anime and most pixel art; recommended). Simple: also a 1 px hint of a
   brow or a nose, only on heads 14 px tall or more. Detailed: nose, brows and a mouth, for big sprites (heads
   of 20 px or more). At 48 px a stylized head is about 10 px tall: a nose there reads as a big nose. →
   `--face minimal|simple|detailed`.
8. **Animation.** Fluid (8-frame walks, in-between frames, overlapping motion; recommended) or snappy
   (4–6-frame cycles, held poses, a retro feel)? And should the body move in whole pixels (less shimmering
   on slow idles, steps instead of drift; recommended no, yes suits snappy)? → `--animation fluid|snappy
   --snap yes|no`.
9. **Finish and light.** Render `spritekiln style preview` (MCP: `style_preview`; without a spec it uses the
   humanoid template), give the user the image (its path) and let them choose by looking. Inner lines: depth (between parts; recommended),
   depth+normal (also at folds of armour and stone: crisper) or none. Highlights on metal and gems: yes
   (recommended) or no. Dither: none (recommended), bayer2 (a checker between tones, retro) or bayer4
   (finer). Light: classic (top left; recommended), top, dramatic (low side light, strong contrast), soft
   (bright, low contrast) or flat (the game lights the sprites through normal maps). → `--lines
   depth|depth+normal|none --highlights yes|no --dither none|bayer2|bayer4 --light
   classic|top|dramatic|soft|flat`.
10. **References (optional).** Games, artists or images whose look to match, and anything else every asset
   must respect ("enemies glow red", "no blood", "readable on a small phone"). → `--references ...` and
   `--notes "..."`. Open the images the user names and let them inform the answers above.

## What the style means for each asset
| answer | modeling and colour | animation | the art director checks |
|---|---|---|---|
| view, height, directions, mirror, palette | `spritekiln new` sets them; never change `camera.scale`, `camera.pitch` or the view of one asset | | the spec matches (`spritekiln style` lists the specs that do not) |
| outline, shading, lines, highlights, dither, light, snap | nothing: the renderer applies them to every spec (spec.md, "render"). Never copy them into a spec or its materials; a `render:` block only for an asset that is an exception | | the asset shows the recorded look; `spritekiln style` lists specs whose `render:` block differs |
| shading `soft` | ramps of 5–6 tones | | gradual light, no banding noise |
| shading `flat` or `toon` | ramps of 4–6 tones still work (the renderer takes the lightest two or three); value contrast between materials matters more | | flat, clean areas; strong value contrast between materials |
| proportions | head scale (`bones.head` `scale`): stylized 1.2–1.4, chibi 1.6–2.0, realistic 1.0–1.1; limb lengths to match | | the proportions match the other assets |
| face | `minimal`: eyes only, the head kit's `nose: 0`; `simple`: a brow or a `nose` hint only on heads of 14 px or more; `detailed`: nose, brows, mouth on heads of 20 px or more. Any face: the head is not a ball and the hair has locks ([modeling.md](SKILL.md), "Heads, faces and hair") | | `pose --focus head`: no bump under 2 px on the face; the head and hair read as this character |
| animation `fluid` | | walk and run 8 frames, idle 6–8, tweens on actions, overlap and follow-through | |
| animation `snappy` | | walk and run 4–6 frames, idle 2–4, held keys, few or no tweens | |
| colors, references, notes | the palette, ramps and accents follow them | timing and feel follow them | the asset reads as the same game as the references and the approved assets |

## Changing the style
Only when the user explicitly asks to change the project's style ("from now on characters are 32 px",
"switch to no outlines"). Then record only what changed (`spritekiln style set --outline none`): the rest
stays, and `style` lists the existing specs that no longer match. Ask whether to update and re-render
them; do not do it on your own.

A request about one asset is not a style change. "Make this boss twice as big" means a bigger model and a
bigger `size` for that spec, with the same density; "this ghost has no outline" means `render: {outline:
none}` in its spec. Write the exception in that spec's `brief:` so later sessions keep it. When a request
seems to contradict the style without saying so, ask whether it is an exception for this asset or a new
style for the project.
