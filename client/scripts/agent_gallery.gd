class_name AgentGallery
extends Control

## 角色畫廊：顯示「人物產生器」產生的角色（頭像 SVG + 代號 + 定位）。
## TAB 切換顯示。

const CELL := 132

var visible_now: bool = false

var _grid: GridContainer


func setup(index: Dictionary) -> void:
	# 半透明背景
	var bg := ColorRect.new()
	bg.color = Color(0.05, 0.06, 0.08, 0.88)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# 標題
	var title := Label.new()
	title.text = "VANTA 角色圖鑑（可程式化人物產生器）"
	title.add_theme_font_size_override("font_size", 26)
	title.position = Vector2(20, 16)
	add_child(title)

	# 角色網格
	_grid = GridContainer.new()
	_grid.columns = 6
	_grid.position = Vector2(24, 64)
	add_child(_grid)

	var agents: Array = index.get("agents", [])
	var portraits: Dictionary = {}
	for path in index.get("agent_portraits", []):
		var key := String(path).get_file().get_basename()
		portraits[key] = path

	for path in agents:
		var f := FileAccess.open(path, FileAccess.READ)
		if f == null:
			continue
		var data: Dictionary = JSON.parse_string(f.get_as_text())
		_add_card(data, portraits.get(data.get("key", ""), ""))

	visible = false


func toggle() -> void:
	visible_now = not visible_now
	visible = visible_now


func _add_card(data: Dictionary, portrait_path: String) -> void:
	var cell := VBoxContainer.new()
	cell.custom_minimum_size = Vector2(CELL, CELL + 34)

	var tex := TextureRect.new()
	tex.custom_minimum_size = Vector2(CELL, CELL)
	tex.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	tex.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	var tex_tex: ImageTexture = _load_svg(portrait_path)
	if tex_tex != null:
		tex.texture = tex_tex
	cell.add_child(tex)

	var name_lbl := Label.new()
	name_lbl.text = "%s（%s）" % [data.get("codename", "?"), data.get("role_label", "?")]
	name_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_lbl.add_theme_font_size_override("font_size", 14)
	cell.add_child(name_lbl)

	var kit: Array = data.get("kit", [])
	var kit_lbl := Label.new()
	kit_lbl.text = " ".join(PackedStringArray(kit))
	kit_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	kit_lbl.add_theme_font_size_override("font_size", 11)
	kit_lbl.modulate = Color(0.75, 0.8, 0.9)
	cell.add_child(kit_lbl)

	_grid.add_child(cell)


func _load_svg(path: String) -> ImageTexture:
	if path == "":
		return null
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return null
	var img := Image.new()
	var err: int = img.load_svg_from_buffer(f.get_buffer(f.get_length()))
	if err != OK:
		return null
	img.resize(CELL, CELL, Image.INTERPOLATE_LANCZOS)
	return ImageTexture.create_from_image(img)
