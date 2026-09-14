class_name FlashOverlay
extends CanvasLayer

## 閃光致盲漸層白屏遮罩
## ========================
## 當被閃光彈命中時，全螢幕白色漸層遮罩：
##   0.0–0.1s：快速淡入到峰值 alpha（1.0）
##   0.1–2.0s：指數衰減淡出（alpha = intensity * exp(-4*t)）
##   2.0s+   ：完全透明，遮罩隱藏
##
## 特色：
##   * 漸層而非實心 — 邊緣比中心更透（徑向遮罩）
##   * 峰值後立即衰減 — 符合特戰「先全白再漸漸恢复」的體驗
##   * 多次疊加：新閃光重置計時，但取最大 intensity

var _overlay: ColorRect = null
var _timer := 0.0
var _intensity := 0.0
var _active := false

# 漸層紋理（徑向遮罩：中心不透，邊緣漸透）
var _gradient_tex: GradientTexture2D = null


func _ready() -> void:
	layer = 15  # 在 HUD 之上
	_build_overlay()
	_active = false
	_overlay.visible = false


func _build_overlay() -> void:
	_overlay = ColorRect.new()
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.color = Color(1.0, 1.0, 1.0, 0.0)
	# 徑向漸層：中心 alpha=1，邊緣 alpha=0.3（讓閃光看起來從中心爆開）
	_gradient_tex = GradientTexture2D.new()
	_gradient_tex.fill = Color(1.0, 1.0, 1.0, 1.0)
	_gradient_tex.fill_from = Vector2(0.5, 0.5)
	_gradient_tex.fill_to = Vector2(0.5, 0.5)
	var grad := Gradient.new()
	grad.set_color(0, Color(1.0, 1.0, 1.0, 1.0))
	grad.set_color(1, Color(1.0, 1.0, 1.0, 0.35))
	_gradient_tex.gradient = grad
	_gradient_tex.fill_type = GradientTexture2D.FILL_RADIAL
	add_child(_overlay)


func trigger(intensity: float) -> void:
	"""觸發閃光致盲：intensity 0.0–1.0。"""
	_timer = 0.0
	_intensity = maxf(_intensity, intensity) if _active else intensity
	_active = true
	_overlay.visible = true


func _process(delta: float) -> void:
	if not _active:
		return
	_timer += delta
	var alpha := 0.0
	if _timer < 0.1:
		# 快速淡入（0 → intensity）
		alpha = lerpf(0.0, _intensity, _timer / 0.1)
	else:
		# 指數衰減淡出
		var t := _timer - 0.1
		alpha = _intensity * exp(-3.5 * t)
		if alpha < 0.01:
			_active = false
			_overlay.visible = false
			_intensity = 0.0
			return
	_overlay.color.a = alpha
	# 微微的色温變化：剛閃時偏藍白，恢復時偏暖白
	var warmth := clampf(_timer / 2.0, 0.0, 1.0)
	_overlay.color.r = lerpf(0.9, 1.0, warmth)
	_overlay.color.g = lerpf(0.95, 1.0, warmth)
	_overlay.color.b = lerpf(1.0, 0.95, warmth)
