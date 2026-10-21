extends Node2D
## A short flash spawned on the `hit` event at the `strike` socket.

const LIFE := 0.2

var _t := 0.0


func _ready() -> void:
	z_index = 10


func _process(delta: float) -> void:
	_t += delta
	if _t >= LIFE:
		queue_free()
	queue_redraw()


func _draw() -> void:
	var k := 1.0 - _t / LIFE
	draw_circle(Vector2.ZERO, 1.5 + 5.0 * (1.0 - k), Color(1.0, 0.8, 0.4, k))
