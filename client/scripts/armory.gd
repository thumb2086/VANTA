class_name Armory
extends Node

## 軍械庫（Armory）—— 槍皮瀏覽 / 試槍 / 升級 / Chroma / 裝備
##
## 全部 UI 用程式建立（与本專案其他畫面一致，不需额外 .tscn 资源），
## 資料完全来自 `res://assets/skins.json`（由 tools/cli.py 產生）。
##
## 三個 pane：
##   左：系列列表（含程序化繪製的系列卡，顏色直接取自 colorway）
##   中：3D 試槍視窗（SubViewport + 自己的 FxManager → 可以真的開槍看特效）
##   右：皮膚詳情 + 升級 + Chroma + 裝備
##
## 關閉／出戰會把結果寫回 VantaGlobal（skin_revision++），對局中的 main.gd 會即時重建模型。

const BG := Color(0.045, 0.05, 0.07)
const PANEL := Color(0.09, 0.10, 0.13, 0.92)
const PANEL_HI := Color(0.13, 0.15, 0.19, 0.95)
const LINE := Color(0.28, 0.31, 0.38, 0.55)
const TXT := Color(0.92, 0.93, 0.96)
const TXT_DIM := Color(0.62, 0.66, 0.74)
const ACCENT := Color(0.95, 0.35, 0.32)

const SLOTS := ["主武器", "副武器", "近戰"]
const SLOT_KEYS := {0: ["vandal", "phantom", "bulldog", "guardian", "spectre", "stinger",
	"ares", "odin", "operator", "marshal", "outlaw", "bucky", "judge"],
	1: ["sheriff", "ghost", "classic", "shorty", "frenzy", "bandit"],
	2: ["knife"]}

var registry: SkinRegistry = null
var prog: SkinProgression = null

var _root := Control.new()
var _collections_box := VBoxContainer.new()
var _skin_box := VBoxContainer.new()
var _detail_box := VBoxContainer.new()
var _title := Label.new()
var _money := Label.new()
var _view: SubViewport = null
var _view_cam: Camera3D = null
var _model_root: Node3D = null
var _fx: FxManager = null
var _audio: AudioManager = null
var _finish: Dictionary = {}
var _preview_res: Dictionary = {}
var _selected_coll := ""
var _selected_skin := ""
var _slot_filter := -1
var _rot := 0.0
var _fire_impulse := 0.0
var _card_controls: Array = []
var _level_override := 0
var _chroma_override := -1
var _test_fire_t := -1.0
var _inspect_t := -1.0
var _light_bg: MeshInstance3D = null


func _ready() -> void:
	registry = SkinRegistry.shared()
	if not registry.ready:
		push_warning("[armory] 找不到 res://assets/skins.json")
	prog = _find_profile()
	_build_layout()
	_populate_collections()
	_select_collection(_first_collection())
	_refresh_money()


func _find_profile() -> SkinProgression:
	var tree := get_tree()
	if tree != null:
		var g := tree.root.get_node_or_null("VantaGlobal")
		if g != null and g.has_method("get_skin_progression"):
			return g.call("get_skin_progression")
	var p := SkinProgression.new()
	p.name = "SkinProgression"
	add_child(p)
	return p


# ═══════════════════════════════════════════════════════
#  版面
# ═══════════════════════════════════════════════════════
func _build_layout() -> void:
	var bg := ColorRect.new()
	bg.color = BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	_deco = Control.new()
	var deco := _deco
	deco.name = "Deco"
	deco.set_anchors_preset(Control.PRESET_FULL_RECT)
	deco.mouse_filter = Control.MOUSE_FILTER_IGNORE
	deco.draw.connect(_draw_backdrop)
	add_child(deco)

	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.offset_left = 24
	_root.offset_top = 16
	_root.offset_right = -24
	_root.offset_bottom = -18
	add_child(_root)

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(margin)

	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", 10)
	margin.add_child(outer)

	# ── 頂列 ──
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 12)
	outer.add_child(top)
	_title = Label.new()
	_title.text = "軍械庫   ARMORY"
	_title.add_theme_font_size_override("font_size", 26)
	_title.add_theme_color_override("font_color", TXT)
	top.add_child(_title)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(spacer)
	for slot in range(3):
		var b := Button.new()
		b.text = SLOTS[slot]
		b.custom_minimum_size = Vector2(96, 34)
		b.focus_mode = Control.FOCUS_NONE
		_style_button(b, false)
		b.pressed.connect(_on_slot_filter.bind(slot))
		top.add_child(b)
	_all_btn = Button.new()
	_all_btn.text = "全部"
	_all_btn.custom_minimum_size = Vector2(72, 34)
	_all_btn.focus_mode = Control.FOCUS_NONE
	_style_button(_all_btn, false)
	_all_btn.pressed.connect(_on_slot_filter.bind(-1))
	top.add_child(_all_btn)
	_money = Label.new()
	_money.add_theme_font_size_override("font_size", 17)
	_money.add_theme_color_override("font_color", Color(0.99, 0.83, 0.42))
	top.add_child(_money)

	# ── 三欄 ──
	var cols := HBoxContainer.new()
	cols.add_theme_constant_override("separation", 14)
	cols.size_flags_vertical = Control.SIZE_EXPAND_FILL
	outer.add_child(cols)

	var left := _panel(250)
	cols.add_child(left)
	var left_v := VBoxContainer.new()
	left_v.add_theme_constant_override("separation", 8)
	left.add_child(left_v)
	left_v.add_child(_section_label("系列 COLLECTIONS"))
	var lscroll := ScrollContainer.new()
	lscroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	lscroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	left_v.add_child(lscroll)
	_collections_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lscroll.add_child(_collections_box)

	var mid := _panel(560)
	cols.add_child(mid)
	var mid_v := VBoxContainer.new()
	mid_v.add_theme_constant_override("separation", 8)
	mid.add_child(mid_v)
	var sscroll := ScrollContainer.new()
	sscroll.custom_minimum_size = Vector2(0, 132)
	sscroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	mid_v.add_child(sscroll)
	_skin_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sscroll.add_child(_skin_box)

	var preview := PanelContainer.new()
	preview.size_flags_vertical = Control.SIZE_EXPAND_FILL
	preview.custom_minimum_size = Vector2(0, 330)
	mid_v.add_child(preview)
	var psb := StyleBoxFlat.new()
	psb.bg_color = Color(0.02, 0.023, 0.032)
	psb.border_color = LINE
	psb.set_border_width_all(1)
	psb.corner_radius_top_left = 6
	preview.add_theme_stylebox_override("panel", psb)
	var pc := VBoxContainer.new()
	pc.add_theme_constant_override("separation", 0)
	preview.add_child(pc)
	_view = SubViewport.new()
	_view.size = Vector2i(540, 300)
	_view.own_world_3d = true
	_view.transparent_bg = false
	_view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	var vpc := SubViewportContainer.new()
	vpc.stretch = true
	vpc.size_flags_vertical = Control.SIZE_EXPAND_FILL
	pc.add_child(vpc)
	vpc.add_child(_view)
	_build_preview_world()

	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", 8)
	pc.add_child(bar)
	var fire_btn := Button.new()
	fire_btn.text = "試射  [空白鍵]"
	fire_btn.custom_minimum_size = Vector2(140, 34)
	_style_button(fire_btn, true)
	fire_btn.pressed.connect(_test_fire)
	bar.add_child(fire_btn)
	var insp_btn := Button.new()
	insp_btn.text = "檢視  [Y]"
	_style_button(insp_btn, false)
	insp_btn.pressed.connect(_do_inspect)
	bar.add_child(insp_btn)
	var spin := CheckButton.new()
	spin.text = "自動旋轉"
	spin.button_pressed = true
	spin.toggled.connect(func(on: bool): _auto_spin = on)
	bar.add_child(spin)
	var lvl_box := HBoxContainer.new()
	lvl_box.add_theme_constant_override("separation", 4)
	bar.add_child(lvl_box)
	var lv_dn := Button.new()
	lv_dn.text = "Lv −"
	_style_button(lv_dn, false)
	lv_dn.pressed.connect(func(): _step_level(-1))
	bar.add_child(lv_dn)
	_lvl_lbl = Label.new()
	_lvl_lbl.add_theme_color_override("font_color", TXT)
	bar.add_child(_lvl_lbl)
	var lv_up := Button.new()
	lv_up.text = "Lv +"
	_style_button(lv_up, false)
	lv_up.pressed.connect(func(): _step_level(1))
	bar.add_child(lv_up)
	var ch_btn := Button.new()
	ch_btn.text = "Chroma"
	_style_button(ch_btn, false)
	ch_btn.pressed.connect(_cycle_chroma)
	bar.add_child(ch_btn)
	_chroma_btn = ch_btn

	var right := _panel(320)
	cols.add_child(right)
	var rv := VBoxContainer.new()
	rv.add_theme_constant_override("separation", 8)
	right.add_child(rv)
	rv.add_child(_section_label("詳細 DETAILS"))
	var rscroll := ScrollContainer.new()
	rscroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	rscroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	rv.add_child(rscroll)
	_detail_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rscroll.add_child(_detail_box)

	# ── 底列 ──
	var bottom := HBoxContainer.new()
	bottom.add_theme_constant_override("separation", 10)
	outer.add_child(bottom)
	var back := Button.new()
	back.text = "← 返回主選單  [ESC]"
	back.custom_minimum_size = Vector2(200, 40)
	_style_button(back, false)
	back.pressed.connect(_go_back)
	bottom.add_child(back)
	var hint := Label.new()
	hint.text = "方向鍵／滑鼠瀏覽 · Enter 裝備 · F 購買 · U 升級 · T 試槍 · C 切換 Chroma"
	hint.add_theme_color_override("font_color", TXT_DIM)
	hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hint.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	bottom.add_child(hint)
	var play := Button.new()
	play.text = "出戰  ENTER"
	play.custom_minimum_size = Vector2(180, 40)
	_style_button(play, true)
	play.pressed.connect(_go_battle)
	bottom.add_child(play)


var _all_btn: Button = null
var _lvl_lbl: Label = null
var _chroma_btn: Button = null
var _auto_spin := true


func _panel(w: float) -> PanelContainer:
	var p := PanelContainer.new()
	p.custom_minimum_size = Vector2(w, 0)
	p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var sb := StyleBoxFlat.new()
	sb.bg_color = PANEL
	sb.border_color = LINE
	sb.set_border_width_all(1)
	sb.corner_radius_top_left = 6
	sb.corner_radius_top_right = 6
	sb.corner_radius_bottom_left = 6
	sb.corner_radius_bottom_right = 6
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 12
	sb.content_margin_bottom = 12
	p.add_theme_stylebox_override("panel", sb)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	p.add_child(v)
	return p


func _section_label(text: String) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 12)
	l.add_theme_color_override("font_color", TXT_DIM)
	return l


func _style_button(b: Button, primary: bool) -> void:
	b.focus_mode = Control.FOCUS_NONE
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(ACCENT.r, ACCENT.g, ACCENT.b, 0.92) if primary else Color(0.14, 0.16, 0.2, 0.9)
	sb.border_color = Color(1, 1, 1, 0.12) if primary else LINE
	sb.set_border_width_all(1)
	sb.corner_radius_top_left = 4
	sb.corner_radius_top_right = 4
	sb.corner_radius_bottom_left = 4
	sb.corner_radius_bottom_right = 4
	sb.content_margin_left = 10
	sb.content_margin_right = 10
	b.add_theme_stylebox_override("normal", sb)
	var hv := sb.duplicate()
	hv.bg_color = Color(1.0, 0.45, 0.4) if primary else Color(0.2, 0.23, 0.28, 0.95)
	b.add_theme_stylebox_override("hover", hv)
	b.add_theme_color_override("font_color", TXT)
	b.add_theme_color_override("font_hover_color", Color(1, 1, 1))


var _deco: Control = null


func _draw_backdrop() -> void:
	var c := _root.get_viewport_rect().size
	if _deco == null or c.x < 2.0:
		return
	# 斜向光帶 + 網格：讓背景有「產品頁」質感而不是純黑
	for i in 9:
		var t := float(i) / 9.0
		var col := Color(0.9, 0.35, 0.3, 0.020 + 0.012 * (1.0 - t))
		var lx := c.x * (t * 1.4 - 0.2)
		_deco.draw_line(Vector2(lx, 0), Vector2(lx + c.y * 0.55, c.y),
			col, 90.0)
	for x in range(0, int(c.x), 96):
		_deco.draw_line(Vector2(x, 0), Vector2(x, c.y), Color(1, 1, 1, 0.016), 1.0)
	for y in range(0, int(c.y), 96):
		_deco.draw_line(Vector2(0, y), Vector2(c.x, y), Color(1, 1, 1, 0.016), 1.0)
	_deco.draw_rect(Rect2(Vector2(0, 0), Vector2(c.x, 3)), Color(ACCENT.r, ACCENT.g, ACCENT.b, 0.7))


# ═══════════════════════════════════════════════════════
#  3D 預覽
# ═══════════════════════════════════════════════════════
func _build_preview_world() -> void:
	var env := WorldEnvironment.new()
	var we := Environment.new()
	we.background_mode = Environment.BG_COLOR
	we.background_color = Color(0.03, 0.033, 0.048)
	we.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	we.ambient_light_color = Color(0.55, 0.6, 0.75)
	we.ambient_light_energy = 0.55
	env.environment = we
	_view.add_child(env)

	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-52, 38, -12)
	key.light_energy = 1.25
	key.light_color = Color(1.0, 0.97, 0.92)
	_view.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(18, -140, 0)
	fill.light_energy = 0.45
	fill.light_color = Color(0.55, 0.7, 1.0)
	_view.add_child(fill)

	_model_root = Node3D.new()
	_view.add_child(_model_root)

	_view_cam = Camera3D.new()
	_view_cam.fov = 45.0
	_view_cam.position = Vector3(0.42, 0.16, 0.85)
	_view_cam.look_at_from_position(Vector3(0.42, 0.16, 0.85), Vector3(0, 0, -0.05), Vector3.UP)
	_view.add_child(_view_cam)
	_view_cam.make_current()

	# 試槍用的特效管理器（只在預覽世界內活動）
	_fx = FxManager.new()
	_fx.name = "PreviewFx"
	_view.add_child(_fx)
	_fx.setup(registry, _view_cam, null, null, null)
	_fx.quality = 2

	# 聲音（合成 SFX，不需音檔）
	_audio = AudioManager.new()
	add_child(_audio)
	var idx := _load_json("res://assets/asset_index.json")
	if idx.is_empty():
		_audio = null
	else:
		_audio.setup(idx, _load_json("res://assets/fx/event_bindings.json"))


func _load_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}


## 重建預覽槍械（換皮膚／換 Chroma／換等級）
func _rebuild_preview() -> void:
	_preview_res = _resolve_preview()
	if _model_root == null:
		return
	if not _finish.is_empty():
		WeaponFinish.clear(_model_root, _finish)
		_finish = {}
	for c in _model_root.get_children():
		c.queue_free()
	if _preview_res.is_empty():
		return
	_finish = WeaponFinish.build(_model_root, _preview_res, registry, {
		"textures": true, "texture_size": ProceduralTexture.SIZE_PREVIEW,
		"uv_density": 2.0, "scale": 1.35,
	})
	_fx.set_skin_resolution(_preview_res)
	_rot = -0.35


func _resolve_preview() -> Dictionary:
	if _selected_skin == "" or registry == null:
		return {}
	var level := _level_override if _level_override > 0 else (
		prog.level_of(_selected_skin) if prog != null else 1)
	var chroma := _chroma_override if _chroma_override >= 0 else (
		prog.chroma_of(_selected_skin) if prog != null else 0)
	return registry.resolve(_selected_skin, {"level": level, "chroma": chroma})


func _test_fire() -> void:
	if _preview_res.is_empty():
		return
	_fire_impulse = 1.0
	_test_fire_t = 0.0
	var fx: Dictionary = _preview_res.get("fx", {})
	var dir := -_view_cam.global_transform.basis.z
	var muzzle_pos := _model_root.global_transform.origin + dir * 0.55
	var xf := Transform3D(Basis.looking_at(dir, Vector3.UP), muzzle_pos)
	var impact := {"point": _model_root.global_transform.origin + dir * 6.0, "normal": -dir}
	if _fx != null:
		_fx.fire(xf, dir, impact, _preview_res, _preview_res.get("weapon", "") == "knife")
	var skey := String(fx.get("sound_key", ""))
	if _audio != null and skey != "":
		_audio.play_synth(skey, float(fx.get("sound_pitch", 1.0)),
			float(fx.get("sound_gain_db", 0.0)))
	elif _audio != null:
		_audio.play_synth(String(_preview_res.get("weapon", "phantom")), 1.0, -6.0)


func _do_inspect() -> void:
	_inspect_t = 0.0


func _step_level(d: int) -> void:
	if _selected_skin == "":
		return
	var sk: Dictionary = registry.skin(_selected_skin)
	var mx := 1 + int((sk.get("upgrades", []) as Array).size())
	_level_override = clampi((_level_override if _level_override > 0 else 1) + d, 1, maxi(1, mx))
	_rebuild_preview()
	_refresh_detail()


func _cycle_chroma() -> void:
	if _selected_skin == "":
		return
	var cnt: int = 0
	var s: Dictionary = registry.skin(_selected_skin)
	cnt = 1 + int((s.get("chroma", []) as Array).size())
	if cnt <= 1:
		return
	_chroma_override = ((_chroma_override if _chroma_override >= 0 else 0) + 1) % cnt
	_rebuild_preview()
	_refresh_detail()


func _process(delta: float) -> void:
	_rot += delta * (0.55 if _auto_spin else 0.0)
	_fire_impulse = maxf(0.0, _fire_impulse - delta * 5.5)
	if _test_fire_t >= 0.0:
		_test_fire_t += delta
		if _test_fire_t > 3.0:
			_test_fire_t = -1.0
	if _inspect_t >= 0.0:
		_inspect_t += delta
		if _inspect_t > 2.4:
			_inspect_t = -1.0
	if _model_root != null and not _finish.is_empty():
		var ads := 0.0
		WeaponFinish.tick(_finish, delta, _fire_impulse, ads, -1.0, 0.0,
			Vector3(sin(_rot * 1.7) * 0.4, cos(_rot * 1.3) * 0.4, 0))
		var tilt := 0.0
		var lift := 0.0
		if _inspect_t >= 0.0:
			# 檢視：翻到側面仔細看（傳說皮的「舉起武器」動感）
			var u := clampf(_inspect_t / 2.4, 0.0, 1.0)
			var k := sin(u * PI)
			tilt = k * 0.55
			lift = k * 0.06
			_model_root.rotation.y = _rot + k * 1.35
		else:
			_model_root.rotation.y = _rot
		_model_root.rotation.z = tilt
		_model_root.position.y = sin(_rot * 0.9) * 0.006 + lift
	elif _model_root != null:
		_model_root.rotation.y = _rot


# ═══════════════════════════════════════════════════════
#  列表
# ═══════════════════════════════════════════════════════
func _first_collection() -> String:
	for c in registry.collections:
		var tier := String(c.get("tier", ""))
		if tier != "standard":
			return String(c.get("id", ""))
	return String(registry.collections[0].get("id", "")) if not registry.collections.is_empty() else ""


func _on_slot_filter(slot: int) -> void:
	_slot_filter = slot
	_populate_collections()
	var coll := _selected_coll
	_select_collection(coll if _collection_has_slot(coll) else _first_collection())


func _collection_has_slot(coll: String) -> bool:
	if _slot_filter < 0:
		return true
	for s in registry.skins_for_collection(coll):
		if String(s.get("weapon", "")) in SLOT_KEYS.get(_slot_filter, []):
			return true
	return false


func _populate_collections() -> void:
	for c in _collections_box.get_children():
		c.queue_free()
	_card_controls.clear()
	for coll in registry.collections:
		var cid := String(coll.get("id", ""))
		if _slot_filter >= 0 and not _collection_has_slot(cid):
			continue
		_collections_box.add_child(_make_collection_row(coll))


func _make_collection_row(coll: Dictionary) -> Control:
	var cid := String(coll.get("id", ""))
	var card := Button.new()
	card.flat = true
	card.custom_minimum_size = Vector2(0, 84)
	card.focus_mode = Control.FOCUS_NONE
	card.alignment = HORIZONTAL_ALIGNMENT_LEFT
	card.pressed.connect(_select_collection.bind(cid))
	_style_button(card, false)
	# 左側色條 = 系列色
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.11, 0.125, 0.16, 0.92)
	var tc := SkinRegistry.hex_color(coll.get("tier_color", "#8f96a3"), TXT)
	sb.border_color = tc
	sb.border_width_left = 4
	sb.border_width_top = 1
	sb.border_width_bottom = 1
	sb.border_width_right = 1
	sb.corner_radius_top_left = 3
	sb.corner_radius_bottom_left = 3
	sb.content_margin_left = 10
	sb.content_margin_top = 6
	sb.content_margin_bottom = 6
	card.add_theme_stylebox_override("normal", sb)
	var hv := sb.duplicate()
	hv.bg_color = PANEL_HI
	card.add_theme_stylebox_override("hover", hv)
	card.add_theme_stylebox_override("pressed", hv)

	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 10)
	card.add_child(hb)
	var art_draw := Control.new()
	art_draw.custom_minimum_size = Vector2(96, 62)
	art_draw.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var skins: Array = registry.skins_for_collection(cid)
	art_draw.draw.connect(_draw_collection_art.bind(art_draw, coll, skins))
	_card_controls.append(art_draw)
	hb.add_child(art_draw)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 2)
	vb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hb.add_child(vb)
	var name_l := Label.new()
	name_l.text = String(coll.get("name", cid))
	name_l.add_theme_font_size_override("font_size", 15)
	name_l.add_theme_color_override("font_color", TXT)
	vb.add_child(name_l)
	var sub := Label.new()
	sub.text = "%s · %d 支" % [String(coll.get("tier_label", "")), skins.size()]
	sub.add_theme_font_size_override("font_size", 11)
	sub.add_theme_color_override("font_color", tc)
	vb.add_child(sub)
	if cid == _selected_coll:
		card.modulate = Color(1.12, 1.12, 1.18)
	return card


## 系列卡：直接用 colorway 畫（無外部圖檔；SVG 卡是工具鏈/網頁輸出）
func _draw_collection_art(c: Control, coll: Dictionary, skins: Array) -> void:
	var sz := c.size
	if sz.x < 2.0:
		return
	var cw: Dictionary = {}
	if not skins.is_empty():
		cw = skins[0].get("colorway", {})
	var primary := SkinRegistry.hex_color(cw.get("primary", "#24272f"), Color(0.14, 0.15, 0.19))
	var secondary := SkinRegistry.hex_color(cw.get("secondary", "#12141a"), Color(0.07, 0.08, 0.10))
	var accent := SkinRegistry.hex_color(cw.get("accent", "#ff7a35"), Color(1, 0.48, 0.21))
	var emis := SkinRegistry.hex_color(cw.get("emissive", "#ff9d4d"), accent)
	c.draw_rect(Rect2(Vector2.ZERO, sz), secondary)
	# 對角漸層帶
	for i in 8:
		var t := float(i) / 7.0
		var col := SkinRegistry.lerp_color(primary, accent, t * 0.55)
		c.draw_colored_polygon(PackedVector2Array([
			Vector2(sz.x * (t * 1.2 - 0.35), 0), Vector2(sz.x * (t * 1.2 - 0.15), 0),
			Vector2(sz.x * (t * 1.2 - 0.45), sz.y), Vector2(sz.x * (t * 1.2 - 0.25), sz.y)]),
			Color(col.r, col.g, col.b, 0.55))
	# 發光節點（呼應「沿脊線發光」的槍皮紋路）
	var seed := int(abs(hash(String(coll.get("id", "")))))
	for k in 14:
		var hx := float((seed + k * 37) % 100) / 100.0
		var hy := float((seed * 3 + k * 53) % 100) / 100.0
		var p := Vector2(hx * sz.x, hy * sz.y)
		var r := 1.4 + float((seed + k * 17) % 5) * 0.5
		c.draw_circle(p, r * 2.6, Color(emis.r, emis.g, emis.b, 0.10))
		c.draw_circle(p, r, Color(emis.r, emis.g, emis.b, 0.85))
	var bar := Color(accent.r, accent.g, accent.b, 0.9)
	c.draw_rect(Rect2(Vector2(0, sz.y - 3), Vector2(sz.x, 3)), bar)
	c.draw_rect(Rect2(Vector2.ZERO, sz), Color(1, 1, 1, 0.10), false, 1.0)


func _select_collection(cid: String) -> void:
	_selected_coll = cid
	_populate_skins()
	_populate_collections()
	var skins: Array = registry.skins_for_collection(cid)
	if not skins.is_empty():
		_select_skin(String(_filter_skins(skins)[0].get("id", "")))


func _filter_skins(skins: Array) -> Array:
	if _slot_filter < 0:
		return skins
	var out: Array = []
	for s in skins:
		if String(s.get("weapon", "")) in SLOT_KEYS.get(_slot_filter, []):
			out.append(s)
	return out if not out.is_empty() else skins


func _populate_skins() -> void:
	for c in _skin_box.get_children():
		c.queue_free()
	var skins: Array = _filter_skins(registry.skins_for_collection(_selected_coll))
	var flow := HFlowContainer.new()
	flow.add_theme_constant_override("h_separation", 8)
	flow.add_theme_constant_override("v_separation", 8)
	_skin_box.add_child(flow)
	for s in skins:
		flow.add_child(_make_skin_chip(s))


func _make_skin_chip(s: Dictionary) -> Control:
	var id := String(s.get("id", ""))
	var owned: bool = prog != null and prog.is_skin_unlocked(id)
	var b := Button.new()
	b.flat = true
	b.custom_minimum_size = Vector2(150, 54)
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(_select_skin.bind(id))
	var sb := StyleBoxFlat.new()
	var cw: Dictionary = s.get("colorway", {})
	sb.bg_color = Color(0.115, 0.13, 0.165, 0.95) if owned else Color(0.075, 0.085, 0.11, 0.9)
	sb.border_color = SkinRegistry.hex_color(s.get("tier_color", "#8f96a3"), LINE)
	sb.set_border_width_all(1)
	sb.border_width_left = 3
	sb.content_margin_left = 8
	sb.content_margin_top = 4
	sb.content_margin_bottom = 4
	b.add_theme_stylebox_override("normal", sb)
	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 8)
	b.add_child(hb)
	var sw := ColorRect.new()
	sw.custom_minimum_size = Vector2(10, 34)
	sw.mouse_filter = Control.MOUSE_FILTER_IGNORE
	sw.color = SkinRegistry.hex_color(cw.get("primary", "#2b2f38"), Color(0.2, 0.2, 0.25))
	hb.add_child(sw)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 0)
	hb.add_child(vb)
	var n := Label.new()
	n.text = String(s.get("weapon_label", s.get("weapon", ""))).split(" ")[0]
	n.add_theme_font_size_override("font_size", 14)
	n.add_theme_color_override("font_color", TXT)
	vb.add_child(n)
	var st := Label.new()
	st.text = ("已擁有 · Lv%d" % prog.level_of(id)) if owned else "%d VP" % int(s.get("price_vp", 0))
	st.add_theme_font_size_override("font_size", 10)
	st.add_theme_color_override("font_color", Color(0.55, 0.9, 0.6) if owned else TXT_DIM)
	vb.add_child(st)
	if id == _selected_skin:
		b.modulate = Color(1.2, 1.2, 1.28)
	return b


func _select_skin(id: String) -> void:
	_selected_skin = id
	_level_override = 0
	_chroma_override = -1
	_populate_skins()
	_rebuild_preview()
	_refresh_detail()
	_refresh_money()


# ═══════════════════════════════════════════════════════
#  右欄：詳情 / 購買 / 升級
# ═══════════════════════════════════════════════════════
func _refresh_detail() -> void:
	for c in _detail_box.get_children():
		c.queue_free()
	if _selected_skin == "":
		var l := Label.new()
		l.text = "請選擇皮膚"
		l.add_theme_color_override("font_color", TXT_DIM)
		_detail_box.add_child(l)
		return
	var s: Dictionary = registry.skin(_selected_skin)
	var res := _resolve_preview()
	var tc := SkinRegistry.hex_color(s.get("tier_color", "#8f96a3"), TXT)

	var nm := Label.new()
	nm.text = String(s.get("name", ""))
	nm.add_theme_font_size_override("font_size", 20)
	nm.add_theme_color_override("font_color", tc)
	nm.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail_box.add_child(nm)

	var sub := Label.new()
	sub.text = "%s · %s" % [String(s.get("collection_name", "")), String(s.get("tier_label", ""))]
	sub.add_theme_font_size_override("font_size", 12)
	sub.add_theme_color_override("font_color", TXT_DIM)
	_detail_box.add_child(sub)

	var desc := Label.new()
	desc.text = String(s.get("desc", ""))
	desc.add_theme_font_size_override("font_size", 12)
	desc.add_theme_color_override("font_color", Color(0.82, 0.84, 0.9))
	desc.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	desc.custom_minimum_size = Vector2(0, 58)
	_detail_box.add_child(desc)

	# 色板條
	var swatches := HBoxContainer.new()
	swatches.add_theme_constant_override("separation", 4)
	_detail_box.add_child(swatches)
	var cw: Dictionary = res.get("colorway", {})
	for key in ["primary", "secondary", "accent", "emissive", "rim_color"]:
		var r := ColorRect.new()
		r.custom_minimum_size = Vector2(26, 26)
		r.mouse_filter = Control.MOUSE_FILTER_IGNORE
		r.color = SkinRegistry.hex_color(cw.get(key, "#888888"), Color(0.4, 0.4, 0.45))
		swatches.add_child(r)

	# 特效規格（讓玩家「看得見」特效升級）
	var fx: Dictionary = res.get("fx", {})
	_detail_box.add_child(_kv("特效風格", String(registry.effects.get("style_meta", {})
		.get(String(fx.get("style", "default")), {}).get("label", "基準"))))
	_detail_box.add_child(_kv("曳光", String(fx.get("tracer_style", "bolt"))))
	_detail_box.add_child(_kv("命中", String(fx.get("impact_style", "cone"))))
	_detail_box.add_child(_kv("擊殺", String(fx.get("kill_style", "burst"))))
	_detail_box.add_child(_kv("音效", String(fx.get("sound_key", "武器基準"))))
	var feats: Array = res.get("features", [])
	if not feats.is_empty():
		var fl := Label.new()
		fl.text = "特徵：" + " / ".join(PackedStringArray(feats))
		fl.add_theme_font_size_override("font_size", 11)
		fl.add_theme_color_override("font_color", TXT_DIM)
		fl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_detail_box.add_child(fl)

	# 價格 / 擁有狀態
	var owned: bool = prog != null and prog.is_skin_unlocked(_selected_skin)
	var price := int(s.get("price_vp", 0))
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 8)
	_detail_box.add_child(line)
	var price_l := Label.new()
	price_l.text = ("已擁有" if owned else "%s VP" % _fmt(price))
	price_l.add_theme_font_size_override("font_size", 17)
	price_l.add_theme_color_override("font_color",
		Color(0.55, 0.9, 0.6) if owned else Color(0.99, 0.83, 0.42))
	line.add_child(price_l)
	if not owned:
		var buy := Button.new()
		buy.text = "購買  [F]"
		buy.custom_minimum_size = Vector2(110, 34)
		_style_button(buy, true)
		buy.disabled = prog == null or prog.player_vp < price
		buy.pressed.connect(_buy)
		line.add_child(buy)
	else:
		var eq := Button.new()
		var legacy := int(s.get("legacy_weapon_id", 0))
		var equipped := prog != null and prog.get_equipped_skin(legacy) == _selected_skin
		eq.text = "已裝備" if equipped else "裝備  [Enter]"
		eq.custom_minimum_size = Vector2(110, 34)
		_style_button(eq, not equipped)
		eq.pressed.connect(_equip)
		line.add_child(eq)

	# 升級軌（Radianite）
	var ups: Array = s.get("upgrades", [])
	if not ups.is_empty():
		_detail_box.add_child(_section_label("RADIANITE 升級"))
		var cur_level := _level_override if _level_override > 0 else prog.level_of(_selected_skin)
		for u in ups:
			var row := HBoxContainer.new()
			row.add_theme_constant_override("separation", 6)
			_detail_box.add_child(row)
			var got := cur_level >= int(u.get("level", 99))
			var dot := ColorRect.new()
			dot.custom_minimum_size = Vector2(8, 8)
			dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
			dot.color = tc if got else Color(0.3, 0.32, 0.38)
			row.add_child(dot)
			var tl := Label.new()
			tl.text = "Lv%d  %s" % [int(u.get("level", 0)), String(u.get("name", ""))]
			tl.add_theme_font_size_override("font_size", 12)
			tl.add_theme_color_override("font_color", TXT if got else TXT_DIM)
			tl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			tl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			row.add_child(tl)
			if prog != null and not got:
				var cost := int(u.get("radianite", 20))
				var ub := Button.new()
				ub.text = "%d" % cost
				ub.custom_minimum_size = Vector2(52, 26)
				_style_button(ub, false)
				ub.disabled = prog.player_radianite < cost or cur_level + 1 != int(u.get("level", 0))
				ub.pressed.connect(_upgrade)
				row.add_child(ub)
		var note := Label.new()
		note.text = "預覽用 Lv%d；購買後在對局中生效" % cur_level if not owned else "目前 Lv%d" % cur_level
		note.add_theme_font_size_override("font_size", 11)
		note.add_theme_color_override("font_color", TXT_DIM)
		_detail_box.add_child(note)

	# Chroma
	var chroma_list: Array = s.get("chroma", [])
	if not chroma_list.is_empty():
		_detail_box.add_child(_section_label("CHROMA 色板"))
		var crow := HBoxContainer.new()
		crow.add_theme_constant_override("separation", 6)
		_detail_box.add_child(crow)
		var cur_idx := _chroma_override if _chroma_override >= 0 else prog.chroma_of(_selected_skin)
		var orig := Button.new()
		orig.text = "原版"
		orig.custom_minimum_size = Vector2(56, 26)
		_style_button(orig, cur_idx == 0)
		orig.pressed.connect(_set_chroma.bind(0))
		crow.add_child(orig)
		for i in chroma_list.size():
			var ch: Dictionary = chroma_list[i]
			var b2 := Button.new()
			b2.text = String(ch.get("name", "Chroma %d" % (i + 1)))
			b2.custom_minimum_size = Vector2(72, 26)
			_style_button(b2, cur_idx == i + 1)
			b2.pressed.connect(_set_chroma.bind(i + 1))
			crow.add_child(b2)
		if cur_idx > 0 and prog != null and prog.level_of(_selected_skin) < 3 and owned:
			var warn := Label.new()
			warn.text = "· Chroma 需先升級至 Lv3"
			warn.add_theme_font_size_override("font_size", 11)
			warn.add_theme_color_override("font_color", Color(1, 0.6, 0.35))
			_detail_box.add_child(warn)
	if _lvl_lbl != null:
		_lvl_lbl.text = "Lv%d" % (res.get("level", 1))
	if _chroma_btn != null:
		_chroma_btn.visible = not chroma_list.is_empty()


func _set_chroma(idx: int) -> void:
	_chroma_override = idx
	if prog != null:
		prog.set_chroma(_selected_skin, idx)
	_rebuild_preview()
	_refresh_detail()


func _kv(k: String, v: String) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	var a := Label.new()
	a.text = k
	a.add_theme_font_size_override("font_size", 11)
	a.add_theme_color_override("font_color", TXT_DIM)
	a.custom_minimum_size = Vector2(66, 0)
	row.add_child(a)
	var b := Label.new()
	b.text = v
	b.add_theme_font_size_override("font_size", 11)
	b.add_theme_color_override("font_color", TXT)
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(b)
	return row


func _fmt(v: int) -> String:
	var s := str(v)
	var out := ""
	var c := 0
	for i in range(s.length() - 1, -1, -1):
		out = s[i] + out
		c += 1
		if c % 3 == 0 and i > 0:
			out = "," + out
	return out


func _refresh_money() -> void:
	if prog == null:
		return
	_money.text = "%s VP    %d Radianite    等級 %d" % [_fmt(prog.player_vp),
		prog.player_radianite, prog.player_level]


func _buy() -> void:
	if prog == null or _selected_skin == "":
		return
	if prog.buy_skin_vp(_selected_skin):
		_selected_coll = _selected_coll
		_populate_skins()
		_rebuild_preview()
		_refresh_detail()
		_refresh_money()
		_notify()


func _equip() -> void:
	if prog == null or _selected_skin == "":
		return
	var s: Dictionary = registry.skin(_selected_skin)
	prog.equip_skin(int(s.get("legacy_weapon_id", 0)), _selected_skin)
	_refresh_detail()
	_populate_skins()
	_notify()


func _upgrade() -> void:
	if prog == null or _selected_skin == "":
		return
	if prog.upgrade_with_radianite(_selected_skin):
		_level_override = 0
		_rebuild_preview()
		_refresh_detail()
		_refresh_money()
		_notify()


func _notify() -> void:
	var g := get_tree().root.get_node_or_null("VantaGlobal")
	if g != null and g.has_method("notify_skins_changed"):
		g.call("notify_skins_changed")


func _go_back() -> void:
	_notify()
	get_tree().change_scene_to_file("res://menu.tscn")


func _go_battle() -> void:
	_notify()
	get_tree().change_scene_to_file("res://main.tscn")


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_ESCAPE:
				_go_back()
			KEY_SPACE:
				_test_fire()
			KEY_T:
				_test_fire()
			KEY_Y:
				_do_inspect()
			KEY_F:
				_buy()
			KEY_U:
				_upgrade()
			KEY_C:
				_cycle_chroma()
			KEY_ENTER:
				_equip()
			KEY_LEFT, KEY_A:
				_move_selection(-1)
			KEY_RIGHT, KEY_D:
				_move_selection(1)
			KEY_UP, KEY_W:
				_move_collection(-1)
			KEY_DOWN, KEY_S:
				_move_collection(1)


func _move_selection(d: int) -> void:
	var skins: Array = _filter_skins(registry.skins_for_collection(_selected_coll))
	var idx := -1
	for i in skins.size():
		if String(skins[i].get("id", "")) == _selected_skin:
			idx = i
	idx = clampi(idx + d, 0, skins.size() - 1)
	if idx >= 0 and idx < skins.size():
		_select_skin(String(skins[idx].get("id", "")))


func _move_collection(d: int) -> void:
	var ids: Array = []
	for c in registry.collections:
		if _slot_filter < 0 or _collection_has_slot(String(c.get("id", ""))):
			ids.append(String(c.get("id", "")))
	if ids.is_empty():
		return
	var idx := ids.find(_selected_coll)
	idx = clampi(idx + d, 0, ids.size() - 1)
	_select_collection(String(ids[idx]))
