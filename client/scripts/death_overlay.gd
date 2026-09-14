class_name DeathOverlay
extends Control

## 死亡旁觀畫面 — 玩家死亡時顯示
##
## 功能：
##   1. 死亡瞬間灰屏淡入 + 「你已被擊殺」橫幅
##   2. 顯示擊殺者資訊（名字 + 武器 + 距離）
##   3. 旁觀攝影機切換：跟隨存活隊友（左右鍵切換）
##   4. 回合剩餘時間倒數
##   5. 隊友存活狀態面板（5 人列表 + 存活/死亡）
##   6. 3 秒後自動切換到旁觀模式

# ──── 顏色 ────
const COL_BG := Color(0.02, 0.02, 0.04, 0.85)
const COL_RED := Color(0.92, 0.22, 0.28)
const COL_GREEN := Color(0.15, 0.85, 0.30)
const COL_DIM := Color(0.50, 0.53, 0.60)
const COL_TEXT := Color(0.94, 0.95, 0.97)
const COL_GOLD := Color(1.0, 0.82, 0.32)

# ──── 狀態 ────
var _anim_t := 0.0
var _death_timer := 0.0
var _is_dead := false
var _killer_name := ""
var _killer_weapon := ""
var _kill_distance := 0.0
var _is_headshot := false
var _spectate_target := -1
var _spectate_targets: Array = []  # 存活隊友 slot 列表
var _own_slot := -1
var _own_team := 0

# ──── 外部資料 ────
var players_dict: Dictionary = {}
var round_timer := -1
var phase_text := ""

# ──── 信號 ────
signal spectate_changed(slot: int)


func _ready() -> void:
	set_process(true)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false


func show_death(killer_name: String, weapon: String, headshot: bool, distance: float) -> void:
	_killer_name = killer_name
	_killer_weapon = weapon
	_is_headshot = headshot
	_kill_distance = distance
	_death_timer = 0.0
	_anim_t = 0.0
	_is_dead = true
	visible = true
	_update_spectate_targets()


func hide_death() -> void:
	_is_dead = false
	visible = false
	_spectate_target = -1


func is_dead() -> bool:
	return _is_dead


func _process(delta: float) -> void:
	if not _is_dead:
		return
	_anim_t += delta
	_death_timer += delta
	# 3 秒後進入旁觀模式
	if _death_timer > 3.0 and _spectate_target < 0 and _spectate_targets.size() > 0:
		_spectate_target = _spectate_targets[0]
		spectate_changed.emit(_spectate_target)
	# 左右鍵切換旁觀目標
	if Input.is_action_just_pressed("ui_left") or Input.is_key_pressed(KEY_Q):
		_cycle_spectate(-1)
	if Input.is_action_just_pressed("ui_right") or Input.is_key_pressed(KEY_E):
		_cycle_spectate(1)
	queue_redraw()


func _cycle_spectate(dir: int) -> void:
	if _spectate_targets.size() == 0:
		return
	if _spectate_target < 0:
		_spectate_target = _spectate_targets[0]
		return
	var idx := _spectate_targets.find(_spectate_target)
	if idx < 0:
		_spectate_target = _spectate_targets[0]
		return
	idx = (idx + dir + _spectate_targets.size()) % _spectate_targets.size()
	_spectate_target = _spectate_targets[idx]
	spectate_changed.emit(_spectate_target)


func _update_spectate_targets() -> void:
	_spectate_targets.clear()
	for s in range(10):
		if s == _own_slot:
			continue
		var p: Dictionary = players_dict.get(s, {})
		if p.is_empty():
			continue
		if int(p.get("team", 0)) != _own_team:
			continue
		if int(p.get("health", 0)) > 0:
			_spectate_targets.append(s)
	if _spectate_target >= 0 and not _spectate_targets.has(_spectate_target):
		_spectate_target = -1


func set_own_info(slot: int, team: int) -> void:
	_own_slot = slot
	_own_team = team


# ═══════════════════════════════════════════════
#  繪 製
# ═══════════════════════════════════════════════
func _draw() -> void:
	if not _is_dead:
		return
	var vp := get_viewport_rect().size
	var font := ThemeDB.fallback_font

	# 灰屏淡入（前 0.5s 淡入到 0.85）
	var bg_alpha := clampf(_death_timer * 2.0, 0.0, 0.85)
	draw_rect(Rect2(Vector2.ZERO, vp), Color(0.02, 0.02, 0.04, bg_alpha))

	# 死亡橫幅（前 3 秒顯示）
	if _death_timer < 4.0:
		_draw_death_banner(vp, font)

	# 旁觀提示（3 秒後）
	if _death_timer > 3.0:
		_draw_spectate_info(vp, font)

	# 隊友存活面板（右側）
	_draw_team_status(vp, font)

	# 回合剩餘時間（頂部中央）
	if round_timer >= 0:
		_draw_round_timer(vp, font)


func _draw_death_banner(vp: Vector2, font: Font) -> void:
	var cx := vp.x * 0.5
	var cy := vp.y * 0.30
	# 淡入淡出：0-0.3s 淡入，3-4s 淡出
	var alpha := 1.0
	if _death_timer < 0.3:
		alpha = _death_timer / 0.3
	elif _death_timer > 3.0:
		alpha = clampf((4.0 - _death_timer) / 1.0, 0.0, 1.0)
	alpha = clampf(alpha, 0.0, 1.0)

	# 主標題
	var title := "你已被擊殺"
	var fs := 42
	var tw := font.get_string_size(title, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
	draw_rect(Rect2(cx - tw * 0.5 - 24, cy - fs - 8, tw + 48, fs + 20),
		Color(0.08, 0.02, 0.04, alpha * 0.7))
	draw_string(font, Vector2(cx - tw * 0.5, cy), title,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(COL_RED.r, COL_RED.g, COL_RED.b, alpha))

	# 擊殺者資訊
	var cy2 := cy + 56
	var info := "由  %s  以  %s  擊殺" % [_killer_name, _killer_weapon]
	var fs2 := 18
	var iw := font.get_string_size(info, HORIZONTAL_ALIGNMENT_CENTER, -1, fs2).x
	draw_string(font, Vector2(cx - iw * 0.5, cy2), info,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs2, Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha * 0.8))

	# 爆頭標記
	if _is_headshot:
		var hs_text := "✦ 爆頭"
		var hs_fs := 16
		var hw := font.get_string_size(hs_text, HORIZONTAL_ALIGNMENT_LEFT, -1, hs_fs).x
		draw_string(font, Vector2(cx + iw * 0.5 + 12, cy2), hs_text,
			HORIZONTAL_ALIGNMENT_LEFT, -1, hs_fs, Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha))

	# 距離
	var dist_text := "距離: %.1fm" % _kill_distance
	var dt_fs := 14
	var dw := font.get_string_size(dist_text, HORIZONTAL_ALIGNMENT_LEFT, -1, dt_fs).x
	draw_string(font, Vector2(cx - dw * 0.5, cy2 + 28), dist_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, dt_fs, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha))


func _draw_spectate_info(vp: Vector2, font: Font) -> void:
	var cx := vp.x * 0.5
	var cy := vp.y * 0.20
	var alpha := clampf((_death_timer - 3.0) * 2.0, 0.0, 1.0)

	# 旁觀模式提示
	var spec_text := "旁觀模式"
	var fs := 24
	var sw := font.get_string_size(spec_text, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
	draw_string(font, Vector2(cx - sw * 0.5, cy), spec_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha * 0.7))

	# 切換提示
	var hint := "◀ Q / E 切換隊友 ▶"
	var hfs := 14
	var hw := font.get_string_size(hint, HORIZONTAL_ALIGNMENT_CENTER, -1, hfs).x
	draw_string(font, Vector2(cx - hw * 0.5, cy + 32), hint,
		HORIZONTAL_ALIGNMENT_LEFT, -1, hfs, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha * 0.6))

	# 當前旁觀目標
	if _spectate_target >= 0:
		var p: Dictionary = players_dict.get(_spectate_target, {})
		if not p.is_empty():
			var name_text := "正在旁觀: 隊友 P%02d" % _spectate_target
			var nfs := 16
			var nw := font.get_string_size(name_text, HORIZONTAL_ALIGNMENT_CENTER, -1, nfs).x
			draw_string(font, Vector2(cx - nw * 0.5, cy + 58), name_text,
				HORIZONTAL_ALIGNMENT_LEFT, -1, nfs, Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha * 0.7))


func _draw_team_status(vp: Vector2, font: Font) -> void:
	# 右側隊友存活面板
	var panel_w := 180.0
	var panel_h := 240.0
	var x := vp.x - panel_w - 12.0
	var y := 80.0
	var alpha := clampf(_death_timer * 2.0, 0.0, 0.9)

	draw_rect(Rect2(x, y, panel_w, panel_h), Color(0.04, 0.05, 0.08, alpha * 0.8))

	# 標題
	var title := "隊伍狀態"
	draw_string(font, Vector2(x + 12, y + 22), title,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha * 0.7))

	# 分隔線
	draw_line(Vector2(x + 12, y + 30), Vector2(x + panel_w - 12, y + 30),
		Color(0.25, 0.28, 0.35, alpha * 0.5), 1.0)

	# 隊友列表
	var team_start := _own_team * 5
	var row_y := y + 44
	for i in range(5):
		var slot := team_start + i
		var p: Dictionary = players_dict.get(slot, {})
		if p.is_empty():
			continue
		var alive := int(p.get("health", 0)) > 0
		var hp := int(p.get("health", 0))
		var is_self := slot == _own_slot
		var is_spec := slot == _spectate_target

		# 背景
		var row_col := Color(0.1, 0.12, 0.16, alpha * 0.4)
		if is_spec:
			row_col = Color(0.15, 0.25, 0.35, alpha * 0.6)
		draw_rect(Rect2(x + 8, row_y - 14, panel_w - 16, 32), row_col)

		# 狀態圖示
		var icon := "✕" if not alive else "✓"
		var icon_col := COL_RED if not alive else COL_GREEN
		icon_col.a = alpha
		draw_string(font, Vector2(x + 14, row_y), icon,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, icon_col)

		# 名字
		var name_str := "P%02d%s" % [slot, " (你)" if is_self else ""]
		var name_col := Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha * 0.8)
		if not alive:
			name_col = Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha * 0.5)
		draw_string(font, Vector2(x + 34, row_y), name_str,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 12, name_col)

		# 血量
		if alive:
			var hp_str := "%d HP" % hp
			var hp_col := COL_GREEN if hp > 50 else COL_RED
			hp_col.a = alpha * 0.7
			var hp_w := font.get_string_size(hp_str, HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x
			draw_string(font, Vector2(x + panel_w - 12 - hp_w, row_y), hp_str,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 11, hp_col)

		row_y += 38


func _draw_round_timer(vp: Vector2, font: Font) -> void:
	var cx := vp.x * 0.5
	var y := 12.0
	var fs := 28
	var label := "%ds" % round_timer
	var tw := font.get_string_size(label, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
	var alpha := clampf(_death_timer * 2.0, 0.0, 0.8)
	draw_rect(Rect2(cx - tw * 0.5 - 16, y, tw + 32, fs + 12),
		Color(0.04, 0.05, 0.08, alpha * 0.7))
	draw_string(font, Vector2(cx - tw * 0.5, y + fs), label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs,
		Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha))
