@tool
@icon("res://addons/pxforge/icon.svg")
class_name PxSprite2D
extends AnimatedSprite2D
## Reproduz um atlas exportado pelo pxforge (`pxforge godot <spec>`): animações em 8 direções
## com duração exata por frame, eventos de gameplay (hit, step_l, windup...) e camada emissiva.
##
## O node fica com a origem no ponto de contato com o chão (pivô do pxforge), o que deixa o
## Y-sort correto. Uso típico:
## [codeblock]
## $Sprite.play_anim(&"walk")
## $Sprite.face(velocity)                 # escolhe a direção exportada mais próxima
## $Sprite.px_event.connect(func(anim, ev): if ev == &"hit": deal_damage())
## $Sprite.px_finished.connect(func(anim): $Sprite.play_anim(&"idle"))
## [/codeblock]

## Emitido no frame que carrega um evento (ex.: hit, windup, step_l, step_r, release).
signal px_event(anim: StringName, event: StringName)
## Emitido quando uma animação sem loop chega ao fim.
signal px_finished(anim: StringName)

## JSON gerado pelo pxforge (<nome>.json). Traz pivô, direções, loop e eventos.
@export var sheet: JSON:
	set(v):
		sheet = v
		_parse_sheet()
		_refresh_clip()
## SpriteFrames sobre o atlas emissivo (<nome>_emissive.tres). Opcional: desenhado em blend aditivo.
@export var emissive_frames: SpriteFrames:
	set(v):
		emissive_frames = v
		_setup_emissive()
## Animação lógica atual (idle, walk, attack...). Use play_anim() em jogo.
@export var anim: StringName = &"idle":
	set(v):
		anim = v
		_refresh_clip()
## Direção atual (s, se, e, ne, n, nw, w, sw). Use face() / set_facing() em jogo.
@export var facing: StringName = &"s":
	set(v):
		if v == facing:
			return
		facing = v
		_switch_direction()
## Começa a tocar `anim` automaticamente ao entrar na cena (o `autoplay` nativo é ignorado).
@export var auto_play: bool = true

var _dirs: Array = []            # [{name: StringName, yaw: float(rad)}]
var _anims: Dictionary = {}      # anim -> {loop, events: {dir: {frame: [StringName]}}, sockets: {dir: {name: [..]}}}
var _pivot := Vector2.ZERO
var _emissive: AnimatedSprite2D
var _suppress_events := false


func _ready() -> void:
	_parse_sheet()
	_setup_emissive()
	if Engine.is_editor_hint():
		_refresh_clip()
		return
	frame_changed.connect(_on_frame_changed)
	animation_changed.connect(_sync_emissive)
	animation_finished.connect(_on_animation_finished)
	if auto_play:
		play_anim(anim, true)
	else:
		_refresh_clip()


# ---------------------------------------------------------------- API

## Toca uma animação lógica (sem sufixo de direção). Reinicia só se `restart` ou se mudou.
func play_anim(name: StringName, restart: bool = false) -> void:
	if not _anims.has(name):
		push_warning("PxSprite2D: animação '%s' não existe em %s" % [name, _sheet_name()])
		return
	var changed := name != anim or not is_playing()
	anim = name          # o setter já troca o clip (sem tocar)
	if changed or restart:
		var clip := clip_name()
		_suppress_events = true
		if sprite_frames and sprite_frames.has_animation(clip):
			stop()
			play(clip)
		_suppress_events = false
		_sync_emissive()
		_fire_events(0)


## Escolhe a direção exportada mais próxima de um vetor em tela (x direita, y baixo).
func face(dir: Vector2) -> void:
	if dir.length_squared() < 1e-6 or _dirs.is_empty():
		return
	var yaw := atan2(dir.x, dir.y)     # s = 0, e = +90°, n = 180°, w = -90°  (convenção pxforge)
	var best: StringName = facing
	var best_d := INF
	for d in _dirs:
		var diff: float = absf(wrapf(yaw - d.yaw, -PI, PI))
		if diff < best_d:
			best_d = diff
			best = d.name
	facing = best


## Define a direção pelo nome (s, se, e, ...), mantendo o frame atual.
func set_facing(dir: StringName) -> void:
	facing = dir


## Vetor unitário (tela) da direção atual.
func facing_vector() -> Vector2:
	for d in _dirs:
		if d.name == facing:
			return Vector2(sin(d.yaw), cos(d.yaw))
	return Vector2.DOWN


## Nome do clip no SpriteFrames: "<anim>_<facing>".
func clip_name() -> StringName:
	return StringName("%s_%s" % [anim, facing])


## Animações lógicas disponíveis.
func anim_names() -> Array:
	return _anims.keys()


## Direções exportadas (ordem do pxforge).
func direction_names() -> Array:
	var out := []
	for d in _dirs:
		out.append(d.name)
	return out


func is_loop(name: StringName = anim) -> bool:
	return _anims.get(name, {}).get("loop", true)


## Position of a socket (muzzle, hand, foot...) in the current frame, in this node's local space (pixels,
## origin = the ground point under the character). Vector2.INF when the animation has no such socket
## or it is hidden in this frame. Use `to_global()` for world coordinates.
func get_socket(socket: StringName) -> Vector2:
	var p = _socket_data(socket)
	if p == null:
		return Vector2.INF
	return Vector2(float(p[0]), float(p[1])) + (_pivot - _pivot.round())


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
	return _anims.get(anim, {}).get("sockets", {}).get(facing, {}).keys()


# ---------------------------------------------------------------- internals

func _sheet_name() -> String:
	var px := _block()
	return str(px.get("name", "?")) if not px.is_empty() else "?"


## The exporter's block: "spritekiln" (output format 1) or "pxforge" (older files, `pxforge` command).
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
	var px := _block()
	if px.is_empty():
		return
	var yaws: Dictionary = px.get("direction_yaw", {})
	for d in px.get("directions", []):
		_dirs.append({"name": StringName(d), "yaw": deg_to_rad(float(yaws.get(d, _default_yaw(d))))})
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
	centered = false
	offset = Vector2(-roundf(_pivot.x), -roundf(_pivot.y))
	if _emissive:
		_emissive.offset = offset


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


## Aponta `animation` para o clip atual sem iniciar a reprodução (editor / autoplay off).
func _refresh_clip() -> void:
	if sprite_frames == null:
		return
	var clip := clip_name()
	if sprite_frames.has_animation(clip) and animation != clip:
		_suppress_events = true
		animation = clip
		_suppress_events = false
		_sync_emissive()


## Troca de direção preservando frame e progresso (a animação continua de onde estava).
func _switch_direction() -> void:
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
	var per: Dictionary = _anims.get(anim, {}).get("sockets", {}).get(facing, {})
	var frames = per.get(String(socket))
	if frames == null or frame >= frames.size():
		return null
	return frames[frame]


func _fire_events(f: int) -> void:
	var A: Dictionary = _anims.get(anim, {})
	var per: Dictionary = A.get("events", {}).get(facing, {})
	if per.has(f):
		for e in per[f]:
			px_event.emit(anim, e)


func _on_frame_changed() -> void:
	_sync_emissive()
	if _suppress_events:
		return
	_fire_events(frame)


func _on_animation_finished() -> void:
	px_finished.emit(anim)


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
