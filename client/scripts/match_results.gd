class_name MatchResults
extends Control

## 賽後結算頁面 — 比賽結束時顯示
##
## 功能：
##   1. 勝利/失敗大橫幅（勝 = 金色，敗 = 紅色）
##   2. 最終比分（攻方 vs 守方）
##   3. 全場計分板（10 名玩家：K/D/A、戰鬥評分）
##   4. MVP 表演選手
##   5. 回合記錄（每回合勝方 + 勝利原因）
##   6. 繼續按鈕 → 返回主選單

# ──── 顏色 ────
const COL_BG := Color(0.03, 0.04, 0.06, 0.95)
const COL_WIN := Color(1.0, 0.82, 0.32)
const COL_LOSE := Color(0.92, 0.22, 0.28)
const COL_ATTACK := Color(0.95, 0.28, 0.22)
const COL_DEFEND := Color(0.22, 0.55, 0.95)
const COL_TEXT := Color(0.94, 0.95, 0.97)
const COL_DIM := Color(0.50, 0.53, 0.60)
const COL_GREEN := Color(0.15, 0.85, 0.30)
const COL_GOLD := Color(1.0, 0.82, 0.32)

# ──── 狀態 ────
var _anim_t := 0.0
var _is_shown := false
var _won := false
var _score_a := 0
var _score_b := 0
var _own_slot := -1
var _own_team := 0
var _round_records: Array = []
var _players_data: Dictionary = {}
var _mvp_slot := -1

# ──── 按鈕 ────
var _continue_btn: Button = null

# ──── 信號 ────
signal continue_pressed


func _ready() -> void:
	set_process(true)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	_create_continue_button()


func _create_continue_button() -> void:
	_continue_btn = Button.new()
	_continue_btn.text = "繼續 → 返回大廳"
	_continue_btn.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_continue_btn.position = Vector2(-120, -60)
	_continue_btn.size = Vector2(240, 48)
	_continue_btn.add_theme_font_size_override("font_size", 18)
	_continue_btn.add_theme_color_override("font_color", Color.WHITE)
	var sb := StyleBoxFlat.new()
	sb.bg_color = COL_WIN if _won else COL_LOSE
	sb.corner_radius_top_left = 4
	sb.corner_radius_top_right = 4
	sb.corner_radius_bottom_left = 4
	sb.corner_radius_bottom_right = 4
	_continue_btn.add_theme_stylebox_override("normal", sb)
	var hsb := sb.duplicate()
	hsb.bg_color = (COL_WIN if _won else COL_LOSE).lightened(0.12)
	_continue_btn.add_theme_stylebox_override("hover", hsb)
	_continue_btn.pressed.connect(func(): continue_pressed.emit())
	add_child(_continue_btn)


func show_results(won: bool, score_a: int, score_b: int,
		round_records: Array, players_data: Dictionary,
		own_slot: int, own_team: int) -> void:
	_won = won
	_score_a = score_a
	_score_b = score_b
	_round_records = round_records
	_players_data = players_data
	_own_slot = own_slot
	_own_team = own_team
	_mvp_slot = _calc_mvp()
	_anim_t = 0.0
	_is_shown = true
	visible = true
	# 更新按鈕顏色
	if _continue_btn:
		var sb2 := _continue_btn.get_theme_stylebox("normal")
		if sb2 is StyleBoxFlat:
			sb2.bg_color = COL_WIN if _won else COL_LOSE
	Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)


func hide_results() -> void:
	_is_shown = false
	visible = false


func _calc_mvp() -> int:
	var best_slot := -1
	var best_score := -1.0
	for s in range(10):
		var p: Dictionary = _players_data.get(s, {})
		if p.is_empty():
			continue
		var kills := int(p.get("kills", 0))
		var deaths := int(p.get("deaths", 1))
		var kda := float(kills) / maxf(1.0, float(deaths))
		var score := float(kills) * 3.0 + kda * 2.0
		if score > best_score:
			best_score = score
			best_slot = s
	return best_slot


func _process(delta: float) -> void:
	if not _is_shown:
		return
	_anim_t += delta
	# ESC 也可以繼續
	if Input.is_key_pressed(KEY_ESCAPE) or Input.is_key_pressed(KEY_ENTER):
		if _anim_t > 1.0:
			continue_pressed.emit()
	queue_redraw()


func _draw() -> void:
	if not _is_shown:
		return
	var vp := get_viewport_rect().size
	var font := ThemeDB.fallback_font

	# 全幕背景
	var bg_alpha := clampf(_anim_t * 1.5, 0.0, 0.95)
	draw_rect(Rect2(Vector2.ZERO, vp), Color(COL_BG.r, COL_BG.g, COL_BG.b, bg_alpha))

	# 動畫進度 0..1
	var t := clampf(_anim_t / 0.6, 0.0, 1.0)

	_draw_title(vp, font, t)
	_draw_final_score(vp, font, t)
	_draw_scoreboard(vp, font, t)
	_draw_mvp(vp, font, t)
	_draw_round_history(vp, font, t)


func _draw_title(vp: Vector2, font: Font, t: float) -> void:
	var cx := vp.x * 0.5
	var cy := vp.y * 0.10
	var alpha := clampf(t * 2.0, 0.0, 1.0)
	var pop := 1.0 + (1.0 - clampf(t * 3.0, 0.0, 1.0)) * 0.15  # 出現瞬間微放大

	var title := "勝  利" if _won else "敗  北"
	var fs := int(56 * pop)
	var col := COL_WIN if _won else COL_LOSE
	col.a = alpha
	var tw := font.get_string_size(title, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
	# 背景條
	draw_rect(Rect2(cx - tw * 0.5 - 30, cy - fs * 0.8, tw + 60, fs * 1.4),
		Color(0.05, 0.05, 0.07, alpha * 0.6))
	draw_string(font, Vector2(cx - tw * 0.5, cy + fs * 0.3), title,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)


func _draw_final_score(vp: Vector2, font: Font, t: float) -> void:
	var cx := vp.x * 0.5
	var cy := vp.y * 0.22
	var alpha := clampf((t - 0.2) * 2.5, 0.0, 1.0)
	if alpha <= 0:
		return

	# 攻方分數
	var atk_text := str(_score_a)
	var atk_fs := 48
	var atk_w := font.get_string_size(atk_text, HORIZONTAL_ALIGNMENT_CENTER, -1, atk_fs).x
	draw_string(font, Vector2(cx - 80 - atk_w * 0.5, cy + atk_fs * 0.4), atk_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, atk_fs, Color(COL_ATTACK.r, COL_ATTACK.g, COL_ATTACK.b, alpha))

	# vs
	var vs_fs := 24
	var vs_w := font.get_string_size(":", HORIZONTAL_ALIGNMENT_CENTER, -1, vs_fs).x
	draw_string(font, Vector2(cx - vs_w * 0.5, cy + vs_fs * 0.8), ":",
		HORIZONTAL_ALIGNMENT_LEFT, -1, vs_fs, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha))

	# 守方分數
	var def_text := str(_score_b)
	var def_fs := 48
	var def_w := font.get_string_size(def_text, HORIZONTAL_ALIGNMENT_CENTER, -1, def_fs).x
	draw_string(font, Vector2(cx + 80 - def_w * 0.5, cy + def_fs * 0.4), def_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, def_fs, Color(COL_DEFEND.r, COL_DEFEND.g, COL_DEFEND.b, alpha))

	# 標籤
	var lbl_fs := 14
	var atk_lbl := "攻方"
	var atk_lw := font.get_string_size(atk_lbl, HORIZONTAL_ALIGNMENT_CENTER, -1, lbl_fs).x
	draw_string(font, Vector2(cx - 80 - atk_lw * 0.5, cy + 70), atk_lbl,
		HORIZONTAL_ALIGNMENT_LEFT, -1, lbl_fs, Color(COL_ATTACK.r, COL_ATTACK.g, COL_ATTACK.b, alpha * 0.6))
	var def_lbl := "守方"
	var def_lw := font.get_string_size(def_lbl, HORIZONTAL_ALIGNMENT_CENTER, -1, lbl_fs).x
	draw_string(font, Vector2(cx + 80 - def_lw * 0.5, cy + 70), def_lbl,
		HORIZONTAL_ALIGNMENT_LEFT, -1, lbl_fs, Color(COL_DEFEND.r, COL_DEFEND.g, COL_DEFEND.b, alpha * 0.6))


func _draw_scoreboard(vp: Vector2, font: Font, t: float) -> void:
	var alpha := clampf((t - 0.4) * 2.0, 0.0, 1.0)
	if alpha <= 0:
		return
	var x := vp.x * 0.10
	var y := vp.y * 0.34
	var w := vp.x * 0.55
	var row_h := 26.0

	# 標題行
	draw_rect(Rect2(x, y, w, row_h), Color(0.08, 0.10, 0.14, alpha * 0.8))
	var headers := ["玩家", "K", "D", "K/D", "戰鬥評分"]
	var col_xs := [x + 12, x + w * 0.45, x + w * 0.55, x + w * 0.65, x + w * 0.80]
	var hs := 13
	for i in range(headers.size()):
		draw_string(font, Vector2(col_xs[i], y + 18), headers[i],
			HORIZONTAL_ALIGNMENT_LEFT, -1, hs, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha))

	# 玩家行
	for i in range(10):
		var p: Dictionary = _players_data.get(i, {})
		if p.is_empty():
			continue
		var ry := y + row_h + i * (row_h - 2)
		var is_own := i == _own_slot
		var is_mvp := i == _mvp_slot
		var team := int(p.get("team", 0))
		var kills := int(p.get("kills", 0))
		var deaths := int(p.get("deaths", 0))
		var kda := float(kills) / maxf(1.0, float(deaths))
		var score := kills * 3 + int(kda * 100)

		# 行背景
		var row_col := Color(0.05, 0.06, 0.10, alpha * 0.3)
		if is_own:
			row_col = Color(0.10, 0.20, 0.30, alpha * 0.4)
		if is_mvp:
			row_col = Color(0.20, 0.16, 0.06, alpha * 0.5)
		draw_rect(Rect2(x, ry, w, row_h - 2), row_col)

		# 隊伍顏色條
		var tc := COL_ATTACK if team == 0 else COL_DEFEND
		draw_rect(Rect2(x, ry, 3, row_h - 2), Color(tc.r, tc.g, tc.b, alpha * 0.8))

		# 名字
		var name_str := "P%02d%s%s" % [i, " (你)" if is_own else "", " ★MVP" if is_mvp else ""]
		var name_col := Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha)
		if is_mvp:
			name_col = Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha)
		draw_string(font, Vector2(col_xs[0], ry + 18), name_str,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 12, name_col)

		# K/D/KD/Score
		var vals := [str(kills), str(deaths), "%.2f" % kda, str(score)]
		for j in range(4):
			var vcol := Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha * 0.8)
			if j == 0 and kills > 0:
				vcol = Color(COL_GREEN.r, COL_GREEN.g, COL_GREEN.b, alpha * 0.8)
			if j == 1 and deaths > 5:
				vcol = Color(COL_LOSE.r, COL_LOSE.g, COL_LOSE.b, alpha * 0.5)
			draw_string(font, Vector2(col_xs[j + 1], ry + 18), vals[j],
				HORIZONTAL_ALIGNMENT_LEFT, -1, 12, vcol)


func _draw_mvp(vp: Vector2, font: Font, t: float) -> void:
	if _mvp_slot < 0:
		return
	var alpha := clampf((t - 0.7) * 2.5, 0.0, 1.0)
	if alpha <= 0:
		return
	var x := vp.x * 0.68
	var y := vp.y * 0.34
	var w := vp.x * 0.22
	var h := 80.0

	# MVP 面板
	draw_rect(Rect2(x, y, w, h), Color(0.10, 0.08, 0.04, alpha * 0.7))
	draw_rect(Rect2(x, y, w, h), Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha * 0.3), false, 2.0)

	# MVP 標題
	draw_string(font, Vector2(x + 12, y + 22), "★ MVP",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha))

	var p: Dictionary = _players_data.get(_mvp_slot, {})
	var kills := int(p.get("kills", 0))
	var deaths := int(p.get("deaths", 0))
	var team := int(p.get("team", 0))
	var team_str := "攻方" if team == 0 else "守方"
	draw_string(font, Vector2(x + 12, y + 44), "P%02d  (%s)" % [_mvp_slot, team_str],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha))
	draw_string(font, Vector2(x + 12, y + 66), "%d K / %d D" % [kills, deaths],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(COL_GREEN.r, COL_GREEN.g, COL_GREEN.b, alpha * 0.7))


func _draw_round_history(vp: Vector2, font: Font, t: float) -> void:
	if _round_records.size() == 0:
		return
	var alpha := clampf((t - 0.9) * 2.0, 0.0, 1.0)
	if alpha <= 0:
		return
	var x := vp.x * 0.68
	var y := vp.y * 0.34 + 90
	var w := vp.x * 0.22
	var row_h := 18.0

	# 標題
	draw_string(font, Vector2(x, y + 14), "回合記錄",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha * 0.7))

	# 每回合結果
	var max_rows := mini(_round_records.size(), 15)
	for i in range(max_rows):
		var r: Dictionary = _round_records[i]
		var ry := y + 20 + i * row_h
		var winner := int(r.get("w", -1))
		var reason: String = r.get("r", "")
		var winner_col := COL_ATTACK if winner == 0 else COL_DEFEND
		winner_col.a = alpha * 0.7
		# 回合號
		draw_string(font, Vector2(x, ry + 14), "R%d" % int(r.get("n", i + 1)),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha * 0.5))
		# 勝方
		var w_text := "攻" if winner == 0 else "守"
		draw_string(font, Vector2(x + 35, ry + 14), w_text,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 11, winner_col)
		# 原因（截短）
		var reason_short := reason.left(16)
		draw_string(font, Vector2(x + 55, ry + 14), reason_short,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha * 0.4))
