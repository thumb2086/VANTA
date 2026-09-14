class_name PlayerRig
extends Node3D

## 第三人稱程序化角色骨架（無外部模型/動畫）：
## 頭 + 軀幹 + 四肢，由快照狀態驅動程序化動作：
##   * 步態擺動（腿依速度正弦擺動、手臂反相）
##   * 蹲伏（降低姿態） / 跳躍（收腿）/ 落地緩衝
##   * 死亡（倒下 + 變暗）

const TEAM_COLORS := {
	0: Color(0.95, 0.35, 0.30),
	1: Color(0.30, 0.55, 0.95)
}

var team := 0
var _torso: MeshInstance3D
var _head: MeshInstance3D
var _leg_l: MeshInstance3D
var _leg_r: MeshInstance3D
var _arm_l: MeshInstance3D
var _arm_r: MeshInstance3D
var _bob := 0.0
var _fall := 0.0
var _last_speed := 0.0


func build(team_id: int) -> void:
	team = team_id
	var col: Color = TEAM_COLORS[team]
	var dark := col.darkened(0.35)
	var skin := Color(0.78, 0.65, 0.55)

	_torso = _part(Vector3(0.32, 0.42, 0.22), col, Vector3(0, 0.82, 0))
	# 護甲肩
	var shoulder_l := _part(Vector3(0.14, 0.08, 0.18), dark, Vector3(-0.2, 1.05, 0))
	var shoulder_r := _part(Vector3(0.14, 0.08, 0.18), dark, Vector3(0.2, 1.05, 0))
	_head = _part(Vector3(0.24, 0.24, 0.24), skin, Vector3(0, 1.35, 0))
	var visor := _part(Vector3(0.26, 0.07, 0.05), col.lightened(0.3), Vector3(0, 1.4, 0.09))
	_leg_l = _part(Vector3(0.14, 0.7, 0.16), dark, Vector3(-0.11, 0.35, 0))
	_leg_r = _part(Vector3(0.14, 0.7, 0.16), dark, Vector3(0.11, 0.35, 0))
	_arm_l = _part(Vector3(0.11, 0.62, 0.12), col, Vector3(-0.23, 0.85, 0))
	_arm_r = _part(Vector3(0.11, 0.62, 0.12), col, Vector3(0.23, 0.85, 0))


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
	if not alive:
		_fall = minf(1.0, _fall + dt * 2.0)
		rotation.x = -PI * 0.5 * _fall          # 倒地
		scale = Vector3(1.0, lerpf(scale.y, 0.4, 1.0 - exp(-8.0 * dt)), 1.0)
		return
	# 步態相位
	if speed > 0.2 and on_ground:
		_bob += dt * (6.0 + speed * 1.4)
	var amp := clampf(speed / 5.4, 0.0, 1.0)
	var swing := sin(_bob) * 0.7 * amp
	var lunge := maxf(0.0, -sin(_bob)) * 0.12 * amp

	# 腿擺動（樞軸在髖部）
	_leg_l.rotation.x = swing
	_leg_r.rotation.x = -swing
	_leg_l.position.y = 0.35 - absf(swing) * 0.12 + lunge
	_leg_r.position.y = 0.35 - absf(swing) * 0.12 - lunge
	# 手臂反相
	_arm_l.rotation.x = -swing * 0.6
	_arm_r.rotation.x = swing * 0.6

	# 姿態：蹲伏降低 / 跳躍收腿
	var crouch_off := 0.42 if crouch else 0.0
	var air_tuck := 0.15 if not on_ground else 0.0
	var base_y := 0.0
	_torso.position.y = 0.82 - crouch_off
	_head.position.y = 1.35 - crouch_off
	_leg_l.position.y = 0.35 - crouch_off * 0.5 - air_tuck
	_leg_r.position.y = 0.35 - crouch_off * 0.5 - air_tuck
	_arm_l.position.y = 0.85 - crouch_off
	_arm_r.position.y = 0.85 - crouch_off
	if not on_ground:
		_leg_l.rotation.x = -0.5        # 空中收腿姿
		_leg_r.rotation.x = 0.3

	_last_speed = speed
