extends Control

## 地圖產生器 — 程序化生成 Valorant 風格戰術地圖
## 功能：房間 + 走廊 + 站點 + 重生點 + 2D 預覽 + JSON 匯出

# ──── 色彩 ────
const BG_DARK := Color(0.03, 0.04, 0.07)
const ACCENT := Color(0.0, 0.85, 0.75)
const ACCENT_RED := Color(0.92, 0.22, 0.28)
const TEXT_WHITE := Color(0.94, 0.95, 0.97)
const TEXT_DIM := Color(0.50, 0.53, 0.60)
const TEXT_GOLD := Color(1.0, 0.82, 0.32)
const BORDER_DIM := Color(0.22, 0.25, 0.32)

# ──── 地圖參數 ────
var _grid_size := 40        # 格子大小（世界單位）
var _cell_size := 1.0       # 每格世界單位
var _room_count := 6        # 房間數量
var _corridor_width := 3.0  # 走廊寬度
var _wall_height := 4.0     # 牆壁高度
var _seed := 42             # 隨機種子
var _map_name := "custom_map"

# ──── 生成結果 ────
var _rooms: Array = []       # [{x, y, w, h, name}]
var _corridors: Array = []   # [{x1, y1, x2, y2}]
var _walls: Array = []       # [{mn, mx, material}]
var _sites: Array = []       # [{name, center, radius}]
var _spawns_a: Array = []    # [{x, y, z}]
var _spawns_d: Array = []    # [{x, y, z}]
var _grid: Array = []        # 2D 陣列：0=空地, 1=牆, 2=房間, 3=走廊, 4=站點, 5=重生點

# ──── 預覽 ────
var _preview_offset := Vector2(540, 60)
var _preview_scale := 6.0
var _preview_size := Vector2(600, 600)

# ──── UI 引用 ────
var _seed_input: LineEdit
var _room_input: HSlider
var _corridor_input: HSlider
var _wall_input: HSlider
var _name_input: LineEdit
var _status_label: Label


func _ready() -> void:
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
	# 左側控制面板
	var left := _build_control_panel()
	main_hbox.add_child(left)
	# 中央 2D 預覽
	var center := _build_preview()
	main_hbox.add_child(center)
	# 右側資訊
	var right := _build_info_panel()
	main_hbox.add_child(right)
	# 頂部導航
	add_child(_build_top_bar())
	# 初始生成
	_generate_map()


func _draw() -> void:
	_draw_grid()
	_draw_walls()
	_draw_sites()
	_draw_spawns()
	_draw_corridors()


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
	var back_btn := Button.new()
	back_btn.text = "◀ 返回"
	back_btn.flat = true
	back_btn.custom_minimum_size = Vector2(80, 36)
	back_btn.add_theme_font_size_override("font_size", 14)
	back_btn.add_theme_color_override("font_color", TEXT_DIM)
	back_btn.pressed.connect(func(): get_tree().change_scene_to_file("res://menu.tscn"))
	hbox.add_child(back_btn)
	var sep := VSeparator.new()
	hbox.add_child(sep)
	var title := Label.new()
	title.text = "🗺 地圖產生器"
	title.add_theme_font_size_override("font_size", 20)
	title.add_theme_color_override("font_color", TEXT_GOLD)
	hbox.add_child(title)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(spacer)
	_status_label = Label.new()
	_status_label.text = "就緒"
	_status_label.add_theme_font_size_override("font_size", 12)
	_status_label.add_theme_color_override("font_color", TEXT_DIM)
	hbox.add_child(_status_label)
	return bar


# ═══════════════════════════════════════════════
#  左側控制面板
# ═══════════════════════════════════════════════
func _build_control_panel() -> PanelContainer:
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
	vbox.add_theme_constant_override("separation", 14)
	scroll.add_child(vbox)
	# 標題
	var lbl := Label.new()
	lbl.text = "地圖參數"
	lbl.add_theme_font_size_override("font_size", 16)
	lbl.add_theme_color_override("font_color", TEXT_WHITE)
	vbox.add_child(lbl)
	# 地圖名稱
	vbox.add_child(_make_label("地圖名稱"))
	_name_input = LineEdit.new()
	_name_input.text = _map_name
	_name_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_name_input.custom_minimum_size.y = 32
	vbox.add_child(_name_input)
	# 隨機種子
	vbox.add_child(_make_label("隨機種子"))
	var seed_hbox := HBoxContainer.new()
	seed_hbox.add_theme_constant_override("separation", 8)
	vbox.add_child(seed_hbox)
	_seed_input = LineEdit.new()
	_seed_input.text = str(_seed)
	_seed_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_seed_input.custom_minimum_size.y = 32
	seed_hbox.add_child(_seed_input)
	var rand_btn := Button.new()
	rand_btn.text = "🎲"
	rand_btn.custom_minimum_size = Vector2(36, 32)
	rand_btn.add_theme_font_size_override("font_size", 16)
	rand_btn.pressed.connect(func(): _seed = randi() % 10000; _seed_input.text = str(_seed); _generate_map())
	seed_hbox.add_child(rand_btn)
	# 房間數量
	vbox.add_child(_make_label("房間數量: %d" % _room_count))
	_room_input = HSlider.new()
	_room_input.min_value = 3
	_room_input.max_value = 12
	_room_input.value = _room_count
	_room_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_room_input.value_changed.connect(func(v): _room_count = int(v); _generate_map())
	vbox.add_child(_room_input)
	# 走廊寬度
	vbox.add_child(_make_label("走廊寬度: %.1f" % _corridor_width))
	_corridor_input = HSlider.new()
	_corridor_input.min_value = 2.0
	_corridor_input.max_value = 6.0
	_corridor_input.step = 0.5
	_corridor_input.value = _corridor_width
	_corridor_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_corridor_input.value_changed.connect(func(v): _corridor_width = v; _generate_map())
	vbox.add_child(_corridor_input)
	# 牆壁高度
	vbox.add_child(_make_label("牆壁高度: %.1f" % _wall_height))
	_wall_input = HSlider.new()
	_wall_input.min_value = 2.0
	_wall_input.max_value = 8.0
	_wall_input.step = 0.5
	_wall_input.value = _wall_height
	_wall_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_wall_input.value_changed.connect(func(v): _wall_height = v; _generate_map())
	vbox.add_child(_wall_input)
	# 分隔
	vbox.add_child(HSeparator.new())
	# 重新生成按鈕
	var gen_btn := Button.new()
	gen_btn.text = "🔄 重新生成"
	gen_btn.custom_minimum_size = Vector2(0, 44)
	gen_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	gen_btn.add_theme_font_size_override("font_size", 14)
	gen_btn.add_theme_color_override("font_color", Color.WHITE)
	var gen_sb := StyleBoxFlat.new()
	gen_sb.bg_color = ACCENT
	gen_sb.corner_radius_top_left = 4
	gen_sb.corner_radius_top_right = 4
	gen_sb.corner_radius_bottom_left = 4
	gen_sb.corner_radius_bottom_right = 4
	gen_btn.add_theme_stylebox_override("normal", gen_sb)
	var gen_h := gen_sb.duplicate()
	gen_h.bg_color = Color(0.0, 0.95, 0.85)
	gen_btn.add_theme_stylebox_override("hover", gen_h)
	gen_btn.pressed.connect(_generate_map)
	vbox.add_child(gen_btn)
	# 匯出 JSON 按鈕
	var export_btn := Button.new()
	export_btn.text = "💾 匯出 JSON"
	export_btn.custom_minimum_size = Vector2(0, 44)
	export_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	export_btn.add_theme_font_size_override("font_size", 14)
	export_btn.add_theme_color_override("font_color", Color.WHITE)
	var exp_sb := StyleBoxFlat.new()
	exp_sb.bg_color = Color(0.2, 0.5, 0.3)
	exp_sb.corner_radius_top_left = 4
	exp_sb.corner_radius_top_right = 4
	exp_sb.corner_radius_bottom_left = 4
	exp_sb.corner_radius_bottom_right = 4
	export_btn.add_theme_stylebox_override("normal", exp_sb)
	var exp_h := exp_sb.duplicate()
	exp_h.bg_color = Color(0.25, 0.6, 0.35)
	export_btn.add_theme_stylebox_override("hover", exp_h)
	export_btn.pressed.connect(_export_json)
	vbox.add_child(export_btn)
	# 套用到遊戲按鈕
	var apply_btn := Button.new()
	apply_btn.text = "🎮 套用到遊戲"
	apply_btn.custom_minimum_size = Vector2(0, 44)
	apply_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	apply_btn.add_theme_font_size_override("font_size", 14)
	apply_btn.add_theme_color_override("font_color", Color.WHITE)
	var app_sb := StyleBoxFlat.new()
	app_sb.bg_color = ACCENT_RED
	app_sb.corner_radius_top_left = 4
	app_sb.corner_radius_top_right = 4
	app_sb.corner_radius_bottom_left = 4
	app_sb.corner_radius_bottom_right = 4
	apply_btn.add_theme_stylebox_override("normal", app_sb)
	var app_h := app_sb.duplicate()
	app_h.bg_color = Color(1.0, 0.32, 0.38)
	apply_btn.add_theme_stylebox_override("hover", app_h)
	apply_btn.pressed.connect(_apply_to_game)
	vbox.add_child(apply_btn)
	return panel


func _make_label(text: String) -> Label:
	var lbl := Label.new()
	lbl.text = text
	lbl.add_theme_font_size_override("font_size", 12)
	lbl.add_theme_color_override("font_color", TEXT_DIM)
	return lbl


# ═══════════════════════════════════════════════
#  中央 2D 預覽
# ═══════════════════════════════════════════════
func _build_preview() -> Control:
	var container := Control.new()
	container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	container.size_flags_vertical = Control.SIZE_EXPAND_FILL
	# 預覽背景
	var preview_bg := ColorRect.new()
	preview_bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	preview_bg.color = Color(0.06, 0.07, 0.10)
	container.add_child(preview_bg)
	# 標籤
	var lbl := Label.new()
	lbl.text = "2D 俯視圖"
	lbl.position = Vector2(20, 56)
	lbl.add_theme_font_size_override("font_size", 14)
	lbl.add_theme_color_override("font_color", TEXT_DIM)
	container.add_child(lbl)
	return container


# ═══════════════════════════════════════════════
#  右側資訊面板
# ═══════════════════════════════════════════════
func _build_info_panel() -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(220, 0)
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.05, 0.08, 0.9)
	sb.border_color = BORDER_DIM
	sb.set_border_width_all(1)
	sb.content_margin_left = 14
	sb.content_margin_right = 14
	sb.content_margin_top = 60
	sb.content_margin_bottom = 16
	panel.add_theme_stylebox_override("panel", sb)
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.add_child(scroll)
	var vbox := VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 10)
	scroll.add_child(vbox)
	var lbl := Label.new()
	lbl.text = "📊 地圖資訊"
	lbl.add_theme_font_size_override("font_size", 16)
	lbl.add_theme_color_override("font_color", TEXT_WHITE)
	vbox.add_child(lbl)
	vbox.add_child(HSeparator.new())
	# 統計
	var info := Label.new()
	info.name = "InfoLabel"
	info.text = "生成中..."
	info.add_theme_font_size_override("font_size", 12)
	info.add_theme_color_override("font_color", TEXT_DIM)
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(info)
	# 圖例
	vbox.add_child(HSeparator.new())
	var legend_title := Label.new()
	legend_title.text = "圖例"
	legend_title.add_theme_font_size_override("font_size", 13)
	legend_title.add_theme_color_override("font_color", TEXT_WHITE)
	vbox.add_child(legend_title)
	var legends := [
		[Color(0.25, 0.28, 0.35), "牆壁"],
		[Color(0.18, 0.35, 0.25), "房間"],
		[Color(0.35, 0.30, 0.18), "走廊"],
		[Color(0.9, 0.25, 0.25), "站點 (A/B)"],
		[Color(0.2, 0.6, 0.95), "攻方重生"],
		[Color(0.95, 0.6, 0.2), "守方重生"],
	]
	for leg in legends:
		var hbox := HBoxContainer.new()
		hbox.add_theme_constant_override("separation", 8)
		vbox.add_child(hbox)
		var color_rect := ColorRect.new()
		color_rect.color = leg[0]
		color_rect.custom_minimum_size = Vector2(16, 16)
		hbox.add_child(color_rect)
		var leg_lbl := Label.new()
		leg_lbl.text = leg[1]
		leg_lbl.add_theme_font_size_override("font_size", 11)
		leg_lbl.add_theme_color_override("font_color", TEXT_DIM)
		leg_lbl.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		hbox.add_child(leg_lbl)
	return panel


# ═══════════════════════════════════════════════
#  程序化地圖生成
# ═══════════════════════════════════════════════
func _generate_map() -> void:
	_map_name = _name_input.text if _name_input else "custom_map"
	_seed = int(_seed_input.text) if _seed_input else 42
	seed(_seed)
	_rooms.clear()
	_corridors.clear()
	_walls.clear()
	_sites.clear()
	_spawns_a.clear()
	_spawns_d.clear()
	# 初始化格子
	_grid = []
	for y in range(_grid_size):
		var row := []
		for x in range(_grid_size):
			row.append(0)
		_grid.append(row)
	# 生成房間
	_generate_rooms()
	# 生成走廊連接房間
	_generate_corridors()
	# 轉換為牆壁 JSON 格式
	_build_walls_from_grid()
	# 放置站點（在最大的兩個房間）
	_place_sites()
	# 放置重生點
	_place_spawns()
	# 更新資訊
	_update_info()
	# 重繪
	queue_redraw()
	if _status_label:
		_status_label.text = "✅ 已生成 (seed=%d)" % _seed


func _generate_rooms() -> void:
	var attempts := 0
	var max_attempts := _room_count * 20
	while _rooms.size() < _room_count and attempts < max_attempts:
		attempts += 1
		var rw := randi_range(5, 10)
		var rh := randi_range(5, 10)
		var rx := randi_range(2, _grid_size - rw - 2)
		var ry := randi_range(2, _grid_size - rh - 2)
		# 檢查重疊
		var overlap := false
		for room in _rooms:
			if rx < room["x"] + room["w"] + 2 and rx + rw + 2 > room["x"] and \
				ry < room["y"] + room["h"] + 2 and ry + rh + 2 > room["y"]:
				overlap = true
				break
		if not overlap:
			var room := {"x": rx, "y": ry, "w": rw, "h": rh, "name": "Room%d" % _rooms.size()}
			_rooms.append(room)
			# 標記格子
			for y in range(ry, ry + rh):
				for x in range(rx, rx + rw):
					_grid[y][x] = 2


func _generate_corridors() -> void:
	# 用 MST 連接所有房間
	if _rooms.size() < 2:
		return
	# 計算房間中心
	var centers: Array[Vector2] = []
	for room in _rooms:
		centers.append(Vector2(room["x"] + room["w"] * 0.5, room["y"] + room["h"] * 0.5))
	# Prim MST
	var in_mst := [0]
	var edges: Array = []
	while in_mst.size() < _rooms.size():
		var best_dist := 999999.0
		var best_from := -1
		var best_to := -1
		for from_idx in in_mst:
			for to_idx in range(_rooms.size()):
				if to_idx in in_mst:
					continue
				var d: float = centers[from_idx].distance_to(centers[to_idx])
				if d < best_dist:
					best_dist = d
					best_from = from_idx
					best_to = to_idx
		if best_to < 0:
			break
		in_mst.append(best_to)
		edges.append([best_from, best_to])
		# 生成走廊（L 形）
		var c1: Vector2 = centers[best_from]
		var c2: Vector2 = centers[best_to]
		var cw := int(ceil(_corridor_width * 0.5))
		_corridors.append({"x1": int(c1.x), "y1": int(c1.y), "x2": int(c2.x), "y2": int(c2.y)})
		# 先水平再垂直
		var sx := int(min(c1.x, c2.x))
		var ex := int(max(c1.x, c2.x))
		for x in range(sx, ex + 1):
			for dy in range(-cw, cw + 1):
				var yy := int(c1.y) + dy
				if yy >= 0 and yy < _grid_size and x >= 0 and x < _grid_size:
					if _grid[yy][x] == 0:
						_grid[yy][x] = 3
		var sy := int(min(c1.y, c2.y))
		var ey := int(max(c1.y, c2.y))
		for y in range(sy, ey + 1):
			for dx in range(-cw, cw + 1):
				var xx := int(c2.x) + dx
				if y >= 0 and y < _grid_size and xx >= 0 and xx < _grid_size:
					if _grid[y][xx] == 0:
						_grid[y][xx] = 3
	# 額外隨機連接（增加路徑選擇）
	for _i in range(3):
		if _rooms.size() < 2:
			break
		var a := randi() % _rooms.size()
		var b := randi() % _rooms.size()
		if a != b:
			var c1b: Vector2 = centers[a]
			var c2b: Vector2 = centers[b]
			var cw2 := int(ceil(_corridor_width * 0.5))
			_corridors.append({"x1": int(c1b.x), "y1": int(c1b.y), "x2": int(c2b.x), "y2": int(c2b.y)})
			var sx2 := int(min(c1b.x, c2b.x))
			var ex2 := int(max(c1b.x, c2b.x))
			for x in range(sx2, ex2 + 1):
				for dy in range(-cw2, cw2 + 1):
					var yy := int(c1b.y) + dy
					if yy >= 0 and yy < _grid_size and x >= 0 and x < _grid_size:
						if _grid[yy][x] == 0:
							_grid[yy][x] = 3


func _build_walls_from_grid() -> void:
	# 將格子轉為牆壁矩形（貪婪合併）
	var visited := []
	for y in range(_grid_size):
		var row := []
		for x in range(_grid_size):
			row.append(false)
		visited.append(row)
	for y in range(_grid_size):
		for x in range(_grid_size):
			if visited[y][x]:
				continue
			if _grid[y][x] != 0:
				visited[y][x] = true
				continue
			# 找最大水平延伸
			var end_x := x
			while end_x + 1 < _grid_size and _grid[y][end_x + 1] == 0 and not visited[y][end_x + 1]:
				end_x += 1
			# 找最大垂直延伸
			var end_y := y
			var valid := true
			while end_y + 1 < _grid_size and valid:
				for xx in range(x, end_x + 1):
					if _grid[end_y + 1][xx] != 0 or visited[end_y + 1][xx]:
						valid = false
						break
				if valid:
					end_y += 1
			# 標記已訪問
			for yy in range(y, end_y + 1):
				for xx in range(x, end_x + 1):
					visited[yy][xx] = true
			# 轉為世界座標
			var world_x := (x - _grid_size * 0.5) * _cell_size
			var world_z := (y - _grid_size * 0.5) * _cell_size
			var w := (end_x - x + 1) * _cell_size
			var h := (end_y - y + 1) * _cell_size
			_walls.append({
				"mn": {"x": world_x, "y": 0, "z": world_z},
				"mx": {"x": world_x + w, "y": _wall_height, "z": world_z + h},
				"material": "concrete"
			})


func _place_sites() -> void:
	# 找最大的兩個房間作為 A/B 站點
	var sorted_rooms := _rooms.duplicate()
	sorted_rooms.sort_custom(func(a, b): return (a["w"] * a["h"]) > (b["w"] * b["h"]))
	for i in range(min(2, sorted_rooms.size())):
		var room: Dictionary = sorted_rooms[i]
		var cx: float = (float(room["x"]) + float(room["w"]) * 0.5 - _grid_size * 0.5) * _cell_size
		var cz: float = (float(room["y"]) + float(room["h"]) * 0.5 - _grid_size * 0.5) * _cell_size
		var site_name := "A" if i == 0 else "B"
		_sites.append({
			"name": site_name,
			"center": {"x": cx, "y": 0, "z": cz},
			"radius": 2.0
		})
		# 標記格子
		var gx: int = int(room["x"] + room["w"] * 0.5)
		var gy: int = int(room["y"] + room["h"] * 0.5)
		if gy >= 0 and gy < _grid_size and gx >= 0 and gx < _grid_size:
			_grid[gy][gx] = 4


func _place_spawns() -> void:
	# 攻方重生（地圖左側）
	var left_rooms: Array = _rooms.filter(func(r): return r["x"] + r["w"] * 0.5 < _grid_size * 0.5)
	left_rooms.sort_custom(func(a, b): return a["x"] < b["x"])
	var attacker_room: Dictionary = left_rooms[0] if left_rooms.size() > 0 else _rooms[0]
	for i in range(5):
		var sx: float = (float(attacker_room["x"]) + 1 + i * 2 - _grid_size * 0.5) * _cell_size
		var sz: float = (float(attacker_room["y"]) + float(attacker_room["h"]) * 0.5 - _grid_size * 0.5) * _cell_size
		_spawns_a.append({"x": sx, "y": 0, "z": sz})
	# 守方重生（地圖右側）
	var right_rooms: Array = _rooms.filter(func(r): return r["x"] + r["w"] * 0.5 >= _grid_size * 0.5)
	right_rooms.sort_custom(func(a, b): return a["x"] > b["x"])
	var defender_room: Dictionary = right_rooms[0] if right_rooms.size() > 0 else _rooms[_rooms.size() - 1]
	for i in range(5):
		var sx: float = (float(defender_room["x"]) + 1 + i * 2 - _grid_size * 0.5) * _cell_size
		var sz: float = (float(defender_room["y"]) + float(defender_room["h"]) * 0.5 - _grid_size * 0.5) * _cell_size
		_spawns_d.append({"x": sx, "y": 0, "z": sz})


# ═══════════════════════════════════════════════
#  2D 預覽繪製
# ═══════════════════════════════════════════════
func _draw_grid() -> void:
	# 背景
	draw_rect(Rect2(_preview_offset, _preview_size), Color(0.08, 0.09, 0.12))
	# 格子
	var cell_px := _preview_size.x / _grid_size
	for y in range(_grid_size):
		for x in range(_grid_size):
			var cell: int = _grid[y][x]
			var col: Color
			match cell:
				0: col = Color(0.10, 0.11, 0.14)  # 空地
				1: col = Color(0.25, 0.28, 0.35)   # 牆壁
				2: col = Color(0.18, 0.30, 0.22)   # 房間
				3: col = Color(0.30, 0.25, 0.15)   # 走廊
				4: col = Color(0.9, 0.25, 0.25)    # 站點
				5: col = Color(0.2, 0.6, 0.95)     # 重生點
			var rect := Rect2(
				_preview_offset + Vector2(x * cell_px, y * cell_px),
				Vector2(cell_px, cell_px)
			)
			draw_rect(rect, col)
	# 邊框
	draw_rect(Rect2(_preview_offset, _preview_size), BORDER_DIM, false, 1.0)


func _draw_walls() -> void:
	# 繪製牆壁邊框
	var cell_px := _preview_size.x / _grid_size
	for y in range(_grid_size):
		for x in range(_grid_size):
			if _grid[y][x] != 0:
				continue
			# 檢查四邊是否有非空格子
			var has_wall := false
			for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var nx: int = x + d.x
				var ny: int = y + d.y
				if nx >= 0 and nx < _grid_size and ny >= 0 and ny < _grid_size:
					if _grid[ny][nx] != 0:
						has_wall = true
						break
			if has_wall:
				var rect := Rect2(
					_preview_offset + Vector2(x * cell_px, y * cell_px),
					Vector2(cell_px, cell_px)
				)
				draw_rect(rect, Color(0.4, 0.45, 0.5, 0.6))


func _draw_sites() -> void:
	var cell_px := _preview_size.x / _grid_size
	for site in _sites:
		var gx: float = (float(site["center"]["x"]) / _cell_size + _grid_size * 0.5)
		var gy: float = (float(site["center"]["z"]) / _cell_size + _grid_size * 0.5)
		var pos := _preview_offset + Vector2(gx * cell_px, gy * cell_px)
		# 站點圓圈
		draw_circle(pos, cell_px * 2, Color(0.9, 0.25, 0.25, 0.3))
		draw_circle(pos, cell_px * 2, Color(0.9, 0.25, 0.25), false, 2.0)
		# 站點名稱
		var font := ThemeDB.fallback_font
		draw_string(font, pos + Vector2(-6, 5), site["name"],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color.WHITE)


func _draw_spawns() -> void:
	var cell_px := _preview_size.x / _grid_size
	# 攻方（藍色圓點）
	for sp in _spawns_a:
		var gx: float = (float(sp["x"]) / _cell_size + _grid_size * 0.5)
		var gy: float = (float(sp["z"]) / _cell_size + _grid_size * 0.5)
		var pos := _preview_offset + Vector2(gx * cell_px, gy * cell_px)
		draw_circle(pos, cell_px * 0.6, Color(0.2, 0.6, 0.95))
	# 守方（橙色圓點）
	for sp in _spawns_d:
		var gx: float = (float(sp["x"]) / _cell_size + _grid_size * 0.5)
		var gy: float = (float(sp["z"]) / _cell_size + _grid_size * 0.5)
		var pos := _preview_offset + Vector2(gx * cell_px, gy * cell_px)
		draw_circle(pos, cell_px * 0.6, Color(0.95, 0.6, 0.2))


func _draw_corridors() -> void:
	# 走廊中心線
	var cell_px := _preview_size.x / _grid_size
	for cor in _corridors:
		var p1 := _preview_offset + Vector2(
			(cor["x1"] + 0.5) * cell_px,
			(cor["y1"] + 0.5) * cell_px
		)
		var p2 := _preview_offset + Vector2(
			(cor["x2"] + 0.5) * cell_px,
			(cor["y2"] + 0.5) * cell_px
		)
		draw_line(p1, p2, Color(0.5, 0.45, 0.3, 0.4), 1.0)


# ═══════════════════════════════════════════════
#  資訊更新
# ═══════════════════════════════════════════════
func _update_info() -> void:
	var info: Label = get_node_or_null("InfoLabel")
	if not info:
		info = _find_info_label()
	if info:
		info.text = "房間: %d\n走廊: %d\n牆壁: %d\n站點: %d\n攻方重生: %d\n守方重生: %d\n格子: %dx%d\n種子: %d" % [
			_rooms.size(), _corridors.size(), _walls.size(),
			_sites.size(), _spawns_a.size(), _spawns_d.size(),
			_grid_size, _grid_size, _seed
		]


func _find_info_label() -> Label:
	# 遞迴找 InfoLabel
	for child in get_children():
		if child is PanelContainer:
			for sub in child.get_children():
				if sub is ScrollContainer:
					for sub2 in sub.get_children():
						for sub3 in sub2.get_children():
							if sub3 is Label and sub3.name == "InfoLabel":
								return sub3
	return null


# ═══════════════════════════════════════════════
#  匯出
# ═══════════════════════════════════════════════
func _export_json() -> void:
	var map_data := {
		"bounds_min": {"x": -_grid_size * 0.5 * _cell_size, "y": 0, "z": -_grid_size * 0.5 * _cell_size},
		"bounds_max": {"x": _grid_size * 0.5 * _cell_size, "y": _wall_height, "z": _grid_size * 0.5 * _cell_size},
		"walls": _walls,
		"sites": _sites,
		"spawns_attackers": _spawns_a,
		"spawns_defenders": _spawns_d
	}
	var json_str := JSON.stringify(map_data, "\t")
	var path := "res://assets/maps/%s_seed%d.json" % [_map_name, _seed]
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f:
		f.store_string(json_str)
		f.close()
		_status_label.text = "✅ 已匯出: %s" % path
	else:
		_status_label.text = "❌ 匯出失敗"


func _apply_to_game() -> void:
	# 保存到 VantaGlobal
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		g.custom_map_data = {
			"bounds_min": {"x": -_grid_size * 0.5 * _cell_size, "y": 0, "z": -_grid_size * 0.5 * _cell_size},
			"bounds_max": {"x": _grid_size * 0.5 * _cell_size, "y": _wall_height, "z": _grid_size * 0.5 * _cell_size},
			"walls": _walls,
			"sites": _sites,
			"spawns_attackers": _spawns_a,
			"spawns_defenders": _spawns_d
		}
		_status_label.text = "✅ 已套用到遊戲！開始對戰即可使用"
	else:
		_status_label.text = "❌ VantaGlobal 未找到"
