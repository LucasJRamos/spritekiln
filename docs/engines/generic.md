# SpriteKiln in any engine

A render is an atlas PNG plus a JSON that is a valid **Aseprite "hash" sprite sheet**, so any engine or
library that reads Aseprite exports loads it as is. What Aseprite's format cannot say (pivot, directions,
events, sockets, mirroring) is in the `spritekiln` block, described in [format.md](../format.md). Godot,
Unity and MonoGame have ready runtimes ([godot.md](godot.md), [unity.md](unity.md), [monogame.md](monogame.md));
for the rest, this page shows what to read and how.

```
spritekiln render specs/characters/knight/knight.yaml          # out/knight/: knight.png, knight.json, maps
spritekiln export specs/characters/knight/knight.yaml --engine generic --to path/in/your/game
```

> The snippets below are starting points written against each engine's documented API. They are not
> covered by SpriteKiln's tests, unlike the Godot, Unity and MonoGame runtimes.

## What every runtime does

1. **Clips.** Each frame tag `<anim>_<dir>` (`walk_ne`) is a clip; `spritekiln.animations[anim].directions[dir]`
   lists its frame keys, `durations` (ms per frame) and `loop`.
2. **Pivot.** Place the sprite so that `spritekiln.pivot` (px from the cell's top-left) sits on the
   entity's position: it is the ground point under the character, the right point for y-sorting.
3. **Direction.** From a screen-space vector `v` (y down): `yaw = atan2(v.x, v.y)` in degrees, then the
   direction in `direction_yaw` with the nearest angle (mirrored ones included).
4. **Mirrored directions.** When `spritekiln.mirrors` has the direction (`{"w": "e"}`), play the twin's clip
   flipped horizontally around the pivot and negate socket `x`.
5. **Timing and events.** Advance with accumulated time, not frame counts. Frame *i*'s events
   (`events["i"]`) fire when it becomes visible; frame 0's when the clip starts. A clip with `loop: false`
   stops on its last frame.
6. **Sockets.** `sockets[name][frame]` is `[x, y, depth]` in px from the pivot, or `null` while hidden.
7. **Maps.** `*_normal.png` (camera-space normals) and `*_emissive.png` (draw additively on top) share the
   atlas layout.

## Phaser 3

Phaser reads Aseprite files and their per-frame durations:

```js
// preload
this.load.aseprite('knight', 'knight.png', 'knight.json');
this.load.json('knight-data', 'knight.json');
// create
const tags = this.anims.createFromAseprite('knight');           // one animation per <anim>_<dir>
const data = this.cache.json.get('knight-data').spritekiln;
const knight = this.add.sprite(x, y, 'knight')
  .setOrigin(data.pivot.x / data.frame_size, data.pivot.y / data.frame_size);
function play(anim, dir) {
  const twin = (data.mirrors || {})[dir];
  knight.setFlipX(Boolean(twin));                               // the origin is the pivot: flips around it
  knight.play({ key: `${anim}_${twin || dir}`, repeat: data.animations[anim].loop ? -1 : 0 });
}
knight.on('animationupdate', (a, frame) => {                    // events of frames 1..n
  const [anim, dir] = [a.key.slice(0, a.key.lastIndexOf('_')), a.key.slice(a.key.lastIndexOf('_') + 1)];
  for (const ev of data.animations[anim].directions[dir].events[frame.index - 1] || []) onEvent(anim, ev);
});
```

Fire frame 0's events yourself right after `play()` (and on `animationrepeat` for loops). Depth: set
`knight.setDepth(knight.y)`.

## LÖVE

```lua
local json = require "json"   -- any JSON library, e.g. rxi/json.lua
local Kiln = {}; Kiln.__index = Kiln

function Kiln.load(dir, name)
  local data = json.decode(love.filesystem.read(dir .. "/" .. name .. ".json"))
  local image = love.graphics.newImage(dir .. "/" .. data.meta.image)
  image:setFilter("nearest", "nearest")
  local quads = {}
  for key, f in pairs(data.frames) do
    quads[key] = love.graphics.newQuad(f.frame.x, f.frame.y, f.frame.w, f.frame.h, image:getDimensions())
  end
  return setmetatable({ data = data.spritekiln, image = image, quads = quads, t = 0, frame = 1 }, Kiln)
end

function Kiln:play(anim, dir, onEvent)
  local twin = self.data.mirrors and self.data.mirrors[dir]
  self.anim, self.flip, self.onEvent, self.t, self.frame = anim, twin ~= nil, onEvent, 0, 1
  self.clip = self.data.animations[anim].directions[twin or dir]
  self:fire()
end

function Kiln:fire()
  for _, ev in ipairs((self.clip.events or {})[tostring(self.frame - 1)] or {}) do self.onEvent(self.anim, ev) end
end

function Kiln:update(dt)
  self.t = self.t + dt * 1000
  while self.t >= self.clip.durations[self.frame] do
    self.t = self.t - self.clip.durations[self.frame]
    if self.frame < #self.clip.frames then self.frame = self.frame + 1
    elseif self.data.animations[self.anim].loop then self.frame = 1
    else self.t = 0; return end
    self:fire()
  end
end

function Kiln:draw(x, y, scale)
  local p = self.data.pivot
  love.graphics.draw(self.image, self.quads[self.clip.frames[self.frame]], math.floor(x), math.floor(y), 0,
    (self.flip and -1 or 1) * scale, scale, p.x, p.y)   -- the origin is the pivot: flips around it
end

return Kiln
```

## Defold

Make a **Tile Source** from the atlas (tile width and height = `frame_size`) with one animation per clip:
`start tile` = `row` × columns + 1 and `end tile` = `start tile` + frames − 1, where `row` is the clip's
atlas row in the JSON and columns = atlas width / `frame_size` (short rows are padded). Defold plays a flipbook at a fixed
fps, so set each animation's fps to `1000 / duration` when its durations are all equal, or drive the frame
from a script that reads `durations` and `events` from the JSON (loaded with `sys.load_resource`):

```lua
-- show frame i (0-based) of a clip with n frames, without Defold's own timing
sprite.play_flipbook("#sprite", clip_id, nil, { offset = i / n, playback_rate = 0 })
```

Set the sprite's position offset so the pivot sits on the game object's origin, and `sprite.set_hflip`
for mirrored directions.

## GameMaker

Import each clip as a sprite (an atlas row is a strip of `frame_size` cells, see `row` in the JSON) and set
the sprite's origin to the pivot. GameMaker plays sprites at one speed, so for exact timing set
`image_speed = 0` and advance `image_index` from the durations in the Step event:

```gml
// Create: clip = the clip's data from the JSON (json_parse), t = 0
t += delta_time / 1000;
while (t >= clip.durations[image_index]) {
    t -= clip.durations[image_index];
    if (image_index + 1 < array_length(clip.durations)) image_index += 1;
    else if (anim_loops) image_index = 0;
    else { t = 0; break; }
    var evs = clip.events[$ string(image_index)];
    if (evs != undefined) for (var i = 0; i < array_length(evs); i++) on_event(evs[i]);
}
```

For mirrored directions draw with `image_xscale = -1` (the origin is the pivot, so it flips around it).
Sequences also take per-frame lengths and broadcast messages, if you prefer to build clips there.
