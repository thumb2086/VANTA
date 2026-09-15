class_name WeaponViewmodelV2
extends Node3D

## Valorant-quality first-person weapon viewmodel.
## Replaces the procedural box-built weapon with a high-fidelity system:
## - Idle sway (subtle figure-8)
## - Fire recoil + return
## - Reload sequence (mag out → mag in)
## - Weapon switch animation
## - ADS (aim down sights) with zoom
## - Inspect animation for skin showcase
## - Muzzle flash, shell ejection, tracer lines
## - View bob synced with walk
## - Recoil recovery

signal reload_mag_drop
signal reload_rack

const REST_POS := Vector3(0.22, -0.20, -0.42)
const REST_ROT := Vector3(0.0, 0.0, 0.0)
const ADS_POS := Vector3(0.0, -0.12, -0.48)
const ADS_ROT := Vector3(0.0, 0.0, 0.0)
const INSPECT_CENTER := Vector3(-0.05, -0.05, -0.30)

var weapon_slot := 1
var _weapon_id := 0
var _parts := {}
var _state := "idle"
var _t := 0.0
var _dur := 0.2

# Recoil
var _recoil_offset := Vector3.ZERO
var _recoil_rot := Vector3.ZERO
var _recoil_recovery_speed := 8.0

# Sway (figure-8 idle motion)
var _sway_time := 0.0
var _sway_amount := Vector3(0.003, 0.004, 0.002)
var _sway_speed := 1.2
var _mouse_sway := Vector2.ZERO

# ADS
var _ads := 0.0
var _ads_target := false
var _ads_speed := 10.0

# Bob
var _bob_phase := 0.0
var _bob_intensity := 0.0

# Fire
var _fire_kick := 0.0
var _fire_return_t := 0.0

# Reload
var _reload_t := 0.0
var _reload_local := false
var _prev_reload_frac := -1.0
var _mag_emitted := false
var _rack_emitted := false

# Shell ejection
var _shell_particles: CPUParticles3D = null

# Muzzle flash
var _muzzle_flash_light: OmniLight3D = null
var _muzzle_flash_sprite: Sprite3D = null
var _muzzle_flash_timer := 0.0

# Tracer
var _tracer_pool: Array[MeshInstance3D] = []

# Inspect
var _inspect_time := 0.0

# Speed
var _speed := 0.0

# Muzzle position (world-space relative to camera)
var _muzzle_world := Vector3.ZERO

# Weapon model root
var _weapon_root: Node3D = null

## 皮膚／特效整合
var _finish: Dictionary = {}          # WeaponFinish.build() 回傳的 state
var skin_res: Dictionary = {}         # SkinRegistry.resolve() 的結果
var fx_mgr: Node = null               # FxManager（有 → 由它負責槍口/曳光）
var _fire_decay := 0.0                # 開火脈衝（0..1，驅動滑套/發光）
var _mag_out := 0.0                   # 換彈時彈匣退出量
var _weapon_key := "phantom"
var _bob_vec := Vector3.ZERO


func _ready() -> void:
	_weapon_root = Node3D.new()
	add_child(_weapon_root)
	_init_muzzle_flash()
	_init_shell_ejector()
	_init_tracer_pool()


# ═══════════════════════════════════════════════════════════════
#  Build weapon (drop-in replacement for WeaponViewModel.build_weapon)
# ═══════════════════════════════════════════════════════════════
func build_weapon(slot: int, palette: Dictionary, weapon_id: int = -1,
		resolution: Dictionary = {}) -> void:
	clear_parts()
	weapon_slot = slot
	if weapon_id < 0:
		weapon_id = 0 if slot == 0 else 2 if slot == 1 else 4
	_weapon_id = weapon_id
	_weapon_key = String(palette.get("weapon_key", _key_for_id(weapon_id)))
	_weapon_root.position = REST_POS
	_weapon_root.rotation = REST_ROT
	skin_res = resolution

	var body_col: Color = palette.get("primary", Color(0.2, 0.2, 0.25))
	var dark: Color = body_col.darkened(0.45)
	var metal: Color = Color(0.45, 0.47, 0.52)
	var accent: Color = palette.get("accent", Color(0.9, 0.9, 0.95))

	# 有皮肤解析結果 → 用 WeaponFinish（花紋貼圖 + 角色材質 + 發光件 + 槍飾）
	if not skin_res.is_empty() and skin_res.has("colorway"):
		_finish = WeaponFinish.build(_weapon_root, skin_res, SkinRegistry.shared(), {
			"textures": true, "texture_size": ProceduralTexture.SIZE_VIEWMODEL,
			"uv_density": 2.2, "scale": 1.0,
		})
		_index_parts()
		_tint_internal_fx()
		return

	# 沒皮膚資料時：仍然用同一份圖譜組裝（全 20 把槍、角色配色），
	# 這樣武器不會因為素材缺失而退化成一個方塊。
	var fallback_res := {
		"skin_id": "", "weapon": _weapon_key, "collection": "standard", "level": 1,
		"chroma_index": 0, "tier_glow": 0.0,
		"colorway": {"primary": "#" + body_col.to_html(false),
			"secondary": "#" + dark.to_html(false),
			"accent": "#" + accent.to_html(false),
			"emissive": "#000000", "metalness": 0.45, "roughness": 0.55, "clearcoat": 0.0,
			"iridescence": 0.0, "pattern_mix": 0.0, "emissive_strength": 0.0,
			"rim_color": "#ffffff", "rim_strength": 0.0, "wear": 0.15, "name": "標準"},
		"fx": {"style": "default", "muzzle_color": "#ffd9a0", "tracer_color": "#ffe6a0",
			"impact_color": "#ffcf8a", "kill_color": "#ffdd66", "shell_color": "#c9a24a",
			"shell_glow": 0.0, "tracer_width": 1.0, "muzzle_scale": 1.0},
		"flags": {}, "extras": [], "features": [], "pattern": "solid", "pattern_params": {},
	}
	_finish = WeaponFinish.build(_weapon_root, fallback_res, SkinRegistry.shared(), {
		"textures": false, "uv_density": 1.0, "scale": 1.0,
	})
	_index_parts()


static func _key_for_id(weapon_id: int) -> String:
	const IDS := ["phantom", "vandal", "ghost", "classic", "knife", "sheriff", "spectre",
		"operator", "shorty", "bulldog", "guardian", "judge", "frenzy", "outlaw", "marshal",
		"bandit", "stinger", "ares", "odin", "bucky"]
	if weapon_id >= 0 and weapon_id < IDS.size():
		return IDS[weapon_id]
	return "phantom"


## 把 WeaponFinish 的零件索引回舊欄位（沿用換彈/拉滑套動畫與 signal 邏輯）
func _index_parts() -> void:
	_parts.clear()
	for p in _finish.get("parts", []):
		var d: Dictionary = p
		var node: Node3D = d.get("node", null)
		if node == null:
			continue
		var nm := String(d.get("role", "")) + "_" + String(node.name)
		_parts[node.name] = node
		if nm.begins_with("body_receiver") or nm.begins_with("body_frame"):
			_parts["receiver"] = node
		elif String(d.get("anim", "")) == "mag":
			_parts["mag"] = node
		elif String(d.get("anim", "")) in ["slide", "bolt", "charging"]:
			_parts["slide"] = node
		elif node.name == "barrel" or node.name == "integral_supp":
			_parts["barrel"] = node


## 讓內建的槍口光／彈殼顏色跟皮膚一致
func _tint_internal_fx() -> void:
	var fx: Dictionary = skin_res.get("fx", {})
	var mc := SkinRegistry.hex_color(fx.get("muzzle_color", "#ffd9a0"), Color(1, 0.85, 0.5))
	if _muzzle_flash_light != null:
		_muzzle_flash_light.light_color = SkinRegistry.hex_color(
			fx.get("light_color", "#ffb060"), mc)
		_muzzle_flash_light.light_energy = 0.0
	if _muzzle_flash_sprite != null:
		_muzzle_flash_sprite.modulate = Color(mc.r, mc.g, mc.b, 0.0)
		_muzzle_flash_sprite.shadow_casting = ShadowCastingSetting.SHADOW_CASTING_SETTING_OFF
	var shell := SkinRegistry.hex_color(fx.get("shell_color", "#c9a24a"), Color(0.85, 0.7, 0.25))
	if _shell_particles != null and _shell_particles.mesh != null:
		var m := StandardMaterial3D.new()
		m.albedo_color = shell
		var glow := float(fx.get("shell_glow", 0.0))
		if glow > 0.02:
			m.emission_enabled = true
			m.emission = shell
			m.emission_energy_multiplier = 1.0 + glow * 3.0
		var nm2 := _shell_particles.mesh.duplicate()
		_shell_particles.mesh = nm2
		nm2.material = m


## 供 FxManager 使用的槍口變換（世界座標 + 朝向）
func muzzle_transform() -> Transform3D:
	var anchor := WeaponGeometry.muzzle_anchor(_weapon_key)
	var origin := _weapon_root.to_global(anchor)
	var cam := get_viewport().get_camera_3d() if get_viewport() != null else null
	var dir := -global_transform.basis.z
	if cam != null:
		dir = -cam.global_transform.basis.z
	return Transform3D(Basis.looking_at(dir.normalized(), Vector3.UP), origin)


func set_skin_resolution(res: Dictionary) -> void:
	skin_res = res
	if fx_mgr != null and fx_mgr.has_method("set_skin_resolution"):
		fx_mgr.call("set_skin_resolution", res)
	if not res.is_empty():
		_tint_internal_fx()


func current_weapon_key() -> String:
	return _weapon_key


# ═══════════════════════════════════════════════════════════════
#  Weapon builders (simplified — key parts only, can swap for .glb later)
# ═══════════════════════════════════════════════════════════════
func _build_phantom(body: Color, dark: Color, metal: Color, accent: Color) -> void:
	# Receiver
	_add_part("receiver", Vector3(0.07, 0.095, 0.30), body, Vector3(0, -0.02, -0.06))
	# Barrel + suppressor
	_add_part("barrel", Vector3(0.05, 0.05, 0.45), metal, Vector3(0, 0, -0.48))
	_add_part("suppressor", Vector3(0.06, 0.06, 0.14), Color(0.25, 0.27, 0.30), Vector3(0, 0, -0.72))
	# Magazine
	_add_part("mag", Vector3(0.05, 0.17, 0.08), dark, Vector3(0, -0.12, -0.06))
	# Grip
	_add_part("grip", Vector3(0.048, 0.14, 0.065), body, Vector3(0, -0.13, 0.08))
	# Stock
	_add_part("stock", Vector3(0.05, 0.07, 0.20), dark, Vector3(0, -0.01, 0.22))
	# Rail
	_add_part("rail", Vector3(0.038, 0.012, 0.32), metal, Vector3(0, 0.053, -0.12))
	# Sight
	_add_part("sight", Vector3(0.035, 0.04, 0.08), accent, Vector3(0, 0.08, -0.10))
	_add_part("sight_lens", Vector3(0.025, 0.025, 0.01), Color(0.3, 0.6, 0.9, 0.7), Vector3(0, 0.08,
		-0.14))
	# Accent stripe
	_add_part("accent", Vector3(0.072, 0.006, 0.26), accent, Vector3(0, 0.028, -0.06))


func _build_vandal(body: Color, dark: Color, metal: Color, accent: Color) -> void:
	_add_part("receiver", Vector3(0.075, 0.10, 0.26), body, Vector3(0, -0.02, -0.04))
	_add_part("barrel", Vector3(0.055, 0.055, 0.38), metal, Vector3(0, 0, -0.42))
	_add_part("handguard", Vector3(0.07, 0.07, 0.18), dark, Vector3(0, -0.005, -0.26))
	_add_part("mag", Vector3(0.05, 0.18, 0.07), dark, Vector3(0.01, -0.13, -0.05))
	_add_part("grip", Vector3(0.05, 0.15, 0.065), body, Vector3(0, -0.13, 0.07))
	_add_part("stock", Vector3(0.06, 0.08, 0.22), dark, Vector3(0, -0.01, 0.22))
	_add_part("rail", Vector3(0.04, 0.015, 0.34), metal, Vector3(0, 0.055, -0.14))
	_add_part("sight", Vector3(0.03, 0.045, 0.05), accent, Vector3(0, 0.08, -0.08))
	_add_part("muzzle", Vector3(0.06, 0.05, 0.06), metal, Vector3(0, 0, -0.62))
	_add_part("accent", Vector3(0.077, 0.008, 0.22), accent, Vector3(0, 0.03, -0.04))


func _build_ghost(body: Color, dark: Color, metal: Color, accent: Color) -> void:
	var s := 0.70
	_add_part("slide", Vector3(0.055 * s, 0.05 * s, 0.22 * s), body, Vector3(0, 0.03, -0.12))
	_add_part("barrel", Vector3(0.035 * s, 0.035 * s, 0.28 * s), metal, Vector3(0, 0, -0.28))
	_add_part("suppressor", Vector3(0.042 * s, 0.042 * s, 0.10 * s), Color(0.22, 0.24, 0.28),
		Vector3(0, 0, -0.44))
	_add_part("mag", Vector3(0.035 * s, 0.10 * s, 0.05 * s), dark, Vector3(0, -0.08, -0.04))
	_add_part("grip", Vector3(0.04 * s, 0.11 * s, 0.05 * s), body, Vector3(0, -0.09, 0.06))
	_add_part("sight", Vector3(0.02 * s, 0.025 * s, 0.03 * s), accent, Vector3(0, 0.065, -0.10))


func _build_classic(body: Color, dark: Color, metal: Color, accent: Color) -> void:
	var s := 0.65
	_add_part("slide", Vector3(0.052 * s, 0.048 * s, 0.20 * s), body, Vector3(0, 0.025, -0.10))
	_add_part("barrel", Vector3(0.032 * s, 0.032 * s, 0.20 * s), metal, Vector3(0, 0, -0.22))
	_add_part("mag", Vector3(0.032 * s, 0.09 * s, 0.045 * s), dark, Vector3(0, -0.07, -0.03))
	_add_part("grip", Vector3(0.038 * s, 0.10 * s, 0.048 * s), body, Vector3(0, -0.08, 0.05))
	_add_part("sight", Vector3(0.018 * s, 0.02 * s, 0.025 * s), accent, Vector3(0, 0.058, -0.08))


func _build_knife(_body: Color, dark: Color, _metal: Color, _accent: Color) -> void:
	var blade_col := Color(0.75, 0.78, 0.85)
	_add_part("blade", Vector3(0.03, 0.02, 0.28), blade_col, Vector3(0, 0.01, -0.22))
	_add_part("guard", Vector3(0.09, 0.025, 0.02), dark, Vector3(0, 0, -0.07))
	_add_part("handle", Vector3(0.04, 0.04, 0.14), dark, Vector3(0, -0.01, 0.06))
	_add_part("pommel", Vector3(0.05, 0.045, 0.03), Color(0.5, 0.35, 0.15), Vector3(0, -0.01, 0.14))


func clear_parts() -> void:
	if not _finish.is_empty():
		WeaponFinish.clear(_weapon_root, _finish)
	_finish = {}
	for p in _parts.values():
		if p is Node and is_instance_valid(p):
			p.queue_free()
	_parts.clear()


func _add_part(name: String, size: Vector3, color: Color, pos: Vector3) -> MeshInstance3D:
	var n := MeshInstance3D.new()
	var m := BoxMesh.new()
	m.size = size
	n.mesh = m
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.7
	n.material_override = mat
	n.position = pos
	_weapon_root.add_child(n)
	_parts[name] = n
	return n


# ═══════════════════════════════════════════════════════════════
#  Muzzle flash (PointLight3D + sprite at barrel tip)
# ═══════════════════════════════════════════════════════════════
func _init_muzzle_flash() -> void:
	_muzzle_flash_light = OmniLight3D.new()
	_muzzle_flash_light.light_color = Color(1.0, 0.85, 0.5)
	_muzzle_flash_light.light_energy = 0.0
	_muzzle_flash_light.omni_range = 2.5
	_muzzle_flash_light.omni_attenuation = 2.0
	add_child(_muzzle_flash_light)

	_muzzle_flash_sprite = Sprite3D.new()
	_muzzle_flash_sprite.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_muzzle_flash_sprite.pixel_size = 0.003
	_muzzle_flash_sprite.modulate = Color(1.0, 0.9, 0.5, 0.0)
	# Use a simple circle texture or procedural
	var img := Image.create(32, 32, false, Image.FORMAT_RGBA8)
	for x in range(32):
		for y in range(32):
			var dx := (x - 16.0) / 16.0
			var dy := (y - 16.0) / 16.0
			var dist := sqrt(dx * dx + dy * dy)
			var a := clampf(1.0 - dist, 0.0, 1.0)
			img.set_pixel(x, y, Color(1.0, 0.85, 0.4, a))
	var tex := ImageTexture.create_from_image(img)
	_muzzle_flash_sprite.texture = tex
	add_child(_muzzle_flash_sprite)


func trigger_muzzle_flash() -> void:
	_muzzle_flash_timer = 0.06
	# Random rotation for variety
	_muzzle_flash_sprite.rotation = randf() * TAU
	_muzzle_flash_sprite.scale = Vector3.ONE * randf_range(0.8, 1.3)


func _update_muzzle_flash(delta: float, muzzle_pos: Vector3) -> void:
	_muzzle_flash_timer -= delta
	if _muzzle_flash_timer > 0.0:
		var intensity := _muzzle_flash_timer / 0.06
		_muzzle_flash_light.light_energy = intensity * 8.0
		_muzzle_flash_light.position = muzzle_pos
		_muzzle_flash_sprite.position = muzzle_pos
		_muzzle_flash_sprite.modulate.a = intensity
	else:
		_muzzle_flash_light.light_energy = 0.0
		_muzzle_flash_sprite.modulate.a = 0.0


# ═══════════════════════════════════════════════════════════════
#  Shell ejection (small brass particles flying right)
# ═══════════════════════════════════════════════════════════════
func _init_shell_ejector() -> void:
	_shell_particles = CPUParticles3D.new()
	_shell_particles.emitting = false
	_shell_particles.one_shot = true
	_shell_particles.amount = 1
	_shell_particles.lifetime = 0.8
	_shell_particles.explosiveness = 1.0

	var shell_mesh := BoxMesh.new()
	shell_mesh.size = Vector3(0.008, 0.012, 0.02)
	_shell_particles.mesh = shell_mesh

	var shell_mat := StandardMaterial3D.new()
	shell_mat.albedo_color = Color(0.85, 0.7, 0.25)
	shell_mat.emission_enabled = true
	shell_mat.emission = Color(0.8, 0.65, 0.2)
	shell_mat.emission_energy_multiplier = 0.5
	_shell_particles.mesh.material_override = shell_mat

	# Eject to the right and slightly up
	_shell_particles.direction = Vector3(1, 0.5, 0.3)
	_shell_particles.spread = 20.0
	_shell_particles.initial_velocity_min = 1.5
	_shell_particles.initial_velocity_max = 3.0
	_shell_particles.gravity = Vector3(0, -6.0, 0)
	_shell_particles.scale_amount_min = 0.8
	_shell_particles.scale_amount_max = 1.2
	_shell_particles.rotation_speed_min = 300
	_shell_particles.rotation_speed_max = 600

	add_child(_shell_particles)


func eject_shell() -> void:
	# Position at ejection port (right side of receiver)
	var eject_pos := Vector3(0.04, 0.02, -0.04)
	_shell_particles.position = eject_pos
	_shell_particles.restart()
	_shell_particles.emitting = true


# ═══════════════════════════════════════════════════════════════
#  Tracer lines
# ═══════════════════════════════════════════════════════════════
func _init_tracer_pool() -> void:
	for i in range(3):
		var tracer := MeshInstance3D.new()
		var mesh := BoxMesh.new()
		mesh.size = Vector3(0.004, 0.004, 1.0)
		tracer.mesh = mesh
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(1.0, 0.95, 0.6, 0.0)
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.emission_enabled = true
		mat.emission = Color(1.0, 0.9, 0.5)
		mat.emission_energy_multiplier = 2.0
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		tracer.material_override = mat
		tracer.visible = false
		add_child(tracer)
		_tracer_pool.append(tracer)


func fire_tracer(origin: Vector3, direction: Vector3, max_dist: float = 30.0) -> void:
	for tracer in _tracer_pool:
		if tracer.visible:
			continue
		tracer.visible = true
		tracer.global_position = origin + direction * (max_dist * 0.5)
		tracer.look_at(origin + direction * max_dist, Vector3.UP)
		tracer.scale = Vector3(1, 1, max_dist)
		# Auto-hide after short time
		var tw := create_tween()
		tw.tween_property(tracer.material_override, "albedo_color:a", 0.0, 0.15)
		tw.tween_callback(func(): tracer.visible = false)
		tw.tween_property(tracer.material_override, "albedo_color:a", 0.0, 0.0)
		return


# ═══════════════════════════════════════════════════════════════
#  Animation triggers (drop-in compatible with WeaponViewModel API)
# ═══════════════════════════════════════════════════════════════
func play_fire(recoil_pitch: float) -> void:
	_fire_decay = 1.0
	_state = "fire"
	_t = 0.0
	_dur = 0.10
	_fire_kick = 0.14 + minf(recoil_pitch, 3.0) * 0.02
	# Recoil recovery target
	_recoil_offset = Vector3(0, 0, _fire_kick)
	_recoil_rot = Vector3(_fire_kick * 2.0, (randf() - 0.5) * 0.02, 0)
	# Muzzle flash
	trigger_muzzle_flash()
	# Shell ejection
	if _weapon_id != 4:  # Not knife
		eject_shell()


func play_reload(duration: float) -> void:
	_state = "reload"
	_t = 0.0
	_dur = maxf(duration, 0.6)
	_reload_t = 0.0
	_reload_local = true
	_mag_emitted = false
	_rack_emitted = false


func begin_reload_from_server() -> void:
	if _state != "reload":
		_state = "reload"
	_reload_local = false
	_mag_emitted = false
	_rack_emitted = false


func play_switch_in() -> void:
	_state = "switch_in"
	_t = 0.0
	_dur = 0.25


func play_switch_out() -> void:
	_state = "switch_out"
	_t = 0.0
	_dur = 0.20


func play_knife() -> void:
	_state = "knife"
	_t = 0.0
	_dur = 0.35


func play_inspect() -> void:
	if _state == "inspect":
		return
	_state = "inspect"
	_t = 0.0
	_dur = 1.2


func set_ads(on: bool) -> void:
	_ads_target = on


func set_recoil(pitch_deg: float) -> void:
	_recoil_rot.x = pitch_deg


# ═══════════════════════════════════════════════════════════════
#  Per-frame update
# ═══════════════════════════════════════════════════════════════
## 检视动作随皮肤风格变化（传说皮「召唤武器」，能量皮「悬浮旋转」…）
func _inspect_style(u: float, pos: Vector3, rot: Vector3) -> void:
	if skin_res.is_empty():
		return
	var style := String(skin_res.get("inspect", "standard"))
	var k := sin(clampf(u, 0.0, 1.0) * PI)
	match style:
		"summon":
			# 從虛空中召喚：先远离再抓住
			rot.y += k * 0.55
			pos.z += k * 0.10
			pos.y -= k * 0.05
		"examine", "inspect":
			rot.x += k * 0.30
			rot.z += k * 0.42
		"holo":
			rot.z += k * 0.28
			pos.y -= k * 0.035 + sin(u * TAU * 2.0) * 0.004
		"spin":
			rot.y += u * TAU * 0.9
		"flip":
			rot.z += sin(u * PI * 2.0) * 0.7
			pos.y -= absf(sin(u * PI * 2.0)) * 0.03
		"reveal":
			rot.x -= k * 0.45
			pos.z += k * 0.06
		_:
			pass


func update(dt: float, speed: float, on_ground: bool, mouse_delta: Vector2,
		reload_frac: float = -1.0) -> void:
	_mouse_sway = mouse_delta * 0.0015
	_speed = speed

	# ADS interpolation
	_ads = lerpf(_ads, 1.0 if _ads_target else 0.0, 1.0 - exp(-_ads_speed * dt))

	# Sway phase (figure-8 motion)
	_sway_time += dt * _sway_speed

	# Bob phase (only when moving on ground, disabled during ADS)
	if speed > 0.3 and on_ground and _ads < 0.3:
		_bob_phase += dt * (5.5 + speed * 1.2)
		_bob_intensity = lerpf(_bob_intensity, 1.0, 1.0 - exp(-8.0 * dt))
	else:
		_bob_intensity = lerpf(_bob_intensity, 0.0, 1.0 - exp(-6.0 * dt))

	# State time
	_t += dt

	# External reload end detection
	if _state == "reload" and not _reload_local and reload_frac < 0.0:
		_state = "idle"
		_reload_u = -1.0
		_reload_apply(0.0, -1.0)
	if _state == "fire" and _t >= _dur:
		_state = "idle"
	elif _state == "reload" and _t >= _dur and _reload_local:
		_state = "idle"
		_reload_local = false
	elif _state == "switch_out" and _t >= _dur:
		_state = "idle"
	elif _state == "switch_in" and _t >= _dur:
		_state = "idle"
	elif _state == "knife" and _t >= _dur:
		_state = "idle"
	elif _state == "inspect" and _t >= _dur:
		_state = "idle"

	# ── Compute target position/rotation ──
	var pos := REST_POS
	var rot := REST_ROT

	# ADS blend
	pos = pos.lerp(ADS_POS, _ads)
	rot = rot.lerp(ADS_ROT, _ads)

	# Idle sway (figure-8) — reduced during ADS
	var sway_scale := (1.0 - _ads) * 0.6
	var sway_x := sin(_sway_time * 1.1) * cos(_sway_time * 0.7) * _sway_amount.x * sway_scale
	var sway_y := sin(_sway_time * 0.9) * cos(_sway_time * 1.3) * _sway_amount.y * sway_scale
	var sway_z := cos(_sway_time * 1.5) * _sway_amount.z * sway_scale * 0.5

	# Mouse-driven micro-sway
	var mouse_sway_x := _mouse_sway.x * (1.0 - _ads * 0.7)
	var mouse_sway_y := _mouse_sway.y * (1.0 - _ads * 0.7)
	_mouse_sway = _mouse_sway.lerp(Vector2.ZERO, 1.0 - exp(-14.0 * dt))

	# Walk bob (figure-8 pattern)
	var bob_x := sin(_bob_phase * 0.5) * 0.005 * _bob_intensity
	var bob_y := absf(sin(_bob_phase)) * 0.007 * _bob_intensity

	# State-specific offsets
	match _state:
		"fire":
			var u := _t / _dur
			var kick := _fire_kick * (1.0 - u)
			pos.z += kick
			rot.x += kick * 2.5
			rot.y += (randf() - 0.5) * 0.015
		"reload":
			var u := reload_frac if reload_frac >= 0.0 else clampf(_reload_t, 0.0, 1.0)
			if reload_frac < 0.0:
				_reload_t += dt / _dur
				u = clampf(_reload_t, 0.0, 1.0)
			u = clampf(u, 0.0, 1.0)
			_reload_u = u
			_reload_apply(u, reload_frac)
			# Weapon dips down and tilts during reload
			pos.y -= sin(u * PI) * 0.20
			pos.z += sin(u * PI) * 0.08
			rot.x += sin(u * PI) * 0.5
		"inspect":
			var u := _t / _dur
			_inspect_style(u, pos, rot)
			if u < 0.35:
				# Bring weapon to center and rotate
				var lu := u / 0.35
				pos = pos.lerp(INSPECT_CENTER, lu)
				rot.y = lu * 0.8
				rot.x = lu * 0.5
				rot.z = lu * 0.3
			else:
				# Rotate to showcase angle
				var hu := (u - 0.35) / 0.65
				pos = INSPECT_CENTER.lerp(Vector3(-0.08, -0.02, -0.35), hu)
				rot.y = lerpf(0.8, PI * 0.9, hu)
				rot.x = lerpf(0.5, -0.1, hu)
				rot.z = lerpf(0.3, 0.0, hu)
		"switch_out":
			var u := _t / _dur
			pos.y -= u * 0.35
			pos.z += u * 0.3
			rot.x += u * 1.4
			rot.y += u * 0.9
		"switch_in":
			var u := 1.0 - _t / _dur
			pos.y -= u * 0.35
			pos.z += u * 0.3
			rot.x += u * 1.4
			rot.y += u * 0.9
		"knife":
			var u := _t / _dur
			rot.y = lerpf(0.9, -0.9, u)
			rot.x = lerpf(-0.5, 0.4, u)
			pos.x = lerpf(0.1, -0.25, u)
			pos.y -= u * 0.05

	# Apply recoil (recovers over time)
	_recoil_offset = _recoil_offset.lerp(Vector3.ZERO, 1.0 - exp(-_recoil_recovery_speed * dt))
	_recoil_rot = _recoil_rot.lerp(Vector3.ZERO, 1.0 - exp(-_recoil_recovery_speed * dt))

	# Final assembly
	pos += Vector3(sway_x + mouse_sway_x, sway_y + mouse_sway_y, sway_z)
	pos += Vector3(bob_x, bob_y, 0)
	pos += _recoil_offset
	rot += _recoil_rot

	_weapon_root.position = pos
	_weapon_root.rotation = rot

	# 開火脈衝衰減（滑套/槍機/發光件都讀這個值）
	_fire_decay = maxf(0.0, _fire_decay - dt * 9.0)
	if _state != "reload":
		_mag_out = lerpf(_mag_out, 0.0, clampf(dt * 12.0, 0.0, 1.0))

	# 皮膚細節：發光呼吸、槍飾搖曳、彈匣/滑套位移
	if not _finish.is_empty():
		_bob_vec = Vector3(sway_x + bob_x, sway_y + bob_y, sway_z)
		WeaponFinish.tick(_finish, dt, _fire_decay, _ads,
			_reload_u if _state == "reload" else -1.0, _mag_out, _bob_vec)
		if bool(skin_res.get("flags", {}).get("breathing", false)):
			var br := 1.0 + sin(_t * 1.05) * 0.004
			_weapon_root.scale = Vector3(br, br, br)
		else:
			_weapon_root.scale = Vector3.ONE

	# 槍口位置改用幾何圖譜的錨點（換槍／換皮膚都正確）
	var muzzle_local := WeaponGeometry.muzzle_anchor(_weapon_key)
	_muzzle_world = _weapon_root.to_global(muzzle_local)
	_update_muzzle_flash(dt, _muzzle_world)


## 目前換彈進度（提供給 WeaponFinish）
var _reload_u := -1.0


func _reload_apply(u: float, external: float) -> void:
	"""換彈：退匣 → 入匣 → 拉滑套（有 WeaponFinish 時由它驅動零件位移）"""
	# 彈匣退出量（WeaponFinish.tick 讀它來移動 mag 零件）
	if u < 0.20:
		_mag_out = 0.0
	elif u < 0.42:
		_mag_out = (u - 0.20) / 0.22
	elif u < 0.56:
		_mag_out = 1.0
	else:
		_mag_out = clampf(1.0 - (u - 0.56) / 0.18, 0.0, 1.0)
	if not _finish.is_empty():
		# 開火/換彈時的拉機把由 fire 脈衝驅動
		_fire_decay = maxf(_fire_decay, 0.55 if (u >= 0.60 and u < 0.80) else 0.0)
		_milestone(external, u)
		return
	# Mag out (0.20-0.40)
	if u >= 0.20 and u < 0.40:
		var mu := (u - 0.20) / 0.20
		if _parts.has("mag"):
			_parts["mag"].position = Vector3(0, -0.11 - mu * 0.25, -0.06 + mu * 0.10)
	elif u >= 0.40:
		var mu := clampf((u - 0.40) / 0.20, 0.0, 1.0)
		if _parts.has("mag"):
			_parts["mag"].position = Vector3(0, -0.11 + mu * 0.001, -0.06)
	# Rack slide (0.60-0.78)
	if u >= 0.60 and u < 0.78:
		var su := (u - 0.60) / 0.18
		if _parts.has("receiver"):
			_parts["receiver"].position.z = -0.05 + sin(su * PI) * 0.04
	elif u >= 0.78 and _parts.has("receiver"):
		_parts["receiver"].position.z = -0.05
	_milestone(external, u)


func _milestone(external: float, u: float) -> void:
	if external >= 0.0:
		if not _mag_emitted and u >= 0.28:
			_mag_emitted = true
			reload_mag_drop.emit()
		if not _rack_emitted and u >= 0.62:
			_rack_emitted = true
			reload_rack.emit()
