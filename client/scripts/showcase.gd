extends Node3D

## 動畫展示場 — 武器視角動畫預覽（換槍 / 換彈 / 開火 / 切刀 / 刀揮 / 步態 bob / ADS）
## 操作：1/2/3 切武器 | R 換彈 | 左鍵開火（刀=揮砍）| 右鍵瞄準 | WASD 移動（看 bob）

var cam: Camera3D
var viewmodel: WeaponViewModel
var info: Label
var _yaw := 0.0
var _pitch := 0.0
var _dir := Vector2.ZERO
var _move := Vector3.ZERO
var _speed := 0.0
var _palettes := [
	{"primary": Color(0.25, 0.27, 0.32), "accent": Color(0.85, 0.4, 0.25)},
	{"primary": Color(0.18, 0.22, 0.3), "accent": Color(0.3, 0.7, 1.0)},
	{"primary": Color(0.3, 0.24, 0.2), "accent": Color(1.0, 0.7, 0.2)},
]


func _ready() -> void:
	# 展示舞台：地板 + 柱子 + 光
	_build_stage()
	cam = Camera3D.new()
	cam.fov = 80.0
	cam.position = Vector3(0, 1.6, 0)
	add_child(cam)
	cam.make_current()

	viewmodel = WeaponViewModel.new()
	cam.add_child(viewmodel)
	viewmodel.build_weapon(1, _palettes[0])

	var layer := CanvasLayer.new()
	add_child(layer)
	info = Label.new()
	info.position = Vector2(20, 20)
	info.add_theme_font_size_override("font_size", 20)
	info.text = "動畫展示場 — 1/2/3 切武器 | R 換彈 | 左鍵開火 | 右鍵瞄準 | WASD 移動"
	layer.add_child(info)

	Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)


func _build_stage() -> void:
	var ground := MeshInstance3D.new()
	var gm := PlaneMesh.new()
	gm.size = Vector2(40, 40)
	ground.mesh = gm
	var gmat := StandardMaterial3D.new()
	gmat.albedo_color = Color(0.16, 0.18, 0.22)
	ground.material_override = gmat
	add_child(ground)

	for i in range(8):
		var pillar := MeshInstance3D.new()
		var pm := BoxMesh.new()
		pm.size = Vector3(0.6, 2.5, 0.6)
		pillar.mesh = pm
		var pmat := StandardMaterial3D.new()
		pmat.albedo_color = Color(0.3, 0.32, 0.38)
		pillar.material_override = pmat
		var a := TAU * i / 8.0
		pillar.position = Vector3(cos(a) * 6.0, 1.25, sin(a) * 6.0)
		add_child(pillar)

	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-50, -30, 0)
	add_child(light)
	var hemi := OmniLight3D.new()
	hemi.position = Vector3(0, 4, 0)
	hemi.light_color = Color(0.7, 0.8, 1.0)
	add_child(hemi)


func _process(delta: float) -> void:
	# 移動（world 軸向，展示 bob）
	var f := 0.0
	var s := 0.0
	if Input.is_key_pressed(KEY_W):
		f += 1.0
	if Input.is_key_pressed(KEY_S):
		f -= 1.0
	if Input.is_key_pressed(KEY_D):
		s += 1.0
	if Input.is_key_pressed(KEY_A):
		s -= 1.0
	var fwd := Vector3(sin(_yaw), 0, cos(_yaw))
	var right := Vector3(sin(_yaw + PI / 2), 0, cos(_yaw + PI / 2))
	var wish := fwd * f + right * s
	var target_speed := wish.length() * 3.0
	_speed = lerpf(_speed, target_speed, 1.0 - exp(-10.0 * delta))
	if wish.length() > 0.1:
		cam.position += wish.normalized() * 3.0 * delta

	cam.rotation = Vector3(_pitch, _yaw, 0)
	viewmodel.update(delta, _speed, true, Vector2.ZERO)

	info.text = "動畫展示場 — 1/2/3 切武器 | R 換彈 | Y 檢視武器 | 左鍵開火 | 右鍵瞄準 | WASD 移動\n" \
		+ "目前武器槽位: %d | 狀態: %s" % [viewmodel.weapon_slot, viewmodel._state]


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
		_yaw -= event.relative.x * 0.003
		_pitch -= event.relative.y * 0.003
		_pitch = clampf(_pitch, -1.2, 1.2)
	elif event is InputEventMouseButton and event.pressed:
		match event.button_index:
			MOUSE_BUTTON_LEFT:
				if viewmodel.weapon_slot == 2:
					viewmodel.play_knife()
				else:
					viewmodel.play_fire(randf_range(0.5, 1.5))
			MOUSE_BUTTON_RIGHT:
				viewmodel.set_ads(true)
	elif event is InputEventMouseButton and not event.pressed \
			and event.button_index == MOUSE_BUTTON_RIGHT:
		viewmodel.set_ads(false)
	elif event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_1:
				_switch_to(0)
			KEY_2:
				_switch_to(1)
			KEY_3:
				_switch_to(2)
			KEY_R:
				viewmodel.play_reload(1.4)
			KEY_Y:
				viewmodel.play_inspect()        # 檢視武器（特戰按鍵：Y）
			KEY_ESCAPE:
				Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)


func _switch_to(slot: int) -> void:
	if slot == viewmodel.weapon_slot:
		return
	viewmodel.play_switch_out()
	await get_tree().create_timer(0.18).timeout
	viewmodel.build_weapon(slot, _palettes[slot % _palettes.size()])
	viewmodel.play_switch_in()
