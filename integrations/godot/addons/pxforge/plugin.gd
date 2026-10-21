@tool
extends EditorPlugin

const MENU := "pxforge: re-escanear assets/pxforge"


func _enter_tree() -> void:
	add_tool_menu_item(MENU, _rescan)


func _exit_tree() -> void:
	remove_tool_menu_item(MENU)


func _rescan() -> void:
	EditorInterface.get_resource_filesystem().scan()
	print("pxforge: filesystem re-escaneado")
