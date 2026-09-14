class_name CharacterGenerator
extends RefCounted

## 程序化人形角色生成器
## 替代 player_rig.gd 的方塊骨架，使用更真實的人體比例
## 總高度 ~1.8m（標準 FPS 角色高度）
##
## 使用方式：
##   var gen = CharacterGenerator.new()
##   var character = gen.generate(team_id)
##   add_child(character)

const TEAM_COLORS := {
	0: Color(0.95, 0.35, 0.30),
	1: Color(0.30, 0.55, 0.95),
}

const SKIN_COLOR := Color(0.78, 0.65, 0.55)

## 人體比例常數（米）
const TOTAL_HEIGHT := 1.80
const HEAD_RADIUS := 0.105
const HEAD_Y := 1.68
const NECK_HEIGHT := 0.06
const NECK_Y := 1.58
const TORSO_WIDTH := 0.34
const TORSO_HEIGHT := 0.44
const TORSO_DEPTH := 0.20
const TORSO_Y := 1.25
const SHOULDER_Y := 1.45
const UPPER_ARM_LEN := 0.28
const LOWER_ARM_LEN := 0.26
const HAND_RADIUS := 0.045
const UPPER_LEG_LEN := 0.40
const LOWER_LEG_LEN := 0.38
const FOOT_LEN := 0.13
const FOOT_HEIGHT := 0.06
const HIP_Y := 1.03


func generate(team_id: int) -> Node3D:
	var root := Node3D.new()
	root.name = "Character"

	var col: Color = TEAM_COLORS.get(team_id, TEAM_COLORS[0])
	var accent := col.darkened(0.40)
	var highlight := col.lightened(0.25)

	# ── 頭部 ──
	var head := _make_sphere(HEAD_RADIUS, SKIN_COLOR, "Head")
	head.position = Vector3(0, HEAD_Y, 0)
	root.add_child(head)

	# 遮陽板 / 面罩
	var visor := _make_box(Vector3(0.16, 0.04, 0.03), highlight, "Visor")
	visor.position = Vector3(0, HEAD_Y + 0.02, HEAD_RADIUS * 0.85)
	root.add_child(visor)

	# ── 脖子 ──
	var neck := _make_cylinder(0.04, NECK_HEIGHT, accent, "Neck")
	neck.position = Vector3(0, NECK_Y, 0)
	root.add_child(neck)

	# ── 軀幹 ──
	var torso := _make_box(Vector3(TORSO_WIDTH, TORSO_HEIGHT, TORSO_DEPTH), col, "Torso")
	torso.position = Vector3(0, TORSO_Y, 0)
	root.add_child(torso)

	# 胸甲 / 裝飾線
	var chest_plate := _make_box(
		Vector3(TORSO_WIDTH * 0.6, TORSO_HEIGHT * 0.3, 0.02), accent, "ChestPlate"
	)
	chest_plate.position = Vector3(0, TORSO_Y + 0.08, TORSO_DEPTH * 0.52)
	root.add_child(chest_plate)

	# 腰帶
	var belt := _make_box(
		Vector3(TORSO_WIDTH + 0.02, 0.04, TORSO_DEPTH + 0.01), accent, "Belt"
	)
	belt.position = Vector3(0, TORSO_Y - TORSO_HEIGHT * 0.45, 0)
	root.add_child(belt)

	# ── 上臂（L / R） ──
	var upper_arm_l := _make_cylinder(0.05, UPPER_ARM_LEN, col, "UpperArmL")
	upper_arm_l.position = Vector3(-0.20, SHOULDER_Y - UPPER_ARM_LEN * 0.5, 0)
	root.add_child(upper_arm_l)

	var upper_arm_r := _make_cylinder(0.05, UPPER_ARM_LEN, col, "UpperArmR")
	upper_arm_r.position = Vector3(0.20, SHOULDER_Y - UPPER_ARM_LEN * 0.5, 0)
	root.add_child(upper_arm_r)

	# 肩甲
	var shoulder_pad_l := _make_sphere(0.065, accent, "ShoulderPadL")
	shoulder_pad_l.position = Vector3(-0.20, SHOULDER_Y, 0)
	root.add_child(shoulder_pad_l)

	var shoulder_pad_r := _make_sphere(0.065, accent, "ShoulderPadR")
	shoulder_pad_r.position = Vector3(0.20, SHOULDER_Y, 0)
	root.add_child(shoulder_pad_r)

	# ── 下臂（L / R） ──
	var elbow_y := SHOULDER_Y - UPPER_ARM_LEN

	var lower_arm_l := _make_cylinder(0.042, LOWER_ARM_LEN, col.darkened(0.12), "LowerArmL")
	lower_arm_l.position = Vector3(-0.20, elbow_y - LOWER_ARM_LEN * 0.5, 0)
	root.add_child(lower_arm_l)

	var lower_arm_r := _make_cylinder(0.042, LOWER_ARM_LEN, col.darkened(0.12), "LowerArmR")
	lower_arm_r.position = Vector3(0.20, elbow_y - LOWER_ARM_LEN * 0.5, 0)
	root.add_child(lower_arm_r)

	# 手
	var hand_y := elbow_y - LOWER_ARM_LEN

	var hand_l := _make_sphere(HAND_RADIUS, SKIN_COLOR, "HandL")
	hand_l.position = Vector3(-0.20, hand_y, 0)
	root.add_child(hand_l)

	var hand_r := _make_sphere(HAND_RADIUS, SKIN_COLOR, "HandR")
	hand_r.position = Vector3(0.20, hand_y, 0)
	root.add_child(hand_r)

	# ── 上腿（L / R） ──
	var upper_leg_l := _make_cylinder(0.07, UPPER_LEG_LEN, accent, "UpperLegL")
	upper_leg_l.position = Vector3(-0.10, HIP_Y - UPPER_LEG_LEN * 0.5, 0)
	root.add_child(upper_leg_l)

	var upper_leg_r := _make_cylinder(0.07, UPPER_LEG_LEN, accent, "UpperLegR")
	upper_leg_r.position = Vector3(0.10, HIP_Y - UPPER_LEG_LEN * 0.5, 0)
	root.add_child(upper_leg_r)

	# ── 下腿（L / R） ──
	var knee_y := HIP_Y - UPPER_LEG_LEN

	var lower_leg_l := _make_cylinder(0.055, LOWER_LEG_LEN, accent.darkened(0.15), "LowerLegL")
	lower_leg_l.position = Vector3(-0.10, knee_y - LOWER_LEG_LEN * 0.5, 0)
	root.add_child(lower_leg_l)

	var lower_leg_r := _make_cylinder(0.055, LOWER_LEG_LEN, accent.darkened(0.15), "LowerLegR")
	lower_leg_r.position = Vector3(0.10, knee_y - LOWER_LEG_LEN * 0.5, 0)
	root.add_child(lower_leg_r)

	# 膝甲
	var knee_pad_l := _make_sphere(0.05, col.darkened(0.25), "KneePadL")
	knee_pad_l.position = Vector3(-0.10, knee_y, 0.03)
	root.add_child(knee_pad_l)

	var knee_pad_r := _make_sphere(0.05, col.darkened(0.25), "KneePadR")
	knee_pad_r.position = Vector3(0.10, knee_y, 0.03)
	root.add_child(knee_pad_r)

	# ── 腳 ──
	var foot_y := knee_y - LOWER_LEG_LEN

	var foot_l := _make_box(Vector3(0.09, FOOT_HEIGHT, FOOT_LEN), accent.darkened(0.3), "FootL")
	foot_l.position = Vector3(-0.10, foot_y + FOOT_HEIGHT * 0.5, FOOT_LEN * 0.3)
	root.add_child(foot_l)

	var foot_r := _make_box(Vector3(0.09, FOOT_HEIGHT, FOOT_LEN), accent.darkened(0.3), "FootR")
	foot_r.position = Vector3(0.10, foot_y + FOOT_HEIGHT * 0.5, FOOT_LEN * 0.3)
	root.add_child(foot_r)

	return root


## 便利方法：生成並直接加入父節點
func generate_and_add(parent: Node3D, team_id: int) -> Node3D:
	var c := generate(team_id)
	parent.add_child(c)
	return c


## 印出角色骨架結構（除錯用）
func print_tree(root: Node3D, indent: String = "") -> void:
	for child in root.get_children():
		var pos := child.position
		print("%s[%s] %s  pos=(%.2f, %.2f, %.2f)" % [
			indent, child.get_class(), child.name, pos.x, pos.y, pos.z
		])
		if child is Node3D:
			print_tree(child, indent + "  ")


# ─── 內部：网格建立 ──────────────────────────────────────

func _make_sphere(radius: float, color: Color, part_name: String) -> MeshInstance3D:
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
	return m


func _make_cylinder(radius: float, height: float, color: Color, part_name: String) -> MeshInstance3D:
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
	return m


func _make_box(size: Vector3, color: Color, part_name: String) -> MeshInstance3D:
	var m := MeshInstance3D.new()
	m.name = part_name
	var mesh := BoxMesh.new()
	mesh.size = size
	m.mesh = mesh
	m.material_override = _make_mat(color)
	m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	return m


func _make_mat(color: Color) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.65
	mat.metallic = 0.1
	return mat
