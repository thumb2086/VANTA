class_name CharacterGeneratorV2
extends RefCounted

## Valorant-style procedural character generator — 45 mesh parts
## 总高度 ~1.75m，解剖學正確四肢比例
##
## 使用方式：
##   var gen = CharacterGeneratorV2.new()
##   var character = gen.generate(team_id, "duelist")
##   add_child(character)

const TEAM_COLORS := {
	0: Color(0.95, 0.35, 0.30),
	1: Color(0.30, 0.55, 0.95),
}

const SKIN_COLOR := Color(0.78, 0.65, 0.55)
const DARK_FABRIC := Color(0.15, 0.16, 0.19)
const JOINT_COLOR := Color(0.25, 0.26, 0.30)

# ── 比例常數（米） ──
const H := 1.75          # 總高度
const HEAD_R := 0.10
const HEAD_Y := 1.64
const NECK_R := 0.038
const NECK_H := 0.055
const NECK_Y := 1.56

# 軀幹
const CHEST_W := 0.34
const CHEST_H := 0.28
const CHEST_D := 0.19
const CHEST_Y := 1.32
const ABDOMEN_W := 0.30
const ABDOMEN_H := 0.18
const ABDOMEN_D := 0.17
const ABDOMEN_Y := 1.10

# 肩
const SHOULDER_Y := 1.44
const SHOULDER_SPREAD := 0.21

# 臂
const UPPER_ARM_LEN := 0.27
const UPPER_ARM_R := 0.045
const ELBOW_R := 0.038
const FOREARM_LEN := 0.25
const FOREARM_R := 0.040
const WRIST_R := 0.032
const HAND_W := 0.065
const HAND_H := 0.08
const HAND_D := 0.035

# 腿
const HIP_Y := 1.00
const HIP_SPREAD := 0.11
const UPPER_LEG_LEN := 0.38
const UPPER_LEG_R := 0.065
const KNEE_R := 0.050
const SHIN_LEN := 0.36
const SHIN_R := 0.050
const ANKLE_R := 0.035
const FOOT_W := 0.09
const FOOT_H := 0.05
const FOOT_LEN := 0.14

# 細節
const BELT_H := 0.045
const COLLAR_H := 0.04
const BACKPACK_W := 0.22
const BACKPACK_H := 0.24
const BACKPACK_D := 0.08


func generate(team_id: int, _agent_key: String = "") -> Node3D:
	var root := Node3D.new()
	root.name = "Character"

	var col: Color = TEAM_COLORS.get(team_id, TEAM_COLORS[0])
	var accent := col.darkened(0.40)
	var highlight := col.lightened(0.25)
	var dark_armor := accent.darkened(0.20)
	var skin := SKIN_COLOR

	# ═══════════════════ 頭部（5 parts） ═══════════════════
	_add_sphere(root, HEAD_R, skin, "Head", Vector3(0, HEAD_Y, 0))

	# 遮陽板
	_add_box(root, Vector3(0.15, 0.035, 0.025), highlight, "Visor",
		Vector3(0, HEAD_Y + 0.015, HEAD_R * 0.88))

	# 左耳
	_add_box(root, Vector3(0.015, 0.04, 0.035), dark_armor, "EarL",
		Vector3(-HEAD_R * 0.95, HEAD_Y + 0.01, 0))

	# 右耳
	_add_box(root, Vector3(0.015, 0.04, 0.035), dark_armor, "EarR",
		Vector3(HEAD_R * 0.95, HEAD_Y + 0.01, 0))

	# 下巴 / 下顎
	_add_box(root, Vector3(0.09, 0.035, 0.04), skin.darkened(0.12), "Jaw",
		Vector3(0, HEAD_Y - HEAD_R * 0.6, HEAD_R * 0.45))

	# ═══════════════════ 脖子（1 part） ═══════════════════
	_add_cyl(root, NECK_R, NECK_H, skin.darkened(0.08), "Neck",
		Vector3(0, NECK_Y, 0))

	# ═══════════════════ 軀幹（7 parts） ═══════════════════
	# 胸甲
	_add_box(root, Vector3(CHEST_W, CHEST_H, CHEST_D), col, "Chest",
		Vector3(0, CHEST_Y, 0))

	# 胸甲板（前凸起）
	_add_box(root, Vector3(CHEST_W * 0.55, CHEST_H * 0.35, 0.025), accent, "ChestPlate",
		Vector3(0, CHEST_Y + 0.04, CHEST_D * 0.52))

	# 腹部
	_add_box(root, Vector3(ABDOMEN_W, ABDOMEN_H, ABDOMEN_D), col.darkened(0.10), "Abdomen",
		Vector3(0, ABDOMEN_Y, 0))

	# 背板
	_add_box(root, Vector3(CHEST_W * 0.7, CHEST_H * 0.8, 0.02), accent.darkened(0.15), "BackPlate",
		Vector3(0, CHEST_Y, -CHEST_D * 0.52))

	# 腰帶
	_add_box(root, Vector3(ABDOMEN_W + 0.02, BELT_H, ABDOMEN_D + 0.015), dark_armor, "Belt",
		Vector3(0, ABDOMEN_Y - ABDOMEN_H * 0.45, 0))

	# 衣領
	_add_box(root, Vector3(CHEST_W * 0.6, COLLAR_H, CHEST_D * 0.5), accent, "Collar",
		Vector3(0, CHEST_Y + CHEST_H * 0.52, 0))

	# 背包模組
	_add_box(root, Vector3(BACKPACK_W, BACKPACK_H, BACKPACK_D), accent.darkened(0.25), "Backpack",
		Vector3(0, CHEST_Y + 0.02, -CHEST_D * 0.5 - BACKPACK_D * 0.5))

	# ═══════════════════ 頸甲（1 part） ═══════════════════
	_add_box(root, Vector3(NECK_R * 3.0, NECK_H * 0.8, NECK_R * 3.0), dark_armor, "NeckGuard",
		Vector3(0, NECK_Y + NECK_H * 0.1, 0))

	# ═══════════════════ 手臂（12 parts = 6 × 2） ═══════════════════
	_build_arm(root, -1, col, accent, highlight, dark_armor, skin)
	_build_arm(root, 1, col, accent, highlight, dark_armor, skin)

	# ═══════════════════ 腿部（12 parts = 6 × 2） ═══════════════════
	_build_leg(root, -1, accent, dark_armor)
	_build_leg(root, 1, accent, dark_armor)

	return root


func _build_arm(root: Node3D, side: int, col: Color, accent: Color,
		highlight: Color, dark_armor: Color, skin: Color) -> void:
	var s := "L" if side < 0 else "R"
	var x := SHOULDER_SPREAD * side

	# 肩甲（帶發光）
	var shoulder_pad := _add_sphere(root, 0.06, accent, "ShoulderPad" + s,
		Vector3(x, SHOULDER_Y, 0))
	_set_emission(shoulder_pad, highlight, 1.5)

	# 上臂
	_add_cyl(root, UPPER_ARM_R, UPPER_ARM_LEN, col, "UpperArm" + s,
		Vector3(x, SHOULDER_Y - UPPER_ARM_LEN * 0.5, 0))

	# 肘關節
	var elbow_y := SHOULDER_Y - UPPER_ARM_LEN
	_add_sphere(root, ELBOW_R, JOINT_COLOR, "Elbow" + s,
		Vector3(x, elbow_y, 0))

	# 前臂
	_add_cyl(root, FOREARM_R, FOREARM_LEN, col.darkened(0.08), "Forearm" + s,
		Vector3(x, elbow_y - FOREARM_LEN * 0.5, 0))

	# 前臂護甲
	_add_box(root, Vector3(FOREARM_R * 2.5, FOREARM_LEN * 0.4, FOREARM_R * 2.0),
		dark_armor, "ForearmGuard" + s,
		Vector3(x, elbow_y - FOREARM_LEN * 0.45, FOREARM_R * 1.2))

	# 腕關節
	var wrist_y := elbow_y - FOREARM_LEN
	_add_sphere(root, WRIST_R, JOINT_COLOR, "Wrist" + s,
		Vector3(x, wrist_y, 0))

	# 手
	_add_box(root, Vector3(HAND_W, HAND_H, HAND_D), skin, "Hand" + s,
		Vector3(x, wrist_y - HAND_H * 0.5, 0))


func _build_leg(root: Node3D, side: int, accent: Color, dark_armor: Color) -> void:
	var s := "L" if side < 0 else "R"
	var x := HIP_SPREAD * side

	# 髖關節
	_add_sphere(root, KNEE_R * 0.9, JOINT_COLOR, "Hip" + s,
		Vector3(x, HIP_Y, 0))

	# 大腿
	_add_cyl(root, UPPER_LEG_R, UPPER_LEG_LEN, accent, "UpperLeg" + s,
		Vector3(x, HIP_Y - UPPER_LEG_LEN * 0.5, 0))

	# 膝蓋
	var knee_y := HIP_Y - UPPER_LEG_LEN
	var knee_pad := _add_sphere(root, KNEE_R, dark_armor, "KneePad" + s,
		Vector3(x, knee_y, KNEE_R * 0.6))
	_set_emission(knee_pad, accent, 1.2)

	# 膝蓋護板
	_add_box(root, Vector3(KNEE_R * 2.2, KNEE_R * 1.8, KNEE_R * 1.5),
		dark_armor, "KneeGuard" + s,
		Vector3(x, knee_y, KNEE_R * 1.2))

	# 脛骨
	_add_cyl(root, SHIN_R, SHIN_LEN, accent.darkened(0.12), "Shin" + s,
		Vector3(x, knee_y - SHIN_LEN * 0.5, 0))

	# 踝關節
	var ankle_y := knee_y - SHIN_LEN
	_add_sphere(root, ANKLE_R, JOINT_COLOR, "Ankle" + s,
		Vector3(x, ankle_y, 0))

	# 腳
	_add_box(root, Vector3(FOOT_W, FOOT_H, FOOT_LEN),
		accent.darkened(0.30), "Foot" + s,
		Vector3(x, ankle_y + FOOT_H * 0.5, FOOT_LEN * 0.3))


func generate_and_add(parent: Node3D, team_id: int, agent_key: String = "") -> Node3D:
	var c := generate(team_id, agent_key)
	parent.add_child(c)
	return c


func print_tree(root: Node3D, indent: String = "") -> void:
	for child in root.get_children():
		var pos := child.position
		print("%s[%s] %s  pos=(%.2f, %.2f, %.2f)" % [
			indent, child.get_class(), child.name, pos.x, pos.y, pos.z
		])
		if child is Node3D:
			print_tree(child, indent + "  ")


# ─── 內部工具 ────────────────────────────────────────────

func _add_sphere(root: Node3D, radius: float, color: Color,
		part_name: String, pos: Vector3) -> MeshInstance3D:
	var m := MeshInstance3D.new()
	m.name = part_name
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2.0
	mesh.radial_segments = 16
	mesh.rings = 12
	m.mesh = mesh
	m.material_override = _make_mat(color)
	m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	m.position = pos
	root.add_child(m)
	return m


func _add_cyl(root: Node3D, radius: float, height: float, color: Color,
		part_name: String, pos: Vector3) -> MeshInstance3D:
	var m := MeshInstance3D.new()
	m.name = part_name
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mesh.radial_segments = 12
	m.mesh = mesh
	m.material_override = _make_mat(color)
	m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	m.position = pos
	root.add_child(m)
	return m


func _add_box(root: Node3D, size: Vector3, color: Color,
		part_name: String, pos: Vector3) -> MeshInstance3D:
	var m := MeshInstance3D.new()
	m.name = part_name
	var mesh := BoxMesh.new()
	mesh.size = size
	m.mesh = mesh
	m.material_override = _make_mat(color)
	m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	m.position = pos
	root.add_child(m)
	return m


func _make_mat(color: Color) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.65
	mat.metallic = 0.1
	return mat


func _set_emission(node: MeshInstance3D, color: Color, energy: float) -> void:
	var mat: StandardMaterial3D = node.material_override
	if mat:
		mat.emission_enabled = true
		mat.emission = color
		mat.emission_energy_multiplier = energy
