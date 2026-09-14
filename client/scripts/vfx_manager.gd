class_name VFXManager
extends Node3D

## 讀取「工具鏈產生的粒子定義」（assets/vfx/particles/*.json）
## 並以 CPUParticles3D 實例化 — 資料驅動特效。

var _emitters := {}


func setup(index: Dictionary) -> void:
	# 從 JSON 載入粒子定義
	for path in index.get("vfx_particles", []):
		var f := FileAccess.open(path, FileAccess.READ)
		if f == null:
			continue
		var data = JSON.parse_string(f.get_as_text())
		if data is Dictionary:
			var em: Dictionary = data.get("emitter", {})
			_emitters[em.get("name", path.get_file().get_basename())] = em
	# 確保關鍵特效存在（硬編碼 fallback）
	if not _emitters.has("kill_confirm"):
		_emitters["kill_confirm"] = {
			"count": 40, "speed": 6.0, "speed_var": 0.4, "life": 1.0,
			"size": 0.12, "size_var": 0.3, "gravity": -2.0,
			"color_start": [255, 220, 80], "color_end": [255, 50, 50],
			"direction": [0.0, 1.0, 0.0], "cone_angle": 60.0
		}
	if not _emitters.has("muzzle_flash"):
		_emitters["muzzle_flash"] = {
			"count": 12, "speed": 10.0, "speed_var": 0.3, "life": 0.1,
			"size": 0.15, "size_var": 0.2, "gravity": 0.0,
			"color_start": [255, 240, 180], "color_end": [255, 140, 40],
			"direction": [0.0, 0.0, -1.0], "cone_angle": 25.0
		}
	if not _emitters.has("explosion_debris"):
		_emitters["explosion_debris"] = {
			"count": 60, "speed": 8.0, "speed_var": 0.5, "life": 1.5,
			"size": 0.2, "size_var": 0.4, "gravity": -5.0,
			"color_start": [255, 180, 60], "color_end": [80, 40, 20],
			"direction": [0.0, 1.0, 0.0], "cone_angle": 90.0
		}
	if not _emitters.has("hit_marker"):
		_emitters["hit_marker"] = {
			"count": 6, "speed": 3.0, "speed_var": 0.2, "life": 0.3,
			"size": 0.08, "size_var": 0.1, "gravity": 0.0,
			"color_start": [255, 255, 255], "color_end": [255, 200, 100],
			"direction": [0.0, 0.0, -1.0], "cone_angle": 15.0
		}
	if not _emitters.has("tracer"):
		_emitters["tracer"] = {
			"count": 1, "speed": 0.0, "speed_var": 0.0, "life": 0.15,
			"size": 0.015, "size_var": 0.0, "gravity": 0.0,
			"color_start": [255, 240, 180], "color_end": [255, 180, 60],
			"direction": [0.0, 0.0, -1.0], "cone_angle": 0.0,
			"trail": true, "trail_lifetime": 0.1
		}


func spawn(name: String, world_pos: Vector3) -> void:
	var em: Dictionary = _emitters.get(name)
	if em == null:
		return
	var p := CPUParticles3D.new()
	p.position = world_pos
	p.amount = int(em.get("count", 10))
	p.lifetime = float(em.get("life", 0.6))
	p.one_shot = true
	p.explosiveness = 1.0
	p.emitting = true
	var speed: float = float(em.get("speed", 5.0))
	var jitter: float = float(em.get("speed_var", 0.3))
	p.initial_velocity_min = speed * (1.0 - jitter)
	p.initial_velocity_max = speed * (1.0 + jitter)
	var size: float = float(em.get("size", 0.1))
	var sv: float = float(em.get("size_var", 0.3))
	p.scale_amount_min = size * (1.0 - sv)
	p.scale_amount_max = size * (1.0 + sv)
	p.gravity = Vector3(0.0, -float(em.get("gravity", 0.0)), 0.0)
	var d: Array = em.get("direction", [0.0, 1.0, 0.0])
	p.direction = Vector3(d[0], d[1], d[2])
	p.spread = float(em.get("cone_angle", 30.0))
	# 顏色漸變
	var cs: Array = em.get("color_start", [255, 255, 255])
	var ce: Array = em.get("color_end", [255, 255, 255])
	var grad := Gradient.new()
	grad.set_color(0, Color(cs[0] / 255.0, cs[1] / 255.0, cs[2] / 255.0, 1.0))
	grad.set_color(1, Color(ce[0] / 255.0, ce[1] / 255.0, ce[2] / 255.0, 0.0))
	p.color_ramp = grad
	p.color = Color(cs[0] / 255.0, cs[1] / 255.0, cs[2] / 255.0)
	# 拖尾
	if em.get("trail", false):
		p.draw_order = CPUParticles3D.DRAW_ORDER_LIFETIME
	add_child(p)
	# 播完自動釋放
	var t := get_tree().create_timer(p.lifetime + 0.2)
	t.timeout.connect(_free_particles.bind(p))


func spawn_tracer(origin: Vector3, direction: Vector3, dist: float) -> void:
	"""子彈軌跡：從 origin 沿 direction 延伸 dist 距離的發光線段。"""
	var n := MeshInstance3D.new()
	var m := BoxMesh.new()
	m.size = Vector3(0.008, 0.008, dist)
	n.mesh = m
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(1.0, 0.9, 0.5, 0.7)
	mat.emission_enabled = true
	mat.emission = Color(1.0, 0.85, 0.3)
	mat.emission_energy_multiplier = 3.0
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	n.material_override = mat
	# 定位：從 origin 朝 direction 延伸
	n.position = origin + direction * dist * 0.5
	# 朝向：讓 Z 軸對齊 direction
	n.look_at(origin + direction, Vector3.UP)
	add_child(n)
	# 淡出消失
	var tween := create_tween()
	tween.tween_property(mat, "albedo_color:a", 0.0, 0.15)
	tween.tween_callback(n.queue_free)


func _free_particles(p: CPUParticles3D) -> void:
	if is_instance_valid(p):
		p.queue_free()
