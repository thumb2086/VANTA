class_name MapLoader
extends Node3D

## Reads tool-chain generated map JSON (generator.py / map_generator.gd format)
## and constructs the full 3D world: walls, sites, spawns, buy zones,
## teleporters, ropes, ambient lighting, and a minimap camera.

const WALL_HEIGHT_DEFAULT := 4.0
const SITE_GLOW_COLOR := Color(0.9, 0.25, 0.25)
const SPAWN_ATK_COLOR := Color(0.20, 0.55, 0.95)
const SPAWN_DEF_COLOR := Color(0.95, 0.60, 0.20)
const BUY_ZONE_ALPHA := 0.22

var _walls: Array = []
var _sites: Array = []
var _spawns_a: Array = []
var _spawns_d: Array = []
var _buy_atk: Array = []
var _buy_def: Array = []
var _teleporters: Array = []
var _ropes: Array = []
var _bounds_min := Vector3.ZERO
var _bounds_max := Vector3.ZERO


func load_from_json(map_data: Dictionary) -> void:
	_parse_bounds(map_data)
	_walls = map_data.get("walls", [])
	_sites = map_data.get("sites", [])
	_spawns_a = map_data.get("spawns_attackers", [])
	_spawns_d = map_data.get("spawns_defenders", [])
	_buy_atk = _parse_buy_zone(map_data.get("buy_zone_attackers", []))
	_buy_def = _parse_buy_zone(map_data.get("buy_zone_defenders", []))
	_teleporters = map_data.get("teleporters", [])
	_ropes = map_data.get("ropes", [])

	_build_floor()
	_build_walls()
	_build_sites()
	_build_spawn_markers()
	_build_buy_zones()
	_build_teleporters()
	_build_ropes()
	_build_ceiling()
	_build_ambient_light()
	_build_minimap_camera()


func load_from_file(path: String) -> void:
	var f := FileAccess.open(path, FileAccess.READ)
	if not f:
		push_error("MapLoader: cannot open %s" % path)
		return
	var json := JSON.new()
	var err := json.parse(f.get_as_text())
	if err != OK:
		push_error("MapLoader: JSON parse error in %s: %s" % [path, json.get_error_message()])
		return
	load_from_json(json.data)
	f.close()


# ── Bounds ──────────────────────────────────────

func _parse_bounds(d: Dictionary) -> void:
	_bounds_min = _v(d.get("bounds_min", {"x": -20, "y": 0, "z": -20}))
	_bounds_max = _v(d.get("bounds_max", {"x": 20, "y": 12, "z": 20}))


func _parse_buy_zone(data) -> Array:
	# buy_zone format: [{x,y,z}, {x,y,z}] two corners of AABB, or [] for none
	if data is Array and data.size() >= 2:
		return [_v(data[0]), _v(data[1])]
	return []


# ── Floor ───────────────────────────────────────

func _build_floor() -> void:
	var bmin := _bounds_min
	var bmax := _bounds_max
	var center := (bmin + bmax) * 0.5
	var span := bmax - bmin

	# Main floor
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.14, 0.16, 0.20)
	floor_mat.roughness = 0.9
	_add_static_box(Vector3(center.x, -0.2, center.z), Vector3(span.x, 0.4, span.z), floor_mat)

	# Grid lines (5-unit spacing)
	var grid_mat := StandardMaterial3D.new()
	grid_mat.albedo_color = Color(0.18, 0.20, 0.24, 0.25)
	var half := span.x * 0.5
	var step := 5.0
	var i := -half
	while i <= half:
		_add_static_box(Vector3(center.x + i, 0.01, center.z), Vector3(0.04, 0.02, span.z), grid_mat)
		_add_static_box(Vector3(center.x, 0.01, center.z + i), Vector3(span.x, 0.02, 0.04), grid_mat)
		i += step


# ── Walls ───────────────────────────────────────

func _build_walls() -> void:
	for w in _walls:
		var mn: Vector3 = _v(w["mn"])
		var mx: Vector3 = _v(w["mx"])
		var size := mx - mn
		var c := mn + size * 0.5
		var mat := _wall_material(w.get("material", "concrete"))
		_add_static_box(c, size, mat)

		# Top-edge highlight strip (subtle glow)
		var edge_mat := StandardMaterial3D.new()
		edge_mat.albedo_color = Color(0.45, 0.50, 0.55, 0.35)
		edge_mat.emission_enabled = true
		edge_mat.emission = Color(0.25, 0.30, 0.35)
		_add_static_box(
			Vector3(c.x, mx.y, c.z),
			Vector3(size.x + 0.06, 0.04, size.z + 0.06),
			edge_mat
		)


func _wall_material(type: String) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.roughness = 0.75
	match type:
		"unbreakable":
			mat.albedo_color = Color(0.12, 0.13, 0.16)
			mat.emission_enabled = true
			mat.emission = Color(0.05, 0.06, 0.08)
			mat.emission_energy_multiplier = 0.3
		"wood":
			mat.albedo_color = Color(0.42, 0.30, 0.18)
			mat.roughness = 0.92
		"concrete":
			mat.albedo_color = Color(0.36, 0.38, 0.42)
		_:
			mat.albedo_color = Color(0.16, 0.17, 0.20)
	return mat


# ── Sites (A/B) ─────────────────────────────────

func _build_sites() -> void:
	for s in _sites:
		var c: Vector3 = _v(s["center"])
		var radius: float = s.get("radius", 2.0)
		var label_text: String = s.get("name", "?")

		# Glow disc on ground
		var disc_mat := StandardMaterial3D.new()
		disc_mat.albedo_color = Color(SITE_GLOW_COLOR.r, SITE_GLOW_COLOR.g, SITE_GLOW_COLOR.b, 0.55)
		disc_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		disc_mat.emission_enabled = true
		disc_mat.emission = SITE_GLOW_COLOR
		disc_mat.emission_energy_multiplier = 2.5
		var disc := MeshInstance3D.new()
		var disc_mesh := CylinderMesh.new()
		disc_mesh.top_radius = radius
		disc_mesh.bottom_radius = radius
		disc_mesh.height = 0.08
		disc.mesh = disc_mesh
		disc.material_override = disc_mat
		disc.position = c + Vector3(0, 0.05, 0)
		add_child(disc)

		# Border ring
		var ring_mat := StandardMaterial3D.new()
		ring_mat.albedo_color = Color(SITE_GLOW_COLOR.r, SITE_GLOW_COLOR.g, SITE_GLOW_COLOR.b, 0.7)
		ring_mat.emission_enabled = true
		ring_mat.emission = SITE_GLOW_COLOR
		ring_mat.emission_energy_multiplier = 1.8
		var ring := MeshInstance3D.new()
		var ring_mesh := TorusMesh.new()
		ring_mesh.inner_radius = radius - 0.15
		ring_mesh.outer_radius = radius + 0.15
		ring.mesh = ring_mesh
		ring.material_override = ring_mat
		ring.position = c + Vector3(0, 0.1, 0)
		ring.rotation.x = PI / 2
		add_child(ring)

		# Label
		var label := Label3D.new()
		label.text = label_text
		label.position = c + Vector3(0, 1.8, 0)
		label.font_size = 80
		label.outline_size = 12
		label.modulate = Color(1.0, 0.45, 0.45)
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		add_child(label)


# ── Spawn Markers ────────────────────────────────

func _build_spawn_markers() -> void:
	for sp in _spawns_a:
		_spawn_marker(_v(sp), SPAWN_ATK_COLOR, "ATK")
	for sp in _spawns_d:
		_spawn_marker(_v(sp), SPAWN_DEF_COLOR, "DEF")


func _spawn_marker(pos: Vector3, col: Color, tag: String) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(col.r, col.g, col.b, 0.5)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.emission_enabled = true
	mat.emission = col
	mat.emission_energy_multiplier = 1.5
	var mesh_inst := MeshInstance3D.new()
	var m := CylinderMesh.new()
	m.top_radius = 0.35
	m.bottom_radius = 0.35
	m.height = 0.06
	mesh_inst.mesh = m
	mesh_inst.material_override = mat
	mesh_inst.position = pos + Vector3(0, 0.04, 0)
	add_child(mesh_inst)

	var label := Label3D.new()
	label.text = tag
	label.position = pos + Vector3(0, 0.6, 0)
	label.font_size = 24
	label.outline_size = 4
	label.modulate = col
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	add_child(label)


# ── Buy Zones (translucent floor) ────────────────

func _build_buy_zones() -> void:
	if _buy_atk.size() == 2:
		_buy_zone_rect(_buy_atk[0], _buy_atk[1], SPAWN_ATK_COLOR, "BUY ATK")
	if _buy_def.size() == 2:
		_buy_zone_rect(_buy_def[0], _buy_def[1], SPAWN_DEF_COLOR, "BUY DEF")


func _buy_zone_rect(corner_a: Vector3, corner_b: Vector3, col: Color, tag: String) -> void:
	var mn := Vector3(
		minf(corner_a.x, corner_b.x),
		0.01,
		minf(corner_a.z, corner_b.z)
	)
	var mx := Vector3(
		maxf(corner_a.x, corner_b.x),
		0.03,
		maxf(corner_a.z, corner_b.z)
	)
	var center := (mn + mx) * 0.5
	var size := mx - mn
	size.y = 0.04

	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(col.r, col.g, col.b, BUY_ZONE_ALPHA)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.emission_enabled = true
	mat.emission = col
	mat.emission_energy_multiplier = 0.8
	_add_static_box(center, size, mat)

	var label := Label3D.new()
	label.text = tag
	label.position = center + Vector3(0, 0.5, 0)
	label.font_size = 28
	label.outline_size = 4
	label.modulate = Color(col.r, col.g, col.b, 0.7)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	add_child(label)


# ── Teleporters (portal discs) ───────────────────

func _build_teleporters() -> void:
	for tp in _teleporters:
		var from_pos: Vector3 = _v(tp["from"])
		var to_pos: Vector3 = _v(tp["to"])
		_portal_disc(from_pos, Color(0.30, 0.85, 0.95))
		_portal_disc(to_pos, Color(0.30, 0.95, 0.65))
		# Visible line connecting the two portals
		_line_between(from_pos + Vector3(0, 1.5, 0), to_pos + Vector3(0, 1.5, 0), Color(0.30, 0.85, 0.95, 0.3))


func _portal_disc(pos: Vector3, col: Color) -> void:
	# Outer ring
	var ring_mat := StandardMaterial3D.new()
	ring_mat.albedo_color = Color(col.r, col.g, col.b, 0.6)
	ring_mat.emission_enabled = true
	ring_mat.emission = col
	ring_mat.emission_energy_multiplier = 3.0
	var ring := MeshInstance3D.new()
	var ring_m := TorusMesh.new()
	ring_m.inner_radius = 0.8
	ring_m.outer_radius = 1.0
	ring.mesh = ring_m
	ring.material_override = ring_mat
	ring.position = pos + Vector3(0, 1.5, 0)
	ring.rotation.x = PI / 2
	add_child(ring)

	# Inner glow disc
	var disc_mat := StandardMaterial3D.new()
	disc_mat.albedo_color = Color(col.r, col.g, col.b, 0.35)
	disc_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	disc_mat.emission_enabled = true
	disc_mat.emission = col
	disc_mat.emission_energy_multiplier = 2.0
	var disc := MeshInstance3D.new()
	var disc_m := CylinderMesh.new()
	disc_m.top_radius = 0.8
	disc_m.bottom_radius = 0.8
	disc_m.height = 0.1
	disc.mesh = disc_m
	disc.material_override = disc_mat
	disc.position = pos + Vector3(0, 1.5, 0)
	add_child(disc)


# ── Ropes (lines between anchor points) ──────────

func _build_ropes() -> void:
	for rope in _ropes:
		var points: Array = rope.get("points", [])
		if points.size() < 2:
			continue
		var col := Color(0.7, 0.65, 0.50, 0.6)
		for i in range(points.size() - 1):
			_line_between(_v(points[i]), _v(points[i + 1]), col)


func _line_between(a: Vector3, b: Vector3, col: Color) -> void:
	var mid := (a + b) * 0.5
	var diff := b - a
	var length := diff.length()
	var mat := StandardMaterial3D.new()
	mat.albedo_color = col
	mat.emission_enabled = true
	mat.emission = Color(col.r, col.g, col.b)
	mat.emission_energy_multiplier = 1.0

	var mesh_inst := MeshInstance3D.new()
	var m := BoxMesh.new()
	m.size = Vector3(0.04, 0.04, length)
	mesh_inst.mesh = m
	mesh_inst.material_override = mat
	mesh_inst.position = mid
	if abs(diff.z) > 0.001 or abs(diff.x) > 0.001:
		mesh_inst.look_at(b, Vector3.UP)
		mesh_inst.rotate_object_local(Vector3(1, 0, 0), PI / 2)
	add_child(mesh_inst)


# ── Ceiling ──────────────────────────────────────

func _build_ceiling() -> void:
	var span := _bounds_max - _bounds_min
	var center := (_bounds_min + _bounds_max) * 0.5
	var ceil_h := _bounds_max.y
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.10, 0.12, 0.16, 0.5)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_add_static_box(Vector3(center.x, ceil_h, center.z), Vector3(span.x, 0.3, span.z), mat)


# ── Ambient Light + Environment ──────────────────

func _build_ambient_light() -> void:
	# Directional light (sun-like, slight angle)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, 30, 0)
	sun.light_energy = 0.9
	sun.light_color = Color(0.95, 0.92, 0.88)
	sun.shadow_enabled = true
	sun.shadow_opacity = 0.6
	add_child(sun)

	# Fill light from opposite side
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-30, -150, 0)
	fill.light_energy = 0.3
	fill.light_color = Color(0.7, 0.75, 0.85)
	add_child(fill)

	# WorldEnvironment for ambient + sky
	var env_res := Environment.new()
	env_res.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env_res.ambient_light_color = Color(0.15, 0.17, 0.22)
	env_res.ambient_light_energy = 0.4
	env_res.tonemap_mode = Environment.TONE_MAP_ACES
	env_res.tonemap_white = 6.0
	env_res.ssao_enabled = true
	env_res.ssao_radius = 2.0
	env_res.ssao_intensity = 1.2
	env_res.glow_enabled = true
	env_res.glow_intensity = 0.4
	env_res.glow_bloom = 0.1
	env_res.fog_enabled = true
	env_res.fog_light_color = Color(0.12, 0.14, 0.18)
	env_res.fog_density = 0.008
	env_res.fog_sky_affect = 0.3

	var world_env := WorldEnvironment.new()
	world_env.environment = env_res
	add_child(world_env)


# ── Minimap Camera ───────────────────────────────

func _build_minimap_camera() -> void:
	var span := _bounds_max - _bounds_min
	var center := (_bounds_min + _bounds_max) * 0.5
	var ortho_size := maxf(span.x, span.z) * 0.55

	var cam := Camera3D.new()
	cam.name = "MinimapCamera"
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = ortho_size
	cam.near = 0.1
	cam.far = 100.0
	cam.position = Vector3(center.x, center.y + 60.0, center.z)
	cam.rotation_degrees = Vector3(-90, 0, 0)
	cam.current = false
	add_child(cam)


# ── Helpers ──────────────────────────────────────

func _add_static_box(center_pos: Vector3, size: Vector3, mat: Material) -> void:
	var body := StaticBody3D.new()
	body.position = center_pos
	var col := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	col.shape = shape
	body.add_child(col)
	var mesh_inst := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	mesh_inst.mesh = mesh
	mesh_inst.material_override = mat
	body.add_child(mesh_inst)
	add_child(body)


func _v(d) -> Vector3:
	if d is Vector3:
		return d
	return Vector3(d["x"], d["y"], d["z"])
