## DEPRECATED: Use match_results.gd instead. Kept for reference.
class_name MatchResultsV2
extends Control

## Valorant-quality post-match scoreboard
## Full-screen dark background, team-colored accents, KDA, economy, round timeline

const COL_BG := Color(0.02, 0.03, 0.05, 0.97)
const COL_ATK := Color(0.92, 0.25, 0.22)
const COL_DEF := Color(0.18, 0.52, 0.92)
const COL_WIN := Color(1.0, 0.82, 0.32)
const COL_LOSE := Color(0.92, 0.22, 0.28)
const COL_TEXT := Color(0.94, 0.95, 0.97)
const COL_DIM := Color(0.42, 0.45, 0.52)
const COL_GREEN := Color(0.18, 0.88, 0.35)
const COL_RED := Color(0.92, 0.25, 0.28)
const COL_GOLD := Color(1.0, 0.82, 0.32)
const COL_PANEL := Color(0.06, 0.07, 0.10, 0.9)
const COL_HEADER := Color(0.08, 0.10, 0.14, 0.95)
const COL_ROW_EVEN := Color(0.04, 0.05, 0.08, 0.6)
const COL_ROW_ODD := Color(0.06, 0.07, 0.10, 0.6)
const COL_ROW_OWN := Color(0.10, 0.22, 0.35, 0.7)

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
var _sort_mode := 0  # 0=score, 1=kda, 2=damage
var _sorted_players: Array = []

signal continue_pressed

var _continue_btn: Button = null


func _ready() -> void:
	set_process(true)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	_create_continue_button()


func _create_continue_button() -> void:
	_continue_btn = Button.new()
	_continue_btn.text = "CONTINUE"
	_continue_btn.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_continue_btn.position = Vector2(-100, -50)
	_continue_btn.size = Vector2(200, 44)
	_continue_btn.add_theme_font_size_override("font_size", 16)
	_continue_btn.add_theme_color_override("font_color", Color.WHITE)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.18, 0.52, 0.92, 0.9)
	sb.corner_radius_top_left = 3
	sb.corner_radius_top_right = 3
	sb.corner_radius_bottom_left = 3
	sb.corner_radius_bottom_right = 3
	_continue_btn.add_theme_stylebox_override("normal", sb)
	var hsb := sb.duplicate()
	hsb.bg_color = Color(0.22, 0.58, 0.98, 0.95)
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
	_sort_mode = 0
	_rebuild_sorted()
	_anim_t = 0.0
	_is_shown = true
	visible = true
	if _continue_btn:
		var sb2 := _continue_btn.get_theme_stylebox("normal")
		if sb2 is StyleBoxFlat:
			sb2.bg_color = Color(0.92, 0.25, 0.22, 0.9) if _won else Color(0.18, 0.52, 0.92, 0.9)
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
		var score := _player_score(p)
		if score > best_score:
			best_score = score
			best_slot = s
	return best_slot


func _player_score(p: Dictionary) -> float:
	var kills := int(p.get("kills", 0))
	var deaths := int(p.get("deaths", 1))
	var assists := int(p.get("assists", 0))
	var damage := int(p.get("damage", 0))
	return float(kills) * 3.0 + float(assists) * 1.0 + float(damage) * 0.01


func _player_kda(p: Dictionary) -> float:
	var kills := int(p.get("kills", 0))
	var deaths := int(p.get("deaths", 1))
	return float(kills + assists_val(p)) / maxf(1.0, float(deaths))


func assists_val(p: Dictionary) -> int:
	return int(p.get("assists", 0))


func _rebuild_sorted() -> void:
	_sorted_players.clear()
	for s in range(10):
		if _players_data.has(s) and not _players_data[s].is_empty():
			_sorted_players.append(s)
	match _sort_mode:
		0:
			_sorted_players.sort_custom(func(a, b): return _player_score(_players_data[a]) > _player_score(_players_data[b]))
		1:
			_sorted_players.sort_custom(func(a, b): return _player_kda(_players_data[a]) > _player_kda(_players_data[b]))
		2:
			_sorted_players.sort_custom(func(a, b): return int(_players_data[a].get("damage", 0)) > int(_players_data[b].get("damage", 0)))


func _process(delta: float) -> void:
	if not _is_shown:
		return
	_anim_t += delta
	if Input.is_key_pressed(KEY_ESCAPE) or Input.is_key_pressed(KEY_ENTER):
		if _anim_t > 1.5:
			continue_pressed.emit()
	if Input.is_action_just_pressed("ui_accept"):
		_sort_mode = (_sort_mode + 1) % 3
		_rebuild_sorted()
	queue_redraw()


func _draw() -> void:
	if not _is_shown:
		return
	var vp := get_viewport_rect().size
	var font := ThemeDB.fallback_font
	var bg_alpha := clampf(_anim_t * 2.0, 0.0, 0.97)
	draw_rect(Rect2(Vector2.ZERO, vp), Color(COL_BG.r, COL_BG.g, COL_BG.b, bg_alpha))
	var t := clampf(_anim_t / 0.5, 0.0, 1.0)

	_draw_accent_lines(vp, bg_alpha)
	_draw_header(vp, font, t)
	_draw_scoreboard(vp, font, t)
	_draw_mvp_panel(vp, font, t)
	_draw_round_timeline(vp, font, t)
	_draw_sort_hint(vp, font, t)


func _draw_accent_lines(vp: Vector2, alpha: float) -> void:
	var line_w := 3.0
	draw_rect(Rect2(0, 0, vp.x, line_w), Color(COL_ATK.r, COL_ATK.g, COL_ATK.b, alpha * 0.6))
	draw_rect(Rect2(0, vp.y - line_w, vp.x, line_w), Color(COL_DEF.r, COL_DEF.g, COL_DEF.b, alpha * 0.6))


func _draw_header(vp: Vector2, font: Font, t: float) -> void:
	var cx := vp.x * 0.5
	var cy := vp.y * 0.08
	var alpha := clampf(t * 2.5, 0.0, 1.0)
	var pop := 1.0 + (1.0 - clampf(t * 4.0, 0.0, 1.0)) * 0.12

	var title := "VICTORY" if _won else "DEFEAT"
	var fs := int(64 * pop)
	var col := COL_WIN if _won else COL_LOSE
	col.a = alpha
	var tw := font.get_string_size(title, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
	draw_rect(Rect2(cx - tw * 0.5 - 40, cy - fs * 0.7, tw + 80, fs * 1.3),
		Color(0.03, 0.03, 0.05, alpha * 0.7))
	draw_string(font, Vector2(cx - tw * 0.5, cy + fs * 0.25), title,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)

	# Score
	var score_text := "%d : %d" % [_score_a, _score_b]
	var sfs := 36
	var stw := font.get_string_size(score_text, HORIZONTAL_ALIGNMENT_CENTER, -1, sfs).x
	draw_string(font, Vector2(cx - stw * 0.5, cy + 70), score_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, sfs, Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha * 0.9))

	# Team labels
	var lfs := 14
	var atk_lw := font.get_string_size("ATTACK", HORIZONTAL_ALIGNMENT_CENTER, -1, lfs).x
	draw_string(font, Vector2(cx - 60 - atk_lw * 0.5, cy + 92), "ATTACK",
		HORIZONTAL_ALIGNMENT_LEFT, -1, lfs, Color(COL_ATK.r, COL_ATK.g, COL_ATK.b, alpha * 0.5))
	var def_lw := font.get_string_size("DEFEND", HORIZONTAL_ALIGNMENT_CENTER, -1, lfs).x
	draw_string(font, Vector2(cx + 60 - def_lw * 0.5, cy + 92), "DEFEND",
		HORIZONTAL_ALIGNMENT_LEFT, -1, lfs, Color(COL_DEF.r, COL_DEF.g, COL_DEF.b, alpha * 0.5))


func _draw_scoreboard(vp: Vector2, font: Font, t: float) -> void:
	var alpha := clampf((t - 0.3) * 2.5, 0.0, 1.0)
	if alpha <= 0:
		return
	var x := vp.x * 0.05
	var y := vp.y * 0.20
	var w := vp.x * 0.62
	var row_h := 30.0

	# Headers
	draw_rect(Rect2(x, y, w, row_h), Color(COL_HEADER.r, COL_HEADER.g, COL_HEADER.b, alpha * 0.9))
	var headers := ["", "PLAYER", "K", "D", "A", "KDA", "SCORE", "DMG", "FK", "FD", "PLT", "DEF", "ECON"]
	var col_xs := _scoreboard_col_x(x, w)
	var hs := 11
	for i in range(headers.size()):
		if i == 0:
			continue
		var hcol := Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha * 0.7)
		if _sort_mode == 0 and headers[i] == "SCORE":
			hcol = Color(COL_WIN.r, COL_WIN.g, COL_WIN.b, alpha)
		elif _sort_mode == 1 and headers[i] == "KDA":
			hcol = Color(COL_WIN.r, COL_WIN.g, COL_WIN.b, alpha)
		elif _sort_mode == 2 and headers[i] == "DMG":
			hcol = Color(COL_WIN.r, COL_WIN.g, COL_WIN.b, alpha)
		draw_string(font, Vector2(col_xs[i], y + 20), headers[i],
			HORIZONTAL_ALIGNMENT_LEFT, -1, hs, hcol)

	# Player rows
	for ri in range(_sorted_players.size()):
		var slot: int = _sorted_players[ri]
		var p: Dictionary = _players_data[slot]
		var ry := y + row_h + ri * row_h
		var is_own := slot == _own_slot
		var is_mvp := slot == _mvp_slot
		var team := int(p.get("team", 0))

		# Row background
		var row_col: Color
		if is_mvp:
			row_col = Color(0.15, 0.12, 0.04, alpha * 0.6)
		elif is_own:
			row_col = Color(COL_ROW_OWN.r, COL_ROW_OWN.g, COL_ROW_OWN.b, alpha)
		elif ri % 2 == 0:
			row_col = Color(COL_ROW_EVEN.r, COL_ROW_EVEN.g, COL_ROW_EVEN.b, alpha)
		else:
			row_col = Color(COL_ROW_ODD.r, COL_ROW_ODD.g, COL_ROW_ODD.b, alpha)
		draw_rect(Rect2(x, ry, w, row_h - 1), row_col)

		# Team color bar
		var tc := COL_ATK if team == 0 else COL_DEF
		draw_rect(Rect2(x, ry, 3, row_h - 1), Color(tc.r, tc.g, tc.b, alpha * 0.8))

		# Agent icon (colored circle)
		var icon_cx := col_xs[0] + 12
		var icon_cy := ry + row_h * 0.5
		var icon_r := 10.0
		var agent_color := _agent_color(int(p.get("agent_id", 0)))
		draw_circle(Vector2(icon_cx, icon_cy), icon_r, Color(agent_color.r, agent_color.g, agent_color.b, alpha * 0.9))
		draw_circle(Vector2(icon_cx, icon_cy), icon_r - 2, Color(agent_color.r * 0.4, agent_color.g * 0.4, agent_color.b * 0.4, alpha * 0.3))

		# Player name
		var name_str := "P%02d" % slot
		if is_own:
			name_str += " (YOU)"
		var name_col := Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha)
		if is_mvp:
			name_col = Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha)
		draw_string(font, Vector2(col_xs[1], ry + 20), name_str,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 12, name_col)

		# Stats
		var kills := int(p.get("kills", 0))
		var deaths := int(p.get("deaths", 0))
		var assists := int(p.get("assists", 0))
		var kda_val := float(kills + assists) / maxf(1.0, float(deaths))
		var score_val := _player_score(p)
		var damage := int(p.get("damage", 0))
		var fk := int(p.get("first_kills", 0))
		var fd := int(p.get("first_deaths", 0))
		var plants := int(p.get("plants", 0))
		var defuses := int(p.get("defuses", 0))
		var econ := int(p.get("economy", 0))

		var vals := [str(kills), str(deaths), str(assists), "%.1f" % kda_val,
			str(int(score_val)), str(damage), str(fk), str(fd), str(plants), str(defuses), str(econ)]
		for j in range(vals.size()):
			var vcol := Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha * 0.85)
			if j == 0 and kills > 0:
				vcol = Color(COL_GREEN.r, COL_GREEN.g, COL_GREEN.b, alpha * 0.9)
			elif j == 1 and deaths >= 8:
				vcol = Color(COL_RED.r, COL_RED.g, COL_RED.b, alpha * 0.6)
			elif j == 4:
				vcol = Color(COL_WIN.r, COL_WIN.g, COL_WIN.b, alpha * 0.9)
			draw_string(font, Vector2(col_xs[j + 2], ry + 20), vals[j],
				HORIZONTAL_ALIGNMENT_LEFT, -1, 11, vcol)

		# MVP crown
		if is_mvp:
			draw_string(font, Vector2(x + w - 20, ry + 20), "\u265B",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha))

		# Team divider
		if ri == 4 and _sorted_players.size() > 5:
			var div_y := ry + row_h
			draw_rect(Rect2(x, div_y - 1, w, 2), Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha * 0.3))


func _scoreboard_col_x(x: float, w: float) -> Array:
	return [
		x + 8,       # icon
		x + 32,      # name
		x + w * 0.22, # K
		x + w * 0.27, # D
		x + w * 0.32, # A
		x + w * 0.37, # KDA
		x + w * 0.44, # SCORE
		x + w * 0.53, # DMG
		x + w * 0.61, # FK
		x + w * 0.67, # FD
		x + w * 0.73, # PLT
		x + w * 0.80, # DEF
		x + w * 0.88, # ECON
	]


func _agent_color(agent_id: int) -> Color:
	match agent_id % 8:
		0: return Color(0.92, 0.25, 0.22)  # Duelist red
		1: return Color(0.18, 0.52, 0.92)  # Controller blue
		2: return Color(0.18, 0.85, 0.45)  # Initiator green
		3: return Color(0.85, 0.55, 0.15)  # Sentinel orange
		4: return Color(0.65, 0.35, 0.92)  # Flex purple
		5: return Color(0.15, 0.75, 0.85)  # Teal
		6: return Color(0.92, 0.65, 0.18)  # Yellow
		7: return Color(0.85, 0.35, 0.65)  # Pink
	return Color(0.5, 0.5, 0.5)


func _draw_mvp_panel(vp: Vector2, font: Font, t: float) -> void:
	if _mvp_slot < 0:
		return
	var alpha := clampf((t - 0.6) * 3.0, 0.0, 1.0)
	if alpha <= 0:
		return
	var x := vp.x * 0.70
	var y := vp.y * 0.20
	var w := vp.x * 0.26
	var h := 100.0

	draw_rect(Rect2(x, y, w, h), Color(0.12, 0.10, 0.04, alpha * 0.8))
	draw_rect(Rect2(x, y, w, h), Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha * 0.35), false, 2.0)

	draw_string(font, Vector2(x + 14, y + 24), "\u265B  MATCH MVP",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, alpha))

	var p: Dictionary = _players_data.get(_mvp_slot, {})
	var kills := int(p.get("kills", 0))
	var deaths := int(p.get("deaths", 0))
	var assists := int(p.get("assists", 0))
	var team := int(p.get("team", 0))
	var team_str := "ATK" if team == 0 else "DEF"
	var score_val := int(_player_score(p))

	draw_string(font, Vector2(x + 14, y + 46), "P%02d  [%s]" % [_mvp_slot, team_str],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, alpha * 0.8))
	draw_string(font, Vector2(x + 14, y + 64), "%d / %d / %d" % [kills, deaths, assists],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(COL_GREEN.r, COL_GREEN.g, COL_GREEN.b, alpha * 0.8))
	draw_string(font, Vector2(x + 14, y + 82), "SCORE: %d" % score_val,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(COL_WIN.r, COL_WIN.g, COL_WIN.b, alpha * 0.7))


func _draw_round_timeline(vp: Vector2, font: Font, t: float) -> void:
	if _round_records.size() == 0:
		return
	var alpha := clampf((t - 0.7) * 3.0, 0.0, 1.0)
	if alpha <= 0:
		return

	var x := vp.x * 0.05
	var y := vp.y * 0.82
	var w := vp.x * 0.90
	var h := 40.0
	var total := _round_records.size()
	var bar_w := w / maxf(float(total), 1.0)

	# Label
	draw_string(font, Vector2(x, y - 8), "ROUND TIMELINE",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha * 0.6))

	for i in range(total):
		var r: Dictionary = _round_records[i]
		var winner := int(r.get("w", -1))
		var bx := x + i * bar_w
		var won_round := (winner == _own_team)

		# Bar
		var bar_col: Color
		if won_round:
			bar_col = Color(COL_GREEN.r, COL_GREEN.g, COL_GREEN.b, alpha * 0.7)
		else:
			bar_col = Color(COL_RED.r, COL_RED.g, COL_RED.b, alpha * 0.7)
		draw_rect(Rect2(bx + 1, y, bar_w - 2, h), bar_col)

		# Round number
		var reason: String = r.get("r", "")
		var icon := ""
		if reason.contains("spike_detonated"):
			icon = "\u26A1"
		elif reason.contains("spike_defused"):
			icon = "\u2714"
		elif reason.contains("eliminated"):
			icon = "\u2694"

		if bar_w > 16:
			draw_string(font, Vector2(bx + bar_w * 0.3, y + h * 0.65), str(i + 1),
				HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(1, 1, 1, alpha * 0.8))
		if icon != "" and bar_w > 20:
			draw_string(font, Vector2(bx + bar_w * 0.3, y - 4), icon,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(1, 1, 1, alpha * 0.5))

	# Half divider
	if total > 12:
		var div_x := x + 12 * bar_w
		draw_rect(Rect2(div_x - 1, y - 4, 2, h + 8), Color(1, 1, 1, alpha * 0.3))


func _draw_sort_hint(vp: Vector2, font: Font, t: float) -> void:
	var alpha := clampf((t - 0.9) * 4.0, 0.0, 0.6)
	if alpha <= 0:
		return
	var sort_names := ["SORTED BY SCORE", "SORTED BY KDA", "SORTED BY DAMAGE"]
	draw_string(font, Vector2(vp.x * 0.05, vp.y * 0.97), "TAB: " + sort_names[_sort_mode],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, alpha))
