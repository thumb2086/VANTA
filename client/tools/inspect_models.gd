extends SceneTree

func _init() -> void:
	var spike := load("res://assets/weapons_models/Spike.fbx")
	if spike is PackedScene:
		var inst: Node = spike.instantiate()
		print("SPIKE root: ", inst.name)
		var c: Node3D = inst
		print("bounds: ", c.get_aabb())
		inst.free()
	else:
		print("SPIKE type: ", typeof(spike), " value: ", spike)
	var knife := load("res://assets/weapons_models/knife.obj")
	print("KNIFE type: ", typeof(knife), " is Mesh: ", knife is Mesh)
	quit()