class_name SocialSystem
extends Node

## VANTA 社交系統 — 好友/聊天/戰績/排位
## 本地模擬（可擴展為伺服器端同步）

signal friend_online(friend_id: String)
signal friend_offline(friend_id: String)
signal chat_message(sender: String, message: String, channel: String)
signal rank_updated(new_rank: String, rp: int)

# ─── 好友系統 ─────────────────────────────────────────────
var friends: Array[Dictionary] = []  # [{id, name, rank, online, last_seen}]
var friend_requests: Array[Dictionary] = []  # [{id, name, rank}]
var blocked_users: Array[String] = []

# ─── 聊天系統 ─────────────────────────────────────────────
var chat_channels: Dictionary = {
	"global": [],      # 全服聊天
	"party": [],       # 群組聊天
	"team": [],        # 隊伍聊天
	"whisper": [],     # 私聊
}
var max_chat_history := 100

# ─── 戰績系統 ─────────────────────────────────────────────
var stats: Dictionary = {
	"kills": 0,
	"deaths": 0,
	"assists": 0,
	"matches_played": 0,
	"matches_won": 0,
	"matches_lost": 0,
	"win_streak": 0,
	"best_win_streak": 0,
	"headshots": 0,
	"total_damage": 0,
	"spike_plants": 0,
	"spike_defuses": 0,
	"aces": 0,
	"clutches": 0,
	"first_bloods": 0,
	"agents_played": {},  # {agent_key: count}
	"weapons_kills": {},  # {weapon_key: count}
	"avg_combat_score": 0.0,
	"match_history": [],  # [{date, map, mode, result, score, kda, agents}]
}

# ─── 排位系統 ─────────────────────────────────────────────
var rank_tier: int = 0  # 0=未定級, 1=鐵, 2=銅, 3=銀, 4=金, 5=鉑, 6=鑽石, 7=不朽, 8=輻能
var rank_division: int = 1  # 1-3（鐵/銅/銀/金/鉑/鑽石）或 1-2（不朽/輻能）
var rank_points: int = 0  # 當前 RP
var rank_history: Array[Dictionary] = []  # [{date, tier, division, rp_change, result}]
var season: int = 1
var season_start_rp: int = 0

const RANK_NAMES := {
	0: "未定級",
	1: "鐵",
	2: "銅",
	3: "銀",
	4: "金",
	5: "鉑",
	6: "鑽石",
	7: "不朽",
	8: "輻能"
}

const RANK_COLORS := {
	0: Color(0.5, 0.5, 0.5),
	1: Color(0.4, 0.3, 0.2),
	2: Color(0.7, 0.4, 0.2),
	3: Color(0.75, 0.75, 0.8),
	4: Color(1.0, 0.85, 0.0),
	5: Color(0.0, 0.8, 1.0),
	6: Color(0.3, 0.5, 1.0),
	7: Color(0.7, 0.3, 1.0),
	8: Color(1.0, 0.2, 0.2)
}


func _ready() -> void:
	_load_data()
	_add_demo_friends()


func _add_demo_friends() -> void:
	"""添加示範好友（用於展示 UI）"""
	if friends.size() > 0:
		return
	friends = [
		{"id": "ai-01", "name": "AI-戰士", "rank": 4, "division": 2, "online": true, "last_seen": "線上"},
		{"id": "ai-02", "name": "AI-狙擊手", "rank": 3, "division": 1, "online": true, "last_seen": "線上"},
		{"id": "ai-03", "name": "AI-偵查員", "rank": 5, "division": 1, "online": false, "last_seen": "30 分鐘前"},
		{"id": "ai-04", "name": "AI-爆破手", "rank": 2, "division": 3, "online": false, "last_seen": "2 小時前"},
		{"id": "ai-05", "name": "AI-守衛者", "rank": 6, "division": 1, "online": true, "last_seen": "線上"},
	]


# ─── 好友操作 ─────────────────────────────────────────────
func add_friend(friend_id: String, friend_name: String, rank: int = 0) -> bool:
	"""發送好友邀請"""
	if friend_id in blocked_users:
		return false
	for f in friends:
		if f["id"] == friend_id:
			return false  # 已是好友
	friend_requests.append({
		"id": friend_id,
		"name": friend_name,
		"rank": rank
	})
	return true


func accept_friend(friend_id: String) -> bool:
	"""接受好友邀請"""
	for i in range(friend_requests.size()):
		if friend_requests[i]["id"] == friend_id:
			var req := friend_requests[i]
			friends.append({
				"id": req["id"],
				"name": req["name"],
				"rank": req["rank"],
				"division": 1,
				"online": true,
				"last_seen": "線上"
			})
			friend_requests.remove_at(i)
			_save_data()
			return true
	return false


func decline_friend(friend_id: String) -> bool:
	"""拒絕好友邀請"""
	for i in range(friend_requests.size()):
		if friend_requests[i]["id"] == friend_id:
			friend_requests.remove_at(i)
			return true
	return false


func remove_friend(friend_id: String) -> bool:
	"""移除好友"""
	for i in range(friends.size()):
		if friends[i]["id"] == friend_id:
			friends.remove_at(i)
			_save_data()
			return true
	return false


func block_user(user_id: String) -> void:
	"""封鎖用戶"""
	if user_id not in blocked_users:
		blocked_users.append(user_id)
		remove_friend(user_id)


func get_online_friends() -> Array[Dictionary]:
	"""取得在線好友"""
	return friends.filter(func(f): return f["online"])


func get_friend_count() -> int:
	return friends.size()


func get_online_count() -> int:
	return get_online_friends().size()


# ─── 聊天系統 ─────────────────────────────────────────────
func send_message(channel: String, message: String, sender: String = "thumb") -> void:
	"""發送聊天訊息"""
	if not chat_channels.has(channel):
		return
	var msg := {
		"sender": sender,
		"message": message,
		"time": Time.get_datetime_string_from_system()
	}
	chat_channels[channel].append(msg)
	# 限制歷史記錄長度
	if chat_channels[channel].size() > max_chat_history:
		chat_channels[channel].pop_front()
	chat_message.emit(sender, message, channel)


func get_messages(channel: String, limit: int = 50) -> Array:
	"""取得聊天訊息"""
	if not chat_channels.has(channel):
		return []
	var msgs: Array = chat_channels[channel]
	return msgs.slice(-limit)


func add_system_message(channel: String, message: String) -> void:
	"""添加系統訊息"""
	send_message(channel, "[系統] " + message, "SYSTEM")


# ─── 戰績系統 ─────────────────────────────────────────────
func record_match(result: String, score_a: int, score_b: int, mode: String,
				map_name: String, agent: String, kills: int, deaths: int, assists: int) -> void:
	"""記錄對戰結果"""
	stats["matches_played"] += 1
	stats["kills"] += kills
	stats["deaths"] += deaths
	stats["assists"] += assists

	if result == "win":
		stats["matches_won"] += 1
		stats["win_streak"] += 1
		stats["best_win_streak"] = max(stats["best_win_streak"], stats["win_streak"])
	else:
		stats["matches_lost"] += 1
		stats["win_streak"] = 0

	# 記錄 Agent 使用次數
	if not stats["agents_played"].has(agent):
		stats["agents_played"][agent] = 0
	stats["agents_played"][agent] += 1

	# 計算戰鬥評分
	var kda: float = (kills + assists * 0.5) / max(1.0, float(deaths))
	stats["avg_combat_score"] = (stats["avg_combat_score"] * (stats["matches_played"] - 1) + kda * 100) / stats["matches_played"]

	# 記錄歷史
	stats["match_history"].append({
		"date": Time.get_datetime_string_from_system(),
		"map": map_name,
		"mode": mode,
		"result": result,
		"score": "%d-%d" % [score_a, score_b],
		"kda": "%d/%d/%d" % [kills, deaths, assists],
		"agent": agent
	})

	# 限制歷史記錄
	if stats["match_history"].size() > 100:
		stats["match_history"] = stats["match_history"].slice(-100)

	_save_data()


func get_kda() -> Dictionary:
	"""取得 KDA 統計"""
	var k := float(stats["kills"])
	var d := float(stats["deaths"])
	var a := float(stats["assists"])
	var ratio: float = (k + a * 0.5) / max(1.0, d)
	return {
		"kills": stats["kills"],
		"deaths": stats["deaths"],
		"assists": stats["assists"],
		"ratio": ratio,
		"display": "%d/%d/%d (%.2f)" % [stats["kills"], stats["deaths"], stats["assists"], ratio]
	}


func get_win_rate() -> float:
	"""取得勝率"""
	if stats["matches_played"] == 0:
		return 0.0
	return float(stats["matches_won"]) / float(stats["matches_played"]) * 100.0


func get_rank_name(tier: int = -1, division: int = -1) -> String:
	"""取得段位名稱"""
	if tier < 0:
		tier = rank_tier
	if division < 0:
		division = rank_division
	if tier == 0:
		return "未定級"
	var base: String = RANK_NAMES.get(tier, "未知")
	if tier <= 6:
		return base + " " + str(division)
	return base  # 不朽/輻能無分段


func get_rank_color(tier: int = -1) -> Color:
	"""取得段位顏色"""
	if tier < 0:
		tier = rank_tier
	return RANK_COLORS.get(tier, Color.WHITE)


func get_rank_progress() -> float:
	"""取得段位進度 (0.0-1.0)"""
	if rank_tier == 0:
		return 0.0
	# 每段需要 100 RP
	return float(rank_points % 100) / 100.0


# ─── 排位計算 ─────────────────────────────────────────────
func update_rank(result: String, score_diff: int) -> void:
	"""根據對戰結果更新排位"""
	var rp_change := 0
	if result == "win":
		rp_change = 20 + maxi(0, score_diff * 5)  # 大比分勝利獎勵更多
	else:
		rp_change = -15 + mini(0, score_diff * 3)  # 小比分失敗扣更少

	rank_points += rp_change

	# 段位晉級/降級
	if rank_points >= 100:
		rank_points -= 100
		if rank_division < 3:
			rank_division += 1
		elif rank_tier < 8:
			rank_tier += 1
			rank_division = 1
	elif rank_points < 0:
		rank_points += 100
		if rank_division > 1:
			rank_division -= 1
		elif rank_tier > 1:
			rank_tier -= 1
			rank_division = 3

	# 記錄歷史
	rank_history.append({
		"date": Time.get_datetime_string_from_system(),
		"tier": rank_tier,
		"division": rank_division,
		"rp_change": rp_change,
		"result": result
	})

	rank_updated.emit(get_rank_name(), rank_points)
	_save_data()


# ─── 持久化 ─────────────────────────────────────────────
func _save_data() -> void:
	"""保存資料到檔案"""
	var data := {
		"friends": friends,
		"stats": stats,
		"rank_tier": rank_tier,
		"rank_division": rank_division,
		"rank_points": rank_points,
		"season": season,
		"blocked": blocked_users
	}
	var file := FileAccess.open("user://social_data.json", FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(data, "\t"))
		file.close()


func _load_data() -> void:
	"""從檔案載入資料"""
	var file := FileAccess.open("user://social_data.json", FileAccess.READ)
	if not file:
		return
	var json := JSON.new()
	var err := json.parse(file.get_as_text())
	file.close()
	if err != OK:
		return
	var data: Dictionary = json.data
	friends = data.get("friends", [])
	var loaded_stats: Dictionary = data.get("stats", {})
	for key in loaded_stats:
		stats[key] = loaded_stats[key]
	rank_tier = data.get("rank_tier", 0)
	rank_division = data.get("rank_division", 1)
	rank_points = data.get("rank_points", 0)
	season = data.get("season", 1)
	blocked_users = data.get("blocked", [])
