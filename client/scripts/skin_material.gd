class_name SkinMaterial
extends RefCounted

## 由「解析後的皮膚」建置武器材質組（role → Material）。
##
## 設計重點（品質來源）：
##   1. 花紋貼圖 + 邊緣發光 → 高級皮的重點是「光沿紋路走」，不是整片自發光。
##   2. 每個零件依 `WeaponGeometry` 的 role 使用不同金屬度/粗糙度（機加工金屬、
##      聚合物底殼、光學鏡片、握把橡膠），所以皮膚換上去後仍然有材質差異。
##   3. `next_pass` 疊加一層「能量紋」著色器（有 `energy_veins` / `aura` / 虹彩時），
##      讓槍身在移動與開槍後有緩慢流動的光；著色器缺失時自動退回純 StandardMaterial3D。
##   4. 等級（Radianite）直接反映在發光強度、粒子/拖尾、槍飾與鏡片光暈上。

const SHADER_AURA := "res://shaders/skin_aura.gdshader"

static var _prop_cache: Dictionary = {}


static func build(res: Dictionary, spec: Dictionary, opts: Dictionary = {}) -> Dictionary:
	var out := {}
	if res.is_empty():
		return out
	var cw: Dictionary = res.get("colorway", {})
	var fx: Dictionary = res.get("fx", {})
	var flags: Dictionary = res.get("flags", {})
	var level := int(res.get("level", 1))
	var tier_glow := float(res.get("tier_glow", 0.0))
	var emis_scale := float(fx.get("emissive_scale", 1.0))

	var primary := SkinRegistry.hex_color(cw.get("primary", "#2b2f38"), Color(0.17, 0.18, 0.22))
	var secondary := SkinRegistry.hex_color(cw.get("secondary", "#171a20"), Color(0.09, 0.10, 0.13))
	var accent := SkinRegistry.hex_color(cw.get("accent", "#ff7a35"), Color(1, 0.48, 0.21))
	var emis := SkinRegistry.hex_color(cw.get("emissive", "#ff9d4d"), Color(1, 0.62, 0.30))
	var rim := SkinRegistry.hex_color(cw.get("rim_color", "#ffffff"), Color(1, 1, 1))

	var metalness := float(cw.get("metalness", 0.55))
	var roughness := float(cw.get("roughness", 0.38))
	var clearcoat := float(cw.get("clearcoat", 0.0))
	var iridescence := float(cw.get("iridescence", 0.0))
	var emis_strength := float(cw.get("emissive_strength", 0.0))
	var rim_strength := float(cw.get("rim_strength", 0.0))

	var want_tex := bool(opts.get("textures", true))
	var tex_size := int(opts.get("texture_size", ProceduralTexture.SIZE_VIEWMODEL))
	var maps := {}
	if want_tex:
		maps = ProceduralTexture.textures_for(res, spec, tex_size)
	var albedo_tex: Texture2D = maps.get("albedo", null)
	var emissive_tex: Texture2D = maps.get("emissive", null)
	var normal_tex: Texture2D = maps.get("normal", null)

	var uv_density := float(opts.get("uv_density", 1.0))
	var use_aura := (bool(flags.get("veins", false)) or bool(flags.get("aura", false))
		or iridescence > 0.05 or emis_strength > 1.2)

	var shared := {
		"albedo_tex": albedo_tex, "emissive_tex": emissive_tex, "normal_tex": normal_tex,
		"uv_density": uv_density, "emis_strength": emis_strength, "level": level,
		"tier_glow": tier_glow, "rim": rim, "rim_strength": rim_strength,
		"clearcoat": clearcoat, "iridescence": iridescence,
		"texture_spec": spec, "aura": use_aura, "emis_scale": emis_scale,
	}

	out["body"] = _material(primary, 0.34, metalness, roughness, emis, shared, "body")
	out["moving"] = _material(SkinRegistry.shade(primary, 0.82), 0.40,
		minf(1.0, metalness + 0.28), maxf(0.12, roughness - 0.14), emis, shared, "moving")
	out["metal"] = _material(SkinRegistry.mix_white(SkinRegistry.shade(secondary, 1.35), 0.18),
		0.52, minf(1.0, metalness + 0.42), 0.26, SkinRegistry.shade(emis, 0.5), shared, "metal")
	out["grip"] = _material(SkinRegistry.shade(secondary, 1.05), 0.10,
		maxf(0.02, metalness * 0.25), minf(1.0, roughness + 0.34), Color.BLACK, shared, "grip")
	out["optic"] = _material(SkinRegistry.shade(primary, 0.55), 0.12,
		0.90, 0.10, emis, shared, "optic")
	out["lens"] = _material(SkinRegistry.shade(emis, 0.35), 0.05, 0.0, 0.04,
		emis, shared, "lens")
	out["accent"] = _material(accent, 0.65, minf(0.9, metalness + 0.1),
		maxf(0.10, roughness - 0.10), accent, shared, "accent")
	out["blade"] = _material(SkinRegistry.mix_white(SkinRegistry.shade(accent, 1.1), 0.45),
		0.30, 1.0, 0.12, SkinRegistry.shade(emis, 0.7), shared, "blade")
	out["mag"] = _material(SkinRegistry.shade(primary, 0.72), 0.30,
		metalness, minf(1.0, roughness + 0.08), SkinRegistry.shade(emis, 0.6), shared, "mag")
	out["glow"] = _glow_material(emis, rim, emis_strength, level)
	out["shell"] = _shell_material(fx)
	out["_meta"] = {"skin_id": res.get("skin_id", ""), "level": level,
		"texture_size": tex_size, "has_texture": albedo_tex != null}
	return out


## 單一 role 的材質。`tex_mix` 決定花紋對該零件的影響強度。
static func _material(base: Color, tex_mix: float, metal: float, rough: float,
		emis_col: Color, shared: Dictionary, role: String) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.albedo_color = base
	var albedo_tex: Texture2D = shared.get("albedo_tex", null)
	if albedo_tex != null and tex_mix > 0.01:
		m.albedo_texture = albedo_tex
		var dens: float = float(shared.get("uv_density", 1.0))
		m.uv1_scale = Vector3(dens, dens, dens)
	m.metallic = metal
	m.metallic_specular = clampf(0.55 + metal * 0.35, 0.0, 1.0)
	m.roughness = clampf(rough, 0.03, 1.0)
	var normal_tex: Texture2D = shared.get("normal_tex", null)
	if normal_tex != null:
		m.normal_enabled = true
		m.normal_texture = normal_tex
		m.normal_scale = float(shared.get("texture_spec", {}).get("normal_strength", 2.2)) * 0.5
	var emis_strength := float(shared.get("emis_strength", 0.0))
	var tier_glow := float(shared.get("tier_glow", 0.0))
	var level := int(shared.get("level", 1))
	var emis_scale := float(shared.get("emis_scale", 1.0))
	if emis_strength > 0.02 and role not in ["grip"]:
		m.emission_enabled = true
		m.emission = emis_col
		var e := emis_strength * emis_scale * (0.55 + 0.45 * tier_glow)
		if role == "body" or role == "mag":
			e *= 0.55
		elif role == "accent" or role == "lens":
			e *= 1.25
		elif role == "metal" or role == "moving":
			e *= 0.7
		e *= 1.0 + float(level - 1) * 0.10
		m.emission_energy_multiplier = e
		var emissive_tex: Texture2D = shared.get("emissive_tex", null)
		if emissive_tex != null:
			_try(m, "emission_texture", emissive_tex)
	if float(shared.get("rim_strength", 0.0)) > 0.02 or tier_glow > 0.5:
		m.rim_enabled = true
		var rim_base := SkinRegistry.hex_color(shared.get("rim", Color(1, 1, 1)), Color(1, 1, 1))
		m.rim = rim_base * (0.25 + 0.75 * tier_glow)
		m.rim_tint = 0.55
	var clearcoat := float(shared.get("clearcoat", 0.0))
	if clearcoat > 0.02:
		m.clearcoat_enabled = true
		m.clearcoat = clearcoat
		m.clearcoat_roughness = 0.08
	var irid := float(shared.get("iridescence", 0.0))
	if irid > 0.02:
		m.iridescence_enabled = true
		m.iridescence = irid
		_try(m, "iridescence_directionality", 0.4)
	if bool(shared.get("aura", false)) and (role == "body" or role == "moving"):
		m.next_pass = _aura_pass(emis_col, shared)
	return m


## 自發光疊加件（能量紋、光環、鏡片光暈）——加性混合、不受光
static func _glow_material(emis: Color, rim: Color, strength: float,
		level: int) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	# 進階級（拉帝安特升級）讓外圈往 rim 色偏，光暈不會一直是一個色調
	var glow_col := emis.lerp(rim, clampf(0.06 * float(level), 0.0, 0.36))
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	var col := SkinRegistry.mix_white(glow_col, 0.25)
	col.a = clampf(0.30 + 0.22 * float(level - 1) + strength * 0.10, 0.05, 0.95)
	m.albedo_color = col
	m.emission_enabled = true
	m.emission = col
	m.emission_energy_multiplier = 1.6 + strength * 0.8
	return m


## 彈殼（金／銅 + 開槍後餘溫發光）
static func _shell_material(fx: Dictionary) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = SkinRegistry.hex_color(fx.get("shell_color", "#c9a24a"), Color(0.79, 0.64, 0.29))
	m.metallic = 0.95
	m.metallic_specular = 0.8
	m.roughness = 0.22
	var glow := float(fx.get("shell_glow", 0.0))
	if glow > 0.02:
		m.emission_enabled = true
		m.emission = m.albedo_color
		m.emission_energy_multiplier = 1.2 + glow * 3.0
	return m


static func _aura_pass(emis: Color, shared: Dictionary) -> Material:
	var shader: Shader = null
	if ResourceLoader.exists(SHADER_AURA):
		shader = load(SHADER_AURA) as Shader
	if shader == null:
		return null
	var m := ShaderMaterial.new()
	m.render_priority = 2
	m.shader = shader
	m.set_shader_parameter("glow_color", Color(emis.r, emis.g, emis.b, 1.0))
	m.set_shader_parameter("intensity", clampf(0.35 + float(shared.get("emis_strength", 0.0)) * 0.22,
		0.1, 1.4))
	m.set_shader_parameter("flow_speed", 0.22 + 0.06 * int(shared.get("level", 1)))
	m.set_shader_parameter("pulse_speed", 1.15)
	m.set_shader_parameter("uv_scale", float(shared.get("uv_density", 1.0)) * 1.6)
	var tex: Texture2D = shared.get("emissive_tex", null)
	if tex != null:
		m.set_shader_parameter("pattern", tex)
	return m


## 安全設定屬性（不同渲染器/版本可能沒有該屬性時不報錯）
static func _try(obj: Object, prop: String, value: Variant) -> bool:
	var key := obj.get_class()
	if not _prop_cache.has(key):
		var names := {}
		for p in obj.get_property_list():
			names[String(p.name)] = true
		_prop_cache[key] = names
	if not (_prop_cache[key] as Dictionary).has(prop):
		return false
	obj.set(prop, value)
	return true
