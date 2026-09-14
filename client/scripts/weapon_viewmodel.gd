class_name WeaponViewModel
extends Node3D

## 第一人稱武器視角模型 + 程序化動畫。
## 武器 = 由「武器 JSON 資料」程序化組裝的箱體零件（接收器/槍管/彈匣/握把/槍托/瞄具/刀）。
## 動畫（純程序化，時間軸驅動）：
##   * fire       開火後座（後退 + 上揚，隨後座力偏移）
##   * reload     換彈：放低 → 退彈匣 → 裝新匣 → 拉滑套 → 回位
##   * switch     換槍：放下（switch_out）→ 抬起（switch_in）
##   * knife      切刀揮砍：弧線
##   * bob        移動時武器上下/左右擺動（步態）
##   * ads        瞄準：武器移向畫面中心

## 換彈動畫里程碑音效（與伺服器 reload_progress 對齊）
signal reload_mag_drop          # 退匣 → 彈匣落地
signal reload_rack              # 拉滑套

const REST_POS := Vector3(0.24, -0.22, -0.45)
const REST_ROT := Vector3(0.0, 0.0, 0.0)

var weapon_slot := 1
var _parts := {}
var _state := "idle"            # idle / fire / reload / switch_out / switch_in / knife / inspect
var _t := 0.0
var _dur := 0.2
var _reload_t := 0.0
var _reload_local := false
var _prev_reload_frac := -1.0
var _mag_emitted := false
var _rack_emitted := false
var _fire_kick := 0.0
var _bob_phase := 0.0
var _speed := 0.0
var _ads := 0.0
var _target_ads := 0.0
var _muzzle := Vector3.ZERO
var _recoil_pitch := 0.0
var _ads_target := false
var _sway_target := Vector2.ZERO
var _inspect_done := false


## 武器 ID 對照
##   0 = Phantom（幻象）步槍 — 長槍管 + 消音器 + 直彈匣
##   1 = Vandal（暴徒）步槍 — 短槍管 + 弧形彈匣 + 突擊風格
##   2 = Ghost（鬼魅）手槍 — 消音手槍 + 小型
##   3 = Classic（經典）手槍 — 標準手槍 + 緊湊
##   4 = 匕首
var _weapon_id := 0

func build_weapon(slot: int, palette: Dictionary, weapon_id: int = -1) -> void:
	clear_parts()
	weapon_slot = slot
	# 自動決定武器 ID
	if weapon_id < 0:
		weapon_id = 0 if slot == 0 else 2 if slot == 1 else 4
	_weapon_id = weapon_id
	if weapon_id == 4:
		_build_knife()
		return
	var body_col: Color = palette.get("primary", Color(0.2, 0.2, 0.25))
	var dark: Color = body_col.darkened(0.45)
	var metal: Color = Color(0.45, 0.47, 0.52)
	var accent: Color = palette.get("accent", Color(0.9, 0.9, 0.95))
	match weapon_id:
		0: _build_phantom(body_col, dark, metal, accent)
		1: _build_vandal(body_col, dark, metal, accent)
		2: _build_ghost(body_col, dark, metal, accent)
		3: _build_classic(body_col, dark, metal, accent)
		5: _build_sheriff(body_col, dark, metal, accent)
		6: _build_frenzy(body_col, dark, metal, accent)
		7: _build_bandit(body_col, dark, metal, accent)
		10: _build_stinger(body_col, dark, metal, accent)
		11: _build_spectre(body_col, dark, metal, accent)
		20: _build_bulldog(body_col, dark, metal, accent)
		21: _build_guardian(body_col, dark, metal, accent)
		30: _build_marshal(body_col, dark, metal, accent)
		31: _build_operator(body_col, dark, metal, accent)
		32: _build_outlaw(body_col, dark, metal, accent)
		40: _build_bucky(body_col, dark, metal, accent)
		41: _build_judge(body_col, dark, metal, accent)
		50: _build_ares(body_col, dark, metal, accent)
		51: _build_odin(body_col, dark, metal, accent)
		_: _build_phantom(body_col, dark, metal, accent)  # fallback


# ═══════════════════════════════════════════════
#  幻象 Phantom — 平衡步槍，長槍管 + 消音器
# ═══════════════════════════════════════════════
func _build_phantom(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	# 消音槍管（粗短圓柱感 = 方塊）
	_parts["barrel"] = _box(Vector3(0.05, 0.05, 0.45), metal, Vector3(0, 0, -0.48))
	# 消音器（前端加粗）
	_parts["suppressor"] = _box(Vector3(0.06, 0.06, 0.14), Color(0.25, 0.27, 0.30),
		Vector3(0, 0, -0.72))
	# 消音器散熱環
	_parts["suppressor_ring"] = _box(Vector3(0.063, 0.063, 0.015), metal,
		Vector3(0, 0, -0.66))
	# 護木（圓潤感）
	_parts["handguard"] = _box(Vector3(0.065, 0.065, 0.24), dark, Vector3(0, -0.005, -0.30))
	# 護木散熱孔
	for j in range(4):
		var vz := -0.38 + j * 0.04
		_parts["vent_l%d" % j] = _box(Vector3(0.001, 0.018, 0.025), metal, Vector3(-0.034, 0.0, vz))
		_parts["vent_r%d" % j] = _box(Vector3(0.001, 0.018, 0.025), metal, Vector3(0.034, 0.0, vz))
	# 上導軌
	_parts["rail_top"] = _box(Vector3(0.038, 0.012, 0.32), metal, Vector3(0, 0.053, -0.12))
	for j in range(5):
		_parts["rail_tab%d" % j] = _box(Vector3(0.04, 0.007, 0.01), accent,
			Vector3(0, 0.062, -0.26 + j * 0.055))
	# 機匣（方正）
	_parts["receiver"] = _box(Vector3(0.07, 0.095, 0.30), body_col, Vector3(0, -0.02, -0.06))
	# 上機匣蓋（較窄）
	_parts["top_cover"] = _box(Vector3(0.05, 0.025, 0.28), dark, Vector3(0, 0.055, -0.06))
	# 拋殼口
	_parts["ejection_port"] = _box(Vector3(0.001, 0.03, 0.045), Color(0.08, 0.08, 0.1),
		Vector3(0.036, 0.02, -0.04))
	# 彈匣（直長）
	_parts["mag"] = _box(Vector3(0.05, 0.17, 0.08), dark, Vector3(0, -0.12, -0.06))
	# 扳機護弓
	_parts["trigger_guard"] = _box(Vector3(0.038, 0.012, 0.055), metal, Vector3(0, -0.065, 0.04))
	# 扳機
	_parts["trigger"] = _box(Vector3(0.007, 0.025, 0.008), accent, Vector3(0, -0.055, 0.03))
	# 握把
	_parts["grip"] = _box(Vector3(0.048, 0.14, 0.065), body_col, Vector3(0, -0.13, 0.08))
	# 槍托（伸縮式）
	_parts["stock"] = _box(Vector3(0.05, 0.07, 0.20), dark, Vector3(0, -0.01, 0.22))
	_parts["stock_pad"] = _box(Vector3(0.055, 0.08, 0.03), Color(0.15, 0.15, 0.18),
		Vector3(0, -0.01, 0.33))
	# 瞄具（光學瞄準鏡）
	_parts["sight"] = _box(Vector3(0.035, 0.04, 0.08), accent, Vector3(0, 0.08, -0.10))
	_parts["sight_lens"] = _box(Vector3(0.025, 0.025, 0.01), Color(0.3, 0.6, 0.9, 0.7),
		Vector3(0, 0.08, -0.14))
	# 槍口
	_parts["muzzle"] = _box(Vector3(0.04, 0.04, 0.05), metal, Vector3(0, 0, -0.80))
	_parts["muzzle_hole"] = _cyl(0.012, 0.005, Color(0.05, 0.05, 0.05), Vector3(0, 0, -0.83))
	# 機匣裝飾
	_parts["accent_stripe"] = _box(Vector3(0.072, 0.006, 0.26), accent,
		Vector3(0, 0.028, -0.06))
	_muzzle = Vector3(0, 0, -0.82)


# ═══════════════════════════════════════════════
#  暴徒 Vandal — 高傷害步槍，短槍管 + 弧形彈匣
# ═══════════════════════════════════════════════
func _build_vandal(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	# 槍管（短粗）
	_parts["barrel"] = _box(Vector3(0.055, 0.055, 0.38), metal, Vector3(0, 0, -0.42))
	# 護木（戰術感，較短）
	_parts["handguard"] = _box(Vector3(0.07, 0.07, 0.18), dark, Vector3(0, -0.005, -0.26))
	# 護木散熱孔（左右各 3）
	for j in range(3):
		var vz := -0.34 + j * 0.05
		_parts["vent_l%d" % j] = _box(Vector3(0.001, 0.02, 0.03), metal, Vector3(-0.036, 0.0, vz))
		_parts["vent_r%d" % j] = _box(Vector3(0.001, 0.02, 0.03), metal, Vector3(0.036, 0.0, vz))
	# 上導軌（皮卡汀尼）
	_parts["rail_top"] = _box(Vector3(0.04, 0.015, 0.34), metal, Vector3(0, 0.055, -0.14))
	for j in range(6):
		_parts["rail_tab%d" % j] = _box(Vector3(0.042, 0.008, 0.012), accent,
			Vector3(0, 0.065, -0.28 + j * 0.055))
	# 機匣（厚實）
	_parts["receiver"] = _box(Vector3(0.075, 0.10, 0.26), body_col, Vector3(0, -0.02, -0.04))
	# 拋殼口
	_parts["ejection_port"] = _box(Vector3(0.001, 0.035, 0.05), Color(0.08, 0.08, 0.1),
		Vector3(0.038, 0.02, -0.02))
	# 拉機柄
	_parts["charging_handle"] = _box(Vector3(0.025, 0.015, 0.06), metal, Vector3(0, 0.065, 0.04))
	# 弧形彈匣（AK 風格，傾斜）
	_parts["mag"] = _box(Vector3(0.05, 0.18, 0.07), dark, Vector3(0.01, -0.13, -0.05))
	_parts["mag_curve"] = _box(Vector3(0.04, 0.06, 0.06), dark, Vector3(0.02, -0.20, -0.03))
	# 彈匣释放鈕
	_parts["mag_release"] = _box(Vector3(0.015, 0.015, 0.02), accent, Vector3(0.025, -0.04, -0.02))
	# 握把
	_parts["grip"] = _box(Vector3(0.05, 0.15, 0.065), body_col, Vector3(0, -0.13, 0.07))
	# 扳機護弓
	_parts["trigger_guard"] = _box(Vector3(0.04, 0.015, 0.06), metal, Vector3(0, -0.07, 0.03))
	# 扳機
	_parts["trigger"] = _box(Vector3(0.008, 0.03, 0.01), accent, Vector3(0, -0.06, 0.02))
	# 槍托（固定式，較粗）
	_parts["stock"] = _box(Vector3(0.06, 0.08, 0.22), dark, Vector3(0, -0.01, 0.22))
	_parts["stock_bridge"] = _box(Vector3(0.03, 0.04, 0.10), metal, Vector3(0, 0.03, 0.18))
	_parts["stock_pad"] = _box(Vector3(0.055, 0.075, 0.025), Color(0.15, 0.14, 0.13),
		Vector3(0, -0.01, 0.34))
	# 瞄具（機械式）
	_parts["sight"] = _box(Vector3(0.03, 0.045, 0.05), accent, Vector3(0, 0.08, -0.08))
	_parts["sight_post"] = _box(Vector3(0.008, 0.03, 0.008), accent,
		Vector3(0, 0.095, -0.18))
	# 槍口制動器
	_parts["muzzle"] = _box(Vector3(0.06, 0.05, 0.06), metal, Vector3(0, 0, -0.62))
	# 槍口內徑
	_parts["muzzle_hole"] = _cyl(0.015, 0.005, Color(0.05, 0.05, 0.05), Vector3(0, 0, -0.655))
	# 機匣裝飾條
	_parts["accent_stripe"] = _box(Vector3(0.077, 0.008, 0.22), accent,
		Vector3(0, 0.03, -0.04))
	_muzzle = Vector3(0, 0, -0.65)


# ═══════════════════════════════════════════════
#  鬼魅 Ghost — 消音手槍，小型
# ═══════════════════════════════════════════════
func _build_ghost(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	var s := 0.70  # 手槍整體縮放
	# 消音槍管
	_parts["barrel"] = _box(Vector3(0.035 * s, 0.035 * s, 0.28 * s), metal,
		Vector3(0, 0, -0.28))
	# 消音器
	_parts["suppressor"] = _box(Vector3(0.042 * s, 0.042 * s, 0.10 * s),
		Color(0.22, 0.24, 0.28), Vector3(0, 0, -0.44))
	# 滑套（上機匣）
	_parts["slide"] = _box(Vector3(0.055 * s, 0.05 * s, 0.22 * s), body_col,
		Vector3(0, 0.03, -0.12))
	# 下機匣
	_parts["frame"] = _box(Vector3(0.05 * s, 0.04 * s, 0.18 * s), dark,
		Vector3(0, -0.02, -0.08))
	# 彈匣（短）
	_parts["mag"] = _box(Vector3(0.035 * s, 0.10 * s, 0.05 * s), dark,
		Vector3(0, -0.08, -0.04))
	# 握把
	_parts["grip"] = _box(Vector3(0.04 * s, 0.11 * s, 0.05 * s), body_col,
		Vector3(0, -0.09, 0.06))
	# 瞄具
	_parts["sight"] = _box(Vector3(0.02 * s, 0.025 * s, 0.03 * s), accent,
		Vector3(0, 0.065, -0.10))
	# 槍口
	_parts["muzzle"] = _box(Vector3(0.03 * s, 0.03 * s, 0.04 * s), metal,
		Vector3(0, 0, -0.50))
	_muzzle = Vector3(0, 0, -0.52)


# ═══════════════════════════════════════════════
#  經典 Classic — 標準手槍，緊湊
# ═══════════════════════════════════════════════
func _build_classic(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	var s := 0.65
	# 槍管（短）
	_parts["barrel"] = _box(Vector3(0.032 * s, 0.032 * s, 0.20 * s), metal,
		Vector3(0, 0, -0.22))
	# 滑套
	_parts["slide"] = _box(Vector3(0.052 * s, 0.048 * s, 0.20 * s), body_col,
		Vector3(0, 0.025, -0.10))
	# 下機匣
	_parts["frame"] = _box(Vector3(0.048 * s, 0.038 * s, 0.16 * s), dark,
		Vector3(0, -0.02, -0.06))
	# 彈匣（短）
	_parts["mag"] = _box(Vector3(0.032 * s, 0.09 * s, 0.045 * s), dark,
		Vector3(0, -0.07, -0.03))
	# 握把
	_parts["grip"] = _box(Vector3(0.038 * s, 0.10 * s, 0.048 * s), body_col,
		Vector3(0, -0.08, 0.05))
	# 扳機護弓
	_parts["trigger_guard"] = _box(Vector3(0.035 * s, 0.025 * s, 0.06 * s), metal,
		Vector3(0, -0.05, 0.01))
	# 瞄具
	_parts["sight"] = _box(Vector3(0.018 * s, 0.02 * s, 0.025 * s), accent,
		Vector3(0, 0.058, -0.08))
	# 槍口
	_parts["muzzle"] = _box(Vector3(0.028 * s, 0.028 * s, 0.03 * s), metal,
		Vector3(0, 0, -0.33))
	_muzzle = Vector3(0, 0, -0.35)


# ═══════════════════════════════════════════════
#  左輪 Sheriff — 高傷害左輪
# ═══════════════════════════════════════════════
func _build_sheriff(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	var s := 0.75
	_parts["barrel"] = _box(Vector3(0.04 * s, 0.04 * s, 0.30 * s), metal, Vector3(0, 0, -0.30))
	_parts["slide"] = _box(Vector3(0.06 * s, 0.055 * s, 0.26 * s), body_col, Vector3(0, 0.03, -0.12))
	_parts["frame"] = _box(Vector3(0.055 * s, 0.04 * s, 0.20 * s), dark, Vector3(0, -0.02, -0.08))
	_parts["cylinder"] = _box(Vector3(0.05 * s, 0.05 * s, 0.08 * s), metal, Vector3(0, 0.01, -0.06))
	_parts["mag"] = _box(Vector3(0.035 * s, 0.10 * s, 0.05 * s), dark, Vector3(0, -0.08, -0.04))
	_parts["grip"] = _box(Vector3(0.042 * s, 0.12 * s, 0.055 * s), body_col, Vector3(0, -0.09, 0.06))
	_parts["sight"] = _box(Vector3(0.022 * s, 0.025 * s, 0.03 * s), accent, Vector3(0, 0.065, -0.10))
	_parts["muzzle"] = _box(Vector3(0.035 * s, 0.035 * s, 0.04 * s), metal, Vector3(0, 0, -0.46))
	_muzzle = Vector3(0, 0, -0.48)


# ═══════════════════════════════════════════════
#  狂亂 Frenzy — 全自動手槍
# ═══════════════════════════════════════════════
func _build_frenzy(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	var s := 0.68
	_parts["barrel"] = _box(Vector3(0.03 * s, 0.03 * s, 0.22 * s), metal, Vector3(0, 0, -0.24))
	_parts["slide"] = _box(Vector3(0.05 * s, 0.045 * s, 0.20 * s), body_col, Vector3(0, 0.025, -0.10))
	_parts["frame"] = _box(Vector3(0.048 * s, 0.035 * s, 0.16 * s), dark, Vector3(0, -0.02, -0.06))
	_parts["mag"] = _box(Vector3(0.03 * s, 0.10 * s, 0.045 * s), dark, Vector3(0, -0.07, -0.03))
	_parts["grip"] = _box(Vector3(0.038 * s, 0.10 * s, 0.048 * s), body_col, Vector3(0, -0.08, 0.05))
	_parts["sight"] = _box(Vector3(0.018 * s, 0.02 * s, 0.025 * s), accent, Vector3(0, 0.055, -0.08))
	_parts["muzzle"] = _box(Vector3(0.028 * s, 0.028 * s, 0.03 * s), metal, Vector3(0, 0, -0.36))
	_muzzle = Vector3(0, 0, -0.38)


# ═══════════════════════════════════════════════
#  盜賊 Bandit — 半自動精準手槍（2026 新槍）
# ═══════════════════════════════════════════════
func _build_bandit(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	var s := 0.72
	_parts["barrel"] = _box(Vector3(0.035 * s, 0.035 * s, 0.26 * s), metal, Vector3(0, 0, -0.26))
	_parts["slide"] = _box(Vector3(0.052 * s, 0.048 * s, 0.22 * s), body_col, Vector3(0, 0.028, -0.12))
	_parts["frame"] = _box(Vector3(0.048 * s, 0.038 * s, 0.18 * s), dark, Vector3(0, -0.02, -0.08))
	_parts["mag"] = _box(Vector3(0.034 * s, 0.11 * s, 0.05 * s), dark, Vector3(0, -0.085, -0.04))
	_parts["grip"] = _box(Vector3(0.042 * s, 0.115 * s, 0.052 * s), body_col, Vector3(0, -0.09, 0.06))
	_parts["trigger_guard"] = _box(Vector3(0.038 * s, 0.025 * s, 0.055 * s), metal, Vector3(0, -0.052, 0.01))
	_parts["sight"] = _box(Vector3(0.02 * s, 0.028 * s, 0.03 * s), accent, Vector3(0, 0.062, -0.10))
	_parts["muzzle"] = _box(Vector3(0.03 * s, 0.03 * s, 0.035 * s), metal, Vector3(0, 0, -0.40))
	_muzzle = Vector3(0, 0, -0.42)


# ═══════════════════════════════════════════════
#  逃犯 Outlaw — 雙倍鏡中階狙擊（2024 新槍）
# ═══════════════════════════════════════════════
func _build_outlaw(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.046, 0.046, 0.52), metal, Vector3(0, 0, -0.50))
	_parts["handguard"] = _box(Vector3(0.058, 0.058, 0.18), dark, Vector3(0, -0.005, -0.28))
	_parts["receiver"] = _box(Vector3(0.062, 0.085, 0.30), body_col, Vector3(0, -0.02, -0.08))
	_parts["mag"] = _box(Vector3(0.045, 0.13, 0.065), dark, Vector3(0, -0.10, -0.06))
	_parts["grip"] = _box(Vector3(0.046, 0.125, 0.058), body_col, Vector3(0, -0.115, 0.06))
	_parts["stock"] = _box(Vector3(0.052, 0.07, 0.22), dark, Vector3(0, -0.01, 0.21))
	# 雙倍率瞄準鏡
	_parts["scope"] = _box(Vector3(0.033, 0.04, 0.13), accent, Vector3(0, 0.082, -0.08))
	_parts["scope_lens_front"] = _box(Vector3(0.024, 0.024, 0.01), Color(0.3, 0.5, 0.8, 0.7), Vector3(0, 0.082, -0.15))
	_parts["scope_lens_rear"] = _box(Vector3(0.02, 0.02, 0.01), Color(0.2, 0.4, 0.7, 0.6), Vector3(0, 0.082, -0.01))
	_parts["muzzle"] = _box(Vector3(0.038, 0.038, 0.045), metal, Vector3(0, 0, -0.78))
	_muzzle = Vector3(0, 0, -0.80)


# ═══════════════════════════════════════════════
#  刺針 Stinger — 高射速衝鋒槍
# ═══════════════════════════════════════════════
func _build_stinger(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.04, 0.04, 0.32), metal, Vector3(0, 0, -0.35))
	_parts["handguard"] = _box(Vector3(0.055, 0.055, 0.16), dark, Vector3(0, -0.005, -0.22))
	_parts["receiver"] = _box(Vector3(0.06, 0.08, 0.22), body_col, Vector3(0, -0.02, -0.04))
	_parts["mag"] = _box(Vector3(0.04, 0.12, 0.06), dark, Vector3(0, -0.09, -0.04))
	_parts["grip"] = _box(Vector3(0.042, 0.11, 0.055), body_col, Vector3(0, -0.10, 0.06))
	_parts["stock"] = _box(Vector3(0.04, 0.06, 0.14), dark, Vector3(0, -0.01, 0.18))
	_parts["sight"] = _box(Vector3(0.025, 0.03, 0.04), accent, Vector3(0, 0.06, -0.08))
	_parts["muzzle"] = _box(Vector3(0.035, 0.035, 0.04), metal, Vector3(0, 0, -0.52))
	_muzzle = Vector3(0, 0, -0.54)


# ═══════════════════════════════════════════════
#  魅影 Spectre — 消音衝鋒槍
# ═══════════════════════════════════════════════
func _build_spectre(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.045, 0.045, 0.38), metal, Vector3(0, 0, -0.40))
	_parts["suppressor"] = _box(Vector3(0.055, 0.055, 0.12), Color(0.22, 0.24, 0.28), Vector3(0, 0, -0.56))
	_parts["handguard"] = _box(Vector3(0.06, 0.06, 0.18), dark, Vector3(0, -0.005, -0.24))
	_parts["receiver"] = _box(Vector3(0.065, 0.085, 0.24), body_col, Vector3(0, -0.02, -0.04))
	_parts["mag"] = _box(Vector3(0.045, 0.14, 0.07), dark, Vector3(0, -0.10, -0.04))
	_parts["grip"] = _box(Vector3(0.045, 0.12, 0.06), body_col, Vector3(0, -0.11, 0.06))
	_parts["stock"] = _box(Vector3(0.045, 0.065, 0.16), dark, Vector3(0, -0.01, 0.18))
	_parts["sight"] = _box(Vector3(0.028, 0.035, 0.05), accent, Vector3(0, 0.065, -0.08))
	_parts["muzzle"] = _box(Vector3(0.04, 0.04, 0.04), metal, Vector3(0, 0, -0.62))
	_muzzle = Vector3(0, 0, -0.64)


# ═══════════════════════════════════════════════
#  牛犬 Bulldog — 三連發步槍
# ═══════════════════════════════════════════════
func _build_bulldog(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.048, 0.048, 0.42), metal, Vector3(0, 0, -0.44))
	_parts["handguard"] = _box(Vector3(0.058, 0.058, 0.20), dark, Vector3(0, -0.005, -0.26))
	_parts["receiver"] = _box(Vector3(0.065, 0.09, 0.26), body_col, Vector3(0, -0.02, -0.05))
	_parts["mag"] = _box(Vector3(0.048, 0.15, 0.07), dark, Vector3(0, -0.11, -0.05))
	_parts["grip"] = _box(Vector3(0.045, 0.13, 0.06), body_col, Vector3(0, -0.12, 0.07))
	_parts["stock"] = _box(Vector3(0.05, 0.07, 0.18), dark, Vector3(0, -0.01, 0.20))
	_parts["sight"] = _box(Vector3(0.03, 0.04, 0.05), accent, Vector3(0, 0.07, -0.10))
	_parts["muzzle"] = _box(Vector3(0.042, 0.042, 0.05), metal, Vector3(0, 0, -0.66))
	_muzzle = Vector3(0, 0, -0.68)


# ═══════════════════════════════════════════════
#  守衛 Guardian — 半自動步槍
# ═══════════════════════════════════════════════
func _build_guardian(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.05, 0.05, 0.48), metal, Vector3(0, 0, -0.48))
	_parts["handguard"] = _box(Vector3(0.062, 0.062, 0.22), dark, Vector3(0, -0.005, -0.28))
	_parts["receiver"] = _box(Vector3(0.068, 0.095, 0.28), body_col, Vector3(0, -0.02, -0.06))
	_parts["mag"] = _box(Vector3(0.05, 0.16, 0.08), dark, Vector3(0, -0.12, -0.06))
	_parts["grip"] = _box(Vector3(0.048, 0.14, 0.065), body_col, Vector3(0, -0.13, 0.08))
	_parts["stock"] = _box(Vector3(0.052, 0.075, 0.20), dark, Vector3(0, -0.01, 0.22))
	_parts["sight"] = _box(Vector3(0.032, 0.045, 0.06), accent, Vector3(0, 0.075, -0.10))
	_parts["muzzle"] = _box(Vector3(0.044, 0.044, 0.05), metal, Vector3(0, 0, -0.72))
	_muzzle = Vector3(0, 0, -0.74)


# ═══════════════════════════════════════════════
#  連狙 Marshal — 輕型狙擊
# ═══════════════════════════════════════════════
func _build_marshal(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.04, 0.04, 0.55), metal, Vector3(0, 0, -0.52))
	_parts["handguard"] = _box(Vector3(0.05, 0.05, 0.18), dark, Vector3(0, -0.005, -0.28))
	_parts["receiver"] = _box(Vector3(0.055, 0.08, 0.30), body_col, Vector3(0, -0.02, -0.08))
	_parts["mag"] = _box(Vector3(0.04, 0.12, 0.06), dark, Vector3(0, -0.09, -0.06))
	_parts["grip"] = _box(Vector3(0.04, 0.12, 0.055), body_col, Vector3(0, -0.10, 0.06))
	_parts["stock"] = _box(Vector3(0.045, 0.065, 0.22), dark, Vector3(0, -0.01, 0.20))
	_parts["scope"] = _box(Vector3(0.03, 0.035, 0.12), accent, Vector3(0, 0.08, -0.08))
	_parts["scope_lens"] = _box(Vector3(0.02, 0.02, 0.01), Color(0.3, 0.5, 0.8, 0.7), Vector3(0, 0.08, -0.14))
	_parts["muzzle"] = _box(Vector3(0.035, 0.035, 0.04), metal, Vector3(0, 0, -0.80))
	_muzzle = Vector3(0, 0, -0.82)


# ═══════════════════════════════════════════════
#  大狙 Operator — 重型狙擊
# ═══════════════════════════════════════════════
func _build_operator(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.05, 0.05, 0.60), metal, Vector3(0, 0, -0.55))
	_parts["handguard"] = _box(Vector3(0.06, 0.06, 0.20), dark, Vector3(0, -0.005, -0.30))
	_parts["receiver"] = _box(Vector3(0.065, 0.09, 0.32), body_col, Vector3(0, -0.02, -0.08))
	_parts["mag"] = _box(Vector3(0.05, 0.14, 0.07), dark, Vector3(0, -0.11, -0.06))
	_parts["grip"] = _box(Vector3(0.048, 0.13, 0.06), body_col, Vector3(0, -0.12, 0.06))
	_parts["stock"] = _box(Vector3(0.055, 0.075, 0.24), dark, Vector3(0, -0.01, 0.22))
	_parts["scope"] = _box(Vector3(0.035, 0.04, 0.14), accent, Vector3(0, 0.085, -0.08))
	_parts["scope_lens"] = _box(Vector3(0.025, 0.025, 0.01), Color(0.3, 0.5, 0.8, 0.7), Vector3(0, 0.085, -0.15))
	_parts["muzzle"] = _box(Vector3(0.04, 0.04, 0.05), metal, Vector3(0, 0, -0.86))
	_muzzle = Vector3(0, 0, -0.88)


# ═══════════════════════════════════════════════
#  短管 Bucky — 泵動霰彈
# ═══════════════════════════════════════════════
func _build_bucky(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.055, 0.055, 0.42), metal, Vector3(0, 0, -0.42))
	_parts["handguard"] = _box(Vector3(0.065, 0.065, 0.20), dark, Vector3(0, -0.005, -0.26))
	_parts["receiver"] = _box(Vector3(0.07, 0.09, 0.26), body_col, Vector3(0, -0.02, -0.04))
	_parts["mag"] = _box(Vector3(0.05, 0.14, 0.07), dark, Vector3(0, -0.10, -0.04))
	_parts["grip"] = _box(Vector3(0.048, 0.13, 0.06), body_col, Vector3(0, -0.12, 0.07))
	_parts["stock"] = _box(Vector3(0.05, 0.07, 0.18), dark, Vector3(0, -0.01, 0.20))
	_parts["sight"] = _box(Vector3(0.025, 0.03, 0.04), accent, Vector3(0, 0.065, -0.08))
	_parts["muzzle"] = _box(Vector3(0.05, 0.05, 0.05), metal, Vector3(0, 0, -0.64))
	_muzzle = Vector3(0, 0, -0.66)


# ═══════════════════════════════════════════════
#  判官 Judge — 連發霰彈
# ═══════════════════════════════════════════════
func _build_judge(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.058, 0.058, 0.40), metal, Vector3(0, 0, -0.40))
	_parts["handguard"] = _box(Vector3(0.068, 0.068, 0.18), dark, Vector3(0, -0.005, -0.24))
	_parts["receiver"] = _box(Vector3(0.072, 0.095, 0.26), body_col, Vector3(0, -0.02, -0.04))
	_parts["mag"] = _box(Vector3(0.052, 0.15, 0.08), dark, Vector3(0, -0.11, -0.04))
	_parts["grip"] = _box(Vector3(0.05, 0.14, 0.065), body_col, Vector3(0, -0.13, 0.07))
	_parts["stock"] = _box(Vector3(0.052, 0.075, 0.20), dark, Vector3(0, -0.01, 0.22))
	_parts["sight"] = _box(Vector3(0.028, 0.035, 0.045), accent, Vector3(0, 0.07, -0.08))
	_parts["muzzle"] = _box(Vector3(0.055, 0.055, 0.05), metal, Vector3(0, 0, -0.60))
	_muzzle = Vector3(0, 0, -0.62)


# ═══════════════════════════════════════════════
#  戰神 Ares — 輕機槍
# ═══════════════════════════════════════════════
func _build_ares(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.05, 0.05, 0.50), metal, Vector3(0, 0, -0.48))
	_parts["handguard"] = _box(Vector3(0.062, 0.062, 0.22), dark, Vector3(0, -0.005, -0.28))
	_parts["receiver"] = _box(Vector3(0.07, 0.10, 0.30), body_col, Vector3(0, -0.02, -0.06))
	_parts["belt"] = _box(Vector3(0.08, 0.06, 0.12), metal, Vector3(0.04, -0.06, 0.0))
	_parts["mag"] = _box(Vector3(0.05, 0.18, 0.08), dark, Vector3(0, -0.13, -0.06))
	_parts["grip"] = _box(Vector3(0.05, 0.14, 0.065), body_col, Vector3(0, -0.13, 0.08))
	_parts["stock"] = _box(Vector3(0.055, 0.08, 0.22), dark, Vector3(0, -0.01, 0.24))
	_parts["sight"] = _box(Vector3(0.03, 0.04, 0.05), accent, Vector3(0, 0.08, -0.10))
	_parts["muzzle"] = _box(Vector3(0.045, 0.045, 0.05), metal, Vector3(0, 0, -0.74))
	_muzzle = Vector3(0, 0, -0.76)


# ═══════════════════════════════════════════════
#  奧丁 Odin — 重機槍
# ═══════════════════════════════════════════════
func _build_odin(body_col: Color, dark: Color, metal: Color, accent: Color) -> void:
	_parts["barrel"] = _box(Vector3(0.055, 0.055, 0.55), metal, Vector3(0, 0, -0.52))
	_parts["handguard"] = _box(Vector3(0.068, 0.068, 0.24), dark, Vector3(0, -0.005, -0.30))
	_parts["receiver"] = _box(Vector3(0.075, 0.105, 0.32), body_col, Vector3(0, -0.02, -0.06))
	_parts["belt"] = _box(Vector3(0.09, 0.07, 0.14), metal, Vector3(0.05, -0.07, 0.0))
	_parts["mag"] = _box(Vector3(0.055, 0.20, 0.09), dark, Vector3(0, -0.14, -0.06))
	_parts["grip"] = _box(Vector3(0.052, 0.15, 0.07), body_col, Vector3(0, -0.14, 0.08))
	_parts["stock"] = _box(Vector3(0.058, 0.085, 0.24), dark, Vector3(0, -0.01, 0.26))
	_parts["sight"] = _box(Vector3(0.032, 0.045, 0.055), accent, Vector3(0, 0.085, -0.10))
	_parts["muzzle"] = _box(Vector3(0.05, 0.05, 0.06), metal, Vector3(0, 0, -0.80))
	_muzzle = Vector3(0, 0, -0.82)


func _build_knife() -> void:
	var metal := Color(0.75, 0.78, 0.85)
	var dark := Color(0.15, 0.13, 0.12)
	_parts["blade"] = _box(Vector3(0.03, 0.02, 0.28), metal, Vector3(0, 0.01, -0.22))
	_parts["edge"] = _box(Vector3(0.002, 0.04, 0.2), Color(0.9, 0.95, 1.0),
		Vector3(0.016, 0.0, -0.2))
	_parts["guard"] = _box(Vector3(0.09, 0.025, 0.02), dark, Vector3(0, 0, -0.07))
	_parts["handle"] = _box(Vector3(0.04, 0.04, 0.14), dark, Vector3(0, -0.01, 0.06))
	_parts["pommel"] = _box(Vector3(0.05, 0.045, 0.03), Color(0.5, 0.35, 0.15),
		Vector3(0, -0.01, 0.14))
	_muzzle = Vector3(0, 0, -0.4)


func clear_parts() -> void:
	for p in _parts.values():
		if is_instance_valid(p):
			p.queue_free()
	_parts.clear()


func _box(size: Vector3, color: Color, pos: Vector3) -> MeshInstance3D:
	var n := MeshInstance3D.new()
	var m := BoxMesh.new()
	m.size = size
	n.mesh = m
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	n.material_override = mat
	n.position = pos
	add_child(n)
	return n


func _cyl(radius: float, height: float, color: Color, pos: Vector3) -> MeshInstance3D:
	var n := MeshInstance3D.new()
	var m := CylinderMesh.new()
	m.top_radius = radius
	m.bottom_radius = radius
	m.height = height
	n.mesh = m
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	n.material_override = mat
	n.position = pos
	n.rotation_degrees = Vector3(90, 0, 0)
	add_child(n)
	return n


# --------------------------------------------------------------------- #
# 動畫觸發
# --------------------------------------------------------------------- #
func play_fire(recoil_pitch: float) -> void:
	_state = "fire"
	_t = 0.0
	_dur = 0.12
	_fire_kick = 0.16 + min(recoil_pitch, 3.0) * 0.02


func play_reload(duration: float) -> void:
	_state = "reload"
	_t = 0.0
	_dur = max(duration, 0.6)
	_reload_t = 0.0
	_reload_local = true
	_mag_emitted = false
	_rack_emitted = false


func begin_reload_from_server() -> void:
	"""伺服器驅動換彈（進度由快照 reload_frac 提供）。"""
	if _state != "reload":
		_state = "reload"
	_reload_local = false
	_mag_emitted = false
	_rack_emitted = false


func play_switch_in() -> void:
	_state = "switch_in"
	_t = 0.0
	_dur = 0.22


func play_switch_out() -> void:
	_state = "switch_out"
	_t = 0.0
	_dur = 0.18


func play_knife() -> void:
	_state = "knife"
	_t = 0.0
	_dur = 0.32


func play_inspect() -> void:
	"""檢視武器（特戰按 Y）：將武器移至面前檢視一圈。純視覺、客戶端本機。"""
	if _state == "inspect":
		return
	_state = "inspect"
	_t = 0.0
	_dur = 1.15
	# 完成後回到待機
	_inspect_done = false


# --------------------------------------------------------------------- #
# 每幀更新
# --------------------------------------------------------------------- #
func update(dt: float, speed: float, on_ground: bool, mouse_delta: Vector2,
		reload_frac := -1.0) -> void:
	_sway_target = mouse_delta * 0.002
	_speed = speed
	_target_ads = 1.0 if _ads_on() else 0.0
	_ads = lerpf(_ads, _target_ads, 1.0 - exp(-12.0 * dt))

	# 步態相位
	if speed > 0.3 and on_ground:
		_bob_phase += dt * (5.5 + speed * 1.2)
	var bob_amp := clampf(speed / 5.4, 0.0, 1.0)
	var bob := Vector3.ZERO
	var sway := Vector3(_sway_target.x, _sway_target.y, 0.0)
	_sway_target = _sway_target.lerp(Vector2.ZERO, 1.0 - exp(-14.0 * dt))
	if _state != "reload" and _ads < 0.5:
		bob = Vector3(
			sin(_bob_phase * 0.5) * 0.006 * bob_amp,
			abs(sin(_bob_phase)) * 0.008 * bob_amp,
			0.0
		)

	# 狀態時間推進
	_t += dt
	# 外部換彈結束（快照回到未換彈）→ 回到待機
	if _state == "reload" and not _reload_local and reload_frac < 0.0:
		_state = "idle"
		_reload_apply(0.0, -1.0)
	if _state == "fire" and _t >= _dur:
		_state = "idle"
	elif _state == "reload" and _t >= _dur and _reload_local:
		_state = "idle"
		_reload_local = false
	elif _state == "switch_out" and _t >= _dur:
		_state = "idle"
	elif _state == "switch_in" and _t >= _dur:
		_state = "idle"
	elif _state == "knife" and _t >= _dur:
		_state = "idle"
	elif _state == "inspect" and _t >= _dur:
		_state = "idle"
		_inspect_done = true

	# 位置/旋轉計算
	var pos := REST_POS
	var rot := REST_ROT

	# ADS 偏移
	pos = pos.lerp(Vector3(0.0, -0.13, -0.5), _ads)
	rot = rot.lerp(Vector3(0.0, 0.0, 0.0), _ads)

	match _state:
		"fire":
			var u := _t / _dur
			var kick := _fire_kick * (1.0 - u)
			pos.z += kick
			rot.x += kick * 2.2
			rot.y += (0.5 - randf()) * 0.02
		"reload":
			# 進度 u：外部伺服器進度優先（reload_frac），本地回退用內部計時
			var u := reload_frac
			if u < 0.0:
				_reload_t += dt / _dur
				u = clampf(_reload_t, 0.0, 1.0)
			else:
				u = clampf(u, 0.0, 1.0)
			_reload_apply(u, reload_frac)
			# 放低 → 退匣 → 裝匣 → 拉滑套 → 回位（由 _reload_apply 處理零件位置）
			pos.y -= sin(u * PI) * 0.22
			pos.z += sin(u * PI) * 0.1
			rot.x += sin(u * PI) * 0.6
		"inspect":
			# 檢視武器：放低右移（前 40%）→ 移至面前轉動（後 60%）
			var u := _t / _dur
			if u < 0.4:
				var lu := u / 0.4
				pos.x = REST_POS.x + sin(lu * PI * 0.5) * 0.22
				pos.y = REST_POS.y - lu * 0.28
				pos.z = REST_POS.z + lu * 0.3
				rot.y = lu * 0.7
				rot.x = lu * 0.4
			else:
				var hu := (u - 0.4) / 0.6
				pos.x = lerpf(REST_POS.x + 0.22, -0.06, hu)
				pos.y = lerpf(REST_POS.y - 0.28, -0.06, hu)
				pos.z = lerpf(REST_POS.z + 0.3, -0.32, hu)
				rot.y = lerpf(0.7, PI * 0.95, hu)
				rot.x = lerpf(0.4, -0.15, hu)
		"switch_out":
			var u := _t / _dur
			pos.y -= u * 0.3
			pos.z += u * 0.25
			rot.x += u * 1.2
			rot.y += u * 0.8
		"switch_in":
			var u := 1.0 - _t / _dur
			pos.y -= u * 0.3
			pos.z += u * 0.25
			rot.x += u * 1.2
			rot.y += u * 0.8
		"knife":
			var u := _t / _dur
			# 刀弧線：右上 → 左下
			rot.y = lerpf(0.9, -0.9, u)
			rot.x = lerpf(-0.5, 0.4, u)
			pos.x = lerpf(0.1, -0.25, u)
			pos.y -= u * 0.05

	position = pos + bob + sway
	rotation = rot

	# 後座力殘餘（瞄準視角）
	_recoil_pitch = lerpf(_recoil_pitch, 0.0, 1.0 - exp(-6.0 * dt))


func _reload_apply(u: float, external: float) -> void:
	"""換彈零件位置 + 里程碑音效訊號（與伺服器進度對齊）。"""
	# 退匣（0.25-0.45）
	if u >= 0.25 and u < 0.45:
		var mu := (u - 0.25) / 0.2
		if _parts.has("mag"):
			_parts["mag"].position = Vector3(0, -0.11 - mu * 0.25, -0.06 + mu * 0.1)
	elif u >= 0.45:
		var mu := clampf((u - 0.45) / 0.2, 0.0, 1.0)
		if _parts.has("mag"):
			_parts["mag"].position = Vector3(0, -0.11 + mu * 0.001, -0.06)
	# 拉滑套（0.65-0.8）
	if u >= 0.65 and u < 0.8:
		var su := (u - 0.65) / 0.15
		if _parts.has("receiver"):
			_parts["receiver"].position.z = -0.05 + sin(su * PI) * 0.04
	elif u >= 0.8 and _parts.has("receiver"):
		_parts["receiver"].position.z = -0.05
	# 里程碑音效：只觸發一次（外部進度前進時）
	if external >= 0.0:
		if not _mag_emitted and u >= 0.30:
			_mag_emitted = true
			reload_mag_drop.emit()
		if not _rack_emitted and u >= 0.65:
			_rack_emitted = true
			reload_rack.emit()


func set_recoil(pitch_deg: float) -> void:
	_recoil_pitch = pitch_deg


func _ads_on() -> bool:
	# 由外部透過 aim_down_sight 控制
	return _ads_target



func set_ads(on: bool) -> void:
	_ads_target = on
