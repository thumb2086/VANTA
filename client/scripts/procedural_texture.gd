class_name ProceduralTexture
extends RefCounted

## 程序化槍皮貼圖（與 tools/skins/patterns.py + emit.py 逐運算式對齊）
##
## 為什麼在遊戲內生成而不提交 PNG：140 支皮膚 × 4 張圖 = 數 MB 二進位檔，
## 而生成規則只有幾 KB。工具鏈（`python3 -m tools.cli skins --textures`）也能輸出
## 完全相同的 PNG 到 `assets/skins/textures/`，若存在則直接載入（省啟動時間）。
##
## 四張圖：
##   albedo  : RGBA8（sRGB）— 花紋混色 + 邊緣露色 + 凹凸明暗 + 磨損露底
##   emissive: RGB8（sRGB）— 只沿「花紋脊線/邊緣」發光，避免整片變燈箱
##   detail  : RG8（線性）  — R=金屬度、G=粗糙度（對應工具鏈的 ORM，AO 已折進 albedo）
##   normal  : RG8（線性）  — 高度 → 法線（set_normal_map 標記）
##
## 常數全部讀自 skins.json 的 texture_spec（emit.py 的 TEX），因此改工具鏈參數
## 就會同步影響遊戲渲染，不需要兩邊手動同步。

const RES_TEXTURE_DIR := "res://assets/skins/textures"

## 視角模型用低解析度（生成成本 ~0.1s），軍械庫大预览用高解析度
const SIZE_VIEWMODEL := 64
const SIZE_PREVIEW := 128
const SIZE_DEFAULT := SIZE_VIEWMODEL

# ─── 與 patterns.py 相同的噪訊基礎 ──────────────────────
const TILE := 8
const OCTAVES := 4
const GAIN := 0.5


static func _clamp01(v: float) -> float:
	return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


static func _smooth01(v: float) -> float:
	v = _clamp01(v)
	return v * v * (3.0 - 2.0 * v)


static func _contrast(v: float, c: float) -> float:
	return _clamp01((v - 0.5) * c + 0.5)


static func _imod(a: int, b: int) -> int:
	var r := a % b
	return r + b if r < 0 else r


## 整數格點偽隨機（32bit 回繞，與 Python 逐位元組一致）
static func hash2(ix: int, iy: int, seed: int = 0) -> float:
	var n: int = (ix * 374761393 + iy * 668265263 + seed * 2246822519) & 0xFFFFFFFF
	n = (n ^ (n >> 13)) & 0xFFFFFFFF
	n = (n * 1274126177) & 0xFFFFFFFF
	n = (n ^ (n >> 16)) & 0xFFFFFFFF
	return float(n) / 4294967295.0


static func _hermite(t: float) -> float:
	return t * t * (3.0 - 2.0 * t)


static func value_noise(x: float, y: float, seed: int, tile: int) -> float:
	var x0 := int(floor(x))
	var y0 := int(floor(y))
	var fx := _hermite(x - float(x0))
	var fy := _hermite(y - float(y0))
	var m := tile if tile > 0 else (1 << 30)
	var x0m := _imod(x0, m)
	var x1m := _imod(x0 + 1, m)
	var y0m := _imod(y0, m)
	var y1m := _imod(y0 + 1, m)
	var v00 := hash2(x0m, y0m, seed)
	var v10 := hash2(x1m, y0m, seed)
	var v01 := hash2(x0m, y1m, seed)
	var v11 := hash2(x1m, y1m, seed)
	var a := v00 + (v10 - v00) * fx
	var b := v01 + (v11 - v01) * fx
	return a + (b - a) * fy


static func fbm(x: float, y: float, seed: int, octaves: int, tile: int = TILE) -> float:
	var amp := 0.5
	var total := 0.0
	var norm := 0.0
	var freq := 1.0
	for o in octaves:
		var t := tile * int(pow(2.0, o)) if tile > 0 else 0
		total += amp * value_noise(x * freq, y * freq, seed + o * 977, t)
		norm += amp
		amp *= GAIN
		freq *= 2.0
	return total / norm if norm > 0.0 else 0.0


static func ridged(x: float, y: float, seed: int, octaves: int, tile: int = TILE) -> float:
	var amp := 0.5
	var total := 0.0
	var norm := 0.0
	var freq := 1.0
	for o in octaves:
		var t := tile * maxi(1, int(round(freq))) if tile > 0 else 0
		var n := value_noise(x * freq, y * freq, seed + o * 541, t)
		var r := 1.0 - abs(n * 2.0 - 1.0)
		total += amp * r * r
		norm += amp
		amp *= 0.5
		freq *= 2.0
	return total / norm if norm > 0.0 else 0.0


# ─── 花紋產生器（回傳 row-major PackedFloat32Array）─────
static func render(name: String, size: int, params: Dictionary) -> PackedFloat32Array:
	match name:
		"noise":
			return pat_noise(size, params)
		"marble":
			return pat_marble(size, params)
		"scales":
			return pat_scales(size, params)
		"hex":
			return pat_hex(size, params)
		"scanline":
			return pat_scanline(size, params)
		"circuit":
			return pat_circuit(size, params)
		"cracks":
			return pat_cracks(size, params)
		"frost":
			return pat_frost(size, params)
		"nebula":
			return pat_nebula(size, params)
		"flame":
			return pat_flame(size, params)
		"camo":
			return pat_camo(size, params)
		"carbon":
			return pat_carbon(size, params)
		"sakura":
			return pat_sakura(size, params)
		_:
			var v := float(params.get("value", 0.5))
			var out := PackedFloat32Array()
			out.resize(size * size)
			out.fill(v)
			return out


static func pat_noise(size: int, p: Dictionary) -> PackedFloat32Array:
	var scale := float(p.get("scale", 3.0))
	var seed := int(p.get("seed", 0))
	var contrast := float(p.get("contrast", 1.0))
	var oct_count := int(p.get("octaves", 3))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		for x in size:
			var n := fbm(float(x) / size * TILE * scale, float(y) / size * TILE * scale, seed, oct_count,
				TILE)
			out[y * size + x] = _contrast(n, contrast)
	return out


static func pat_marble(size: int, p: Dictionary) -> PackedFloat32Array:
	var scale := float(p.get("scale", 2.0))
	var seed := int(p.get("seed", 1))
	var twist := float(p.get("twist", 6.0))
	var tau := TAU
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		for x in size:
			var u := float(x) / size * tau * scale
			var v := float(y) / size * tau * scale
			var n := fbm(float(x) / size * TILE * scale, float(y) / size * TILE * scale, seed, 4, TILE)
			out[y * size + x] = _clamp01(0.5 + 0.5 * sin(u + v + twist * n))
	return out


static func pat_scales(size: int, p: Dictionary) -> PackedFloat32Array:
	var cells := int(p.get("cells", 10))
	var seed := int(p.get("seed", 3))
	var bump := float(p.get("bump", 1.0))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		for x in size:
			var gy := float(y) / size * cells
			var gx := float(x) / size * cells + (0.5 if int(floor(gy)) % 2 == 1 else 0.0)
			var cx := int(floor(gx))
			var cy := int(floor(gy))
			var fx := gx - float(cx)
			var fy := gy - float(cy)
			var d := sqrt((fx - 0.5) * (fx - 0.5) + (fy - 0.5) * (fy - 0.5))
			var dome := _clamp01(1.0 - d * 2.0)
			var v := 0.20 + 0.66 * pow(dome, 0.55) + 0.14 * hash2(cx, cy, seed)
			var gap := _clamp01((d - 0.42) * 6.0)
			v *= 1.0 - bump * gap * 0.85
			out[y * size + x] = _clamp01(v)
	return out


static func pat_hex(size: int, p: Dictionary) -> PackedFloat32Array:
	var cells := int(p.get("cells", 8))
	var glow := float(p.get("glow", 0.22))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		var v := float(y) / size * cells
		for x in size:
			var u := float(x) / size * cells * 1.1547
			var d1 := abs(_fmod(u + v, 1.0) - 0.5)
			var d2 := abs(_fmod(u - v, 1.0) - 0.5)
			var d3 := abs(_fmod(v, 1.0) - 0.5)
			var edge := maxf(d1, maxf(d2, d3)) * 2.0
			out[y * size + x] = _clamp01(1.0 - _clamp01(edge / maxf(0.01, glow)))
	return out


static func pat_scanline(size: int, p: Dictionary) -> PackedFloat32Array:
	var lines := int(p.get("lines", 40))
	var blocky := float(p.get("blocky", 0.5))
	var seed := int(p.get("seed", 7))
	var out := PackedFloat32Array()
	out.resize(size * size)
	var block_h := maxi(1, size / 16)
	for y in size:
		var band := sin(float(y) / size * lines * TAU) * 0.5 + 0.5
		var block_row := hash2(0, int(floor(float(y) / block_h)), seed)
		var shift := 0.0
		if block_row > 1.0 - blocky * 0.35:
			shift = (hash2(y, 7, seed) - 0.5) * 0.8
		for x in size:
			out[y * size + x] = _clamp01(band + shift)
	return out


static func pat_circuit(size: int, p: Dictionary) -> PackedFloat32Array:
	var cells := int(p.get("cells", 12))
	var seed := int(p.get("seed", 11))
	var width := float(p.get("width", 0.16))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		var gy := float(y) / size * cells
		var iy := int(floor(gy))
		var fy := gy - float(iy)
		for x in size:
			var gx := float(x) / size * cells
			var ix := int(floor(gx))
			var fx := gx - float(ix)
			var r := hash2(ix, iy, seed)
			var line := 0.0
			if r < 0.5:
				line = maxf(line, 1.0 - _clamp01(abs(fy - 0.5) / width))
			else:
				line = maxf(line, 1.0 - _clamp01(abs(fx - 0.5) / width))
			if r > 0.78:
				var d := sqrt((fx - 0.5) * (fx - 0.5) + (fy - 0.5) * (fy - 0.5))
				line = maxf(line, 1.0 - _clamp01(d / (width * 1.6)))
			out[y * size + x] = _clamp01(line)
	return out


static func pat_cracks(size: int, p: Dictionary) -> PackedFloat32Array:
	var scale := float(p.get("scale", 3.0))
	var seed := int(p.get("seed", 13))
	var sharp := float(p.get("sharp", 3.0))
	var glow := float(p.get("glow", 0.55))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		for x in size:
			var r := ridged(float(x) / size * TILE * scale, float(y) / size * TILE * scale, seed, 4, TILE)
			var c := pow(_clamp01(1.0 - r), sharp)
			out[y * size + x] = _clamp01(c * (1.0 + glow * 2.0))
	return out


static func pat_frost(size: int, p: Dictionary) -> PackedFloat32Array:
	var cells := int(p.get("cells", 9))
	var seed := int(p.get("seed", 17))
	var pts := PackedVector2Array()
	for i in cells * cells:
		var ix := i % cells
		var iy := int(floor(float(i) / cells))
		pts.append(Vector2((ix + hash2(ix, iy, seed)) / cells, (iy + hash2(ix, iy, seed + 3)) / cells))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		var v := float(y) / size
		for x in size:
			var u := float(x) / size
			var d1 := 9.9
			var d2 := 9.9
			for j in pts.size():
				var pt: Vector2 = pts[j]
				var dx := u - pt.x
				var dy := v - pt.y
				if dx > 0.5:
					dx -= 1.0
				if dx < -0.5:
					dx += 1.0
				if dy > 0.5:
					dy -= 1.0
				if dy < -0.5:
					dy += 1.0
				var dd := dx * dx + dy * dy
				if dd < d1:
					d2 = d1
					d1 = dd
				elif dd < d2:
					d2 = dd
			var edge := _clamp01(1.0 - (sqrt(d2) - sqrt(d1)) * cells * 1.4)
			out[y * size + x] = _clamp01(0.18 + 0.82 * edge)
	return out


static func pat_nebula(size: int, p: Dictionary) -> PackedFloat32Array:
	var seed := int(p.get("seed", 23))
	var stars := int(p.get("stars", 60))
	var scale := float(p.get("scale", 2.0))
	var star_size := float(p.get("star_size", 0.010))
	var sx := PackedFloat32Array()
	var sy := PackedFloat32Array()
	for i in stars:
		sx.append(hash2(i, 1, seed))
		sy.append(hash2(i, 2, seed + 1))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		var v := float(y) / size
		for x in size:
			var u := float(x) / size
			var n := fbm(u * TILE * scale, v * TILE * scale, seed, 5, TILE)
			var core := pow(n, 2.2)
			var s := 0.0
			for i in stars:
				var dx := u - sx[i]
				var dy := v - sy[i]
				var d := sqrt(dx * dx + dy * dy)
				if d < star_size * 6.0:
					s = maxf(s, _clamp01(1.0 - d / star_size))
			out[y * size + x] = _clamp01(core * 0.8 + s)
	return out


static func pat_flame(size: int, p: Dictionary) -> PackedFloat32Array:
	var seed := int(p.get("seed", 29))
	var freq := float(p.get("freq", 3.0))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		var v := float(y) / size
		for x in size:
			var u := float(x) / size
			var n := fbm(u * TILE * freq, v * TILE * freq, seed, 4, TILE)
			var ramp := _clamp01(1.0 - v)
			out[y * size + x] = _clamp01(ramp * (0.45 + 1.4 * n))
	return out


static func pat_camo(size: int, p: Dictionary) -> PackedFloat32Array:
	var seed := int(p.get("seed", 31))
	var blobs := int(p.get("blobs", 14))
	var cx := PackedFloat32Array()
	var cy := PackedFloat32Array()
	var cr := PackedFloat32Array()
	for i in blobs:
		cx.append(hash2(i, 5, seed))
		cy.append(hash2(i, 6, seed))
		cr.append(0.05 + 0.09 * hash2(i, 7, seed))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		var v := float(y) / size
		for x in size:
			var u := float(x) / size
			var acc := 0.0
			for i in blobs:
				var dx := u - cx[i]
				var dy := v - cy[i]
				var d := sqrt(dx * dx + dy * dy)
				acc += _clamp01(1.0 - d / cr[i])
			out[y * size + x] = _clamp01(0.25 + 0.6 * _smooth01(acc))
	return out


static func pat_carbon(size: int, p: Dictionary) -> PackedFloat32Array:
	var weave := int(p.get("weave", 6))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		for x in size:
			var u := int(floor(float(x) / size * weave * 2.0))
			var v := int(floor(float(y) / size * weave * 2.0))
			var phase := ((u + v) % 2 == 0)
			var fx := _fmod(float(x) / size * weave * 2.0, 1.0)
			var fy := _fmod(float(y) / size * weave * 2.0, 1.0)
			var d := fx if phase else fy
			out[y * size + x] = _clamp01(0.30 + 0.5 * sin(d * PI))
	return out


static func pat_sakura(size: int, p: Dictionary) -> PackedFloat32Array:
	var seed := int(p.get("seed", 37))
	var count := int(p.get("count", 22))
	var pts := PackedFloat32Array()
	for i in count:
		pts.append(hash2(i, 11, seed))
		pts.append(hash2(i, 12, seed))
		pts.append(hash2(i, 13, seed) * PI)
		pts.append(0.02 + 0.03 * hash2(i, 14, seed))
	var out := PackedFloat32Array()
	out.resize(size * size)
	for y in size:
		var v := float(y) / size
		for x in size:
			var u := float(x) / size
			var acc := 0.0
			for i in count:
				var cx := u - pts[i * 4]
				var cy := v - pts[i * 4 + 1]
				var rot: float = pts[i * 4 + 2]
				var sz: float = pts[i * 4 + 3]
				var lx := cx * cos(rot) + cy * sin(rot)
				var ly := (-cx * sin(rot) + cy * cos(rot)) * 2.0
				var d := sqrt(lx * lx + ly * ly)
				acc += _clamp01(1.0 - d / sz)
			out[y * size + x] = _clamp01(acc * 0.9 + 0.06)
	return out


static func _fmod(a: float, b: float) -> float:
	if b == 0.0:
		return 0.0
	var r := fmod(a, b)
	return r + b if r < 0.0 else r


# ─── 合成（對齊 emit.py::compose_maps）──────────────────
static func _params_with_seed(params: Dictionary, seed: int) -> Dictionary:
	var out := params.duplicate()
	if not out.has("seed"):
		out["seed"] = seed
	return out


static func smooth_grid(g: PackedFloat32Array, size: int, passes: int) -> PackedFloat32Array:
	var cur := g
	for _k in passes:
		var ng := PackedFloat32Array()
		ng.resize(size * size)
		for y in size:
			var ym := _imod(y - 1, size) * size
			var yp := _imod(y + 1, size) * size
			var yr := y * size
			for x in size:
				var xm := _imod(x - 1, size)
				var xp := _imod(x + 1, size)
				ng[yr + x] = (cur[yr + x] * 4.0 + cur[yr + xm] + cur[yr + xp]
					+ cur[ym + x] + cur[yp + x]) / 8.0
		cur = ng
	return cur


## 依 colorway + pattern 生成四張圖（tools 未預先輸出 PNG 時的即時路徑）。
## 與 tools/skins/emit.py::compose_maps 逐運算式對齊：
##   結構層（花紋本身，模糊後取梯度 + 90 分位正規化）決定「發光長在哪裡」；
##   細節層（高頻噪訊）只讓 albedo/法線有顆粒感。混起來算會讓整片飽和。
static func compose(pattern: String, params: Dictionary, colorway: Dictionary,
		spec: Dictionary, size: int, seed: int) -> Dictionary:
	var dw := float(spec.get("detail_weight", 0.20))
	var edge_gain := float(spec.get("edge_gain", 1.15))
	var edge_blur := int(spec.get("edge_blur", 2))
	var edge_stride := maxi(1, int(spec.get("edge_stride", 1)))
	var edge_norm := int(spec.get("edge_normalize", 1))
	var emis_gain := float(spec.get("emissive_gain", 0.34))
	var ridge_thr := float(spec.get("emissive_ridge_threshold", 0.78))
	var ridge_w := float(spec.get("emissive_ridge_weight", 0.18))
	var emis_curve := float(spec.get("emissive_curve", 1.35))
	var shade_min := float(spec.get("albedo_shade_min", 0.62))
	var shade_range := float(spec.get("albedo_shade_range", 0.52))
	var normal_strength := float(spec.get("normal_strength", 2.2))
	var ao_base := float(spec.get("ao_base", 0.5))
	var rough_gain := float(spec.get("roughness_pattern_gain", 0.26))
	var metal_gain := float(spec.get("metal_pattern_gain", 0.10))
	if int(spec.get("version", 2)) != 2:
		push_warning("ProceduralTexture: texture_spec 版本 %d 與實作(2)不同，"
			% int(spec.get("version", 2)) + "建議重新產生 assets 或同步演算法")

	var passes := int(spec.get("smooth_passes", 1))
	var struct := smooth_grid(render(pattern, size, _params_with_seed(params, seed)), size, passes)
	var detail := render("noise", size, {
		"scale": float(spec.get("detail_scale", 7.0)), "contrast": 1.15,
		"octaves": 4, "seed": seed + 41})
	var n := size * size
	var grid := PackedFloat32Array()
	grid.resize(n)
	for i in n:
		grid[i] = clampf(struct[i] * (1.0 - dw) + detail[i] * dw, 0.0, 1.0)
	var wear_grid := render("noise", size, {"scale": 4.5, "contrast": 1.5, "seed": seed + 91})

	# ── 結構脊線場（模糊 → 中心差分 → 分位數正規化）──
	var blur := smooth_grid(struct, size, edge_blur)
	var raw := PackedFloat32Array()
	raw.resize(n)
	var sorted_vals := PackedFloat32Array()
	for y in size:
		var yp := _imod(y + edge_stride, size)
		var ym := _imod(y - edge_stride, size)
		for x in size:
			var xp := _imod(x + edge_stride, size)
			var xm := _imod(x - edge_stride, size)
			var dxg := blur[y * size + xp] - blur[y * size + xm]
			var dyg := blur[yp * size + x] - blur[ym * size + x]
			var v := sqrt(dxg * dxg + dyg * dyg)
			raw[y * size + x] = v
			sorted_vals.append(v)
	var ref := 1.0
	if edge_norm != 0 and sorted_vals.size() > 0:
		sorted_vals.sort()
		ref = maxf(0.0001, sorted_vals[mini(sorted_vals.size() - 1,
			int(sorted_vals.size() * 0.90))])
	var edge := PackedFloat32Array()
	edge.resize(n)
	for i in n:
		edge[i] = clampf(raw[i] / ref * edge_gain, 0.0, 1.0)

	var primary := SkinRegistry.hex_color(
		colorway.get("primary", "#2b2f38"), Color(0.17, 0.18, 0.22))
	var secondary := SkinRegistry.hex_color(
		colorway.get("secondary", "#171a20"), Color(0.09, 0.10, 0.13))
	var accent := SkinRegistry.hex_color(
		colorway.get("accent", "#ff7a35"), Color(1, 0.48, 0.21))
	var emis_c := SkinRegistry.hex_color(
		colorway.get("emissive", "#ff9d4d"), Color(1, 0.62, 0.30))
	var rim_c := SkinRegistry.hex_color(
		colorway.get("rim_color", "#ffffff"), Color(1, 1, 1))

	var mix_amt := float(colorway.get("pattern_mix", 0.45))
	var emis_strength := float(colorway.get("emissive_strength", 1.0))
	var wear := float(colorway.get("wear", 0.12))
	var rough := float(colorway.get("roughness", 0.38))
	var metal := float(colorway.get("metalness", 0.55))
	var irid := float(colorway.get("iridescence", 0.0))
	var clearcoat := float(colorway.get("clearcoat", 0.0))

	var alb := PackedByteArray()
	alb.resize(n * 4)
	var ems := PackedByteArray()
	ems.resize(n * 3)
	var det := PackedByteArray()
	det.resize(n * 2)

	var wear_span := maxf(0.05, wear)
	for y in size:
		for x in size:
			var i := y * size + x
			var g: float = grid[i]
			var dx2 := grid[y * size + _imod(x + 1, size)] - grid[y * size + _imod(x - 1, size)]
			var dy2 := grid[_imod(y + 1, size) * size + x] - grid[_imod(y - 1, size) * size + x]
			var micro := clampf(sqrt(dx2 * dx2 + dy2 * dy2) * 6.0, 0.0, 1.0)
			var e := clampf(edge[i] * (0.90 + 0.10 * micro), 0.0, 1.0)

			# albedo：底色混花紋 → 脊線露 accent → 依高度明暗 → AO → 磨損露底材
			var t := _smooth01(g) * mix_amt
			var cr := lerpf(primary.r, secondary.r, t)
			var cg := lerpf(primary.g, secondary.g, t)
			var cb := lerpf(primary.b, secondary.b, t)
			var ea: float = e * (0.30 + 0.40 * mix_amt)
			cr = lerpf(cr, accent.r, ea)
			cg = lerpf(cg, accent.g, ea)
			cb = lerpf(cb, accent.b, ea)
			var sh := shade_min + shade_range * g
			cr *= sh
			cg *= sh
			cb *= sh
			var wear_mask := clampf((wear_grid[i] - (1.0 - wear)) / wear_span, 0.0, 1.0)
			if wear_mask > 0.0:
				var wm := wear_mask * 0.5
				cr = lerpf(cr, minf(1.0, cr * 1.45 * 0.45 + 0.58 * 0.55), wm)
				cg = lerpf(cg, minf(1.0, cg * 1.45 * 0.45 + 0.59 * 0.55), wm)
				cb = lerpf(cb, minf(1.0, cb * 1.45 * 0.45 + 0.62 * 0.55), wm)
			if irid > 0.0:
				var hue := (float(x) / size + float(y) / size) * TAU
				var im := irid * 0.32
				cr = lerpf(cr, 0.5 + 0.5 * sin(hue), im)
				cg = lerpf(cg, 0.5 + 0.5 * sin(hue + 2.09), im)
				cb = lerpf(cb, 0.5 + 0.5 * sin(hue + 4.19), im)
			var ao := minf(1.0, ao_base + (1.0 - ao_base) * g)
			var ao_k := lerpf(0.80, 1.0, ao)
			alb[i * 4] = int(clampf(cr * ao_k, 0.0, 1.0) * 255.0)
			alb[i * 4 + 1] = int(clampf(cg * ao_k, 0.0, 1.0) * 255.0)
			alb[i * 4 + 2] = int(clampf(cb * ao_k, 0.0, 1.0) * 255.0)
			alb[i * 4 + 3] = 255

			# emission：只有「結構脊線」與高亮頂面會發光（不會整片糊成燈箱）
			var ridge := maxf(0.0, g - ridge_thr) / maxf(0.001, 1.0 - ridge_thr)
			var em := clampf((e + ridge_w * ridge * ridge) * emis_strength * emis_gain, 0.0, 1.0)
			em = pow(em, emis_curve)
			var ek := 0.30 * (1.0 - em)
			ems[i * 3] = int(clampf(lerpf(emis_c.r, rim_c.r, ek), 0.0, 1.0) * em * 255.0)
			ems[i * 3 + 1] = int(clampf(lerpf(emis_c.g, rim_c.g, ek), 0.0, 1.0) * em * 255.0)
			ems[i * 3 + 2] = int(clampf(lerpf(emis_c.b, rim_c.b, ek), 0.0, 1.0) * em * 255.0)

			# detail：R=metal、G=rough（工具鏈 ORM 的線性部分；AO 已折進 albedo）
			var met := clampf(metal + e * metal_gain + wear_mask * 0.30 + clearcoat * 0.15, 0.0, 1.0)
			var rgh := clampf(rough + (0.5 - g) * rough_gain - e * 0.12, 0.0, 1.0)
			det[i * 2] = int(met * 255.0)
			det[i * 2 + 1] = int(rgh * 255.0)

	# normal：直接從 grid（含細節）取高度 → Sobel，与 height_to_normal 一致
	var normal := PackedByteArray()
	normal.resize(n * 2)
	for y in size:
		for x in size:
			var hl: float = grid[y * size + _imod(x - 1, size)]
			var hr: float = grid[y * size + _imod(x + 1, size)]
			var hd: float = grid[_imod(y - 1, size) * size + x]
			var hu: float = grid[_imod(y + 1, size) * size + x]
			var nx := -(hr - hl) * normal_strength
			var ny := -(hu - hd) * normal_strength
			var ln := sqrt(nx * nx + ny * ny + 1.0)
			normal[(y * size + x) * 2] = int((nx / ln * 0.5 + 0.5) * 255.0)
			normal[(y * size + x) * 2 + 1] = int((ny / ln * 0.5 + 0.5) * 255.0)
	return {"albedo": alb, "emissive": ems, "detail": det, "normal": normal, "size": size}


# ─── 快取 / 載入 ────────────────────────────────────────
static var _textures: Dictionary = {}


static func cache_key(res: Dictionary, size: int) -> String:
	var cw: Dictionary = res.get("colorway", {})
	return "%s|%s|%s|%d|%d|%d" % [
		res.get("skin_id", "none"), String(cw.get("name", "")), res.get("pattern", "solid"),
		int(res.get("level", 1)), int(res.get("chroma_index", 0)), size]


static func clear_cache() -> void:
	_textures.clear()


static func cached_count() -> int:
	return _textures.size()


## 取得 {albedo, emissive, normal, detail}（ImageTexture）。
## 優先序：記憶體快取 → 工具鏈預先輸出的 PNG → 即時生成。
static func textures_for(res: Dictionary, spec: Dictionary, size: int = 0) -> Dictionary:
	if res.is_empty():
		return {}
	var sz := size if size > 0 else SIZE_VIEWMODEL
	var key := cache_key(res, sz)
	if _textures.has(key):
		return _textures[key]
	var out := _load_baked(res, sz)
	if out.is_empty():
		var seed := int(abs(hash(String(res.get("skin_id", "x")))) % 9973)
		var maps := compose(String(res.get("pattern", "solid")),
			res.get("pattern_params", {}), res.get("colorway", {}), spec, sz, seed)
		out = _to_textures(maps)
	_textures[key] = out
	return out


static func _baked_prefix(res: Dictionary) -> String:
	return "%s/%s_c%d" % [RES_TEXTURE_DIR, res.get("collection", "standard"),
		int(res.get("chroma_index", 0))]


## 工具鏈 `python3 -m tools.cli skins --textures` 的輸出（選配，存在就用）
static func _load_baked(res: Dictionary, size: int) -> Dictionary:
	var prefix := _baked_prefix(res)
	var out := {}
	for map_name in ["albedo", "emissive", "normal", "detail"]:
		var path := "%s_%d_%s.png" % [prefix, size, map_name]
		if not FileAccess.file_exists(path):
			return {}
		var img := Image.new()
		if img.load(path) != OK:
			return {}
		out[map_name] = _image_texture(img, map_name)
	return out


static func _to_textures(maps: Dictionary) -> Dictionary:
	var size := int(maps.get("size", 0))
	var out := {}
	for map_name in ["albedo", "emissive", "detail", "normal"]:
		var buf: PackedByteArray = maps.get(map_name, PackedByteArray())
		if buf.is_empty():
			continue
		var img := Image.create_from_data(size, size, false, _format_of(map_name), buf)
		out[map_name] = _image_texture(img, map_name)
	return out


static func _format_of(map_name: String) -> int:
	match map_name:
		"albedo":
			return Image.FORMAT_RGBA8
		"emissive":
			return Image.FORMAT_RGB8
		_:
			return Image.FORMAT_RG8


static func _image_texture(img: Image, map_name: String) -> ImageTexture:
	# 只有 2 的冪尺寸才開 mipmap（64/128 ✓）
	var w := img.get_width()
	var want_mips: bool = (w == img.get_height() and (w & (w - 1)) == 0 and w > 1)
	var tex := ImageTexture.create_from_image(img, want_mips)
	if tex == null:
		return null
	tex.resource_name = "skin_%s" % map_name
	if tex.has_method("set_normal_map"):
		tex.call("set_normal_map", map_name == "normal", 0)
	if want_mips:
		tex.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	else:
		tex.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR
	return tex


## 除錯：把生成的四張圖寫成 PNG（可在瀏覽器/影像軟體檢視）
static func dump_png(maps: Dictionary, base_path: String) -> void:
	var size := int(maps.get("size", 0))
	for map_name in ["albedo", "emissive", "detail", "normal"]:
		var buf: PackedByteArray = maps.get(map_name, PackedByteArray())
		if buf.is_empty():
			continue
		var img := Image.create_from_data(size, size, false, _format_of(map_name), buf)
		img.save_png("%s_%s.png" % [base_path, map_name])
