@tool
@icon("res://addons/spritekiln/icon.svg")
class_name KilnSprite2D
extends AnimatedSprite2D
## Plays a sprite exported by SpriteKiln: animations in up to 8 directions with exact per-frame
## durations, gameplay events (hit, step_l, windup...), sockets (muzzles, hands...) and an emissive layer.
##
## The node's origin is the ground point under the character (SpriteKiln's pivot), which makes
## y-sorting work. Typical use:
## [codeblock]
## $Sprite.play_anim(&"walk")
## $Sprite.face(velocity)                 # picks the nearest exported (or mirrored) direction
## $Sprite.anim_event.connect(func(anim, ev): if ev == &"hit": deal_damage())
## $Sprite.anim_finished.connect(func(anim): $Sprite.play_anim(&"idle"))
## var muzzle := $Sprite.to_global($Sprite.get_socket(&"muzzle_R"))
## [/codeblock]

## Emitted when a frame that carries an event becomes visible (hit, windup, step_l, release...).
signal anim_event(anim: StringName, event: StringName)
## Emitted when a non-looping animation reaches its end.
signal anim_finished(anim: StringName)

## The JSON exported by SpriteKiln (<name>.json): pivot, directions, loops, events, sockets.
@export var sheet: JSON:
	set(v):
		sheet = v
		_parse_sheet()
		_refresh_clip()
## SpriteFrames over the emissive atlas (<name>_emissive.tres). Optional; drawn with additive blending.
@export var emissive_frames: SpriteFrames:
	set(v):
		emissive_frames = v
		_setup_emissive()
## Current logical animation (idle, walk, attack...). Use play_anim() in game code.
@export var anim: StringName = &"idle":
	set(v):
		anim = v
		_refresh_clip()
## Current direction (s, se, e, ne, n, nw, w, sw). Use face() / set_facing() in game code.
@export var facing: StringName = &"s":
	set(v):
		if v == facing:
			return
		facing = v
		_switch_direction()
## Start playing `anim` when the node enters the scene (the built-in `autoplay` is ignored).
@export var auto_play: bool = true

var _dirs: Array = []  # [{name: StringName, yaw: float (rad)}], mirrored directions included
var _mirrors: Dictionary = {}  # direction -> rendered direction it flips (from `mirror: true` specs)
var _anims: Dictionary = {}  # anim -> {loop, events: {dir: {frame: [StringName]}}, sockets: {dir: {name: [..]}}}
var _pivot := Vector2.ZERO
var _frame_size := 0
var _emissive: AnimatedSprite2D
var _suppress_events := false
var _started := false


func _ready() -> void:
	_parse_sheet()
	_setup_emissive()
	if Engine.is_editor_hint():
		_refresh_clip()
		return
	frame_changed.connect(_on_frame_changed)
	animation_changed.connect(_sync_emissive)
	animation_finished.connect(_on_animation_finished)
	if auto_play and not _started:  # play_anim() before _ready() already started a clip
		play_anim(anim, true)
	else:
		_refresh_clip()


# ---------------------------------------------------------------- API

## Plays a logical animation (no direction suffix). Restarts only when `restart` or when it changed.
## Events of frame 0 fire right away, in this call.
func play_anim(name: StringName, restart: bool = false) -> void:
	if not _anims.has(name):
		push_warning("KilnSprite2D: no animation '%s' in %s" % [name, _sheet_name()])
		return
	var changed := name != anim or not is_playing()
	anim = name  # the setter points `animation` at the clip without playing it
	_started = true
	if changed or restart:
		var clip := clip_name()
		_suppress_events = true
		if sprite_frames and sprite_frames.has_animation(clip):
			stop()
			play(clip)
		_suppress_events = false
		_sync_emissive()
		_fire_events(0)


## Picks the exported direction nearest to a screen vector (x right, y down).
func face(dir: Vector2) -> void:
	if dir.length_squared() < 1e-6 or _dirs.is_empty():
		return
	var yaw := atan2(dir.x, dir.y)  # s = 0, e = +90 deg, n = 180, w = -90 (SpriteKiln convention)
	var best: StringName = facing
	var best_d := INF
	for d in _dirs:
		var diff: float = absf(wrapf(yaw - d.yaw, -PI, PI))
		if diff < best_d:
			best_d = diff
			best = d.name
	facing = best


## Sets the direction by name (s, se, e...), keeping the current frame.
func set_facing(dir: StringName) -> void:
	facing = dir


## Unit screen vector of the current direction.
func facing_vector() -> Vector2:
	for d in _dirs:
		if d.name == facing:
			return Vector2(sin(d.yaw), cos(d.yaw))
	return Vector2.DOWN


## Clip in the SpriteFrames for the current animation and direction: "<anim>_<dir>" (a mirrored
## direction plays its twin's clip, flipped).
func clip_name() -> StringName:
	return StringName("%s_%s" % [anim, _mirrors.get(facing, facing)])


## Logical animations available.
func anim_names() -> Array:
	return _anims.keys()


## Directions this sprite can face (exported and mirrored).
func direction_names() -> Array:
	var out := []
	for d in _dirs:
		out.append(d.name)
	return out


func is_loop(name: StringName = anim) -> bool:
	return _anims.get(name, {}).get("loop", true)


## Position of a socket (muzzle, hand, foot...) in the current frame, in this node's local space (pixels,
## origin = the ground point under the character). Vector2.INF when the animation has no such socket or
## it is hidden in this frame. Use `to_global()` for world coordinates.
func get_socket(socket: StringName) -> Vector2:
	var p = _socket_data(socket)
	if p == null:
		return Vector2.INF
	var local := Vector2(float(p[0]), float(p[1])) + (_pivot - _pivot.round())
	if _is_mirrored():
		local.x = -local.x
	return local


## Depth of a socket in the current frame: ground distance in pixels from the character's vertical axis
## toward the viewer (> 0 in front of the body, < 0 behind). NAN when unavailable.
func get_socket_depth(socket: StringName) -> float:
	var p = _socket_data(socket)
	return float(p[2]) if p != null else NAN


## True when the socket exists and is visible in the current frame.
func has_socket(socket: StringName) -> bool:
	return _socket_data(socket) != null


## Socket names exported for the current animation and direction.
func socket_names() -> Array:
	return _anims.get(anim, {}).get("sockets", {}).get(_mirrors.get(facing, facing), {}).keys()


# ---------------------------------------------------------------- internals

func _sheet_name() -> String:
	var px := _block()
	return str(px.get("name", "?")) if not px.is_empty() else "?"


## The exporter's block: "spritekiln" (output format 1) or "pxforge" (older files).
func _block() -> Dictionary:
	if sheet == null or not (sheet.data is Dictionary):
		return {}
	for key in ["spritekiln", "pxforge"]:
		if sheet.data.has(key):
			return sheet.data[key]
	return {}


func _parse_sheet() -> void:
	_dirs.clear()
	_anims.clear()
	_mirrors.clear()
	var px := _block()
	if px.is_empty():
		return
	var yaws: Dictionary = px.get("direction_yaw", {})
	for d in px.get("mirrors", {}):
		_mirrors[StringName(d)] = StringName(px["mirrors"][d])
	for d in Array(px.get("directions", [])) + _mirrors.keys():
		_dirs.append({"name": StringName(d), "yaw": deg_to_rad(float(yaws.get(String(d), _default_yaw(d))))})
	for a in px.get("animations", {}):
		var A: Dictionary = px["animations"][a]
		var evs := {}
		var socks := {}
		for d in A.get("directions", {}):
			var D: Dictionary = A["directions"][d]
			socks[StringName(d)] = D.get("sockets", {})
			var per := {}
			for f in D.get("events", {}):
				var list := []
				for e in D["events"][f]:
					list.append(StringName(e))
				per[int(f)] = list
			evs[StringName(d)] = per
		_anims[StringName(a)] = {"loop": bool(A.get("loop", true)), "events": evs, "sockets": socks}
	var pv: Dictionary = px.get("pivot", {})
	_pivot = Vector2(float(pv.get("x", 0)), float(pv.get("y", 0)))
	_frame_size = int(px.get("frame_size", 0))
	centered = false
	_apply_flip()


static func _default_yaw(d: String) -> float:
	match d:
		"s": return 0.0
		"se": return 45.0
		"e": return 90.0
		"ne": return 135.0
		"n": return 180.0
		"nw": return -135.0
		"w": return -90.0
		"sw": return -45.0
	return 0.0


func _is_mirrored() -> bool:
	return _mirrors.has(facing)


## Mirrored directions draw their twin's frames flipped, with the pivot still on the node's origin.
func _apply_flip() -> void:
	flip_h = _is_mirrored()
	var x := -roundf(_pivot.x)
	if flip_h:
		x = -(_frame_size - roundf(_pivot.x))
	offset = Vector2(x, -roundf(_pivot.y))
	if _emissive:
		_emissive.offset = offset
		_emissive.flip_h = flip_h


## Points `animation` at the current clip without playing it (editor, auto_play off).
func _refresh_clip() -> void:
	_apply_flip()
	if sprite_frames == null:
		return
	var clip := clip_name()
	if sprite_frames.has_animation(clip) and animation != clip:
		_suppress_events = true
		animation = clip
		_suppress_events = false
		_sync_emissive()


## Changes direction keeping frame and progress (the animation continues where it was).
func _switch_direction() -> void:
	_apply_flip()
	if sprite_frames == null:
		return
	var clip := clip_name()
	if not sprite_frames.has_animation(clip) or animation == clip:
		return
	var f := frame
	var p := frame_progress
	var was_playing := is_playing()
	_suppress_events = true
	animation = clip
	set_frame_and_progress(f, p)
	if was_playing and not Engine.is_editor_hint():
		play()
	_suppress_events = false
	_sync_emissive()


func _socket_data(socket: StringName):
	var per: Dictionary = _anims.get(anim, {}).get("sockets", {}).get(_mirrors.get(facing, facing), {})
	var frames = per.get(String(socket))
	if frames == null or frame >= frames.size():
		return null
	return frames[frame]


func _fire_events(f: int) -> void:
	var current := anim  # a copy: Godot hands the member itself to every listener, and one may change it
	var A: Dictionary = _anims.get(current, {})
	var per: Dictionary = A.get("events", {}).get(_mirrors.get(facing, facing), {})
	if per.has(f):
		for e in per[f]:
			anim_event.emit(current, e)


func _on_frame_changed() -> void:
	_sync_emissive()
	if _suppress_events:
		return
	_fire_events(frame)


func _on_animation_finished() -> void:
	var current := anim  # a copy (see _fire_events)
	anim_finished.emit(current)


func _setup_emissive() -> void:
	if not is_inside_tree():
		return
	if emissive_frames == null:
		if _emissive:
			_emissive.queue_free()
			_emissive = null
		return
	if _emissive == null:
		_emissive = AnimatedSprite2D.new()
		_emissive.name = "Emissive"
		var mat := CanvasItemMaterial.new()
		mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		_emissive.material = mat
		_emissive.centered = false
		_emissive.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		_emissive.light_mask = 0
		add_child(_emissive, false, Node.INTERNAL_MODE_BACK)
	_emissive.sprite_frames = emissive_frames
	_emissive.offset = offset
	_emissive.flip_h = flip_h
	_sync_emissive()


func _sync_emissive() -> void:
	if _emissive == null or _emissive.sprite_frames == null:
		return
	if _emissive.sprite_frames.has_animation(animation):
		if _emissive.animation != animation:
			_emissive.animation = animation
		_emissive.set_frame_and_progress(frame, 0.0)
		_emissive.visible = true
	else:
		_emissive.visible = false
