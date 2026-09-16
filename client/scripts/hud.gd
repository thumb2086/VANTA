class_name HUD
extends Control

## Valorant 風格 HUD — 半透明深色面板 + 團隊配色 + 即時資訊
##
## 佈局（基於視窗比例）：
##   上方中央：比分（攻方-守方）+ 回合
##   左上：小地圖 + 隊伍構成
##   右上：連線統計 + 擊殺訊息
##   左下：血量 + 護甲
##   中央下方：技能欄
##   右下：彈匣 + 金錢
##   正中央：準星 + 宣告

# ──── 顏色 ────
const COL_PANEL := Color(0.0, 0.0, 0.0, 0.55)
const COL_ATTACK := Color(0.95, 0.28, 0.22)       # 攻方紅
const COL_DEFEND := Color(0.22, 0.55, 0.95)       # 守方藍
const COL_HEALTH := Color(0.15, 0.85, 0.30)        # 血量綠
const COL_SHIELD := Color(0.25, 0.65, 0.95)        # 護甲藍
const COL_MONEY := Color(1.0, 0.85, 0.20)          # 金錢金
const COL_AMMO_LOW := Color(1.0, 0.35, 0.25)       # 低彈藥紅
const COL_AMMO_OK := Color(1.0, 1.0, 1.0)          # 正常白
const COL_SPIKE := Color(1.0, 0.35, 0.25)          # Spike 紅
const COL_TEXT := Color(1.0, 1.0, 1.0)
const COL_TEXT_DIM := Color(0.7, 0.7, 0.75)
const COL_CROSSHAIR := Color(0.22, 1.0, 0.08)

# ──── 資料（main.gd 寫入）────────
var connected_text := ""
var ping_text := "0"
var tick_text := ""

var health := 100
var max_health := 100
var shield := 0
var max_shield := 50
var mag := 0
var mag_max := 30
var credits := 0
var weapon_name := "Classic"
var weapon_slot := 1

var score_attack := 0
var score_defend := 0
var round_number := 1
var phase_text := ""  # 買槍 / 行動 / 結算
var round_timer := -1  # 回合剩餘秒數（-1 = 未知，不顯示）

var spike_text := ""             # "已安放" / "已拆除" / "爆炸" / ""
var _spike_timer := 0.0

# ──── 小地圖 ────
var map_data: Dictionary = {}    # 從 main.gd 傳入
var own_slot := -1
var players_dict: Dictionary = {} # net.players 的引用

# ──── 開鏡狀態 ────
var is_ads := false       # 是否右鍵開鏡
var is_scoped := false    # 是否狙擊槍（有瞄準鏡）

# ──── 技能冷卻 ────
var ability_cooldowns := [0.0, 0.0, 0.0, 0.0]  # C/Q/E/X 冷卻秒數
var ability_max_cds := [10.0, 10.0, 0.0, 0.0]   # 最大冷卻（由权威封包的第一個觀測值推得）
var ability_charges := [1, 1, 1, 1]             # 各槽剩餘使用次數（伺服器權威）
# 終點球（X 槽）：points/cost 由 0x07 ABILITY_STATE 每秒推一次
var ult_points := 0
var ult_cost := 0
var ult_ready := false
var ult_blocked := false
var _ult_pulse := 0.0

# ──── 彈道散布 ────
var spread_angle := 0.0  # 當前散布角度（度）
var _spread_decay := 0.0 # 散布衰減計時
# ──── 手感三件套（資料來源：res://assets/recoil/recoil.json）────
var recoil_model: RecoilModel = null   # main 注入；有它準星就是「真的」擴散圓
var spread_linked := true             # false → 回到舊的固定衰減行為
var spread_locked := false            # 模型每幀推值時停用本地衰減
var recoil_indicator := false         # 中央顯示该槍图案 + 目前累積偏移
var spread_state := 0                 # 0 站/跑 1 靜步 2 蹲 3 空中 4 剛落地
var _px_per_deg := 8.0               # 1° → 多少像素（設定面板可调）

# ──── 準心自訂（從 VantaGlobal 載入）───
var ch_color := Color(0.22, 1.0, 0.08)
var ch_size := 4.0
var ch_gap := 4.0
var ch_thickness := 2.0
var ch_outline := false
var ch_dot := true
var ch_style := 0  # 0=十字, 1=圓形, 2=點

# ──── 擊殺訊息 ────
var feed: Array[Dictionary] = []

# ──── 宣告 ────
var announce_text := ""
var announce_color := Color.WHITE
var _announce_timer := 0.0

# ──── 準星 ────
var _killflash_timer := 0.0
var _banner_text := ""
var _banner_hs := false
var _banner_weapon := ""
var _banner_timer := 0.0
var _banner_color := Color(1.0, 0.32, 0.28)
var _banner_frame := "default"
var _banner_level := 1
var _killflash_color := Color(1.0, 0.2, 0.2)
var _hitmarker_timer := 0.0
var _hitmarker_headshot := false
var _hitmarker_color := Color(1.0, 1.0, 1.0)
var _hitmarker_scale := 1.0
var _damage_numbers: Array = []
var _damage_direction_timer := 0.0
var _damage_direction_angle := 0.0
var _hit_marker_crosshair := false


func _ready() -> void:
	set_process(true)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	reload_crosshair_config()


## 從 VantaGlobal 讀準心／手感設定（設定面板套用後會再呼叫一次）
func reload_crosshair_config() -> void:
	var g := get_node_or_null("/root/VantaGlobal")
	if g == null:
		return
	ch_color = _g(g, "crosshair_color", ch_color)
	ch_size = float(_g(g, "crosshair_size", ch_size))
	ch_gap = float(_g(g, "crosshair_gap", ch_gap))
	ch_thickness = float(_g(g, "crosshair_thickness", ch_thickness))
	ch_outline = bool(_g(g, "crosshair_outline", ch_outline))
	ch_dot = bool(_g(g, "crosshair_dot", ch_dot))
	ch_style = int(_g(g, "crosshair_style", ch_style))
	recoil_indicator = bool(_g(g, "recoil_indicator", recoil_indicator))
	spread_linked = bool(_g(g, "crosshair_spread_linked", spread_linked))
	_px_per_deg = float(_g(g, "crosshair_spread_scale", _px_per_deg))
	queue_redraw()


func _g(node: Node, prop: String, fallback: Variant) -> Variant:
	if prop in node:
		return node.get(prop)
	return fallback


func _process(delta: float) -> void:
	if _announce_timer > 0.0:
		_announce_timer = maxf(0.0, _announce_timer - delta)
	if _killflash_timer > 0.0:
		_killflash_timer = maxf(0.0, _killflash_timer - delta)
	if _banner_timer > 0.0:
		_banner_timer = maxf(0.0, _banner_timer - delta)
	if _hitmarker_timer > 0.0:
		_hitmarker_timer = maxf(0.0, _hitmarker_timer - delta)
	if _damage_direction_timer > 0.0:
		_damage_direction_timer = maxf(0.0, _damage_direction_timer - delta)
	for i in range(_damage_numbers.size() - 1, -1, -1):
		_damage_numbers[i]["t"] = float(_damage_numbers[i]["t"]) + delta
		if float(_damage_numbers[i]["t"]) > 1.0:
			_damage_numbers.remove_at(i)
	if _hit_marker_crosshair and _hitmarker_timer <= 0.0:
		_hit_marker_crosshair = false
	if _spike_timer > 0.0:
		_spike_timer = maxf(0.0, _spike_timer - delta)
	# 終點球就緒：呼吸光（只在本機做視覺，數值仍是伺服器的）
	if ult_ready:
		_ult_pulse = fmod(_ult_pulse + delta * 2.6, TAU)
	# 彈道散布衰減（只有「非模型驅動」時才用本地指數衰減）
	if spread_angle > 0.0 and (not spread_locked or not spread_linked):
		spread_angle = maxf(0.0, spread_angle - delta * 15.0)  # 0.3 秒歸零
	for i in range(feed.size() - 1, -1, -1):
		feed[i]["t"] = float(feed[i]["t"]) + delta
		if float(feed[i]["t"]) > 5.0:
			feed.remove_at(i)
	queue_redraw()


# ──── 外部 API（與舊版相容）───────────
func announce(text: String, color := Color(1.0, 0.8, 0.2)) -> void:
	announce_text = text
	announce_color = color
	_announce_timer = 3.0


func push_feed(text: String) -> void:
	feed.push_front({"text": text, "t": 0.0})
	if feed.size() > 5:
		feed.resize(5)


func killflash(headshot := false) -> void:
	_killflash_timer = 0.6
	_killflash_color = Color(1.0, 0.3, 0.3) if headshot else Color(1.0, 0.9, 0.4)


func show_kill_banner(victim: String, headshot := false, weapon := "") -> void:
	# 特戰風格擊殺橫幅：畫面下方「你擊殺了 ○○」
	_banner_text = victim
	_banner_hs = headshot
	_banner_weapon = weapon
	_banner_timer = 2.2


## 皮膚感知的命中回饋（FxManager 由 blueprint 的 hud 層呼叫）
func hit_marker(color := Color(1.0, 1.0, 1.0), headshot := false, scale := 1.0) -> void:
	_hitmarker_timer = 0.25
	_hitmarker_headshot = headshot
	_hitmarker_color = color
	_hitmarker_scale = scale


## 傳說級擊殺橫幅：底色／框／等級都由皮膚決定
func show_kill_banner_fx(victim: String, skin_name := "", color := Color(1.0, 0.32, 0.28),
		frame := "default", level := 1) -> void:
	_banner_text = victim
	_banner_hs = false
	_banner_timer = 2.2
	_banner_weapon = skin_name
	_banner_color = color
	_banner_frame = frame
	_banner_level = clampi(level, 1, 5)


func show_hitmarker(headshot := false) -> void:
	_hitmarker_timer = 0.25
	_hitmarker_headshot = headshot

func show_damage_number(amount: float, world_pos: Vector3) -> void:
	_damage_numbers.append({"amount": amount, "world_pos": world_pos, "t": 0.0})

func show_damage_direction(angle_rad: float) -> void:
	_damage_direction_timer = 0.8
	_damage_direction_angle = angle_rad

func show_hit_marker_crosshair() -> void:
	_hit_marker_crosshair = true


## 模型 → HUD：把「真的」擴散圓（度）交給準星
func set_spread_deg(deg: float) -> void:
	if not spread_linked:
		spread_locked = false
		return
	spread_locked = true
	spread_angle = clampf(rad_to_deg(deg), 0.0, 26.0)


## 停用模型驅動（無 bundle／使用者關閉）→ 退回本地衰減
func release_spread() -> void:
	spread_locked = false


## 权威終點球狀態（main 從 0x07 封包同步過來）
func set_ult(points: int, cost: int, ready: bool, blocked: bool = false) -> void:
	ult_points = points
	ult_cost = cost
	ult_blocked = blocked
	if ult_ready != ready:
		ult_ready = ready
		queue_redraw()


func set_spread_state(state: int) -> void:
	if spread_state != state:
		spread_state = state
		queue_redraw()
	_hitmarker_timer = 0.15


func set_spike(text: String) -> void:
	spike_text = text
	if text != "":
		_spike_timer = 99.0


# ═══════════════════════════════════════════════
#  繪 製
# ═══════════════════════════════════════════════
func _draw() -> void:
	var vp := get_viewport_rect().size
	var font := ThemeDB.fallback_font
	_draw_crosshair(vp, font)
	_draw_score_bar(vp, font)
	_draw_phase_label(vp, font)
	_draw_health_shield(vp, font)
	_draw_ammo_money(vp, font)
	_draw_minimap(vp, font)
	_draw_kill_feed(vp, font)
	_draw_announce(vp, font)
	_draw_kill_banner(vp, font)
	_draw_net_stats(vp, font)
	_draw_spike_status(vp, font)
	_draw_ability_bar(vp, font)
	_draw_agent_dots(vp, font)
	_draw_team_status(vp, font)
	_draw_hitmarker(vp, font)
	_draw_damage_numbers(vp, font)
	_draw_damage_direction(vp)
	_draw_health_bar_visual(vp, font)
	_draw_weapon_silhouette(vp, font)
	_draw_scope_overlay(vp, font)


# ──── 準星 + 彈道散布 ─────────────────────
func _draw_crosshair(vp: Vector2, font: Font) -> void:
	var cx := vp.x * 0.5
	var cy := vp.y * 0.5
	# 散布間距＝真實擴散圓（1° = _px_per_deg 像素，可在設定面板調整）
	var spread_px := spread_angle * _px_per_deg
	var gap := ch_gap + spread_px
	var len := ch_size
	var thick := ch_thickness
	var spread_ratio := clampf(spread_angle / 5.0, 0.0, 1.0)
	var xh_color := ch_color.lerp(Color(1.0, 0.3, 0.2), spread_ratio)
	match ch_style:
		0:
			draw_line(Vector2(cx - gap - len, cy), Vector2(cx - gap, cy), xh_color, thick)
			draw_line(Vector2(cx + gap, cy), Vector2(cx + gap + len, cy), xh_color, thick)
			draw_line(Vector2(cx, cy - gap - len), Vector2(cx, cy - gap), xh_color, thick)
			draw_line(Vector2(cx, cy + gap), Vector2(cx, cy + gap + len), xh_color, thick)
		1:
			var cpts := PackedVector2Array()
			for i in range(33):
				var ang := deg_to_rad(i * 11.25)
				cpts.append(Vector2(cx + cos(ang) * gap, cy + sin(ang) * gap))
			draw_polyline(cpts, xh_color, thick)
		2:
			draw_circle(Vector2(cx, cy), thick * 1.5, xh_color)
	if ch_outline:
		var ol := Color(0, 0, 0, 0.8)
		draw_line(Vector2(cx - gap - len - 1, cy), Vector2(cx - gap - 1, cy), ol, thick + 2)
		draw_line(Vector2(cx + gap + 1, cy), Vector2(cx + gap + len + 1, cy), ol, thick + 2)
		draw_line(Vector2(cx, cy - gap - len - 1), Vector2(cx, cy - gap - 1), ol, thick + 2)
		draw_line(Vector2(cx, cy + gap + 1), Vector2(cx, cy + gap + len + 1), ol, thick + 2)
	if ch_style != 2 and ch_dot:
		draw_circle(Vector2(cx, cy), 1.5, xh_color)
	# 移動／準度狀態回饋：蹲=加成（綠框）、空中/剛落地=劣化（紅框）
	match spread_state:
		2:
			_draw_state_brackets(cx, cy, gap + len + 8.0, Color(0.35, 1.0, 0.55, 0.55))
		3:
			_draw_state_brackets(cx, cy, gap + len + 8.0, Color(1.0, 0.30, 0.24, 0.75), true)
		4:
			_draw_state_brackets(cx, cy, gap + len + 12.0, Color(1.0, 0.55, 0.25, 0.6), true)
	# 散布範圍指示（四角小點）
	if spread_px > 2.0:
		var dd := gap + len + 4.0
		var ds := 1.5 + spread_ratio * 2.0
		draw_circle(Vector2(cx - dd, cy), ds, Color(xh_color.r, xh_color.g, xh_color.b, 0.5))
		draw_circle(Vector2(cx + dd, cy), ds, Color(xh_color.r, xh_color.g, xh_color.b, 0.5))
		draw_circle(Vector2(cx, cy - dd), ds, Color(xh_color.r, xh_color.g, xh_color.b, 0.5))
		draw_circle(Vector2(cx, cy + dd), ds, Color(xh_color.r, xh_color.g, xh_color.b, 0.5))
	# 後座图案預覽（練習用；預設關閉）
	if recoil_indicator:
		_draw_recoil_preview(cx, cy)
	# 擊殺閃爍（X）
	if _killflash_timer > 0.0:
		var u := _killflash_timer / 0.6
		_killflash_color.a = u
		var s := 28.0 * (1.0 + (1.0 - u) * 0.3)
		draw_line(Vector2(cx - s, cy - s), Vector2(cx + s, cy + s), _killflash_color, 5.0)
		draw_line(Vector2(cx + s, cy - s), Vector2(cx - s, cy + s), _killflash_color, 5.0)


func _draw_state_brackets(cx: float, cy: float, r: float, col: Color,
			inward: bool = false) -> void:
	## 四角括號：inward=true 時朝內（表示「不準」），否則朝外（表示「更準」）
	var d := -1.0 if inward else 1.0
	var seg := 6.0
	for sx in [-1.0, 1.0]:
		for sy in [-1.0, 1.0]:
			var p0 := Vector2(cx + sx * r, cy + sy * r)
			draw_line(p0, p0 + Vector2(sx * seg * d, 0.0), col, 2.0)
			draw_line(p0, p0 + Vector2(0.0, sy * seg * d), col, 2.0)


func _draw_recoil_preview(cx: float, cy: float) -> void:
	## 把該槍的图案畫在準星上：已打出的發＝實心點，整串花紋＝淡線，
	## 目前累積偏移＝亮點（含隨機 yaw），保護彈期＝綠色光圈。
	if recoil_model == null or not recoil_model.has_data:
		return
	var px := _px_per_deg
	var total := recoil_model.pattern_length()
	if total <= 0:
		return
	var fired := clampi(recoil_model.bullet_index, 0, total)
	var prev := Vector2(cx, cy)
	for i in range(total):
		var off := recoil_model.pattern_point(i)
		var pos := Vector2(cx - off.x * px, cy - off.y * px)
		var played := i < fired
		# 已打出的那幾發亮、往後的花紋淡（預習用）；第 11 發之後淡到快看不见
		var a := 0.16
		if played:
			a = clampf(0.85 - float(fired - i - 1) * 0.07, 0.12, 0.85)
		draw_circle(pos, (1.7 if played else 1.1) + float(mini(i, 8)) * 0.12,
				Color(0.55, 0.95, 1.0, a))
		if i > 0:
			draw_line(prev, pos, Color(0.55, 0.95, 1.0, 0.22 if played else 0.08), 1.0)
		prev = pos
	var cur := Vector2(cx - recoil_model.yaw * px, cy - recoil_model.pitch * px)
	draw_line(Vector2(cx, cy), cur, Color(1.0, 0.5, 0.35, 0.55), 1.5)
	draw_circle(cur, 2.6, Color(1.0, 0.82, 0.4, 0.95))
	var left := recoil_model.protected_left()
	if left > 0:
		draw_circle(Vector2(cx, cy), 4.0 + float(left) * 2.2, Color(0.4, 1.0, 0.6, 0.22))
		draw_arc(Vector2(cx, cy), 4.0 + float(left) * 2.2, 0.0, TAU, 24,
				Color(0.4, 1.0, 0.6, 0.5), 1.0)

# ──── 狙擊鏡 overlay ─────────────────────
func _draw_kill_banner(vp: Vector2, font: Font) -> void:
	if _banner_timer <= 0.0 or _banner_text == "":
		return
	var u := _banner_timer / 2.2                       # 1 → 0
	var alpha: float = clampf((1.0 - u) * 8.0, 0.0, 1.0) * clampf(u * 4.0, 0.0, 1.0)
	var cy := vp.y * 0.80
	var pop := 1.0 + (1.0 - clampf((1.0 - u) * 6.0, 0.0, 1.0)) * 0.12
	var fs := int(30.0 * (vp.y / 720.0) * pop)
	var main := "你擊殺了  " + _banner_text
	var col := _banner_color if _banner_frame != "default" else Color(1.0, 0.32, 0.28)
	col = Color(col.r, col.g, col.b, alpha)
	var w := font.get_string_size(main, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
	var cx := vp.x * 0.5 - w * 0.5
	# 底部襯條（傳說皮加高、加系列色描邊）
	var pad := 18.0 + (6.0 if _banner_frame != "default" else 0.0)
	var box := Rect2(cx - pad, cy - fs - 8, w + pad * 2.0, fs + 20 + (10.0 if _banner_level >= 4 else 0.0))
	draw_rect(box, Color(0.05, 0.05, 0.07, alpha * (0.55 if _banner_frame == "default" else 0.75)))
	if _banner_frame != "default":
		var top := Vector2(box.position.x, box.position.y)
		draw_line(top, Vector2(box.end.x, top.y), Color(col.r, col.g, col.b, alpha * 0.85), 2.0)
		draw_line(Vector2(box.position.x, box.end.y), Vector2(box.end.x, box.end.y),
			Color(col.r, col.g, col.b, alpha * 0.45), 1.5)
		# 等級點（Radianite 升級可見化）
		for i in _banner_level:
			var px := box.position.x + 10 + i * 9.0
			draw_rect(Rect2(px, box.position.y - 5, 6, 3),
				Color(col.r, col.g, col.b, alpha * 0.9))
	draw_string(font, Vector2(cx, cy), main, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
	if _banner_weapon != "":
		var ws := int(fs * 0.45)
		var wt := _banner_weapon
		var ww := font.get_string_size(wt, HORIZONTAL_ALIGNMENT_LEFT, -1, ws).x
		draw_string(font, Vector2(vp.x * 0.5 - ww * 0.5, cy + ws * 1.3), wt,
			HORIZONTAL_ALIGNMENT_LEFT, -1, ws, Color(col.r, col.g, col.b, alpha * 0.95))
	if _banner_hs:
		var hs_fs := int(fs * 0.5)
		var ht := "[爆頭]"
		var hw := font.get_string_size(ht, HORIZONTAL_ALIGNMENT_LEFT, -1, hs_fs).x
		draw_string(font, Vector2(cx + w + 10, cy), ht,
			HORIZONTAL_ALIGNMENT_LEFT, -1, hs_fs, Color(1.0, 0.8, 0.2, alpha))


func _draw_scope_overlay(vp: Vector2, font: Font) -> void:
	if not is_ads or not is_scoped:
		return
	var cx := vp.x * 0.5
	var cy := vp.y * 0.5
	var radius := minf(vp.x, vp.y) * 0.42
	# 外圈黑色遮罩（圆形瞄準鏡外的區域变暗）
	# 上方弧形
	for i in range(60):
		var angle := deg_to_rad(-180 + i * 3)
		var next_angle := deg_to_rad(-180 + (i + 1) * 3)
		var p1 := Vector2(cx + cos(angle) * radius, cy + sin(angle) * radius)
		var p2 := Vector2(cx + cos(next_angle) * radius, cy + sin(next_angle) * radius)
		var p3 := Vector2(cx + cos(next_angle) * (radius + 300), cy + sin(next_angle) * (radius + 300))
		var p4 := Vector2(cx + cos(angle) * (radius + 300), cy + sin(angle) * (radius + 300))
		draw_colored_polygon(PackedVector2Array([p1, p2, p3, p4]), Color(0, 0, 0, 0.85))
	# 中央圓圈邊框
	var circle_color := Color(0.8, 0.85, 0.9, 0.9)
	var circle_points := PackedVector2Array()
	for i in range(64):
		var angle := deg_to_rad(i * 360.0 / 64.0)
		circle_points.append(Vector2(cx + cos(angle) * radius, cy + sin(angle) * radius))
	circle_points.append(circle_points[0])
	draw_polyline(circle_points, circle_color, 2.0)
	# 十字線（紅色）
	var cross_len := radius * 0.85
	var cross_gap := 8.0
	var cross_color := Color(0.9, 0.2, 0.2, 0.9)
	# 水平線（中斷）
	draw_line(Vector2(cx - cross_len, cy), Vector2(cx - cross_gap, cy), cross_color, 1.5)
	draw_line(Vector2(cx + cross_gap, cy), Vector2(cx + cross_len, cy), cross_color, 1.5)
	# 垂直線（中斷）
	draw_line(Vector2(cx, cy - cross_len), Vector2(cx, cy - cross_gap), cross_color, 1.5)
	draw_line(Vector2(cx, cy + cross_gap), Vector2(cx, cy + cross_len), cross_color, 1.5)
	# 中央小點
	draw_circle(Vector2(cx, cy), 2.0, cross_color)
	# 刻度線（每 30 度）
	for i in range(12):
		var angle := deg_to_rad(i * 30)
		var inner := radius - 6.0
		var outer := radius + 2.0
		draw_line(
			Vector2(cx + cos(angle) * inner, cy + sin(angle) * inner),
			Vector2(cx + cos(angle) * outer, cy + sin(angle) * outer),
			Color(0.6, 0.65, 0.7, 0.6), 1.0)
	# 距離刻度（左右兩側）
	for i in range(1, 5):
		var offset := float(i) * radius * 0.2
		var tick_len := 4.0
		draw_line(Vector2(cx - offset, cy - tick_len), Vector2(cx - offset, cy + tick_len),
			Color(0.5, 0.55, 0.6, 0.4), 1.0)
		draw_line(Vector2(cx + offset, cy - tick_len), Vector2(cx + offset, cy + tick_len),
			Color(0.5, 0.55, 0.6, 0.4), 1.0)


# ──── 比分條（上方中央）──────────────
func _draw_score_bar(vp: Vector2, font: Font) -> void:
	var w := 280.0
	var h := 48.0
	var x := (vp.x - w) * 0.5
	var y := 8.0
	# 背景面板
	draw_rect(Rect2(x, y, w, h), COL_PANEL)
	# 攻方分數（左側紅色）
	draw_rect(Rect2(x, y, w * 0.42, h), Color(COL_ATTACK.r, COL_ATTACK.g, COL_ATTACK.b, 0.25))
	var atk_label := str(score_attack)
	var atk_size := 32
	var atk_w := font.get_string_size(atk_label, HORIZONTAL_ALIGNMENT_LEFT, -1, atk_size).x
	draw_string(font, Vector2(x + w * 0.42 * 0.5 - atk_w * 0.5, y + 36), atk_label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, atk_size, COL_ATTACK)
	# 中間 "回合" 號碼
	var round_label := "R%d" % round_number
	var round_size := 20
	var round_w := font.get_string_size(round_label, HORIZONTAL_ALIGNMENT_LEFT, -1, round_size).x
	draw_string(font, Vector2(x + w * 0.5 - round_w * 0.5, y + 30), round_label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, round_size, COL_TEXT_DIM)
	# 守方分數（右側藍色）
	draw_rect(Rect2(x + w * 0.58, y, w * 0.42, h), Color(COL_DEFEND.r, COL_DEFEND.g, COL_DEFEND.b, 0.25))
	var def_label := str(score_defend)
	var def_w := font.get_string_size(def_label, HORIZONTAL_ALIGNMENT_LEFT, -1, atk_size).x
	draw_string(font, Vector2(x + w * 0.58 + w * 0.42 * 0.5 - def_w * 0.5, y + 36), def_label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, atk_size, COL_DEFEND)


# ──── 階段標籤（比分條下方）+ 回合倒數（最後10秒紅色放大）────────────
func _draw_phase_label(vp: Vector2, font: Font) -> void:
	if phase_text == "":
		return
	var fs := 18
	var label := phase_text
	var col := COL_TEXT_DIM
	if phase_text == "買槍":
		col = Color(0.3, 0.8, 1.0)
	elif phase_text == "行動":
		col = Color(1.0, 0.8, 0.3)
	elif phase_text == "結算":
		col = Color(0.7, 0.7, 0.7)
	if round_timer >= 0:
		if round_timer <= 10:
			fs = 32
			col = Color(1.0, 0.25, 0.2)
			label = str(round_timer)
		else:
			label = "%s  %d" % [phase_text, round_timer]
	var text_w := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var cx := vp.x * 0.5
	var y := 68.0
	draw_string(font, Vector2(cx - text_w * 0.5, y + fs), label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)


# ──── 血量 + 護甲（左下，特戰式大字+分段條）────────────
func _draw_health_shield(vp: Vector2, font: Font) -> void:
	var x := 16.0
	var y := vp.y - 80.0
	var hp_bar_w := 200.0
	var bar_h := 10.0
	# 大血量數字
	var hp_color := COL_HEALTH if health > 30 else COL_AMMO_LOW
	draw_string(font, Vector2(x, y + 36), str(health),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 36, hp_color)
	# 護甲數字（在血量右側）
	if max_shield > 0:
		draw_string(font, Vector2(x + 80, y + 30), str(shield),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_SHIELD)
	# 血量條背景
	var bar_y := y + 48.0
	draw_rect(Rect2(x, bar_y, hp_bar_w, bar_h), Color(0.15, 0.15, 0.2, 0.85))
	var hp_frac := clampf(float(health) / float(max_health), 0.0, 1.0)
	var hp_bar_color := COL_HEALTH if hp_frac > 0.3 else COL_AMMO_LOW
	draw_rect(Rect2(x, bar_y, hp_bar_w * hp_frac, bar_h), hp_bar_color)
	# 護甲條（在血量條上方，黃色分段）
	if max_shield > 0:
		var sh_y := bar_y - 14.0
		var sh_frac := clampf(float(shield) / float(max_shield), 0.0, 1.0)
		var seg := 5.0
		for s in range(int(seg)):
			var seg_x := x + hp_bar_w * (float(s) / seg)
			var seg_w := hp_bar_w / seg - 1.0
			var fill := clampf((sh_frac * seg) - float(s), 0.0, 1.0)
			draw_rect(Rect2(seg_x, sh_y, seg_w, 8.0), Color(0.15, 0.15, 0.2, 0.85))
			if fill > 0.0:
				draw_rect(Rect2(seg_x, sh_y, seg_w * fill, 8.0), COL_SHIELD)
	# 死亡提示
	if health <= 0:
		draw_string(font, Vector2(x, y + 36), "死亡",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 36, COL_AMMO_LOW)


# ──── 彈匣 + 金錢（右下，含武器類別圖示）────────────
func _draw_ammo_money(vp: Vector2, font: Font) -> void:
	var panel_w := 200.0
	var panel_h := 90.0
	var x := vp.x - panel_w - 12.0
	var y := vp.y - panel_h - 12.0
	draw_rect(Rect2(x, y, panel_w, panel_h), COL_PANEL)
	# 武器類別圖示
	var icon_x := x + panel_w - 45.0
	var icon_y := y + 10.0
	match weapon_slot:
		0: # 刀
			draw_line(Vector2(icon_x, icon_y), Vector2(icon_x + 30, icon_y + 25), Color(0.7, 0.7, 0.7, 0.5), 2.0)
		1: # 手槍
			draw_rect(Rect2(icon_x, icon_y + 8, 22, 10), Color(0.7, 0.7, 0.7, 0.5))
			draw_rect(Rect2(icon_x + 22, icon_y + 11, 8, 4), Color(0.7, 0.7, 0.7, 0.5))
		2: # 主武器
			draw_rect(Rect2(icon_x, icon_y + 6, 36, 8), Color(0.7, 0.7, 0.7, 0.5))
			draw_rect(Rect2(icon_x + 8, icon_y + 14, 12, 6), Color(0.7, 0.7, 0.7, 0.5))
	# 武器名
	draw_string(font, Vector2(x + 12, y + 24), weapon_name,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, COL_TEXT_DIM)
	# 彈匣
	var ammo_color := COL_AMMO_LOW if mag <= 5 and mag_max > 0 else COL_AMMO_OK
	var ammo_str := "%d / %d" % [mag, mag_max]
	draw_string(font, Vector2(x + 12, y + 56), ammo_str,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 30, ammo_color)
	# 金錢（$ 圖示）
	draw_string(font, Vector2(x + 12, y + 82), "$%d" % credits,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, COL_MONEY)


# ──── 小地圖（左上，特戰式地形+隊伍+朝向）────────────────
func _draw_minimap(vp: Vector2, font: Font) -> void:
	var map_w := 180.0
	var map_h := 180.0
	var mx := 12.0
	var my := 12.0
	draw_rect(Rect2(mx, my, map_w, map_h), Color(0.06, 0.07, 0.10, 0.80))
	draw_rect(Rect2(mx, my, map_w, map_h), Color(0.35, 0.35, 0.4, 0.5), false, 1.0)
	if map_data.is_empty():
		return
	# 地圖範圍
	var bounds: Dictionary = map_data.get("bounds_min", {})
	var bmax: Dictionary = map_data.get("bounds_max", {})
	if bounds.is_empty() or bmax.is_empty():
		return
	var mn := Vector2(bounds.get("x", -20.0), bounds.get("z", -20.0))
	var mx2 := Vector2(bmax.get("x", 20.0), bmax.get("z", 20.0))
	var range_xy := mx2 - mn
	if range_xy.x <= 0 or range_xy.y <= 0:
		return
	# 繪製牆壁（灰色線段）
	var walls: Array = map_data.get("walls", [])
	for w in walls:
		var wmn: Dictionary = w.get("mn", {})
		var wmx: Dictionary = w.get("mx", {})
		var p1 := _map_to_mini(Vector2(wmn.get("x", 0), wmn.get("z", 0)), mn, range_xy, mx, my, map_w, map_h)
		var p2 := _map_to_mini(Vector2(wmx.get("x", 0), wmx.get("z", 0)), mn, range_xy, mx, my, map_w, map_h)
		draw_line(p1, p2, Color(0.5, 0.5, 0.5, 0.6), 1.0)
	# 繪製 Spike 點位
	var sites: Array = map_data.get("sites", [])
	for s in sites:
		var sc: Dictionary = s.get("center", {})
		var pos := _map_to_mini(Vector2(sc.get("x", 0), sc.get("z", 0)), mn, range_xy, mx, my, map_w, map_h)
		draw_circle(pos, 4.0, Color(COL_SPIKE.r, COL_SPIKE.g, COL_SPIKE.b, 0.7))
		draw_string(font, Vector2(pos.x - 4, pos.y - 8), s.get("name", "?"),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_SPIKE)
	# 繪製玩家（圓點 + 朝向箭頭）
	for i in range(10):
		var snap: Dictionary = players_dict.get(i, {})
		if snap.is_empty():
			continue
		var ppos: Vector3 = snap.get("pos", Vector3.ZERO)
		var vel: Vector3 = snap.get("vel", Vector3.ZERO)
		var alive: bool = snap.get("alive", true)
		if not alive:
			continue
		var pos := _map_to_mini(Vector2(ppos.x, ppos.z), mn, range_xy, mx, my, map_w, map_h)
		var col := COL_ATTACK if i < 5 else COL_DEFEND
		if i == own_slot:
			draw_circle(pos, 5.0, Color.WHITE)
			var dir := Vector2(vel.x, vel.z).normalized()
			if dir.length() > 0.1:
				draw_line(pos, pos + dir * 8.0, Color.WHITE, 2.0)
		else:
			draw_circle(pos, 3.0, col)
			var dir := Vector2(vel.x, vel.z).normalized()
			if dir.length() > 0.1:
				draw_line(pos, pos + dir * 6.0, col, 1.5)


func _map_to_mini(world_pos: Vector2, mn: Vector2, range_xy: Vector2,
		map_x: float, map_y: float, mw: float, mh: float) -> Vector2:
	var nx := (world_pos.x - mn.x) / range_xy.x
	var ny := (world_pos.y - mn.y) / range_xy.y
	return Vector2(map_x + nx * mw, map_y + ny * mh)


# ──── 擊殺訊息（右上）──────────────
func _draw_kill_feed(vp: Vector2, font: Font) -> void:
	var fx := vp.x - 20.0
	var fy := 20.0
	for f in feed:
		var a := clampf(5.0 - float(f["t"]), 0.0, 1.0)
		if a <= 0.0:
			continue
		var text: String = f["text"]
		var size := 16
		var text_w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
		var line_h := size + 8.0
		# 半透明背景
		draw_rect(Rect2(fx - text_w - 12, fy - size, text_w + 16, line_h),
			Color(0, 0, 0, 0.5 * a))
		var c := COL_TEXT
		c.a = a
		draw_string(font, Vector2(fx - text_w - 4, fy), text,
			HORIZONTAL_ALIGNMENT_LEFT, -1, size, c)
		fy += line_h


# ──── 宣告（中央，回合結束全螢幕覆蓋）──────────────────
func _draw_announce(vp: Vector2, font: Font) -> void:
	if _announce_timer <= 0.0 or announce_text == "":
		return
	var cx := vp.x * 0.5
	var cy := vp.y * 0.35
	var a := clampf(_announce_timer, 0.0, 1.0)
	# 全螢幕暗色覆蓋
	var bg_alpha := a * 0.35
	draw_rect(Rect2(0, 0, vp.x, vp.y), Color(0, 0, 0, bg_alpha))
	# 回合結束大字（特戰風格）
	var fs := 64
	var text_w := font.get_string_size(announce_text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	# 背景條
	var strip_h := fs + 30
	draw_rect(Rect2(0, cy - fs * 0.6, vp.x, strip_h),
		Color(announce_color.r, announce_color.g, announce_color.b, a * 0.15))
	draw_rect(Rect2(0, cy - fs * 0.6, vp.x, strip_h),
		Color(announce_color.r, announce_color.g, announce_color.b, a * 0.4), false, 2.0)
	# 文字
	announce_color.a = a
	draw_string(font, Vector2(cx - text_w * 0.5, cy + fs * 0.3), announce_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, announce_color)


# ──── 連線統計（右上角小字）────────
func _draw_net_stats(vp: Vector2, font: Font) -> void:
	var x := vp.x - 12.0
	var y := 20.0
	var fs := 13
	var lines := [
		"RTT %s ms | tick %s" % [ping_text, tick_text],
		"players %d" % players_dict.size(),
	]
	for line in lines:
		var text_w := font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
		draw_string(font, Vector2(x - text_w, y), line,
			HORIZONTAL_ALIGNMENT_LEFT, -1, fs, COL_TEXT_DIM)
		y += fs + 4


# ──── Spike 狀態（中上，特戰式脈衝 + 弧形計時）────────────
func _draw_spike_status(vp: Vector2, font: Font) -> void:
	if spike_text == "" or _spike_timer <= 0.0:
		return
	var cx := vp.x * 0.5
	var cy := 100.0
	var pulse := 1.0 + sinf(_spike_timer * 8.0) * 0.15
	var radius := 18.0 * pulse
	var alpha := clampf(_spike_timer / 1.0, 0.3, 1.0)
	# 外圈脈衝
	draw_arc(Vector2(cx, cy), radius, 0, TAU, 32,
		Color(COL_SPIKE.r, COL_SPIKE.g, COL_SPIKE.b, alpha * 0.4), 3.0)
	# 弧形計時（倒數 45 秒 → 圓弧遞減）
	var max_t := 45.0
	var frac := clampf(_spike_timer / max_t, 0.0, 1.0)
	var arc_r := 24.0
	draw_arc(Vector2(cx, cy), arc_r, deg_to_rad(-90), deg_to_rad(-90 + frac * 360), 32,
		Color(COL_SPIKE.r, COL_SPIKE.g, COL_SPIKE.b, alpha), 3.0)
	# 中心文字
	var fs := 16
	var label := spike_text
	var tw := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	draw_string(font, Vector2(cx - tw * 0.5, cy + fs * 0.4), label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(COL_SPIKE.r, COL_SPIKE.g, COL_SPIKE.b, alpha))


# ──── 技能欄（下方中央，特戰式弧形冷卻）──────
func _draw_ability_bar(vp: Vector2, font: Font) -> void:
	var slot_w := 56.0
	var slot_h := 56.0
	var gap := 6.0
	var total_w := slot_w * 4 + gap * 3
	var x := (vp.x - total_w) * 0.5
	var y := vp.y - slot_h - 16.0
	var keys := ["C", "Q", "E", "X"]
	var key_colors := [
		Color(0.3, 0.8, 1.0),
		Color(0.2, 0.9, 0.4),
		Color(0.9, 0.8, 0.2),
		Color(0.9, 0.3, 0.2),
	]
	for i in range(4):
		var sx := x + i * (slot_w + gap)
		var cx2 := sx + slot_w * 0.5
		var cy2 := y + slot_h * 0.5
		var cd: float = ability_cooldowns[i]
		var on_cd := cd > 0.0
		var col := key_colors[i]
		if on_cd:
			col = Color(0.3, 0.3, 0.35)
		draw_rect(Rect2(sx, y, slot_w, slot_h), Color(0.08, 0.09, 0.14, 0.85))
		draw_rect(Rect2(sx, y, slot_w, slot_h), col if not on_cd else Color(0.25, 0.25, 0.3, 0.6), false, 2.0)
		if on_cd and ability_max_cds[i] > 0:
			var frac: float = 1.0 - (cd / float(ability_max_cds[i]))
			var radius := slot_w * 0.42
			var pts := PackedVector2Array()
			for j in range(33):
				var ang := deg_to_rad(-90.0 + frac * 360.0 * j / 32.0)
				pts.append(Vector2(cx2 + cos(ang) * radius, cy2 + sin(ang) * radius))
			draw_polyline(pts, Color(col.r, col.g, col.b, 0.4), 3.0)
		var key_size := 20
		var key_w := font.get_string_size(keys[i], HORIZONTAL_ALIGNMENT_LEFT, -1, key_size).x
		draw_string(font, Vector2(cx2 - key_w * 0.5, cy2 + 7), keys[i],
			HORIZONTAL_ALIGNMENT_LEFT, -1, key_size, col)
		if on_cd:
			var cd_str := "%.0f" % cd
			var cd_w := font.get_string_size(cd_str, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x
			draw_string(font, Vector2(cx2 - cd_w * 0.5, y + slot_h - 4), cd_str,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_AMMO_LOW)
		elif i == 3 and ult_cost > 0:
			# 終點球：畫 n 格充能（而不是「OK」），滿了就呼吸發光
			var pw := 8.0
			var n := clampi(ult_cost, 1, 12)
			var row_w := pw * float(n) + 2.0 * float(n - 1)
			var px0 := cx2 - row_w * 0.5
			for k in range(n):
				var filled: bool = k < ult_points
				var pc := Color(1.0, 0.78, 0.28) if filled else Color(1, 1, 1, 0.16)
				draw_rect(Rect2(px0 + float(k) * (pw + 2.0), y + slot_h - 11.0, pw, 6.0), pc)
			if ult_ready:
				var glow := 0.45 + 0.35 * sin(_ult_pulse)
				draw_rect(Rect2(sx - 2.0, y - 2.0, slot_w + 4.0, slot_h + 4.0),
						Color(1.0, 0.82, 0.35, glow), false, 2.0)
		else:
			var ready_w := font.get_string_size("OK", HORIZONTAL_ALIGNMENT_LEFT, -1, 10).x
			draw_string(font, Vector2(cx2 - ready_w * 0.5, y + slot_h - 4), "OK",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(col.r, col.g, col.b, 0.6))
		# 使用次數點點（終點球槽不畫：它上面已有充能格）
		if not (i == 3 and ult_cost > 0):
			var left := clampi(int(ability_charges[i]) if ability_charges.size() > i else 1, 0, 3)
			if left > 0:
				for k in range(left):
					draw_circle(Vector2(cx2 - 8.0 + float(k) * 8.0, y + 8.0), 2.4,
							Color(col.r, col.g, col.b, 0.9))
			elif not on_cd:
				draw_rect(Rect2(sx, y, slot_w, slot_h), Color(1.0, 0.35, 0.3, 0.14))
	# 被 KAY/O 壓制：整條技能蓋上一層紫
	if ult_blocked:
		draw_rect(Rect2(sx, y, slot_w, slot_h), Color(0.55, 0.25, 0.85, 0.28))


# ──── 隊伍構成（頂部，比分下方小圖示）
func _draw_agent_dots(vp: Vector2, font: Font) -> void:
	var dot_r := 8.0
	var y := 60.0
	# 攻方（左側）
	for i in range(5):
		var x := 12.0 + i * (dot_r * 2 + 4)
		draw_circle(Vector2(x + dot_r, y + dot_r), dot_r, COL_ATTACK)
		var label := "A%d" % i
		draw_string(font, Vector2(x + dot_r - 5, y + dot_r + 4), label,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color.WHITE)
	# 守方（右側）
	var vp_w := get_viewport_rect().size.x
	for i in range(5):
		var x := vp_w - 12.0 - (5 - i) * (dot_r * 2 + 4)
		draw_circle(Vector2(x, y + dot_r), dot_r, COL_DEFEND)
		var label := "D%d" % i
		draw_string(font, Vector2(x - 5, y + dot_r + 4), label,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color.WHITE)


func _draw_team_status(vp: Vector2, font: Font) -> void:
	var x := 12.0
	var y := 200.0
	var fs := 13
	for i in range(10):
		var snap: Dictionary = players_dict.get(i, {})
		if snap.is_empty():
			continue
		var alive: bool = snap.get("alive", true)
		var col := COL_ATTACK if i < 5 else COL_DEFEND
		var sy := y + i * (fs + 6)
		var label := "P%02d" % i
		if i == own_slot:
			label += " (我)"
		if not alive:
			col = Color(0.4, 0.4, 0.42)
		draw_string(font, Vector2(x, sy), label,
			HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
		if alive:
			draw_circle(Vector2(x + 80, sy - 3), 3.0, col)
		else:
			draw_line(Vector2(x + 77, sy - 6), Vector2(x + 83, sy), Color(0.7, 0.2, 0.2, 0.8), 2.0)
			draw_line(Vector2(x + 77, sy), Vector2(x + 83, sy - 6), Color(0.7, 0.2, 0.2, 0.8), 2.0)


func _draw_hitmarker(vp: Vector2, font: Font) -> void:
	if _hitmarker_timer <= 0.0:
		return
	var cx := vp.x * 0.5
	var cy := vp.y * 0.5
	var alpha := _hitmarker_timer / 0.25
	var len := 4.0 * maxf(0.6, _hitmarker_scale)
	var gap := 6.0 * maxf(0.6, _hitmarker_scale)
	var col := Color(_hitmarker_color.r, _hitmarker_color.g, _hitmarker_color.b, alpha)
	var sc := maxf(0.6, _hitmarker_scale)
	if _hitmarker_headshot:
		col = Color(1.0, 0.2, 0.2, alpha)
		draw_line(Vector2(cx - gap - len - 1, cy - gap - len - 1), Vector2(cx - gap + 1, cy - gap + 1), Color(1, 1, 1, alpha * 0.6), 3.0)
		draw_line(Vector2(cx + gap + 1, cy - gap - len - 1), Vector2(cx + gap - 1, cy - gap + 1), Color(1, 1, 1, alpha * 0.6), 3.0)
		draw_line(Vector2(cx - gap - len - 1, cy + gap + len + 1), Vector2(cx - gap + 1, cy + gap - 1), Color(1, 1, 1, alpha * 0.6), 3.0)
		draw_line(Vector2(cx + gap + 1, cy + gap + len + 1), Vector2(cx + gap - 1, cy + gap - 1), Color(1, 1, 1, alpha * 0.6), 3.0)
	draw_line(Vector2(cx - gap - len, cy - gap - len), Vector2(cx - gap, cy - gap), col, 2.0)
	draw_line(Vector2(cx + gap, cy - gap - len), Vector2(cx + gap + len, cy - gap), col, 2.0)
	draw_line(Vector2(cx - gap - len, cy + gap + len), Vector2(cx - gap, cy + gap), col, 2.0)
	draw_line(Vector2(cx + gap, cy + gap + len), Vector2(cx + gap + len, cy + gap), col, 2.0)


func _draw_damage_numbers(vp: Vector2, font: Font) -> void:
	var fs := 22
	for d in _damage_numbers:
		var t: float = d["t"]
		var amount: float = d["amount"]
		var alpha := 1.0 - t
		if alpha <= 0.0:
			continue
		var y_pos := vp.y * 0.4 - t * 80.0
		var col := Color(1.0, 1.0, 1.0, alpha)
		if amount < 0:
			col = Color(1.0, 0.3, 0.2, alpha)
		var text := str(int(absf(amount)))
		if amount < 0:
			text = "-" + text
		var text_w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
		draw_string(font, Vector2(vp.x * 0.5 - text_w * 0.5, y_pos), text,
			HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)


func _draw_damage_direction(vp: Vector2) -> void:
	if _damage_direction_timer <= 0.0:
		return
	var cx := vp.x * 0.5
	var cy := vp.y * 0.5
	var alpha := _damage_direction_timer / 0.8
	var radius := 60.0
	var arc_color := Color(1.0, 0.25, 0.2, alpha)
	var arc_start := _damage_direction_angle - deg_to_rad(20.0)
	var arc_end := _damage_direction_angle + deg_to_rad(20.0)
	draw_arc(Vector2(cx, cy), radius, arc_start, arc_end, 20, arc_color, 3.0)
	var tip_x := cx + cos(_damage_direction_angle) * radius
	var tip_y := cy + sin(_damage_direction_angle) * radius
	var perp_x := cos(_damage_direction_angle + PI * 0.5) * 5.0
	var perp_y := sin(_damage_direction_angle + PI * 0.5) * 5.0
	var back_dist := 10.0
	var back_x := cx + cos(_damage_direction_angle) * (radius - back_dist)
	var back_y := cy + sin(_damage_direction_angle) * (radius - back_dist)
	var tri := PackedVector2Array([
		Vector2(tip_x + perp_x, tip_y + perp_y),
		Vector2(tip_x - perp_x, tip_y - perp_y),
		Vector2(back_x, back_y),
	])
	draw_colored_polygon(tri, arc_color)


func _draw_health_bar_visual(vp: Vector2, font: Font) -> void:
	var bar_w := 180.0
	var bar_h := 14.0
	var x := 20.0
	var y := vp.y - 60.0
	draw_rect(Rect2(x, y, bar_w, bar_h), Color(0.15, 0.15, 0.18, 0.85))
	var hp_frac := clampf(float(health) / float(max_health), 0.0, 1.0)
	var hp_color := COL_HEALTH if hp_frac > 0.3 else COL_AMMO_LOW
	draw_rect(Rect2(x, y, bar_w * hp_frac, bar_h), hp_color)
	if max_shield > 0:
		var sh_frac := clampf(float(shield) / float(max_shield), 0.0, 1.0)
		var sh_x := x + bar_w * hp_frac
		draw_rect(Rect2(sh_x, y, bar_w * sh_frac, bar_h), COL_SHIELD)
	var hp_text := str(health)
	if max_shield > 0:
		hp_text += " | " + str(shield)
	draw_string(font, Vector2(x + 4, y + bar_h - 2), hp_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color.WHITE)


func _draw_weapon_silhouette(vp: Vector2, font: Font) -> void:
	var x := vp.x - 120.0
	var y := vp.y - 60.0
	var col := Color(1.0, 1.0, 1.0, 0.4)
	var wn := weapon_name.to_lower()
	if wn.contains("rifle") or wn.contains("phantom") or wn.contains("vandal") or wn.contains("bulldog") or wn.contains("guardian"):
		draw_rect(Rect2(x, y, 60, 8), col)
		draw_rect(Rect2(x + 50, y - 2, 20, 4), col)
		draw_rect(Rect2(x + 20, y + 8, 8, 14), col)
	elif wn.contains("pistol") or wn.contains("classic") or wn.contains("shorty") or wn.contains("frenzy") or wn.contains("ghost") or wn.contains("sheriff"):
		draw_rect(Rect2(x, y, 36, 8), col)
		draw_rect(Rect2(x + 28, y + 8, 6, 12), col)
	elif wn.contains("knife") or wn.contains("melee"):
		draw_line(Vector2(x, y), Vector2(x + 40, y + 30), col, 3.0)
		draw_line(Vector2(x + 40, y + 30), Vector2(x + 44, y + 26), col, 2.0)
	else:
		draw_rect(Rect2(x, y, 50, 8), col)
		draw_rect(Rect2(x + 42, y - 2, 14, 4), col)

