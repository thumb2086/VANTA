extends Control

## 設定選單 — 靈敏度 + 準心 + 音量 + 畫質

const BG_DARK := Color(0.03, 0.04, 0.07)
const ACCENT := Color(0.0, 0.85, 0.75)
const TEXT_WHITE := Color(0.94, 0.95, 0.97)
const TEXT_DIM := Color(0.50, 0.53, 0.60)
const BORDER_DIM := Color(0.22, 0.25, 0.32)

# ──── 設定值（預設值 = Valorant 預設）───
var sensitivity := 0.35        # 滑鼠靈敏度（Valorant 預設 0.35）
var ads_sensitivity := 1.0     # ADS 靈敏度倍率
var scoped_sens := 0.35        # 狙擊鏡靈敏度
# 準心
var crosshair_color := Color(0.22, 1.0, 0.08)  # 綠色（Valorant 預設）
var crosshair_size := 4.0      # 內線長度
var crosshair_gap := 4.0       # 間距
var crosshair_thickness := 2.0 # 線條粗細
var crosshair_outline := false # 外框
var crosshair_dot := true      # 中央點
var crosshair_style := 0       # 0=十字, 1=圓形, 2=點
# 音量
var master_volume := 80
var sfx_volume := 80
var music_volume := 60
# 畫質
var fov := 90
# 輔助功能
var colorblind_mode := 0       # 0=None, 1=Protanopia, 2=Deuteranopia, 3=Tritanopia
var font_size_index := 1       # 0=Small(12), 1=Medium(14), 2=Large(16)
var subtitles_on := true
var accessibility_master_vol := 1.0
var accessibility_sfx_vol := 0.8
var accessibility_bgm_vol := 0.6
var graphics_quality := 1      # 0=Low, 1=Medium, 2=High

var _preview_crosshair: Control


func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = BG_DARK
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	# 頂部
	add_child(_build_top_bar())
	# 主內容
	var main_hbox := HBoxContainer.new()
	main_hbox.position = Vector2(0, 52)
	main_hbox.size = Vector2(1280, 668)
	main_hbox.add_theme_constant_override("separation", 0)
	add_child(main_hbox)
	# 左側分類
	var left := _build_category_panel()
	main_hbox.add_child(left)
	# 中央設定區
	var center := _build_settings_panel()
	main_hbox.add_child(center)
	# 右側準心預覽
	var right := _build_preview_panel()
	main_hbox.add_child(right)


func _draw() -> void:
	# 準心預覽背景
	var preview_bg := ColorRect.new()
	preview_bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	preview_bg.color = Color(0.15, 0.17, 0.22)
	preview_bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(preview_bg)


func _build_top_bar() -> PanelContainer:
	var bar := PanelContainer.new()
	bar.set_anchors_preset(Control.PRESET_TOP_WIDE)
	bar.custom_minimum_size = Vector2(0, 50)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.02, 0.03, 0.05, 0.94)
	sb.content_margin_left = 20
	bar.add_theme_stylebox_override("panel", sb)
	var hbox := HBoxContainer.new()
	hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	hbox.add_theme_constant_override("separation", 12)
	bar.add_child(hbox)
	var back := Button.new()
	back.text = "◀ 返回"
	back.flat = true
	back.add_theme_font_size_override("font_size", 14)
	back.add_theme_color_override("font_color", TEXT_DIM)
	back.pressed.connect(func(): get_tree().change_scene_to_file("res://menu.tscn"))
	hbox.add_child(back)
	var sep := VSeparator.new()
	hbox.add_child(sep)
	var title := Label.new()
	title.text = "⚙ 設定"
	title.add_theme_font_size_override("font_size", 20)
	title.add_theme_color_override("font_color", ACCENT)
	hbox.add_child(title)
	return bar


func _build_category_panel() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(180, 0)
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.05, 0.08, 0.9)
	sb.border_color = BORDER_DIM
	sb.set_border_width_all(1)
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 16
	panel.add_theme_stylebox_override("panel", sb)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 4)
	panel.add_child(vbox)
	for cat in ["🎯 遊戲", "🔫 準心", "🔊 音量", "🖥 畫質", "♿ 輔助"]:
		var btn := Button.new()
		btn.text = cat
		btn.custom_minimum_size = Vector2(0, 36)
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.add_theme_font_size_override("font_size", 13)
		btn.add_theme_color_override("font_color", TEXT_WHITE)
		var btn_sb := StyleBoxFlat.new()
		btn_sb.bg_color = Color(0.06, 0.08, 0.12)
		btn_sb.corner_radius_top_left = 4
		btn_sb.corner_radius_top_right = 4
		btn_sb.corner_radius_bottom_left = 4
		btn_sb.corner_radius_bottom_right = 4
		btn_sb.content_margin_left = 12
		btn.add_theme_stylebox_override("normal", btn_sb)
		vbox.add_child(btn)
	return panel


func _build_settings_panel() -> ScrollContainer:
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.05, 0.06, 0.09, 0.9)
	scroll.add_theme_stylebox_override("panel", sb)
	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 20)
	scroll.add_child(content)
	# ── 遊戲設定 ──
	content.add_child(_section_header("🎯 遊戲設定"))
	content.add_child(_slider_setting("滑鼠靈敏度", 0.05, 1.0, sensitivity, func(v): sensitivity = v))
	content.add_child(_slider_setting("ADS 靈敏度倍率", 0.1, 2.0, ads_sensitivity, func(v): ads_sensitivity = v))
	content.add_child(_slider_setting("FOV", 60, 120, fov, func(v): fov = v))
	# ── 準心設定 ──
	content.add_child(_section_header("🔫 準心設定"))
	content.add_child(_color_setting("準心顏色", crosshair_color, func(c): crosshair_color = c))
	content.add_child(_slider_setting("準心大小", 1.0, 20.0, crosshair_size, func(v): crosshair_size = v))
	content.add_child(_slider_setting("準心間距", 0.0, 15.0, crosshair_gap, func(v): crosshair_gap = v))
	content.add_child(_slider_setting("準心粗細", 1.0, 6.0, crosshair_thickness, func(v): crosshair_thickness = v))
	content.add_child(_toggle_setting("準心外框", crosshair_outline, func(v): crosshair_outline = v))
	content.add_child(_toggle_setting("中央點", crosshair_dot, func(v): crosshair_dot = v))
	content.add_child(_slider_setting("準心樣式", 0, 2, crosshair_style, func(v): crosshair_style = int(v), ["十字", "圓形", "點"]))
	# ── 音量設定 ──
	content.add_child(_section_header("🔊 音量設定"))
	content.add_child(_slider_setting("主音量", 0, 100, master_volume, func(v): master_volume = int(v)))
	content.add_child(_slider_setting("音效音量", 0, 100, sfx_volume, func(v): sfx_volume = int(v)))
	content.add_child(_slider_setting("音樂音量", 0, 100, music_volume, func(v): music_volume = int(v)))
	# ── 輔助功能 ──
	content.add_child(_section_header("♿ 輔助功能"))
	content.add_child(_option_setting("色盲模式", ["無", "紅色盲", "綠色盲", "藍色盲"], colorblind_mode, func(v): colorblind_mode = v))
	content.add_child(_option_setting("字體大小", ["小 (12)", "中 (14)", "大 (16)"], font_size_index, func(v): font_size_index = v))
	content.add_child(_toggle_setting("字幕", subtitles_on, func(v): subtitles_on = v))
	content.add_child(_slider_setting("輔助主音量", 0.0, 1.0, accessibility_master_vol, func(v): accessibility_master_vol = v))
	content.add_child(_slider_setting("輔助音效音量", 0.0, 1.0, accessibility_sfx_vol, func(v): accessibility_sfx_vol = v))
	content.add_child(_slider_setting("輔助背景音樂", 0.0, 1.0, accessibility_bgm_vol, func(v): accessibility_bgm_vol = v))
	content.add_child(_option_setting("畫質", ["低", "中", "高"], graphics_quality, func(v): graphics_quality = v))
	# ── 套用按鈕 ──
	var apply_btn := Button.new()
	apply_btn.text = "💾 套用設定"
	apply_btn.custom_minimum_size = Vector2(0, 44)
	apply_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	apply_btn.add_theme_font_size_override("font_size", 16)
	apply_btn.add_theme_color_override("font_color", Color.WHITE)
	var absb := StyleBoxFlat.new()
	absb.bg_color = ACCENT
	absb.corner_radius_top_left = 4
	absb.corner_radius_top_right = 4
	absb.corner_radius_bottom_left = 4
	absb.corner_radius_bottom_right = 4
	apply_btn.add_theme_stylebox_override("normal", absb)
	apply_btn.pressed.connect(_apply_settings)
	content.add_child(apply_btn)
	return scroll


func _build_preview_panel() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(300, 0)
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.15, 0.17, 0.22)
	sb.border_color = BORDER_DIM
	sb.set_border_width_all(1)
	panel.add_theme_stylebox_override("panel", sb)
	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 8)
	panel.add_child(vbox)
	var title := Label.new()
	title.text = "準心預覽"
	title.add_theme_font_size_override("font_size", 16)
	title.add_theme_color_override("font_color", TEXT_WHITE)
	vbox.add_child(title)
	# 預覽區域
	_preview_crosshair = Control.new()
	_preview_crosshair.custom_minimum_size = Vector2(260, 260)
	_preview_crosshair.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	vbox.add_child(_preview_crosshair)
	# 當前值顯示
	var info := Label.new()
	info.name = "InfoLabel"
	info.text = "靈敏度: %.2f\nADS 倍率: %.1f\nFOV: %d" % [sensitivity, ads_sensitivity, int(fov)]
	info.add_theme_font_size_override("font_size", 12)
	info.add_theme_color_override("font_color", TEXT_DIM)
	vbox.add_child(info)
	return panel


func _section_header(text: String) -> Label:
	var lbl := Label.new()
	lbl.text = text
	lbl.add_theme_font_size_override("font_size", 16)
	lbl.add_theme_color_override("font_color", TEXT_WHITE)
	return lbl


func _slider_setting(label: String, min_val: float, max_val: float, current: float, callback: Callable, labels: Array = []) -> HBoxContainer:
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	var lbl := Label.new()
	lbl.text = label
	lbl.custom_minimum_size = Vector2(160, 0)
	lbl.add_theme_font_size_override("font_size", 13)
	lbl.add_theme_color_override("font_color", TEXT_DIM)
	hbox.add_child(lbl)
	var slider := HSlider.new()
	slider.min_value = min_val
	slider.max_value = max_val
	slider.step = 0.01 if max_val - min_val < 5 else 1.0
	slider.value = current
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.custom_minimum_size.y = 28
	slider.value_changed.connect(callback)
	hbox.add_child(slider)
	var val_lbl := Label.new()
	val_lbl.text = "%.2f" % current if max_val - min_val < 5 else str(int(current))
	val_lbl.custom_minimum_size = Vector2(50, 0)
	val_lbl.add_theme_font_size_override("font_size", 13)
	val_lbl.add_theme_color_override("font_color", TEXT_WHITE)
	slider.value_changed.connect(func(v): val_lbl.text = "%.2f" % v if max_val - min_val < 5 else str(int(v)))
	hbox.add_child(val_lbl)
	return hbox


func _color_setting(label: String, current: Color, callback: Callable) -> HBoxContainer:
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	var lbl := Label.new()
	lbl.text = label
	lbl.custom_minimum_size = Vector2(160, 0)
	lbl.add_theme_font_size_override("font_size", 13)
	lbl.add_theme_color_override("font_color", TEXT_DIM)
	hbox.add_child(lbl)
	var colors := [
		Color(0.22, 1.0, 0.08),  # 綠
		Color(1.0, 0.2, 0.2),    # 紅
		Color(0.2, 0.6, 1.0),    # 藍
		Color(1.0, 1.0, 1.0),    # 白
		Color(0.0, 0.0, 0.0),    # 黑
		Color(1.0, 0.8, 0.0),    # 黃
		Color(1.0, 0.4, 0.8),    # 粉
	]
	for col in colors:
		var btn := Button.new()
		btn.custom_minimum_size = Vector2(28, 28)
		var csb := StyleBoxFlat.new()
		csb.bg_color = col
		csb.corner_radius_top_left = 14
		csb.corner_radius_top_right = 14
		csb.corner_radius_bottom_left = 14
		csb.corner_radius_bottom_right = 14
		csb.border_color = Color.WHITE if col == current else Color(0, 0, 0, 0)
		csb.set_border_width_all(2 if col == current else 0)
		btn.add_theme_stylebox_override("normal", csb)
		btn.pressed.connect(func(): callback.call(col); _update_color_buttons(btn, colors, col))
		hbox.add_child(btn)
	return hbox


func _update_color_buttons(active: Button, all_buttons: Array, active_color: Color) -> void:
	# 簡化：重新建立顏色按鈕（需要 parent ref）
	pass


func _toggle_setting(label: String, current: bool, callback: Callable) -> HBoxContainer:
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	var lbl := Label.new()
	lbl.text = label
	lbl.custom_minimum_size = Vector2(160, 0)
	lbl.add_theme_font_size_override("font_size", 13)
	lbl.add_theme_color_override("font_color", TEXT_DIM)
	hbox.add_child(lbl)
	var btn := Button.new()
	btn.text = "ON" if current else "OFF"
	btn.custom_minimum_size = Vector2(60, 30)
	btn.add_theme_font_size_override("font_size", 12)
	btn.add_theme_color_override("font_color", Color.WHITE)
	var btn_sb := StyleBoxFlat.new()
	btn_sb.bg_color = ACCENT if current else Color(0.15, 0.15, 0.18)
	btn_sb.corner_radius_top_left = 4
	btn_sb.corner_radius_top_right = 4
	btn_sb.corner_radius_bottom_left = 4
	btn_sb.corner_radius_bottom_right = 4
	btn.add_theme_stylebox_override("normal", btn_sb)
	btn.pressed.connect(func():
		current = not current
		callback.call(current)
		btn.text = "ON" if current else "OFF"
		var new_sb := StyleBoxFlat.new()
		new_sb.bg_color = ACCENT if current else Color(0.15, 0.15, 0.18)
		new_sb.corner_radius_top_left = 4
		new_sb.corner_radius_top_right = 4
		new_sb.corner_radius_bottom_left = 4
		new_sb.corner_radius_bottom_right = 4
		btn.add_theme_stylebox_override("normal", new_sb)
	)
	hbox.add_child(btn)
	return hbox


func _option_setting(label: String, options: Array, current: int, callback: Callable) -> HBoxContainer:
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	var lbl := Label.new()
	lbl.text = label
	lbl.custom_minimum_size = Vector2(160, 0)
	lbl.add_theme_font_size_override("font_size", 13)
	lbl.add_theme_color_override("font_color", TEXT_DIM)
	hbox.add_child(lbl)
	var option_btn := OptionButton.new()
	option_btn.add_theme_font_size_override("font_size", 13)
	for opt in options:
		option_btn.add_item(opt)
	option_btn.selected = current
	option_btn.custom_minimum_size = Vector2(120, 30)
	option_btn.item_selected.connect(func(idx): callback.call(idx))
	hbox.add_child(option_btn)
	return hbox


func _apply_settings() -> void:
	# 保存到 VantaGlobal
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		g.sensitivity = sensitivity
		g.ads_sensitivity = ads_sensitivity
		g.crosshair_color = crosshair_color
		g.crosshair_size = crosshair_size
		g.crosshair_gap = crosshair_gap
		g.crosshair_thickness = crosshair_thickness
		g.crosshair_outline = crosshair_outline
		g.crosshair_dot = crosshair_dot
		g.crosshair_style = crosshair_style
		g.fov = fov
		g.colorblind_mode = colorblind_mode
		g.font_size_index = font_size_index
		g.subtitles_on = subtitles_on
		g.master_volume = accessibility_master_vol
		g.sfx_volume = accessibility_sfx_vol
		g.bgm_volume = accessibility_bgm_vol
		g.graphics_quality = graphics_quality
	# 更新 InfoLabel
	var info: Label = get_node_or_null("InfoLabel")
	if info:
		info.text = "靈敏度: %.2f\nADS 倍率: %.1f\nFOV: %d\n✅ 已套用" % [sensitivity, ads_sensitivity, int(fov)]
	queue_redraw()
