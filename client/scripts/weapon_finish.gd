class_name WeaponFinish
extends RefCounted

## 把「零件清單 + 皮膚」組裝成看得見的槍（視角模型 / 軍械庫預覽 / 第三人稱共用）。
##
## 不做成 Node 子類別，而是靜態 build() 回傳 state Dictionary：
## 這樣 viewmodel、armory、render_world 都能各管自己的節點生命週期，
## 又能共用同一套材質、發光件、動畫零件規則（品質一致、程式碼不複製）。

const KIND_BOX := "box"
const KIND_CYL := "cyl"
const KIND_CAPSULE := "capsule"
const KIND_TORUS := "torus"
const KIND_SPHERE := "sphere"
const KIND_PRISM := "prism"

## 建立模型；回傳 state（供 tick / apply）
static func build(parent: Node3D, res: Dictionary, registry: SkinRegistry,
		opts: Dictionary = {}) -> Dictionary:
	var state := {
		"root": parent, "parts": [], "glow": [], "charm": null, "charm_angle": 0.0,
		"muzzle": WeaponGeometry.muzzle_anchor(String(res.get("weapon", "phantom"))),
		"eject": WeaponGeometry.eject_anchor(String(res.get("weapon", "phantom"))),
		"mats": {}, "t": 0.0, "fire": 0.0, "res": res, "scale": 1.0,
	}
	if res.is_empty():
		return state
	var want_tex := bool(opts.get("textures", true))
	var tex_size := int(opts.get("texture_size", ProceduralTexture.SIZE_VIEWMODEL))
	var mats := SkinMaterial.build(res, registry.texture_spec, {
		"textures": want_tex, "texture_size": tex_size,
		"uv_density": float(opts.get("uv_density", 2.0)),
	})
	state["mats"] = mats
	var scale := float(opts.get("scale", 1.0))
	state["scale"] = scale

	var parts: Array = WeaponGeometry.parts_for(String(res.get("weapon", "phantom")))
	for p in parts:
		var part: Dictionary = p
		var role := String(part.get("role", "body"))
		var mat: Material = pick_material(mats, role)
		var node := _make_node(part, mat, scale)
		if node == null:
			continue
		node.name = String(part.get("name", "part"))
		parent.add_child(node)
		state["parts"].append({
			"node": node, "base_pos": node.position, "base_rot": node.rotation_degrees,
			"anim": String(part.get("anim", "")), "role": role,
		})

	_build_features(state, res, mats, scale)
	return state


static func pick_material(mats: Dictionary, role: String) -> Material:
	var kind := WeaponGeometry.role_kind(role)
	match kind:
		"metal":
			return mats.get("mag", mats.get("metal"))
		"grip":
			return mats.get("grip", mats.get("body"))
		"optic":
			return mats.get("optic", mats.get("body"))
		"accent":
			if role == "blade":
				return mats.get("blade", mats.get("accent"))
			if role == "lens":
				return mats.get("lens", mats.get("accent"))
			return mats.get("accent", mats.get("body"))
		"moving":
			return mats.get("moving", mats.get("body"))
		_:
			return mats.get("body", null)


static func _make_node(part: Dictionary, mat: Material, scale: float) -> MeshInstance3D:
	var kind := String(part.get("kind", "box"))
	var size: Vector3 = part.get("size", Vector3(0.05, 0.05, 0.05))
	var mesh: Mesh = null
	match kind:
		KIND_CYL:
			var c := CylinderMesh.new()
			c.top_radius = maxf(0.001, size.x * scale)
			c.bottom_radius = c.top_radius
			c.height = maxf(0.001, size.y * scale)
			c.radial_segments = 12
			c.rings = 1
			mesh = c
		KIND_CAPSULE:
			var cap := CapsuleMesh.new()
			cap.radius = maxf(0.001, size.x * scale)
			cap.height = maxf(0.01, size.y * scale)
			cap.radial_segments = 10
			cap.rings = 4
			mesh = cap
		KIND_TORUS:
			var t := TorusMesh.new()
			t.inner_radius = maxf(0.001, (size.x - maxf(0.002, size.y)) * scale)
			t.outer_radius = maxf(t.inner_radius + 0.002, size.x * scale)
			t.rings = 20
			t.ring_segments = 8
			mesh = t
		KIND_SPHERE:
			var sp := SphereMesh.new()
			sp.radius = maxf(0.001, size.x * scale)
			sp.height = sp.radius * 2.0
			sp.radial_segments = 12
			sp.rings = 6
			mesh = sp
		KIND_PRISM:
			var pr := PrismMesh.new()
			pr.size = Vector3(maxf(0.002, size.x * scale), maxf(0.002, size.y * scale),
				maxf(0.002, size.z * scale))
			mesh = pr
		_:
			var b := BoxMesh.new()
			b.size = Vector3(maxf(0.001, size.x * scale), maxf(0.001, size.y * scale),
				maxf(0.001, size.z * scale))
			mesh = b
	if mesh == null:
		return null
	var node := MeshInstance3D.new()
	node.mesh = mesh
	if mat != null:
		node.material_override = mat
	var pos: Vector3 = part.get("pos", Vector3.ZERO)
	node.position = pos * scale
	var rot: Vector3 = part.get("rot", Vector3.ZERO)
	node.rotation_degrees = rot
	if kind == KIND_CYL or kind == KIND_TORUS:
		# 圓柱預設沿 Y；零件表以 Z 為軸（rot.x = 90 表示旋轉過）
		pass
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return node


# ─── 皮膚專屬細節（發光件 / 能量紋 / 槍飾 / 全息瞄具）────
static func _build_features(state: Dictionary, res: Dictionary, mats: Dictionary,
		scale: float) -> void:
	var root: Node3D = state.get("root", null)
	if root == null:
		return
	var flags: Dictionary = res.get("flags", {})
	var fx: Dictionary = res.get("fx", {})
	var glow_mat: Material = mats.get("glow", null)
	var emis := SkinRegistry.hex_color(
		(res.get("colorway", {}) as Dictionary).get("emissive", "#ff9d4d"), Color(1, 0.6, 0.3))
	var level := int(res.get("level", 1))

	# 1) extras（目錄裡的金額資料：浮動寶珠、環、水晶…）→ 自發光幾何
	for e in res.get("extras", []):
		var ex: Dictionary = e
		var kind := String(ex.get("kind", "orb"))
		var pos: Vector3 = ex.get("pos", Vector3(0, 0.08, 0))
		var sz := float(ex.get("size", 0.04))
		var col: Variant = ex.get("color", "emissive")
		var node := MeshInstance3D.new()
		var color := emis
		match String(col):
			"accent":
				color = SkinRegistry.hex_color(
					(res.get("colorway", {}) as Dictionary).get("accent", "#ff7a35"), emis)
			"rim":
				color = SkinRegistry.hex_color(
					(res.get("colorway", {}) as Dictionary).get("rim_color", "#ffffff"), emis)
		var mat: StandardMaterial3D = null
		if glow_mat != null:
			mat = glow_mat.duplicate()
		if mat != null:
			mat.albedo_color = Color(color.r, color.g, color.b, mat.albedo_color.a)
			mat.emission = mat.albedo_color
			node.material_override = mat
		node.mesh = _glow_mesh(kind, sz * scale)
		node.position = pos * scale
		node.set_meta("pulse", float(ex.get("pulse", 1.4)))
		node.set_meta("base_scale", node.scale)
		root.add_child(node)
		state["glow"].append(node)

	# 2) 能量紋：沿機匣的細長光條（開槍後短暫增亮）
	if bool(flags.get("veins", false)):
		for i in 3:
			var v := MeshInstance3D.new()
			var vb := BoxMesh.new()
			vb.size = Vector3(0.006 * scale, 0.010 * scale, (0.10 + 0.05 * i) * scale)
			v.mesh = vb
			if glow_mat != null:
				v.material_override = glow_mat.duplicate()
			v.position = Vector3((i - 1) * 0.026 * scale, (0.030 + 0.004 * i) * scale,
				(-0.02 - 0.03 * i) * scale)
			v.set_meta("pulse", 1.9 + 0.3 * i)
			root.add_child(v)
			state["glow"].append(v)

	# 3) 光環 / 靈體環
	if bool(flags.get("aura", false)):
		var ring := MeshInstance3D.new()
		var tor := TorusMesh.new()
		tor.inner_radius = 0.055 * scale
		tor.outer_radius = 0.062 * scale
		tor.rings = 24
		tor.ring_segments = 6
		ring.mesh = tor
		if glow_mat != null:
			var rm: StandardMaterial3D = glow_mat.duplicate()
			rm.albedo_color = Color(emis.r, emis.g, emis.b, 0.55)
			rm.emission = rm.albedo_color
			ring.material_override = rm
		ring.position = Vector3(0, 0.05 * scale, 0.10 * scale)
		ring.rotation_degrees = Vector3(78, 0, 0)
		ring.set_meta("spin", 0.85)
		ring.set_meta("pulse", 1.1)
		root.add_child(ring)
		state["glow"].append(ring)

	# 4) 全息瞄具：小發光方塊
	if bool(flags.get("holo_sight", false)):
		var h := MeshInstance3D.new()
		var hb := BoxMesh.new()
		hb.size = Vector3(0.020 * scale, 0.020 * scale, 0.004 * scale)
		h.mesh = hb
		if glow_mat != null:
			h.material_override = glow_mat.duplicate()
		h.position = Vector3(0, 0.086 * scale, -0.20 * scale)
		h.set_meta("pulse", 2.6)
		root.add_child(h)
		state["glow"].append(h)

	# 5) 槍飾（Level 4/5 才有）：懸掛 + 搖曳物理（簡化彈簧）
	if bool(flags.get("charm", false)) and level >= 4:
		var pivot := Node3D.new()
		pivot.name = "CharmPivot"
		pivot.position = Vector3(0.020 * scale, -0.085 * scale, 0.075 * scale)
		root.add_child(pivot)
		var cord := MeshInstance3D.new()
		var cb := BoxMesh.new()
		cb.size = Vector3(0.004 * scale, 0.055 * scale, 0.004 * scale)
		cord.mesh = cb
		cord.position = Vector3(0, -0.028 * scale, 0)
		if mats.get("accent", null) != null:
			cord.material_override = mats.get("accent")
		pivot.add_child(cord)
		var charm := MeshInstance3D.new()
		charm.mesh = _glow_mesh(String(fx.get("charm_kind", "orb")), 0.030 * scale)
		charm.position = Vector3(0, -0.070 * scale, 0)
		if glow_mat != null:
			charm.material_override = glow_mat.duplicate()
		pivot.add_child(charm)
		state["charm"] = pivot

	# 6) 低階皮膚也要有「活著」的感覺：呼吸式自發光（tier_glow 驅動）
	if int(state["glow"].size()) == 0 and float(res.get("tier_glow", 0.0)) > 0.2:
		var acc := MeshInstance3D.new()
		var ab := BoxMesh.new()
		ab.size = Vector3(0.076 * scale, 0.004 * scale, 0.16 * scale)
		acc.mesh = ab
		if glow_mat != null:
			acc.material_override = glow_mat.duplicate()
		acc.position = Vector3(0, 0.032 * scale, -0.05 * scale)
		acc.set_meta("pulse", 0.9)
		root.add_child(acc)
		state["glow"].append(acc)


static func _glow_mesh(kind: String, size: float) -> Mesh:
	match kind:
		"ring", "halo":
			var t := TorusMesh.new()
			t.inner_radius = size * 0.8
			t.outer_radius = size
			t.rings = 20
			t.ring_segments = 6
			return t
		"crystal", "shard":
			var pr := PrismMesh.new()
			pr.size = Vector3(size * 0.7, size * 1.6, size * 0.7)
			return pr
		"spine":
			var b := BoxMesh.new()
			b.size = Vector3(size * 0.35, size * 0.35, size * 3.0)
			return b
		"eye":
			var s := SphereMesh.new()
			s.radius = size * 0.7
			s.height = size * 1.4
			s.radial_segments = 12
			s.rings = 6
			return s
		_:
			var sp := SphereMesh.new()
			sp.radius = size
			sp.height = size * 2.0
			sp.radial_segments = 12
			sp.rings = 6
			return sp


# ─── 每幀更新：射擊滑套/槍機、換彈、開火脈衝、發光呼吸、槍飾搖曳 ───
## fire ∈ 0..1（開槍後衰減）、ads ∈ 0..1、reload ∈ 0..1（-1 = 未換彈）、
## mag_out ∈ 0..1（彈匣退出程度）
static func tick(state: Dictionary, delta: float, fire: float, _ads: float,
		reload: float, mag_out: float, bob: Vector3 = Vector3.ZERO) -> void:
	state["t"] = float(state.get("t", 0.0)) + delta
	state["fire"] = fire
	var t: float = state.get("t", 0.0)
	for p in state.get("parts", []):
		var part: Dictionary = p
		var node: Node3D = part.get("node", null)
		if node == null:
			continue
		var anim: String = part.get("anim", "")
		var base: Vector3 = part.get("base_pos", Vector3.ZERO)
		var pos := base
		match anim:
			"slide", "bolt", "charging":
				# 開火後座 + 換彈時拉拽
				pos.z += fire * 0.045
				if reload >= 0.0:
					pos.z += sin(reload * PI) * 0.055
			"mag":
				if mag_out > 0.001:
					pos.y -= mag_out * 0.22
					pos.z += mag_out * 0.02
			"cylinder":
				# 左輪彈巢：開火脈衝期間轉 1/6 格
				var ca := float(state.get("cyl", 0.0)) + fire * delta * 9.0
				state["cyl"] = ca
				node.rotation.z = ca
			"stock":
				pos.z += fire * 0.006
			_:
				pass
		node.position = pos
		if anim == "mag":
			node.visible = mag_out < 0.92
	# 發光件：呼吸 + 開火增亮
	var glow_mat_flash := 1.0 + fire * 1.8
	for g in state.get("glow", []):
		var node2: MeshInstance3D = g
		if node2 == null or not is_instance_valid(node2):
			continue
		var pulse := float(node2.get_meta("pulse", 1.0))
		var k := 0.75 + 0.35 * sin(t * pulse * 2.4)
		if node2.has_meta("spin"):
			node2.rotate_y(delta * float(node2.get_meta("spin")))
		var mat := node2.material_override as StandardMaterial3D
		if mat != null:
			var base_a := 0.42
			mat.albedo_color.a = clampf(base_a * k * glow_mat_flash, 0.05, 0.95)
			mat.emission_energy_multiplier = (1.4 + k) * glow_mat_flash * 0.75
		var sc := 1.0 + 0.06 * sin(t * pulse * 2.0) + fire * 0.18
		node2.scale = Vector3(sc, sc, sc)
	# 槍飾搖曳（簡化彈簧：受開火與移動激勵）
	var charm: Node3D = state.get("charm", null)
	if charm != null and is_instance_valid(charm):
		var target := -bob.x * 0.9 + sin(t * 1.7) * 0.05 + fire * 0.5
		state["charm_angle"] = lerpf(float(state["charm_angle"]), target, clampf(delta * 6.5, 0.0, 1.0))
		charm.rotation.x = float(state["charm_angle"])
		charm.rotation.z = sin(t * 1.15) * 0.12 - bob.y * 0.5


## 清除 build() 产生的節點（換皮膚/換槍時用）
static func clear(_parent: Node3D, state: Dictionary) -> void:
	for p in state.get("parts", []):
		var node: Node = (p as Dictionary).get("node", null)
		if node != null and is_instance_valid(node):
			node.queue_free()
	for g in state.get("glow", []):
		var gn: Node = g
		if gn != null and is_instance_valid(gn):
			gn.queue_free()
	var charm: Node = state.get("charm", null)
	if charm != null and is_instance_valid(charm):
		charm.queue_free()
	state["parts"] = []
	state["glow"] = []
	state["charm"] = null
