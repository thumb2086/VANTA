class_name ScreenFx
extends CanvasLayer

## 螢幕後特效 / 鏡頭手感（創傷式 Shake + 閃光 + 暗角 + 速度線 + 受擊方向）
##
## 為什麼不用 WorldEnvironment 的 glow/bloom：本项目跑在 GL Compatibility 渲染器，
## 部分環境效果會被忽略。這裡用「疊加繪製 + 鏡頭微動」保證在任意渲染器都有
## 一致的打擊感，同時 main.gd 仍然設了 glow 參數（Forward+ 下會更漂亮）。
##
## 震動用 trauma^2 曲線（业界標準做法）：小幅度時幾乎不影響瞄準，
## 大幅度（擊殺、被爆頭）才有明顯「撞到」的感覺。

const DECAY := 1.75

var camera: Camera3D = null
var base_fov := 90.0
var intensity := 1.0        # 使用者可調（0 = 關閉鏡頭晃動）
var ads_amount := 0.0       # 0..1，瞄準時压低晃動、加深暗角
var speed_amount := 0.0     # 0..1，衝刺速度線
var low_health := 0.0       # 0..1
var scope_mode := false     # 開鏡（Operator/Marshal）黑邊
var hit_tint := Color(0.9, 0.1, 0.1)

var _trauma := 0.0
var _fov_kick := 0.0
var _flash_color := Color(1, 1, 1)
var _flash := 0.0
var _kill_glow := 0.0
var _kill_color := Color(1, 0.85, 0.4)
var _t := 0.0
var _hit_dirs: Array = []
var _overlay: Control = null
var _shake := Vector3.ZERO
var _roll := 0.0
var _quality := 1


class Overlay extends Control:
	var owner_fx: Node = null

	func _ready() -> void:
		set_anchors_preset(Control.PRESET_FULL_RECT)
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		set_process(true)

	func _process(_delta: float) -> void:
		if owner_fx != null and is_instance_valid(owner_fx):
			queue_redraw()

	func _draw() -> void:
		if owner_fx != null and is_instance_valid(owner_fx):
			owner_fx.draw_overlay(self)


func _ready() -> void:
	layer = 6
	_overlay = Overlay.new()
	_overlay.owner_fx = self
	_overlay.name = "Overlay"
	add_child(_overlay)
	set_process(true)


func configure(trauma_scale: float = 1.0, quality: int = 1) -> void:
	intensity = clampf(trauma_scale, 0.0, 2.0)
	_quality = quality


func position_offset() -> Vector3:
	return _shake


func roll() -> float:
	return _roll


func fov_delta() -> float:
	return _fov_kick


# ─── 外部觸發 ────────────────────────────────────────────
func add_trauma(amount: float) -> void:
	_trauma = clampf(_trauma + amount * intensity, 0.0, 1.0)


func add_fov_kick(amount: float) -> void:
	_fov_kick += amount * intensity * 0.55


func flash(color: Color, energy: float = 0.5) -> void:
	_flash_color = color
	_flash = maxf(_flash, clampf(energy, 0.0, 1.6))


func on_kill(color: Color) -> void:
	_kill_glow = 1.0
	_kill_color = color
	flash(Color(color.r, color.g, color.b, 1.0), 0.22)
	add_trauma(0.16)


func on_hit(direction_angle: float, damage_ratio: float, from_right: bool) -> void:
	_hit_dirs.append({"angle": direction_angle, "t": 0.0, "k": clampf(damage_ratio, 0.15, 1.0),
		"right": from_right})
	if _hit_dirs.size() > 5:
		_hit_dirs.pop_front()
	flash(hit_tint, 0.16 + damage_ratio * 0.30)
	add_trauma(0.10 + damage_ratio * 0.22)


func set_scope(on: bool) -> void:
	scope_mode = on


## HUD 動詞（FxManager 找不到 HUD 時的退回介面）
func hit_marker(_color: Color, _headshot: bool) -> void:
	add_trauma(0.03)


func pulse_hud(preset: String, color: Color) -> void:
	match preset:
		"spike_plant":
			flash(Color(color.r, color.g, color.b, 1.0), 0.5)
			add_trauma(0.25)
		"spike_defuse":
			flash(Color(0.4, 0.9, 1.0, 1.0), 0.35)
		"round_win":
			flash(Color(color.r, color.g, color.b, 1.0), 0.7)
			_kill_glow = 1.0
			_kill_color = color
		_:
			flash(color, 0.25)


# ─── 每幀 ───────────────────────────────────────────────
func _process(delta: float) -> void:
	_t += delta
	_trauma = maxf(0.0, _trauma - delta * DECAY)
	_fov_kick = lerpf(_fov_kick, 0.0, clampf(delta * 9.0, 0.0, 1.0))
	_flash = maxf(0.0, _flash - delta * 4.2)
	_kill_glow = maxf(0.0, _kill_glow - delta * 1.35)
	var amp := _trauma * _trauma
	# 兩個不同頻率的正弦疊加 → 比純隨機更像「撞擊」（也避免抖動感）
	var s1 := sin(_t * 47.0) * 0.6 + sin(_t * 31.3 + 1.7) * 0.4
	var s2 := cos(_t * 39.7) * 0.55 + sin(_t * 23.1 + 0.9) * 0.45
	var damp := lerpf(1.0, 0.45, ads_amount)
	_shake = Vector3(s1 * 0.052, s2 * 0.048, s1 * 0.02) * amp * damp
	_roll = s2 * 2.6 * amp * damp
	for i in range(_hit_dirs.size() - 1, -1, -1):
		var h: Dictionary = _hit_dirs[i]
		h["t"] = float(h["t"]) + delta
		if float(h["t"]) > 1.1:
			_hit_dirs.remove_at(i)


## 實際套用到攝影機（main.gd 在自己的攝影機更新之後呼叫）
func apply_to_camera(base_position: Vector3, base_rotation_deg: Vector2, fov: float) -> void:
	if camera == null or not is_instance_valid(camera):
		return
	camera.position = base_position + position_offset()
	var rot := base_rotation_deg
	rot.y += _roll
	camera.rotation_degrees = Vector3(rot.x, rot.y, _roll)
	var want := fov + fov_delta()
	if not is_equal_approx(camera.fov, want):
		camera.fov = want


# ─── 繪製 ───────────────────────────────────────────────
func draw_overlay(c: Control) -> void:
	var size := c.size
	if size.x <= 1.0 or size.y <= 1.0:
		return
	var center := size * 0.5
	var max_r := center.length()
	var amp := _trauma * _trauma

	# 1) 暗角（呼吸 + 受擊加深 + 開鏡大幅加深）
	var vig := 0.30 + amp * 0.30 + low_health * 0.42 + ads_amount * 0.22
	if vig > 0.012:
		_draw_vignette(c, size, center, Color(0.02, 0.02, 0.035, clampf(vig, 0.0, 0.9)))
	if low_health > 0.02:
		var pulse := 0.5 + 0.5 * sin(_t * (3.4 + low_health * 3.0))
		_draw_vignette(c, size, center, Color(hit_tint.r, hit_tint.g * 0.35, hit_tint.b * 0.35,
			low_health * (0.16 + 0.14 * pulse)))

	# 2) 開鏡遮罩（狙击鏡的圓形黑邊）
	if scope_mode:
		var r := minf(size.x, size.y) * 0.44
		var dark := Color(0, 0, 0, 0.96)
		var steps := 26
		for i in steps:
			var k := float(i) / steps
			c.draw_circle(center, r * (1.02 + k * 0.85), dark.lerp(Color(0, 0, 0, 0.0), k * 0.10))
		c.draw_circle(center, r, Color(0, 0, 0, 1))
		c.draw_arc(center, r, 0.0, TAU, 96, Color(0.75, 0.85, 1.0, 0.30), 2.0)

	# 3) 速度線（衝刺 / 技能加速）
	if speed_amount > 0.02 and _quality > 0:
		var n := 16
		for i in n:
			var a := float(i) / n * TAU + _t * 0.6
			var inner := maxf(size.x, size.y) * (0.22 + 0.06 * sin(_t * 5.0 + i))
			var outer := inner + maxf(size.x, size.y) * (0.10 + 0.16 * speed_amount)
			var col := Color(0.85, 0.92, 1.0, 0.055 + 0.10 * speed_amount)
			c.draw_line(center + Vector2(cos(a), sin(a)) * inner,
				center + Vector2(cos(a), sin(a)) * outer, col, 2.0 + speed_amount * 3.0)

	# 4) 全螢幕閃光（擊殺/爆頭/技能）
	if _flash > 0.004:
		var a := pow(_flash, 1.35)
		c.draw_rect(Rect2(Vector2.ZERO, size), Color(_flash_color.r, _flash_color.g,
			_flash_color.b, clampf(a * 0.55, 0.0, 0.85)))

	# 5) 擊殺瞬間：中央擴散環 + 四角光暈（傳說皮的「擊殺回饋」升級感）
	if _kill_glow > 0.01:
		var k := _kill_glow
		var ring_r := lerpf(max_r * 0.62, max_r * 0.06, 1.0 - k)
		c.draw_arc(center, ring_r, 0.0, TAU, 72,
			Color(_kill_color.r, _kill_color.g, _kill_color.b, k * 0.55), 1.0 + k * 3.0)
		c.draw_arc(center, ring_r * 1.14, 0.0, TAU, 72,
			Color(_kill_color.r, _kill_color.g, _kill_color.b, k * 0.22), 1.0)
		var corner := Color(_kill_color.r, _kill_color.g, _kill_color.b, k * 0.16)
		var cs := size * 0.16
		for pt in [Vector2.ZERO, Vector2(size.x - cs.x, 0), Vector2(0, size.y - cs.y),
			Vector2(size.x - cs.x, size.y - cs.y)]:
			c.draw_rect(Rect2(pt, Vector2(cs.x, cs.y)), corner)

	# 6) 受擊方向指示（弧線指向子彈來的方向）
	for h in _hit_dirs:
		var t := float(h["t"])
		var fade := clampf(1.0 - t / 1.1, 0.0, 1.0)
		var a := float(h["angle"])
		var rr := lerpf(max_r * 0.34, max_r * 0.5, t / 1.1)
		var thick := (5.0 + float(h["k"]) * 9.0) * fade
		var col := Color(hit_tint.r, hit_tint.g, hit_tint.b, 0.75 * fade)
		c.draw_arc(center, rr, a - 0.32, a + 0.32, 24, col, thick)
		c.draw_arc(center, rr * 1.06, a - 0.18, a + 0.18, 16,
			Color(1, 1, 1, 0.35 * fade), thick * 0.5)


func _draw_vignette(c: Control, size: Vector2, _center: Vector2, col: Color) -> void:
	# 四邊漸層（頂點著色四邊形）：中心透明 → 邊緣著色；比貼圖便宜且不受渲染器影響
	var a := col
	var clear := Color(a.r, a.g, a.b, 0.0)
	var pad := size.x * 0.16
	var padv := size.y * 0.16
	var pts: Array = [
		[Vector2(0, 0), Vector2(size.x, 0), Vector2(size.x, pad), Vector2(0, pad)],
		[Vector2(0, size.y), Vector2(size.x, size.y), Vector2(size.x, size.y - pad),
			Vector2(0, size.y - pad)],
		[Vector2(0, 0), Vector2(0, size.y), Vector2(padv, size.y), Vector2(padv, 0)],
		[Vector2(size.x, 0), Vector2(size.x, size.y), Vector2(size.x - padv, size.y),
			Vector2(size.x - padv, 0)],
	]
	for p4 in pts:
		var arr := PackedVector2Array()
		for v in p4:
			arr.append(v)
		c.draw_polygon(arr, PackedColorArray([a, a, clear, clear]))
