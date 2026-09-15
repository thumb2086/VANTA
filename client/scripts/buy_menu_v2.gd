## DEPRECATED: Use buy_menu.gd instead. Kept for reference.
class_name BuyMenuV2
extends Control

## Valorant-quality buy menu v2 — professional two-panel tactical shop
##
## Layout:
##   Left panel: Weapon grid organized by category (Sidearms/SMGs/Rifles/Snipers/Shotguns/Heavy)
##   Right panel: Armor + Abilities + Buy button
##   Top: Credits display + total cost
##   Keyboard shortcuts: 1-6 categories, Enter to buy, Esc to close

const BG_DARK := Color(0.03, 0.04, 0.07)
const ACCENT := Color(0.0, 0.85, 0.75)
const ACCENT_RED := Color(0.92, 0.22, 0.28)
const TEXT_WHITE := Color(0.94, 0.95, 0.97)
const TEXT_DIM := Color(0.50, 0.53, 0.60)
const TEXT_GOLD := Color(1.0, 0.82, 0.32)
const BORDER_DIM := Color(0.22, 0.25, 0.32)
const CAN_AFFORD_COL := Color(0.15, 0.85, 0.30)
const CANT_AFFORD_COL := Color(0.6, 0.2, 0.2)

# ──── Weapon data (matches server weapons.py item_ids) ────
const WEAPON_CATEGORIES := [
	{
		"name": "Sidearms",
		"key": "sidearms",
		"weapons": [
			{"key": "classic", "item_id": 3, "name": "Classic", "price": 0, "damage": 22, "rpm": 450, "mag": 12, "desc": "Standard sidearm, full-auto burst"},
			{"key": "shorty", "item_id": 14, "name": "Shorty", "price": 300, "damage": 12, "rpm": 210, "mag": 2, "desc": "Double-barrel shotgun, close range"},
			{"key": "frenzy", "item_id": 4, "name": "Frenzy", "price": 450, "damage": 18, "rpm": 750, "mag": 13, "desc": "Full-auto pistol, spray king"},
			{"key": "ghost", "item_id": 5, "name": "Ghost", "price": 500, "damage": 30, "rpm": 420, "mag": 15, "desc": "Silenced pistol, precise and quiet"},
			{"key": "sheriff", "item_id": 13, "name": "Sheriff", "price": 800, "damage": 55, "rpm": 250, "mag": 6, "desc": "High-damage revolver, one-tap potential"},
		]
	},
	{
		"name": "SMGs",
		"key": "smgs",
		"weapons": [
			{"key": "stinger", "item_id": 16, "name": "Stinger", "price": 1100, "damage": 27, "rpm": 960, "mag": 20, "desc": "High fire rate, close quarters"},
			{"key": "spectre", "item_id": 15, "name": "Spectre", "price": 1600, "damage": 26, "rpm": 800, "mag": 30, "desc": "Silenced SMG, mid-range stable"},
		]
	},
	{
		"name": "Rifles",
		"key": "rifles",
		"weapons": [
			{"key": "bulldog", "item_id": 2, "name": "Bulldog", "price": 2050, "damage": 35, "rpm": 550, "mag": 24, "desc": "3-round burst, great value"},
			{"key": "guardian", "item_id": 6, "name": "Guardian", "price": 2250, "damage": 65, "rpm": 315, "mag": 12, "desc": "Semi-auto, high precision damage"},
			{"key": "phantom", "item_id": 12, "name": "Phantom", "price": 2900, "damage": 39, "rpm": 660, "mag": 30, "desc": "Full-auto, silenced, stable"},
			{"key": "vandal", "item_id": 17, "name": "Vandal", "price": 2900, "damage": 40, "rpm": 585, "mag": 25, "desc": "Full-auto, high damage, heavy recoil"},
		]
	},
	{
		"name": "Snipers",
		"key": "snipers",
		"weapons": [
			{"key": "marshal", "item_id": 9, "name": "Marshal", "price": 950, "damage": 50, "rpm": 90, "mag": 5, "desc": "Light sniper, scoped precision"},
			{"key": "operator", "item_id": 11, "name": "Operator", "price": 4700, "damage": 150, "rpm": 40, "mag": 5, "desc": "Heavy sniper, one-shot kill"},
		]
	},
	{
		"name": "Shotguns",
		"key": "shotguns",
		"weapons": [
			{"key": "bucky", "item_id": 1, "name": "Bucky", "price": 900, "damage": 20, "rpm": 60, "mag": 5, "desc": "Pump-action, devastating close range"},
			{"key": "judge", "item_id": 7, "name": "Judge", "price": 1850, "damage": 17, "rpm": 210, "mag": 5, "desc": "Auto shotgun, point-defense king"},
		]
	},
	{
		"name": "Heavy",
		"key": "heavy",
		"weapons": [
			{"key": "ares", "item_id": 0, "name": "Ares", "price": 1600, "damage": 30, "rpm": 780, "mag": 50, "desc": "LMG, massive ammo pool"},
			{"key": "odin", "item_id": 10, "name": "Odin", "price": 3200, "damage": 38, "rpm": 720, "mag": 100, "desc": "Heavy LMG, suppressive fire"},
		]
	},
]

const ARMOR_OPTIONS := [
	{"key": "light", "name": "Light Shield", "price": 400, "hp": 25, "desc": "+25 HP armor"},
	{"key": "heavy", "name": "Heavy Shield", "price": 1000, "hp": 50, "desc": "+50 HP armor"},
]

const ABILITY_OPTIONS := [
	{"key": "C", "name": "C Ability", "price": 200, "desc": "Buy 1 charge per round"},
	{"key": "Q", "name": "Q Ability", "price": 200, "desc": "Buy 1 charge per round"},
	{"key": "E", "name": "E Ability", "price": 0, "desc": "Free — 1 charge per round"},
	{"key": "X", "name": "X Ultimate", "price": 0, "desc": "Charged by kills/rounds"},
]

var _credits := 8000
var _selected_weapon := ""
var _selected_category := 0
var _selected_armor := -1  # -1=none, 0=light, 1=heavy
var _selected_ability := -1
var _owned_weapons: Array = []
var _has_armor := false
var _armor_hp := 0
var _ability_charges := [1, 1, 1, 0]
var _is_open := false
var _anim_t := 0.0
var _anim_slide := 0.0  # 0=closed, 1=open

# Hover preview
var _hover_weapon: Dictionary = {}
var _hover_pos := Vector2.ZERO


func _ready() -> void:
	visible = false
	_build_ui()


func _process(delta: float) -> void:
	_anim_t += delta
	# Slide animation
	if _is_open and _anim_slide < 1.0:
		_anim_slide = minf(1.0, _anim_slide + delta * 5.0)
		_apply_slide()
	elif not _is_open and _anim_slide > 0.0:
		_anim_slide = maxf(0.0, _anim_slide - delta * 6.0)
		_apply_slide()
		if _anim_slide <= 0.0:
			visible = false
	# Handle keyboard shortcuts
	if _is_open:
		if Input.is_action_just_pressed("ui_cancel"):
			close_menu()
		for i in range(min(6, WEAPON_CATEGORIES.size())):
			if Input.is_physical_key_pressed(KEY_1 + i):
				_on_category_select(i)


func _apply_slide() -> void:
	var panel: PanelContainer = get_node_or_null("Panel")
	if panel:
		var target_x := 140.0
		panel.position.x = target_x + (1200.0 - target_x) * (1.0 - _anim_slide)
		panel.modulate.a = _anim_slide


func _build_ui() -> void:
	# Fullscreen background
	var bg := ColorRect.new()
	bg.name = "Bg"
	bg.color = Color(0, 0, 0, 0.7)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_STOP
	bg.gui_input.connect(_on_bg_input)
	add_child(bg)
	# Main panel
	var panel := PanelContainer.new()
	panel.name = "Panel"
	panel.position = Vector2(140, 50)
	panel.size = Vector2(1060, 620)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.05, 0.08, 0.96)
	sb.border_color = BORDER_DIM
	sb.set_border_width_all(2)
	sb.corner_radius_top_left = 8
	sb.corner_radius_top_right = 8
	sb.corner_radius_bottom_left = 8
	sb.corner_radius_bottom_right = 8
	sb.content_margin_left = 0
	sb.content_margin_right = 0
	sb.content_margin_top = 0
	sb.content_margin_bottom = 0
	panel.add_theme_stylebox_override("panel", sb)
	add_child(panel)
	# Main HBox (left=weapons, right=armor+abilities)
	var hbox := HBoxContainer.new()
	hbox.name = "MainHBox"
	hbox.add_theme_constant_override("separation", 0)
	panel.add_child(hbox)
	# ─── LEFT PANEL: Weapons ───
	var left_panel := VBoxContainer.new()
	left_panel.name = "LeftPanel"
	left_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_panel.add_theme_constant_override("separation", 8)
	hbox.add_child(left_panel)
	# Title row
	var title_row := HBoxContainer.new()
	title_row.add_theme_constant_override("separation", 12)
	left_panel.add_child(title_row)
	var title := Label.new()
	title.text = "WEAPON SHOP"
	title.add_theme_font_size_override("font_size", 20)
	title.add_theme_color_override("font_color", TEXT_WHITE)
	title_row.add_child(title)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_row.add_child(spacer)
	var credit_lbl := Label.new()
	credit_lbl.name = "CreditLabel"
	credit_lbl.text = "$%d" % _credits
	credit_lbl.add_theme_font_size_override("font_size", 18)
	credit_lbl.add_theme_color_override("font_color", TEXT_GOLD)
	title_row.add_child(credit_lbl)
	# Category tabs
	var cat_row := HBoxContainer.new()
	cat_row.name = "CategoryRow"
	cat_row.add_theme_constant_override("separation", 4)
	left_panel.add_child(cat_row)
	for i in range(WEAPON_CATEGORIES.size()):
		var cat: Dictionary = WEAPON_CATEGORIES[i]
		var btn := Button.new()
		btn.text = "%s [%d]" % [cat["name"], i + 1]
		btn.custom_minimum_size = Vector2(90, 28)
		btn.add_theme_font_size_override("font_size", 11)
		btn.add_theme_color_override("font_color", TEXT_WHITE)
		var btn_sb := StyleBoxFlat.new()
		btn_sb.bg_color = Color(0.08, 0.10, 0.14) if i != _selected_category else ACCENT
		btn_sb.corner_radius_top_left = 4
		btn_sb.corner_radius_top_right = 4
		btn_sb.corner_radius_bottom_left = 4
		btn_sb.corner_radius_bottom_right = 4
		btn_sb.content_margin_left = 6
		btn_sb.content_margin_right = 6
		btn.add_theme_stylebox_override("normal", btn_sb)
		btn.pressed.connect(_on_category_select.bind(i))
		cat_row.add_child(btn)
	# Weapons grid (scrollable)
	var scroll := ScrollContainer.new()
	scroll.name = "WeaponsScroll"
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left_panel.add_child(scroll)
	var weapons_grid := GridContainer.new()
	weapons_grid.name = "WeaponsGrid"
	weapons_grid.columns = 2
	weapons_grid.add_theme_constant_override("h_separation", 8)
	weapons_grid.add_theme_constant_override("v_separation", 8)
	scroll.add_child(weapons_grid)
	# ─── RIGHT PANEL: Armor + Abilities ───
	var right_panel := VBoxContainer.new()
	right_panel.name = "RightPanel"
	right_panel.custom_minimum_size = Vector2(280, 0)
	right_panel.add_theme_constant_override("separation", 10)
	hbox.add_child(right_panel)
	# Armor section
	var armor_title := Label.new()
	armor_title.text = "ARMOR"
	armor_title.add_theme_font_size_override("font_size", 16)
	armor_title.add_theme_color_override("font_color", TEXT_WHITE)
	right_panel.add_child(armor_title)
	for i in range(ARMOR_OPTIONS.size()):
		var armor: Dictionary = ARMOR_OPTIONS[i]
		var card := _build_armor_card(armor, i)
		right_panel.add_child(card)
	# Divider
	var divider := HSeparator.new()
	divider.add_theme_constant_override("separation", 10)
	right_panel.add_child(divider)
	# Abilities section
	var ability_title := Label.new()
	ability_title.text = "ABILITIES"
	ability_title.add_theme_font_size_override("font_size", 16)
	ability_title.add_theme_color_override("font_color", TEXT_WHITE)
	right_panel.add_child(ability_title)
	for i in range(ABILITY_OPTIONS.size()):
		var ab: Dictionary = ABILITY_OPTIONS[i]
		var card := _build_ability_card(ab, i)
		right_panel.add_child(card)
	# Spacer
	var spacer2 := Control.new()
	spacer2.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right_panel.add_child(spacer2)
	# Total cost + Buy button
	var total_row := HBoxContainer.new()
	total_row.add_theme_constant_override("separation", 10)
	right_panel.add_child(total_row)
	var total_label := Label.new()
	total_label.name = "TotalLabel"
	total_label.text = "Total: $0"
	total_label.add_theme_font_size_override("font_size", 14)
	total_label.add_theme_color_override("font_color", TEXT_WHITE)
	total_row.add_child(total_label)
	var buy_btn := Button.new()
	buy_btn.name = "BuyButton"
	buy_btn.text = "BUY [Enter]"
	buy_btn.custom_minimum_size = Vector2(120, 36)
	buy_btn.add_theme_font_size_override("font_size", 14)
	buy_btn.add_theme_color_override("font_color", Color.WHITE)
	var buy_sb := StyleBoxFlat.new()
	buy_sb.bg_color = ACCENT
	buy_sb.corner_radius_top_left = 4
	buy_sb.corner_radius_top_right = 4
	buy_sb.corner_radius_bottom_left = 4
	buy_sb.corner_radius_bottom_right = 4
	buy_btn.add_theme_stylebox_override("normal", buy_sb)
	buy_btn.pressed.connect(_on_buy)
	total_row.add_child(buy_btn)
	# Close button
	var close_row := HBoxContainer.new()
	close_row.add_theme_constant_override("separation", 8)
	right_panel.add_child(close_row)
	var close_btn := Button.new()
	close_btn.text = "CLOSE [B/Esc]"
	close_btn.custom_minimum_size = Vector2(200, 32)
	close_btn.add_theme_font_size_override("font_size", 12)
	close_btn.add_theme_color_override("font_color", TEXT_DIM)
	var close_sb := StyleBoxFlat.new()
	close_sb.bg_color = Color(0.10, 0.12, 0.16)
	close_sb.corner_radius_top_left = 4
	close_sb.corner_radius_top_right = 4
	close_sb.corner_radius_bottom_left = 4
	close_sb.corner_radius_bottom_right = 4
	close_btn.add_theme_stylebox_override("normal", close_sb)
	close_btn.pressed.connect(close_menu)
	close_row.add_child(close_btn)
	# Initial display
	_update_weapons_grid()


func _on_bg_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		close_menu()


func open_menu(credits: int) -> void:
	_credits = credits
	_is_open = true
	visible = true
	_anim_slide = 0.0
	_apply_slide()
	_update_credits()
	_update_weapons_grid()
	_update_total()


func close_menu() -> void:
	_is_open = false


func is_open() -> bool:
	return _is_open


func _on_category_select(idx: int) -> void:
	_selected_category = idx
	_update_category_buttons()
	_update_weapons_grid()


func _update_category_buttons() -> void:
	var cat_row: HBoxContainer = get_node_or_null("Panel/MainHBox/LeftPanel/CategoryRow")
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
	var grid: GridContainer = get_node_or_null("Panel/MainHBox/LeftPanel/WeaponsScroll/WeaponsGrid")
	if not grid:
		return
	for child in grid.get_children():
		child.queue_free()
	var cat: Dictionary = WEAPON_CATEGORIES[_selected_category]
	for weapon in cat["weapons"]:
		var card := _build_weapon_card(weapon)
		grid.add_child(card)


func _build_weapon_card(weapon: Dictionary) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(480, 80)
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var can_afford: bool = _credits >= weapon["price"] or weapon["price"] == 0
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.06, 0.08, 0.12, 0.9) if can_afford else Color(0.04, 0.05, 0.07, 0.6)
	sb.border_color = ACCENT if weapon["key"] == _selected_weapon else Color(0, 0, 0, 0)
	sb.set_border_width_all(2 if weapon["key"] == _selected_weapon else 0)
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
	hbox.add_theme_constant_override("separation", 12)
	panel.add_child(hbox)
	# Left: name + price + description
	var info_vbox := VBoxContainer.new()
	info_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info_vbox.add_theme_constant_override("separation", 2)
	hbox.add_child(info_vbox)
	var name_row := HBoxContainer.new()
	name_row.add_theme_constant_override("separation", 8)
	info_vbox.add_child(name_row)
	var name_lbl := Label.new()
	name_lbl.text = weapon["name"]
	name_lbl.add_theme_font_size_override("font_size", 14)
	name_lbl.add_theme_color_override("font_color", TEXT_WHITE if can_afford else TEXT_DIM)
	name_row.add_child(name_lbl)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_row.add_child(spacer)
	var price_text := "$%d" % weapon["price"] if weapon["price"] > 0 else "FREE"
	var price_lbl := Label.new()
	price_lbl.text = price_text
	price_lbl.add_theme_font_size_override("font_size", 13)
	price_lbl.add_theme_color_override("font_color", TEXT_GOLD if can_afford else Color(0.4, 0.35, 0.15))
	name_row.add_child(price_lbl)
	# Stats bars
	var stats_row := HBoxContainer.new()
	stats_row.add_theme_constant_override("separation", 8)
	info_vbox.add_child(stats_row)
	var max_damage := 150.0
	var max_rpm := 960.0
	var max_mag := 100.0
	for stat_pair in [
		["DMG", float(weapon["damage"]), max_damage, ACCENT],
		["RPM", float(weapon["rpm"]), max_rpm, Color(0.3, 0.8, 1.0)],
		["MAG", float(weapon["mag"]), max_mag, Color(0.9, 0.8, 0.2)]
	]:
		var sv := VBoxContainer.new()
		sv.add_theme_constant_override("separation", 1)
		stats_row.add_child(sv)
		var lbl := Label.new()
		lbl.text = stat_pair[0]
		lbl.add_theme_font_size_override("font_size", 9)
		lbl.add_theme_color_override("font_color", TEXT_DIM)
		sv.add_child(lbl)
		var bar_w := 70.0
		var bar_h := 4.0
		var frac := stat_pair[1] / stat_pair[2]
		var bar_bg := ColorRect.new()
		bar_bg.custom_minimum_size = Vector2(bar_w, bar_h)
		bar_bg.color = Color(0.12, 0.14, 0.18)
		sv.add_child(bar_bg)
		var bar_fg := ColorRect.new()
		bar_fg.custom_minimum_size = Vector2(bar_w * clampf(frac, 0.1, 1.0), bar_h)
		bar_fg.color = stat_pair[3]
		sv.add_child(bar_fg)
		var val_lbl := Label.new()
		val_lbl.text = str(int(stat_pair[1]))
		val_lbl.add_theme_font_size_override("font_size", 9)
		val_lbl.add_theme_color_override("font_color", stat_pair[3])
		sv.add_child(val_lbl)
	# Description
	var desc_lbl := Label.new()
	desc_lbl.text = weapon["desc"]
	desc_lbl.add_theme_font_size_override("font_size", 10)
	desc_lbl.add_theme_color_override("font_color", Color(0.55, 0.58, 0.65))
	info_vbox.add_child(desc_lbl)
	# Right: Buy button
	var buy_col := VBoxContainer.new()
	buy_col.alignment = BoxContainer.ALIGNMENT_CENTER
	hbox.add_child(buy_col)
	var buy_btn := Button.new()
	buy_btn.text = "BUY" if can_afford else "INSUFFICIENT"
	buy_btn.custom_minimum_size = Vector2(80, 32)
	buy_btn.add_theme_font_size_override("font_size", 12)
	buy_btn.add_theme_color_override("font_color", Color.WHITE if can_afford else TEXT_DIM)
	buy_btn.disabled = not can_afford
	var buy_sb := StyleBoxFlat.new()
	buy_sb.bg_color = ACCENT if can_afford else Color(0.08, 0.08, 0.10)
	buy_sb.corner_radius_top_left = 4
	buy_sb.corner_radius_top_right = 4
	buy_sb.corner_radius_bottom_left = 4
	buy_sb.corner_radius_bottom_right = 4
	buy_btn.add_theme_stylebox_override("normal", buy_sb)
	if can_afford:
		buy_btn.pressed.connect(_on_buy_weapon.bind(weapon))
	buy_col.add_child(buy_btn)
	# Click to select
	panel.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			_selected_weapon = weapon["key"]
			_hover_weapon = weapon
			_update_weapons_grid()
	)
	panel.mouse_entered.connect(func():
		_hover_weapon = weapon
	)
	panel.mouse_exited.connect(func():
		_hover_weapon = {}
	)
	return panel


func _build_armor_card(armor: Dictionary, idx: int) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(0, 50)
	var selected := _selected_armor == idx
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.06, 0.08, 0.12, 0.9)
	sb.border_color = ACCENT if selected else Color(0, 0, 0, 0)
	sb.set_border_width_all(2 if selected else 0)
	sb.corner_radius_top_left = 4
	sb.corner_radius_top_right = 4
	sb.corner_radius_bottom_left = 4
	sb.corner_radius_bottom_right = 4
	sb.content_margin_left = 10
	sb.content_margin_right = 10
	sb.content_margin_top = 6
	sb.content_margin_bottom = 6
	panel.add_theme_stylebox_override("panel", sb)
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 8)
	panel.add_child(hbox)
	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(info)
	var name_lbl := Label.new()
	name_lbl.text = armor["name"]
	name_lbl.add_theme_font_size_override("font_size", 13)
	name_lbl.add_theme_color_override("font_color", TEXT_WHITE)
	info.add_child(name_lbl)
	var desc_lbl := Label.new()
	desc_lbl.text = "%s — $%d" % [armor["desc"], armor["price"]]
	desc_lbl.add_theme_font_size_override("font_size", 10)
	desc_lbl.add_theme_color_override("font_color", TEXT_DIM)
	info.add_child(desc_lbl)
	var btn := Button.new()
	btn.text = "SELECT"
	btn.custom_minimum_size = Vector2(70, 28)
	btn.add_theme_font_size_override("font_size", 11)
	btn.add_theme_color_override("font_color", TEXT_WHITE)
	var btn_sb := StyleBoxFlat.new()
	btn_sb.bg_color = ACCENT if _credits >= armor["price"] else Color(0.08, 0.08, 0.10)
	btn_sb.corner_radius_top_left = 3
	btn_sb.corner_radius_top_right = 3
	btn_sb.corner_radius_bottom_left = 3
	btn_sb.corner_radius_bottom_right = 3
	btn.add_theme_stylebox_override("normal", btn_sb)
	btn.disabled = _credits < armor["price"]
	btn.pressed.connect(_on_select_armor.bind(idx))
	hbox.add_child(btn)
	panel.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			_on_select_armor(idx)
	)
	return panel


func _build_ability_card(ab: Dictionary, idx: int) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(0, 44)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.06, 0.08, 0.12, 0.9)
	sb.corner_radius_top_left = 4
	sb.corner_radius_top_right = 4
	sb.corner_radius_bottom_left = 4
	sb.corner_radius_bottom_right = 4
	sb.content_margin_left = 10
	sb.content_margin_right = 10
	sb.content_margin_top = 4
	sb.content_margin_bottom = 4
	panel.add_theme_stylebox_override("panel", sb)
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 8)
	panel.add_child(hbox)
	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(info)
	var name_lbl := Label.new()
	name_lbl.text = "%s — %s" % [ab["key"], ab["name"]]
	name_lbl.add_theme_font_size_override("font_size", 12)
	name_lbl.add_theme_color_override("font_color", TEXT_WHITE)
	info.add_child(name_lbl)
	var desc_lbl := Label.new()
	var price_str := "$%d" % ab["price"] if ab["price"] > 0 else "Free"
	desc_lbl.text = "%s — %s" % [ab["desc"], price_str]
	desc_lbl.add_theme_font_size_override("font_size", 9)
	desc_lbl.add_theme_color_override("font_color", TEXT_DIM)
	info.add_child(desc_lbl)
	# Charge display
	var charge_lbl := Label.new()
	charge_lbl.text = "x%d" % _ability_charges[idx]
	charge_lbl.add_theme_font_size_override("font_size", 14)
	charge_lbl.add_theme_color_override("font_color", ACCENT)
	hbox.add_child(charge_lbl)
	panel.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			_on_buy_ability(idx)
	)
	return panel


func _on_select_armor(idx: int) -> void:
	var armor: Dictionary = ARMOR_OPTIONS[idx]
	if _credits < armor["price"]:
		return
	_selected_armor = idx
	_update_right_panel()
	_update_total()


func _on_buy_ability(idx: int) -> void:
	var ab: Dictionary = ABILITY_OPTIONS[idx]
	if ab["price"] > 0 and _credits < ab["price"]:
		return
	if ab["price"] > 0:
		_credits -= ab["price"]
	_ability_charges[idx] += 1
	_update_credits()
	_update_right_panel()
	_update_total()
	# Send buy to server
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		g.pending_buy_item_id = ab.get("item_id", -1)


func _on_buy_weapon(weapon: Dictionary) -> void:
	if _credits < weapon["price"] and weapon["price"] > 0:
		return
	_credits -= weapon["price"]
	_owned_weapons.append(weapon["key"])
	_update_credits()
	_update_weapons_grid()
	_update_total()
	# Send buy to server
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		g.pending_buy_item_id = weapon["item_id"]


func _on_buy() -> void:
	# Buy selected weapon if any
	if _selected_weapon != "":
		for cat in WEAPON_CATEGORIES:
			for w in cat["weapons"]:
				if w["key"] == _selected_weapon:
					_on_buy_weapon(w)
					return
	# Buy selected armor
	if _selected_armor >= 0:
		_on_select_armor(_selected_armor)


func _update_credits() -> void:
	var lbl: Label = get_node_or_null("Panel/MainHBox/LeftPanel/CreditLabel")
	if lbl:
		lbl.text = "$%d" % _credits


func _update_right_panel() -> void:
	# Rebuild right panel
	var rp: VBoxContainer = get_node_or_null("Panel/MainHBox/RightPanel")
	if not rp:
		return
	# Keep title, rebuild cards
	# (Simple approach: just update totals)
	_update_total()


func _update_total() -> void:
	var total := 0
	if _selected_weapon != "":
		for cat in WEAPON_CATEGORIES:
			for w in cat["weapons"]:
				if w["key"] == _selected_weapon:
					total += w["price"]
	if _selected_armor >= 0:
		total += ARMOR_OPTIONS[_selected_armor]["price"]
	var lbl: Label = get_node_or_null("Panel/MainHBox/RightPanel/TotalLabel")
	if lbl:
		lbl.text = "Total: $%d" % total
		lbl.add_theme_color_override("font_color", TEXT_WHITE if _credits >= total else ACCENT_RED)
	var buy_btn: Button = get_node_or_null("Panel/MainHBox/RightPanel/BuyButton")
	if buy_btn:
		buy_btn.disabled = _credits < total
		var buy_sb := StyleBoxFlat.new()
		buy_sb.bg_color = ACCENT if _credits >= total else Color(0.08, 0.08, 0.10)
		buy_sb.corner_radius_top_left = 4
		buy_sb.corner_radius_top_right = 4
		buy_sb.corner_radius_bottom_left = 4
		buy_sb.corner_radius_bottom_right = 4
		buy_btn.add_theme_stylebox_override("normal", buy_sb)
