class_name SkinRegistry
extends RefCounted

## 槍皮目錄載入器（資料驅動，來源 = tools/cli.py skins 產生的 res://assets/skins/skins.json）
##
## 這裡是「工具鏈 → 遊戲」的接合點：
##   * collections / skins / tiers / texture_spec / effects 全部來自同一份 JSON，
##     所以遊戲內模型、軍械庫 UI、網頁展示台看到的是同一套設定（顏色、特效、花紋）。
##   * resolve() 把「皮膚 + Chroma 色板 + 輻射點升級等級」算成最終的
##     colorway / fx 參數，渲染層只認這個結果。

const CATALOG_PATH := "res://assets/skins/skins.json"

var ready := false
var load_error := ""
var version := 1

var tiers: Dictionary = {}                    # tier key -> {label, color, base_price, glow}
var tier_order: Array = []
var weapons: Array = []                       # 有皮膚可換的武器鍵
var weapon_labels: Dictionary = {}            # weapon key -> 顯示名
var collections: Array = []                   # [collection dict]
var skins: Array = []                         # [skin dict]
var texture_spec: Dictionary = {}        # 程序貼圖常數（= tools/skins/emit.TEX）
var effects: Dictionary = {}           # 特效庫（particles/sprites/decals/blueprints）

var _by_id: Dictionary = {}
var _by_weapon: Dictionary = {}               # weapon key -> [skin dict]
var _by_collection: Dictionary = {}           # collection id -> [skin dict]
var _collection_by_id: Dictionary = {}

# 依武器鍵回退（當皮肤與武器不完全對應時）
const WEAPON_FALLBACK := {
	"vandal": "phantom", "phantom": "vandal", "guardian": "bulldog",
	"bulldog": "guardian", "spectre": "stinger", "stinger": "spectre",
	"sheriff": "ghost", "ghost": "classic", "classic": "ghost",
	"operator": "marshal", "marshal": "operator", "ares": "odin",
	"odin": "ares", "bucky": "judge", "judge": "bucky",
	"bandit": "shorty", "shorty": "bandit", "outlaw": "marshal",
	"knife": "knife",
}


static var _shared: SkinRegistry = null


static func shared() -> SkinRegistry:
	if _shared == null:
		_shared = SkinRegistry.new()
		_shared.load_catalog()
	return _shared


static func reset_shared() -> void:
	_shared = null


func load_catalog(path: String = "") -> bool:
	if ready:
		return true
	var file := path if path != "" else CATALOG_PATH
	if not FileAccess.file_exists(file):
		load_error = "找不到 %s（請先執行 python3 -m tools.cli skins && python3 -m tools.cli godot）" % file
		push_warning("[SkinRegistry] " + load_error)
		return false
	var text := FileAccess.get_file_as_string(file)
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		load_error = "JSON 解析失敗"
		return false
	var data: Dictionary = parsed
	version = int(data.get("version", 1))
	tiers = data.get("tiers", {})
	tier_order = data.get("tier_order", [])
	weapons = data.get("weapons", [])
	weapon_labels = data.get("weapon_labels", {})
	collections = data.get("collections", [])
	skins = data.get("skins", [])
	texture_spec = data.get("texture_spec", {})
	effects = data.get("effects", {})
	for c in collections:
		_collection_by_id[String(c.get("id", ""))] = c
		_by_collection[String(c.get("id", ""))] = []
	for s in skins:
		var id := String(s.get("id", ""))
		_by_id[id] = s
		var wkey := String(s.get("weapon", "phantom"))
		if not _by_weapon.has(wkey):
			_by_weapon[wkey] = []
		_by_weapon[wkey].append(s)
		var coll := String(s.get("collection", ""))
		if _by_collection.has(coll):
			_by_collection[coll].append(s)
	ready = true
	return true


# ─── 查詢 ────────────────────────────────────────────────
func skin(id: String) -> Dictionary:
	return _by_id.get(id, {})


func has_skin(id: String) -> bool:
	return _by_id.has(id)


func skin_ids() -> Array:
	return _by_id.keys()


func skins_for_weapon(weapon_key: String) -> Array:
	return _by_weapon.get(weapon_key, [])


func skins_for_collection(coll_id: String) -> Array:
	return _by_collection.get(coll_id, [])


func collection(coll_id: String) -> Dictionary:
	return _collection_by_id.get(coll_id, {})


func tier_info(tier: String) -> Dictionary:
	return tiers.get(tier, {"label": tier, "color": "#8f96a3", "glow": 0.0})


func tier_color(tier: String) -> Color:
	return hex_color(String(tier_info(tier).get("color", "#8f96a3")))


## 该武器預設皮膚（未購買時顯示的「制式」皮）
func default_skin_for(weapon_key: String) -> Dictionary:
	for s in skins_for_weapon(weapon_key):
		if String(s.get("tier", "")) == "standard":
			return s
	var arr: Array = skins_for_weapon(weapon_key)
	return arr[0] if not arr.is_empty() else {}


## 依「武器鍵 + 可選的 legacy weapon_id」找出可用皮膚清單（含退回件）
func skin_for(weapon_key: String, skin_id: String) -> Dictionary:
	if skin_id != "" and _by_id.has(skin_id):
		var s: Dictionary = _by_id[skin_id]
		if String(s.get("weapon", "")) == weapon_key:
			return s
		# 同一系列的其他武器版本（保持「裝備了 Reaver」的整體感）
		var coll := String(s.get("collection", ""))
		for alt in skins_for_collection(coll):
			if String(alt.get("weapon", "")) == weapon_key:
				return alt
		if WEAPON_FALLBACK.has(weapon_key):
			for alt in skins_for_weapon(String(WEAPON_FALLBACK[weapon_key])):
				if String(alt.get("collection", "")) == coll:
					return alt
	return default_skin_for(weapon_key)


# ─── 特效資料（VFX）──────────────────────────────────────
func particles(preset: String) -> Dictionary:
	return effects.get("particles", {}).get(preset, {})


func blueprint(id: String) -> Dictionary:
	return effects.get("blueprints", {}).get(id, {})


func sprite(name: String) -> Dictionary:
	return effects.get("sprites", {}).get(name, {})


func decal(id: String) -> Dictionary:
	return effects.get("decals", {}).get(id, {})


func mesh_primitive(name: String) -> Dictionary:
	return effects.get("mesh_primitives", {}).get(name, {})


func style_presets(style: String) -> Array:
	var names: Array = effects.get("styles", {}).get(style, [])
	return names if not names.is_empty() else effects.get("styles", {}).get("default", [])


## slot（muzzle/tracer/impact/kill/smoke）+ style → 粒子預設名
func preset_for_slot(style: String, slot: String) -> String:
	if slot == "":
		return ""
	var base := "%s_%s" % [slot, style]
	if effects.get("particles", {}).has(base):
		return base
	var generic := "%s_default" % slot
	if effects.get("particles", {}).has(generic):
		return generic
	# 依樣式清單比對尾綴
	for p in style_presets(style):
		if String(p).begins_with(slot + "_"):
			return String(p)
	for p in style_presets("default"):
		if String(p).begins_with(slot + "_"):
			return String(p)
	return ""


# ─── 解析：皮膚 + Chroma + 升級等級 → 最終外觀 ───────────
## 回傳 {skin, colorway, fx, features, extras, level, max_level, chroma_index,
##        chroma_name, finish: {...}, banner, has_*}
func resolve(skin_id: String, opts: Dictionary = {}) -> Dictionary:
	var s: Dictionary = skin(skin_id)
	if s.is_empty():
		s = default_skin_for(String(opts.get("weapon", "phantom")))
	if s.is_empty():
		return {}
	var level := clampi(int(opts.get("level", 1)), 1, 5)
	var chroma_index := int(opts.get("chroma", 0))
	var cw: Dictionary = s.get("colorway", {})
	var chroma_list: Array = s.get("chroma", [])
	if chroma_index > 0 and chroma_index - 1 < chroma_list.size() and level >= 3:
		cw = chroma_list[chroma_index - 1]
	var fx: Dictionary = (s.get("fx", {}) as Dictionary).duplicate(true)
	var feats: Array = (s.get("features", []) as Array).duplicate()
	var extras: Array = (s.get("extras", []) as Array).duplicate()
	var tier_glow := float(s.get("tier_glow", 0.0))

	# 升級（Radianite）逐级強化：更亮的發光、额外特效層、槍飾、橫幅
	var gain := 1.0 + float(level - 1) * 0.16
	fx["emissive_scale"] = gain
	fx["light_energy"] = float(fx.get("light_energy", 4.0)) * gain
	if level >= 2:
		fx["tracer_extra"] = true
	if level >= 4:
		fx["kill_banner"] = true
		fx["sub_operate"] = true
	var upgrades: Array = s.get("upgrades", [])
	for u in upgrades:
		if int(u.get("level", 99)) <= level:
			var kind := String(u.get("kind", ""))
			if kind == "charm":
				fx["has_charm"] = true
			elif kind == "banner":
				fx["kill_banner"] = true
			elif kind == "finish":
				fx["chroma_available"] = true
			elif kind == "vfx":
				fx["tracer_extra"] = true
	# 特徵旗標（渲染層直接讀，免去字串比對）
	var flags := {
		"veins": feats.has("energy_veins") or feats.has("veins"),
		"aura": feats.has("aura") or feats.has("halo"),
		"charm": fx.get("has_charm", feats.has("charm")),
		"holo_sight": feats.has("holo_sight"),
		"breathing": feats.has("living_metal") or feats.has("dragon_breath"),
		"smoke_trail": feats.has("smoke_trail"),
		"particles_always": level >= 2 and tier_glow > 0.5,
	}

	return {
		"skin": s,
		"skin_id": String(s.get("id", "")),
		"collection": String(s.get("collection", "standard")),
		"weapon": String(s.get("weapon", "phantom")),
		"name": String(s.get("name", "")),
		"tier": String(s.get("tier", "standard")),
		"tier_color": hex_color(String(s.get("tier_color", "#8f96a3"))),
		"tier_glow": tier_glow,
		"level": level,
		"max_level": 1 + upgrades.size(),
		"chroma_index": chroma_index,
		"chroma_count": chroma_list.size() + 1,
		"chroma_name": String(cw.get("name", "")),
		"colorway": cw,
		"fx": fx,
		"features": feats,
		"extras": extras,
		"pattern": String(s.get("pattern", "solid")),
		"pattern_params": s.get("pattern_params", {}),
		"flags": flags,
		"inspect": String(s.get("inspect", "standard")),
		"legacy_weapon_id": int(s.get("legacy_weapon_id", -1)),
	}


static func hex_color(value: Variant, fallback := Color(0.6, 0.6, 0.6)) -> Color:
	if typeof(value) == TYPE_COLOR:
		return value
	var s := String(value)
	if s == "" or not s.begins_with("#"):
		return fallback
	var c := Color.from_string(s, fallback)
	return c


# ─── 小工具 ──────────────────────────────────────────────
static func lerp_color(a: Color, b: Color, t: float) -> Color:
	return Color(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t,
		(a.a + (b.a - a.a) * t))


static func mix_white(c: Color, t: float) -> Color:
	return lerp_color(c, Color(1, 1, 1), t)


static func shade(c: Color, k: float) -> Color:
	return Color(clampf(c.r * k, 0.0, 1.0), clampf(c.g * k, 0.0, 1.0),
		clampf(c.b * k, 0.0, 1.0), c.a)


## 決定這把槍開槍時要用哪個 blueprint（含升級/樣式微調）
func muzzle_blueprint(res: Dictionary) -> String:
	var fx: Dictionary = res.get("fx", {})
	var cand := String(fx.get("muzzle", "muzzle_default"))
	if blueprint(cand).is_empty():
		var style := String(fx.get("style", "default"))
		cand = "muzzle_" + style
	if blueprint(cand).is_empty():
		cand = "muzzle_default"
	return cand


func impact_blueprint(res: Dictionary) -> String:
	var fx: Dictionary = res.get("fx", {})
	var cand := String(fx.get("impact", "impact_default"))
	if blueprint(cand).is_empty():
		cand = "impact_" + String(fx.get("style", "default"))
	if blueprint(cand).is_empty():
		cand = "impact_default"
	return cand


func kill_blueprint(res: Dictionary) -> String:
	var fx: Dictionary = res.get("fx", {})
	var cand := String(fx.get("kill", "kill_default"))
	if blueprint(cand).is_empty():
		cand = "kill_" + String(fx.get("style", "default"))
	if blueprint(cand).is_empty():
		cand = "kill_default"
	return cand
