class_name PlayerRig
extends Node3D

## 第三人稱角色骨架：
##   模式 A（預設）：載入 .glb 模型 + Skeleton3D + AnimationPlayer
##   模式 B（fallback）：程序化骨架
##     - 優先 CharacterGeneratorV2（45 部位 Valorant 品質）
##     - 回退 CharacterGenerator（20 部位）
##     - 最終回退方塊骨架
##
## .glb 模型放在 res://assets/characters/ 目錄下

const TEAM_COLORS := {
	0: Color(0.95, 0.35, 0.30),
	1: Color(0.30, 0.55, 0.95)
}

var team := 0
var _bob := 0.0
var _fall := 0.0
var _last_speed := 0.0

# GLB 模式
var _glb_model: Node3D = null
var _anim_player: AnimationPlayer = null
var _skeleton: Skeleton3D = null
var _use_glb := false

# 程序化模式
var _use_v2 := false
var _anim_ctrl: AnimationController = null

# 舊版 fallback 引用（方塊骨架）
var _torso: MeshInstance3D
var _head: MeshInstance3D
var _leg_l: MeshInstance3D
var _leg_r: MeshInstance3D
var _arm_l: MeshInstance3D
var _arm_r: MeshInstance3D

# GLB 動畫名稱映射
var _anim_idle: String = "Idle"
var _anim_run: String = "Run"
var _anim_walk: String = "Walk"
var _anim_crouch: String = "Crouch"
var _anim_jump: String = "Jump"
var _anim_death: String = "Death"
var _anim_shoot: String = "Shoot"
var _anim_reload: String = "Reload"


func build(team_id: int, slot: int = -1) -> void:
	team = team_id
	if _try_load_glb(team_id, slot):
		_use_glb = true
		return
	_use_glb = false
	_build_procedural(team_id)


func _try_load_glb(team_id: int, slot: int) -> bool:
	var paths := [
		"res://assets/characters/char_%d_%d.glb" % [team_id, slot],
		"res://assets/characters/char_%d.glb" % team_id,
		"res://assets/characters/char_default.glb",
	]
	for path in paths:
		if ResourceLoader.exists(path):
			var scene: PackedScene = load(path)
			if scene:
				_glb_model = scene.instantiate()
				add_child(_glb_model)
				_anim_player = _find_node(_glb_model, AnimationPlayer)
				_skeleton = _find_node(_glb_model, Skeleton3D)
				if _skeleton:
					for child in _skeleton.get_children():
						if child is MeshInstance3D:
							child.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
				return true
	return false


func _find_node(root: Node, type) -> Node:
	for child in root.get_children():
		if child is type:
			return child
		var found = _find_node(child, type)
		if found:
			return found
	return null


func _build_procedural(team_id: int) -> void:
	# Priority 1: CharacterGeneratorV2 (45-part Valorant quality)
	if CharacterGeneratorV2:
		var gen := CharacterGeneratorV2.new()
		var model := gen.generate(team_id)
		for child in model.get_children():
			model.remove_child(child)
			add_child(child)
		model.queue_free()
		_use_v2 = true
		# Set up AnimationController for v2 rig
		_anim_ctrl = AnimationController.new()
		_anim_ctrl.bind(self)
		return

	# Priority 2: CharacterGenerator (20-part)
	if CharacterGenerator:
		var gen := CharacterGenerator.new()
		var model := gen.generate(team_id)
		for child in model.get_children():
			model.remove_child(child)
			add_child(child)
		model.queue_free()
		# Set up AnimationController for legacy rig too
		_anim_ctrl = AnimationController.new()
		_anim_ctrl.bind(self)
		return

	# Priority 3: Original box fallback
	_use_v2 = false
	var col: Color = TEAM_COLORS[team_id]
	var dark := col.darkened(0.35)
	var skin := Color(0.78, 0.65, 0.55)

	_torso = _part(Vector3(0.32, 0.42, 0.22), col, Vector3(0, 0.82, 0))
	var shoulder_l := _part(Vector3(0.14, 0.08, 0.18), dark, Vector3(-0.2, 1.05, 0))
	var shoulder_r := _part(Vector3(0.14, 0.08, 0.18), dark, Vector3(0.2, 1.05, 0))
	_head = _part(Vector3(0.24, 0.24, 0.24), skin, Vector3(0, 1.35, 0))
	var visor := _part(Vector3(0.26, 0.07, 0.05), col.lightened(0.3), Vector3(0, 1.4, 0.09))
	_leg_l = _part(Vector3(0.14, 0.7, 0.16), dark, Vector3(-0.11, 0.35, 0))
	_leg_r = _part(Vector3(0.14, 0.7, 0.16), dark, Vector3(0.11, 0.35, 0))
	_arm_l = _part(Vector3(0.11, 0.62, 0.12), col, Vector3(-0.23, 0.85, 0))
	_arm_r = _part(Vector3(0.11, 0.62, 0.12), col, Vector3(0.23, 0.85, 0))


func _find_mesh(target_name: String) -> MeshInstance3D:
	for child in get_children():
		if child.name == target_name and child is MeshInstance3D:
			return child
		var found := _find_mesh_in(child, target_name)
		if found:
			return found
	return null


func _find_mesh_in(node: Node, target_name: String) -> MeshInstance3D:
	for child in node.get_children():
		if child.name == target_name and child is MeshInstance3D:
			return child
		var found := _find_mesh_in(child, target_name)
		if found:
			return found
	return null


func _part(size: Vector3, color: Color, pos: Vector3) -> MeshInstance3D:
	var n := MeshInstance3D.new()
	var m := BoxMesh.new()
	m.size = size
	n.mesh = m
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	n.material_override = mat
	n.position = pos
	add_child(n)
	return n


func update_anim(dt: float, speed: float, on_ground: bool, crouch: bool, alive: bool) -> void:
	if _use_glb:
		_update_glb_anim(dt, speed, on_ground, crouch, alive)
	elif _anim_ctrl and _anim_ctrl.is_bound():
		# V2 or legacy rig with AnimationController
		_anim_ctrl.update(dt, speed, on_ground, crouch, alive)
	else:
		# Original box fallback — inline animation
		_update_box_fallback(dt, speed, on_ground, crouch, alive)


func _update_glb_anim(dt: float, speed: float, on_ground: bool, crouch: bool, alive: bool) -> void:
	if not alive:
		_fall = minf(1.0, _fall + dt * 2.0)
		if _anim_player and _anim_player.has_animation(_anim_death):
			if _anim_player.current_animation != _anim_death:
				_anim_player.play(_anim_death)
		return

	_fall = 0.0

	var target_anim := _anim_idle
	if not on_ground:
		target_anim = _anim_jump
	elif crouch:
		target_anim = _anim_crouch
	elif speed > 0.5:
		target_anim = _anim_run if speed > 3.0 else _anim_walk

	if _anim_player and _anim_player.has_animation(target_anim):
		if _anim_player.current_animation != target_anim:
			_anim_player.play(target_anim)
		_anim_player.speed_scale = clampf(speed / 3.0, 0.5, 1.5) if speed > 0.5 else 1.0

	_last_speed = speed


func _update_box_fallback(dt: float, speed: float, on_ground: bool, crouch: bool, alive: bool) -> void:
	if not alive:
		_fall = minf(1.0, _fall + dt * 2.0)
		rotation.x = -PI * 0.5 * _fall
		scale = Vector3(1.0, lerpf(scale.y, 0.4, 1.0 - exp(-8.0 * dt)), 1.0)
		return
	if speed > 0.2 and on_ground:
		_bob += dt * (6.0 + speed * 1.4)
	var amp := clampf(speed / 5.4, 0.0, 1.0)
	var swing := sin(_bob) * 0.7 * amp
	var lunge := maxf(0.0, -sin(_bob)) * 0.12 * amp

	_leg_l.rotation.x = swing
	_leg_r.rotation.x = -swing
	_leg_l.position.y = 0.35 - absf(swing) * 0.12 + lunge
	_leg_r.position.y = 0.35 - absf(swing) * 0.12 - lunge
	_arm_l.rotation.x = -swing * 0.6
	_arm_r.rotation.x = swing * 0.6

	var crouch_off := 0.42 if crouch else 0.0
	var air_tuck := 0.15 if not on_ground else 0.0
	_torso.position.y = 0.82 - crouch_off
	_head.position.y = 1.35 - crouch_off
	_leg_l.position.y = 0.35 - crouch_off * 0.5 - air_tuck
	_leg_r.position.y = 0.35 - crouch_off * 0.5 - air_tuck
	_arm_l.position.y = 0.85 - crouch_off
	_arm_r.position.y = 0.85 - crouch_off
	if not on_ground:
		_leg_l.rotation.x = -0.5
		_leg_r.rotation.x = 0.3

	_last_speed = speed
