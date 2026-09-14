class_name SkinProgression
extends Node

## VANTA 皮膚進度系統 — 追蹤皮膚解鎖/取得/使用
## 解鎖方式：戰鬥通行證/商店購買/成就/等級獎勵

signal skin_unlocked(skin_id: String)
signal skin_equipped(weapon_id: int, skin_id: String)
signal xp_gained(amount: int, reason: String)

# ─── 玩家進度 ─────────────────────────────────────────────
var player_level: int = 1
var player_xp: int = 0
var player_vp: int = 5000  # 虛擬貨幣（Valorant Points）
var player_radianite: int = 200  # 升級材料

# ─── 已解鎖皮膚 ─────────────────────────────────────────────
var unlocked_skins: Array[String] = []  # ["reaver_phantom", "prime_vandal", ...]
var equipped_skins: Dictionary = {  # {weapon_id: skin_id}
	0: "",  # Phantom
	1: "",  # Vandal
	2: "",  # Ghost
	3: "",  # Classic
	4: "",  # Knife
}

# ─── 皮膚定義 ─────────────────────────────────────────────
# 每個皮膚的取得方式和價格
const SKIN_CATALOG: Dictionary = {
	# ═══ 標準皮膚（預設解鎖）═══
	"default_phantom": {"name": "標準 Phantom", "weapon": 0, "tier": "標準", "source": "預設", "price_vp": 0, "price_rad": 0},
	"default_vandal": {"name": "標準 Vandal", "weapon": 1, "tier": "標準", "source": "預設", "price_vp": 0, "price_rad": 0},
	"default_ghost": {"name": "標準 Ghost", "weapon": 2, "tier": "標準", "source": "預設", "price_vp": 0, "price_rad": 0},
	"default_classic": {"name": "標準 Classic", "weapon": 3, "tier": "標準", "source": "預設", "price_vp": 0, "price_rad": 0},
	"default_knife": {"name": "標準 匕首", "weapon": 4, "tier": "標準", "source": "預設", "price_vp": 0, "price_rad": 0},

	# ═══ 戰鬥通行證獎勵（免費）═══
	"bp_reaver_phantom": {"name": "掠奪者 Phantom", "weapon": 0, "tier": "傳說", "source": "戰鬥通行證 Lv.10", "price_vp": 0, "price_rad": 0, "bp_level": 10},
	"bp_prime_vandal": {"name": "貴族 Vandal", "weapon": 1, "tier": "傳說", "source": "戰鬥通行證 Lv.20", "price_vp": 0, "price_rad": 0, "bp_level": 20},
	"bp_sentinels_ghost": {"name": "光之哨兵 Ghost", "weapon": 2, "tier": "傳說", "source": "戰鬥通行證 Lv.30", "price_vp": 0, "price_rad": 0, "bp_level": 30},
	"bp_knife_gold": {"name": "黃金 匕首", "weapon": 4, "tier": "精英", "source": "戰鬥通行證 Lv.40", "price_vp": 0, "price_rad": 0, "bp_level": 40},

	# ═══ 等級獎勵 ═══
	"lvl_military_phantom": {"name": "軍規 Phantom", "weapon": 0, "tier": "標準", "source": "等級 5", "price_vp": 0, "price_rad": 0, "req_level": 5},
	"lvl_nova_vandal": {"name": "星塵 Vandal", "weapon": 1, "tier": "稀有", "source": "等級 10", "price_vp": 0, "price_rad": 0, "req_level": 10},
	"lvl_eclipse_ghost": {"name": "日蝕 Ghost", "weapon": 2, "tier": "稀有", "source": "等級 15", "price_vp": 0, "price_rad": 0, "req_level": 15},
	"lvl_punk_classic": {"name": "暴走 Classic", "weapon": 3, "tier": "稀有", "source": "等級 20", "price_vp": 0, "price_rad": 0, "req_level": 20},

	# ═══ 成就獎勵 ═══
	"ach_headshot_100": {"name": "神射手 Ghost", "weapon": 2, "tier": "精英", "source": "成就：100 次爆頭", "price_vp": 0, "price_rad": 0, "req_achievement": "headshot_100"},
	"ach_kill_500": {"name": "殺手 Phantom", "weapon": 0, "tier": "精英", "source": "成就：500 次擊殺", "price_vp": 0, "price_rad": 0, "req_achievement": "kill_500"},
	"ach_win_100": {"name": "勝利者 Vandal", "weapon": 1, "tier": "精英", "source": "成就：100 勝", "price_vp": 0, "price_rad": 0, "req_achievement": "win_100"},
	"ach_ace_10": {"name": "王牌 匕首", "weapon": 4, "tier": "傳說", "source": "成就：10 次 Ace", "price_vp": 0, "price_rad": 0, "req_achievement": "ace_10"},

	# ═══ 商店購買（VP）═══
	"shop_reaver_vandal": {"name": "掠奪者 Vandal", "weapon": 1, "tier": "傳說", "source": "商店", "price_vp": 1775, "price_rad": 0},
	"shop_prime_phantom": {"name": "貴族 Phantom", "weapon": 0, "tier": "傳說", "source": "商店", "price_vp": 1775, "price_rad": 0},
	"shop_sentinels_vandal": {"name": "光之哨兵 Vandal", "weapon": 1, "tier": "傳說", "source": "商店", "price_vp": 1775, "price_rad": 0},
	"shop_glitchpop_phantom": {"name": "源計畫 Phantom", "weapon": 0, "tier": "傳說", "source": "商店", "price_vp": 2175, "price_rad": 0},
	"shop_elderflame_vandal": {"name": "暗影之刃 Vandal", "weapon": 1, "tier": "傳說", "source": "商店", "price_vp": 2475, "price_rad": 0},
	"shop_dragontail_phantom": {"name": "龍炎 Phantom", "weapon": 0, "tier": "精英", "source": "商店", "price_vp": 1275, "price_rad": 0},
	"shop_winter_ghost": {"name": "冰霜幻影 Ghost", "weapon": 2, "tier": "精英", "source": "商店", "price_vp": 1275, "price_rad": 0},
	"shop_viper_classic": {"name": "毒素之牙 Classic", "weapon": 3, "tier": "精英", "source": "商店", "price_vp": 1275, "price_rad": 0},

	# ═══ 商店購買（Radianite）═══
	"rad_reaver_upgraded": {"name": "掠奪者 升級版", "weapon": 0, "tier": "傳說", "source": "Radianite 升級", "price_vp": 0, "price_rad": 30},
	"rad_prime_upgraded": {"name": "貴族 升級版", "weapon": 1, "tier": "傳說", "source": "Radianite 升級", "price_vp": 0, "price_rad": 30},

	# ═══ 夜市（隨機折扣）═══
	"night_phantom": {"name": "隨機 Phantom", "weapon": 0, "tier": "隨機", "source": "夜市", "price_vp": 887, "price_rad": 0, "discount": 0.5},
	"night_vandal": {"name": "隨機 Vandal", "weapon": 1, "tier": "隨機", "source": "夜市", "price_vp": 887, "price_rad": 0, "discount": 0.5},
	"night_ghost": {"name": "隨機 Ghost", "weapon": 2, "tier": "隨機", "source": "夜市", "price_vp": 637, "price_rad": 0, "discount": 0.5},
	"night_knife": {"name": "隨機 匕首", "weapon": 4, "tier": "隨機", "source": "夜市", "price_vp": 437, "price_rad": 0, "discount": 0.5}
}

# ─── 成就定義 ─────────────────────────────────────────────
const ACHIEVEMENTS: Dictionary = {
	"headshot_10": {"name": "初學射手", "desc": "10 次爆頭", "target": 10},
	"headshot_100": {"name": "神射手", "desc": "100 次爆頭", "target": 100},
	"headshot_500": {"name": "爆頭大師", "desc": "500 次爆頭", "target": 500},
	"kill_100": {"name": "新手殺手", "desc": "100 次擊殺", "target": 100},
	"kill_500": {"name": "殺手", "desc": "500 次擊殺", "target": 500},
	"kill_1000": {"name": "死神", "desc": "1000 次擊殺", "target": 1000},
	"win_10": {"name": "勝利者", "desc": "10 勝", "target": 10},
	"win_50": {"name": "常勝軍", "desc": "50 勝", "target": 50},
	"win_100": {"name": "傳說勝者", "desc": "100 勝", "target": 100},
	"ace_1": {"name": "Ace 新手", "desc": "1 次 Ace", "target": 1},
	"ace_10": {"name": "Ace 專家", "desc": "10 次 Ace", "target": 10},
	"clutch_1": {"name": "Clutch 新手", "desc": "1 次 Clutch", "target": 1},
	"clutch_10": {"name": "Clutch 專家", "desc": "10 次 Clutch", "target": 10},
	"play_100": {"name": "忠實玩家", "desc": "100 場對戰", "target": 100},
	"play_500": {"name": "資深玩家", "desc": "500 場對戰", "target": 500}
}

var achievement_progress: Dictionary = {}  # {achievement_id: current_count}


func _ready() -> void:
	_load_data()
	_unlock_defaults()


func _unlock_defaults() -> void:
	"""解鎖預設皮膚"""
	for skin_id in SKIN_CATALOG:
		var skin: Dictionary = SKIN_CATALOG[skin_id]
		if skin["source"] == "預設" and skin_id not in unlocked_skins:
			unlocked_skins.append(skin_id)


# ─── 經驗值系統 ─────────────────────────────────────────────
func add_xp(amount: int, reason: String = "") -> void:
	"""增加經驗值"""
	player_xp += amount
	xp_gained.emit(amount, reason)

	# 檢查升級
	var xp_needed := _xp_for_level(player_level + 1)
	while player_xp >= xp_needed:
		player_xp -= xp_needed
		player_level += 1
		_check_level_rewards()
		xp_needed = _xp_for_level(player_level + 1)

	_save_data()


func _xp_for_level(level: int) -> int:
	"""計算升級所需經驗值"""
	return 1000 + (level - 1) * 200  # 逐漸增加


func _check_level_rewards() -> void:
	"""檢查等級獎勵"""
	for skin_id in SKIN_CATALOG:
		var skin: Dictionary = SKIN_CATALOG[skin_id]
		if skin.has("req_level") and skin["req_level"] <= player_level:
			if skin_id not in unlocked_skins:
				unlocked_skins.append(skin_id)
				skin_unlocked.emit(skin_id)


# ─── 成就系統 ─────────────────────────────────────────────
func unlock_achievement(achievement_id: String) -> void:
	"""解鎖成就"""
	if not ACHIEVEMENTS.has(achievement_id):
		return
	if not achievement_progress.has(achievement_id):
		achievement_progress[achievement_id] = 0
	achievement_progress[achievement_id] += 1

	var achievement: Dictionary = ACHIEVEMENTS[achievement_id]
	if achievement_progress[achievement_id] >= achievement["target"]:
		_check_achievement_rewards(achievement_id)

	_save_data()


func _check_achievement_rewards(achievement_id: String) -> void:
	"""檢查成就獎勵"""
	for skin_id in SKIN_CATALOG:
		var skin: Dictionary = SKIN_CATALOG[skin_id]
		if skin.has("req_achievement") and skin["req_achievement"] == achievement_id:
			if skin_id not in unlocked_skins:
				unlocked_skins.append(skin_id)
				skin_unlocked.emit(skin_id)


# ─── 商店購買 ─────────────────────────────────────────────
func buy_skin_vp(skin_id: String) -> bool:
	"""用 VP 購買皮膚"""
	if not SKIN_CATALOG.has(skin_id):
		return false
	if skin_id in unlocked_skins:
		return false  # 已擁有

	var skin: Dictionary = SKIN_CATALOG[skin_id]
	var price: int = skin.get("price_vp", 0)
	if price <= 0:
		return false  # 非 VP 商品
	if player_vp < price:
		return false  # VP 不足

	player_vp -= price
	unlocked_skins.append(skin_id)
	skin_unlocked.emit(skin_id)
	_save_data()
	return true


func buy_skin_radianite(skin_id: String) -> bool:
	"""用 Radianite 購買皮膚"""
	if not SKIN_CATALOG.has(skin_id):
		return false
	if skin_id in unlocked_skins:
		return false

	var skin: Dictionary = SKIN_CATALOG[skin_id]
	var price: int = skin.get("price_rad", 0)
	if price <= 0:
		return false
	if player_radianite < price:
		return false

	player_radianite -= price
	unlocked_skins.append(skin_id)
	skin_unlocked.emit(skin_id)
	_save_data()
	return true


# ─── 裝備皮膚 ─────────────────────────────────────────────
func equip_skin(weapon_id: int, skin_id: String) -> bool:
	"""裝備皮膚"""
	if skin_id not in unlocked_skins:
		return false
	var skin: Dictionary = SKIN_CATALOG.get(skin_id, {})
	if skin.get("weapon", -1) != weapon_id:
		return false

	equipped_skins[weapon_id] = skin_id
	skin_equipped.emit(weapon_id, skin_id)
	_save_data()
	return true


func get_equipped_skin(weapon_id: int) -> String:
	"""取得已裝備的皮膚"""
	return equipped_skins.get(weapon_id, "")


func get_skin_info(skin_id: String) -> Dictionary:
	"""取得皮膚資訊"""
	return SKIN_CATALOG.get(skin_id, {})


func is_skin_unlocked(skin_id: String) -> bool:
	"""檢查皮膚是否已解鎖"""
	return skin_id in unlocked_skins


func get_skins_for_weapon(weapon_id: int) -> Array[String]:
	"""取得某武器的所有皮膚"""
	var result: Array[String] = []
	for skin_id in SKIN_CATALOG:
		var skin: Dictionary = SKIN_CATALOG[skin_id]
		if skin["weapon"] == weapon_id:
			result.append(skin_id)
	return result


func get_unlocked_skins_for_weapon(weapon_id: int) -> Array[String]:
	"""取得某武器已解鎖的皮膚"""
	var result: Array[String] = []
	for skin_id in unlocked_skins:
		var skin: Dictionary = SKIN_CATALOG.get(skin_id, {})
		if skin.get("weapon", -1) == weapon_id:
			result.append(skin_id)
	return result


# ─── 夜市系統 ─────────────────────────────────────────────
func get_night_market_skins() -> Array[Dictionary]:
	"""取得夜市隨機皮膚（每天刷新）"""
	var today := Time.get_date_dict_from_system()
	var seed: int = int(today["year"]) * 10000 + int(today["month"]) * 100 + int(today["day"])
	var rng := RandomNumberGenerator.new()
	rng.seed = seed

	var available: Array[String] = []
	for skin_id in SKIN_CATALOG:
		var skin: Dictionary = SKIN_CATALOG[skin_id]
		if skin["source"] == "夜市" and skin_id not in unlocked_skins:
			available.append(skin_id)

	# 隨機選 4 個
	var result: Array[Dictionary] = []
	available.shuffle()
	for i in range(mini(4, available.size())):
		var skin_id: String = available[i]
		var skin: Dictionary = SKIN_CATALOG[skin_id].duplicate()
		skin["id"] = skin_id
		result.append(skin)

	return result


# ─── 戰鬥通行證 ─────────────────────────────────────────────
func check_battle_pass_reward(bp_level: int) -> String:
	"""檢查戰鬥通行證獎勵"""
	for skin_id in SKIN_CATALOG:
		var skin: Dictionary = SKIN_CATALOG[skin_id]
		if skin.has("bp_level") and skin["bp_level"] == bp_level:
			if skin_id not in unlocked_skins:
				unlocked_skins.append(skin_id)
				skin_unlocked.emit(skin_id)
				return skin_id
	return ""


# ─── 統計 ─────────────────────────────────────────────
func get_unlock_count() -> int:
	return unlocked_skins.size()


func get_total_skins() -> int:
	return SKIN_CATALOG.size()


func get_completion_rate() -> float:
	if SKIN_CATALOG.is_empty():
		return 0.0
	return float(get_unlock_count()) / float(get_total_skins()) * 100.0


# ─── 持久化 ─────────────────────────────────────────────
func _save_data() -> void:
	var data := {
		"level": player_level,
		"xp": player_xp,
		"vp": player_vp,
		"radianite": player_radianite,
		"unlocked": unlocked_skins,
		"equipped": equipped_skins,
		"achievements": achievement_progress
	}
	var file := FileAccess.open("user://skin_progression.json", FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(data, "\t"))
		file.close()


func _load_data() -> void:
	var file := FileAccess.open("user://skin_progression.json", FileAccess.READ)
	if not file:
		return
	var json := JSON.new()
	var err := json.parse(file.get_as_text())
	file.close()
	if err != OK:
		return
	var data: Dictionary = json.data
	player_level = data.get("level", 1)
	player_xp = data.get("xp", 0)
	player_vp = data.get("vp", 5000)
	player_radianite = data.get("radianite", 200)
	unlocked_skins = data.get("unlocked", [])
	equipped_skins = data.get("equipped", {})
	achievement_progress = data.get("achievements", {})
