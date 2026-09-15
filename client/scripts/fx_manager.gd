class_name FxManager
extends Node3D

## 分層特效管理器（資料驅動：資料來源 = res://assets/skins.json 的 `effects` 區段）
##
## 一個「blueprint」= 多層（particles / mesh / light / decal / hud / camera / sound）。
## 每層的顏色取自皮膚 colorway（`color_key`）、預設取自 style+slot、`when_style`
## 決定「只有能量/聖光/雷射/噬魂等風格才有衝擊波」——換皮 → 特效跟著變，
## 腳本裡沒有任何「如果是某支皮膚就⋯」的硬編碼。
##
## 效能與穩定：
##   * 節點全部池化（取得/歸還），同屏用量有上限（quality 控制），超-budget 直接丟棄。
##   * 只用 CPUParticles3D / MeshInstance3D / OmniLight3D（Compatibility 渲染器可用）。
##   * 屬性用 `_set()` 安全賦值：不同 Godot 小版缺少的屬性會被跳過而不是報錯。

signal fx_spawned(name: String, count: int)

const POOL_LIMITS := {
	"particles": 22, "mesh": 26, "light": 8, "decal": 16, "billboard": 20,
}
const DECAL_KEEP := 16

var registry: SkinRegistry = null
var hud: Node = null                       # HUD（hit marker / banner 由 blueprint 驅動）
var quality := 1                           # 0=低 1=中 2=高
var muzzle_light := true
var enabled := true
var max_decal_age := 14.0

var _pools: Dictionary = {"particles": [], "mesh": [], "light": [], "decal": [], "billboard": []}
var _active: Array = []
var _decals: Array = []
var _tex: Dictionary = {}
var _pmesh: Dictionary = {}
var _budget: Dictionary = {}
var _budget_window := 0.0
var _spawned_total := 0
var _skin_res: Dictionary = {}
var _camera: Camera3D = null
var _screen: Node = null
var _audio: Node = null
var _time := 0.0
var _props: Dictionary = {}


func _ready() -> void:
	_ensure_textures()


func setup(reg: SkinRegistry, camera: Camera3D = null, screen: Node = null,
		audio: Node = null, p_hud: Node = null) -> void:
	registry = reg
	_camera = camera
	_screen = screen
	_audio = audio
	hud = p_hud
	_ensure_textures()


func set_skin_resolution(res: Dictionary) -> void:
	_skin_res = res


func stats() -> Dictionary:
	return {"active": _active.size(), "decals": _decals.size(), "spawned": _spawned_total,
		"budget": _budget.duplicate()}


## 安全設定屬性（版本/渲染器缺少該屬性時靜默略過）
func _set(obj: Object, prop: String, value: Variant) -> bool:
	var key := obj.get_class()
	if not _props.has(key):
		var names := {}
		for p in obj.get_property_list():
			names[String(p.name)] = true
		_props[key] = names
	if not (_props[key] as Dictionary).has(prop):
		return false
	obj.set(prop, value)
	return true


# ═══════════════════════════════════════════════════════
#  紋理（程序化生成，不依賴外部 PNG）
# ═══════════════════════════════════════════════════════
func _ensure_textures() -> void:
	if not _tex.is_empty():
		return
	_tex["glow"] = _make_radial(64, 2.4, 0.0)
	_tex["soft"] = _make_radial(64, 1.1, 0.35)
	_tex["star4"] = _make_star(64, 4, 0.16)
	_tex["star6"] = _make_star(64, 6, 0.13)
	_tex["star2"] = _make_star(48, 2, 0.20)
	_tex["spark"] = _make_spark(48)
	_tex["ring"] = _make_ring(64, 0.14)
	_tex["smoke"] = _make_smoke(64)
	_tex["shard"] = _make_shard(48)
	_tex["dot"] = _make_dot(16)
	_tex["hole"] = _make_hole(48)


static func _new_img(size: int) -> Image:
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	return img


static func _tex_from(img: Image) -> ImageTexture:
	return ImageTexture.create_from_image(img, false)


func _make_radial(size: int, power: float, core: float) -> ImageTexture:
	var img := _new_img(size)
	var half := size * 0.5
	for y in size:
		for x in size:
			var dx := (float(x) - half + 0.5) / half
			var dy := (float(y) - half + 0.5) / half
			var d := sqrt(dx * dx + dy * dy)
			var a := pow(clampf(1.0 - d, 0.0, 1.0), power)
			if core > 0.0:
				a = clampf(a + core * clampf(1.0 - d * 4.0, 0.0, 1.0), 0.0, 1.0)
			img.set_pixel(x, y, Color(1, 1, 1, a))
	return _tex_from(img)


func _make_star(size: int, points: int, thick: float) -> ImageTexture:
	var img := _new_img(size)
	var half := size * 0.5
	for y in size:
		for x in size:
			var dx := (float(x) - half + 0.5) / half
			var dy := (float(y) - half + 0.5) / half
			var d := sqrt(dx * dx + dy * dy)
			if d > 1.0:
				continue
			var ang := atan2(dy, dx)
			var petal := abs(cos(ang * float(points) * 0.5))
			var spike := pow(clampf(1.0 - d, 0.0, 1.0), 1.0 + thick * 6.0)
			var core := pow(clampf(1.0 - d * 2.2, 0.0, 1.0), 1.4)
			var a := clampf(pow(petal, 1.0 / maxf(0.05, thick * 2.0)) * spike * 0.9 + core, 0.0, 1.0)
			img.set_pixel(x, y, Color(1, 1, 1, a))
	return _tex_from(img)


func _make_spark(size: int) -> ImageTexture:
	var img := _new_img(size)
	var half := size * 0.5
	for y in size:
		for x in size:
			var dx := (float(x) - half + 0.5) / half
			var dy := (float(y) - half + 0.5) / half
			var along := pow(clampf(1.0 - abs(dx), 0.0, 1.0), 1.6)
			var across := pow(clampf(1.0 - abs(dy) * 4.5, 0.0, 1.0), 1.2)
			var dot := pow(clampf(1.0 - sqrt(dx * dx + dy * dy) * 2.4, 0.0, 1.0), 1.5)
			img.set_pixel(x, y, Color(1, 1, 1, clampf(along * across * 0.85 + dot, 0.0, 1.0)))
	return _tex_from(img)


func _make_ring(size: int, thick: float) -> ImageTexture:
	var img := _new_img(size)
	var half := size * 0.5
	for y in size:
		for x in size:
			var dx := (float(x) - half + 0.5) / half
			var dy := (float(y) - half + 0.5) / half
			var d := sqrt(dx * dx + dy * dy)
			var a := pow(clampf(1.0 - abs(d - 0.82) / maxf(0.02, thick), 0.0, 1.0), 1.4)
			img.set_pixel(x, y, Color(1, 1, 1, a))
	return _tex_from(img)


func _make_smoke(size: int) -> ImageTexture:
	var img := _new_img(size)
	var half := size * 0.5
	for y in size:
		for x in size:
			var dx := (float(x) - half + 0.5) / half
			var dy := (float(y) - half + 0.5) / half
			var d := sqrt(dx * dx + dy * dy)
			var n := (sin(dx * 9.1 + dy * 4.3) + sin(dy * 7.7 - dx * 3.1)
				+ sin((dx + dy) * 5.9)) / 3.0
			var a := clampf(1.0 - d * 0.95, 0.0, 1.0)
			a = clampf(a * a * (0.62 + 0.38 * (n * 0.5 + 0.5)), 0.0, 1.0)
			img.set_pixel(x, y, Color(1, 1, 1, a))
	return _tex_from(img)


func _make_shard(size: int) -> ImageTexture:
	var img := _new_img(size)
	var half := size * 0.5
	for y in size:
		for x in size:
			var dx := (float(x) - half + 0.5) / half
			var dy := (float(y) - half + 0.5) / half
			var diamond := clampf(1.0 - (abs(dx) + abs(dy) * 1.7), 0.0, 1.0)
			img.set_pixel(x, y, Color(1, 1, 1, pow(clampf(diamond * 2.6, 0.0, 1.0), 1.1) * 0.95))
	return _tex_from(img)


func _make_dot(size: int) -> ImageTexture:
	var img := _new_img(size)
	var half := size * 0.5
	for y in size:
		for x in size:
			var dx := (float(x) - half + 0.5) / half
			var dy := (float(y) - half + 0.5) / half
			var a := clampf(1.0 - sqrt(dx * dx + dy * dy) * 1.05, 0.0, 1.0)
			img.set_pixel(x, y, Color(1, 1, 1, pow(a, 0.7)))
	return _tex_from(img)


func _make_hole(size: int) -> ImageTexture:
	var img := _new_img(size)
	var half := size * 0.5
	for y in size:
		for x in size:
			var dx := (float(x) - half + 0.5) / half
			var dy := (float(y) - half + 0.5) / half
			var d := sqrt(dx * dx + dy * dy) * 1.12
			var ang := atan2(dy, dx)
			var hole := clampf((d - 0.52) * 7.0, 0.0, 1.0)
			var scorch := pow(clampf(1.0 - d, 0.0, 1.0), 0.85)
			var jitter := 0.5 + 0.5 * sin(ang * 7.0)
			var a := clampf(scorch * (0.55 + 0.45 * jitter) + (1.0 - hole) * 0.9, 0.0, 1.0)
			img.set_pixel(x, y, Color(0.02, 0.02, 0.025, a * 0.92))
	return _tex_from(img)


func _tex_for(sprite_key: String, fallback: String = "glow") -> Texture2D:
	match sprite_key:
		"star", "muzzle_star":
			return _tex.get("star4", null)
		"star6":
			return _tex.get("star6", null)
		"soul", "spike", "cross":
			return _tex.get("star2", null)
		"spark", "streak":
			return _tex.get("spark", null)
		"ring", "shockwave":
			return _tex.get("ring", null)
		"smoke", "puff", "dust":
			return _tex.get("smoke", null)
		"shard", "glass":
			return _tex.get("shard", null)
		"dot", "pixel":
			return _tex.get("dot", null)
		"":
			return _tex.get(fallback, null)
		_:
			return _tex.get(fallback, null)


## 粒子外觀網格（加色混合 → 發光；同 key 共用）
func _particle_mesh(add: bool, sprite_key: String) -> QuadMesh:
	var key := "%s|%s" % [sprite_key, "a" if add else "m"]
	if _pmesh.has(key):
		return _pmesh[key]
	var quad := QuadMesh.new()
	quad.size = Vector2(1, 1)
	quad.orientation = PrimitiveMesh.FORWARD_Z
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD if add else BaseMaterial3D.BLEND_MODE_MIX
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.vertex_color_use_as_albedo = true
	mat.albedo_texture = _tex_for(sprite_key)
	quad.material = mat
	_pmesh[key] = quad
	return quad


# ═══════════════════════════════════════════════════════
#  池化
# ═══════════════════════════════════════════════════════
func _take(kind: String) -> Variant:
	var pool: Array = _pools.get(kind, [])
	if not pool.is_empty():
		return pool.pop_back()
	match kind:
		"particles":
			var p := CPUParticles3D.new()
			p.local_coords = false
			p.one_shot = true
			return p
		"billboard", "mesh", "decal":
			var m := MeshInstance3D.new()
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			m.visible = true
			return m
		"light":
			var l := OmniLight3D.new()
			l.shadow_enabled = false
			return l
		_:
			return null


func _release(kind: String, node: Node) -> void:
	if node == null or not is_instance_valid(node):
		return
	var parent := node.get_parent()
	if parent != null:
		parent.remove_child(node)
	var pool: Array = _pools.get(kind, [])
	if pool.size() < int(POOL_LIMITS.get(kind, 16)):
		pool.append(node)
		_pools[kind] = pool
	else:
		node.queue_free()


func _acquire_slot(kind: String) -> bool:
	var cap := int(POOL_LIMITS.get(kind, 16))
	if quality == 0:
		cap = int(cap * 0.45)
	elif quality == 2:
		cap = int(cap * 1.75)
	var used := int(_budget.get(kind, 0))
	if used >= cap:
		return false
	_budget[kind] = used + 1
	return true


func _release_slot(kind: String) -> void:
	_budget[kind] = maxi(0, int(_budget.get(kind, 0)) - 1)


# ═══════════════════════════════════════════════════════
#  播放 blueprint
# ═══════════════════════════════════════════════════════
## ctx: {muzzle: Transform3D, impact: Vector3, normal: Vector3, victim: Vector3,
##       dir: Vector3, scale: float, res: Dictionary, hud: Node, headshot: bool,
##       victim_name: String, smoke: bool}
func play(blueprint_id: String, ctx: Dictionary = {}) -> void:
	if not enabled or registry == null:
		return
	if _time - _budget_window > 0.1:
		_budget_window = _time
		_budget = {}
	var bp: Dictionary = registry.blueprint(blueprint_id)
	if bp.is_empty():
		spawn_preset(blueprint_id, Vector3(ctx.get("impact", Vector3.ZERO)), ctx)
		return
	var res: Dictionary = ctx.get("res", _skin_res)
	var style := String(res.get("fx", {}).get("style", "default"))
	var base_scale := float(ctx.get("scale", 1.0))
	var count := 0
	for layer in bp.get("layers", []):
		var l: Dictionary = layer
		if l.has("when_style"):
			var ws: Array = l["when_style"]
			if not ws.has(style):
				continue
		if l.has("when_smoke") and not bool(ctx.get("smoke", false)):
			continue
		if _play_layer(l, res, ctx, base_scale, float(l.get("delay", 0.0))):
			count += 1
	_spawned_total += count
	fx_spawned.emit(blueprint_id, count)
	var audio: Dictionary = bp.get("audio", {})
	if not audio.is_empty() and _audio != null and _audio.has_method("play_synth"):
		_audio.call("play_synth", String(audio.get("sfx", "")), float(audio.get("pitch", 1.0)),
			float(audio.get("gain_db", 0.0)), 0.0)


func _play_layer(l: Dictionary, res: Dictionary, ctx: Dictionary, base_scale: float,
		delay: float) -> bool:
	var type := String(l.get("type", "particles"))
	var at := String(l.get("at", "impact"))
	var pos := _resolve_at(at, ctx)
	var color := _layer_color(l, res)
	match type:
		"particles":
			var preset := _layer_preset(l, res)
			if preset == "":
				return false
			_emit_particles(preset, pos, color, base_scale * float(l.get("scale", 1.0)),
				ctx, delay)
			return true
		"mesh":
			_play_mesh(String(l.get("preset", "shockwave")), pos, color, l, base_scale, ctx)
			return true
		"light":
			_play_light(pos, color, l, base_scale, delay)
			return true
		"decal":
			_play_decal(l, res, pos, ctx, base_scale)
			return true
		"camera":
			_play_camera(l)
			return true
		"hud":
			_play_hud(l, res, ctx, color)
			return true
		"sound":
			# 圖層自帶的音效（藍圖的 audio 段另有主音效，這裡是額外分層音）
			if _audio != null:
				_audio.play_synth(String(l.get("sfx", l.get("preset", ""))),
					clampf(float(l.get("gain_db", 0.0)) / 24.0 + 1.0, 0.2, 2.0),
					float(l.get("pitch", 1.0)))
			return true
		_:
			return false


func _resolve_at(at: String, ctx: Dictionary) -> Vector3:
	match at:
		"muzzle":
			var xf: Transform3D = ctx.get("muzzle", Transform3D.IDENTITY)
			return xf.origin
		"weapon":
			var xf2: Transform3D = ctx.get("muzzle", Transform3D.IDENTITY)
			return xf2.origin
		"eject":
			return ctx.get("eject", ctx.get("impact", Vector3.ZERO))
		"ground":
			var g: Vector3 = ctx.get("impact", Vector3.ZERO)
			return Vector3(g.x, ctx.get("ground_y", g.y), g.z)
		"world":
			# 直接採用呼叫端給的位置（不需要掛在槍／人身上）
			return ctx.get("impact", Vector3.ZERO)
		"victim":
			return ctx.get("victim", ctx.get("impact", Vector3.ZERO))
		"tracer":
			var a: Vector3 = ctx.get("tracer_from", Vector3.ZERO)
			var b: Vector3 = ctx.get("impact", a)
			return a.lerp(b, 0.5)
		"screen", "camera":
			if _camera != null:
				var f := -_camera.global_transform.basis.z
				return _camera.global_transform.origin + f * 1.2
			return ctx.get("impact", Vector3.ZERO)
		"ground":
			var g: Vector3 = ctx.get("impact", Vector3.ZERO)
			return Vector3(g.x, g.y - 0.02, g.z)
		_:
			return ctx.get("impact", Vector3.ZERO)


func _layer_preset(l: Dictionary, res: Dictionary) -> String:
	if l.has("preset"):
		return String(l["preset"])
	if l.has("slot"):
		var fx: Dictionary = res.get("fx", {})
		var key := String(l["slot"])
		var style := String(fx.get("style", "default"))
		var mapped := registry.preset_for_slot(style, key)
		if mapped != "":
			return mapped
		var direct := String(fx.get(key, ""))
		return direct
	return ""


func _layer_color(l: Dictionary, res: Dictionary) -> Color:
	var fx: Dictionary = res.get("fx", {})
	if l.has("color_key"):
		var v: Variant = fx.get(String(l["color_key"]), null)
		if v != null:
			return SkinRegistry.hex_color(v, Color(1, 0.85, 0.6))
	if l.has("color"):
		return SkinRegistry.hex_color(l["color"], Color(1, 0.85, 0.6))
	return SkinRegistry.hex_color(fx.get("muzzle_color", "#ffd9a0"), Color(1, 0.85, 0.6))


func _play_camera(l: Dictionary) -> void:
	if _screen == null or not _screen.has_method("add_trauma"):
		return
	var preset := String(l.get("preset", "kick"))
	var trauma := float(l.get("trauma", 0.1))
	match preset:
		"shake":
			_screen.call("add_trauma", trauma)
		"kick", "recoil":
			_screen.call("add_trauma", trauma)
			if _screen.has_method("add_fov_kick"):
				_screen.call("add_fov_kick", -trauma * 9.0)
		"pulse":
			if _screen.has_method("flash"):
				_screen.call("flash", Color(1, 1, 1, 0.10), 0.30)
			_screen.call("add_trauma", trauma)
		_:
			_screen.call("add_trauma", trauma)


func _play_hud(l: Dictionary, res: Dictionary, ctx: Dictionary, color: Color) -> void:
	var preset := String(l.get("preset", "hitmarker"))
	var target: Node = ctx.get("hud", hud)
	match preset:
		"hitmarker":
			if target != null and target.has_method("hit_marker"):
				target.call("hit_marker", color, bool(ctx.get("headshot", false)),
					1.0 + 0.12 * int(res.get("level", 1)))
			if _audio != null and _audio.has_method("play_hitmarker"):
				_audio.call("play_hitmarker", bool(ctx.get("headshot", false)))
		"kill_banner":
			var frame := String(res.get("fx", {}).get("banner_frame", "default"))
			var vname := String(ctx.get("victim_name", "對手"))
			if target != null and target.has_method("show_kill_banner_fx"):
				target.call("show_kill_banner_fx", vname, String(res.get("name", "")), color, frame,
					int(res.get("level", 1)))
			elif target != null and target.has_method("show_kill_banner"):
				target.call("show_kill_banner", vname, false, String(res.get("name", "")))
		"flash":
			if _screen != null and _screen.has_method("flash"):
				_screen.call("flash", color, float(l.get("intensity", 0.5)))
		_:
			if _screen != null and _screen.has_method("pulse_hud"):
				_screen.call("pulse_hud", preset, color)


func _play_light(pos: Vector3, color: Color, l: Dictionary, base_scale: float,
		delay: float) -> void:
	if not muzzle_light or quality == 0:
		return
	if not _acquire_slot("light"):
		return
	var node: OmniLight3D = _take("light")
	if node == null:
		_release_slot("light")
		return
	node.light_color = color
	node.omni_energy = float(l.get("energy", 3.0)) * base_scale
	node.omni_range = float(l.get("range", 2.5)) * base_scale
	node.global_transform = Transform3D(Basis.IDENTITY, pos)
	add_child(node)
	_active.append({"kind": "light", "node": node, "t": -delay,
		"ttl": float(l.get("ttl", 0.06)) + delay, "energy0": node.omni_energy})


func _play_mesh(preset: String, pos: Vector3, color: Color, l: Dictionary,
		base_scale: float, ctx: Dictionary) -> void:
	var prim: Dictionary = registry.mesh_primitive(preset)
	if prim.is_empty():
		return
	if not _acquire_slot("mesh"):
		return
	var node: MeshInstance3D = _take("mesh")
	if node == null:
		_release_slot("mesh")
		return
	var mesh := _mesh_for(String(prim.get("geometry", "ring")))
	if mesh == null:
		_release_slot("mesh")
		return
	node.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if bool(prim.get("additive", true)):
		mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	else:
		mat.blend_mode = BaseMaterial3D.BLEND_MODE_MIX
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.emission_enabled = true
	mat.emission = color
	mat.emission_energy_multiplier = float(prim.get("energy", 2.0))
	mat.albedo_color = Color(color.r, color.g, color.b, 0.9)
	node.material_override = mat
	var sc := float(l.get("scale", 1.0)) * base_scale
	node.global_position = pos
	var nrm := _vec3(ctx.get("normal", Vector3.UP))
	if String(prim.get("geometry", "ring")) == "ring" or String(prim.get("geometry", "")) == "ring":
		if nrm.length_squared() > 0.001:
			node.look_at(pos + nrm.normalized())
	node.scale = Vector3(sc, sc, sc)
	add_child(node)
	_active.append({"kind": "mesh", "node": node, "mat": mat, "t": 0.0,
		"ttl": float(l.get("ttl", 0.28)), "grow": float(prim.get("grow", 3.0)),
		"fade": String(prim.get("fade", "quad_out")), "sc0": sc,
		"alpha0": mat.albedo_color.a})


func _mesh_for(geo: String) -> Mesh:
	match geo:
		"ring":
			var t := TorusMesh.new()
			t.inner_radius = 0.66
			t.outer_radius = 1.0
			t.rings = 24
			t.ring_segments = 4
			return t
		"arc":
			var q := QuadMesh.new()
			q.size = Vector2(1.4, 0.7)
			q.orientation = PrimitiveMesh.FORWARD_Z
			return q
		"lines":
			var q2 := QuadMesh.new()
			q2.size = Vector2(0.6, 0.6)
			q2.orientation = PrimitiveMesh.FORWARD_Z
			return q2
		"sphere":
			var s := SphereMesh.new()
			s.radius = 0.5
			s.height = 1.0
			s.radial_segments = 14
			s.rings = 6
			return s
		_:
			return null


func _play_decal(l: Dictionary, res: Dictionary, pos: Vector3, ctx: Dictionary,
		base_scale: float) -> void:
	var key := String(l.get("preset_key", "decal"))
	var decal_id := String(res.get("fx", {}).get(key, "bullet_hole"))
	if registry.decal(decal_id).is_empty():
		decal_id = "bullet_hole"
	var d: Dictionary = registry.decal(decal_id)
	if d.is_empty():
		return
	if not _acquire_slot("decal"):
		return
	var node: MeshInstance3D = _take("decal")
	if node == null:
		_release_slot("decal")
		return
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ALPHA
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.albedo_texture = _tex.get("hole", null)
	var col := SkinRegistry.hex_color(d.get("color", "#141014"), Color(0.1, 0.1, 0.1))
	mat.albedo_color = Color(col.r, col.g, col.b, float(d.get("opacity", 0.9)))
	node.mesh = node.mesh if node.mesh != null else QuadMesh.new()
	node.material_override = mat
	node.global_position = pos
	var nrm := _vec3(ctx.get("normal", Vector3.UP))
	if nrm.length_squared() < 0.001:
		nrm = -Vector3(ctx.get("dir", Vector3(0, 0, -1))).normalized()
	node.look_at(pos + nrm)
	node.translate(nrm.normalized() * 0.014)
	var size := float(d.get("size", 0.3)) * base_scale * float(l.get("scale", 1.0))
	node.scale = Vector3(size, size, size)
	add_child(node)
	_decals.append({"node": node, "mat": mat, "age": 0.0,
		"ttl": minf(max_decal_age, float(d.get("lifetime", 12.0))),
		"alpha0": mat.albedo_color.a})
	while _decals.size() > DECAL_KEEP:
		var old: Dictionary = _decals.pop_front()
		var on: Node = old.get("node", null)
		if on != null and is_instance_valid(on):
			_release("decal", on)
		_release_slot("decal")


# ═══════════════════════════════════════════════════════
#  粒子（particles.json → CPUParticles3D）
# ═══════════════════════════════════════════════════════
func _emit_particles(preset: String, pos: Vector3, color: Color, scale: float,
		ctx: Dictionary, delay: float) -> void:
	var p: Dictionary = registry.particles(preset)
	if p.is_empty():
		return
	if not _acquire_slot("particles"):
		return
	var node: CPUParticles3D = _take("particles")
	if node == null:
		_release_slot("particles")
		return
	var amount := int(p.get("count", 12))
	if quality == 0:
		amount = int(amount * 0.5)
	elif quality == 2:
		amount = int(amount * 1.4)
	var life := float(p.get("life", 0.4))
	node.amount = amount
	node.lifetime = life + float(p.get("life_var", 0.0)) * 0.6
	node.one_shot = true
	node.explosiveness = 1.0 if float(p.get("speed", 0.0)) > 0.5 else 0.4
	node.randomness = float(p.get("life_var", 0.0)) * 0.5
	node.preprocess = 0.0
	node.emitting = true
	node.visible = delay <= 0.0
	_set(node, "direction", _vec3(p.get("direction", [0, 1, 0])))
	_set(node, "spread", float(p.get("cone_angle", 45.0)))
	var speed := float(p.get("speed", 3.0)) * scale
	var svar := float(p.get("speed_var", 0.3))
	_set(node, "initial_velocity_min", speed * (1.0 - svar))
	_set(node, "initial_velocity_max", speed)
	_set(node, "gravity", Vector3(0, -float(p.get("gravity", 0.0)), 0))
	_set(node, "damping_min", float(p.get("drag", 0.0)))
	_set(node, "damping_max", float(p.get("drag", 0.0)))
	var sz := maxf(0.004, float(p.get("size", 0.05)) * scale * 8.0)
	_set(node, "scale_amount_min", sz)
	_set(node, "scale_amount_max", sz * (1.0 + float(p.get("size_var", 0.3))))
	_set(node, "angular_velocity_min", float(p.get("spin", 0.0)))
	_set(node, "angular_velocity_max", float(p.get("spin", 0.0)) * 1.8)
	_set(node, "emission_shape", CPUParticles3D.EMISSION_SHAPE_SPHERE)
	_set(node, "emission_sphere_radius", float(p.get("radius", 0.04)) * scale)
	_set(node, "turbulence", float(p.get("turbulence", 0.0)) * 4.0)
	var cs: Variant = p.get("color_start", null)
	var ce: Variant = p.get("color_end", null)
	var c0 := color
	var c1 := color
	if cs != null and typeof(cs) == TYPE_ARRAY:
		c0 = Color(int(cs[0]) / 255.0, int(cs[1]) / 255.0, int(cs[2]) / 255.0)
	if ce != null and typeof(ce) == TYPE_ARRAY:
		c1 = Color(int(ce[0]) / 255.0, int(ce[1]) / 255.0, int(ce[2]) / 255.0)
	c0 = c0.lerp(color, 0.5)
	c1 = c1.lerp(color, 0.75)
	var grad := Gradient.new()
	grad.set_color(0, c0)
	grad.set_color(1, c1)
	var ramp := GradientTexture1D.new()
	ramp.gradient = grad
	_set(node, "color_ramp", ramp)
	node.mesh = _particle_mesh(bool(p.get("additive", true)), String(p.get("sprite", "")))
	node.global_transform = Transform3D(Basis.IDENTITY, pos)
	add_child(node)
	_active.append({"kind": "particles", "node": node, "t": -delay,
		"ttl": node.lifetime + delay, "lifetime": node.lifetime})
	var sub_light: Dictionary = p.get("light", {})
	if not sub_light.is_empty():
		_play_light(pos, color, sub_light, scale, 0.0)
	var sub := String(p.get("sub", ""))
	if sub != "" and not registry.blueprint(sub).is_empty():
		var sub_ctx := ctx.duplicate()
		sub_ctx["scale"] = scale
		play(sub, sub_ctx)


# ═══════════════════════════════════════════════════════
#  遊戲內入口
# ═══════════════════════════════════════════════════════
## 曳光彈（從槍口到命中點）
func tracer(from: Vector3, to: Vector3, res: Dictionary, width: float = 1.0) -> void:
	var fx: Dictionary = res.get("fx", {})
	var color := SkinRegistry.hex_color(fx.get("tracer_color", "#ffe6a0"), Color(1, 0.9, 0.6))
	var style := String(fx.get("tracer_style", "bolt"))
	var thick := maxf(0.006, 0.016 * width * (1.3 if style == "ribbon" else 1.0))
	var delta := to - from
	var dist := delta.length()
	if dist < 0.02:
		return
	if not _acquire_slot("billboard"):
		return
	var ttl := clampf(dist * 0.006, 0.05, 0.16)
	_spawn_tracer_bar(from, delta, dist, thick, color, ttl, 0.85, 0.0)
	if style == "ribbon":
		_spawn_tracer_bar(from, delta, dist, thick * 1.9, color, ttl * 1.25, 0.32, PI * 0.5)
	if bool(fx.get("tracer_extra", false)):
		_spawn_tracer_bar(from, delta, dist * 0.92, thick * 2.6,
			SkinRegistry.mix_white(color, 0.35), ttl * 1.6, 0.16, PI * 0.25)


func _spawn_tracer_bar(from: Vector3, delta: Vector3, dist: float, thick: float,
		color: Color, ttl: float, alpha: float, roll: float) -> void:
	var node: MeshInstance3D = _take("billboard")
	if node == null:
		_release_slot("billboard")
		return
	var mesh := CylinderMesh.new()
	mesh.top_radius = thick
	mesh.bottom_radius = thick
	mesh.height = dist
	mesh.radial_segments = 6
	mesh.rings = 1
	node.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.albedo_color = Color(color.r, color.g, color.b, alpha)
	mat.emission_enabled = true
	mat.emission = color
	mat.emission_energy_multiplier = 3.2
	node.material_override = mat
	node.global_position = from + delta * 0.5
	var dir := delta.normalized()
	var up := Vector3.UP if absf(dir.dot(Vector3.UP)) < 0.98 else Vector3.RIGHT
	var xa := up.cross(dir).normalized()
	if roll != 0.0:
		xa = xa.rotated(dir, roll)
	node.global_basis = Basis(xa, dir, xa.cross(dir).normalized())
	add_child(node)
	_active.append({"kind": "tracer", "node": node, "mat": mat, "t": 0.0, "ttl": ttl,
		"alpha0": alpha})


## 兼容舊 API：main.gd 以名字觸發（muzzle_flash / hit_marker / kill_confirm …）
func spawn(name: String, world_pos: Vector3, normal: Vector3 = Vector3.UP) -> void:
	if registry == null:
		return
	var mapped := name
	match name:
		"muzzle_flash":
			mapped = registry.muzzle_blueprint(_skin_res)
		"impact", "bullet_impact":
			mapped = registry.impact_blueprint(_skin_res)
		"kill_confirm":
			mapped = registry.kill_blueprint(_skin_res)
	play(mapped, {"impact": world_pos, "normal": normal,
		"muzzle": Transform3D(Basis.IDENTITY, world_pos)})


func spawn_preset(preset: String, world_pos: Vector3, ctx: Dictionary = {}) -> void:
	var color := SkinRegistry.hex_color(
		_skin_res.get("fx", {}).get("muzzle_color", "#ffd9a0"), Color(1, 0.85, 0.6))
	_emit_particles(preset, world_pos, color, float(ctx.get("scale", 1.0)), ctx, 0.0)


## 開槍總入口：槍口 + 曳光（命中特效由 ballistics 事件驅動）
func fire(muzzle_xform: Transform3D, aim_dir: Vector3, impact: Dictionary,
		res: Dictionary, is_knife: bool = false) -> void:
	if registry == null:
		return
	var scale := float(res.get("fx", {}).get("muzzle_scale", 1.0))
	var ctx := {
		"muzzle": muzzle_xform,
		"impact": impact.get("point", muzzle_xform.origin + aim_dir * 40.0),
		"normal": impact.get("normal", Vector3.UP),
		"dir": aim_dir,
		"res": res,
		"eject": muzzle_xform.origin + aim_dir * 0.05 + muzzle_xform.basis.x * 0.05,
		"tracer_from": muzzle_xform.origin + aim_dir * 0.32,
		"scale": scale,
	}
	if is_knife:
		var slash_color := SkinRegistry.hex_color(
			res.get("fx", {}).get("kill_color", "#ffdd66"), Color(1, 0.87, 0.4))
		_play_mesh("slash_arc", Vector3(ctx["impact"]), slash_color,
			{"scale": 1.3, "ttl": 0.22}, 1.0, ctx)
		return
	play(registry.muzzle_blueprint(res), ctx)
	tracer(Vector3(ctx["tracer_from"]), Vector3(ctx["impact"]), res,
		float(res.get("fx", {}).get("tracer_width", 1.0)))
	var impact_pt: Vector3 = ctx["impact"]
	if bool(res.get("flags", {}).get("particles_always", false)):
		_emit_particles("ember_float", impact_pt,
			SkinRegistry.hex_color(res.get("fx", {}).get("impact_color", "#ffcf8a"), Color(1, 0.8, 0.5)),
			scale * 0.8, ctx, 0.05)


# ═══════════════════════════════════════════════════════
#  生命週期
# ═══════════════════════════════════════════════════════
func _process(delta: float) -> void:
	_time += delta
	var i := _active.size()
	while i > 0:
		i -= 1
		var e: Dictionary = _active[i]
		e["t"] = float(e["t"]) + delta
		var t := float(e["t"])
		var node: Node = e.get("node", null)
		if node == null or not is_instance_valid(node):
			_release_slot(String(e.get("kind", "mesh")))
			_active.remove_at(i)
			continue
		if t < 0.0:
			continue
		var kind := String(e.get("kind", "mesh"))
		match kind:
			"light":
				var nl: OmniLight3D = node
				var k := clampf(1.0 - t / float(e["ttl"]), 0.0, 1.0)
				nl.omni_energy = float(e.get("energy0", 3.0)) * pow(k, 2.0)
			"mesh":
				var nmi: MeshInstance3D = node
				var mm: StandardMaterial3D = e.get("mat", null)
				if mm != null:
					var k := clampf(t / float(e["ttl"]), 0.0, 1.0)
					var a := 1.0 - k
					match String(e.get("fade", "quad_out")):
						"linear":
							a = 1.0 - k
						"hold":
							a = 1.0 if k < 0.6 else (1.0 - k) * 2.5
						_:
							a = pow(1.0 - k, 1.7)
					var grow := float(e.get("grow", 3.0))
					var sc := float(e.get("sc0", 1.0)) * lerpf(0.4, grow, ease(k, 0.6))
					nmi.scale = Vector3(sc, sc, sc)
					mm.albedo_color.a = float(e.get("alpha0", 0.9)) * a
					mm.emission_energy_multiplier = (2.2 + grow * 0.45) * a
			"tracer":
				var tm: StandardMaterial3D = e.get("mat", null)
				if tm != null:
					var ka := clampf(1.0 - t / float(e["ttl"]), 0.0, 1.0)
					tm.albedo_color.a = float(e.get("alpha0", 0.85)) * pow(ka, 1.3)
			_:
				pass
		if t >= float(e["ttl"]):
			if kind == "decal":
				if is_instance_valid(node):
					node.queue_free()
			else:
				if kind == "particles":
					_set(node, "emitting", false)
				_release(kind, node)
			_release_slot(kind)
			_active.remove_at(i)
	# 彈孔淡出
	for dd in _decals:
		var d: Dictionary = dd
		d["age"] = float(d["age"]) + delta
		var dm: StandardMaterial3D = d.get("mat", null)
		var tt := float(d["age"]) / maxf(0.5, float(d.get("ttl", 12.0)))
		if dm != null and tt > 0.85:
			dm.albedo_color.a = float(d["alpha0"]) * clampf(1.0 - (tt - 0.85) * 6.6, 0.0, 1.0)
