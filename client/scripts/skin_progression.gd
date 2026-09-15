class_name SkinProgression
extends Node

## 玩家收藏 / 升級 / 貨幣（資料驅動版）
##
## 目錄本身來自工具鏈（`res://assets/skins.json`，140 支皮膚），這裡只負責
## 「誰拥有什麼、升級到幾等、用哪組 Chroma、花了多少 VP/Radianite」。
## 這樣做的好处：設計資料改一個 JSON 就全部生效（商店、軍械庫、遊戲內模型、
## 特效、HUD 橫幅都用同一個 resolve()），而存檔只寫 id + 等級。
##
## 公開 API 維持與舊版相容（workshop.gd 仍照舊呼叫），新增：
##   level_of / set_level / upgrade_with_radianite / chroma_count / set_chroma / resolve_current

signal skin_unlocked(skin_id: String)
signal skin_equipped(weapon_id: int, skin_id: String)
signal skin_upgraded(skin_id: String, level: int)
signal xp_gained(amount: int, reason: String)

const SAVE_PATH := "user://skin_progression.json"
const DAILY_ROTATE_DAYS := 3

var player_level: int = 1
var player_xp: int = 0
var player_vp: int = 5000
var player_radianite: int = 200

var unlocked_skins: Array[String] = []
var equipped_skins: Dictionary = {}          # {weapon_id(int): skin_id}
var skin_levels: Dictionary = {}             # {skin_id: 1..5}
var skin_chroma: Dictionary = {}             # {skin_id: chroma index（0 = 原版）}
var achievement_progress: Dictionary = {}

## 由 skins.json 建立；保留舊欄位（name/weapon/tier/source/price_vp/price_rad）
## 讓武器工坊與商店列表不用改也能跑。
var SKIN_CATALOG: Dictionary = {}

# 舊 skin_id → 新 id（存檔相容）
const LEGACY_ALIAS := {
	"default_phantom": "standard_phantom", "default_vandal": "standard_vandal",
	"default_ghost": "standard_ghost", "default_classic": "standard_classic",
	"default_knife": "standard_knife",
	"bp_reaver_phantom": "reaver_phantom", "bp_prime_vandal": "prime_vandal",
	"bp_sentinels_ghost": "sentinels_ghost", "bp_knife_gold": "reaver_knife",
	"shop_reaver_vandal": "reaver_vandal", "shop_prime_phantom": "prime_phantom",
	"shop_sentinels_vandal": "sentinels_vandal", "shop_glitchpop_phantom": "glitchpop_phantom",
	"shop_elderflame_vandal": "elderflame_vandal", "shop_dragontail_phantom": "dragontail_phantom",
	"shop_winter_ghost": "winterwunder_ghost", "shop_viper_classic": "reaver_classic",
	"rad_reaver_upgraded": "reaver_phantom", "rad_prime_upgraded": "prime_phantom",
}

# 少量「取得來源」中繼資料（工具鏈不管商店動線，這裡補齊舊 UI 需要的欄位）
const SOURCES := {
	"reaver_phantom": {"source": "戰鬥通行證", "bp_level": 10},
	"prime_vandal": {"source": "戰鬥通行證", "bp_level": 20},
	"sentinels_ghost": {"source": "戰鬥通行證", "bp_level": 30},
	"reaver_knife": {"source": "戰鬥通行證", "bp_level": 40},
}

const ACHIEVEMENTS: Dictionary = {
	"headshot_10": {"name": "初學射手", "desc": "10 次爆頭", "target": 10},
	"headshot_100": {"name": "神射手", "desc": "100 次爆頭", "target": 100},
	"headshot_500": {"name": "爆頭大師", "desc": "500 次爆頭", "target": 500},
	"kill_100": {"name": "開路先鋒", "desc": "100 次擊殺", "target": 100},
	"kill_500": {"name": "殺手", "desc": "500 次擊殺", "target": 500},
	"win_10": {"name": "隊友模範", "desc": "10 勝", "target": 10},
	"win_100": {"name": "勝利者", "desc": "100 勝", "target": 100},
	"ace_1": {"name": "王牌", "desc": "1 次 Ace", "target": 1},
	"ace_10": {"name": "王牌之王", "desc": "10 次 Ace", "target": 10},
	"knife_10": {"name": "近戰大師", "desc": "10 次匕首擊殺", "target": 10},
	"spike_25": {"name": "爆破專家", "desc": "25 次成功拆／下點", "target": 25},
	"first_blood_20": {"name": "先手", "desc": "20 次首殺", "target": 20},
}

const ACHIEVEMENT_REWARDS := {
	"headshot_100": "sentinels_classic",
	"kill_500": "reaver_spectre",
	"win_100": "prime_guardian",
	"ace_10": "glitchpop_knife",
}

var _registry: SkinRegistry = null
var _night_cache: Array[Dictionary] = []


func _ready() -> void:
	_registry = SkinRegistry.shared()
	_build_catalog()
	_load_data()
	_unlock_defaults()


func registry() -> SkinRegistry:
	if _registry == null:
		_registry = SkinRegistry.shared()
		_build_catalog()
	return _registry


func _build_catalog() -> void:
	SKIN_CATALOG.clear()
	if _registry == null or not _registry.ready:
		return
	for s in _registry.skins:
		var id := String(s.get("id", ""))
		var entry := {
			"name": String(s.get("name", "")),
			"weapon": int(s.get("legacy_weapon_id", 0)),
			"weapon_key": String(s.get("weapon", "")),
			"tier": String(s.get("tier_label", "")),
			"tier_key": String(s.get("tier", "")),
			"source": "商店",
			"price_vp": int(s.get("price_vp", 0)),
			"price_rad": 0,
			"collection": String(s.get("collection", "")),
			"collection_name": String(s.get("collection_name", "")),
			"skin": s,
		}
		if String(s.get("tier", "")) == "standard":
			entry["source"] = "預設"
			entry["price_vp"] = 0
		elif int(s.get("price_vp", 0)) == 0:
			entry["source"] = "奖励"
		if SOURCES.has(id):
			for k in SOURCES[id]:
				entry[k] = SOURCES[id][k]
		SKIN_CATALOG[id] = entry
		if not equipped_skins.has(entry["weapon"]):
			pass


func _unlock_defaults() -> void:
	if _registry == null:
		_registry = registry()
	for id in SKIN_CATALOG:
		if String(SKIN_CATALOG[id].get("source", "")) == "預設":
			if id not in unlocked_skins:
				unlocked_skins.append(id)
			if not skin_levels.has(id):
				skin_levels[id] = 1
	# 保底：新玩家給一支傳說皮體驗（提升「想玩」的動機）
	if unlocked_skins.size() <= 12:
		for demo in ["reaver_vandal", "prime_phantom"]:
			if SKIN_CATALOG.has(demo) and demo not in unlocked_skins:
				unlocked_skins.append(demo)
				skin_levels[demo] = 1
				equipped_skins[int(SKIN_CATALOG[demo]["weapon"])] = demo
	_save_data()


# ─── 经验 / 等級 ────────────────────────────────────────
func add_xp(amount: int, reason: String = "") -> void:
	player_xp += amount
	xp_gained.emit(amount, reason)
	while player_xp >= _xp_for_level(player_level + 1):
		player_xp -= _xp_for_level(player_level + 1)
		player_level += 1
		player_radianite += 10
		player_vp += 200
		_check_level_rewards()
	_save_data()


func _xp_for_level(level: int) -> int:
	return 400 + (level - 1) * 160


func _check_level_rewards() -> void:
	for id in SKIN_CATALOG:
		var info: Dictionary = SKIN_CATALOG[id]
		var req := int(info.get("req_level", 0))
		if req > 0 and player_level >= req and id not in unlocked_skins:
			unlocked_skins.append(id)
			skin_unlocked.emit(id)


func unlock_achievement(achievement_id: String) -> void:
	if not ACHIEVEMENTS.has(achievement_id):
		return
	achievement_progress[achievement_id] = int(achievement_progress.get(achievement_id, 0)) + 1
	if int(achievement_progress[achievement_id]) >= int(ACHIEVEMENTS[achievement_id]["target"]):
		_check_achievement_rewards(achievement_id)
	_save_data()


func _check_achievement_rewards(achievement_id: String) -> void:
	var reward := String(ACHIEVEMENT_REWARDS.get(achievement_id, ""))
	if reward != "" and SKIN_CATALOG.has(reward) and reward not in unlocked_skins:
		unlocked_skins.append(reward)
		skin_unlocked.emit(reward)


# ─── 購買 / 裝備 ────────────────────────────────────────
func _real_id(skin_id: String) -> String:
	return String(LEGACY_ALIAS.get(skin_id, skin_id))


func buy_skin_vp(skin_id: String) -> bool:
	var id := _real_id(skin_id)
	if not SKIN_CATALOG.has(id) or id in unlocked_skins:
		return false
	var price := int(SKIN_CATALOG[id].get("price_vp", 0))
	if player_vp < price:
		return false
	player_vp -= price
	unlocked_skins.append(id)
	skin_levels[id] = 1
	skin_chroma[id] = 0
	skin_unlocked.emit(id)
	_save_data()
	return true


## Radianite 升級：一次升一等（消耗該級定義的價格）
func upgrade_with_radianite(skin_id: String) -> bool:
	var id := _real_id(skin_id)
	if id not in unlocked_skins:
		return false
	var cost := upgrade_cost(id)
	if cost < 0 or player_radianite < cost:
		return false
	player_radianite -= cost
	skin_levels[id] = level_of(id) + 1
	skin_upgraded.emit(id, skin_levels[id])
	_save_data()
	return true


func buy_skin_radianite(skin_id: String) -> bool:
	return upgrade_with_radianite(skin_id)


func upgrade_cost(skin_id: String) -> int:
	var id := _real_id(skin_id)
	var nxt := level_of(id) + 1
	var s: Dictionary = _registry.skin(id) if _registry != null else {}
	for u in s.get("upgrades", []):
		if int(u.get("level", 0)) == nxt:
			return int(u.get("radianite", 20))
	return -1


func level_of(skin_id: String) -> int:
	var id := _real_id(skin_id)
	if id not in unlocked_skins:
		return 1
	return int(skin_levels.get(id, 1))


func max_level(skin_id: String) -> int:
	var id := _real_id(skin_id)
	var s: Dictionary = _registry.skin(id) if _registry != null else {}
	return 1 + int((s.get("upgrades", []) as Array).size())


func chroma_count(skin_id: String) -> int:
	var id := _real_id(skin_id)
	var s: Dictionary = _registry.skin(id) if _registry != null else {}
	return 1 + int((s.get("chroma", []) as Array).size())


func chroma_of(skin_id: String) -> int:
	return int(skin_chroma.get(_real_id(skin_id), 0))


func set_chroma(skin_id: String, index: int) -> void:
	var id := _real_id(skin_id)
	var cnt := chroma_count(id) - 1
	if cnt <= 0 or index < 0 or index > cnt:
		return
	if level_of(id) < 3:
		return                     # Chroma 需要先升級（與 Valorant 一致）
	skin_chroma[id] = index
	_save_data()


func set_level(skin_id: String, level: int) -> void:
	var id := _real_id(skin_id)
	skin_levels[id] = clampi(level, 1, max_level(id))
	_save_data()


func equip_skin(weapon_id: int, skin_id: String) -> bool:
	var id := _real_id(skin_id)
	if id == "":
		return false
	if id not in unlocked_skins and SKIN_CATALOG.has(id):
		if int(SKIN_CATALOG[id].get("price_vp", 0)) > 0:
			return false
	equipped_skins[weapon_id] = id
	skin_equipped.emit(weapon_id, id)
	_save_data()
	return true


func get_equipped_skin(weapon_id: int) -> String:
	return String(equipped_skins.get(weapon_id, ""))


## 目前這把武器該長什麼樣子（給 main.gd / 軍械庫 / 特效共用）
func resolve_current(weapon_key: String, weapon_id: int) -> Dictionary:
	if registry() == null or not _registry.ready:
		return {}
	var id := get_equipped_skin(weapon_id)
	return _registry.resolve(id, {"weapon": weapon_key,
		"level": level_of(id) if id != "" else 1,
		"chroma": chroma_of(id) if id != "" else 0})


func get_skin_info(skin_id: String) -> Dictionary:
	return SKIN_CATALOG.get(_real_id(skin_id), {})


func is_skin_unlocked(skin_id: String) -> bool:
	return _real_id(skin_id) in unlocked_skins


func get_skins_for_weapon(weapon_id: int) -> Array[String]:
	var out: Array[String] = []
	for id in SKIN_CATALOG:
		if int(SKIN_CATALOG[id].get("weapon", -1)) == weapon_id:
			out.append(id)
	out.sort()
	return out


func get_unlocked_skins_for_weapon(weapon_id: int) -> Array[String]:
	var out: Array[String] = []
	for id in get_skins_for_weapon(weapon_id):
		if id in unlocked_skins:
			out.append(id)
	return out


## 夜市：每 DAILY_ROTATE_DAYS 輪替，折扣 40-60%（以日期當亂數種子 → 全域一致）
func get_night_market_skins() -> Array[Dictionary]:
	if not _night_cache.is_empty():
		return _night_cache
	var out: Array[Dictionary] = []
	var days := int(Time.get_unix_time_from_system() / 86400.0)
	var seed_v := days / DAILY_ROTATE_DAYS
	var pool: Array[String] = []
	for id in SKIN_CATALOG:
		var tier := String(SKIN_CATALOG[id].get("tier_key", ""))
		if tier in ["premium", "ultra", "exclusive", "deluxe"]:
			if id not in unlocked_skins:
				pool.append(id)
	pool.sort()
	if pool.is_empty():
		return out
	var idx := int(abs(hash(str(seed_v)))) % pool.size()
	for k in range(4):
		var pick := pool[(idx + k * 7) % pool.size()]
		var info: Dictionary = SKIN_CATALOG[pick].duplicate()
		info["id"] = pick
		var disc := 0.4 + float((abs(hash(str(seed_v) + str(k))) % 21)) / 100.0
		info["discount"] = disc
		info["price_vp"] = int(float(int(SKIN_CATALOG[pick].get("price_vp", 0))) * (1.0 - disc))
		info["source"] = "夜市"
		out.append(info)
	_night_cache = out
	return out


func check_battle_pass_reward(bp_level: int) -> String:
	for id in SKIN_CATALOG:
		var bl := int(SKIN_CATALOG[id].get("bp_level", 0))
		if bl > 0 and bl <= bp_level and id not in unlocked_skins:
			unlocked_skins.append(id)
			skin_unlocked.emit(id)
			return id
	return ""


func get_unlock_count() -> int:
	return unlocked_skins.size()


func get_total_skins() -> int:
	return SKIN_CATALOG.size()


func get_completion_rate() -> float:
	var total := get_total_skins()
	if total == 0:
		return 0.0
	return float(unlocked_skins.size()) / float(total)


func claim_win_rewards(kills: int, headshots: int, won: bool) -> void:
	add_xp(120 + kills * 25 + headshots * 15, "match")
	player_radianite += 2 if won else 1
	for k in kills:
		unlock_achievement("kill_100")
	for k in headshots:
		unlock_achievement("headshot_10")
	if won:
		unlock_achievement("win_10")
	_save_data()


# ─── 存檔 ───────────────────────────────────────────────
func _save_data() -> void:
	var data := {
		"player_level": player_level, "player_xp": player_xp,
		"player_vp": player_vp, "player_radianite": player_radianite,
		"unlocked_skins": unlocked_skins, "equipped_skins": equipped_skins,
		"skin_levels": skin_levels, "skin_chroma": skin_chroma,
		"achievement_progress": achievement_progress,
	}
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(data, "  "))
		file.close()


func _load_data() -> void:
	if not FileAccess.file_exists(SAVE_PATH):
		return
	var file := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	var d: Dictionary = parsed
	player_level = int(d.get("player_level", player_level))
	player_xp = int(d.get("player_xp", player_xp))
	player_vp = int(d.get("player_vp", player_vp))
	player_radianite = int(d.get("player_radianite", player_radianite))
	var arr: Array = d.get("unlocked_skins", [])
	unlocked_skins.clear()
	for v in arr:
		var id := _real_id(String(v))
		if SKIN_CATALOG.is_empty() or SKIN_CATALOG.has(id):
			unlocked_skins.append(id)
	var eq: Dictionary = d.get("equipped_skins", {})
	equipped_skins.clear()
	for k in eq.keys():
		equipped_skins[int(k)] = _real_id(String(eq[k]))
	var lv: Dictionary = d.get("skin_levels", {})
	skin_levels.clear()
	for k in lv.keys():
		skin_levels[String(k)] = int(lv[k])
	var ch: Dictionary = d.get("skin_chroma", {})
	skin_chroma.clear()
	for k in ch.keys():
		skin_chroma[String(k)] = int(ch[k])
	achievement_progress = d.get("achievement_progress", {})
