class_name RenderWorld
extends Node3D

## 從「工具鏈產生的地圖 JSON」建構 3D 世界，並渲染/插值所有玩家。

const TEAM_COLORS := {
	0: Color(0.95, 0.35, 0.30),   # 攻方（紅）
	1: Color(0.30, 0.55, 0.95),   # 守方（藍）
}

var _player_nodes := {}
var _player_mats := {}
var _smoke_nodes := {}      # 世界煙霧體積霧節點
var _smoke_spawned_tick := -1


func build_map(map_json: Dictionary) -> void:
	# 使用 MapLoader 載入完整地圖（牆面/站點/出生點/購買區/傳送門/繩索/光照/小地圖）
	if MapLoader:
		var loader := MapLoader.new()
		loader.load_from_json(map_json)
		return
	# Fallback：原始程序化地圖
	_build_map_procedural(map_json)


func _build_map_procedural(map_json: Dictionary) -> void:
	# === 地板（帶格線紋理）===
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.18, 0.20, 0.24)
	floor_mat.roughness = 0.85
	_add_box(Vector3.ZERO, Vector3(200.0, 0.4, 200.0), floor_mat)
	# 地板格線
	var grid_mat := StandardMaterial3D.new()
	grid_mat.albedo_color = Color(0.22, 0.24, 0.28, 0.3)
	for i in range(-50, 51, 5):
		_add_box(Vector3(i, 0.01, 0), Vector3(0.05, 0.02, 100.0), grid_mat)
		_add_box(Vector3(0, 0.01, i), Vector3(100.0, 0.02, 0.05), grid_mat)

	# === 牆面（帶邊框 + 發光標記）===
	for w in map_json["walls"]:
		var mn: Vector3 = _v(w["mn"])
		var mx: Vector3 = _v(w["mx"])
		var size := mx - mn
		var center := mn + size * 0.5
		var mat := StandardMaterial3D.new()
		mat.roughness = 0.7
		match w["material"]:
			"wood":
				mat.albedo_color = Color(0.42, 0.30, 0.18)
				mat.roughness = 0.9
			"concrete":
				mat.albedo_color = Color(0.38, 0.40, 0.44)
				mat.roughness = 0.75
			_:
				mat.albedo_color = Color(0.16, 0.17, 0.20)
		_add_box(center, size, mat)
		# 牆面頂部邊框（白色細線）
		var edge_mat := StandardMaterial3D.new()
		edge_mat.albedo_color = Color(0.5, 0.55, 0.6, 0.4)
		edge_mat.emission_enabled = true
		edge_mat.emission = Color(0.3, 0.35, 0.4)
		_add_box(Vector3(center.x, mn.y + size.y, center.z),
			Vector3(size.x + 0.05, 0.04, size.z + 0.05), edge_mat)

	# === Spike 點位標記（發光地板 + 標籤）===
	for s in map_json["sites"]:
		var c: Vector3 = _v(s["center"])
		# 發光地板
		var site_mat := StandardMaterial3D.new()
		site_mat.albedo_color = Color(0.8, 0.2, 0.2)
		site_mat.emission_enabled = true
		site_mat.emission = Color(0.9, 0.3, 0.3)
		site_mat.emission_energy_multiplier = 2.0
		var marker := MeshInstance3D.new()
		var mesh := BoxMesh.new()
		mesh.size = Vector3(4.0, 0.06, 4.0)
		marker.mesh = mesh
		marker.material_override = site_mat
		marker.position = c + Vector3(0, 0.04, 0)
		add_child(marker)
		# 外框
		var frame_mat := StandardMaterial3D.new()
		frame_mat.albedo_color = Color(0.9, 0.3, 0.3)
		frame_mat.emission_enabled = true
		frame_mat.emission = Color(0.9, 0.3, 0.3)
		frame_mat.emission_energy_multiplier = 1.5
		_add_box(Vector3(c.x, 0.04, c.z - 2.2), Vector3(4.4, 0.08, 0.1), frame_mat)
		_add_box(Vector3(c.x, 0.04, c.z + 2.2), Vector3(4.4, 0.08, 0.1), frame_mat)
		_add_box(Vector3(c.x - 2.2, 0.04, c.z), Vector3(0.1, 0.08, 4.4), frame_mat)
		_add_box(Vector3(c.x + 2.2, 0.04, c.z), Vector3(0.1, 0.08, 4.4), frame_mat)
		# 標籤
		var label := Label3D.new()
		label.text = s["name"]
		label.position = c + Vector3(0, 1.5, 0)
		label.font_size = 72
		label.outline_size = 10
		label.modulate = Color(1.0, 0.4, 0.4)
		add_child(label)

	# === 裝飾物（箱子/桶/柱子）===
	var deco_mat := StandardMaterial3D.new()
	deco_mat.albedo_color = Color(0.35, 0.32, 0.28)
	deco_mat.roughness = 0.8
	# 角落柱子
	for pos in [Vector2(-20, -20), Vector2(20, -20), Vector2(-20, 20), Vector2(20, 20)]:
		_add_box(Vector3(pos.x, 2.0, pos.y), Vector3(1.0, 4.0, 1.0), deco_mat)
	# 中央掩體
	var cover_mat := StandardMaterial3D.new()
	cover_mat.albedo_color = Color(0.30, 0.32, 0.36)
	cover_mat.roughness = 0.7
	_add_box(Vector3(0, 0.6, 0), Vector3(3.0, 1.2, 3.0), cover_mat)
	_add_box(Vector3(6, 0.4, -4), Vector3(2.0, 0.8, 1.5), cover_mat)
	_add_box(Vector3(-6, 0.4, 4), Vector3(1.5, 0.8, 2.0), cover_mat)

	# === 天花板（半透明，讓光線穿透）===
	var ceil_mat := StandardMaterial3D.new()
	ceil_mat.albedo_color = Color(0.12, 0.14, 0.18, 0.6)
	ceil_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_add_box(Vector3(0, 8.0, 0), Vector3(60.0, 0.3, 60.0), ceil_mat)


func spawn_players() -> void:
	for i in range(10):
		var team := 0 if i < 5 else 1
		var rig := PlayerRig.new()
		rig.build(team, i)
		# 名牌
		var tag := Label3D.new()
		tag.text = "P%d" % i
		tag.font_size = 36
		tag.outline_size = 6
		tag.position = Vector3(0, 1.15, 0)
		tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		rig.add_child(tag)
		add_child(rig)
		_player_nodes[i] = rig


func update_players(net: NetClient, own_slot: int, own_pos: Vector3, dt: float) -> void:
	for i in range(10):
		var rig: PlayerRig = _player_nodes.get(i)
		if rig == null:
			continue
		var snap: Dictionary = net.players.get(i, {})
		if snap.is_empty():
			rig.visible = false
			continue
		# 第一人稱：自己的角色模型不顯示（避免穿模看到頭頂）
		if i == own_slot:
			rig.visible = false
			continue
		rig.visible = true
		var target: Vector3 = snap["pos"]
		var cur: Vector3 = rig.position
		var rate := 14.0
		rig.position = cur.lerp(target, 1.0 - exp(-rate * dt))
		# 隊友朝向：根據速度向量旋轉角色面朝方向
		var vel_vec: Vector3 = snap.get("vel", Vector3.ZERO)
		if vel_vec.length() > 0.5:
			var look_target := rig.position + Vector3(vel_vec.x, 0, vel_vec.z)
			look_target.y = rig.position.y
			rig.look_at(look_target, Vector3.UP)
		var hp: int = snap.get("health", 100)
		var speed: float = snap.get("vel", Vector3.ZERO).length()
		# 程序化動作：步態 / 蹲伏 / 跳躍 / 死亡
		rig.update_anim(dt, speed, snap.get("on_ground", true),
			snap.get("crouch", false), hp > 0)
	# 同步更新煙霧
	update_smokes(net)


func _add_box(center: Vector3, size: Vector3, mat: Material) -> void:
	var body := StaticBody3D.new()
	body.position = center
	var col := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	col.shape = shape
	body.add_child(col)
	var mesh_node := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	mesh_node.mesh = mesh
	mesh_node.material_override = mat
	body.add_child(mesh_node)
	add_child(body)


func _v(d) -> Vector3:
	return Vector3(d["x"], d["y"], d["z"])


## ── 體積霧煙霧渲染 ──────────────────────────────
func update_smokes(net: NetClient) -> void:
	# 對比伺服器煙霧列表 → 增删/移動本地煙霧節點
	var server_list: Array = net.world_smokes
	var alive_keys := {}
	for i in range(server_list.size()):
		var s: Dictionary = server_list[i]
		var pos: Vector3 = s["pos"]
		var radius: float = s.get("radius", 3.5)
		var time_left: float = s.get("time_left", 0.0)
		var key := "%d_%.1f_%.1f_%.1f" % [i, pos.x, pos.y, pos.z]
		alive_keys[key] = true
		if not _smoke_nodes.has(key):
			var node := _build_smoke_node(pos, radius)
			_smoke_nodes[key] = node
			add_child(node)
		else:
			# 更新位置/半徑（煙霧靜止，但淡出管理）
			var n: Node3D = _smoke_nodes[key]
			if is_instance_valid(n):
				n.position = pos
				# 漸層淡出：最後 2 秒 alpha 遞减
				var mat: StandardMaterial3D = n.get_child(0).material_override
				if mat:
					if time_left < 2.0 and time_left > 0.0:
						mat.albedo_color.a = lerpf(0.0, 0.85, time_left / 2.0)
						mat.emission_energy_multiplier = lerpf(0.0, 0.3, time_left / 2.0)
					else:
						mat.albedo_color.a = 0.85
						mat.emission_energy_multiplier = 0.3
	# 移除已消失的煙霧
	for key in _smoke_nodes.keys():
		if not alive_keys.has(key):
			var n: Node3D = _smoke_nodes[key]
			if is_instance_valid(n):
				n.queue_free()
			_smoke_nodes.erase(key)


func _build_smoke_node(center: Vector3, radius: float) -> Node3D:
	"""建立一個體積霧煙霧節點：球狀网格 + 半透明發光材質。

	特戰式煙霧：邊緣柔和漸層 + 内部不透明 + 微微發光（讓穿過的槍火閃光更亮）。
	"""
	var node := Node3D.new()
	node.position = center
	# 主球體（大、半透明）
	var main_mesh := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = radius
	sphere.height = radius * 2.0
	main_mesh.mesh = sphere
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.62, 0.64, 0.68, 0.85)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.emission_enabled = true
	mat.emission = Color(0.7, 0.72, 0.75)
	mat.emission_energy_multiplier = 0.3
	mat.no_depth_test = true
	main_mesh.material_override = mat
	node.add_child(main_mesh)
	# 外層柔化球（更大、更透明，讓邊緣柔和）
	var halo_mesh := MeshInstance3D.new()
	var halo_sphere := SphereMesh.new()
	halo_sphere.radius = radius * 1.3
	halo_sphere.height = radius * 2.6
	halo_mesh.mesh = halo_sphere
	var halo_mat := StandardMaterial3D.new()
	halo_mat.albedo_color = Color(0.58, 0.60, 0.63, 0.35)
	halo_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	halo_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	halo_mat.no_depth_test = true
	halo_mesh.material_override = halo_mat
	node.add_child(halo_mesh)
	return node
