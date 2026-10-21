@tool
extends EditorPlugin
## SpriteKiln editor plugin: builds SpriteFrames and scenes from render JSONs dropped into the project
## (automatically when they are imported, or on demand from Project > Tools).

const MENU_BUILD := "SpriteKiln: build sprites from render JSONs"


func _enter_tree() -> void:
	add_tool_menu_item(MENU_BUILD, build_all)
	var fs := EditorInterface.get_resource_filesystem()
	if not fs.resources_reimported.is_connected(_on_reimported):
		fs.resources_reimported.connect(_on_reimported)


func _exit_tree() -> void:
	remove_tool_menu_item(MENU_BUILD)
	var fs := EditorInterface.get_resource_filesystem()
	if fs.resources_reimported.is_connected(_on_reimported):
		fs.resources_reimported.disconnect(_on_reimported)


## Builds every render JSON under res:// (resources always; a scene only when it does not exist yet).
func build_all() -> void:
	var built := 0
	for path in _find_json("res://"):
		if KilnBuilder.is_sheet(path):
			KilnBuilder.build(path)
			built += 1
	print("SpriteKiln: built %d sprite(s)" % built)
	EditorInterface.get_resource_filesystem().scan()


func _on_reimported(paths: PackedStringArray) -> void:
	for path in paths:
		if path.ends_with(".json") and KilnBuilder.is_sheet(path):
			KilnBuilder.build(path)


func _find_json(dir: String) -> PackedStringArray:
	var out := PackedStringArray()
	var d := DirAccess.open(dir)
	if d == null:
		return out
	for f in d.get_files():
		if f.ends_with(".json"):
			out.append(dir.path_join(f))
	for sub in d.get_directories():
		if not sub.begins_with("."):
			out.append_array(_find_json(dir.path_join(sub)))
	return out
