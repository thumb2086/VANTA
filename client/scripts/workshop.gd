extends Control

## 武器工坊 — Valorant 風格武器自訂介面
## 功能：顏色自訂 + 皮膚模板 + 3D 武器即時預覽 + 旋轉檢視

# ──── 色彩 ────
const BG_DARK := Color(0.03, 0.04, 0.07)
const ACCENT := Color(0.0, 0.85, 0.75)
const ACCENT_RED := Color(0.92, 0.22, 0.28)
const TEXT_WHITE := Color(0.94, 0.95, 0.97)
const TEXT_DIM := Color(0.50, 0.53, 0.60)
const TEXT_GOLD := Color(1.0, 0.82, 0.32)
const BORDER_DIM := Color(0.22, 0.25, 0.32)

# ──── 皮膚系列（Valorant 風格：每系列多把武器配色）───
const SKIN_SERIES := [
	{
		"name": "掠奪者 Reaver",
		"tier": "傳說",
		"tier_color": Color(0.8, 0.2, 1.0),
		"desc": "暗黑哥德風格，紫黑配色 + 能量流動",
		"skins": {
			0: {"primary": Color(0.12, 0.06, 0.18), "accent": Color(0.65, 0.2, 0.9)},   # Phantom
			1: {"primary": Color(0.10, 0.05, 0.16), "accent": Color(0.7, 0.15, 0.95)},  # Vandal
			2: {"primary": Color(0.14, 0.08, 0.20), "accent": Color(0.6, 0.25, 0.85)},  # Ghost
			3: {"primary": Color(0.11, 0.06, 0.17), "accent": Color(0.68, 0.18, 0.92)}, # Classic
			4: {"primary": Color(0.15, 0.10, 0.22), "accent": Color(0.55, 0.3, 0.8)},   # Knife
		}
	},
	{
		"name": "貴族 Prime",
		"tier": "傳說",
		"tier_color": Color(1.0, 0.85, 0.2),
		"desc": "皇室奢華風格，黑金配色 + 能量核心",
		"skins": {
			0: {"primary": Color(0.15, 0.13, 0.08), "accent": Color(1.0, 0.82, 0.15)},
			1: {"primary": Color(0.12, 0.10, 0.06), "accent": Color(1.0, 0.88, 0.2)},
			2: {"primary": Color(0.18, 0.15, 0.10), "accent": Color(0.95, 0.8, 0.12)},
			3: {"primary": Color(0.14, 0.12, 0.07), "accent": Color(1.0, 0.85, 0.18)},
			4: {"primary": Color(0.16, 0.14, 0.09), "accent": Color(0.98, 0.84, 0.16)}
		}
	},
	{
		"name": "光之哨兵 Sentinels",
		"tier": "傳說",
		"tier_color": Color(0.3, 0.8, 1.0),
		"desc": "神聖光輝風格，白藍配色 + 光環特效",
		"skins": {
			0: {"primary": Color(0.85, 0.88, 0.92), "accent": Color(0.2, 0.6, 1.0)},
			1: {"primary": Color(0.82, 0.85, 0.90), "accent": Color(0.25, 0.55, 0.95)},
			2: {"primary": Color(0.88, 0.90, 0.94), "accent": Color(0.15, 0.65, 1.0)},
			3: {"primary": Color(0.84, 0.87, 0.91), "accent": Color(0.22, 0.58, 0.98)},
			4: {"primary": Color(0.86, 0.89, 0.93), "accent": Color(0.18, 0.62, 1.0)}
		}
	},
	{
		"name": "龍炎 Dragontail",
		"tier": "精英",
		"tier_color": Color(1.0, 0.5, 0.1),
		"desc": "東方龍族風格，紅金配色 + 鱗片紋理",
		"skins": {
			0: {"primary": Color(0.45, 0.08, 0.06), "accent": Color(1.0, 0.75, 0.15)},
			1: {"primary": Color(0.42, 0.06, 0.05), "accent": Color(1.0, 0.78, 0.18)},
			2: {"primary": Color(0.48, 0.10, 0.08), "accent": Color(0.95, 0.72, 0.12)},
			3: {"primary": Color(0.44, 0.07, 0.06), "accent": Color(1.0, 0.76, 0.16)},
			4: {"primary": Color(0.46, 0.09, 0.07), "accent": Color(0.98, 0.74, 0.14)}
		}
	},
	{
		"name": "暗影之刃 Elderflame",
		"tier": "傳說",
		"tier_color": Color(0.9, 0.3, 0.15),
		"desc": "活體火焰風格，暗紅 + 橙焰 + 呼吸動畫",
		"skins": {
			0: {"primary": Color(0.18, 0.04, 0.03), "accent": Color(1.0, 0.45, 0.1)},
			1: {"primary": Color(0.16, 0.03, 0.02), "accent": Color(1.0, 0.48, 0.12)},
			2: {"primary": Color(0.20, 0.05, 0.04), "accent": Color(0.95, 0.42, 0.08)},
			3: {"primary": Color(0.17, 0.04, 0.03), "accent": Color(1.0, 0.46, 0.11)},
			4: {"primary": Color(0.19, 0.045, 0.035), "accent": Color(0.98, 0.44, 0.09)}
		}
	},
	{
		"name": "源計畫 Glitchpop",
		"tier": "傳說",
		"tier_color": Color(0.0, 0.95, 0.8),
		"desc": "賽博龐克風格，霓虹青 + 品紅 + 故障特效",
		"skins": {
			0: {"primary": Color(0.04, 0.12, 0.20), "accent": Color(0.0, 0.95, 0.85)},
			1: {"primary": Color(0.03, 0.10, 0.18), "accent": Color(0.0, 0.98, 0.88)},
			2: {"primary": Color(0.05, 0.14, 0.22), "accent": Color(0.0, 0.92, 0.82)},
			3: {"primary": Color(0.04, 0.11, 0.19), "accent": Color(0.0, 0.96, 0.86)},
			4: {"primary": Color(0.045, 0.13, 0.21), "accent": Color(0.0, 0.94, 0.84)}
		}
	},
	{
		"name": "冰霜幻影 Winterwunder",
		"tier": "精英",
		"tier_color": Color(0.5, 0.8, 1.0),
		"desc": "冰雪奇緣風格，冰藍 + 白霜 + 結晶特效",
		"skins": {
			0: {"primary": Color(0.75, 0.85, 0.92), "accent": Color(0.3, 0.65, 1.0)},
			1: {"primary": Color(0.72, 0.82, 0.90), "accent": Color(0.35, 0.6, 0.95)},
			2: {"primary": Color(0.78, 0.88, 0.94), "accent": Color(0.25, 0.7, 1.0)},
			3: {"primary": Color(0.74, 0.84, 0.91), "accent": Color(0.32, 0.62, 0.98)},
			4: {"primary": Color(0.76, 0.86, 0.93), "accent": Color(0.28, 0.68, 1.0)}
		}
	},
	{
		"name": "毒素之牙 Viper's Bite",
		"tier": "精英",
		"tier_color": Color(0.2, 0.9, 0.35),
		"desc": "生化毒蛇風格，深綠 + 亮綠毒液 + 蝕刻",
		"skins": {
			0: {"primary": Color(0.06, 0.18, 0.08), "accent": Color(0.2, 0.92, 0.38)},
			1: {"primary": Color(0.05, 0.16, 0.07), "accent": Color(0.22, 0.95, 0.4)},
			2: {"primary": Color(0.07, 0.20, 0.09), "accent": Color(0.18, 0.9, 0.36)},
			3: {"primary": Color(0.06, 0.17, 0.08), "accent": Color(0.21, 0.93, 0.39)},
			4: {"primary": Color(0.065, 0.19, 0.085), "accent": Color(0.19, 0.91, 0.37)}
		}
	},
	{
		"name": "星塵 Nova",
		"tier": "稀有",
		"tier_color": Color(0.4, 0.5, 1.0),
		"desc": "宇宙星塵風格，深紫 + 藍星 + 光點特效",
		"skins": {
			0: {"primary": Color(0.10, 0.08, 0.22), "accent": Color(0.4, 0.5, 1.0)},
			1: {"primary": Color(0.09, 0.07, 0.20), "accent": Color(0.42, 0.52, 1.0)},
			2: {"primary": Color(0.11, 0.09, 0.24), "accent": Color(0.38, 0.48, 0.95)},
			3: {"primary": Color(0.10, 0.08, 0.21), "accent": Color(0.41, 0.51, 1.0)},
			4: {"primary": Color(0.105, 0.085, 0.23), "accent": Color(0.39, 0.49, 0.98)}
		}
	},
	{
		"name": "日蝕 Eclipse",
		"tier": "稀有",
		"tier_color": Color(0.9, 0.6, 0.1),
		"desc": "日蝕風格，黑金 + 暗紅蝕光",
		"skins": {
			0: {"primary": Color(0.12, 0.10, 0.06), "accent": Color(0.9, 0.55, 0.1)},
			1: {"primary": Color(0.10, 0.08, 0.05), "accent": Color(0.92, 0.58, 0.12)},
			2: {"primary": Color(0.14, 0.12, 0.07), "accent": Color(0.88, 0.52, 0.08)},
			3: {"primary": Color(0.11, 0.09, 0.055), "accent": Color(0.91, 0.56, 0.11)},
			4: {"primary": Color(0.13, 0.11, 0.065), "accent": Color(0.89, 0.54, 0.09)}
		}
	},
	{
		"name": "暴走 Punk",
		"tier": "稀有",
		"tier_color": Color(1.0, 0.3, 0.5),
		"desc": "龐克搖滾風格，粉紅 + 黑 + 鋸齒",
		"skins": {
			0: {"primary": Color(0.15, 0.08, 0.12), "accent": Color(1.0, 0.3, 0.55)},
			1: {"primary": Color(0.13, 0.07, 0.10), "accent": Color(1.0, 0.32, 0.58)},
			2: {"primary": Color(0.17, 0.09, 0.14), "accent": Color(0.95, 0.28, 0.52)},
			3: {"primary": Color(0.14, 0.08, 0.11), "accent": Color(1.0, 0.31, 0.56)},
			4: {"primary": Color(0.16, 0.085, 0.13), "accent": Color(0.98, 0.29, 0.54)}
		}
	},
	{
		"name": "軍規 military",
		"tier": "標準",
		"tier_color": Color(0.5, 0.55, 0.4),
		"desc": "軍事風格，橄欖綠 + 沙色 + 磨損",
		"skins": {
			0: {"primary": Color(0.25, 0.28, 0.18), "accent": Color(0.55, 0.52, 0.35)},
			1: {"primary": Color(0.23, 0.26, 0.16), "accent": Color(0.58, 0.55, 0.38)},
			2: {"primary": Color(0.27, 0.30, 0.20), "accent": Color(0.52, 0.50, 0.32)},
			3: {"primary": Color(0.24, 0.27, 0.17), "accent": Color(0.56, 0.53, 0.36)},
			4: {"primary": Color(0.26, 0.29, 0.19), "accent": Color(0.54, 0.51, 0.34)}
		}
	},
]

# ──── 簡易色板（快速切換用）───
const SKINS := [
	{"name": "原始本色", "primary": Color(0.25, 0.27, 0.32), "accent": Color(0.85, 0.4, 0.25)},
	{"name": "霓虹脈衝", "primary": Color(0.05, 0.15, 0.25), "accent": Color(0.0, 0.95, 0.85)},
	{"name": "烈焰之怒", "primary": Color(0.35, 0.08, 0.05), "accent": Color(1.0, 0.4, 0.1)},
	{"name": "冰霜之心", "primary": Color(0.15, 0.25, 0.40), "accent": Color(0.6, 0.85, 1.0)},
	{"name": "暗影獵手", "primary": Color(0.08, 0.06, 0.12), "accent": Color(0.55, 0.2, 0.7)},
	{"name": "黃金傳說", "primary": Color(0.35, 0.28, 0.08), "accent": Color(1.0, 0.85, 0.2)},
	{"name": "翠綠毒蛇", "primary": Color(0.06, 0.20, 0.10), "accent": Color(0.2, 0.9, 0.35)},
	{"name": "深紅血月", "primary": Color(0.30, 0.04, 0.06), "accent": Color(0.95, 0.15, 0.25)},
	{"name": "星際迷航", "primary": Color(0.10, 0.08, 0.22), "accent": Color(0.4, 0.5, 1.0)},
	{"name": "日落金沙", "primary": Color(0.40, 0.22, 0.08), "accent": Color(1.0, 0.7, 0.3)},
]

# ──── 武器資料 ────
const WEAPONS := [
	{"name": "幻象 Phantom", "slot": 0, "desc": "全自動步槍 · 高射速 · 低後座力"},
	{"name": "暴徒 Vandal", "slot": 0, "desc": "全自動步槍 · 高傷害 · 高後座力"},
	{"name": "鬼魅 Ghost", "slot": 1, "desc": "消音手槍 · 精準 · 低傷害"},
	{"name": "經典 Classic", "slot": 1, "desc": "標準手槍 · 全自動爆發"},
	{"name": "匕首", "slot": 2, "desc": "近戰武器 · 挥砍"},
]

# ──── 狀態 ────
var _current_skin := 0
var _current_weapon := 0
var _primary_color := Color(0.25, 0.27, 0.32)
var _accent_color := Color(0.85, 0.4, 0.25)
var _customizing_primary := true  # true=主色, false=強調色
var _rotate_y := 0.0
var _rotate_speed := 0.3
var _auto_rotate := true
var _anim_t := 0.0

# 皮膚進度系統（解鎖/購買/裝備 + 持久化）
var _prog: SkinProgression

# 3D 預覽
var _sub_viewport: SubViewport
var _weapon_model: WeaponViewModel
var _preview_camera: Camera3D

# UI 引用
var _primary_panel: PanelContainer
var _accent_panel: PanelContainer
var _primary_slider: HSlider
var _accent_slider: HSlider
var _skin_grid: GridContainer
var _store_box: VBoxContainer
var _preview_label: Label
var _skin_name_lbl: Label

# 進度面板引用
var _lvl_lbl: Label
var _xp_lbl: Label
var _vp_lbl: Label
var _rad_lbl: Label
var _unlock_lbl: Label

const SAVE_PATH := "user://workshop_palette.json"


func _ready() -> void:
	# 皮膚進度（持久化解鎖/購買/裝備）
	_prog = SkinProgression.new()
	add_child(_prog)
	_load_palette()
	# 背景
	var bg := ColorRect.new()
	bg.color = BG_DARK
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	# 主佈局
	var main_hbox := HBoxContainer.new()
	main_hbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	main_hbox.add_theme_constant_override("separation", 0)
	add_child(main_hbox)
	# 左側：武器選擇
	var left_panel := _build_left_panel()
	main_hbox.add_child(left_panel)
	# 中央：3D 預覽
	var center_panel := _build_center_preview()
	main_hbox.add_child(center_panel)
	# 右側：皮膚/顏色
	var right_panel := _build_right_panel()
	main_hbox.add_child(right_panel)
	# 頂部標題
	var top_bar := _build_top_bar()
	add_child(top_bar)


func _process(delta: float) -> void:
	_anim_t += delta
	# 自動旋轉
	if _auto_rotate:
		_rotate_y += delta * _rotate_speed
	if _weapon_model:
		_weapon_model.rotation.y = _rotate_y
		_weapon_model.update(delta, 0.0, true, Vector2.ZERO)


# ═══════════════════════════════════════════════
#  頂部導航
# ═══════════════════════════════════════════════
func _build_top_bar() -> PanelContainer:
	var bar := PanelContainer.new()
	bar.set_anchors_preset(Control.PRESET_TOP_WIDE)
	bar.custom_minimum_size = Vector2(0, 48)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.02, 0.03, 0.05, 0.94)
	sb.content_margin_left = 20
	sb.content_margin_right = 20
	bar.add_theme_stylebox_override("panel", sb)
	var hbox := HBoxContainer.new()
	hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	hbox.add_theme_constant_override("separation", 12)
	bar.add_child(hbox)
	# 返回按鈕
	var back_btn := Button.new()
	back_btn.text = "◀ 返回"
	back_btn.flat = true
	back_btn.custom_minimum_size = Vector2(80, 36)
	back_btn.add_theme_font_size_override("font_size", 14)
	back_btn.add_theme_color_override("font_color", TEXT_DIM)
	back_btn.pressed.connect(_go_back)
	hbox.add_child(back_btn)
	# 分隔
	var sep := VSeparator.new()
	sep.custom_minimum_size.x = 2
	hbox.add_child(sep)
	# 標題
	var title := Label.new()
	title.text = "🔫 武器工坊"
	title.add_theme_font_size_override("font_size", 20)
	title.add_theme_color_override("font_color", TEXT_GOLD)
	hbox.add_child(title)
	# 彈性空間
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(spacer)
	# 當前武器名
	var weapon_name := Label.new()
	weapon_name.name = "WeaponName"
	weapon_name.text = WEAPONS[0]["name"]
	weapon_name.add_theme_font_size_override("font_size", 14)
	weapon_name.add_theme_color_override("font_color", TEXT_WHITE)
	hbox.add_child(weapon_name)
	# 自動旋轉開關
	var rotate_btn := Button.new()
	rotate_btn.text = "🔄 自動旋轉"
	rotate_btn.flat = true
	rotate_btn.custom_minimum_size = Vector2(100, 36)
	rotate_btn.add_theme_font_size_override("font_size", 12)
	rotate_btn.add_theme_color_override("font_color", TEXT_DIM)
	rotate_btn.pressed.connect(func(): _auto_rotate = !_auto_rotate)
	hbox.add_child(rotate_btn)
	return bar


# ═══════════════════════════════════════════════
#  左側：武器選擇
# ═══════════════════════════════════════════════
func _build_left_panel() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(240, 0)
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.05, 0.08, 0.9)
	sb.border_color = BORDER_DIM
	sb.set_border_width_all(1)
	sb.content_margin_left = 16
	sb.content_margin_right = 16
	sb.content_margin_top = 60
	sb.content_margin_bottom = 16
	panel.add_theme_stylebox_override("panel", sb)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 6)
	panel.add_child(vbox)
	# 標題
	var lbl := Label.new()
	lbl.text = "選擇武器"
	lbl.add_theme_font_size_override("font_size", 16)
	lbl.add_theme_color_override("font_color", TEXT_WHITE)
	vbox.add_child(lbl)
	var divider := HSeparator.new()
	vbox.add_child(divider)
	# 武器列表
	for i in range(WEAPONS.size()):
		var weapon: Dictionary = WEAPONS[i]
		var btn := Button.new()
		btn.text = weapon["name"]
		btn.custom_minimum_size = Vector2(0, 44)
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.add_theme_font_size_override("font_size", 13)
		btn.add_theme_color_override("font_color", TEXT_WHITE)
		var btn_sb := StyleBoxFlat.new()
		btn_sb.bg_color = Color(0.06, 0.08, 0.12) if i != _current_skin else Color(0.10, 0.15, 0.22)
		btn_sb.corner_radius_top_left = 4
		btn_sb.corner_radius_top_right = 4
		btn_sb.corner_radius_bottom_left = 4
		btn_sb.corner_radius_bottom_right = 4
		btn_sb.content_margin_left = 12
		btn_sb.content_margin_right = 12
		btn.add_theme_stylebox_override("normal", btn_sb)
		var btn_h := btn_sb.duplicate()
		btn_h.bg_color = Color(0.10, 0.14, 0.20)
		btn.add_theme_stylebox_override("hover", btn_h)
		var btn_p := btn_sb.duplicate()
		btn_p.bg_color = Color(0.08, 0.20, 0.28)
		btn_p.border_color = ACCENT
		btn_p.set_border_width_all(1)
		btn.add_theme_stylebox_override("pressed", btn_p)
		btn.pressed.connect(_on_weapon_select.bind(i))
		vbox.add_child(btn)
		# 描述
		var desc := Label.new()
		desc.text = "  " + weapon["desc"]
		desc.add_theme_font_size_override("font_size", 10)
		desc.add_theme_color_override("font_color", TEXT_DIM)
		vbox.add_child(desc)
	return panel


# ═══════════════════════════════════════════════
#  中央：3D 武器預覽
# ═══════════════════════════════════════════════
func _build_center_preview() -> Control:
	var container := Control.new()
	container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	container.size_flags_vertical = Control.SIZE_EXPAND_FILL
	# SubViewport 用來渲染 3D 武器
	_sub_viewport = SubViewport.new()
	_sub_viewport.size = Vector2i(600, 500)
	_sub_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_sub_viewport.transparent_bg = false
	_sub_viewport.handle_input_locally = true
	_sub_viewport.gui_disable_input = true
	_sub_viewport.msaa_3d = SubViewport.MSAA_4X
	# 深色背景環境
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.06, 0.07, 0.10)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.15, 0.17, 0.22)
	env.ambient_light_energy = 0.5
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	_sub_viewport.add_child(world_env)
	# 攝影機
	_preview_camera = Camera3D.new()
	_preview_camera.position = Vector3(0.0, 0.05, 0.6)
	_preview_camera.fov = 40.0
	_sub_viewport.add_child(_preview_camera)
	# 燈光
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-30, 30, 0)
	light.light_energy = 1.5
	light.light_color = Color(1.0, 0.98, 0.95)
	_sub_viewport.add_child(light)
	var ambient := DirectionalLight3D.new()
	ambient.rotation_degrees = Vector3(30, -150, 0)
	ambient.light_energy = 0.6
	ambient.light_color = Color(0.7, 0.75, 0.85)
	_sub_viewport.add_child(ambient)
	# 武器模型
	_weapon_model = WeaponViewModel.new()
	_weapon_model.position = Vector3(0.0, -0.05, 0.0)
	_sub_viewport.add_child(_weapon_model)
	# 用當前配色構建武器
	_rebuild_weapon()
	# 繪製預覽背景（深色面板 + 幾何裝飾）
	var preview_bg := ColorRect.new()
	preview_bg.color = Color(0.06, 0.07, 0.10)
	preview_bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	preview_bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	container.add_child(preview_bg)
	# SubViewportContainer 顯示
	var vp_container := SubViewportContainer.new()
	vp_container.stretch = true
	vp_container.set_anchors_preset(Control.PRESET_FULL_RECT)
	vp_container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vp_container.add_child(_sub_viewport)
	container.add_child(vp_container)
	# 預覽標籤
	_preview_label = Label.new()
	_preview_label.text = "拖曳旋轉 · 滾輪縮放"
	_preview_label.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	_preview_label.position.y = -30
	_preview_label.size.y = 24
	_preview_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_preview_label.add_theme_font_size_override("font_size", 11)
	_preview_label.add_theme_color_override("font_color", TEXT_DIM)
	container.add_child(_preview_label)
	# 皮膚名稱
	_skin_name_lbl = Label.new()
	_skin_name_lbl.name = "SkinName"
	_skin_name_lbl.text = _skin_label_text()
	_skin_name_lbl.position = Vector2(20, 60)
	_skin_name_lbl.add_theme_font_size_override("font_size", 18)
	_skin_name_lbl.add_theme_color_override("font_color", TEXT_GOLD)
	container.add_child(_skin_name_lbl)
	# ── 試射按鈕 ──
	var fire_btn := Button.new()
	fire_btn.text = "🔫 試射"
	fire_btn.custom_minimum_size = Vector2(100, 40)
	fire_btn.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	fire_btn.position = Vector2(-120, -70)
	fire_btn.add_theme_font_size_override("font_size", 14)
	fire_btn.add_theme_color_override("font_color", Color.WHITE)
	var fbsb := StyleBoxFlat.new()
	fbsb.bg_color = Color(0.85, 0.2, 0.2, 0.9)
	fbsb.corner_radius_top_left = 6
	fbsb.corner_radius_top_right = 6
	fbsb.corner_radius_bottom_left = 6
	fbsb.corner_radius_bottom_right = 6
	fire_btn.add_theme_stylebox_override("normal", fbsb)
	var fbsb_h := fbsb.duplicate()
	fbsb_h.bg_color = Color(0.95, 0.3, 0.3)
	fire_btn.add_theme_stylebox_override("hover", fbsb_h)
	fire_btn.pressed.connect(_on_test_fire)
	container.add_child(fire_btn)
	# ── 擊殺特效預覽按鈕 ──
	var kfx_btn := Button.new()
	kfx_btn.text = "💀 擊殺特效"
	kfx_btn.custom_minimum_size = Vector2(100, 40)
	kfx_btn.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	kfx_btn.position = Vector2(-120, -25)
	kfx_btn.add_theme_font_size_override("font_size", 14)
	kfx_btn.add_theme_color_override("font_color", Color.WHITE)
	var kbsb := StyleBoxFlat.new()
	kbsb.bg_color = Color(0.15, 0.6, 0.85, 0.9)
	kbsb.corner_radius_top_left = 6
	kbsb.corner_radius_top_right = 6
	kbsb.corner_radius_bottom_left = 6
	kbsb.corner_radius_bottom_right = 6
	kfx_btn.add_theme_stylebox_override("normal", kbsb)
	var kbsb_h := kbsb.duplicate()
	kbsb_h.bg_color = Color(0.2, 0.7, 0.95)
	kfx_btn.add_theme_stylebox_override("hover", kbsb_h)
	kfx_btn.pressed.connect(_on_preview_kill_effect)
	container.add_child(kfx_btn)
	return container


# ═══════════════════════════════════════════════
#  右側：皮膚 + 顏色選擇
# ═══════════════════════════════════════════════
func _build_right_panel() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(280, 0)
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.05, 0.08, 0.9)
	sb.border_color = BORDER_DIM
	sb.set_border_width_all(1)
	sb.content_margin_left = 16
	sb.content_margin_right = 16
	sb.content_margin_top = 60
	sb.content_margin_bottom = 16
	panel.add_theme_stylebox_override("panel", sb)
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.add_child(scroll)
	var vbox := VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 12)
	scroll.add_child(vbox)
	# ── 進度面板 ──
	var prog_panel := _build_progress_panel()
	vbox.add_child(prog_panel)
	# ── 皮膚系列 ──
	var series_title := Label.new()
	series_title.text = "🎭 皮膚系列"
	series_title.add_theme_font_size_override("font_size", 16)
	series_title.add_theme_color_override("font_color", TEXT_WHITE)
	vbox.add_child(series_title)
	# 系列列表（垂直滾動）
	for i in range(SKIN_SERIES.size()):
		var series: Dictionary = SKIN_SERIES[i]
		var card := _build_series_card(i, series)
		vbox.add_child(card)
	# ── 分隔 ──
	var div0 := HSeparator.new()
	vbox.add_child(div0)
	# ── 快速色板 ──
	var skin_title := Label.new()
	skin_title.text = "🎨 快速色板"
	skin_title.add_theme_font_size_override("font_size", 14)
	skin_title.add_theme_color_override("font_color", TEXT_DIM)
	vbox.add_child(skin_title)
	# 皮膚網格（2 列）
	_skin_grid = GridContainer.new()
	_skin_grid.columns = 2
	_skin_grid.add_theme_constant_override("h_separation", 6)
	_skin_grid.add_theme_constant_override("v_separation", 6)
	vbox.add_child(_skin_grid)
	_build_skin_grid()
	# ── 分隔 ──
	var div1 := HSeparator.new()
	vbox.add_child(div1)
	# ── 皮膚商店 ──
	var store_title := Label.new()
	store_title.text = "🛒 皮膚商店"
	store_title.add_theme_font_size_override("font_size", 16)
	store_title.add_theme_color_override("font_color", TEXT_WHITE)
	vbox.add_child(store_title)
	var store_desc := Label.new()
	store_desc.text = "每日輪替，用 VP 購買皮膚"
	store_desc.add_theme_font_size_override("font_size", 11)
	store_desc.add_theme_color_override("font_color", TEXT_DIM)
	vbox.add_child(store_desc)
	var store_box := VBoxContainer.new()
	store_box.add_theme_constant_override("separation", 8)
	vbox.add_child(store_box)
	_build_store_cards(store_box)
	# ── 分隔 ──
	var div1b := HSeparator.new()
	vbox.add_child(div1b)
	# ── 自訂顏色 ──
	var color_title := Label.new()
	color_title.text = "🖌 自訂顏色"
	color_title.add_theme_font_size_override("font_size", 16)
	color_title.add_theme_color_override("font_color", TEXT_WHITE)
	vbox.add_child(color_title)
	# 主色選擇器
	var primary_hbox := HBoxContainer.new()
	primary_hbox.add_theme_constant_override("separation", 12)
	vbox.add_child(primary_hbox)
	var p_label := Label.new()
	p_label.text = "主色"
	p_label.add_theme_font_size_override("font_size", 13)
	p_label.add_theme_color_override("font_color", TEXT_DIM)
	p_label.custom_minimum_size.y = 36
	p_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	primary_hbox.add_child(p_label)
	_primary_panel = PanelContainer.new()
	_primary_panel.custom_minimum_size = Vector2(36, 36)
	_primary_panel.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var psb := StyleBoxFlat.new()
	psb.bg_color = _primary_color
	psb.corner_radius_top_left = 4
	psb.corner_radius_top_right = 4
	psb.corner_radius_bottom_left = 4
	psb.corner_radius_bottom_right = 4
	psb.border_color = BORDER_DIM
	psb.set_border_width_all(1)
	_primary_panel.add_theme_stylebox_override("panel", psb)
	_primary_panel.gui_input.connect(_on_primary_color_input)
	primary_hbox.add_child(_primary_panel)
	# 主色滑桿（Hue）
	_primary_slider = HSlider.new()
	_primary_slider.min_value = 0.0
	_primary_slider.max_value = 1.0
	_primary_slider.value = _primary_color.h
	_primary_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_primary_slider.custom_minimum_size.y = 36
	_primary_slider.value_changed.connect(func(v): _primary_color.h = v; _primary_color.s = 0.7; _primary_color.v = 0.5; _on_color_change())
	primary_hbox.add_child(_primary_slider)
	# 強調色選擇器
	var accent_hbox := HBoxContainer.new()
	accent_hbox.add_theme_constant_override("separation", 12)
	vbox.add_child(accent_hbox)
	var a_label := Label.new()
	a_label.text = "強調"
	a_label.add_theme_font_size_override("font_size", 13)
	a_label.add_theme_color_override("font_color", TEXT_DIM)
	a_label.custom_minimum_size.y = 36
	a_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	accent_hbox.add_child(a_label)
	_accent_panel = PanelContainer.new()
	_accent_panel.custom_minimum_size = Vector2(36, 36)
	_accent_panel.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var asb := StyleBoxFlat.new()
	asb.bg_color = _accent_color
	asb.corner_radius_top_left = 4
	asb.corner_radius_top_right = 4
	asb.corner_radius_bottom_left = 4
	asb.corner_radius_bottom_right = 4
	asb.border_color = BORDER_DIM
	asb.set_border_width_all(1)
	_accent_panel.add_theme_stylebox_override("panel", asb)
	_accent_panel.gui_input.connect(_on_accent_color_input)
	accent_hbox.add_child(_accent_panel)
	# 強調色滑桿（Hue）
	_accent_slider = HSlider.new()
	_accent_slider.min_value = 0.0
	_accent_slider.max_value = 1.0
	_accent_slider.value = _accent_color.h
	_accent_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_accent_slider.custom_minimum_size.y = 36
	_accent_slider.value_changed.connect(func(v): _accent_color.h = v; _accent_color.s = 0.85; _accent_color.v = 0.9; _on_color_change())
	accent_hbox.add_child(_accent_slider)
	# ── 分隔 ──
	var div2 := HSeparator.new()
	vbox.add_child(div2)
	# ── 擊殺特效設定 ──
	_build_kill_effect_panel(vbox)
	# ── 分隔 ──
	var div3 := HSeparator.new()
	vbox.add_child(div3)
	# ── 保存按鈕 ──
	var save_btn := Button.new()
	save_btn.text = "💾 保存配色"
	save_btn.custom_minimum_size = Vector2(0, 44)
	save_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	save_btn.add_theme_font_size_override("font_size", 14)
	save_btn.add_theme_color_override("font_color", Color.WHITE)
	var save_sb := StyleBoxFlat.new()
	save_sb.bg_color = ACCENT
	save_sb.corner_radius_top_left = 4
	save_sb.corner_radius_top_right = 4
	save_sb.corner_radius_bottom_left = 4
	save_sb.corner_radius_bottom_right = 4
	save_btn.add_theme_stylebox_override("normal", save_sb)
	var save_h := save_sb.duplicate()
	save_h.bg_color = Color(0.0, 0.95, 0.85)
	save_btn.add_theme_stylebox_override("hover", save_h)
	save_btn.pressed.connect(_save_palette)
	vbox.add_child(save_btn)
	return panel


# ═══════════════════════════════════════════════
#  皮膚系列卡片
# ═══════════════════════════════════════════════
var _current_series := -1

func _build_series_card(idx: int, series: Dictionary) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(0, 72)
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	# 用系列第一把武器的配色做背景
	var first_skin: Dictionary = series["skins"].get(0, {})
	var bg_col: Color = first_skin.get("primary", Color(0.1, 0.1, 0.15))
	var accent_col: Color = first_skin.get("accent", Color(0.5, 0.5, 0.5))
	sb.bg_color = Color(bg_col.r, bg_col.g, bg_col.b, 0.7)
	sb.border_color = series["tier_color"]
	sb.set_border_width_all(3)
	sb.set_border_width_all(1)
	sb.set_border_width_all(1)
	sb.set_border_width_all(1)
	sb.corner_radius_top_left = 4
	sb.corner_radius_top_right = 4
	sb.corner_radius_bottom_left = 4
	sb.corner_radius_bottom_right = 4
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 8
	sb.content_margin_bottom = 8
	panel.add_theme_stylebox_override("panel", sb)
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 10)
	panel.add_child(hbox)
	# 強調色色塊
	var color_block := ColorRect.new()
	color_block.color = accent_col
	color_block.custom_minimum_size = Vector2(8, 48)
	color_block.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	hbox.add_child(color_block)
	# 資訊 VBox
	var info := VBoxContainer.new()
	info.add_theme_constant_override("separation", 2)
	info.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	hbox.add_child(info)
	# 系列名 + 等級
	var name_row := HBoxContainer.new()
	name_row.add_theme_constant_override("separation", 8)
	info.add_child(name_row)
	var name_lbl := Label.new()
	name_lbl.text = series["name"]
	name_lbl.add_theme_font_size_override("font_size", 14)
	name_lbl.add_theme_color_override("font_color", TEXT_WHITE)
	name_row.add_child(name_lbl)
	var tier_lbl := Label.new()
	tier_lbl.text = series["tier"]
	tier_lbl.add_theme_font_size_override("font_size", 10)
	tier_lbl.add_theme_color_override("font_color", series["tier_color"])
	name_row.add_child(tier_lbl)
	# 描述
	var desc_lbl := Label.new()
	desc_lbl.text = series["desc"]
	desc_lbl.add_theme_font_size_override("font_size", 10)
	desc_lbl.add_theme_color_override("font_color", TEXT_DIM)
	info.add_child(desc_lbl)
	# 彈性空間
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(spacer)
	# 套用按鈕
	var apply_btn := Button.new()
	apply_btn.text = "套用"
	apply_btn.custom_minimum_size = Vector2(50, 30)
	apply_btn.add_theme_font_size_override("font_size", 11)
	apply_btn.add_theme_color_override("font_color", Color.WHITE)
	var absb := StyleBoxFlat.new()
	absb.bg_color = series["tier_color"].darkened(0.3)
	absb.corner_radius_top_left = 3
	absb.corner_radius_top_right = 3
	absb.corner_radius_bottom_left = 3
	absb.corner_radius_bottom_right = 3
	apply_btn.add_theme_stylebox_override("normal", absb)
	var abh := absb.duplicate()
	abh.bg_color = series["tier_color"]
	apply_btn.add_theme_stylebox_override("hover", abh)
	apply_btn.pressed.connect(_on_series_select.bind(idx))
	apply_btn.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	hbox.add_child(apply_btn)
	return panel


func _on_series_select(idx: int) -> void:
	_current_series = idx
	var series: Dictionary = SKIN_SERIES[idx]
	# 取得當前武器的配色
	var skin: Dictionary = series["skins"].get(_current_weapon, {})
	if skin.is_empty():
		# fallback 到第一把武器
		skin = series["skins"].values()[0]
	_primary_color = skin.get("primary", Color(0.2, 0.2, 0.25))
	_accent_color = skin.get("accent", Color(0.8, 0.4, 0.2))
	_current_skin = -1  # 標記為系列模式
	# 若此系列 + 此武器有已解鎖皮膚 → 記錄裝備
	var skin_id := _find_catalog_skin(idx, _current_weapon)
	if skin_id != "":
		_prog.equip_skin(_current_weapon, skin_id)
		_show_toast("✅ 已套用「%s」系列" % series["name"])
	else:
		_show_toast("⚠ 已套用配色（此系列未解鎖皮膚，可在商店購買）")
	_rebuild_weapon()
	_build_skin_grid()
	_update_color_panels()
	_update_sliders()
	_refresh_skin_name()
	_refresh_progress()
	_refresh_store()


func _build_skin_grid() -> void:
	_skin_grid.get_children().map(func(c): c.queue_free())
	for i in range(SKINS.size()):
		var skin: Dictionary = SKINS[i]
		var btn := Button.new()
		btn.text = skin["name"]
		btn.custom_minimum_size = Vector2(120, 50)
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		btn.add_theme_font_size_override("font_size", 12)
		btn.add_theme_color_override("font_color", TEXT_WHITE)
		# 漸層背景
		var btn_sb := StyleBoxFlat.new()
		btn_sb.bg_color = skin["primary"]
		btn_sb.border_color = skin["accent"] if i == _current_skin else Color(0, 0, 0, 0)
		btn_sb.set_border_width_all(2 if i == _current_skin else 0)
		btn_sb.corner_radius_top_left = 4
		btn_sb.corner_radius_top_right = 4
		btn_sb.corner_radius_bottom_left = 4
		btn_sb.corner_radius_bottom_right = 4
		btn_sb.content_margin_left = 8
		btn_sb.content_margin_right = 8
		btn_sb.content_margin_top = 6
		btn_sb.content_margin_bottom = 6
		btn.add_theme_stylebox_override("normal", btn_sb)
		var btn_h := btn_sb.duplicate()
		btn_h.border_color = skin["accent"]
		btn_h.set_border_width_all(2)
		btn.add_theme_stylebox_override("hover", btn_h)
		btn.pressed.connect(_on_skin_select.bind(i))
		_skin_grid.add_child(btn)


# ═══════════════════════════════════════════════
#  互動
# ═══════════════════════════════════════════════
func _on_weapon_select(idx: int) -> void:
	_current_weapon = idx
	_rebuild_weapon()
	_refresh_skin_name()
	var wn: Label = get_node_or_null("WeaponName")
	if wn:
		wn.text = WEAPONS[idx]["name"]


func _on_skin_select(idx: int) -> void:
	_current_skin = idx
	_primary_color = SKINS[idx]["primary"]
	_accent_color = SKINS[idx]["accent"]
	_rebuild_weapon()
	_build_skin_grid()
	# 更新皮膚名稱 / 滑桿 / 顏色面板
	_refresh_skin_name()
	_update_sliders()
	_update_color_panels()


func _on_color_change() -> void:
	_current_skin = -1  # 自訂模式
	_rebuild_weapon()
	_build_skin_grid()
	_update_color_panels()
	_update_sliders()
	_refresh_skin_name()


func _on_primary_color_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		_customizing_primary = true
		_cycle_color(true)


func _on_accent_color_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		_customizing_primary = false
		_cycle_color(false)


func _cycle_color(is_primary: bool) -> void:
	# 循環常用顏色
	var colors := [
		Color(0.25, 0.27, 0.32), Color(0.05, 0.15, 0.25),
		Color(0.35, 0.08, 0.05), Color(0.15, 0.25, 0.40),
		Color(0.08, 0.06, 0.12), Color(0.35, 0.28, 0.08),
		Color(0.06, 0.20, 0.10), Color(0.30, 0.04, 0.06),
	]
	if is_primary:
		# 找最接近的下一個
		var best_idx := 0
		var best_dist := 999.0
		for i in range(colors.size()):
			var c: Color = colors[i]
			var d: float = abs(_primary_color.r - c.r) + abs(_primary_color.g - c.g) + abs(_primary_color.b - c.b)
			if d > 0.01 and d < best_dist:
				best_dist = d
				best_idx = i
		_primary_color = colors[(best_idx + 1) % colors.size()]
	else:
		var best_idx := 0
		var best_dist := 999.0
		for i in range(colors.size()):
			var c: Color = colors[i]
			var d: float = abs(_accent_color.r - c.r) + abs(_accent_color.g - c.g) + abs(_accent_color.b - c.b)
			if d > 0.01 and d < best_dist:
				best_dist = d
				best_idx = i
		_accent_color = colors[(best_idx + 1) % colors.size()]
	_on_color_change()


func _update_color_panels() -> void:
	# 直接更新色塊面板（不再依賴 group，避免沒人加入 group）
	if _primary_panel:
		var sb: StyleBox = _primary_panel.get_theme_stylebox("panel")
		if sb is StyleBoxFlat:
			sb.bg_color = _primary_color
	if _accent_panel:
		var sb2: StyleBox = _accent_panel.get_theme_stylebox("panel")
		if sb2 is StyleBoxFlat:
			sb2.bg_color = _accent_color


func _update_sliders() -> void:
	if _primary_slider:
		_primary_slider.set_value_no_signal(_primary_color.h)
	if _accent_slider:
		_accent_slider.set_value_no_signal(_accent_color.h)


func _refresh_skin_name() -> void:
	if _skin_name_lbl:
		_skin_name_lbl.text = _skin_label_text()


func _skin_label_text() -> String:
	if _current_skin >= 0:
		return SKINS[_current_skin]["name"]
	if _current_series >= 0:
		return String(SKIN_SERIES[_current_series]["name"])
	return "自訂"


func _rebuild_weapon() -> void:
	if not _weapon_model:
		return
	_weapon_model.clear_parts()
	_weapon_model.build_weapon(WEAPONS[_current_weapon]["slot"], {
		"primary": _primary_color,
		"accent": _accent_color
	}, _current_weapon)  # weapon_id = index in WEAPONS


func _save_palette() -> void:
	# 保存到 VantaGlobal（對戰中讀取）
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		g.weapon_palette = {
			"primary": _primary_color,
			"accent": _accent_color,
			"skin_name": _skin_label_text()
		}
	# 持久化到 user://（重開遊戲仍保留）
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify({
			"primary": _primary_color.to_html(),
			"accent": _accent_color.to_html(),
			"skin_name": _skin_label_text()
		}, "\t"))
		file.close()
	# 顯示保存成功
	_show_toast("✅ 配色已保存！")


func _load_palette() -> void:
	var file := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if not file:
		return
	var json := JSON.new()
	if json.parse(file.get_as_text()) != OK:
		return
	var data: Dictionary = json.data
	_primary_color = Color.html(data.get("primary", _primary_color.to_html()))
	_accent_color = Color.html(data.get("accent", _accent_color.to_html()))
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		g.weapon_palette = {
			"primary": _primary_color,
			"accent": _accent_color,
			"skin_name": String(data.get("skin_name", "自訂"))
		}


func _find_catalog_skin(series_idx: int, weapon_idx: int) -> String:
	"""在已解鎖皮膚中找「系列關鍵字 + 武器」相符的 skin_id。"""
	var keyword: String = String(SKIN_SERIES[series_idx]["name"]).split(" ")[0]
	for skin_id in _prog.unlocked_skins:
		var info: Dictionary = _prog.SKIN_CATALOG.get(skin_id, {})
		if info.get("weapon", -1) != weapon_idx:
			continue
		if String(info.get("name", "")).begins_with(keyword):
			return skin_id
	return ""


func _build_store_cards(parent: VBoxContainer) -> void:
	"""商店：SKIN_CATALOG 中「商店/夜市」來源（含每日輪替夜市）"""
	_store_box = parent
	_refresh_store()


func _refresh_store() -> void:
	if _store_box == null:
		return
	for c in _store_box.get_children():
		c.queue_free()
	# 商店固定商品 + 夜市每日輪替
	var store_items: Array[Dictionary] = []
	for skin_id in _prog.SKIN_CATALOG:
		var info: Dictionary = _prog.SKIN_CATALOG[skin_id]
		if info.get("source", "") == "商店":
			var item := info.duplicate()
			item["id"] = skin_id
			store_items.append(item)
	for nm in _prog.get_night_market_skins():
		store_items.append(nm)
	for item in store_items:
		var skin_id: String = item.get("id", "")
		var owned := _prog.is_skin_unlocked(skin_id)
		var price: int = item.get("price_vp", 0)
		var card := PanelContainer.new()
		card.custom_minimum_size = Vector2(0, 60)
		card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var csb := StyleBoxFlat.new()
		csb.bg_color = Color(0.1, 0.12, 0.16, 0.7)
		csb.border_color = Color(0.3, 0.32, 0.38) if not owned else Color(0.2, 0.55, 0.35)
		csb.set_border_width_all(1)
		csb.corner_radius_top_left = 4
		csb.corner_radius_top_right = 4
		csb.corner_radius_bottom_left = 4
		csb.corner_radius_bottom_right = 4
		csb.content_margin_left = 10
		csb.content_margin_right = 10
		csb.content_margin_top = 6
		csb.content_margin_bottom = 6
		card.add_theme_stylebox_override("panel", csb)
		var hbox := HBoxContainer.new()
		hbox.add_theme_constant_override("separation", 8)
		card.add_child(hbox)
		# 名稱 + 來源
		var name_lbl := Label.new()
		name_lbl.text = String(item.get("name", "?"))
		name_lbl.add_theme_font_size_override("font_size", 12)
		name_lbl.add_theme_color_override("font_color", TEXT_WHITE)
		hbox.add_child(name_lbl)
		var tier_lbl := Label.new()
		tier_lbl.text = String(item.get("tier", ""))
		tier_lbl.add_theme_font_size_override("font_size", 10)
		tier_lbl.add_theme_color_override("font_color",
			Color(0.8, 0.3, 1.0) if item.get("tier", "") == "傳說"
			else Color(0.9, 0.5, 0.1) if item.get("tier", "") == "精英"
			else TEXT_DIM)
		hbox.add_child(tier_lbl)
		# 彈性空間
		var spacer := Control.new()
		spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		hbox.add_child(spacer)
		if owned:
			var owned_lbl := Label.new()
			owned_lbl.text = "已擁有"
			owned_lbl.add_theme_font_size_override("font_size", 11)
			owned_lbl.add_theme_color_override("font_color", Color(0.3, 0.9, 0.5))
			hbox.add_child(owned_lbl)
			# 裝備按鈕
			var eq_btn := Button.new()
			eq_btn.text = "裝備"
			eq_btn.custom_minimum_size = Vector2(50, 26)
			eq_btn.add_theme_font_size_override("font_size", 11)
			eq_btn.add_theme_color_override("font_color", Color.WHITE)
			var eq_sb := StyleBoxFlat.new()
			eq_sb.bg_color = Color(0.2, 0.45, 0.75)
			eq_sb.corner_radius_top_left = 3
			eq_sb.corner_radius_top_right = 3
			eq_sb.corner_radius_bottom_left = 3
			eq_sb.corner_radius_bottom_right = 3
			eq_btn.add_theme_stylebox_override("normal", eq_sb)
			eq_btn.pressed.connect(_on_equip_store_skin.bind(skin_id))
			hbox.add_child(eq_btn)
		else:
			var price_lbl := Label.new()
			price_lbl.text = "$%d" % price
			price_lbl.add_theme_font_size_override("font_size", 12)
			price_lbl.add_theme_color_override("font_color",
				Color(0.0, 0.85, 0.75) if _prog.player_vp >= price else Color(0.9, 0.3, 0.3))
			hbox.add_child(price_lbl)
			var buy_btn := Button.new()
			buy_btn.text = "購買"
			buy_btn.custom_minimum_size = Vector2(50, 26)
			buy_btn.add_theme_font_size_override("font_size", 11)
			buy_btn.add_theme_color_override("font_color", Color.WHITE)
			var bsb := StyleBoxFlat.new()
			bsb.bg_color = Color(0.2, 0.6, 0.4)
			bsb.corner_radius_top_left = 3
			bsb.corner_radius_top_right = 3
			bsb.corner_radius_bottom_left = 3
			bsb.corner_radius_bottom_right = 3
			buy_btn.add_theme_stylebox_override("normal", bsb)
			buy_btn.disabled = _prog.player_vp < price
			buy_btn.pressed.connect(_on_buy_store_skin.bind(skin_id))
			hbox.add_child(buy_btn)
		_store_box.add_child(card)


func _on_buy_store_skin(skin_id: String) -> void:
	if _prog.buy_skin_vp(skin_id):
		_show_toast("✅ 已購買「%s」！" % String(_prog.get_skin_info(skin_id).get("name", "")))
		_refresh_progress()
		_refresh_store()
	else:
		_show_toast("⚠ 購買失敗：VP 不足或已擁有")


func _on_equip_store_skin(skin_id: String) -> void:
	var info: Dictionary = _prog.get_skin_info(skin_id)
	var weapon_idx: int = info.get("weapon", 0)
	# 從 SKIN_SERIES 找對應系列的配色
	var keyword: String = String(info.get("name", "")).split(" ")[0]
	for i in range(SKIN_SERIES.size()):
		if String(SKIN_SERIES[i]["name"]).begins_with(keyword):
			_current_series = i
			_current_weapon = weapon_idx
			var skin: Dictionary = SKIN_SERIES[i]["skins"].get(weapon_idx, {})
			if not skin.is_empty():
				_primary_color = skin.get("primary", _primary_color)
				_accent_color = skin.get("accent", _accent_color)
			break
	_current_skin = -1
	_prog.equip_skin(weapon_idx, skin_id)
	_rebuild_weapon()
	_build_skin_grid()
	_update_color_panels()
	_update_sliders()
	_refresh_skin_name()
	_refresh_progress()
	_show_toast("✅ 已裝備「%s」！" % String(info.get("name", "")))


func _build_progress_panel() -> PanelContainer:
	"""建立進度面板：等級/VP/Radianite/解鎖數量"""
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(0, 80)
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.08, 0.1, 0.15, 0.9)
	sb.border_color = Color(0.3, 0.5, 0.8)
	sb.set_border_width_all(1)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 8
	sb.content_margin_bottom = 8
	panel.add_theme_stylebox_override("panel", sb)
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 16)
	panel.add_child(hbox)
	# 等級
	var level_vbox := VBoxContainer.new()
	level_vbox.add_theme_constant_override("separation", 2)
	hbox.add_child(level_vbox)
	_lvl_lbl = Label.new()
	_lvl_lbl.text = "Lv.1"
	_lvl_lbl.add_theme_font_size_override("font_size", 18)
	_lvl_lbl.add_theme_color_override("font_color", Color(1.0, 0.85, 0.0))
	level_vbox.add_child(_lvl_lbl)
	_xp_lbl = Label.new()
	_xp_lbl.text = "0 / 1000 XP"
	_xp_lbl.add_theme_font_size_override("font_size", 10)
	_xp_lbl.add_theme_color_override("font_color", TEXT_DIM)
	level_vbox.add_child(_xp_lbl)
	# 分隔線
	var sep1 := VSeparator.new()
	hbox.add_child(sep1)
	# VP
	var vp_vbox := VBoxContainer.new()
	vp_vbox.add_theme_constant_override("separation", 2)
	hbox.add_child(vp_vbox)
	_vp_lbl = Label.new()
	_vp_lbl.text = "$5,000"
	_vp_lbl.add_theme_font_size_override("font_size", 14)
	_vp_lbl.add_theme_color_override("font_color", Color(0.0, 0.85, 0.75))
	vp_vbox.add_child(_vp_lbl)
	var vp_label := Label.new()
	vp_label.text = "VP"
	vp_label.add_theme_font_size_override("font_size", 10)
	vp_label.add_theme_color_override("font_color", TEXT_DIM)
	vp_vbox.add_child(vp_label)
	# 分隔線
	var sep2 := VSeparator.new()
	hbox.add_child(sep2)
	# Radianite
	var rad_vbox := VBoxContainer.new()
	rad_vbox.add_theme_constant_override("separation", 2)
	hbox.add_child(rad_vbox)
	_rad_lbl = Label.new()
	_rad_lbl.text = "200"
	_rad_lbl.add_theme_font_size_override("font_size", 14)
	_rad_lbl.add_theme_color_override("font_color", Color(0.8, 0.3, 1.0))
	rad_vbox.add_child(_rad_lbl)
	var rad_label := Label.new()
	rad_label.text = "Radianite"
	rad_label.add_theme_font_size_override("font_size", 10)
	rad_label.add_theme_color_override("font_color", TEXT_DIM)
	rad_vbox.add_child(rad_label)
	# 分隔線
	var sep3 := VSeparator.new()
	hbox.add_child(sep3)
	# 解鎖進度
	var prog_vbox := VBoxContainer.new()
	prog_vbox.add_theme_constant_override("separation", 2)
	hbox.add_child(prog_vbox)
	_unlock_lbl = Label.new()
	_unlock_lbl.text = "0 / 0"
	_unlock_lbl.add_theme_font_size_override("font_size", 14)
	_unlock_lbl.add_theme_color_override("font_color", Color(0.5, 0.8, 1.0))
	prog_vbox.add_child(_unlock_lbl)
	var prog_desc := Label.new()
	prog_desc.text = "皮膚已解鎖"
	prog_desc.add_theme_font_size_override("font_size", 10)
	prog_desc.add_theme_color_override("font_color", TEXT_DIM)
	prog_vbox.add_child(prog_desc)
	_refresh_progress()
	return panel


func _refresh_progress() -> void:
	if _prog == null or _lvl_lbl == null:
		return
	_lvl_lbl.text = "Lv.%d" % _prog.player_level
	_xp_lbl.text = "%d / %d XP" % [_prog.player_xp, _prog._xp_for_level(_prog.player_level + 1)]
	_vp_lbl.text = "$%s" % _fmt_num(_prog.player_vp)
	_rad_lbl.text = str(_prog.player_radianite)
	_unlock_lbl.text = "%d / %d" % [_prog.get_unlock_count(), _prog.get_total_skins()]


func _fmt_num(n: int) -> String:
	return str(n) if n < 10000 else "%d,%03d" % [floori(n / 1000.0), n % 1000]


func _show_toast(text: String) -> void:
	var toast := Label.new()
	toast.text = text
	toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	toast.position = Vector2(get_viewport_rect().size.x * 0.5 - 120, get_viewport_rect().size.y - 80)
	toast.size = Vector2(240, 36)
	toast.add_theme_font_size_override("font_size", 14)
	toast.add_theme_color_override("font_color", Color.WHITE)
	var tsb := StyleBoxFlat.new()
	tsb.bg_color = Color(0.1, 0.6, 0.4, 0.9)
	tsb.corner_radius_top_left = 6
	tsb.corner_radius_top_right = 6
	tsb.corner_radius_bottom_left = 6
	tsb.corner_radius_bottom_right = 6
	toast.add_theme_stylebox_override("normal", tsb)
	add_child(toast)
	# 2 秒後消失
	var tween := create_tween()
	tween.tween_interval(2.0)
	tween.tween_property(toast, "modulate:a", 0.0, 0.5)
	tween.tween_callback(toast.queue_free)


func _go_back() -> void:
	get_tree().change_scene_to_file("res://menu.tscn")


# ═══════════════════════════════════════════════
#  試射 + 擊殺特效
# ═══════════════════════════════════════════════
var _kill_effect_color := Color(1.0, 0.82, 0.32)  # 金→紅
var _kill_effect_size := 1.0
var _kill_effect_count := 40
var _synth_audio: SynthWeaponAudio = null


func _ensure_synth() -> void:
	if _synth_audio == null:
		_synth_audio = SynthWeaponAudio.new()
		add_child(_synth_audio)


func _on_test_fire() -> void:
	_ensure_synth()
	# 取得當前武器 key
	var wk := "vandal"
	match _current_weapon:
		0: wk = "phantom"
		1: wk = "vandal"
		2: wk = "ghost"
		3: wk = "classic"
		4: wk = "knife"
		5: wk = "sheriff"
		6: wk = "frenzy"
		10: wk = "stinger"
		11: wk = "spectre"
		20: wk = "bulldog"
		21: wk = "guardian"
		30: wk = "marshal"
		31: wk = "operator"
		40: wk = "bucky"
		41: wk = "judge"
		50: wk = "ares"
		51: wk = "odin"
	_synth_audio.trigger(wk, 1.0, -8.0)
	# 後座動畫
	if _weapon_model:
		_weapon_model.play_fire(0.6)
	_show_toast("🔫 %s 試射" % wk.capitalize())


func _on_preview_kill_effect() -> void:
	# 在預覽視口中央產生擊殺特效
	var emitter := CPUParticles3D.new()
	emitter.position = Vector3(0, 0.5, 0)
	emitter.amount = _kill_effect_count
	emitter.lifetime = 1.2
	emitter.one_shot = true
	emitter.explosiveness = 1.0
	emitter.emitting = true
	emitter.initial_velocity_min = 4.0
	emitter.initial_velocity_max = 8.0
	emitter.scale_amount_min = 0.08 * _kill_effect_size
	emitter.scale_amount_max = 0.15 * _kill_effect_size
	emitter.gravity = Vector3(0, -3, 0)
	emitter.direction = Vector3(0, 1, 0)
	emitter.spread = 70.0
	var grad := Gradient.new()
	grad.set_color(0, _kill_effect_color)
	grad.set_color(1, Color(_kill_effect_color.r * 0.5, _kill_effect_color.g * 0.2, 0.0, 0.0))
	emitter.color_ramp = grad
	_sub_viewport.add_child(emitter)
	var timer := get_tree().create_timer(1.5)
	timer.timeout.connect(emitter.queue_free)
	_show_toast("💀 擊殺特效預覽")


func _build_kill_effect_panel(parent: VBoxContainer) -> void:
	"""擊殺特效設定面板。"""
	var title := Label.new()
	title.text = "💀 擊殺特效"
	title.add_theme_font_size_override("font_size", 16)
	title.add_theme_color_override("font_color", TEXT_WHITE)
	parent.add_child(title)
	# 特效顏色
	var color_hbox := HBoxContainer.new()
	color_hbox.add_theme_constant_override("separation", 12)
	parent.add_child(color_hbox)
	var c_label := Label.new()
	c_label.text = "顏色"
	c_label.add_theme_font_size_override("font_size", 13)
	c_label.add_theme_color_override("font_color", TEXT_DIM)
	c_label.custom_minimum_size.y = 32
	c_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	color_hbox.add_child(c_label)
	# 顏色按鈕（循環選擇）
	var color_names := ["金紅", "冰藍", "毒綠", "烈焰", "紫電"]
	var color_values := [
		Color(1.0, 0.82, 0.32),
		Color(0.3, 0.8, 1.0),
		Color(0.2, 0.9, 0.4),
		Color(1.0, 0.4, 0.1),
		Color(0.7, 0.2, 1.0),
	]
	var color_idx := 0
	for i in range(color_values.size()):
		var dc: Color = _kill_effect_color - color_values[i]
		var d: float = sqrt(dc.r * dc.r + dc.g * dc.g + dc.b * dc.b)
		if d < 0.3:
			color_idx = i
			break
	var color_btn := Button.new()
	color_btn.text = color_names[color_idx]
	color_btn.custom_minimum_size = Vector2(70, 30)
	color_btn.add_theme_font_size_override("font_size", 12)
	color_btn.add_theme_color_override("font_color", Color.WHITE)
	var cbsb := StyleBoxFlat.new()
	cbsb.bg_color = color_values[color_idx].darkened(0.2)
	cbsb.corner_radius_top_left = 4
	cbsb.corner_radius_top_right = 4
	cbsb.corner_radius_bottom_left = 4
	cbsb.corner_radius_bottom_right = 4
	color_btn.add_theme_stylebox_override("normal", cbsb)
	color_btn.pressed.connect(func():
		color_idx = (color_idx + 1) % color_values.size()
		_kill_effect_color = color_values[color_idx]
		color_btn.text = color_names[color_idx]
		cbsb.bg_color = _kill_effect_color.darkened(0.2)
	)
	color_hbox.add_child(color_btn)
	# 粒子數量
	var count_hbox := HBoxContainer.new()
	count_hbox.add_theme_constant_override("separation", 8)
	parent.add_child(count_hbox)
	var ct_label := Label.new()
	ct_label.text = "粒子數"
	ct_label.add_theme_font_size_override("font_size", 13)
	ct_label.add_theme_color_override("font_color", TEXT_DIM)
	ct_label.custom_minimum_size.y = 32
	ct_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	count_hbox.add_child(ct_label)
	var ct_slider := HSlider.new()
	ct_slider.min_value = 10
	ct_slider.max_value = 100
	ct_slider.value = _kill_effect_count
	ct_slider.custom_minimum_size.x = 120
	ct_slider.value_changed.connect(func(v): _kill_effect_count = int(v))
	count_hbox.add_child(ct_slider)
	# 大小
	var size_hbox := HBoxContainer.new()
	size_hbox.add_theme_constant_override("separation", 8)
	parent.add_child(size_hbox)
	var sz_label := Label.new()
	sz_label.text = "大小"
	sz_label.add_theme_font_size_override("font_size", 13)
	sz_label.add_theme_color_override("font_color", TEXT_DIM)
	sz_label.custom_minimum_size.y = 32
	sz_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	size_hbox.add_child(sz_label)
	var sz_slider := HSlider.new()
	sz_slider.min_value = 0.3
	sz_slider.max_value = 3.0
	sz_slider.step = 0.1
	sz_slider.value = _kill_effect_size
	sz_slider.custom_minimum_size.x = 120
	sz_slider.value_changed.connect(func(v): _kill_effect_size = v)
	size_hbox.add_child(sz_slider)
