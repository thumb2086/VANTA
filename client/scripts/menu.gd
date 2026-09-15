extends Control

## VANTA 主選單 — Valorant 風格三層導覽
## 1. 大廳（Home）：場景背景 + 頂部導航 + 新聞 + 對戰入口
## 2. 模式選擇：卡片網格（11 種模式）+ 漸層背景
## 3. 配對大廳：5 個高直卡片 + 玩家卡片 + 開始配對

# ──── 色彩 ────
const BG_DARK := Color(0.04, 0.05, 0.08)
const ACCENT := Color(0.0, 0.85, 0.75)
const ACCENT_RED := Color(0.92, 0.22, 0.28)
const ACCENT_RED_HOVER := Color(1.0, 0.32, 0.38)
const TEXT_WHITE := Color(0.94, 0.95, 0.97)
const TEXT_DIM := Color(0.50, 0.53, 0.60)
const TEXT_GOLD := Color(1.0, 0.82, 0.32)
const BORDER_DIM := Color(0.22, 0.25, 0.32)
const BORDER_LIGHT := Color(0.35, 0.38, 0.45)

# ──── 遊戲模式 ────
const MODES := [
	{"name": "一般模式", "desc": "5v5 經典爆破", "tag": "competitive",
		"bg_top": Color(0.12, 0.30, 0.28), "bg_bot": Color(0.04, 0.08, 0.10),
		"geo": Color(0.0, 0.7, 0.6)},
	{"name": "競技模式", "desc": "排位賽", "tag": "competitive",
		"bg_top": Color(0.32, 0.22, 0.08), "bg_bot": Color(0.08, 0.06, 0.04),
		"geo": Color(0.9, 0.7, 0.2)},
	{"name": "奪還作戰", "desc": "Bo7 先到 4・全場同槍・能量球", "tag": "spikerush",
		"bg_top": Color(0.38, 0.10, 0.14), "bg_bot": Color(0.10, 0.04, 0.06),
		"geo": Color(1.0, 0.3, 0.3)},
	{"name": "超速衝點", "desc": "Bo9 先到 5・濃縮經濟", "tag": "swiftplay",
		"bg_top": Color(0.08, 0.22, 0.42), "bg_bot": Color(0.04, 0.06, 0.14),
		"geo": Color(0.2, 0.6, 1.0)},
	{"name": "火線交鋒：2V2", "desc": "2v2 對決（即將推出）", "tag": "2v2",
		"bg_top": Color(0.22, 0.10, 0.38), "bg_bot": Color(0.06, 0.04, 0.12),
		"geo": Color(0.6, 0.3, 1.0)},
	{"name": "死鬥模式", "desc": "個人死鬥 40 殺", "tag": "deathmatch",
		"bg_top": Color(0.38, 0.26, 0.06), "bg_bot": Color(0.10, 0.07, 0.02),
		"geo": Color(1.0, 0.7, 0.1)},
	{"name": "團隊死鬥模式", "desc": "5v5 團隊死鬥 100 殺", "tag": "teamdeathmatch",
		"bg_top": Color(0.38, 0.12, 0.10), "bg_bot": Color(0.12, 0.04, 0.04),
		"geo": Color(1.0, 0.35, 0.2)},
	{"name": "輻能搶攻戰", "desc": "搶奪輻能核心", "tag": "escalation",
		"bg_top": Color(0.06, 0.32, 0.18), "bg_bot": Color(0.02, 0.08, 0.05),
		"geo": Color(0.1, 0.9, 0.4)},
	{"name": "超激進戰", "desc": "升級武器挑戰", "tag": "gun_game",
		"bg_top": Color(0.42, 0.20, 0.04), "bg_bot": Color(0.12, 0.06, 0.02),
		"geo": Color(1.0, 0.5, 0.0)},
	{"name": "PREMIER", "desc": "團隊排位賽", "tag": "premier",
		"bg_top": Color(0.28, 0.08, 0.32), "bg_bot": Color(0.08, 0.03, 0.10),
		"geo": Color(0.8, 0.2, 1.0)},
	{"name": "自訂對戰", "desc": "創建自訂房間", "tag": "custom",
		"bg_top": Color(0.12, 0.14, 0.18), "bg_bot": Color(0.05, 0.06, 0.08),
		"geo": Color(0.5, 0.55, 0.65)},
]

# ──── Agent 角色（配對大廳用）───
const AGENTS := [
	{"name": "夜露", "role": "決鬥者", "color": Color(0.8, 0.2, 0.3)},
	{"name": "幽影", "role": "控場者", "color": Color(0.3, 0.2, 0.7)},
	{"name": "賢者", "role": "守衛者", "color": Color(0.2, 0.7, 0.5)},
	{"name": "蘇法", "role": "偵查者", "color": Color(0.2, 0.5, 0.9)},
	{"name": "捷提", "role": "決鬥者", "color": Color(0.9, 0.6, 0.1)},
]

# ──── 狀態 ────
enum View { HOME, MODES, PARTY }
var _view := View.HOME
var _selected_mode := -1
var _player_name := "thumb"
var _anim_t := 0.0
var _hover_mode := -1
var _transition_alpha := 0.0
var _transition_target := -1
var _home_layer: Control
var _modes_layer: Control
var _party_layer: Control
var _top_bar: Control

# 卡片背景紋理快取
var _card_textures: Array[ImageTexture] = []
# 大廳背景紋理
var _home_bg_tex: ImageTexture
# 配對大廳背景紋理
var _party_bg_tex: ImageTexture


func _ready() -> void:
	# 全幕背景
	var bg := ColorRect.new()
	bg.color = BG_DARK
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	# 生成紋理
	_generate_card_textures()
	_generate_home_bg()
	_generate_party_bg()
	# 建立三層
	_home_layer = _build_home()
	add_child(_home_layer)
	_modes_layer = _build_modes()
	_modes_layer.visible = false
	add_child(_modes_layer)
	_party_layer = _build_party()
	_party_layer.visible = false
	add_child(_party_layer)
	_top_bar = _build_top_bar()
	add_child(_top_bar)
	_show_view(View.HOME)


func _process(delta: float) -> void:
	_anim_t += delta
	# 淡入淡出過渡
	if _transition_target >= 0:
		_transition_alpha = minf(_transition_alpha + delta * 4.0, 1.0)
		if _transition_alpha >= 1.0:
			_view = _transition_target as View
			_home_layer.visible = (_view == View.HOME)
			_modes_layer.visible = (_view == View.MODES)
			_party_layer.visible = (_view == View.PARTY)
			_top_bar.visible = true
			if _view == View.PARTY and _selected_mode >= 0:
				var lbl: Label = _party_layer.get_node_or_null("ModeName")
				if lbl:
					lbl.text = MODES[_selected_mode]["name"]
			_transition_target = -1
			_transition_alpha = 0.0
	queue_redraw()


# ═══════════════════════════════════════════════
#  紋理生成
# ═══════════════════════════════════════════════
func _generate_home_bg() -> void:
	# 1280x720 場景感背景：深空 + 遠山 + 光線
	var img := Image.create(1280, 720, false, Image.FORMAT_RGBA8)
	for y in range(720):
		var t := float(y) / 720.0
		for x in range(1280):
			var tx := float(x) / 1280.0
			# 天空漸層（左上青 → 右上藍 → 下深）
			var sky_top := Color(0.05, 0.18, 0.35)
			var sky_mid := Color(0.08, 0.12, 0.25)
			var sky_bot := Color(0.02, 0.03, 0.06)
			var c: Color
			if t < 0.45:
				c = sky_top.lerp(sky_mid, t / 0.45)
			else:
				c = sky_mid.lerp(sky_bot, (t - 0.45) / 0.55)
			# 加入水平漸變（右邊偏青）
			c = c.lerp(Color(0.04, 0.22, 0.32), tx * 0.3)
			# 遠山輪廓（三角波）
			var mountain_h := 0.0
			mountain_h += exp(-pow((tx - 0.15) * 8.0, 2)) * 0.20
			mountain_h += exp(-pow((tx - 0.35) * 5.0, 2)) * 0.35
			mountain_h += exp(-pow((tx - 0.55) * 6.0, 2)) * 0.28
			mountain_h += exp(-pow((tx - 0.75) * 7.0, 2)) * 0.32
			mountain_h += exp(-pow((tx - 0.92) * 5.0, 2)) * 0.22
			if t > (0.55 - mountain_h):
				var mt := (t - (0.55 - mountain_h)) / mountain_h
				var mc := Color(0.04, 0.06, 0.12).lerp(Color(0.06, 0.08, 0.14), mt)
				c = mc
			# 光束效果（右上角）
			var sun_dist := Vector2(tx - 0.78, t - 0.12).length()
			if sun_dist < 0.15:
				c = c.lerp(Color(0.3, 0.6, 0.8), (0.15 - sun_dist) / 0.15 * 0.4)
			# 噪點
			var noise := randf_range(-0.008, 0.008)
			c.r = clampf(c.r + noise, 0, 1)
			c.g = clampf(c.g + noise, 0, 1)
			c.b = clampf(c.b + noise, 0, 1)
			img.set_pixel(x, y, c)
	_home_bg_tex = ImageTexture.create_from_image(img)


func _generate_party_bg() -> void:
	var img := Image.create(1280, 720, false, Image.FORMAT_RGBA8)
	for y in range(720):
		var t := float(y) / 720.0
		for x in range(1280):
			var tx := float(x) / 1280.0
			# 深色場景（左右對稱暗角）
			var c := Color(0.04, 0.06, 0.12).lerp(Color(0.03, 0.05, 0.09), t)
			# 中央微亮
			var center_dist := absf(tx - 0.5)
			c = c.lerp(Color(0.06, 0.09, 0.16), (1.0 - center_dist) * 0.4)
			# 遠山
			var mh := exp(-pow((tx - 0.3) * 6.0, 2)) * 0.25
			mh += exp(-pow((tx - 0.7) * 5.0, 2)) * 0.30
			if t > (0.50 - mh):
				var mt := (t - (0.50 - mh)) / mh
				c = c.lerp(Color(0.03, 0.05, 0.10), mt * 0.7)
			# 噪點
			var noise := randf_range(-0.005, 0.005)
			c.r = clampf(c.r + noise, 0, 1)
			c.g = clampf(c.g + noise, 0, 1)
			c.b = clampf(c.b + noise, 0, 1)
			img.set_pixel(x, y, c)
	_party_bg_tex = ImageTexture.create_from_image(img)


func _generate_card_textures() -> void:
	_card_textures.clear()
	for mode in MODES:
		var img := Image.create(320, 180, false, Image.FORMAT_RGBA8)
		var top: Color = mode["bg_top"]
		var bot: Color = mode["bg_bot"]
		var geo: Color = mode["geo"]
		for y in range(180):
			var ty := float(y) / 180.0
			for x in range(320):
				var tx := float(x) / 320.0
				var c := bot.lerp(top, ty)
				# 對角線漸變
				c = c.lerp(top * 0.8, (tx + ty) * 0.3)
				# 幾何裝飾（斜線 + 三角形）
				var geo_factor := 0.0
				# 斜線紋理
				var diag := fmod(tx * 3.0 + ty * 2.0, 1.0)
				if diag > 0.92 and diag < 0.96:
					geo_factor = 0.15
				# 右下三角亮區
				if tx > 0.6 and ty > 0.4:
					var tri_dist := (tx - 0.6) + (ty - 0.4)
					if tri_dist > 0.3 and tri_dist < 0.6:
						geo_factor = maxf(geo_factor, 0.1)
				c = c.lerp(geo, geo_factor)
				# 底部漸暗（文字可讀性）
				if ty > 0.55:
					var darken := (ty - 0.55) / 0.45 * 0.65
					c = c.lerp(Color.BLACK, darken)
				# 邊框微亮
				if tx < 0.02 or tx > 0.98 or ty < 0.02:
					c = c.lerp(Color.WHITE, 0.08)
				# 噪點
				var noise := randf_range(-0.012, 0.012)
				c.r = clampf(c.r + noise, 0, 1)
				c.g = clampf(c.g + noise, 0, 1)
				c.b = clampf(c.b + noise, 0, 1)
				img.set_pixel(x, y, c)
		var tex := ImageTexture.create_from_image(img)
		_card_textures.append(tex)


# ═══════════════════════════════════════════════
#  背景繪製（動態疊加在紋理之上）
# ═══════════════════════════════════════════════
func _draw() -> void:
	match _view:
		View.HOME:
			_draw_home_bg()
		View.MODES:
			_draw_modes_bg()
		View.PARTY:
			_draw_party_bg()
	# 過渡遮罩
	if _transition_alpha > 0.0:
		draw_rect(Rect2(Vector2.ZERO, get_viewport_rect().size),
			Color(0, 0, 0, (1.0 - _transition_alpha) * 0.8))


func _draw_home_bg() -> void:
	var vp := get_viewport_rect().size
	# 繪製預生成的背景紋理
	if _home_bg_tex:
		draw_texture_rect(_home_bg_tex, Rect2(Vector2.ZERO, vp), false)
	# 動態光線（從右上方）
	var sun_pos := Vector2(vp.x * 0.78, vp.y * 0.12)
	for i in range(8):
		var angle := deg_to_rad(-50 + i * 12)
		var len := 600.0 + sin(_anim_t * 0.3 + i * 0.7) * 40.0
		var end := sun_pos + Vector2(cos(angle), sin(angle)) * len
		draw_line(sun_pos, end, Color(0.15, 0.40, 0.55, 0.025), 4.0)
	# 中央光暈
	var pulse := 0.04 + sin(_anim_t * 0.8) * 0.015
	draw_circle(sun_pos, 100.0, Color(0.25, 0.55, 0.75, pulse))
	draw_circle(sun_pos, 50.0, Color(0.35, 0.65, 0.85, pulse * 1.5))
	# 浮動粒子（小圓點）
	for i in range(12):
		var px := fmod(vp.x * 0.2 + i * 137.5 + _anim_t * (8.0 + i * 3.0), vp.x)
		var py := fmod(vp.y * 0.3 + i * 89.3 + sin(_anim_t * 0.5 + i) * 30.0, vp.y)
		draw_circle(Vector2(px, py), 1.5 + sin(_anim_t + i) * 0.5,
			Color(0.3, 0.7, 0.9, 0.15 + sin(_anim_t * 0.7 + i) * 0.08))
	# 底部漸暗
	for i in range(60):
		var a := float(i) / 60.0 * 0.4
		draw_line(Vector2(0, vp.y - i), Vector2(vp.x, vp.y - i), Color(0, 0, 0, a), 1.0)


func _draw_modes_bg() -> void:
	var vp := get_viewport_rect().size
	# 深底
	draw_rect(Rect2(Vector2.ZERO, vp), Color(0.04, 0.05, 0.08))
	# 底部微光
	for i in range(40):
		var a := float(i) / 40.0 * 0.15
		draw_line(Vector2(0, vp.y - i), Vector2(vp.x, vp.y - i),
			Color(ACCENT.r, ACCENT.g, ACCENT.b, a * 0.3), 1.0)
	# 頂部裝飾線
	draw_line(Vector2(0, 62), Vector2(vp.x, 62), BORDER_DIM, 1.0)


func _draw_party_bg() -> void:
	var vp := get_viewport_rect().size
	# 預生成背景
	if _party_bg_tex:
		draw_texture_rect(_party_bg_tex, Rect2(Vector2.ZERO, vp), false)
	# 中央菱形光暈（脈動）
	var cx := vp.x * 0.5
	var cy := vp.y * 0.38
	var pulse := 0.03 + sin(_anim_t * 1.0) * 0.012
	var sz := 200.0
	var diamond := PackedVector2Array([
		Vector2(cx, cy - sz),
		Vector2(cx + sz * 0.55, cy),
		Vector2(cx, cy + sz),
		Vector2(cx - sz * 0.55, cy),
		Vector2(cx, cy - sz),
	])
	draw_polyline(diamond, Color(ACCENT.r, ACCENT.g, ACCENT.b, pulse), 1.5)
	sz = 150.0
	diamond = PackedVector2Array([
		Vector2(cx, cy - sz),
		Vector2(cx + sz * 0.55, cy),
		Vector2(cx, cy + sz),
		Vector2(cx - sz * 0.55, cy),
		Vector2(cx, cy - sz),
	])
	draw_polyline(diamond, Color(ACCENT.r, ACCENT.g, ACCENT.b, pulse * 0.6), 1.0)
	# 底部漸暗
	for i in range(50):
		var a := float(i) / 50.0 * 0.35
		draw_line(Vector2(0, vp.y - i), Vector2(vp.x, vp.y - i), Color(0, 0, 0, a), 1.0)


# ═══════════════════════════════════════════════
#  頂部導航列
# ═══════════════════════════════════════════════
func _build_top_bar() -> Control:
	var bar := PanelContainer.new()
	bar.set_anchors_preset(Control.PRESET_TOP_WIDE)
	bar.custom_minimum_size = Vector2(0, 50)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.02, 0.03, 0.05, 0.94)
	sb.content_margin_left = 20
	sb.content_margin_right = 20
	bar.add_theme_stylebox_override("panel", sb)
	var hbox := HBoxContainer.new()
	hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	hbox.add_theme_constant_override("separation", 6)
	bar.add_child(hbox)

	# Logo
	var logo := Label.new()
	logo.text = "V A N T A"
	logo.add_theme_font_size_override("font_size", 17)
	logo.add_theme_color_override("font_color", ACCENT)
	hbox.add_child(logo)

	var sep1 := VSeparator.new()
	sep1.custom_minimum_size.x = 2
	hbox.add_child(sep1)

	# 首頁
	var home_btn := Button.new()
	home_btn.text = "  🏠  "
	home_btn.flat = true
	home_btn.custom_minimum_size = Vector2(40, 38)
	home_btn.add_theme_font_size_override("font_size", 15)
	home_btn.pressed.connect(_on_nav.bind(View.HOME))
	hbox.add_child(home_btn)

	# 「對戰」紅色三角按鈕
	var fight_container := Control.new()
	fight_container.custom_minimum_size = Vector2(120, 38)
	hbox.add_child(fight_container)
	var fight_bg := ColorRect.new()
	fight_bg.color = ACCENT_RED
	fight_bg.position = Vector2(0, 0)
	fight_bg.size = Vector2(120, 38)
	fight_container.add_child(fight_bg)
	# 三角裝飾
	var tri_icon := Label.new()
	tri_icon.text = "⚔"
	tri_icon.position = Vector2(10, 4)
	tri_icon.add_theme_font_size_override("font_size", 14)
	tri_icon.add_theme_color_override("font_color", Color.WHITE)
	fight_container.add_child(tri_icon)
	var fight_lbl := Label.new()
	fight_lbl.text = "對  戰"
	fight_lbl.position = Vector2(35, 6)
	fight_lbl.size = Vector2(70, 26)
	fight_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	fight_lbl.add_theme_font_size_override("font_size", 15)
	fight_lbl.add_theme_color_override("font_color", Color.WHITE)
	fight_container.add_child(fight_lbl)
	var fight_btn := Button.new()
	fight_btn.flat = true
	fight_btn.set_anchors_preset(Control.PRESET_FULL_RECT)
	fight_btn.pressed.connect(_on_nav.bind(View.MODES))
	fight_container.add_child(fight_btn)

	# 右側小圖示
	var icon_data := [
		{"icon": "🏆", "action": func(): get_tree().change_scene_to_file("res://social_ui.tscn")},
		{"icon": "🎒", "action": func(): _show_inventory()},
		{"icon": "🛒", "action": func(): get_tree().change_scene_to_file("res://workshop.tscn")},
		{"icon": "📊", "action": func(): _show_stats()},
	]
	for data in icon_data:
		var btn := Button.new()
		btn.text = data["icon"]
		btn.flat = true
		btn.custom_minimum_size = Vector2(36, 36)
		btn.add_theme_font_size_override("font_size", 14)
		btn.pressed.connect(data["action"])
		hbox.add_child(btn)

	# 彈性空間
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(spacer)

	# 右側統計
	for stat_text in ["4/4", "2/3"]:
		var stat := Label.new()
		stat.text = stat_text
		stat.add_theme_font_size_override("font_size", 12)
		stat.add_theme_color_override("font_color", TEXT_DIM)
		hbox.add_child(stat)
		var stat_sep := Label.new()
		stat_sep.text = "  "
		hbox.add_child(stat_sep)

	# 信箱
	var mail := Label.new()
	mail.text = "✉"
	mail.add_theme_font_size_override("font_size", 14)
	mail.add_theme_color_override("font_color", TEXT_DIM)
	hbox.add_child(mail)

	# 金幣顯示
	for currency in [["204", "💰"], ["105", "💎"], ["1,820", "⚡"]]:
		var c_icon := Label.new()
		c_icon.text = currency[1]
		c_icon.add_theme_font_size_override("font_size", 12)
		c_icon.add_theme_color_override("font_color", TEXT_DIM)
		hbox.add_child(c_icon)
		var c_val := Label.new()
		c_val.text = currency[0]
		c_val.add_theme_font_size_override("font_size", 12)
		c_val.add_theme_color_override("font_color", TEXT_DIM)
		hbox.add_child(c_val)
		var c_sep := Label.new()
		c_sep.text = " "
		hbox.add_child(c_sep)

	# 社交
	var social_btn := Button.new()
	social_btn.text = "👥"
	social_btn.flat = true
	social_btn.custom_minimum_size = Vector2(36, 36)
	social_btn.add_theme_font_size_override("font_size", 16)
	social_btn.pressed.connect(_open_social)
	hbox.add_child(social_btn)

	# 設定
	var settings_btn := Button.new()
	settings_btn.text = "⚙"
	settings_btn.flat = true
	settings_btn.custom_minimum_size = Vector2(36, 36)
	settings_btn.add_theme_font_size_override("font_size", 16)
	settings_btn.pressed.connect(func(): get_tree().change_scene_to_file("res://settings.tscn"))
	hbox.add_child(settings_btn)

	return bar


func _open_social() -> void:
	var social_ui := preload("res://social_ui.tscn").instantiate()
	add_child(social_ui)


func _show_inventory() -> void:
	"""顯示背包/物品欄"""
	var popup := Control.new()
	popup.set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0, 0, 0, 0.8)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.gui_input.connect(func(e): if e is InputEventMouseButton and e.pressed: popup.queue_free())
	popup.add_child(bg)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(500, 400)
	var psb := StyleBoxFlat.new()
	psb.bg_color = Color(0.08, 0.08, 0.12)
	psb.border_color = Color(0.3, 0.3, 0.4)
	psb.set_border_width_all(2)
	psb.corner_radius_top_left = 8
	psb.corner_radius_top_right = 8
	psb.corner_radius_bottom_left = 8
	psb.corner_radius_bottom_right = 8
	panel.add_theme_stylebox_override("panel", psb)
	popup.add_child(panel)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 12)
	vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	panel.add_child(vbox)
	var title := Label.new()
	title.text = "🎒 背包"
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color.WHITE)
	vbox.add_child(title)
	var divider := HSeparator.new()
	vbox.add_child(divider)
	# 已擁有的武器皮膚
	var skins_label := Label.new()
	skins_label.text = "已擁有的皮膚："
	skins_label.add_theme_font_size_override("font_size", 14)
	skins_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.8))
	vbox.add_child(skins_label)
	var grid := GridContainer.new()
	grid.columns = 4
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 8)
	vbox.add_child(grid)
	# 示範皮膚
	var demo_skins := [
		{"name": "標準 Phantom", "color": Color(0.25, 0.27, 0.32)},
		{"name": "掠奪者 Vandal", "color": Color(0.12, 0.06, 0.18)},
		{"name": "鬼魅 Ghost", "color": Color(0.3, 0.3, 0.35)},
		{"name": "經典 Classic", "color": Color(0.2, 0.2, 0.25)},
	]
	for skin in demo_skins:
		var card := PanelContainer.new()
		card.custom_minimum_size = Vector2(110, 60)
		var csb := StyleBoxFlat.new()
		csb.bg_color = skin["color"]
		csb.corner_radius_top_left = 4
		csb.corner_radius_top_right = 4
		csb.corner_radius_bottom_left = 4
		csb.corner_radius_bottom_right = 4
		card.add_theme_stylebox_override("panel", csb)
		grid.add_child(card)
		var skin_name := Label.new()
		skin_name.text = skin["name"]
		skin_name.set_anchors_preset(Control.PRESET_FULL_RECT)
		skin_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		skin_name.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		skin_name.add_theme_font_size_override("font_size", 11)
		skin_name.add_theme_color_override("font_color", Color.WHITE)
		card.add_child(skin_name)
	# 關閉按鈕
	var close_btn := Button.new()
	close_btn.text = "✕ 關閉"
	close_btn.custom_minimum_size = Vector2(100, 36)
	close_btn.pressed.connect(popup.queue_free)
	vbox.add_child(close_btn)
	add_child(popup)


func _show_stats() -> void:
	"""顯示統計資料"""
	var popup := Control.new()
	popup.set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0, 0, 0, 0.8)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.gui_input.connect(func(e): if e is InputEventMouseButton and e.pressed: popup.queue_free())
	popup.add_child(bg)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(500, 400)
	var psb := StyleBoxFlat.new()
	psb.bg_color = Color(0.08, 0.08, 0.12)
	psb.border_color = Color(0.3, 0.3, 0.4)
	psb.set_border_width_all(2)
	psb.corner_radius_top_left = 8
	psb.corner_radius_top_right = 8
	psb.corner_radius_bottom_left = 8
	psb.corner_radius_bottom_right = 8
	panel.add_theme_stylebox_override("panel", psb)
	popup.add_child(panel)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 12)
	vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	panel.add_child(vbox)
	var title := Label.new()
	title.text = "📊 統計資料"
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color.WHITE)
	vbox.add_child(title)
	var divider := HSeparator.new()
	vbox.add_child(divider)
	# 統計項目
	var stats := [
		{"label": "總擊殺", "value": "0", "color": Color(0.2, 0.8, 0.4)},
		{"label": "總死亡", "value": "0", "color": Color(0.8, 0.2, 0.2)},
		{"label": "總助攻", "value": "0", "color": Color(0.2, 0.6, 1.0)},
		{"label": "勝率", "value": "0%", "color": Color(1.0, 0.85, 0.0)},
		{"label": "場數", "value": "0", "color": Color(0.5, 0.5, 0.6)},
		{"label": "最高連勝", "value": "0", "color": Color(1.0, 0.5, 0.2)},
	]
	for stat in stats:
		var hbox := HBoxContainer.new()
		hbox.add_theme_constant_override("separation", 12)
		vbox.add_child(hbox)
		var lbl := Label.new()
		lbl.text = stat["label"]
		lbl.add_theme_font_size_override("font_size", 14)
		lbl.add_theme_color_override("font_color", Color(0.7, 0.7, 0.8))
		hbox.add_child(lbl)
		var spacer := Control.new()
		spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		hbox.add_child(spacer)
		var val := Label.new()
		val.text = stat["value"]
		val.add_theme_font_size_override("font_size", 16)
		val.add_theme_color_override("font_color", stat["color"])
		hbox.add_child(val)
	# 關閉按鈕
	var close_btn := Button.new()
	close_btn.text = "✕ 關閉"
	close_btn.custom_minimum_size = Vector2(100, 36)
	close_btn.pressed.connect(popup.queue_free)
	vbox.add_child(close_btn)
	add_child(popup)


func _on_nav(view: int) -> void:
	if view >= 0:
		_transition_target = view
		_transition_alpha = 0.0


# ═══════════════════════════════════════════════
#  畫面 1：大廳（Home）
# ═══════════════════════════════════════════════
func _build_home() -> Control:
	var layer := Control.new()
	layer.set_anchors_preset(Control.PRESET_FULL_RECT)
	# 標題
	var title := Label.new()
	title.text = "V A N T A"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.position = Vector2(0, 130)
	title.size = Vector2(1280, 60)
	title.add_theme_font_size_override("font_size", 52)
	title.add_theme_color_override("font_color", Color(1, 1, 1, 0.95))
	layer.add_child(title)
	# 副標題
	var sub := Label.new()
	sub.text = "5v5 戰術射擊  ·  伺服器權威防作弊"
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub.position = Vector2(0, 195)
	sub.size = Vector2(1280, 24)
	sub.add_theme_font_size_override("font_size", 14)
	sub.add_theme_color_override("font_color", TEXT_DIM)
	layer.add_child(sub)

	# 「對戰」紅色大按鈕
	var play_btn := Button.new()
	play_btn.text = "⚔  對  戰"
	play_btn.set_anchors_preset(Control.PRESET_CENTER)
	play_btn.position = Vector2(-130, 70)
	play_btn.size = Vector2(260, 54)
	play_btn.add_theme_font_size_override("font_size", 22)
	play_btn.add_theme_color_override("font_color", Color.WHITE)
	var play_sb := StyleBoxFlat.new()
	play_sb.bg_color = ACCENT_RED
	play_sb.corner_radius_top_left = 4
	play_sb.corner_radius_top_right = 4
	play_sb.corner_radius_bottom_left = 4
	play_sb.corner_radius_bottom_right = 4
	play_sb.content_margin_left = 20
	play_sb.content_margin_right = 20
	play_btn.add_theme_stylebox_override("normal", play_sb)
	var play_h := play_sb.duplicate()
	play_h.bg_color = ACCENT_RED_HOVER
	play_btn.add_theme_stylebox_override("hover", play_h)
	play_btn.pressed.connect(_on_nav.bind(View.MODES))
	layer.add_child(play_btn)

	# 左側新聞面板
	var news_panel := _build_news_panel()
	news_panel.position = Vector2(20, 130)
	layer.add_child(news_panel)

	# 左下方武器展示卡
	var weapon_card := _build_weapon_card()
	weapon_card.position = Vector2(20, 400)
	layer.add_child(weapon_card)

	# 左下方地圖產生器卡
	var mapgen_card := _build_mapgen_card()
	mapgen_card.position = Vector2(20, 520)
	layer.add_child(mapgen_card)

	# 底部版本
	var ver := Label.new()
	ver.text = "VANTA v0.1 — 開源研究專案"
	ver.position = Vector2(0, 696)
	ver.size = Vector2(1280, 24)
	ver.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ver.add_theme_font_size_override("font_size", 11)
	ver.add_theme_color_override("font_color", Color(0.20, 0.23, 0.28))
	layer.add_child(ver)

	# 右側好友列表
	var friends := _build_friends_panel()
	friends.position = Vector2(1050, 70)
	layer.add_child(friends)

	return layer


func _build_news_panel() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size = Vector2(280, 250)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.06, 0.10, 0.85)
	sb.border_color = Color(0.15, 0.18, 0.25, 0.5)
	sb.set_border_width_all(1)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	sb.content_margin_left = 16
	sb.content_margin_right = 16
	sb.content_margin_top = 14
	sb.content_margin_bottom = 14
	panel.add_theme_stylebox_override("panel", sb)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 12)
	panel.add_child(vbox)
	var ntitle := Label.new()
	ntitle.text = "📰 最新消息"
	ntitle.add_theme_font_size_override("font_size", 14)
	ntitle.add_theme_color_override("font_color", ACCENT)
	vbox.add_child(ntitle)
	var divider := HSeparator.new()
	vbox.add_child(divider)
	for item in [
		["🎯 夺還作戰", "限時模式：3v3 陣伍，逐步升級裝備"],
		["🗡 邊陲紀元造型槍", "造型槍率先看預告片"],
		["📋 版本更新公告", "v1.3.02 平衡調整已上線"],
	]:
		var hbox := HBoxContainer.new()
		hbox.add_theme_constant_override("separation", 8)
		vbox.add_child(hbox)
		var icon_lbl := Label.new()
		icon_lbl.text = item[0]
		icon_lbl.add_theme_font_size_override("font_size", 12)
		icon_lbl.add_theme_color_override("font_color", TEXT_WHITE)
		hbox.add_child(icon_lbl)
		var desc_lbl := Label.new()
		desc_lbl.text = item[1]
		desc_lbl.add_theme_font_size_override("font_size", 10)
		desc_lbl.add_theme_color_override("font_color", TEXT_DIM)
		hbox.add_child(desc_lbl)
	return panel


func _build_weapon_card() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size = Vector2(280, 120)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.08, 0.10, 0.14, 0.75)
	sb.border_color = Color(0.15, 0.18, 0.25, 0.4)
	sb.set_border_width_all(1)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	sb.content_margin_left = 16
	sb.content_margin_right = 16
	sb.content_margin_top = 12
	panel.add_theme_stylebox_override("panel", sb)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 6)
	panel.add_child(vbox)
	var wtitle := Label.new()
	wtitle.text = "🔫 武器工坊"
	wtitle.add_theme_font_size_override("font_size", 14)
	wtitle.add_theme_color_override("font_color", TEXT_GOLD)
	vbox.add_child(wtitle)
	var wdesc := Label.new()
	wdesc.text = "改造武器外觀 · 檢視動畫 · 自訂配色"
	wdesc.add_theme_font_size_override("font_size", 11)
	wdesc.add_theme_color_override("font_color", TEXT_DIM)
	vbox.add_child(wdesc)
	var wstatus := Label.new()
	wstatus.text = "▶  進入工坊"
	wstatus.add_theme_font_size_override("font_size", 12)
	wstatus.add_theme_color_override("font_color", ACCENT)
	vbox.add_child(wstatus)
	# 點擊進入工坊
	panel.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			get_tree().change_scene_to_file("res://workshop.tscn")
	)
	return panel


func _build_mapgen_card() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size = Vector2(280, 100)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.06, 0.10, 0.14, 0.75)
	sb.border_color = Color(0.15, 0.18, 0.25, 0.4)
	sb.set_border_width_all(1)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	sb.content_margin_left = 16
	sb.content_margin_right = 16
	sb.content_margin_top = 12
	panel.add_theme_stylebox_override("panel", sb)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 6)
	panel.add_child(vbox)
	var wtitle := Label.new()
	wtitle.text = "🗺 地圖產生器"
	wtitle.add_theme_font_size_override("font_size", 14)
	wtitle.add_theme_color_override("font_color", Color(0.3, 0.8, 1.0))
	vbox.add_child(wtitle)
	var wdesc := Label.new()
	wdesc.text = "程序化生成戰術地圖 · 自訂房間/走廊"
	wdesc.add_theme_font_size_override("font_size", 11)
	wdesc.add_theme_color_override("font_color", TEXT_DIM)
	vbox.add_child(wdesc)
	var wstatus := Label.new()
	wstatus.text = "▶  開始生成"
	wstatus.add_theme_font_size_override("font_size", 12)
	wstatus.add_theme_color_override("font_color", Color(0.3, 0.8, 1.0))
	vbox.add_child(wstatus)
	panel.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			get_tree().change_scene_to_file("res://map_generator.tscn")
	)
	return panel


func _build_friends_panel() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size = Vector2(200, 500)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.03, 0.04, 0.07, 0.7)
	sb.border_color = Color(0.12, 0.15, 0.20, 0.3)
	sb.set_border_width_all(1)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 12
	panel.add_theme_stylebox_override("panel", sb)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 8)
	panel.add_child(vbox)
	var ftitle := Label.new()
	ftitle.text = "👥 好友列表"
	ftitle.add_theme_font_size_override("font_size", 12)
	ftitle.add_theme_color_override("font_color", TEXT_DIM)
	vbox.add_child(ftitle)
	var divider := HSeparator.new()
	vbox.add_child(divider)
	for friend in [[" thumb", "線上"], [" 🤖 AI-01", "在線"], [" 🤖 AI-02", "在線"]]:
		var hbox := HBoxContainer.new()
		hbox.add_theme_constant_override("separation", 8)
		vbox.add_child(hbox)
		var name_lbl := Label.new()
		name_lbl.text = friend[0]
		name_lbl.add_theme_font_size_override("font_size", 11)
		name_lbl.add_theme_color_override("font_color", TEXT_WHITE)
		hbox.add_child(name_lbl)
		var status_lbl := Label.new()
		status_lbl.text = friend[1]
		status_lbl.add_theme_font_size_override("font_size", 10)
		status_lbl.add_theme_color_override("font_color", Color(0.2, 0.8, 0.4))
		hbox.add_child(status_lbl)
	return panel


# ═══════════════════════════════════════════════
#  畫面 2：模式選擇
# ═══════════════════════════════════════════════
func _build_modes() -> Control:
	var layer := Control.new()
	layer.set_anchors_preset(Control.PRESET_FULL_RECT)
	# 標題
	var title := Label.new()
	title.text = "選擇列隊"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.position = Vector2(0, 12)
	title.size = Vector2(1280, 44)
	title.add_theme_font_size_override("font_size", 28)
	title.add_theme_color_override("font_color", TEXT_WHITE)
	layer.add_child(title)
	# 標題下方裝飾線
	var line := ColorRect.new()
	line.color = Color(BORDER_DIM.r, BORDER_DIM.g, BORDER_DIM.b, 0.5)
	line.position = Vector2(400, 52)
	line.size = Vector2(480, 1)
	layer.add_child(line)
	# 卡片網格
	var grid := GridContainer.new()
	grid.columns = 4
	grid.position = Vector2(55, 68)
	grid.size = Vector2(1170, 640)
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 10)
	layer.add_child(grid)
	for i in range(MODES.size()):
		var card := _build_mode_card(i)
		grid.add_child(card)
	# 關閉按鈕
	var close_btn := Button.new()
	close_btn.text = "✕"
	close_btn.position = Vector2(1236, 14)
	close_btn.size = Vector2(36, 36)
	close_btn.flat = true
	close_btn.add_theme_font_size_override("font_size", 22)
	close_btn.add_theme_color_override("font_color", TEXT_DIM)
	close_btn.pressed.connect(_on_nav.bind(View.HOME))
	layer.add_child(close_btn)
	return layer


func _build_mode_card(idx: int) -> PanelContainer:
	var mode: Dictionary = MODES[idx]
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(280, 150)
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	# StyleBox
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(1, 1, 1, 0)
	sb.border_color = Color(0.2, 0.22, 0.28, 0.3)
	sb.set_border_width_all(1)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	panel.add_theme_stylebox_override("panel", sb)
	# 背景紋理
	var tex_rect := TextureRect.new()
	tex_rect.stretch_mode = TextureRect.STRETCH_SCALE
	tex_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	tex_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if idx < _card_textures.size():
		tex_rect.texture = _card_textures[idx]
	panel.add_child(tex_rect)
	# 內容（底部覆蓋）
	var vbox := VBoxContainer.new()
	vbox.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	vbox.position = Vector2(0, -55)
	vbox.custom_minimum_size = Vector2(0, 55)
	vbox.grow_vertical = Control.GROW_DIRECTION_BEGIN
	vbox.add_theme_constant_override("separation", 2)
	vbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(vbox)
	# 模式名稱
	var name_lbl := Label.new()
	name_lbl.text = mode["name"]
	name_lbl.add_theme_font_size_override("font_size", 16)
	name_lbl.add_theme_color_override("font_color", Color.WHITE)
	vbox.add_child(name_lbl)
	# Tag + 圖示
	var tag_hbox := HBoxContainer.new()
	tag_hbox.add_theme_constant_override("separation", 4)
	vbox.add_child(tag_hbox)
	var tag_icon := Label.new()
	tag_icon.text = "◉"
	tag_icon.add_theme_font_size_override("font_size", 10)
	tag_icon.add_theme_color_override("font_color", mode["geo"])
	tag_hbox.add_child(tag_icon)
	var tag_lbl := Label.new()
	tag_lbl.text = mode["tag"]
	tag_lbl.add_theme_font_size_override("font_size", 10)
	tag_lbl.add_theme_color_override("font_color", Color(1, 1, 1, 0.55))
	tag_hbox.add_child(tag_lbl)
	# 互動
	panel.mouse_entered.connect(_on_mode_hover.bind(idx))
	panel.mouse_exited.connect(_on_mode_hover.bind(-1))
	panel.gui_input.connect(_on_mode_input.bind(idx))
	return panel


func _on_mode_hover(idx: int) -> void:
	_hover_mode = idx


func _on_mode_input(event: InputEvent, idx: int) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_selected_mode = idx
		_transition_target = View.PARTY
		_transition_alpha = 0.0


# ═══════════════════════════════════════════════
#  畫面 3：配對大廳
# ═══════════════════════════════════════════════
func _build_party() -> Control:
	var layer := Control.new()
	layer.set_anchors_preset(Control.PRESET_FULL_RECT)
	# 「返回 // 對戰」
	var back_btn := Button.new()
	back_btn.text = "◀ 返回 // 對戰"
	back_btn.position = Vector2(20, 14)
	back_btn.size = Vector2(200, 30)
	back_btn.flat = true
	back_btn.add_theme_font_size_override("font_size", 13)
	back_btn.add_theme_color_override("font_color", TEXT_DIM)
	back_btn.pressed.connect(_on_nav.bind(View.MODES))
	layer.add_child(back_btn)
	# 標題
	var title := Label.new()
	title.name = "ModeName"
	title.text = "對  戰"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.position = Vector2(0, 10)
	title.size = Vector2(1280, 40)
	title.add_theme_font_size_override("font_size", 26)
	title.add_theme_color_override("font_color", TEXT_WHITE)
	layer.add_child(title)

	# 左側資訊面板
	var info := PanelContainer.new()
	info.position = Vector2(24, 110)
	info.size = Vector2(180, 200)
	var isb := StyleBoxFlat.new()
	isb.bg_color = Color(0.04, 0.06, 0.10, 0.8)
	isb.border_color = Color(0.15, 0.18, 0.25, 0.4)
	isb.set_border_width_all(1)
	isb.corner_radius_top_left = 6
	isb.corner_radius_top_right = 6
	isb.corner_radius_bottom_left = 6
	isb.corner_radius_bottom_right = 6
	isb.content_margin_left = 14
	isb.content_margin_right = 14
	isb.content_margin_top = 14
	info.add_theme_stylebox_override("panel", isb)
	layer.add_child(info)
	var ivbox := VBoxContainer.new()
	ivbox.add_theme_constant_override("separation", 16)
	info.add_child(ivbox)
	for item in [["列隊", "一般模式"], ["群組代碼", "💬"], ["群組", "🔒 已關閉"]]:
		var vbox := VBoxContainer.new()
		vbox.add_theme_constant_override("separation", 2)
		ivbox.add_child(vbox)
		var k := Label.new()
		k.text = item[0]
		k.add_theme_font_size_override("font_size", 11)
		k.add_theme_color_override("font_color", TEXT_DIM)
		vbox.add_child(k)
		var v := Label.new()
		v.text = item[1]
		v.add_theme_font_size_override("font_size", 13)
		v.add_theme_color_override("font_color", TEXT_WHITE)
		vbox.add_child(v)

	# 5 個高直玩家槽位（Valorant 風格：高瘦卡片 + Agent 占位）
	var slots_start_x := 240.0
	var slot_w := 155.0
	var slot_h := 430.0
	var slot_gap := 14.0
	for i in range(5):
		var x := slots_start_x + i * (slot_w + slot_gap)
		var slot := _build_tall_player_slot(i, Vector2(slot_w, slot_h))
		slot.position = Vector2(x, 80)
		layer.add_child(slot)

	# 底部按鈕列
	var btn_row := HBoxContainer.new()
	btn_row.position = Vector2(0, 620)
	btn_row.size = Vector2(1280, 60)
	btn_row.alignment = BoxContainer.ALIGNMENT_CENTER
	btn_row.add_theme_constant_override("separation", 16)
	layer.add_child(btn_row)

	# 訓練
	var train_btn := _make_button("🎯 訓練", Color(0.14, 0.16, 0.22), Vector2(140, 44))
	train_btn.pressed.connect(_start_game.bind("train"))
	btn_row.add_child(train_btn)
	# 開始配對（紅色大按鈕）
	var match_btn := _make_button("⚔  開始配對", ACCENT_RED, Vector2(220, 50))
	match_btn.add_theme_font_size_override("font_size", 20)
	match_btn.add_theme_color_override("font_color", Color.WHITE)
	var match_sb := match_btn.get_theme_stylebox("normal").duplicate()
	match_sb.corner_radius_top_left = 4
	match_sb.corner_radius_top_right = 4
	match_sb.corner_radius_bottom_left = 4
	match_sb.corner_radius_bottom_right = 4
	match_btn.add_theme_stylebox_override("normal", match_sb)
	var match_h := match_sb.duplicate()
	match_h.bg_color = ACCENT_RED_HOVER
	match_btn.add_theme_stylebox_override("hover", match_h)
	match_btn.pressed.connect(_start_game.bind("match"))
	btn_row.add_child(match_btn)
	# 離開群組
	var leave_btn := _make_button("離開群組", Color(0.10, 0.12, 0.16), Vector2(140, 44))
	leave_btn.add_theme_color_override("font_color", TEXT_DIM)
	leave_btn.pressed.connect(_on_nav.bind(View.MODES))
	btn_row.add_child(leave_btn)

	# 底部連線聊天列
	var chat_bar := PanelContainer.new()
	chat_bar.position = Vector2(0, 688)
	chat_bar.size = Vector2(1280, 32)
	var csb := StyleBoxFlat.new()
	csb.bg_color = Color(0.02, 0.03, 0.05, 0.8)
	chat_bar.add_theme_stylebox_override("panel", csb)
	layer.add_child(chat_bar)
	var chat_lbl := Label.new()
	chat_lbl.text = "  群組："
	chat_lbl.position = Vector2(10, 6)
	chat_lbl.add_theme_font_size_override("font_size", 11)
	chat_lbl.add_theme_color_override("font_color", TEXT_DIM)
	chat_bar.add_child(chat_lbl)

	return layer


func _build_tall_player_slot(idx: int, sz: Vector2) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = sz
	var sb := StyleBoxFlat.new()
	if idx == 0:
		# 自己：完整 Agent 卡片
		sb.bg_color = Color(0.06, 0.10, 0.16, 0.92)
		sb.border_color = ACCENT
		sb.set_border_width_all(2)
	else:
		sb.bg_color = Color(0.05, 0.07, 0.11, 0.45)
		sb.border_color = Color(0.18, 0.20, 0.26, 0.35)
		sb.set_border_width_all(1)
	sb.corner_radius_top_left = 8
	sb.corner_radius_top_right = 8
	sb.corner_radius_bottom_left = 8
	sb.corner_radius_bottom_right = 8
	panel.add_theme_stylebox_override("panel", sb)

	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 4)
	vbox.custom_minimum_size = Vector2(0, 55)
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_child(vbox)

	if idx == 0:
		# Agent 等級
		var rank_badge := Label.new()
		rank_badge.text = "✦ 86"
		rank_badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		rank_badge.add_theme_font_size_override("font_size", 11)
		rank_badge.add_theme_color_override("font_color", TEXT_GOLD)
		vbox.add_child(rank_badge)
		# 角色頭像區（Agent 色彩漸層）
		var avatar := ColorRect.new()
		avatar.color = AGENTS[0]["color"].darkened(0.6)
		avatar.custom_minimum_size = Vector2(120, 220)
		avatar.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		vbox.add_child(avatar)
		# 分隔線（青綠）
		var sep := ColorRect.new()
		sep.color = ACCENT
		sep.custom_minimum_size = Vector2(90, 2)
		sep.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		vbox.add_child(sep)
		# 準備狀態
		var status := Label.new()
		status.text = "準備完成"
		status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		status.add_theme_font_size_override("font_size", 11)
		status.add_theme_color_override("font_color", Color(0.5, 0.9, 0.7))
		vbox.add_child(status)
		# 玩家名
		var name_lbl := Label.new()
		name_lbl.text = _player_name
		name_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		name_lbl.add_theme_font_size_override("font_size", 16)
		name_lbl.add_theme_color_override("font_color", TEXT_GOLD)
		vbox.add_child(name_lbl)
		# Agent 名
		var agent_lbl := Label.new()
		agent_lbl.text = AGENTS[0]["name"]
		agent_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		agent_lbl.add_theme_font_size_override("font_size", 12)
		agent_lbl.add_theme_color_override("font_color", TEXT_DIM)
		vbox.add_child(agent_lbl)
	else:
		# 空槽位 - 可點擊邀請
		var invite_btn := Button.new()
		invite_btn.flat = true
		invite_btn.set_anchors_preset(Control.PRESET_FULL_RECT)
		var invite_sb := StyleBoxFlat.new()
		invite_sb.bg_color = Color(0, 0, 0, 0)
		invite_sb.set_border_width_all(0)
		invite_btn.add_theme_stylebox_override("normal", invite_sb)
		invite_btn.add_theme_stylebox_override("hover", invite_sb)
		invite_btn.pressed.connect(_open_invite_popup.bind(idx))
		panel.add_child(invite_btn)
		var spacer_top := Control.new()
		spacer_top.custom_minimum_size.y = 160
		vbox.add_child(spacer_top)
		var plus := Label.new()
		plus.text = "+"
		plus.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		plus.add_theme_font_size_override("font_size", 36)
		plus.add_theme_color_override("font_color", Color(0.22, 0.25, 0.32))
		vbox.add_child(plus)
		var invite := Label.new()
		invite.text = "邀請"
		invite.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		invite.add_theme_font_size_override("font_size", 10)
		invite.add_theme_color_override("font_color", Color(0.3, 0.5, 0.8))
		vbox.add_child(invite)

	return panel


func _make_button(text: String, bg_color: Color, sz: Vector2) -> Button:
	var btn := Button.new()
	btn.text = text
	btn.custom_minimum_size = sz
	btn.add_theme_font_size_override("font_size", 14)
	btn.add_theme_color_override("font_color", TEXT_WHITE)
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg_color
	sb.corner_radius_top_left = 4
	sb.corner_radius_top_right = 4
	sb.corner_radius_bottom_left = 4
	sb.corner_radius_bottom_right = 4
	btn.add_theme_stylebox_override("normal", sb)
	var h := sb.duplicate()
	h.bg_color = bg_color.lightened(0.08)
	btn.add_theme_stylebox_override("hover", h)
	return btn


func _open_invite_popup(slot_idx: int) -> void:
	"""打開邀請好友彈窗"""
	var popup := Control.new()
	popup.name = "InvitePopup"
	popup.set_anchors_preset(Control.PRESET_FULL_RECT)
	# 背景遮罩
	var bg := ColorRect.new()
	bg.color = Color(0, 0, 0, 0.7)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.gui_input.connect(func(e): if e is InputEventMouseButton and e.pressed: popup.queue_free())
	popup.add_child(bg)
	# 彈窗面板
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(400, 500)
	var psb := StyleBoxFlat.new()
	psb.bg_color = Color(0.08, 0.08, 0.12)
	psb.border_color = Color(0.3, 0.5, 0.8)
	psb.set_border_width_all(2)
	psb.corner_radius_top_left = 8
	psb.corner_radius_top_right = 8
	psb.corner_radius_bottom_left = 8
	psb.corner_radius_bottom_right = 8
	psb.content_margin_left = 16
	psb.content_margin_right = 16
	psb.content_margin_top = 16
	psb.content_margin_bottom = 16
	panel.add_theme_stylebox_override("panel", psb)
	popup.add_child(panel)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 12)
	panel.add_child(vbox)
	# 標題
	var title := Label.new()
	title.text = "👥 邀請好友"
	title.add_theme_font_size_override("font_size", 20)
	title.add_theme_color_override("font_color", Color.WHITE)
	vbox.add_child(title)
	var divider := HSeparator.new()
	vbox.add_child(divider)
	# 好友列表（可滾動）
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(scroll)
	var friends_list := VBoxContainer.new()
	friends_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	friends_list.add_theme_constant_override("separation", 4)
	scroll.add_child(friends_list)
	# 取得好友列表
	var social = get_node_or_null("/root/VantaGlobal/SocialSystem")
	if social == null:
		social = preload("res://scripts/social_system.gd").new()
		social.name = "SocialSystem"
		get_node("/root/VantaGlobal").add_child(social)
	# 在線好友
	var online_friends: Array = social.get_online_friends()
	if online_friends.is_empty():
		var no_friends := Label.new()
		no_friends.text = "沒有在線好友"
		no_friends.add_theme_font_size_override("font_size", 13)
		no_friends.add_theme_color_override("font_color", Color(0.5, 0.5, 0.6))
		no_friends.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		friends_list.add_child(no_friends)
	else:
		for friend in online_friends:
			var row := HBoxContainer.new()
			row.add_theme_constant_override("separation", 8)
			friends_list.add_child(row)
			# 在線狀態
			var dot := ColorRect.new()
			dot.custom_minimum_size = Vector2(8, 8)
			dot.color = Color(0.0, 1.0, 0.5)
			dot.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			row.add_child(dot)
			# 名稱
			var name_lbl := Label.new()
			name_lbl.text = friend.get("name", "Unknown")
			name_lbl.add_theme_font_size_override("font_size", 13)
			name_lbl.add_theme_color_override("font_color", Color.WHITE)
			row.add_child(name_lbl)
			# 段位
			var rank_lbl := Label.new()
			var tier: int = friend.get("rank", 0)
			rank_lbl.text = social.get_rank_name(tier)
			rank_lbl.add_theme_font_size_override("font_size", 11)
			rank_lbl.add_theme_color_override("font_color", social.get_rank_color(tier))
			row.add_child(rank_lbl)
			# 彈性空間
			var spacer := Control.new()
			spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			row.add_child(spacer)
			# 邀請按鈕
			var invite_btn := Button.new()
			invite_btn.text = "邀請"
			invite_btn.custom_minimum_size = Vector2(60, 28)
			invite_btn.add_theme_font_size_override("font_size", 12)
			invite_btn.add_theme_color_override("font_color", Color.WHITE)
			var ibtn_sb := StyleBoxFlat.new()
			ibtn_sb.bg_color = Color(0.2, 0.6, 0.4)
			ibtn_sb.corner_radius_top_left = 4
			ibtn_sb.corner_radius_top_right = 4
			ibtn_sb.corner_radius_bottom_left = 4
			ibtn_sb.corner_radius_bottom_right = 4
			invite_btn.add_theme_stylebox_override("normal", ibtn_sb)
			var ibtn_h := ibtn_sb.duplicate()
			ibtn_h.bg_color = Color(0.3, 0.8, 0.5)
			invite_btn.add_theme_stylebox_override("hover", ibtn_h)
			var friend_name: String = friend.get("name", "")
			invite_btn.pressed.connect(func(): _send_invite(friend_name, popup))
			row.add_child(invite_btn)
	# 搜尋框
	var search_hbox := HBoxContainer.new()
	search_hbox.add_theme_constant_override("separation", 8)
	vbox.add_child(search_hbox)
	var search_input := LineEdit.new()
	search_input.placeholder_text = "搜尋玩家名..."
	search_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	search_hbox.add_child(search_input)
	var search_btn := Button.new()
	search_btn.text = "搜尋"
	search_btn.custom_minimum_size = Vector2(60, 30)
	search_hbox.add_child(search_btn)
	# 關閉按鈕
	var close_btn := Button.new()
	close_btn.text = "✕ 關閉"
	close_btn.custom_minimum_size = Vector2(0, 36)
	close_btn.pressed.connect(popup.queue_free)
	vbox.add_child(close_btn)
	add_child(popup)


func _send_invite(friend_name: String, popup: Control) -> void:
	"""發送邀請並顯示通知"""
	# 顯示邀請已發送通知
	var notification := Label.new()
	notification.text = "✅ 已向「%s」發送邀請" % friend_name
	notification.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	notification.position = Vector2(get_viewport_rect().size.x * 0.5 - 150, 100)
	notification.size = Vector2(300, 40)
	notification.add_theme_font_size_override("font_size", 14)
	notification.add_theme_color_override("font_color", Color.WHITE)
	var nsb := StyleBoxFlat.new()
	nsb.bg_color = Color(0.1, 0.6, 0.4, 0.95)
	nsb.corner_radius_top_left = 6
	nsb.corner_radius_top_right = 6
	nsb.corner_radius_bottom_left = 6
	nsb.corner_radius_bottom_right = 6
	notification.add_theme_stylebox_override("panel", nsb)
	add_child(notification)
	# 2 秒後消失
	var tween := create_tween()
	tween.tween_interval(2.0)
	tween.tween_property(notification, "modulate:a", 0.0, 0.5)
	tween.tween_callback(notification.queue_free)
	# 關閉邀請彈窗
	if popup and popup.is_inside_tree():
		popup.queue_free()


# ═══════════════════════════════════════════════
#  畫面切換
# ═══════════════════════════════════════════════
func _show_view(view: View) -> void:
	_view = view
	_home_layer.visible = (view == View.HOME)
	_modes_layer.visible = (view == View.MODES)
	_party_layer.visible = (view == View.PARTY)
	_top_bar.visible = true
	if view == View.PARTY and _selected_mode >= 0:
		var lbl: Label = _party_layer.get_node_or_null("ModeName")
		if lbl:
			lbl.text = MODES[_selected_mode]["name"]
	queue_redraw()


func _enter_party() -> void:
	_show_view(View.PARTY)


# ═══════════════════════════════════════════════
#  開始遊戲
# ═══════════════════════════════════════════════
func _start_game(game_mode: String) -> void:
	# 根據模式決定伺服器端 mode 參數
	var server_mode := "competitive"
	var tag: String = str(MODES[_selected_mode]["tag"]) if _selected_mode >= 0 else game_mode
	if tag == "dm":
		server_mode = "deathmatch"
	# 訓練模式使用離線模式（無需伺服器）
	var ws_url: String
	var net_mode: String
	if game_mode == "train":
		ws_url = ""
		net_mode = "offline"
	else:
		ws_url = "wss://vanta-ws.cpxru83.workers.dev/ws?match=%s&ai=1&mode=%s" % [game_mode, server_mode]
		net_mode = "ws"
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		g.ws_url = ws_url
		g.net_mode = net_mode
		g.selected_mode = tag
	# 先進入角色選擇，確認後才開始遊戲
	get_tree().change_scene_to_file("res://agent_select.tscn")
