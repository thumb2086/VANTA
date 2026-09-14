class_name HUDV2
extends Control

## Valorant-quality HUD v2 — professional competitive FPS interface
##
## Layout (viewport-ratio based):
##   Top-center: Round timer (MM:SS) + round number + team scores (ATK | DEF)
##   Top-left: Minimap (200x200) with walls, teammates, agents
##   Top-right: Kill feed (scrolling recent kills)
##   Bottom-left: Agent portrait (circular) + health bar + shield bar
##   Bottom-center: Weapon name + ammo (mag/reserve) + fire mode
##   Bottom-right: Credits + ability icons (C/Q/E/X) with charge/cooldown
##   Center: Crosshair + hit marker + damage indicator + announcements
##   Round phase indicator: BUY / ACTION / END with countdown

# ──── Colors ────
const COL_PANEL := Color(0.02, 0.03, 0.06, 0.80)
const COL_ATTACK := Color(0.95, 0.28, 0.22)
const COL_DEFEND := Color(0.22, 0.55, 0.95)
const COL_HEALTH := Color(0.15, 0.85, 0.30)
const COL_SHIELD := Color(0.25, 0.65, 0.95)
const COL_MONEY := Color(1.0, 0.85, 0.20)
const COL_AMMO_LOW := Color(1.0, 0.35, 0.25)
const COL_AMMO_OK := Color(1.0, 1.0, 1.0)
const COL_SPIKE := Color(1.0, 0.35, 0.25)
const COL_TEXT := Color(1.0, 1.0, 1.0)
const COL_TEXT_DIM := Color(0.55, 0.58, 0.65)
const COL_CROSSHAIR := Color(0.22, 1.0, 0.08)
const COL_PHASE_BUY := Color(0.3, 0.8, 1.0)
const COL_PHASE_ACTION := Color(1.0, 0.8, 0.3)
const COL_PHASE_END := Color(0.7, 0.7, 0.7)
const COL_DARK_BG := Color(0.03, 0.04, 0.07, 0.92)
const COL_ACCENT := Color(0.0, 0.85, 0.75)

# ──── Data (written by main.gd) ────
var connected_text := ""
var ping_text := "0"
var tick_text := ""

var health := 100
var max_health := 100
var shield := 0
var max_shield := 50
var mag := 0
var mag_max := 30
var reserve_ammo := 90
var credits := 8000
var weapon_name := "Classic"
var weapon_slot := 1
var fire_mode := "Full"  # "Full" / "Burst" / "Semi"

var score_attack := 0
var score_defend := 0
var round_number := 1
var phase_text := ""  # "BUY" / "ACTION" / "END"
var round_timer := -1

var spike_text := ""
var _spike_timer := 0.0

# ──── Minimap ────
var map_data: Dictionary = {}
var own_slot := -1
var players_dict: Dictionary = {}

# ──── Scope ────
var is_ads := false
var is_scoped := false

# ──── Abilities ────
var ability_charges := [1, 1, 1, 0]  # C/Q/E/X current charges
var ability_max_charges := [1, 1, 1, 1]
var ability_cooldowns := [0.0, 0.0, 0.0, 0.0]
var ability_max_cds := [10.0, 10.0, 0.0, 0.0]
var ability_costs := [200, 200, 0, 0]  # C/Q/E/X price

# ──── Crosshair ────
var ch_color := Color(0.22, 1.0, 0.08)
var ch_size := 4.0
var ch_gap := 4.0
var ch_thickness := 2.0
var ch_outline := false
var ch_dot := true
var ch_style := 0  # 0=cross, 1=circle, 2=dot

# ──── Spread ────
var spread_angle := 0.0
var _spread_decay := 0.0

# ──── Kill feed ────
var feed: Array[Dictionary] = []

# ──── Announcements ────
var announce_text := ""
var announce_color := Color.WHITE
var _announce_timer := 0.0

# ──── Kill flash ────
var _killflash_timer := 0.0
var _killflash_color := Color(1.0, 0.2, 0.2)

# ──── Kill banner ────
var _banner_text := ""
var _banner_hs := false
var _banner_weapon := ""
var _banner_timer := 0.0

# ──── Hit marker ────
var _hitmarker_timer := 0.0
var _hitmarker_headshot := false
var _hit_marker_crosshair := false

# ──── Damage ────
var _damage_numbers: Array = []
var _damage_direction_timer := 0.0
var _damage_direction_angle := 0.0

# ──── Death screen ────
var _death_timer := 0.0
var _respawn_timer := 0.0

# ──── Match point / round win ────
var _round_result_text := ""
var _round_result_timer := 0.0
var _round_result_color := Color.WHITE


func _ready() -> void:
	set_process(true)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


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
	if _death_timer > 0.0:
		_death_timer = maxf(0.0, _death_timer - delta)
	if _round_result_timer > 0.0:
		_round_result_timer = maxf(0.0, _round_result_timer - delta)
	for i in range(_damage_numbers.size() - 1, -1, -1):
		_damage_numbers[i]["t"] = float(_damage_numbers[i]["t"]) + delta
		if float(_damage_numbers[i]["t"]) > 1.0:
			_damage_numbers.remove_at(i)
	if _hit_marker_crosshair and _hitmarker_timer <= 0.0:
		_hit_marker_crosshair = false
	if _spike_timer > 0.0:
		_spike_timer = maxf(0.0, _spike_timer - delta)
	if spread_angle > 0.0:
		spread_angle = maxf(0.0, spread_angle - delta * 15.0)
	for i in range(feed.size() - 1, -1, -1):
		feed[i]["t"] = float(feed[i]["t"]) + delta
		if float(feed[i]["t"]) > 6.0:
			feed.remove_at(i)
	# Cooldown decay
	for i in range(4):
		if ability_cooldowns[i] > 0.0:
			ability_cooldowns[i] = maxf(0.0, ability_cooldowns[i] - delta)
	queue_redraw()


# ──── External API ────
func announce(text: String, color := Color(1.0, 0.8, 0.2)) -> void:
	announce_text = text
	announce_color = color
	_announce_timer = 3.0


func push_feed(text: String) -> void:
	feed.push_front({"text": text, "t": 0.0})
	if feed.size() > 6:
		feed.resize(6)


func killflash(headshot := false) -> void:
	_killflash_timer = 0.6
	_killflash_color = Color(1.0, 0.3, 0.3) if headshot else Color(1.0, 0.9, 0.4)


func show_kill_banner(victim: String, headshot := false, weapon := "") -> void:
	_banner_text = victim
	_banner_hs = headshot
	_banner_weapon = weapon
	_banner_timer = 2.5


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
	_hitmarker_timer = 0.15


func set_spike(text: String) -> void:
	spike_text = text
	if text != "":
		_spike_timer = 99.0


func show_death(respawn_seconds: float) -> void:
	_death_timer = 99.0
	_respawn_timer = respawn_seconds


func show_round_result(text: String, color := Color.WHITE) -> void:
	_round_result_text = text
	_round_result_color = color
	_round_result_timer = 3.0


# ═══════════════════════════════════════════════
#  DRAW
# ═══════════════════════════════════════════════
func _draw() -> void:
	var vp := get_viewport_rect().size
	var font := ThemeDB.fallback_font
	_draw_crosshair(vp, font)
	_draw_top_bar(vp, font)
	_draw_minimap(vp, font)
	_draw_kill_feed(vp, font)
	_draw_health_panel(vp, font)
	_draw_weapon_panel(vp, font)
	_draw_ability_panel(vp, font)
	_draw_agent_dots(vp, font)
	_draw_hitmarker(vp, font)
	_draw_damage_numbers(vp, font)
	_draw_damage_direction(vp)
	_draw_announce(vp, font)
	_draw_kill_banner(vp, font)
	_draw_spike_status(vp, font)
	_draw_net_stats(vp, font)
	_draw_scope_overlay(vp, font)
	_draw_death_screen(vp, font)
	_draw_round_result(vp, font)


# ──── Crosshair + spread ────
func _draw_crosshair(vp: Vector2, font: Font) -> void:
	var cx := vp.x * 0.5
	var cy := vp.y * 0.5
	var spread_px := spread_angle * 8.0
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
	if spread_px > 2.0:
		var dd := gap + len + 4.0
		var ds := 1.5 + spread_ratio * 2.0
		draw_circle(Vector2(cx - dd, cy), ds, Color(xh_color.r, xh_color.g, xh_color.b, 0.5))
		draw_circle(Vector2(cx + dd, cy), ds, Color(xh_color.r, xh_color.g, xh_color.b, 0.5))
		draw_circle(Vector2(cx, cy - dd), ds, Color(xh_color.r, xh_color.g, xh_color.b, 0.5))
		draw_circle(Vector2(cx, cy + dd), ds, Color(xh_color.r, xh_color.g, xh_color.b, 0.5))
	if _killflash_timer > 0.0:
		var u := _killflash_timer / 0.6
		_killflash_color.a = u
		var s := 28.0 * (1.0 + (1.0 - u) * 0.3)
		draw_line(Vector2(cx - s, cy - s), Vector2(cx + s, cy + s), _killflash_color, 5.0)
		draw_line(Vector2(cx + s, cy - s), Vector2(cx - s, cy + s), _killflash_color, 5.0)


# ──── Top bar: Round timer + scores ────
func _draw_top_bar(vp: Vector2, font: Font) -> void:
	var bar_w := 320.0
	var bar_h := 44.0
	var x := (vp.x - bar_w) * 0.5
	var y := 6.0
	# Background
	draw_rect(Rect2(x, y, bar_w, bar_h), COL_PANEL)
	# Attack score (left, red)
	draw_rect(Rect2(x, y, bar_w * 0.35, bar_h), Color(COL_ATTACK.r, COL_ATTACK.g, COL_ATTACK.b, 0.2))
	var atk_label := str(score_attack)
	var atk_fs := 28
	var atk_w := font.get_string_size(atk_label, HORIZONTAL_ALIGNMENT_LEFT, -1, atk_fs).x
	draw_string(font, Vector2(x + bar_w * 0.35 * 0.5 - atk_w * 0.5, y + 33), atk_label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, atk_fs, COL_ATTACK)
	# Round timer (center)
	var timer_str := "00:%02d" % round_timer if round_timer >= 0 else "--:--"
	if round_timer >= 60:
		timer_str = "%02d:%02d" % [int(round_timer) / 60, int(round_timer) % 60]
	var timer_fs := 20
	if round_timer >= 0 and round_timer <= 10:
		timer_fs = 28
		timer_str = str(int(round_timer))
	var timer_col := COL_TEXT_DIM
	if round_timer >= 0 and round_timer <= 10:
		timer_col = COL_AMMO_LOW
	var timer_w := font.get_string_size(timer_str, HORIZONTAL_ALIGNMENT_LEFT, -1, timer_fs).x
	draw_string(font, Vector2(x + bar_w * 0.5 - timer_w * 0.5, y + 32), timer_str,
		HORIZONTAL_ALIGNMENT_LEFT, -1, timer_fs, timer_col)
	# Round number
	var rn_label := "R%d" % round_number
	var rn_fs := 13
	var rn_w := font.get_string_size(rn_label, HORIZONTAL_ALIGNMENT_LEFT, -1, rn_fs).x
	draw_string(font, Vector2(x + bar_w * 0.5 - rn_w * 0.5, y + 14), rn_label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, rn_fs, COL_TEXT_DIM)
	# Defend score (right, blue)
	draw_rect(Rect2(x + bar_w * 0.65, y, bar_w * 0.35, bar_h), Color(COL_DEFEND.r, COL_DEFEND.g, COL_DEFEND.b, 0.2))
	var def_label := str(score_defend)
	var def_w := font.get_string_size(def_label, HORIZONTAL_ALIGNMENT_LEFT, -1, atk_fs).x
	draw_string(font, Vector2(x + bar_w * 0.65 + bar_w * 0.35 * 0.5 - def_w * 0.5, y + 33), def_label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, atk_fs, COL_DEFEND)
	# Phase indicator below bar
	if phase_text != "" and round_timer > 10:
		var phase_label := phase_text
		var phase_col := COL_TEXT_DIM
		match phase_text:
			"BUY": phase_col = COL_PHASE_BUY
			"ACTION": phase_col = COL_PHASE_ACTION
			"END": phase_col = COL_PHASE_END
		var phase_fs := 14
		var phase_w := font.get_string_size(phase_label, HORIZONTAL_ALIGNMENT_LEFT, -1, phase_fs).x
		draw_string(font, Vector2(x + bar_w * 0.5 - phase_w * 0.5, y + bar_h + 16), phase_label,
			HORIZONTAL_ALIGNMENT_LEFT, -1, phase_fs, phase_col)


# ──── Minimap (top-left, 200x200) ────
func _draw_minimap(vp: Vector2, font: Font) -> void:
	var map_w := 200.0
	var map_h := 200.0
	var mx := 10.0
	var my := 10.0
	draw_rect(Rect2(mx, my, map_w, map_h), Color(0.04, 0.05, 0.08, 0.85))
	draw_rect(Rect2(mx, my, map_w, map_h), Color(0.3, 0.3, 0.35, 0.6), false, 1.0)
	if map_data.is_empty():
		return
	var bounds: Dictionary = map_data.get("bounds_min", {})
	var bmax: Dictionary = map_data.get("bounds_max", {})
	if bounds.is_empty() or bmax.is_empty():
		return
	var mn := Vector2(bounds.get("x", -20.0), bounds.get("z", -20.0))
	var mx2 := Vector2(bmax.get("x", 20.0), bmax.get("z", 20.0))
	var range_xy := mx2 - mn
	if range_xy.x <= 0 or range_xy.y <= 0:
		return
	# Walls
	var walls: Array = map_data.get("walls", [])
	for w in walls:
		var wmn: Dictionary = w.get("mn", {})
		var wmx: Dictionary = w.get("mx", {})
		var p1 := _map_to_mini(Vector2(wmn.get("x", 0), wmn.get("z", 0)), mn, range_xy, mx, my, map_w, map_h)
		var p2 := _map_to_mini(Vector2(wmx.get("x", 0), wmx.get("z", 0)), mn, range_xy, mx, my, map_w, map_h)
		draw_line(p1, p2, Color(0.45, 0.45, 0.5, 0.7), 1.0)
	# Sites
	var sites: Array = map_data.get("sites", [])
	for s in sites:
		var sc: Dictionary = s.get("center", {})
		var pos := _map_to_mini(Vector2(sc.get("x", 0), sc.get("z", 0)), mn, range_xy, mx, my, map_w, map_h)
		draw_circle(pos, 5.0, Color(COL_SPIKE.r, COL_SPIKE.g, COL_SPIKE.b, 0.75))
		draw_string(font, Vector2(pos.x - 5, pos.y - 9), s.get("name", "?"),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_SPIKE)
	# Players
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
			draw_circle(pos, 6.0, Color.WHITE)
			var dir := Vector2(vel.x, vel.z).normalized()
			if dir.length() > 0.1:
				draw_line(pos, pos + dir * 10.0, Color.WHITE, 2.0)
		else:
			draw_circle(pos, 3.5, col)
			var dir := Vector2(vel.x, vel.z).normalized()
			if dir.length() > 0.1:
				draw_line(pos, pos + dir * 7.0, col, 1.5)


func _map_to_mini(world_pos: Vector2, mn: Vector2, range_xy: Vector2,
		map_x: float, map_y: float, mw: float, mh: float) -> Vector2:
	var nx := (world_pos.x - mn.x) / range_xy.x
	var ny := (world_pos.y - mn.y) / range_xy.y
	return Vector2(map_x + nx * mw, map_y + ny * mh)


# ──── Kill feed (top-right) ────
func _draw_kill_feed(vp: Vector2, font: Font) -> void:
	var fx := vp.x - 16.0
	var fy := 18.0
	for f in feed:
		var a := clampf(6.0 - float(f["t"]), 0.0, 1.0)
		if a <= 0.0:
			continue
		var text: String = f["text"]
		var size := 15
		var text_w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
		var line_h := size + 10.0
		draw_rect(Rect2(fx - text_w - 14, fy - size, text_w + 18, line_h),
			Color(0, 0, 0, 0.55 * a))
		var c := COL_TEXT
		c.a = a
		draw_string(font, Vector2(fx - text_w - 5, fy), text,
			HORIZONTAL_ALIGNMENT_LEFT, -1, size, c)
		fy += line_h


# ──── Health panel (bottom-left) ────
func _draw_health_panel(vp: Vector2, font: Font) -> void:
	var panel_w := 220.0
	var panel_h := 80.0
	var x := 12.0
	var y := vp.y - panel_h - 12.0
	# Background panel
	draw_rect(Rect2(x, y, panel_w, panel_h), COL_PANEL)
	# Agent portrait circle
	var portrait_r := 24.0
	var portrait_cx := x + 30.0
	var portrait_cy := y + panel_h * 0.5
	draw_circle(Vector2(portrait_cx, portrait_cy), portrait_r, Color(0.12, 0.14, 0.18))
	draw_circle(Vector2(portrait_cx, portrait_cy), portrait_r, COL_ATTACK if own_slot < 5 else COL_DEFEND, false, 2.0)
	var agent_initial := "A"
	draw_string(font, Vector2(portrait_cx - 5, portrait_cy + 7), agent_initial,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, COL_TEXT)
	# Health number
	var hp_color := COL_HEALTH if health > 30 else COL_AMMO_LOW
	draw_string(font, Vector2(x + 65, y + 24), str(health),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 28, hp_color)
	# Health bar
	var bar_x := x + 65.0
	var bar_y := y + 36.0
	var bar_w := 140.0
	var bar_h := 8.0
	draw_rect(Rect2(bar_x, bar_y, bar_w, bar_h), Color(0.12, 0.13, 0.17))
	var hp_frac := clampf(float(health) / float(max_health), 0.0, 1.0)
	draw_rect(Rect2(bar_x, bar_y, bar_w * hp_frac, bar_h), hp_color)
	# Shield bar (above health bar)
	if max_shield > 0:
		var sh_y := bar_y - 12.0
		var sh_frac := clampf(float(shield) / float(max_shield), 0.0, 1.0)
		var seg := 5.0
		for s in range(int(seg)):
			var seg_x := bar_x + bar_w * (float(s) / seg)
			var seg_w := bar_w / seg - 1.0
			var fill := clampf((sh_frac * seg) - float(s), 0.0, 1.0)
			draw_rect(Rect2(seg_x, sh_y, seg_w, 6.0), Color(0.12, 0.13, 0.17))
			if fill > 0.0:
				draw_rect(Rect2(seg_x, sh_y, seg_w * fill, 6.0), COL_SHIELD)
		draw_string(font, Vector2(bar_x, sh_y - 2), str(shield),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 11, COL_SHIELD)
	# Death overlay
	if health <= 0:
		draw_string(font, Vector2(x + 65, y + 24), "DEAD",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 28, COL_AMMO_LOW)


# ──── Weapon panel (bottom-center) ────
func _draw_weapon_panel(vp: Vector2, font: Font) -> void:
	var panel_w := 260.0
	var panel_h := 60.0
	var x := (vp.x - panel_w) * 0.5
	var y := vp.y - panel_h - 12.0
	draw_rect(Rect2(x, y, panel_w, panel_h), COL_PANEL)
	# Weapon name
	draw_string(font, Vector2(x + 12, y + 20), weapon_name,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 15, COL_TEXT_DIM)
	# Fire mode badge
	var fm_w := font.get_string_size(fire_mode, HORIZONTAL_ALIGNMENT_LEFT, -1, 10).x
	draw_rect(Rect2(x + 12 + fm_w + 8, y + 8, fm_w + 12, 16), Color(0.15, 0.17, 0.22))
	draw_string(font, Vector2(x + 14 + fm_w + 8, y + 20), fire_mode,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 10, COL_ACCENT)
	# Ammo (big)
	var ammo_color := COL_AMMO_LOW if mag <= 5 and mag_max > 0 else COL_AMMO_OK
	var ammo_str := "%d" % mag
	draw_string(font, Vector2(x + 12, y + 50), ammo_str,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 32, ammo_color)
	# Separator
	draw_string(font, Vector2(x + 72, y + 46), "/",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_TEXT_DIM)
	# Reserve (smaller)
	draw_string(font, Vector2(x + 88, y + 46), str(reserve_ammo),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_TEXT_DIM)


# ──── Ability panel (bottom-right) ────
func _draw_ability_panel(vp: Vector2, font: Font) -> void:
	var slot_w := 52.0
	var slot_h := 52.0
	var gap := 6.0
	var total_w := slot_w * 4 + gap * 3
	var x := vp.x - total_w - 12.0
	var y := vp.y - slot_h - 12.0
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
		var charges: int = ability_charges[i]
		var col := key_colors[i]
		if on_cd:
			col = Color(0.25, 0.25, 0.3)
		# Background
		draw_rect(Rect2(sx, y, slot_w, slot_h), Color(0.06, 0.07, 0.11, 0.9))
		draw_rect(Rect2(sx, y, slot_w, slot_h), col if not on_cd else Color(0.2, 0.2, 0.25, 0.6), false, 2.0)
		# Cooldown ring
		if on_cd and ability_max_cds[i] > 0:
			var frac: float = 1.0 - (cd / float(ability_max_cds[i]))
			var radius := slot_w * 0.42
			var pts := PackedVector2Array()
			for j in range(33):
				var ang := deg_to_rad(-90.0 + frac * 360.0 * j / 32.0)
				pts.append(Vector2(cx2 + cos(ang) * radius, cy2 + sin(ang) * radius))
			draw_polyline(pts, Color(col.r, col.g, col.b, 0.35), 3.0)
		# Key label
		var key_fs := 18
		var key_w := font.get_string_size(keys[i], HORIZONTAL_ALIGNMENT_LEFT, -1, key_fs).x
		draw_string(font, Vector2(cx2 - key_w * 0.5, cy2 + 6), keys[i],
			HORIZONTAL_ALIGNMENT_LEFT, -1, key_fs, col)
		# Charge dots (bottom of slot)
		for c in range(ability_max_charges[i]):
			var dot_x := sx + 10.0 + c * 10.0
			var dot_y := y + slot_h - 8.0
			var dot_col := col if c < charges else Color(0.2, 0.2, 0.25)
			draw_circle(Vector2(dot_x, dot_y), 3.0, dot_col)
		# Cooldown text
		if on_cd:
			var cd_str := "%.0f" % cd
			var cd_w := font.get_string_size(cd_str, HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x
			draw_string(font, Vector2(cx2 - cd_w * 0.5, y + slot_h - 6), cd_str,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 11, COL_AMMO_LOW)
	# Credits (below abilities)
	var cred_str := "$%d" % credits
	var cred_fs := 16
	draw_string(font, Vector2(x, y - 10), cred_str,
		HORIZONTAL_ALIGNMENT_LEFT, -1, cred_fs, COL_MONEY)


# ──── Agent dots (top bar sides) ────
func _draw_agent_dots(vp: Vector2, font: Font) -> void:
	var dot_r := 7.0
	var y := 56.0
	for i in range(5):
		var x_pos := 10.0 + i * (dot_r * 2 + 3)
		var alive := true
		var snap: Dictionary = players_dict.get(i, {})
		if not snap.is_empty():
			alive = snap.get("alive", true)
		if alive:
			draw_circle(Vector2(x_pos + dot_r, y + dot_r), dot_r, COL_ATTACK)
		else:
			draw_circle(Vector2(x_pos + dot_r, y + dot_r), dot_r, Color(0.3, 0.3, 0.35))
			draw_line(Vector2(x_pos + dot_r - 3, y + dot_r - 3), Vector2(x_pos + dot_r + 3, y + dot_r + 3), Color(0.8, 0.2, 0.2), 1.5)
			draw_line(Vector2(x_pos + dot_r + 3, y + dot_r - 3), Vector2(x_pos + dot_r - 3, y + dot_r + 3), Color(0.8, 0.2, 0.2), 1.5)
	var vp_w := get_viewport_rect().size.x
	for i in range(5):
		var x_pos := vp_w - 10.0 - (5 - i) * (dot_r * 2 + 3)
		var alive := true
		var snap: Dictionary = players_dict.get(i + 5, {})
		if not snap.is_empty():
			alive = snap.get("alive", true)
		if alive:
			draw_circle(Vector2(x_pos, y + dot_r), dot_r, COL_DEFEND)
		else:
			draw_circle(Vector2(x_pos, y + dot_r), dot_r, Color(0.3, 0.3, 0.35))
			draw_line(Vector2(x_pos - 3, y + dot_r - 3), Vector2(x_pos + 3, y + dot_r + 3), Color(0.8, 0.2, 0.2), 1.5)
			draw_line(Vector2(x_pos + 3, y + dot_r - 3), Vector2(x_pos - 3, y + dot_r + 3), Color(0.8, 0.2, 0.2), 1.5)


# ──── Hit marker ────
func _draw_hitmarker(vp: Vector2, font: Font) -> void:
	if _hitmarker_timer <= 0.0:
		return
	var cx := vp.x * 0.5
	var cy := vp.y * 0.5
	var alpha := _hitmarker_timer / 0.25
	var len := 5.0
	var gap := 6.0
	var col := Color(1.0, 1.0, 1.0, alpha)
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
	var radius := 65.0
	var arc_color := Color(1.0, 0.25, 0.2, alpha)
	var arc_start := _damage_direction_angle - deg_to_rad(22.0)
	var arc_end := _damage_direction_angle + deg_to_rad(22.0)
	draw_arc(Vector2(cx, cy), radius, arc_start, arc_end, 20, arc_color, 4.0)
	var tip_x := cx + cos(_damage_direction_angle) * radius
	var tip_y := cy + sin(_damage_direction_angle) * radius
	var perp_x := cos(_damage_direction_angle + PI * 0.5) * 6.0
	var perp_y := sin(_damage_direction_angle + PI * 0.5) * 6.0
	var back_dist := 12.0
	var back_x := cx + cos(_damage_direction_angle) * (radius - back_dist)
	var back_y := cy + sin(_damage_direction_angle) * (radius - back_dist)
	var tri := PackedVector2Array([
		Vector2(tip_x + perp_x, tip_y + perp_y),
		Vector2(tip_x - perp_x, tip_y - perp_y),
		Vector2(back_x, back_y),
	])
	draw_colored_polygon(tri, arc_color)


# ──── Announcements (center screen) ────
func _draw_announce(vp: Vector2, font: Font) -> void:
	if _announce_timer <= 0.0 or announce_text == "":
		return
	var cx := vp.x * 0.5
	var cy := vp.y * 0.35
	var a := clampf(_announce_timer, 0.0, 1.0)
	var bg_alpha := a * 0.35
	draw_rect(Rect2(0, 0, vp.x, vp.y), Color(0, 0, 0, bg_alpha))
	var fs := 56
	var text_w := font.get_string_size(announce_text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var strip_h := fs + 30
	draw_rect(Rect2(0, cy - fs * 0.6, vp.x, strip_h),
		Color(announce_color.r, announce_color.g, announce_color.b, a * 0.15))
	draw_rect(Rect2(0, cy - fs * 0.6, vp.x, strip_h),
		Color(announce_color.r, announce_color.g, announce_color.b, a * 0.4), false, 2.0)
	announce_color.a = a
	draw_string(font, Vector2(cx - text_w * 0.5, cy + fs * 0.3), announce_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, announce_color)


# ──── Kill banner ────
func _draw_kill_banner(vp: Vector2, font: Font) -> void:
	if _banner_timer <= 0.0 or _banner_text == "":
		return
	var u := _banner_timer / 2.5
	var alpha: float = clampf((1.0 - u) * 8.0, 0.0, 1.0) * clampf(u * 4.0, 0.0, 1.0)
	var cy := vp.y * 0.78
	var pop := 1.0 + (1.0 - clampf((1.0 - u) * 6.0, 0.0, 1.0)) * 0.12
	var fs := int(28.0 * (vp.y / 720.0) * pop)
	var main := "ELIMINATED  " + _banner_text
	var col := Color(1.0, 0.32, 0.28, alpha)
	var w := font.get_string_size(main, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var bx := vp.x * 0.5 - w * 0.5
	draw_rect(Rect2(bx - 20, cy - fs - 10, w + 40, fs + 22),
		Color(0.04, 0.04, 0.06, alpha * 0.6))
	draw_string(font, Vector2(bx, cy), main, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
	if _banner_weapon != "":
		var ws := int(fs * 0.42)
		var wt := _banner_weapon
		var ww := font.get_string_size(wt, HORIZONTAL_ALIGNMENT_LEFT, -1, ws).x
		draw_string(font, Vector2(vp.x * 0.5 - ww * 0.5, cy + ws * 1.4), wt,
			HORIZONTAL_ALIGNMENT_LEFT, -1, ws, Color(0.85, 0.85, 0.9, alpha * 0.8))
	if _banner_hs:
		var hs_fs := int(fs * 0.5)
		var ht := "HEADSHOT"
		var hw := font.get_string_size(ht, HORIZONTAL_ALIGNMENT_LEFT, -1, hs_fs).x
		draw_string(font, Vector2(bx + w + 12, cy), ht,
			HORIZONTAL_ALIGNMENT_LEFT, -1, hs_fs, Color(1.0, 0.8, 0.2, alpha))


# ──── Spike status ────
func _draw_spike_status(vp: Vector2, font: Font) -> void:
	if spike_text == "" or _spike_timer <= 0.0:
		return
	var cx := vp.x * 0.5
	var cy := 95.0
	var pulse := 1.0 + sinf(_spike_timer * 8.0) * 0.15
	var radius := 18.0 * pulse
	var alpha := clampf(_spike_timer / 1.0, 0.3, 1.0)
	draw_arc(Vector2(cx, cy), radius, 0, TAU, 32,
		Color(COL_SPIKE.r, COL_SPIKE.g, COL_SPIKE.b, alpha * 0.4), 3.0)
	var max_t := 45.0
	var frac := clampf(_spike_timer / max_t, 0.0, 1.0)
	var arc_r := 24.0
	draw_arc(Vector2(cx, cy), arc_r, deg_to_rad(-90), deg_to_rad(-90 + frac * 360), 32,
		Color(COL_SPIKE.r, COL_SPIKE.g, COL_SPIKE.b, alpha), 3.0)
	var fs := 16
	var label := spike_text
	var tw := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	draw_string(font, Vector2(cx - tw * 0.5, cy + fs * 0.4), label,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(COL_SPIKE.r, COL_SPIKE.g, COL_SPIKE.b, alpha))


# ──── Net stats ────
func _draw_net_stats(vp: Vector2, font: Font) -> void:
	var x := vp.x - 12.0
	var y := 240.0
	var fs := 12
	var lines := [
		"RTT %s ms" % ping_text,
	]
	for line in lines:
		var text_w := font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
		draw_string(font, Vector2(x - text_w, y), line,
			HORIZONTAL_ALIGNMENT_LEFT, -1, fs, COL_TEXT_DIM)
		y += fs + 3


# ──── Scope overlay ────
func _draw_scope_overlay(vp: Vector2, font: Font) -> void:
	if not is_ads or not is_scoped:
		return
	var cx := vp.x * 0.5
	var cy := vp.y * 0.5
	var radius := minf(vp.x, vp.y) * 0.42
	for i in range(60):
		var angle := deg_to_rad(-180 + i * 3)
		var next_angle := deg_to_rad(-180 + (i + 1) * 3)
		var p1 := Vector2(cx + cos(angle) * radius, cy + sin(angle) * radius)
		var p2 := Vector2(cx + cos(next_angle) * radius, cy + sin(next_angle) * radius)
		var p3 := Vector2(cx + cos(next_angle) * (radius + 300), cy + sin(next_angle) * (radius + 300))
		var p4 := Vector2(cx + cos(angle) * (radius + 300), cy + sin(angle) * (radius + 300))
		draw_colored_polygon(PackedVector2Array([p1, p2, p3, p4]), Color(0, 0, 0, 0.85))
	var circle_color := Color(0.8, 0.85, 0.9, 0.9)
	var circle_points := PackedVector2Array()
	for i in range(64):
		var angle := deg_to_rad(i * 360.0 / 64.0)
		circle_points.append(Vector2(cx + cos(angle) * radius, cy + sin(angle) * radius))
	circle_points.append(circle_points[0])
	draw_polyline(circle_points, circle_color, 2.0)
	var cross_len := radius * 0.85
	var cross_gap := 8.0
	var cross_color := Color(0.9, 0.2, 0.2, 0.9)
	draw_line(Vector2(cx - cross_len, cy), Vector2(cx - cross_gap, cy), cross_color, 1.5)
	draw_line(Vector2(cx + cross_gap, cy), Vector2(cx + cross_len, cy), cross_color, 1.5)
	draw_line(Vector2(cx, cy - cross_len), Vector2(cx, cy - cross_gap), cross_color, 1.5)
	draw_line(Vector2(cx, cy + cross_gap), Vector2(cx, cy + cross_len), cross_color, 1.5)
	draw_circle(Vector2(cx, cy), 2.0, cross_color)
	for i in range(12):
		var angle := deg_to_rad(i * 30)
		var inner := radius - 6.0
		var outer := radius + 2.0
		draw_line(
			Vector2(cx + cos(angle) * inner, cy + sin(angle) * inner),
			Vector2(cx + cos(angle) * outer, cy + sin(angle) * outer),
			Color(0.6, 0.65, 0.7, 0.6), 1.0)
	for i in range(1, 5):
		var offset := float(i) * radius * 0.2
		var tick_len := 4.0
		draw_line(Vector2(cx - offset, cy - tick_len), Vector2(cx - offset, cy + tick_len),
			Color(0.5, 0.55, 0.6, 0.4), 1.0)
		draw_line(Vector2(cx + offset, cy - tick_len), Vector2(cx + offset, cy + tick_len),
			Color(0.5, 0.55, 0.6, 0.4), 1.0)


# ──── Death screen ────
func _draw_death_screen(vp: Vector2, font: Font) -> void:
	if health > 0:
		return
	var overlay_alpha := 0.6
	draw_rect(Rect2(0, 0, vp.x, vp.y), Color(0.1, 0.1, 0.12, overlay_alpha))
	# Grayscale vignette effect
	var cx := vp.x * 0.5
	var cy := vp.y * 0.5
	# "ELIMINATED" text
	var fs := 48
	var text := "ELIMINATED"
	var tw := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	draw_string(font, Vector2(cx - tw * 0.5, cy - 20), text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(0.9, 0.25, 0.22, 0.9))
	# Respawn timer
	if _respawn_timer > 0:
		var rt_str := "Respawning in %.1f" % _respawn_timer
		var rt_fs := 22
		var rt_w := font.get_string_size(rt_str, HORIZONTAL_ALIGNMENT_LEFT, -1, rt_fs).x
		draw_string(font, Vector2(cx - rt_w * 0.5, cy + 20), rt_str,
			HORIZONTAL_ALIGNMENT_LEFT, -1, rt_fs, COL_TEXT_DIM)


# ──── Round result ────
func _draw_round_result(vp: Vector2, font: Font) -> void:
	if _round_result_timer <= 0.0 or _round_result_text == "":
		return
	var cx := vp.x * 0.5
	var cy := vp.y * 0.4
	var a := clampf(_round_result_timer, 0.0, 1.0)
	draw_rect(Rect2(0, 0, vp.x, vp.y), Color(0, 0, 0, a * 0.3))
	var fs := 64
	var text_w := font.get_string_size(_round_result_text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var strip_h := fs + 30
	draw_rect(Rect2(0, cy - fs * 0.6, vp.x, strip_h),
		Color(_round_result_color.r, _round_result_color.g, _round_result_color.b, a * 0.12))
	draw_rect(Rect2(0, cy - fs * 0.6, vp.x, strip_h),
		Color(_round_result_color.r, _round_result_color.g, _round_result_color.b, a * 0.35), false, 2.0)
	_round_result_color.a = a
	draw_string(font, Vector2(cx - text_w * 0.5, cy + fs * 0.3), _round_result_text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, _round_result_color)
