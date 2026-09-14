extends Control

## 角色選擇 — Valorant 風格 Agent 選擇畫面
## 功能：10 個 Agent 卡片 + 技能預覽 + 選擇確認

const BG_DARK := Color(0.03, 0.04, 0.07)
const ACCENT := Color(0.0, 0.85, 0.75)
const ACCENT_RED := Color(0.92, 0.22, 0.28)
const TEXT_WHITE := Color(0.94, 0.95, 0.97)
const TEXT_DIM := Color(0.50, 0.53, 0.60)
const TEXT_GOLD := Color(1.0, 0.82, 0.32)
const BORDER_DIM := Color(0.22, 0.25, 0.32)

const AGENTS := [
	{
		"name": "夜戮", "role": "決鬥者", "role_color": Color(0.95, 0.3, 0.3),
		"color": Color(0.8, 0.2, 0.3), "desc": "穿越次元的刺客，擾亂敵方防線",
		"skills": [
			{"key": "C", "name": "聲東擊西", "desc": "放置分身彈，分身被摧毀時會致盲敵人"},
			{"key": "Q", "name": "攻其不備", "desc": "投擲次元碎片，碰撞後發出致盲閃光"},
			{"key": "E", "name": "次元漂移", "desc": "放置傳送標記，再次啟動傳送到標記位置"},
			{"key": "X", "name": "不見蹤影", "desc": "進入次元裂縫，無敵狀態移動"},
		]
	},
	{
		"name": "歐門", "role": "控場者", "role_color": Color(0.5, 0.3, 0.9),
		"color": Color(0.3, 0.2, 0.7), "desc": "暗影行者，操控戰場視野",
		"skills": [
			{"key": "C", "name": "暗影漫步", "desc": "短距離傳送"},
			{"key": "Q", "name": "鬼影籠罩", "desc": "投擲暗影球，致盲敵人"},
			{"key": "E", "name": "暗影籠罩", "desc": "釋放煙霧球，遮蔽視野"},
			{"key": "X", "name": "夢魘降臨", "desc": "傳送至地圖上任意位置"},
		]
	},
	{
		"name": "聖祈", "role": "守衛者", "role_color": Color(0.2, 0.8, 0.5),
		"color": Color(0.2, 0.7, 0.5), "desc": "治癒之源，守護隊友",
		"skills": [
			{"key": "C", "name": "冰牆", "desc": "放置冰牆阻擋敵人"},
			{"key": "Q", "name": "緩速法球", "desc": "投擲減速區域"},
			{"key": "E", "name": "治癒之光", "desc": "治療隊友恢復生命"},
			{"key": "X", "name": "復活", "desc": "復活已陣亡的隊友"},
		]
	},
	{
		"name": "蘇法", "role": "偵查者", "role_color": Color(0.2, 0.5, 0.95),
		"color": Color(0.2, 0.5, 0.9), "desc": "獵鷹大師，獲取敵方情報",
		"skills": [
			{"key": "C", "name": "偵查無人機", "desc": "操控無人機偵查敵人位置"},
			{"key": "Q", "name": "震波箭", "desc": "發射震波箭，造成範圍傷害"},
			{"key": "E", "name": "偵查箭", "desc": "發射偵查箭，揭示敵人位置"},
			{"key": "X", "name": "獵者之怒", "desc": "發射三發遠程能量箭"},
		]
	},
	{
		"name": "婕提", "role": "決鬥者", "role_color": Color(0.95, 0.3, 0.3),
		"color": Color(0.9, 0.6, 0.1), "desc": "風之化身，高速突擊",
		"skills": [
			{"key": "C", "name": "突風", "desc": "向上衝刺飛行"},
			{"key": "Q", "name": "順風", "desc": "向前衝刺"},
			{"key": "E", "name": "煙幕", "desc": "投擲煙霧球"},
			{"key": "X", "name": "暴風旋刃", "desc": "召喚飛刀攻擊"},
		]
	},
	{
		"name": "叛奇", "role": "控場者", "role_color": Color(0.5, 0.3, 0.9),
		"color": Color(0.8, 0.4, 0.1), "desc": "重火力專家，震盪地形",
		"skills": [
			{"key": "C", "name": "閃光爆破", "desc": "發射致盲閃光"},
			{"key": "Q", "name": "地震裂縫", "desc": "發射震盪波眩暈敵人"},
			{"key": "E", "name": "震波", "desc": "發射遠程震盪波"},
			{"key": "X", "name": "大地破裂", "desc": "釋放大範圍震盪"},
		]
	},
	{
		"name": "妮虹", "role": "決鬥者", "role_color": Color(0.95, 0.3, 0.3),
		"color": Color(0.0, 0.8, 0.9), "desc": "電光奔馳，速度壓制",
		"skills": [
			{"key": "C", "name": "電流奔馳", "desc": "高速衝刺"},
			{"key": "Q", "name": "電光彈", "desc": "發射電球致盲"},
			{"key": "E", "name": "滑行充電", "desc": "滑行並充能"},
			{"key": "X", "name": "超載電流", "desc": "釋放電流攻擊"},
		]
	},
	{
		"name": "薇蝮", "role": "控場者", "role_color": Color(0.5, 0.3, 0.9),
		"color": Color(0.1, 0.6, 0.3), "desc": "毒霧籠罩，區域控制",
		"skills": [
			{"key": "C", "name": "蝕雲", "desc": "投擲毒霧球"},
			{"key": "Q", "name": "毒幕", "desc": "釋放毒牆"},
			{"key": "E", "name": "蝕牆", "desc": "投擲毒液區域"},
			{"key": "X", "name": "毒蛇之巢", "desc": "釋放大範圍毒霧"},
		]
	},
	{
		"name": "蓋克", "role": "守衛者", "role_color": Color(0.2, 0.8, 0.5),
		"color": Color(0.5, 0.55, 0.6), "desc": "重裝守衛，防線穩固",
		"skills": [
			{"key": "C", "name": "塵爆", "desc": "放置爆破陷阱"},
			{"key": "Q", "name": "震撼彈", "desc": "投擲震盪彈"},
			{"key": "E", "name": "皮蛋", "desc": "放出偵查夥伴"},
			{"key": "X", "name": "全覆蓋", "desc": "釋放大範圍防禦"},
		]
	},
	{
		"name": "愷宙", "role": "偵查者", "role_color": Color(0.2, 0.5, 0.95),
		"color": Color(0.4, 0.5, 1.0), "desc": "戰術機器人，壓制敵方技能",
		"skills": [
			{"key": "C", "name": "壓制匕首", "desc": "投擲壓制匕首"},
			{"key": "Q", "name": "閃光彈", "desc": "投擲致盲閃光"},
			{"key": "E", "name": "碎片手雷", "desc": "投擲碎片手雷"},
			{"key": "X", "name": "零/點", "desc": "釋放脈衝壓制"},
		]
	},
]

var _selected_agent := 0
var _anim_t := 0.0
var _cards: Array = []


func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = BG_DARK
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	# 頂部
	add_child(_build_top_bar())
	# 標題
	var title := Label.new()
	title.text = "選擇你的 Agent"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.position = Vector2(0, 56)
	title.size = Vector2(1280, 40)
	title.add_theme_font_size_override("font_size", 28)
	title.add_theme_color_override("font_color", TEXT_WHITE)
	add_child(title)
	# Agent 卡片網格（2 列 x 5 欄）
	var grid := GridContainer.new()
	grid.columns = 5
	grid.position = Vector2(40, 110)
	grid.size = Vector2(1200, 440)
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 12)
	add_child(grid)
	for i in range(AGENTS.size()):
		var card := _build_agent_card(i)
		grid.add_child(card)
		_cards.append(card)
	# 技能預覽面板
	add_child(_build_skill_panel())
	# 確認按鈕
	var confirm_btn := Button.new()
	confirm_btn.text = "✓ 確認選擇"
	confirm_btn.set_anchors_preset(Control.PRESET_CENTER)
	confirm_btn.position = Vector2(-100, 300)
	confirm_btn.size = Vector2(200, 50)
	confirm_btn.add_theme_font_size_override("font_size", 18)
	confirm_btn.add_theme_color_override("font_color", Color.WHITE)
	var csb := StyleBoxFlat.new()
	csb.bg_color = ACCENT
	csb.corner_radius_top_left = 4
	csb.corner_radius_top_right = 4
	csb.corner_radius_bottom_left = 4
	csb.corner_radius_bottom_right = 4
	confirm_btn.add_theme_stylebox_override("normal", csb)
	var ch := csb.duplicate()
	ch.bg_color = Color(0.0, 0.95, 0.85)
	confirm_btn.add_theme_stylebox_override("hover", ch)
	confirm_btn.pressed.connect(_confirm_selection)
	add_child(confirm_btn)


func _process(delta: float) -> void:
	_anim_t += delta


func _build_top_bar() -> PanelContainer:
	var bar := PanelContainer.new()
	bar.set_anchors_preset(Control.PRESET_TOP_WIDE)
	bar.custom_minimum_size = Vector2(0, 48)
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
	var lbl := Label.new()
	lbl.text = "Agent 選擇"
	lbl.add_theme_font_size_override("font_size", 18)
	lbl.add_theme_color_override("font_color", ACCENT)
	hbox.add_child(lbl)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(spacer)
	# 倒計時
	var timer := Label.new()
	timer.text = "準備階段"
	timer.add_theme_font_size_override("font_size", 13)
	timer.add_theme_color_override("font_color", TEXT_DIM)
	hbox.add_child(timer)
	return bar


func _build_agent_card(idx: int) -> PanelContainer:
	var agent: Dictionary = AGENTS[idx]
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(220, 200)
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(agent["color"].r, agent["color"].g, agent["color"].b, 0.25)
	sb.border_color = agent["role_color"] if idx == _selected_agent else Color(0, 0, 0, 0)
	sb.set_border_width_all(2 if idx == _selected_agent else 0)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 12
	panel.add_theme_stylebox_override("panel", sb)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 4)
	panel.add_child(vbox)
	# 角色頭像佔位（顏色方塊）
	var avatar := ColorRect.new()
	avatar.color = agent["color"]
	avatar.custom_minimum_size = Vector2(180, 100)
	avatar.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	vbox.add_child(avatar)
	# 名稱
	var name_lbl := Label.new()
	name_lbl.text = agent["name"]
	name_lbl.add_theme_font_size_override("font_size", 14)
	name_lbl.add_theme_color_override("font_color", TEXT_WHITE)
	vbox.add_child(name_lbl)
	# 角色類型
	var role_hbox := HBoxContainer.new()
	role_hbox.add_theme_constant_override("separation", 4)
	vbox.add_child(role_hbox)
	var role_dot := ColorRect.new()
	role_dot.color = agent["role_color"]
	role_dot.custom_minimum_size = Vector2(8, 8)
	role_hbox.add_child(role_dot)
	var role_lbl := Label.new()
	role_lbl.text = agent["role"]
	role_lbl.add_theme_font_size_override("font_size", 11)
	role_lbl.add_theme_color_override("font_color", agent["role_color"])
	role_hbox.add_child(role_lbl)
	# 描述
	var desc_lbl := Label.new()
	desc_lbl.text = agent["desc"]
	desc_lbl.add_theme_font_size_override("font_size", 10)
	desc_lbl.add_theme_color_override("font_color", TEXT_DIM)
	desc_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(desc_lbl)
	# 點擊選擇
	panel.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			_selected_agent = idx
			_update_cards()
	)
	return panel


func _update_cards() -> void:
	for i in range(_cards.size()):
		var card: PanelContainer = _cards[i]
		var sb: StyleBoxFlat = card.get_theme_stylebox("panel")
		if sb is StyleBoxFlat:
			sb.border_color = AGENTS[i]["role_color"] if i == _selected_agent else Color(0, 0, 0, 0)
			sb.set_border_width_all(2 if i == _selected_agent else 0)
	# 更新技能面板
	var skill_panel: PanelContainer = get_node_or_null("SkillPanel")
	if skill_panel:
		_update_skill_panel_content(skill_panel)


func _build_skill_panel() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.name = "SkillPanel"
	panel.position = Vector2(40, 570)
	panel.size = Vector2(1200, 120)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.05, 0.08, 0.85)
	sb.border_color = BORDER_DIM
	sb.set_border_width_all(1)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	sb.content_margin_left = 20
	sb.content_margin_right = 20
	sb.content_margin_top = 10
	panel.add_theme_stylebox_override("panel", sb)
	# 技能內容由 _update_skill_panel 動態設定
	_update_skill_panel_content(panel)
	return panel


func _update_skill_panel_content(panel: PanelContainer) -> void:
	# 清除舊內容
	for child in panel.get_children():
		child.queue_free()
	var agent: Dictionary = AGENTS[_selected_agent]
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 20)
	panel.add_child(hbox)
	# Agent 名稱
	var name_col := VBoxContainer.new()
	name_col.add_theme_constant_override("separation", 4)
	hbox.add_child(name_col)
	var name_lbl := Label.new()
	name_lbl.text = agent["name"]
	name_lbl.add_theme_font_size_override("font_size", 16)
	name_lbl.add_theme_color_override("font_color", TEXT_WHITE)
	name_col.add_child(name_lbl)
	var role_lbl := Label.new()
	role_lbl.text = agent["role"]
	role_lbl.add_theme_font_size_override("font_size", 12)
	role_lbl.add_theme_color_override("font_color", agent["role_color"])
	name_col.add_child(role_lbl)
	# 分隔
	hbox.add_child(VSeparator.new())
	# 四個技能
	for skill in agent["skills"]:
		var skill_box := VBoxContainer.new()
		skill_box.add_theme_constant_override("separation", 2)
		skill_box.custom_minimum_size.x = 200
		hbox.add_child(skill_box)
		# 技能鍵位
		var key_lbl := Label.new()
		key_lbl.text = "[%s] %s" % [skill["key"], skill["name"]]
		key_lbl.add_theme_font_size_override("font_size", 13)
		key_lbl.add_theme_color_override("font_color", ACCENT)
		skill_box.add_child(key_lbl)
		# 技能描述
		var desc_lbl := Label.new()
		desc_lbl.text = skill["desc"]
		desc_lbl.add_theme_font_size_override("font_size", 11)
		desc_lbl.add_theme_color_override("font_color", TEXT_DIM)
		desc_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		skill_box.add_child(desc_lbl)


func _confirm_selection() -> void:
	# 保存到 VantaGlobal
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		g.selected_agent = _selected_agent
		g.selected_agent_name = AGENTS[_selected_agent]["name"]
	# 進入遊戲
	get_tree().change_scene_to_file("res://main.tscn")
