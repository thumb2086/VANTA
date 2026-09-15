## DEPRECATED: No active references found. Kept for reference.
class_name RankedUI
extends Control

## Ranked lobby display: rank icon, RR bar, match history, queue button

const COL_BG := Color(0.04, 0.05, 0.08, 0.95)
const COL_PANEL := Color(0.07, 0.08, 0.12, 0.9)
const COL_TEXT := Color(0.94, 0.95, 0.97)
const COL_DIM := Color(0.42, 0.45, 0.52)
const COL_WIN := Color(0.18, 0.88, 0.35)
const COL_LOSE := Color(0.92, 0.25, 0.28)
const COL_GOLD := Color(1.0, 0.82, 0.32)
const COL_ACCENT := Color(0.18, 0.52, 0.92)
const COL_RANK_IRON := Color(0.55, 0.50, 0.45)
const COL_RANK_BRONZE := Color(0.72, 0.45, 0.20)
const COL_RANK_SILVER := Color(0.75, 0.78, 0.82)
const COL_RANK_GOLD := Color(0.92, 0.78, 0.25)
const COL_RANK_PLATINUM := Color(0.15, 0.72, 0.72)
const COL_RANK_DIAMOND := Color(0.35, 0.60, 0.92)
const COL_RANK_ASCENDANT := Color(0.15, 0.85, 0.45)
const COL_RANK_IMMORTAL := Color(0.85, 0.25, 0.35)
const COL_RANK_RADIANT := Color(1.0, 0.82, 0.32)

var _rank_data: Dictionary = {}
var _match_history: Array = []
var _queue_status: String = "idle"  # idle / searching / found
var _queue_timer: float = 0.0
var _queue_start_time: float = 0.0
var _pre_match_data: Dictionary = {}
var _show_pre_match: bool = false

signal find_match_pressed
signal cancel_queue_pressed
signal continue_to_match

var _find_btn: Button = null
var _cancel_btn: Button = null
var _continue_match_btn: Button = null


func _ready() -> void:
	set_process(true)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	_create_buttons()


func _create_buttons() -> void:
	_find_btn = Button.new()
	_find_btn.text = "FIND MATCH"
	_find_btn.set_anchors_preset(Control.PRESET_CENTER)
	_find_btn.position = Vector2(-100, 120)
	_find_btn.size = Vector2(200, 48)
	_find_btn.add_theme_font_size_override("font_size", 18)
	_find_btn.add_theme_color_override("font_color", Color.WHITE)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.18, 0.52, 0.92, 0.9)
	sb.corner_radius_top_left = 4
	sb.corner_radius_top_right = 4
	sb.corner_radius_bottom_left = 4
	sb.corner_radius_bottom_right = 4
	_find_btn.add_theme_stylebox_override("normal", sb)
	var hsb := sb.duplicate()
	hsb.bg_color = Color(0.22, 0.58, 0.98, 0.95)
	_find_btn.add_theme_stylebox_override("hover", hsb)
	_find_btn.pressed.connect(func(): find_match_pressed.emit())
	add_child(_find_btn)

	_cancel_btn = Button.new()
	_cancel_btn.text = "CANCEL"
	_cancel_btn.set_anchors_preset(Control.PRESET_CENTER)
	_cancel_btn.position = Vector2(-100, 120)
	_cancel_btn.size = Vector2(200, 48)
	_cancel_btn.add_theme_font_size_override("font_size", 18)
	_cancel_btn.add_theme_color_override("font_color", Color.WHITE)
	var csb := StyleBoxFlat.new()
	csb.bg_color = Color(0.92, 0.25, 0.28, 0.9)
	csb.corner_radius_top_left = 4
	csb.corner_radius_top_right = 4
	csb.corner_radius_bottom_left = 4
	csb.corner_radius_bottom_right = 4
	_cancel_btn.add_theme_stylebox_override("normal", csb)
	var chsb := csb.duplicate()
	chsb.bg_color = Color(0.98, 0.30, 0.35, 0.95)
	_cancel_btn.add_theme_stylebox_override("hover", chsb)
	_cancel_btn.pressed.connect(func(): cancel_queue_pressed.emit())
	_cancel_btn.visible = false
	add_child(_cancel_btn)

	_continue_match_btn = Button.new()
	_continue_match_btn.text = "READY"
	_continue_match_btn.set_anchors_preset(Control.PRESET_CENTER)
	_continue_match_btn.position = Vector2(-100, 260)
	_continue_match_btn.size = Vector2(200, 44)
	_continue_match_btn.add_theme_font_size_override("font_size", 16)
	_continue_match_btn.add_theme_color_override("font_color", Color.WHITE)
	var rsb := StyleBoxFlat.new()
	rsb.bg_color = Color(0.18, 0.88, 0.35, 0.9)
	rsb.corner_radius_top_left = 4
	rsb.corner_radius_top_right = 4
	rsb.corner_radius_bottom_left = 4
	rsb.corner_radius_bottom_right = 4
	_continue_match_btn.add_theme_stylebox_override("normal", rsb)
	var rhsb := rsb.duplicate()
	rhsb.bg_color = Color(0.22, 0.95, 0.40, 0.95)
	_continue_match_btn.add_theme_stylebox_override("hover", rhsb)
	_continue_match_btn.pressed.connect(func(): continue_to_match.emit())
	_continue_match_btn.visible = false
	add_child(_continue_match_btn)


func show_ranked(player_id: String) -> void:
	visible = true
	# Fetch from server via NetClient (placeholder — real impl uses RPC)
	_rank_data = {"rank": "Silver", "tier": 2, "rr": 45, "symbol": "\u2B23",
		"elo": 1550, "wins": 12, "losses": 8, "history": []}
	_queue_status = "idle"
	_queue_timer = 0.0
	_show_pre_match = false
	_find_btn.visible = true
	_cancel_btn.visible = false
	_continue_match_btn.visible = false
	queue_redraw()


func hide_ranked() -> void:
	visible = false


func update_rank_data(data: Dictionary) -> void:
	_rank_data = data
	queue_redraw()


func set_queue_status(status: String) -> void:
	_queue_status = status
	match status:
		"idle":
			_find_btn.visible = true
			_cancel_btn.visible = false
			_continue_match_btn.visible = false
		"searching":
			_find_btn.visible = false
			_cancel_btn.visible = true
			_continue_match_btn.visible = false
			_queue_start_time = Time.get_ticks_msec() / 1000.0
		"found":
			_find_btn.visible = false
			_cancel_btn.visible = false
			_continue_match_btn.visible = true
	queue_redraw()


func set_pre_match(data: Dictionary) -> void:
	_pre_match_data = data
	_show_pre_match = true
	queue_redraw()


func _process(delta: float) -> void:
	if _queue_status == "searching":
		_queue_timer = (Time.get_ticks_msec() / 1000.0) - _queue_start_time
		queue_redraw()


func _draw() -> void:
	if not visible:
		return
	var vp := get_viewport_rect().size
	var font := ThemeDB.fallback_font

	# Background
	draw_rect(Rect2(Vector2.ZERO, vp), Color(COL_BG.r, COL_BG.g, COL_BG.b, 0.95))

	# Title
	var title := "RANKED"
	var tfs := 28
	var ttw := font.get_string_size(title, HORIZONTAL_ALIGNMENT_CENTER, -1, tfs).x
	draw_string(font, Vector2(vp.x * 0.5 - ttw * 0.5, 50), title,
		HORIZONTAL_ALIGNMENT_LEFT, -1, tfs, Color(COL_ACCENT.r, COL_ACCENT.g, COL_ACCENT.b, 0.9))

	if _show_pre_match:
		_draw_pre_match(vp, font)
		return

	_draw_rank_panel(vp, font)
	_draw_match_history(vp, font)
	_draw_queue_status(vp, font)


func _draw_rank_panel(vp: Vector2, font: Font) -> void:
	var cx := vp.x * 0.5
	var cy := vp.y * 0.30

	# Rank icon (large symbol)
	var rank_name: String = _rank_data.get("rank", "Iron")
	var tier: int = _rank_data.get("tier", 1)
	var symbol: String = _rank_data.get("symbol", "\u2B21")
	var rr: int = _rank_data.get("rr", 0)
	var rank_col := _rank_color(rank_name)

	# Panel background
	var pw := 280.0
	var ph := 200.0
	draw_rect(Rect2(cx - pw * 0.5, cy - ph * 0.5, pw, ph), Color(COL_PANEL.r, COL_PANEL.g, COL_PANEL.b, 0.9))
	draw_rect(Rect2(cx - pw * 0.5, cy - ph * 0.5, pw, ph), Color(rank_col.r, rank_col.g, rank_col.b, 0.3), false, 2.0)

	# Symbol
	var sfs := 64
	var stw := font.get_string_size(symbol, HORIZONTAL_ALIGNMENT_CENTER, -1, sfs).x
	draw_string(font, Vector2(cx - stw * 0.5, cy - 30), symbol,
		HORIZONTAL_ALIGNMENT_LEFT, -1, sfs, Color(rank_col.r, rank_col.g, rank_col.b, 0.9))

	# Rank name
	var rname := "%s %d" % [rank_name, tier]
	var rnfs := 20
	var rnw := font.get_string_size(rname, HORIZONTAL_ALIGNMENT_CENTER, -1, rnfs).x
	draw_string(font, Vector2(cx - rnw * 0.5, cy + 20), rname,
		HORIZONTAL_ALIGNMENT_LEFT, -1, rnfs, Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, 0.9))

	# RR bar
	var bar_w := 220.0
	var bar_h := 12.0
	var bar_x := cx - bar_w * 0.5
	var bar_y := cy + 40
	draw_rect(Rect2(bar_x, bar_y, bar_w, bar_h), Color(0.1, 0.12, 0.16, 0.8))
	var fill := float(rr) / 100.0
	draw_rect(Rect2(bar_x, bar_y, bar_w * fill, bar_h), Color(rank_col.r, rank_col.g, rank_col.b, 0.8))
	var rr_text := "%d / 100 RR" % rr
	var rrfs := 11
	var rrtw := font.get_string_size(rr_text, HORIZONTAL_ALIGNMENT_CENTER, -1, rrfs).x
	draw_string(font, Vector2(cx - rrtw * 0.5, bar_y + bar_h - 2), rr_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, rrfs, Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, 0.8))

	# Stats
	var wins: int = _rank_data.get("wins", 0)
	var losses: int = _rank_data.get("losses", 0)
	var winrate := float(wins) / maxf(1.0, float(wins + losses)) * 100.0
	var stats_text := "W: %d  L: %d  WR: %.0f%%" % [wins, losses, winrate]
	var sfs2 := 13
	var stw2 := font.get_string_size(stats_text, HORIZONTAL_ALIGNMENT_CENTER, -1, sfs2).x
	draw_string(font, Vector2(cx - stw2 * 0.5, cy + ph * 0.5 - 15), stats_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, sfs2, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, 0.7))


func _draw_match_history(vp: Vector2, font: Font) -> void:
	var history: Array = _rank_data.get("history", [])
	if history.size() == 0:
		return
	var x := vp.x * 0.10
	var y := vp.y * 0.58
	var w := vp.x * 0.35

	draw_string(font, Vector2(x, y), "RECENT MATCHES",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, 0.6))

	var max_show := mini(history.size(), 10)
	for i in range(max_show):
		var h: Dictionary = history[history.size() - 1 - i]
		var ry := y + 20 + i * 22
		var rr_change: int = h.get("rr_change", 0)
		var won := rr_change > 0

		# Result dot
		var dot_col := COL_WIN if won else COL_LOSE
		draw_circle(Vector2(x + 8, ry + 6), 4, Color(dot_col.r, dot_col.g, dot_col.b, 0.8))

		# Rank
		var rname: String = h.get("rank", "?")
		var tier: int = h.get("tier", 1)
		draw_string(font, Vector2(x + 20, ry + 10), "%s %d" % [rname, tier],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, 0.7))

		# RR change
		var rr_text := "%+d RR" % rr_change
		var rr_col := COL_WIN if won else COL_LOSE
		draw_string(font, Vector2(x + w - 60, ry + 10), rr_text,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(rr_col.r, rr_col.g, rr_col.b, 0.8))


func _draw_queue_status(vp: Vector2, font: Font) -> void:
	if _queue_status != "searching":
		return
	var cx := vp.x * 0.5
	var cy := vp.y * 0.70

	# Searching animation (pulsing dots)
	var dots := ""
	var dot_count := int(fmod(_queue_timer * 2.0, 4.0))
	for i in range(dot_count):
		dots += "."
	var search_text := "SEARCHING%s" % dots
	var sfs := 16
	var stw := font.get_string_size(search_text, HORIZONTAL_ALIGNMENT_CENTER, -1, sfs).x
	var pulse := 0.6 + sin(_queue_timer * 3.0) * 0.3
	draw_string(font, Vector2(cx - stw * 0.5, cy), search_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, sfs, Color(COL_ACCENT.r, COL_ACCENT.g, COL_ACCENT.b, pulse))

	# Timer
	var minutes := int(_queue_timer) / 60
	var seconds := int(_queue_timer) % 60
	var time_text := "%d:%02d" % [minutes, seconds]
	var tfs := 14
	var ttw := font.get_string_size(time_text, HORIZONTAL_ALIGNMENT_CENTER, -1, tfs).x
	draw_string(font, Vector2(cx - ttw * 0.5, cy + 24), time_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, tfs, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, 0.6))

	# Estimated wait
	var est_text := "Estimated: ~30s"
	var efs := 11
	var etw := font.get_string_size(est_text, HORIZONTAL_ALIGNMENT_CENTER, -1, efs).x
	draw_string(font, Vector2(cx - etw * 0.5, cy + 42), est_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, efs, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, 0.4))


func _draw_pre_match(vp: Vector2, font: Font) -> void:
	var cx := vp.x * 0.5
	var cy := vp.y * 0.25

	# Title
	var title := "MATCH FOUND"
	var tfs := 24
	var ttw := font.get_string_size(title, HORIZONTAL_ALIGNMENT_CENTER, -1, tfs).x
	draw_string(font, Vector2(cx - ttw * 0.5, cy), title,
		HORIZONTAL_ALIGNMENT_LEFT, -1, tfs, Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, 0.9))

	# Team panels
	_draw_team_panel(vp, font, cx - 200, cy + 40, "TEAM 1", _pre_match_data.get("team1", []), true)
	_draw_team_panel(vp, font, cx + 40, cy + 40, "TEAM 2", _pre_match_data.get("team2", []), false)

	# Average ELO comparison
	var avg1: int = _pre_match_data.get("avg_elo1", 1500)
	var avg2: int = _pre_match_data.get("avg_elo2", 1500)
	var elo_text := "AVG ELO: %d vs %d" % [avg1, avg2]
	var efs := 14
	var etw := font.get_string_size(elo_text, HORIZONTAL_ALIGNMENT_CENTER, -1, efs).x
	draw_string(font, Vector2(cx - etw * 0.5, cy + 320), elo_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, efs, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, 0.6))

	# VS
	var vs_text := "VS"
	var vsfs := 32
	var vstw := font.get_string_size(vs_text, HORIZONTAL_ALIGNMENT_CENTER, -1, vsfs).x
	draw_string(font, Vector2(cx - vstw * 0.5, cy + 180), vs_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, vsfs, Color(COL_GOLD.r, COL_GOLD.g, COL_GOLD.b, 0.5))


func _draw_team_panel(vp: Vector2, font: Font, x: float, y: float, team_name: String, players: Array, is_team1: bool) -> void:
	var pw := 160.0
	var ph := 250.0
	var team_col := Color(0.92, 0.25, 0.22) if is_team1 else Color(0.18, 0.52, 0.92)

	draw_rect(Rect2(x, y, pw, ph), Color(COL_PANEL.r, COL_PANEL.g, COL_PANEL.b, 0.8))
	draw_rect(Rect2(x, y, pw, ph), Color(team_col.r, team_col.g, team_col.b, 0.3), false, 2.0)

	# Team name
	var tnfs := 14
	var tntw := font.get_string_size(team_name, HORIZONTAL_ALIGNMENT_CENTER, -1, tnfs).x
	draw_string(font, Vector2(x + pw * 0.5 - tntw * 0.5, y + 20), team_name,
		HORIZONTAL_ALIGNMENT_LEFT, -1, tnfs, Color(team_col.r, team_col.g, team_col.b, 0.8))

	# Players
	for i in range(mini(players.size(), 5)):
		var p: Dictionary = players[i]
		var py := y + 40 + i * 40
		var pname: String = p.get("name", "P%02d" % i)
		var prank: String = p.get("rank", "Iron")
		var ptier: int = p.get("tier", 1)
		var prr: int = p.get("rr", 0)

		draw_string(font, Vector2(x + 10, py + 14), pname,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(COL_TEXT.r, COL_TEXT.g, COL_TEXT.b, 0.8))
		draw_string(font, Vector2(x + 10, py + 28), "%s %d  (%d RR)" % [prank, ptier, prr],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(COL_DIM.r, COL_DIM.g, COL_DIM.b, 0.6))


func _rank_color(rank_name: String) -> Color:
	match rank_name:
		"Iron": return COL_RANK_IRON
		"Bronze": return COL_RANK_BRONZE
		"Silver": return COL_RANK_SILVER
		"Gold": return COL_RANK_GOLD
		"Platinum": return COL_RANK_PLATINUM
		"Diamond": return COL_RANK_DIAMOND
		"Ascendant": return COL_RANK_ASCENDANT
		"Immortal": return COL_RANK_IMMORTAL
		"Radiant": return COL_RANK_RADIANT
	return COL_DIM
