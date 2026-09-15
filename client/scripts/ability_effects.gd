## DEPRECATED: No active references found. Kept for reference.
class_name AbilityEffects
extends Node3D

## Client-side ability effect renderer.
## Each render_* method spawns self-managing visual nodes that handle
## their own lifetime, fade-in/out, and cleanup.

const ATK_COLOR := Color(0.95, 0.35, 0.30, 1.0)
const DEF_COLOR := Color(0.30, 0.55, 0.95, 1.0)

# ─── Smoke cloud ───────────────────────────────────────────────
func render_smoke(center: Vector3, radius: float, duration: float) -> Node3D:
	var node := Node3D.new()
	node.position = center

	# Core sphere — semi-translucent
	var core_mesh := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = radius
	sphere.height = radius * 2.0
	core_mesh.mesh = sphere
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.62, 0.64, 0.68, 0.0)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.emission_enabled = true
	mat.emission = Color(0.7, 0.72, 0.75)
	mat.emission_energy_multiplier = 0.0
	mat.no_depth_test = true
	core_mesh.material_override = mat
	node.add_child(core_mesh)

	# Outer halo — softer, larger
	var halo_mesh := MeshInstance3D.new()
	var halo_sphere := SphereMesh.new()
	halo_sphere.radius = radius * 1.4
	halo_sphere.height = radius * 2.8
	halo_mesh.mesh = halo_sphere
	var halo_mat := StandardMaterial3D.new()
	halo_mat.albedo_color = Color(0.58, 0.60, 0.63, 0.0)
	halo_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	halo_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	halo_mat.no_depth_test = true
	halo_mesh.material_override = halo_mat
	node.add_child(halo_mesh)

	# Faint point light for internal glow
	var light := OmniLight3D.new()
	light.light_color = Color(0.75, 0.77, 0.82)
	light.light_energy = 0.0
	light.omni_range = radius * 1.2
	node.add_child(light)

	add_child(node)

	# Lifecycle controller
	var ctrl := _SmokeLifecycle.new(node, mat, halo_mat, light, duration)
	add_child(ctrl)
	return node


# ─── Flash screen overlay ──────────────────────────────────────
func render_flash(center: Vector3, direction: Vector3, radius: float) -> void:
	# White full-screen overlay that fades quickly
	var canvas := CanvasLayer.new()
	add_child(canvas)

	var overlay := ColorRect.new()
	overlay.color = Color(1, 1, 1, 0.0)
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	canvas.add_child(overlay)

	# Animate: fade in fast, hold, fade out
	var tween := create_tween()
	tween.tween_property(overlay, "color:a", 0.92, 0.05)
	tween.tween_interval(0.15)
	tween.tween_property(overlay, "color:a", 0.0, 0.8)
	tween.tween_callback(canvas.queue_free)


# ─── Frag explosion ────────────────────────────────────────────
func render_frag(center: Vector3, radius: float) -> void:
	# Explosion particle burst
	var particles := CPUParticles3D.new()
	particles.emitting = true
	particles.one_shot = true
	particles.explosiveness = 0.95
	particles.amount = 40
	particles.lifetime = 0.8
	particles.lifetime_randomness = 0.3
	particles.mesh = _sphere_mesh(0.08)
	particles.direction = Vector3(0, 1, 0)
	particles.spread = 180.0
	particles.initial_velocity_min = radius * 2.5
	particles.initial_velocity_max = radius * 4.0
	particles.gravity = Vector3(0, -9.8, 0)
	particles.scale_amount_min = 0.5
	particles.scale_amount_max = 2.0

	var fire_mat := StandardMaterial3D.new()
	fire_mat.albedo_color = Color(1.0, 0.6, 0.15, 1.0)
	fire_mat.emission_enabled = true
	fire_mat.emission = Color(1.0, 0.5, 0.1)
	fire_mat.emission_energy_multiplier = 4.0
	particles.mesh = _sphere_mesh(0.06)
	particles.color = Color(1.0, 0.55, 0.1)

	add_child(particles)
	particles.position = center

	# Flash light
	var flash_light := OmniLight3D.new()
	flash_light.light_color = Color(1.0, 0.7, 0.3)
	flash_light.light_energy = 15.0
	flash_light.omni_range = radius * 2.0
	add_child(flash_light)
	flash_light.position = center

	# Smoke ring particles
	var smoke := CPUParticles3D.new()
	smoke.emitting = true
	smoke.one_shot = true
	smoke.explosiveness = 0.8
	smoke.amount = 20
	smoke.lifetime = 1.2
	smoke.mesh = _sphere_mesh(0.15)
	smoke.direction = Vector3(0, 1, 0)
	smoke.spread = 180.0
	smoke.initial_velocity_min = radius * 1.0
	smoke.initial_velocity_max = radius * 2.0
	smoke.gravity = Vector3(0, -1.5, 0)
	smoke.scale_amount_min = 1.0
	smoke.scale_amount_max = 3.0
	smoke.color = Color(0.45, 0.45, 0.45, 0.7)
	add_child(smoke)
	smoke.position = center

	# Cleanup after effect completes
	var timer := Timer.new()
	timer.wait_time = 2.0
	timer.one_shot = true
	timer.timeout.connect(func():
		particles.queue_free()
		smoke.queue_free()
		flash_light.queue_free()
	)
	add_child(timer)
	timer.start()


# ─── Heal particles ────────────────────────────────────────────
func render_heal(target_slot: int, amount: float) -> void:
	# Green rising particles around the healed player
	var particles := CPUParticles3D.new()
	particles.emitting = true
	particles.one_shot = true
	particles.explosiveness = 0.6
	particles.amount = 25
	particles.lifetime = 1.2
	particles.mesh = _sphere_mesh(0.04)
	particles.direction = Vector3(0, 1, 0)
	particles.spread = 30.0
	particles.initial_velocity_min = 1.5
	particles.initial_velocity_max = 3.0
	particles.gravity = Vector3(0, -2.0, 0)
	particles.scale_amount_min = 0.6
	particles.scale_amount_max = 1.5
	particles.color = Color(0.3, 0.95, 0.4, 0.9)

	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.3, 0.95, 0.4, 0.9)
	mat.emission_enabled = true
	mat.emission = Color(0.2, 0.9, 0.3)
	mat.emission_energy_multiplier = 2.0
	particles.mesh.material_override = mat

	add_child(particles)

	# Follow target via a deferred free
	var timer := Timer.new()
	timer.wait_time = 1.5
	timer.one_shot = true
	timer.timeout.connect(particles.queue_free)
	add_child(timer)
	timer.start()

	# Heal number label
	# (Positioned by caller or via _process targeting)


# ─── Deployable wall ───────────────────────────────────────────
func render_wall(start: Vector3, end: Vector3, duration: float) -> MeshInstance3D:
	var mesh_node := MeshInstance3D.new()
	var box := BoxMesh.new()

	var dir := end - start
	var length := dir.length()
	var center_pos := start + dir * 0.5

	# Wall perpendicular to horizontal direction, facing forward
	var forward := dir.normalized()
	var thickness := 0.3
	var height := 3.5

	box.size = Vector3(thickness, height, length)
	mesh_node.mesh = box
	mesh_node.position = center_pos + Vector3(0, height * 0.5, 0)
	# Rotate to face the correct direction
	var angle := atan2(forward.x, forward.z)
	mesh_node.rotation_degrees = Vector3(0, rad_to_deg(angle), 0)

	# Team-colored translucent material
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.5, 0.7, 0.9, 0.7)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.emission_enabled = true
	mat.emission = Color(0.4, 0.6, 0.9)
	mat.emission_energy_multiplier = 1.5
	mesh_node.material_override = mat
	add_child(mesh_node)

	# Edge glow lines
	var edge_mat := StandardMaterial3D.new()
	edge_mat.albedo_color = Color(0.6, 0.8, 1.0, 0.5)
	edge_mat.emission_enabled = true
	edge_mat.emission = Color(0.5, 0.7, 1.0)
	edge_mat.emission_energy_multiplier = 2.0

	# Top edge
	var top := MeshInstance3D.new()
	var top_box := BoxMesh.new()
	top_box.size = Vector3(thickness + 0.05, 0.04, length + 0.05)
	top.mesh = top_box
	top.material_override = edge_mat
	top.position = center_pos + Vector3(0, height, 0)
	add_child(top)

	# Lifecycle: fade in, hold, fade out
	var ctrl := _WallLifecycle.new(mesh_node, top, mat, edge_mat, duration)
	add_child(ctrl)
	return mesh_node


# ─── Slow zone (icy floor decal) ──────────────────────────────
func render_slow_zone(center: Vector3, radius: float, duration: float) -> Node3D:
	var node := Node3D.new()
	node.position = center

	# Ground decal — flat disc
	var disc := MeshInstance3D.new()
	var plane := CylinderMesh.new()
	plane.top_radius = radius
	plane.bottom_radius = radius
	plane.height = 0.05
	disc.mesh = plane
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.4, 0.65, 0.95, 0.6)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.emission_enabled = true
	mat.emission = Color(0.3, 0.55, 0.9)
	mat.emission_energy_multiplier = 1.0
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	disc.material_override = mat
	disc.position = Vector3(0, 0.03, 0)
	node.add_child(disc)

	# Frost particle overlay
	var frost := CPUParticles3D.new()
	frost.emitting = true
	frost.one_shot = false
	frost.amount = 12
	frost.lifetime = 1.5
	frost.mesh = _sphere_mesh(0.03)
	frost.direction = Vector3(0, 1, 0)
	frost.spread = 180.0
	frost.initial_velocity_min = 0.2
	frost.initial_velocity_max = 0.5
	frost.gravity = Vector3(0, -0.1, 0)
	frost.scale_amount_min = 0.5
	frost.scale_amount_max = 1.2
	frost.color = Color(0.5, 0.75, 1.0, 0.7)
	frost.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	frost.emission_sphere_radius = radius * 0.8
	node.add_child(frost)

	add_child(node)

	# Fade in/out
	var ctrl := _SlowLifecycle.new(disc, mat, frost, duration)
	add_child(ctrl)
	return node


# ─── Trap (visible with team glow) ────────────────────────────
func render_trap(center: Vector3, team: int) -> Node3D:
	var node := Node3D.new()
	node.position = center

	var team_col := ATK_COLOR if team == 0 else DEF_COLOR

	# Core indicator sphere
	var core := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = 0.15
	sphere.height = 0.3
	core.mesh = sphere
	var mat := StandardMaterial3D.new()
	mat.albedo_color = team_col
	mat.emission_enabled = true
	mat.emission = team_col
	mat.emission_energy_multiplier = 3.0
	core.material_override = mat
	core.position = Vector3(0, 0.15, 0)
	node.add_child(core)

	# Glow ring on ground
	var ring := MeshInstance3D.new()
	var ring_mesh := TorusMesh.new()
	ring_mesh.inner_radius = 0.3
	ring_mesh.outer_radius = 0.5
	ring.mesh = ring_mesh
	var ring_mat := StandardMaterial3D.new()
	ring_mat.albedo_color = Color(team_col.r, team_col.g, team_col.b, 0.4)
	ring_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	ring_mat.emission_enabled = true
	ring_mat.emission = team_col
	ring_mat.emission_energy_multiplier = 2.0
	ring_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ring.material_override = ring_mat
	ring.position = Vector3(0, 0.05, 0)
	ring.rotation_degrees = Vector3(90, 0, 0)
	node.add_child(ring)

	# Pulsing light
	var light := OmniLight3D.new()
	light.light_color = team_col
	light.light_energy = 2.0
	light.omni_range = 1.5
	light.position = Vector3(0, 0.3, 0)
	node.add_child(light)

	# Pulse animation
	var tween := create_tween().set_loops()
	tween.tween_property(light, "light_energy", 0.5, 0.5)
	tween.tween_property(light, "light_energy", 2.5, 0.5)

	add_child(node)
	return node


# ─── Teleport portals ──────────────────────────────────────────
func render_teleport(from: Vector3, to: Vector3, duration: float) -> void:
	# Two portal discs with connecting beam
	var portal_a := _make_portal(from, Color(0.6, 0.3, 0.9))
	var portal_b := _make_portal(to, Color(0.3, 0.6, 0.9))
	add_child(portal_a)
	add_child(portal_b)

	# Beam connecting the two
	var beam := MeshInstance3D.new()
	var beam_mesh := BoxMesh.new()
	var dist := from.distance_to(to)
	var dir := (to - from).normalized()
	beam_mesh.size = Vector3(0.06, 0.06, dist)
	beam.mesh = beam_mesh
	var beam_mat := StandardMaterial3D.new()
	beam_mat.albedo_color = Color(0.5, 0.4, 0.9, 0.5)
	beam_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	beam_mat.emission_enabled = true
	beam_mat.emission = Color(0.5, 0.4, 0.9)
	beam_mat.emission_energy_multiplier = 3.0
	beam_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	beam.material_override = beam_mat
	var beam_center := from + dir * dist * 0.5
	beam.position = beam_center
	beam.look_at(to, Vector3.UP)
	add_child(beam)

	# Fade out after duration
	var timer := Timer.new()
	timer.wait_time = duration
	timer.one_shot = true
	timer.timeout.connect(func():
		var tw := create_tween()
		tw.set_parallel(true)
		tw.tween_property(portal_a, "scale", Vector3.ZERO, 0.3)
		tw.tween_property(portal_b, "scale", Vector3.ZERO, 0.3)
		tw.tween_property(beam, "modulate", Color(1, 1, 1, 0), 0.3)
		tw.chain().tween_callback(func():
			portal_a.queue_free()
			portal_b.queue_free()
			beam.queue_free()
		)
	)
	add_child(timer)
	timer.start()


# ─── Nearsight fog overlay ─────────────────────────────────────
func render_nearsight(center: Vector3, radius: float) -> void:
	# Dark fog sphere around the target zone
	var fog := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	sphere.radius = radius
	sphere.height = radius * 2.0
	fog.mesh = sphere
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.05, 0.05, 0.08, 0.7)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.no_depth_test = true
	fog.material_override = mat
	fog.position = center
	add_child(fog)

	# Fade in, hold, fade out
	var tween := create_tween()
	tween.tween_property(mat, "albedo_color:a", 0.7, 0.3)
	tween.tween_interval(1.5)
	tween.tween_property(mat, "albedo_color:a", 0.0, 0.5)
	tween.tween_callback(fog.queue_free)


# ─── Suppression electrical effect ─────────────────────────────
func render_suppression(target_slot: int, duration: float) -> void:
	# Electrical sparks around the suppressed target
	var emitter := CPUParticles3D.new()
	emitter.emitting = true
	emitter.one_shot = false
	emitter.amount = 15
	emitter.lifetime = 0.6
	emitter.mesh = _sphere_mesh(0.02)
	emitter.direction = Vector3(0, 1, 0)
	emitter.spread = 180.0
	emitter.initial_velocity_min = 2.0
	emitter.initial_velocity_max = 4.0
	emitter.gravity = Vector3(0, -6.0, 0)
	emitter.scale_amount_min = 0.3
	emitter.scale_amount_max = 1.0
	emitter.color = Color(0.8, 0.85, 1.0, 0.9)

	var spark_mat := StandardMaterial3D.new()
	spark_mat.albedo_color = Color(0.8, 0.85, 1.0, 0.9)
	spark_mat.emission_enabled = true
	spark_mat.emission = Color(0.6, 0.7, 1.0)
	spark_mat.emission_energy_multiplier = 4.0
	emitter.mesh.material_override = spark_mat

	add_child(emitter)

	# Electric arc light
	var arc_light := OmniLight3D.new()
	arc_light.light_color = Color(0.5, 0.6, 1.0)
	arc_light.light_energy = 4.0
	arc_light.omni_range = 2.0
	add_child(arc_light)

	# Flicker
	var flicker := create_tween().set_loops()
	flicker.tween_property(arc_light, "light_energy", 1.0, 0.05)
	flicker.tween_property(arc_light, "light_energy", 5.0, 0.05)

	# Cleanup
	var timer := Timer.new()
	timer.wait_time = duration
	timer.one_shot = true
	timer.timeout.connect(func():
		emitter.emitting = false
		arc_light.queue_free()
		var fade := create_tween()
		fade.tween_interval(0.6)
		fade.tween_callback(emitter.queue_free)
	)
	add_child(timer)
	timer.start()


# ═══════════════════════════════════════════════════════════════
#  Helper: portal disc mesh
# ═══════════════════════════════════════════════════════════════
func _make_portal(pos: Vector3, col: Color) -> MeshInstance3D:
	var portal := MeshInstance3D.new()
	var ring := TorusMesh.new()
	ring.inner_radius = 0.6
	ring.outer_radius = 0.85
	portal.mesh = ring
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(col.r, col.g, col.b, 0.6)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.emission_enabled = true
	mat.emission = col
	mat.emission_energy_multiplier = 3.0
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	portal.material_override = mat
	portal.position = pos + Vector3(0, 1.5, 0)
	portal.rotation_degrees = Vector3(90, 0, 0)
	return portal


func _sphere_mesh(radius: float) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = radius
	s.height = radius * 2.0
	return s


# ═══════════════════════════════════════════════════════════════
#  Lifecycle controllers (self-cleaning nodes)
# ═══════════════════════════════════════════════════════════════
class _SmokeLifecycle extends Node:
	var _node: Node3D
	var _mat: StandardMaterial3D
	var _halo_mat: StandardMaterial3D
	var _light: OmniLight3D
	var _duration: float
	var _elapsed := 0.0
	var _fade_start := 0.0

	func _init(node: Node3D, mat: StandardMaterial3D, halo_mat: StandardMaterial3D,
			light: OmniLight3D, duration: float) -> void:
		_node = node
		_mat = mat
		_halo_mat = halo_mat
		_light = light
		_duration = duration
		_fade_start = maxf(0.0, duration - 2.0)

	func _process(delta: float) -> void:
		if not is_instance_valid(_node):
			queue_free()
			return
		_elapsed += delta
		# Fade in (0-0.4s)
		if _elapsed < 0.4:
			var u := _elapsed / 0.4
			_mat.albedo_color.a = u * 0.85
			_mat.emission_energy_multiplier = u * 0.3
			_halo_mat.albedo_color.a = u * 0.35
			_light.light_energy = u * 0.5
		# Fade out (last 2s)
		elif _elapsed > _fade_start and _duration > 0.0:
			var u := clampf((_duration - _elapsed) / 2.0, 0.0, 1.0)
			_mat.albedo_color.a = u * 0.85
			_mat.emission_energy_multiplier = u * 0.3
			_halo_mat.albedo_color.a = u * 0.35
			_light.light_energy = u * 0.5
		# Expired
		if _elapsed >= _duration:
			_node.queue_free()
			queue_free()


class _WallLifecycle extends Node:
	var _mesh: MeshInstance3D
	var _edge: MeshInstance3D
	var _mat: StandardMaterial3D
	var _edge_mat: StandardMaterial3D
	var _duration: float
	var _elapsed := 0.0

	func _init(mesh: MeshInstance3D, edge: MeshInstance3D,
			mat: StandardMaterial3D, edge_mat: StandardMaterial3D,
			duration: float) -> void:
		_mesh = mesh
		_edge = edge
		_mat = mat
		_edge_mat = edge_mat
		_duration = duration

	func _process(delta: float) -> void:
		if not is_instance_valid(_mesh):
			queue_free()
			return
		_elapsed += delta
		# Fade in (0-0.3s)
		if _elapsed < 0.3:
			var u := _elapsed / 0.3
			_mat.albedo_color.a = u * 0.7
			_edge_mat.albedo_color.a = u * 0.5
		# Fade out (last 1.5s)
		var fade_start := maxf(0.0, _duration - 1.5)
		if _elapsed > fade_start:
			var u := clampf((_duration - _elapsed) / 1.5, 0.0, 1.0)
			_mat.albedo_color.a = u * 0.7
			_edge_mat.albedo_color.a = u * 0.5
		if _elapsed >= _duration:
			_mesh.queue_free()
			if is_instance_valid(_edge):
				_edge.queue_free()
			queue_free()


class _SlowLifecycle extends Node:
	var _disc: MeshInstance3D
	var _mat: StandardMaterial3D
	var _frost: CPUParticles3D
	var _duration: float
	var _elapsed := 0.0

	func _init(disc: MeshInstance3D, mat: StandardMaterial3D,
			frost: CPUParticles3D, duration: float) -> void:
		_disc = disc
		_mat = mat
		_frost = frost
		_duration = duration

	func _process(delta: float) -> void:
		if not is_instance_valid(_disc):
			queue_free()
			return
		_elapsed += delta
		# Fade in
		if _elapsed < 0.5:
			_mat.albedo_color.a = (_elapsed / 0.5) * 0.6
		# Fade out (last 1s)
		var fade_start := maxf(0.0, _duration - 1.0)
		if _elapsed > fade_start:
			var u := clampf((_duration - _elapsed) / 1.0, 0.0, 1.0)
			_mat.albedo_color.a = u * 0.6
		if _elapsed >= _duration:
			_frost.emitting = false
			_disc.queue_free()
			var timer := Timer.new()
			timer.wait_time = 1.5
			timer.one_shot = true
			timer.timeout.connect(_frost.queue_free)
			get_tree().root.add_child(timer)
			timer.start()
			queue_free()
