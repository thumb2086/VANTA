class_name NetClient
extends Node

## VANTA 網路客戶端 — 與 server/netcode/protocol.py 位元級相容
## 只負責：發送淨輸入、接收快照與遊戲事件（伺服器權威）。
##
## 兩種傳輸：
##   * mode = "udp"：本機 UDP 權威伺服器（tools.godot.serve）
##   * mode = "ws" ：Cloudflare Workers 部署版（WebSocket + Durable Object）
## 封包格式完全相同，只是載體不同。

const MAGIC := 0x56
const TYPE_INPUT := 0x01
const TYPE_SNAPSHOT := 0x02
const TYPE_WELCOME := 0x03
const TYPE_GAME_EVENT := 0x05
const TYPE_MATCH_STATE := 0x06
const TYPE_ABILITY_STATE := 0x07
const TYPE_WORLD_STATE := 0x09

const INPUT_SIZE := 15
const WELCOME_SIZE := 6
const SNAPSHOT_HEADER := 10
const SNAPSHOT_ENTRY := 26
const MAX_SLOTS := 10
const SNAPSHOT_SIZE := SNAPSHOT_HEADER + MAX_SLOTS * SNAPSHOT_ENTRY
const ABILITY_ENTRY_SIZE := 8                    # 每人 8 bytes（與 protocol.py 同步）
const ABILITY_STATE_SIZE := 6 + MAX_SLOTS * ABILITY_ENTRY_SIZE
const WORLD_STATE_HEADER := 8
const WORLD_STATE_SMOKE_ENTRY := 14
const MAX_WORLD_SMOKES := 8
const WORLD_STATE_SIZE := WORLD_STATE_HEADER + MAX_WORLD_SMOKES * WORLD_STATE_SMOKE_ENTRY

const ACTION_SWITCH := 0x07

const EV_KILL := 1
const EV_SPIKE_PLANTED := 2
const EV_SPIKE_DEFUSED := 3
const EV_SPIKE_DETONATED := 4
const EV_ROUND_WIN := 5
const EV_ROUND_LOSS := 6
const EV_MATCH_END := 7
const EV_ASSIST := 8
const EV_STREAK := 9      # p0=streak(2/3/4/5), p1=killer slot
const EV_CLUTCH := 10     # p0=clutcher, p1=vs count
const EV_ORB := 11        # p0=kind idx, p1=capturer slot

const ACTION_SHOOT := 0x01
const ACTION_RELOAD := 0x02
const ACTION_BUY := 0x03
const ACTION_ABILITY := 0x06

# MatchState 階段常量
const PHASE_BUY := 0
const PHASE_ACTION := 1
const PHASE_END := 2
const PHASE_FINISHED := 3

## 傳輸模式："udp"（本機）或 "ws"（Cloudflare Workers）
@export var mode := "udp"
## WS 模式連線位址（Workers 部署後換成 wss://...）
@export var ws_url := "ws://127.0.0.1:8787/ws?match=demo&ai=1"

var peer := PacketPeerUDP.new()
var ws: WebSocketPeer = null
var server_addr := "127.0.0.1"
var server_port := 7777
var connected := false
var net_id := -1
var slot := -1
var out_seq := 0
var last_server_tick := -1
var snapshot_count := 0
var rtt_ms := 0.0
var own_last_seq := -1
var own_echo_ms := 0

# slot -> {pos, vel, on_ground, crouch, walk, health, mag}
var players := {}
# 遊戲事件佇列（main 消費）：{event, tick, p0, p1}
var events: Array = []
var _last_input_time := 0
var _ws_connect_started := 0

# MatchState（從 0x06 封包解碼，伺服器權威）
var match_phase := PHASE_BUY
var match_round := 1
var match_timer_ms := 0
var match_score_a := 0  # 攻方
var match_score_b := 0  # 守方
var match_spike_state := 0
var match_spike_fuse := 0
var match_credits: Array = []  # 每槽位 credits
var ability_cooldowns: Array = []  # 10 × 4 技能冷卻（秒）
var ability_charges: Array = []    # 10 × 4 剩餘使用次數
var ability_ult: Array = []        # 10 × {points, cost, ready, blocked}
## 世界狀態：煙霧列表 [{pos: Vector3, radius: float, time_left: float, team: int}]
var world_smokes: Array = []
## 閃光致盲事件隊列（main 消費）：{tick, intensity}
var flash_blind_events: Array = []
var _flash_blind_timer := 0.0
var _flash_blind_intensity := 0.0


func start() -> void:
	if mode == "offline":
		# 離線模式：模擬伺服器回應
		connected = true
		net_id = 0
		slot = 0
		# 模擬玩家（slot 0 = 本地玩家）
		players[0] = {
			"pos": Vector3.ZERO,
			"vel": Vector3.ZERO,
			"on_ground": true,
			"crouch": false,
			"walk": false,
			"health": 100,
			"shield": 0,
			"mag": 30,
			"weapon_slot": 0,
			"reload_frac": -1.0,
			"last_seq": 0,
			"echo": 0,
			"credits": 8000,
			"weapon": {"key": "vandal", "mag": 25, "reserve": 75, "reloading": false},
		}
		# 模擬其他 bot（slot 1-4 隊友；不覆蓋 slot 0 自己）
		for i in range(1, 5):
			players[i] = {
				"pos": Vector3(-20 + i * 5, 0, -25),
				"vel": Vector3.ZERO,
				"on_ground": true,
				"crouch": false,
				"walk": false,
				"health": 100,
				"shield": 0,
				"mag": 30,
				"weapon_slot": 0,
				"reload_frac": -1.0,
				"last_seq": 0,
				"echo": 0,
				"credits": 8000,
				"weapon": {"key": "vandal", "mag": 25, "reserve": 75, "reloading": false},
			}
		for i in range(5, 10):
			players[i] = {
				"pos": Vector3(-20 + (i-5) * 5, 0, 25),
				"vel": Vector3.ZERO,
				"on_ground": true,
				"crouch": false,
				"walk": false,
				"health": 100,
				"shield": 0,
				"mag": 30,
				"weapon_slot": 0,
				"reload_frac": -1.0,
				"last_seq": 0,
				"echo": 0,
				"credits": 8000,
				"weapon": {"key": "vandal", "mag": 25, "reserve": 75, "reloading": false},
			}
		match_phase = PHASE_ACTION
		match_round = 1
		match_score_a = 0
		match_score_b = 0
		match_credits = [800, 800, 800, 800, 800, 800, 800, 800, 800, 800]
		return
	if mode == "ws":
		ws = WebSocketPeer.new()
		ws.connect_to_url(ws_url)
		connected = false
		_ws_connect_started = Time.get_ticks_msec()
		return
	peer.set_dest_address(server_addr, server_port)


func stop() -> void:
	if mode == "ws":
		if ws != null:
			ws.close()
			ws = null
		return
	peer.close()


func tick() -> void:
	if mode == "offline":
		# 離線模式：模擬 bot 行為
		var t := Time.get_ticks_msec() * 0.001
		var my_pos: Vector3 = players.get(0, {}).get("pos", Vector3.ZERO)
		for i in range(5, 10):
			if not players.has(i):
				continue
			var p: Dictionary = players[i]
			if p.get("health", 0) <= 0:
				continue
			# 朝玩家移動 + 橫向閃避
			var to_me: Vector3 = (my_pos - p["pos"]).normalized()
			var strafe := Vector3(-to_me.z, 0, to_me.x) * sin(t * 2.0 + i * 1.3) * 2.0
			var speed := 3.5
			var dist_to_me: float = p["pos"].distance_to(my_pos)
			if dist_to_me < 3.0:
				speed = 1.0  # 靠近時減速
			p["vel"] = (to_me * speed + strafe)
			p["pos"] += p["vel"] * 0.016
		return
	if mode == "ws":
		_tick_ws()
		return
	# 非阻塞收包（UDP）
	while peer.get_available_packet_count() > 0:
		var data: PackedByteArray = peer.get_packet()
		if data.size() < 2 or data[0] != MAGIC:
			continue
		match data[1]:
			TYPE_WELCOME:
				_parse_welcome(data)
			TYPE_SNAPSHOT:
				_parse_snapshot(data)
			TYPE_GAME_EVENT:
				_parse_event(data)
			TYPE_MATCH_STATE:
				_parse_match_state(data)
			TYPE_ABILITY_STATE:
				_parse_ability_state(data)
			TYPE_WORLD_STATE:
				_parse_world_state(data)


func _tick_ws() -> void:
	if ws == null:
		return
	ws.poll()
	var state := ws.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		while ws.get_available_packet_count() > 0:
			var data: PackedByteArray = ws.get_packet()
			if data.size() < 2 or data[0] != MAGIC:
				continue
			match data[1]:
				TYPE_WELCOME:
					_parse_welcome(data)
				TYPE_SNAPSHOT:
					_parse_snapshot(data)
				TYPE_GAME_EVENT:
					_parse_event(data)
				TYPE_MATCH_STATE:
					_parse_match_state(data)
				TYPE_ABILITY_STATE:
					_parse_ability_state(data)
				TYPE_WORLD_STATE:
					_parse_world_state(data)
	elif state == WebSocketPeer.STATE_CLOSED:
		connected = false
	# WS 連線逾時 → 自動切離線模式（雲端掛掉仍可玩：準心/射擊/移動全可用）
	elif not connected and _ws_connect_started > 0 and Time.get_ticks_msec() - _ws_connect_started > 6000:
		_ws_connect_started = 0
		mode = "offline"
		if ws != null:
			ws.close()
			ws = null
		start()
		print("[net] WS 連線逾時（6s）→ 自動切換離線模式")


func _send(data: PackedByteArray) -> void:
	if mode == "ws":
		if ws != null and ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
			ws.send(data)
		return
	peer.put_packet(data)


func send_input(dir: Vector2, walk: bool, crouch: bool, jump: bool, ads: bool = false) -> void:
	var b := PackedByteArray()
	b.resize(INPUT_SIZE)
	b[0] = MAGIC
	b[1] = TYPE_INPUT
	b.encode_u16(2, maxi(net_id, 0) & 0xFFFF)
	b.encode_u32(4, out_seq & 0xFFFFFFFF)
	b.encode_u32(8, Time.get_ticks_msec() & 0xFFFFFFFF)
	b.encode_s8(12, int(clampf(dir.x, -1.0, 1.0) * 127.0))
	b.encode_s8(13, int(clampf(dir.y, -1.0, 1.0) * 127.0))
	var flags := 0
	if walk:
		flags |= 1
	if crouch:
		flags |= 2
	if jump:
		flags |= 4
	if ads:
		flags |= 8
	b[14] = flags
	_send(b)
	out_seq += 1


func send_action(action_id: int, p0: int, p1: int, p2: int, input_seq: int) -> void:
	# 離線模式：客戶端處理開火 + 購買
	if mode == "offline":
		if action_id == ACTION_SHOOT:
			_offline_process_shot(p0 * 0.01, p1 * 0.01)
			return
		if action_id == ACTION_BUY:
			_offline_process_buy(p0)
			return
	var b := PackedByteArray()
	b.resize(19)
	b[0] = MAGIC
	b[1] = 0x04
	b.encode_u16(2, maxi(net_id, 0) & 0xFFFF)
	b.encode_u32(4, Time.get_ticks_msec() & 0xFFFFFFFF)
	b.encode_u32(8, input_seq & 0xFFFFFFFF)
	b[12] = action_id & 0xFF
	b.encode_s16(13, p0)
	b.encode_s16(15, p1)
	b.encode_s16(17, p2)
	_send(b)


func _offline_process_shot(yaw: float, pitch: float) -> void:
	"""離線模式：客戶端射線檢測 + 傷害 + 擊殺。"""
	var my_pos: Vector3 = players.get(0, {}).get("pos", Vector3.ZERO) + Vector3(0, 1.6, 0)
	var dir := Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch)).normalized()
	# 射線 vs 每個 bot 的 AABB（0.4x1.8x0.4 居中於 pos+0.9）
	var best_dist := 999.0
	var best_slot := -1
	for s in range(5, 10):
		if not players.has(s):
			continue
		var bp: Dictionary = players[s]
		if bp.get("health", 0) <= 0:
			continue
		var center: Vector3 = bp["pos"] + Vector3(0, 0.9, 0)
		var half := Vector3(0.3, 0.9, 0.3)
		var hit_dist := _ray_aabb(my_pos, dir, center, half)
		if hit_dist >= 0.0 and hit_dist < best_dist:
			best_dist = hit_dist
			best_slot = s
	if best_slot >= 0:
		var dmg: float = 20.0  # 預設傷害（可依武器調整）
		var wk: String = players.get(0, {}).get("weapon", {}).get("key", "classic")
		match wk:
			"vandal": dmg = 40.0
			"phantom": dmg = 39.0
			"operator": dmg = 150.0
			"marshal": dmg = 50.0
			"sheriff": dmg = 55.0
			"guardian": dmg = 65.0
			"bucky": dmg = 20.0
			"judge": dmg = 17.0
			"knife": dmg = 50.0
		var bp2: Dictionary = players[best_slot]
		bp2["health"] = maxf(0.0, bp2.get("health", 100) - dmg)
		# 擊殺事件
		if bp2["health"] <= 0:
			events.append({"event": EV_KILL, "p0": 0, "p1": best_slot})
			# 3 秒後重生
			var timer := get_tree().create_timer(3.0)
			timer.timeout.connect(_respawn_bot.bind(best_slot))


func _respawn_bot(s: int) -> void:
	if not players.has(s):
		return
	players[s]["health"] = 100
	players[s]["shield"] = 0
	players[s]["pos"] = Vector3(-20 + (s - 5) * 5, 0, 25)


# ── 離線購買（item_id → weapon_key 對照 + 扣 credits）──
const _ITEM_TO_WEAPON := {
	0: "ares", 1: "bucky", 2: "bulldog", 3: "classic", 4: "frenzy",
	5: "ghost", 6: "guardian", 7: "judge", 8: "knife", 9: "marshal",
	10: "odin", 11: "operator", 12: "phantom", 13: "sheriff", 14: "shorty",
	15: "spectre", 16: "stinger", 17: "vandal",
}
const _WEAPON_PRICES := {
	"ares": 1600, "bucky": 900, "bulldog": 2050, "classic": 0, "frenzy": 450,
	"ghost": 500, "guardian": 2250, "judge": 1850, "knife": 0, "marshal": 950,
	"odin": 3200, "operator": 4700, "phantom": 2900, "sheriff": 800, "shorty": 300,
	"spectre": 1600, "stinger": 1100, "vandal": 2900,
}


func _offline_process_buy(item_id: int) -> void:
	var wk: String = _ITEM_TO_WEAPON.get(item_id, "")
	if wk == "":
		return
	var price: int = _WEAPON_PRICES.get(wk, 0)
	var me: Dictionary = players.get(0, {})
	var credits: int = me.get("credits", 800)
	if price > credits:
		return
	me["credits"] = credits - price
	# 裝備武器（主武器槽 slot 0，手槍槽 slot 1，刀 slot 2）
	var wclass: String = "rifle"
	match wk:
		"classic", "ghost", "frenzy", "sheriff", "shorty": wclass = "sidearm"
		"stinger", "spectre": wclass = "smg"
		"marshal", "operator": wclass = "sniper"
		"bucky", "judge": wclass = "shotgun"
		"ares", "odin": wclass = "heavy"
		"knife": wclass = "melee"
	var slot := 0
	match wclass:
		"sidearm": slot = 1
		"melee": slot = 2
		_: slot = 0
	me["weapon_slot"] = slot
	me["weapon"] = {"key": wk, "mag": _mag_for(wk), "reserve": _reserve_for(wk), "reloading": false}
	# 更新 player slot 0
	players[0] = me


func _mag_for(wk: String) -> int:
	match wk:
		"classic": return 12
		"ghost": return 15
		"frenzy": return 13
		"sheriff": return 6
		"shorty": return 2
		"stinger": return 20
		"spectre": return 30
		"bulldog": return 24
		"guardian": return 12
		"phantom": return 30
		"vandal": return 25
		"marshal": return 5
		"operator": return 5
		"bucky": return 5
		"judge": return 5
		"ares": return 50
		"odin": return 100
		"knife": return 1
	return 30


func _reserve_for(wk: String) -> int:
	match wk:
		"classic": return 60
		"ghost": return 45
		"frenzy": return 39
		"sheriff": return 18
		"shorty": return 10
		"stinger": return 60
		"spectre": return 90
		"bulldog": return 72
		"guardian": return 36
		"phantom": return 90
		"vandal": return 75
		"marshal": return 15
		"operator": return 15
		"bucky": return 15
		"judge": return 15
		"ares": return 150
		"odin": return 300
		"knife": return 0
	return 60


func _ray_aabb(origin: Vector3, dir: Vector3, center: Vector3, half: Vector3) -> float:
	"""射線 vs AABB 交叉測試，回傳距離（負 = 未命中）。"""
	var inv_dir := Vector3(1.0 / dir.x if dir.x != 0 else 1e30, 1.0 / dir.y if dir.y != 0 else 1e30, 1.0 / dir.z if dir.z != 0 else 1e30)
	var t1 := (center.x - half.x - origin.x) * inv_dir.x
	var t2 := (center.x + half.x - origin.x) * inv_dir.x
	var tmin := minf(t1, t2)
	var tmax := maxf(t1, t2)
	t1 = (center.y - half.y - origin.y) * inv_dir.y
	t2 = (center.y + half.y - origin.y) * inv_dir.y
	tmin = maxf(tmin, minf(t1, t2))
	tmax = minf(tmax, maxf(t1, t2))
	t1 = (center.z - half.z - origin.z) * inv_dir.z
	t2 = (center.z + half.z - origin.z) * inv_dir.z
	tmin = maxf(tmin, minf(t1, t2))
	tmax = minf(tmax, maxf(t1, t2))
	if tmax >= tmin and tmax >= 0.0:
		return tmin if tmin >= 0.0 else tmax
	return -1.0


func send_shot(yaw_deg: float, pitch_deg: float) -> void:
	var yaw_i := int(round(yaw_deg * 100.0))
	var pitch_i := int(round(pitch_deg * 100.0))
	send_action(ACTION_SHOOT, yaw_i, pitch_i, 0, own_last_seq)


func _parse_welcome(data: PackedByteArray) -> void:
	if data.size() < WELCOME_SIZE:
		return
	net_id = data.decode_u16(2)
	slot = data[4]
	connected = true


func _parse_snapshot(data: PackedByteArray) -> void:
	if data.size() < SNAPSHOT_SIZE:
		return
	last_server_tick = data.decode_u32(2)
	snapshot_count += 1
	players.clear()
	for s in range(MAX_SLOTS):
		var off := SNAPSHOT_HEADER + s * SNAPSHOT_ENTRY
		var flags := data[off + 1]
		if (flags & 8) == 0:
			continue
		var px := float(data.decode_s16(off + 2)) * 0.01
		var py := float(data.decode_s16(off + 4)) * 0.01
		var pz := float(data.decode_s16(off + 6)) * 0.01
		var vx := float(data.decode_s16(off + 8)) * 0.01
		var vy := float(data.decode_s16(off + 10)) * 0.01
		var vz := float(data.decode_s16(off + 12)) * 0.01
		var echo := data.decode_u32(off + 14)
		var last_seq := data.decode_u32(off + 18)
		players[s] = {
			"pos": Vector3(px, py, pz),
			"vel": Vector3(vx, vy, vz),
			"on_ground": (flags & 1) != 0,
			"crouch": (flags & 2) != 0,
			"walk": (flags & 4) != 0,
			"reloading": (flags & 16) != 0,
			"health": data[off + 22],
			"mag": data[off + 23],
			"weapon_slot": data[off + 24],
			"reload_frac": _reload_frac(data[off + 25]),
			"last_seq": last_seq,
			"echo": echo
		}
	# 自己的 ack / RTT
	var me: Dictionary = players.get(slot, {})
	if me.is_empty():
		return
	own_last_seq = me["last_seq"]
	own_echo_ms = me["echo"]
	if own_echo_ms > 0:
		var sample := float(Time.get_ticks_msec() - own_echo_ms)
		if sample >= 0.0:
			if rtt_ms <= 0.0:
				rtt_ms = sample
			else:
				rtt_ms = lerpf(rtt_ms, sample, 0.25)


func _reload_frac(byte_val: int) -> float:
	# 255 = 未換彈；0..254 = 進度（伺服器權威）
	if byte_val >= 255:
		return -1.0
	return float(byte_val) / 254.0


func _parse_event(data: PackedByteArray) -> void:
	var ev := data.decode_u16(2)
	var tick := data.decode_u32(4)
	var p0 := data.decode_u32(8)
	var p1 := data.decode_u32(12)
	events.append({"event": ev, "tick": tick, "p0": p0, "p1": p1})


func _parse_match_state(data: PackedByteArray) -> void:
	# 0x06 MATCH_STATE（36B）：伺服器權威比分/回合/階段/Spike/經濟
	if data.size() < 36:
		return
	last_server_tick = data.decode_u32(2)
	match_phase = data[6]
	match_round = data[7]
	match_timer_ms = data.decode_u16(8)
	match_spike_state = data[10]
	match_spike_fuse = data[11]
	match_score_a = data[12]
	match_score_b = data[13]
	match_credits.clear()
	for i in range(10):
		match_credits.append(data.decode_u16(16 + i * 2))


func _parse_ability_state(data: PackedByteArray) -> void:
	# 0x07 ABILITY_STATE（86B）：每人 8 bytes
	#   +0..3 冷卻(0.1s) | +4 終點球點數 | +5 所需點數 | +6 使用次數(2bits/槽) | +7 旗標
	if data.size() < ABILITY_STATE_SIZE:
		return
	ability_cooldowns.clear()
	ability_charges.clear()
	ability_ult.clear()
	for slot in range(MAX_SLOTS):
		var off := 6 + slot * ABILITY_ENTRY_SIZE
		var cds := []
		for a in range(4):
			cds.append(float(data[off + a]) / 10.0)
		ability_cooldowns.append(cds)
		var packed := data[off + 6]
		var ch := []
		for i in range(4):
			ch.append((packed >> (i * 2)) & 3)
		ability_charges.append(ch)
		var flags := data[off + 7]
		ability_ult.append({
			"points": data[off + 4], "cost": data[off + 5],
			"ready": (flags & 1) != 0, "blocked": (flags & 2) != 0,
		})


func _parse_world_state(data: PackedByteArray) -> void:
	# 0x09 WORLD_STATE（120B）：煙霧位置/半徑/剩餘時間
	if data.size() < WORLD_STATE_HEADER:
		return
	var count: int = data[6]
	world_smokes.clear()
	for i in range(mini(count, MAX_WORLD_SMOKES)):
		var off := WORLD_STATE_HEADER + i * WORLD_STATE_SMOKE_ENTRY
		if off + WORLD_STATE_SMOKE_ENTRY > data.size():
			break
		var px: float = float(data.decode_s16(off)) * 0.01
		var py: float = float(data.decode_s16(off + 2)) * 0.01
		var pz: float = float(data.decode_s16(off + 4)) * 0.01
		var radius: float = float(data.decode_u16(off + 6)) * 0.01
		var time_left: float = float(data[off + 8]) / 4.0
		var team: int = data[off + 9]
		world_smokes.append({
			"pos": Vector3(px, py, pz),
			"radius": radius,
			"time_left": time_left,
			"team": team,
			"spawn_tick": last_server_tick,
		})


func trigger_flash_blind(intensity: float, duration: float) -> void:
	"""客戶端觸發閃光致盲效果（離線模式或被閃光彈命中時）。"""
	_flash_blind_timer = duration
	_flash_blind_intensity = clampf(intensity, 0.0, 1.0)
	flash_blind_events.append({"tick": last_server_tick, "intensity": _flash_blind_intensity})


func update_flash_blind(delta: float) -> void:
	"""每幀更新閃光致盲計時（漸層淡出）。"""
	if _flash_blind_timer > 0.0:
		_flash_blind_timer = maxf(0.0, _flash_blind_timer - delta)
	flash_blind_events = flash_blind_events.filter(
		func(e): return last_server_tick - int(e["tick"]) < 300)
