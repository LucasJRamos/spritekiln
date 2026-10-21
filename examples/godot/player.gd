extends CharacterBody2D
## Arrow keys move, Space (or Enter) attacks. KilnSprite2D picks the direction, plays the clips and
## reports the gameplay events written in the spec (step_l/step_r on walk, windup/hit on attack).

const SPEED := 60.0
const Spark := preload("res://spark.gd")

@onready var sprite: KilnSprite2D = $Gargula


func _ready() -> void:
	sprite.anim_event.connect(_on_anim_event)
	sprite.anim_finished.connect(func(_anim): sprite.play_anim(&"idle"))


func _physics_process(_delta: float) -> void:
	var attacking := sprite.anim == &"attack" and sprite.is_playing()
	var input := Input.get_vector(&"ui_left", &"ui_right", &"ui_up", &"ui_down")
	velocity = Vector2.ZERO if attacking else input * SPEED
	move_and_slide()
	if attacking:
		return
	if Input.is_action_just_pressed(&"ui_accept"):
		sprite.play_anim(&"attack", true)
	elif input:
		sprite.face(input)  # nearest of the 8 exported directions
		sprite.play_anim(&"walk")
	else:
		sprite.play_anim(&"idle")


func _on_anim_event(_anim: StringName, event: StringName) -> void:
	if event != &"hit":
		return
	var at := sprite.get_socket(&"strike")  # where the blow lands in this frame and direction
	if at != Vector2.INF:
		var spark := Spark.new()
		spark.position = sprite.to_global(at)
		get_parent().add_child(spark)
