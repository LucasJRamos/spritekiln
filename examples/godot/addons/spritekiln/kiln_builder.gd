@tool
class_name KilnBuilder
extends RefCounted
## Builds Godot resources from a SpriteKiln render (atlas + JSON) inside the editor, without the CLI:
## <name>.tres (SpriteFrames), <name>_canvas.tres + <name>_lit.tres (normal map for Light2D),
## <name>_emissive.tres and a ready <name>.tscn with a KilnSprite2D. `spritekiln export` writes the same.


## The exporter's block of a render JSON ("spritekiln", or "pxforge" in older files), or {}.
static func block(data) -> Dictionary:
	if not (data is Dictionary):
		return {}
	for key in ["spritekiln", "pxforge"]:
		if data.has(key):
			return data[key]
	return {}


static func read_json(path: String):
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return null
	return JSON.parse_string(f.get_as_text())


## True when `path` is a SpriteKiln render JSON.
static func is_sheet(path: String) -> bool:
	return path.ends_with(".json") and not block(read_json(path)).is_empty()


## SpriteFrames with one animation per "<anim>_<dir>" and the exact duration of every frame.
static func sprite_frames(data: Dictionary, atlas: Texture2D) -> SpriteFrames:
	var sf := SpriteFrames.new()
	sf.remove_animation(&"default")
	var px := block(data)
	var frames: Dictionary = data["frames"]
	var regions := {}
	for a in px["animations"]:
		var A: Dictionary = px["animations"][a]
		for d in A["directions"]:
			var D: Dictionary = A["directions"][d]
			var clip := StringName("%s_%s" % [a, d])
			sf.add_animation(clip)
			sf.set_animation_speed(clip, 1.0)  # durations below are in seconds
			sf.set_animation_loop(clip, bool(A.get("loop", true)))
			for i in D["frames"].size():
				var r: Dictionary = frames[D["frames"][i]]["frame"]
				var key := "%d,%d,%d,%d" % [r["x"], r["y"], r["w"], r["h"]]
				if not regions.has(key):
					var at := AtlasTexture.new()
					at.atlas = atlas
					at.region = Rect2(r["x"], r["y"], r["w"], r["h"])
					regions[key] = at
				sf.add_frame(clip, regions[key], float(D["durations"][i]) / 1000.0)
	return sf


## Writes the resources (and the scene when it does not exist yet) next to the JSON. Returns the paths.
static func build(json_path: String, lit := false, overwrite_scene := false) -> Dictionary:
	var data = read_json(json_path)
	var px := block(data)
	if px.is_empty():
		push_error("SpriteKiln: %s is not a SpriteKiln render" % json_path)
		return {}
	var dir := json_path.get_base_dir()
	var name: String = px.get("name", json_path.get_file().get_basename())
	var atlas: Texture2D = load(dir.path_join(data["meta"]["image"]))
	var out := {}
	var frames := sprite_frames(data, atlas)
	out["frames"] = _save(frames, dir.path_join(name + ".tres"))
	var lit_frames: SpriteFrames = null
	var normal_path := dir.path_join(str(px.get("normal_map", "")))
	if px.has("normal_map") and ResourceLoader.exists(normal_path):
		var ct := CanvasTexture.new()
		ct.diffuse_texture = atlas
		ct.normal_texture = load(normal_path)
		out["canvas"] = _save(ct, dir.path_join(name + "_canvas.tres"))
		lit_frames = sprite_frames(data, load(out["canvas"]))
		out["lit"] = _save(lit_frames, dir.path_join(name + "_lit.tres"))
	var emissive: SpriteFrames = null
	var em_path := dir.path_join(str(px.get("emissive_map", "")))
	if px.has("emissive_map") and ResourceLoader.exists(em_path) and _has_pixels(load(em_path)):
		emissive = sprite_frames(data, load(em_path))
		out["emissive"] = _save(emissive, dir.path_join(name + "_emissive.tres"))
	var scene_path := dir.path_join(name + ".tscn")
	if overwrite_scene or not ResourceLoader.exists(scene_path):
		var node := KilnSprite2D.new()
		node.name = name
		node.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		node.sprite_frames = load(out["lit"]) if lit and out.has("lit") else load(out["frames"])
		node.sheet = load(json_path)
		if emissive:
			node.emissive_frames = load(out["emissive"])
		var anims: Array = px["animations"].keys()
		node.anim = &"idle" if anims.has("idle") else StringName(anims[0])
		node.facing = StringName(px["directions"][0])
		var scene := PackedScene.new()
		scene.pack(node)
		out["scene"] = _save(scene, scene_path)
		node.free()
	return out


static func _save(res: Resource, path: String) -> String:
	var err := ResourceSaver.save(res, path)
	if err != OK:
		push_error("SpriteKiln: cannot save %s (error %d)" % [path, err])
	res.take_over_path(path)
	return path


static func _has_pixels(tex: Texture2D) -> bool:
	if tex == null:
		return false
	var img := tex.get_image()
	if img == null:
		return false
	return img.get_used_rect().size != Vector2i.ZERO
