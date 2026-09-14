extends Control

## 買槍商店 — Valorant 風格回合開始購買介面
## 功能：武器分類 + 價格顯示 + 購買確認 + 金錢顯示

const BG_DARK := Color(0.03, 0.04, 0.07)
const ACCENT := Color(0.0, 0.85, 0.75)
const ACCENT_RED := Color(0.92, 0.22, 0.28)
const TEXT_WHITE := Color(0.94, 0.95, 0.97)
const TEXT_DIM := Color(0.50, 0.53, 0.60)
const TEXT_GOLD := Color(1.0, 0.82, 0.32)
const BORDER_DIM := Color(0.22, 0.25, 0.32)

# ──── 武器資料（伺服器端 weapons.py 對照）───
# item_id = sorted(WEAPONS) 的索引（伺服器端 weapon_item_id() 對照）
const WEAPON_CATEGORIES := [
	{
		"name": "手槍", "icon": "🔫",
		"weapons": [
			{"key": "classic", "item_id": 3, "name": "經典 Classic", "price": 0, "damage": 22, "rpm": 450, "mag": 12, "desc": "標準手槍，全自動爆發"},
			{"key": "ghost", "item_id": 5, "name": "鬼魅 Ghost", "price": 500, "damage": 30, "rpm": 420, "mag": 15, "desc": "消音手槍，精準安靜"},
			{"key": "frenzy", "item_id": 4, "name": "狂亂 Frenzy", "price": 450, "damage": 18, "rpm": 750, "mag": 13, "desc": "全自動手槍，近距離猛"},
			{"key": "sheriff", "item_id": 13, "name": "左輪 Sheriff", "price": 800, "damage": 55, "rpm": 250, "mag": 6, "desc": "高傷害左輪，一槍斃命"},
			{"key": "shorty", "item_id": 14, "name": "短管 Shorty", "price": 300, "damage": 12, "rpm": 210, "mag": 2, "desc": "超近程雙管霰彈"},
		]
	},
	{
		"name": "衝鋒槍", "icon": "⚡",
		"weapons": [
			{"key": "stinger", "item_id": 16, "name": "刺針 Stinger", "price": 1100, "damage": 27, "rpm": 960, "mag": 20, "desc": "高射速衝鋒槍，近戰利器"},
			{"key": "spectre", "item_id": 15, "name": "魅影 Spectre", "price": 1600, "damage": 26, "rpm": 800, "mag": 30, "desc": "消音衝鋒槍，中距離穩定"},
		]
	},
	{
		"name": "步槍", "icon": "🎯",
		"weapons": [
			{"key": "bulldog", "item_id": 2, "name": "牛犬 Bulldog", "price": 2050, "damage": 35, "rpm": 550, "mag": 24, "desc": "三連發步槍，性價比高"},
			{"key": "guardian", "item_id": 6, "name": "守衛 Guardian", "price": 2250, "damage": 65, "rpm": 315, "mag": 12, "desc": "半自動步槍，精準高傷"},
			{"key": "phantom", "item_id": 12, "name": "幻象 Phantom", "price": 2900, "damage": 39, "rpm": 660, "mag": 30, "desc": "全自動步槍，消音穩定"},
			{"key": "vandal", "item_id": 17, "name": "暴徒 Vandal", "price": 2900, "damage": 40, "rpm": 585, "mag": 25, "desc": "全自動步槍，高傷後座"},
		]
	},
	{
		"name": "狙擊槍", "icon": "🔭",
		"weapons": [
			{"key": "marshal", "item_id": 9, "name": "連狙 Marshal", "price": 950, "damage": 50, "rpm": 90, "mag": 5, "desc": "輕型狙擊，開鏡精準"},
			{"key": "operator", "item_id": 11, "name": "大狙 Operator", "price": 4700, "damage": 150, "rpm": 40, "mag": 5, "desc": "重型狙擊，一槍斃命"},
		]
	},
	{
		"name": "霰彈槍", "icon": "💥",
		"weapons": [
			{"key": "bucky", "item_id": 1, "name": "短管 Bucky", "price": 900, "damage": 20, "rpm": 60, "mag": 5, "desc": "泵動霰彈，近距離毀滅"},
			{"key": "judge", "item_id": 7, "name": "判官 Judge", "price": 1850, "damage": 17, "rpm": 210, "mag": 5, "desc": "連發霰彈，守點利器"},
		]
	},
	{
		"name": "重武器", "icon": "🔥",
		"weapons": [
			{"key": "ares", "item_id": 0, "name": "戰神 Ares", "price": 1600, "damage": 30, "rpm": 780, "mag": 50, "desc": "輕機槍，彈量充足"},
			{"key": "odin", "item_id": 10, "name": "奧丁 Odin", "price": 3200, "damage": 38, "rpm": 720, "mag": 100, "desc": "重機槍，火力壓制"},
		]
	},
]

# ──── 技能購買 ────
const ABILITY_COSTS := [
	{"key": "C", "name": "C 技能", "price": 200, "desc": "每回合可購買 1 次"},
	{"key": "Q", "name": "Q 技能", "price": 200, "desc": "每回合可購買 1 次"},
	{"key": "E", "name": "E 技能", "price": "免費", "desc": "每回合免費使用 1 次"},
	{"key": "X", "name": "X 終極", "price": "充能", "desc": "擊殺/死亡/回合結束充能"},
]

var _credits := 8000
var _selected_weapon := ""
var _selected_category := 0
var _owned_weapons: Array = []
var _is_open := false
var _anim_t := 0.0


func _ready() -> void:
	visible = false
	# 全幕背景（半透明）
	var bg := ColorRect.new()
	bg.name = "Bg"
	bg.color = Color(0, 0, 0, 0.7)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(bg)
	# 主面板
	var panel := PanelContainer.new()
	panel.name = "Panel"
	panel.position = Vector2(140, 60)
	panel.size = Vector2(1000, 600)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.05, 0.08, 0.95)
	sb.border_color = BORDER_DIM
	sb.set_border_width_all(2)
	sb.corner_radius_top_left = 8
	sb.corner_radius_top_right = 8
	sb.corner_radius_bottom_left = 8
	sb.corner_radius_bottom_right = 8
	sb.content_margin_left = 20
	sb.content_margin_right = 20
	sb.content_margin_top = 16
	sb.content_margin_bottom = 16
	panel.add_theme_stylebox_override("panel", sb)
	add_child(panel)
	# 內容 VBox
	var vbox := VBoxContainer.new()
	vbox.name = "Content"
	vbox.add_theme_constant_override("separation", 12)
	panel.add_child(vbox)
	# 標題列
	var title_row := HBoxContainer.new()
	title_row.add_theme_constant_override("separation", 12)
	vbox.add_child(title_row)
	var title := Label.new()
	title.text = "🔫 武器商店"
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", TEXT_WHITE)
	title_row.add_child(title)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_row.add_child(spacer)
	var credit_lbl := Label.new()
	credit_lbl.name = "CreditLabel"
	credit_lbl.text = "💰 $%d" % _credits
	credit_lbl.add_theme_font_size_override("font_size", 18)
	credit_lbl.add_theme_color_override("font_color", TEXT_GOLD)
	title_row.add_child(credit_lbl)
	# 分類標籤列
	var cat_row := HBoxContainer.new()
	cat_row.name = "CategoryRow"
	cat_row.add_theme_constant_override("separation", 6)
	vbox.add_child(cat_row)
	for i in range(WEAPON_CATEGORIES.size()):
		var cat: Dictionary = WEAPON_CATEGORIES[i]
		var btn := Button.new()
		btn.text = "%s %s" % [cat["icon"], cat["name"]]
		btn.custom_minimum_size = Vector2(100, 32)
		btn.add_theme_font_size_override("font_size", 12)
		btn.add_theme_color_override("font_color", TEXT_WHITE)
		var btn_sb := StyleBoxFlat.new()
		btn_sb.bg_color = Color(0.08, 0.10, 0.14) if i != _selected_category else ACCENT
		btn_sb.corner_radius_top_left = 4
		btn_sb.corner_radius_top_right = 4
		btn_sb.corner_radius_bottom_left = 4
		btn_sb.corner_radius_bottom_right = 4
		btn.add_theme_stylebox_override("normal", btn_sb)
		btn.pressed.connect(_on_category_select.bind(i))
		cat_row.add_child(btn)
	# 武器列表區
	var weapons_grid := GridContainer.new()
	weapons_grid.name = "WeaponsGrid"
	weapons_grid.columns = 4
	weapons_grid.add_theme_constant_override("h_separation", 10)
	weapons_grid.add_theme_constant_override("v_separation", 10)
	vbox.add_child(weapons_grid)
	# 底部按鈕列
	var btn_row := HBoxContainer.new()
	btn_row.add_theme_constant_override("separation", 12)
	vbox.add_child(btn_row)
	var close_btn := Button.new()
	close_btn.text = "✕ 關閉 (B)"
	close_btn.custom_minimum_size = Vector2(120, 40)
	close_btn.add_theme_font_size_override("font_size", 14)
	close_btn.add_theme_color_override("font_color", TEXT_DIM)
	var close_sb := StyleBoxFlat.new()
	close_sb.bg_color = Color(0.12, 0.14, 0.18)
	close_sb.corner_radius_top_left = 4
	close_sb.corner_radius_top_right = 4
	close_sb.corner_radius_bottom_left = 4
	close_sb.corner_radius_bottom_right = 4
	close_btn.add_theme_stylebox_override("normal", close_sb)
	close_btn.pressed.connect(close_menu)
	btn_row.add_child(close_btn)
	var spacer2 := Control.new()
	spacer2.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	btn_row.add_child(spacer2)
	# 已購武器
	var owned_lbl := Label.new()
	owned_lbl.name = "OwnedLabel"
	owned_lbl.text = "已購: 無"
	owned_lbl.add_theme_font_size_override("font_size", 12)
	owned_lbl.add_theme_color_override("font_color", TEXT_DIM)
	btn_row.add_child(owned_lbl)
	# 初始顯示
	_update_weapons_grid()


func _process(delta: float) -> void:
	_anim_t += delta


func open_menu(credits: int) -> void:
	_credits = credits
	_is_open = true
	visible = true
	_update_credits()
	_update_weapons_grid()


func close_menu() -> void:
	_is_open = false
	visible = false


func is_open() -> bool:
	return _is_open


func _on_category_select(idx: int) -> void:
	_selected_category = idx
	_update_category_buttons()
	_update_weapons_grid()


func _update_category_buttons() -> void:
	var cat_row: HBoxContainer = get_node_or_null("Panel/Content/CategoryRow")
	if not cat_row:
		return
	for i in range(cat_row.get_child_count()):
		var btn: Button = cat_row.get_child(i)
		if btn is Button:
			var sb := StyleBoxFlat.new()
			sb.bg_color = Color(0.08, 0.10, 0.14) if i != _selected_category else ACCENT
			sb.corner_radius_top_left = 4
			sb.corner_radius_top_right = 4
			sb.corner_radius_bottom_left = 4
			sb.corner_radius_bottom_right = 4
			btn.add_theme_stylebox_override("normal", sb)


func _update_weapons_grid() -> void:
	var grid: GridContainer = get_node_or_null("Panel/Content/WeaponsGrid")
	if not grid:
		return
	# 清除舊內容
	for child in grid.get_children():
		child.queue_free()
	# 當前分類的武器
	var cat: Dictionary = WEAPON_CATEGORIES[_selected_category]
	for weapon in cat["weapons"]:
		var card := _build_weapon_card(weapon)
		grid.add_child(card)


func _build_weapon_card(weapon: Dictionary) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(220, 120)
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	var can_afford: bool = _credits >= weapon["price"] or weapon["price"] == 0
	sb.bg_color = Color(0.06, 0.08, 0.12, 0.9) if can_afford else Color(0.04, 0.05, 0.07, 0.6)
	sb.border_color = ACCENT if weapon["key"] == _selected_weapon else Color(0, 0, 0, 0)
	sb.set_border_width_all(2 if weapon["key"] == _selected_weapon else 0)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 10
	panel.add_theme_stylebox_override("panel", sb)
	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 3)
	panel.add_child(vbox)
	# 武器名 + 價格
	var name_row := HBoxContainer.new()
	name_row.add_theme_constant_override("separation", 8)
	vbox.add_child(name_row)
	var name_lbl := Label.new()
	name_lbl.text = weapon["name"]
	name_lbl.add_theme_font_size_override("font_size", 14)
	name_lbl.add_theme_color_override("font_color", TEXT_WHITE if can_afford else TEXT_DIM)
	name_row.add_child(name_lbl)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_row.add_child(spacer)
	var price_lbl := Label.new()
	price_lbl.text = "💰 $%d" % weapon["price"] if weapon["price"] > 0 else "免費"
	price_lbl.add_theme_font_size_override("font_size", 13)
	price_lbl.add_theme_color_override("font_color", TEXT_GOLD if can_afford else Color(0.5, 0.4, 0.2))
	name_row.add_child(price_lbl)
	# 數值條
	var stats_hbox := HBoxContainer.new()
	stats_hbox.add_theme_constant_override("separation", 6)
	vbox.add_child(stats_hbox)
	var max_damage := 150.0
	var max_rpm := 960.0
	var max_mag := 100.0
	for stat_pair in [["DPS", float(weapon["damage"]), max_damage, ACCENT],
			["射速", float(weapon["rpm"]), max_rpm, Color(0.3, 0.8, 1.0)],
			["彈匣", float(weapon["mag"]), max_mag, Color(0.9, 0.8, 0.2)]]:
		var vbox2 := VBoxContainer.new()
		vbox2.add_theme_constant_override("separation", 2)
		stats_hbox.add_child(vbox2)
		var lbl := Label.new()
		lbl.text = stat_pair[0]
		lbl.add_theme_font_size_override("font_size", 9)
		lbl.add_theme_color_override("font_color", TEXT_DIM)
		vbox2.add_child(lbl)
		var bar_w := 60.0
		var bar_h := 4.0
		var frac := stat_pair[1] / stat_pair[2]
		var bar_bg := ColorRect.new()
		bar_bg.custom_minimum_size = Vector2(bar_w, bar_h)
		bar_bg.color = Color(0.15, 0.17, 0.22)
		vbox2.add_child(bar_bg)
		var bar_fg := ColorRect.new()
		bar_fg.custom_minimum_size = Vector2(bar_w * clampf(frac, 0.1, 1.0), bar_h)
		bar_fg.color = stat_pair[3]
		vbox2.add_child(bar_fg)
	# 描述
	var desc_lbl := Label.new()
	desc_lbl.text = weapon["desc"]
	desc_lbl.add_theme_font_size_override("font_size", 11)
	desc_lbl.add_theme_color_override("font_color", Color(0.6, 0.65, 0.7))
	vbox.add_child(desc_lbl)
	# 購買按鈕
	var buy_btn := Button.new()
	buy_btn.text = "購買" if can_afford else "金錢不足"
	buy_btn.custom_minimum_size = Vector2(0, 28)
	buy_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	buy_btn.add_theme_font_size_override("font_size", 12)
	buy_btn.add_theme_color_override("font_color", Color.WHITE if can_afford else TEXT_DIM)
	buy_btn.disabled = not can_afford
	var buy_sb := StyleBoxFlat.new()
	buy_sb.bg_color = ACCENT if can_afford else Color(0.1, 0.1, 0.12)
	buy_sb.corner_radius_top_left = 3
	buy_sb.corner_radius_top_right = 3
	buy_sb.corner_radius_bottom_left = 3
	buy_sb.corner_radius_bottom_right = 3
	buy_btn.add_theme_stylebox_override("normal", buy_sb)
	if can_afford:
		buy_btn.pressed.connect(_on_buy_weapon.bind(weapon))
	vbox.add_child(buy_btn)
	# 點擊選中
	panel.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			_selected_weapon = weapon["key"]
			_update_weapons_grid()
	)
	return panel


func _on_buy_weapon(weapon: Dictionary) -> void:
	if _credits < weapon["price"] and weapon["price"] > 0:
		return
	_credits -= weapon["price"]
	_owned_weapons.append(weapon["key"])
	_update_credits()
	_update_weapons_grid()
	_update_owned_label()
	# 發送購買封包到伺服器（通過 VantaGlobal 傳遞 item_id）
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		g.pending_buy_item_id = weapon["item_id"]


func _update_credits() -> void:
	var lbl: Label = get_node_or_null("Panel/Content/CreditLabel")
	if lbl:
		lbl.text = "💰 $%d" % _credits


func _update_owned_label() -> void:
	var lbl: Label = get_node_or_null("Panel/Content/OwnedLabel")
	if lbl:
		if _owned_weapons.size() > 0:
			lbl.text = "已購: %s" % ", ".join(_owned_weapons)
		else:
			lbl.text = "已購: 無"
