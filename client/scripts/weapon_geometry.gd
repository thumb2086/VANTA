class_name WeaponGeometry
extends RefCounted

## 武器幾何圖譜（唯一來源）—— 把每把槍拆成「零件清單」，
## 由 `WeaponFinish` / `WeaponViewmodelV2` / 軍械庫預覽共用。
##
## 每個零件：
##   name  : 零件名（用於動畫/除錯）
##   role  : 材質角色 → skin_material 依此套用顏色（body/accent/metal/optic/lens/grip…）
##   kind  : box | cyl | capsule | torus | sphere | prism
##   size  : box=Vector3(寬,高,長)、cyl/torus=(半徑, 高度)、capsule=(半徑, 長)、sphere=(半徑,0,0)
##   pos   : 相對槍身原點（-Z 為槍口方向）
##   rot   : 角度（度）
##   anim  : "" | slide | bolt | mag | cylinder | charging | stock
##   scale : 可選縮放（Chroma/升級用）
##
## 單位約為公尺；全槍長度 ~0.7（步槍）/ ~0.3（手槍）/ ~0.45（匕首）。

const PARTS_VANDAL: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.072, 0.098, 0.30),
		"pos": Vector3(0, -0.02, -0.04)},
	{"name": "upper_rail", "role": "metal", "kind": "box", "size": Vector3(0.036, 0.014, 0.36),
		"pos": Vector3(0, 0.056, -0.10)},
	{"name": "handguard", "role": "body", "kind": "box", "size": Vector3(0.066, 0.070, 0.24),
		"pos": Vector3(0, -0.002, -0.30)},
	{"name": "vent_l", "role": "accent", "kind": "box", "size": Vector3(0.004, 0.030, 0.14),
		"pos": Vector3(-0.035, 0.0, -0.30)},
	{"name": "vent_r", "role": "accent", "kind": "box", "size": Vector3(0.004, 0.030, 0.14),
		"pos": Vector3(0.035, 0.0, -0.30)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.016, 0.22, 0),
		"pos": Vector3(0, 0.012, -0.50), "rot": Vector3(90, 0, 0)},
	{"name": "muzzle", "role": "metal", "kind": "cyl", "size": Vector3(0.022, 0.055, 0),
		"pos": Vector3(0, 0.012, -0.615), "rot": Vector3(90, 0, 0)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.048, 0.185, 0.075),
		"pos": Vector3(0.006, -0.135, -0.055), "rot": Vector3(-6, 0, 0), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.046, 0.145, 0.062),
		"pos": Vector3(0, -0.125, 0.075), "rot": Vector3(14, 0, 0)},
	{"name": "trigger_guard", "role": "metal", "kind": "box", "size": Vector3(0.020, 0.045, 0.075),
		"pos": Vector3(0, -0.098, 0.028)},
	{"name": "stock", "role": "body", "kind": "box", "size": Vector3(0.052, 0.075, 0.20),
		"pos": Vector3(0, -0.012, 0.215), "anim": "stock"},
	{"name": "cheek", "role": "accent", "kind": "box", "size": Vector3(0.044, 0.020, 0.13),
		"pos": Vector3(0, 0.036, 0.225)},
	{"name": "sight_rear", "role": "optic", "kind": "box", "size": Vector3(0.030, 0.034, 0.045),
		"pos": Vector3(0, 0.080, 0.035)},
	{"name": "sight_front", "role": "optic", "kind": "box", "size": Vector3(0.024, 0.030, 0.030),
		"pos": Vector3(0, 0.076, -0.245)},
	{"name": "charging", "role": "metal", "kind": "box", "size": Vector3(0.052, 0.018, 0.036),
		"pos": Vector3(0, 0.020, 0.115), "anim": "charging"},
	{"name": "accent_stripe", "role": "accent", "kind": "box", "size": Vector3(0.075, 0.007, 0.20),
		"pos": Vector3(0, 0.028, -0.06)},
]

const PARTS_PHANTOM: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.070, 0.094, 0.285),
		"pos": Vector3(0, -0.02, 0.02)},
	{"name": "upper_rail", "role": "metal", "kind": "box", "size": Vector3(0.034, 0.013, 0.30),
		"pos": Vector3(0, 0.053, -0.06)},
	{"name": "handguard", "role": "body", "kind": "box", "size": Vector3(0.060, 0.062, 0.18),
		"pos": Vector3(0, -0.004, -0.215)},
	{"name": "integral_supp", "role": "metal", "kind": "cyl", "size": Vector3(0.029, 0.20, 0),
		"pos": Vector3(0, 0.006, -0.42), "rot": Vector3(90, 0, 0)},
	{"name": "suppressor_tip", "role": "accent", "kind": "cyl", "size": Vector3(0.031, 0.030, 0),
		"pos": Vector3(0, 0.006, -0.53), "rot": Vector3(90, 0, 0)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.046, 0.175, 0.07),
		"pos": Vector3(0.005, -0.13, -0.02), "rot": Vector3(-5, 0, 0), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.044, 0.135, 0.058),
		"pos": Vector3(0, -0.118, 0.10), "rot": Vector3(12, 0, 0)},
	{"name": "trigger_guard", "role": "metal", "kind": "box", "size": Vector3(0.018, 0.040, 0.07),
		"pos": Vector3(0, -0.092, 0.055)},
	{"name": "stock", "role": "body", "kind": "box", "size": Vector3(0.046, 0.062, 0.16),
		"pos": Vector3(0, -0.006, 0.235), "anim": "stock"},
	{"name": "stock_tube", "role": "metal", "kind": "cyl", "size": Vector3(0.016, 0.14, 0),
		"pos": Vector3(0, 0.004, 0.175), "rot": Vector3(90, 0, 0)},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.030, 0.038, 0.062),
		"pos": Vector3(0, 0.077, -0.02)},
	{"name": "sight_lens", "role": "lens", "kind": "cyl", "size": Vector3(0.012, 0.006, 0),
		"pos": Vector3(0, 0.077, -0.052), "rot": Vector3(90, 0, 0)},
	{"name": "accent_line", "role": "accent", "kind": "box", "size": Vector3(0.072, 0.006, 0.24),
		"pos": Vector3(0, 0.026, -0.02)},
	{"name": "charging", "role": "metal", "kind": "box", "size": Vector3(0.048, 0.016, 0.032),
		"pos": Vector3(0, 0.018, 0.14), "anim": "charging"},
]

const PARTS_GUARDIAN: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.068, 0.092, 0.26),
		"pos": Vector3(0, -0.02, 0.0)},
	{"name": "handguard", "role": "body", "kind": "cyl", "size": Vector3(0.032, 0.30, 0),
		"pos": Vector3(0, 0.004, -0.26), "rot": Vector3(90, 0, 0)},
	{"name": "rail_top", "role": "metal", "kind": "box", "size": Vector3(0.030, 0.010, 0.34),
		"pos": Vector3(0, 0.050, -0.10)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.013, 0.16, 0),
		"pos": Vector3(0, 0.004, -0.48), "rot": Vector3(90, 0, 0)},
	{"name": "muzzle_brake", "role": "accent", "kind": "cyl", "size": Vector3(0.020, 0.05, 0),
		"pos": Vector3(0, 0.004, -0.575), "rot": Vector3(90, 0, 0)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.042, 0.14, 0.062),
		"pos": Vector3(0.004, -0.115, -0.03), "rot": Vector3(-4, 0, 0), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.042, 0.13, 0.055),
		"pos": Vector3(0, -0.112, 0.08), "rot": Vector3(13, 0, 0)},
	{"name": "bolt_handle", "role": "metal", "kind": "box", "size": Vector3(0.046, 0.014, 0.03),
		"pos": Vector3(0, 0.012, 0.10), "anim": "charging"},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.026, 0.030, 0.05),
		"pos": Vector3(0, 0.070, -0.02)},
	{"name": "accent_ring", "role": "accent", "kind": "torus", "size": Vector3(0.034, 0.006, 0),
		"pos": Vector3(0, 0.004, -0.36), "rot": Vector3(90, 0, 0)},
]

const PARTS_BULLDOG: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.076, 0.105, 0.25),
		"pos": Vector3(0, -0.02, 0.01)},
	{"name": "handguard", "role": "body", "kind": "box", "size": Vector3(0.070, 0.072, 0.16),
		"pos": Vector3(0, -0.004, -0.205)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.018, 0.14, 0),
		"pos": Vector3(0, 0.008, -0.35), "rot": Vector3(90, 0, 0)},
	{"name": "muzzle", "role": "accent", "kind": "cyl", "size": Vector3(0.024, 0.045, 0),
		"pos": Vector3(0, 0.008, -0.435), "rot": Vector3(90, 0, 0)},
	{"name": "drum_mag", "role": "mag", "kind": "cyl", "size": Vector3(0.062, 0.05, 0),
		"pos": Vector3(0.004, -0.115, -0.03), "rot": Vector3(90, 0, 0), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.045, 0.13, 0.058),
		"pos": Vector3(0, -0.118, 0.09), "rot": Vector3(12, 0, 0)},
	{"name": "stock", "role": "body", "kind": "box", "size": Vector3(0.05, 0.07, 0.15),
		"pos": Vector3(0, -0.01, 0.215), "anim": "stock"},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.03, 0.036, 0.055),
		"pos": Vector3(0, 0.078, -0.02)},
	{"name": "accent_vents", "role": "accent", "kind": "box", "size": Vector3(0.072, 0.012, 0.13),
		"pos": Vector3(0, 0.030, -0.19)},
]

const PARTS_SPECTRE: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.062, 0.086, 0.20),
		"pos": Vector3(0, -0.02, 0.02)},
	{"name": "shroud", "role": "body", "kind": "box", "size": Vector3(0.052, 0.052, 0.12),
		"pos": Vector3(0, -0.006, -0.155)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.013, 0.10, 0),
		"pos": Vector3(0, 0.0, -0.26), "rot": Vector3(90, 0, 0)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.036, 0.16, 0.055),
		"pos": Vector3(0.004, -0.125, -0.02), "rot": Vector3(-4, 0, 0), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.040, 0.12, 0.052),
		"pos": Vector3(0, -0.108, 0.08), "rot": Vector3(12, 0, 0)},
	{"name": "brace", "role": "metal", "kind": "cyl", "size": Vector3(0.014, 0.12, 0),
		"pos": Vector3(0, 0.006, 0.16), "rot": Vector3(90, 0, 0)},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.024, 0.028, 0.042),
		"pos": Vector3(0, 0.058, -0.03)},
	{"name": "accent_slot", "role": "accent", "kind": "box", "size": Vector3(0.054, 0.006, 0.11),
		"pos": Vector3(0, 0.021, -0.14)},
]

const PARTS_STINGER: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.060, 0.088, 0.185),
		"pos": Vector3(0, -0.02, 0.02)},
	{"name": "shroud", "role": "body", "kind": "box", "size": Vector3(0.050, 0.050, 0.10),
		"pos": Vector3(0, -0.004, -0.135)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.012, 0.075, 0),
		"pos": Vector3(0, 0.0, -0.22), "rot": Vector3(90, 0, 0)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.034, 0.13, 0.05),
		"pos": Vector3(0.004, -0.108, 0.01), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.040, 0.115, 0.05),
		"pos": Vector3(0, -0.10, 0.075), "rot": Vector3(12, 0, 0)},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.022, 0.026, 0.036),
		"pos": Vector3(0, 0.056, -0.02)},
	{"name": "accent", "role": "accent", "kind": "box", "size": Vector3(0.062, 0.006, 0.10),
		"pos": Vector3(0, 0.022, -0.06)},
]

const PARTS_SHERIFF: Array = [
	{"name": "frame", "role": "body", "kind": "box", "size": Vector3(0.042, 0.058, 0.16),
		"pos": Vector3(0, 0.01, -0.03)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.016, 0.16, 0),
		"pos": Vector3(0, 0.022, -0.16), "rot": Vector3(90, 0, 0)},
	{"name": "cylinder", "role": "cylinder", "kind": "cyl", "size": Vector3(0.026, 0.055, 0),
		"pos": Vector3(0, 0.006, -0.02), "rot": Vector3(90, 0, 0), "anim": "cylinder"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.038, 0.115, 0.05),
		"pos": Vector3(0, -0.075, 0.055), "rot": Vector3(10, 0, 0)},
	{"name": "hammer", "role": "metal", "kind": "box", "size": Vector3(0.016, 0.030, 0.020),
		"pos": Vector3(0, 0.044, 0.052)},
	{"name": "sight_rear", "role": "optic", "kind": "box", "size": Vector3(0.026, 0.012, 0.014),
		"pos": Vector3(0, 0.042, 0.042)},
	{"name": "sight_front", "role": "optic", "kind": "box", "size": Vector3(0.014, 0.014, 0.012),
		"pos": Vector3(0, 0.040, -0.225)},
	{"name": "accent_vent", "role": "accent", "kind": "box", "size": Vector3(0.044, 0.008, 0.06),
		"pos": Vector3(0, -0.014, -0.09)},
]

const PARTS_GHOST: Array = [
	{"name": "slide", "role": "slide", "kind": "box", "size": Vector3(0.040, 0.044, 0.185),
		"pos": Vector3(0, 0.028, -0.055), "anim": "slide"},
	{"name": "frame", "role": "body", "kind": "box", "size": Vector3(0.038, 0.032, 0.175),
		"pos": Vector3(0, -0.008, -0.05)},
	{"name": "barrel_tip", "role": "metal", "kind": "cyl", "size": Vector3(0.011, 0.03, 0),
		"pos": Vector3(0, 0.026, -0.155), "rot": Vector3(90, 0, 0)},
	{"name": "suppressor", "role": "accent", "kind": "cyl", "size": Vector3(0.020, 0.10, 0),
		"pos": Vector3(0, 0.026, -0.215), "rot": Vector3(90, 0, 0)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.030, 0.095, 0.042),
		"pos": Vector3(0, -0.068, -0.03), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.036, 0.105, 0.048),
		"pos": Vector3(0, -0.07, 0.035), "rot": Vector3(9, 0, 0)},
	{"name": "trigger_guard", "role": "metal", "kind": "box", "size": Vector3(0.014, 0.030, 0.05),
		"pos": Vector3(0, -0.040, -0.005)},
	{"name": "sight_rear", "role": "optic", "kind": "box", "size": Vector3(0.024, 0.010, 0.012),
		"pos": Vector3(0, 0.054, 0.025)},
	{"name": "sight_front", "role": "optic", "kind": "box", "size": Vector3(0.012, 0.011, 0.010),
		"pos": Vector3(0, 0.053, -0.128)},
]

const PARTS_CLASSIC: Array = [
	{"name": "slide", "role": "slide", "kind": "box", "size": Vector3(0.038, 0.040, 0.165),
		"pos": Vector3(0, 0.026, -0.045), "anim": "slide"},
	{"name": "frame", "role": "body", "kind": "box", "size": Vector3(0.036, 0.030, 0.16),
		"pos": Vector3(0, -0.006, -0.04)},
	{"name": "rail", "role": "metal", "kind": "box", "size": Vector3(0.020, 0.008, 0.075),
		"pos": Vector3(0, -0.022, -0.085)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.010, 0.035, 0),
		"pos": Vector3(0, 0.024, -0.135), "rot": Vector3(90, 0, 0)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.028, 0.085, 0.040),
		"pos": Vector3(0, -0.062, -0.02), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.034, 0.098, 0.046),
		"pos": Vector3(0, -0.064, 0.035), "rot": Vector3(11, 0, 0)},
	{"name": "foregrip", "role": "accent", "kind": "box", "size": Vector3(0.026, 0.045, 0.05),
		"pos": Vector3(0, -0.040, -0.10), "rot": Vector3(-10, 0, 0)},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.020, 0.010, 0.012),
		"pos": Vector3(0, 0.049, -0.10)},
]

const PARTS_FRENZY: Array = [
	{"name": "slide", "role": "slide", "kind": "box", "size": Vector3(0.036, 0.038, 0.15),
		"pos": Vector3(0, 0.024, -0.04), "anim": "slide"},
	{"name": "frame", "role": "body", "kind": "box", "size": Vector3(0.034, 0.028, 0.15),
		"pos": Vector3(0, -0.006, -0.035)},
	{"name": "barrel_port", "role": "accent", "kind": "cyl", "size": Vector3(0.014, 0.03, 0),
		"pos": Vector3(0, 0.022, -0.12), "rot": Vector3(90, 0, 0)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.026, 0.08, 0.038),
		"pos": Vector3(0, -0.058, -0.015), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.032, 0.092, 0.044),
		"pos": Vector3(0, -0.06, 0.032), "rot": Vector3(10, 0, 0)},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.018, 0.010, 0.010),
		"pos": Vector3(0, 0.046, -0.09)},
]

const PARTS_SHORTY: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.044, 0.052, 0.14),
		"pos": Vector3(0, 0.006, -0.02)},
	{"name": "barrels", "role": "metal", "kind": "cyl", "size": Vector3(0.017, 0.14, 0),
		"pos": Vector3(0, 0.016, -0.14), "rot": Vector3(90, 0, 0)},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.038, 0.10, 0.05),
		"pos": Vector3(0, -0.062, 0.045), "rot": Vector3(12, 0, 0)},
	{"name": "pump", "role": "accent", "kind": "box", "size": Vector3(0.040, 0.030, 0.06),
		"pos": Vector3(0, -0.006, -0.10), "anim": "charging"},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.016, 0.010, 0.010),
		"pos": Vector3(0, 0.040, -0.19)},
]

const PARTS_JUDGE: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.058, 0.082, 0.24),
		"pos": Vector3(0, -0.01, 0.02)},
	{"name": "magtube", "role": "metal", "kind": "cyl", "size": Vector3(0.019, 0.22, 0),
		"pos": Vector3(0, -0.030, -0.20), "rot": Vector3(90, 0, 0)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.021, 0.26, 0),
		"pos": Vector3(0, 0.018, -0.26), "rot": Vector3(90, 0, 0)},
	{"name": "pump", "role": "accent", "kind": "box", "size": Vector3(0.046, 0.036, 0.09),
		"pos": Vector3(0, -0.028, -0.16), "anim": "charging"},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.030, 0.05, 0.09),
		"pos": Vector3(0.002, -0.072, 0.03), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.042, 0.12, 0.055),
		"pos": Vector3(0, -0.10, 0.10), "rot": Vector3(12, 0, 0)},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.024, 0.028, 0.032),
		"pos": Vector3(0, 0.058, -0.06)},
]

const PARTS_BUCKY: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.064, 0.090, 0.27),
		"pos": Vector3(0, -0.016, 0.02)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.024, 0.34, 0),
		"pos": Vector3(0, 0.014, -0.30), "rot": Vector3(90, 0, 0)},
	{"name": "choke", "role": "accent", "kind": "cyl", "size": Vector3(0.029, 0.045, 0),
		"pos": Vector3(0, 0.014, -0.475), "rot": Vector3(90, 0, 0)},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.046, 0.13, 0.06),
		"pos": Vector3(0, -0.115, 0.10), "rot": Vector3(13, 0, 0)},
	{"name": "stock", "role": "body", "kind": "box", "size": Vector3(0.05, 0.075, 0.17),
		"pos": Vector3(0, -0.012, 0.235), "anim": "stock"},
	{"name": "drum", "role": "mag", "kind": "cyl", "size": Vector3(0.055, 0.045, 0),
		"pos": Vector3(0.004, -0.095, -0.03), "rot": Vector3(90, 0, 0), "anim": "mag"},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.026, 0.030, 0.04),
		"pos": Vector3(0, 0.062, -0.06)},
]

const PARTS_OPERATOR: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.066, 0.090, 0.30),
		"pos": Vector3(0, -0.02, 0.06)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.019, 0.55, 0),
		"pos": Vector3(0, 0.006, -0.34), "rot": Vector3(90, 0, 0)},
	{"name": "muzzle_brake", "role": "accent", "kind": "cyl", "size": Vector3(0.030, 0.10, 0),
		"pos": Vector3(0, 0.006, -0.65), "rot": Vector3(90, 0, 0)},
	{"name": "scope_body", "role": "optic", "kind": "cyl", "size": Vector3(0.034, 0.24, 0),
		"pos": Vector3(0, 0.085, -0.02), "rot": Vector3(90, 0, 0)},
	{"name": "scope_obj", "role": "lens", "kind": "cyl", "size": Vector3(0.030, 0.012, 0),
		"pos": Vector3(0, 0.085, -0.145), "rot": Vector3(90, 0, 0)},
	{"name": "scope_eye", "role": "lens", "kind": "cyl", "size": Vector3(0.026, 0.012, 0),
		"pos": Vector3(0, 0.085, 0.105), "rot": Vector3(90, 0, 0)},
	{"name": "scope_mount", "role": "metal", "kind": "box", "size": Vector3(0.030, 0.030, 0.09),
		"pos": Vector3(0, 0.055, -0.02)},
	{"name": "bolt_handle", "role": "metal", "kind": "box", "size": Vector3(0.055, 0.014, 0.03),
		"pos": Vector3(0.030, 0.020, 0.14), "anim": "bolt"},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.040, 0.10, 0.06),
		"pos": Vector3(0.002, -0.10, -0.02), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.042, 0.125, 0.055),
		"pos": Vector3(0, -0.112, 0.115), "rot": Vector3(12, 0, 0)},
	{"name": "cheek_rest", "role": "accent", "kind": "box", "size": Vector3(0.042, 0.022, 0.14),
		"pos": Vector3(0, 0.038, 0.20)},
	{"name": "bipod_l", "role": "metal", "kind": "box", "size": Vector3(0.008, 0.075, 0.008),
		"pos": Vector3(-0.026, -0.055, -0.44), "rot": Vector3(0, 0, 18)},
	{"name": "bipod_r", "role": "metal", "kind": "box", "size": Vector3(0.008, 0.075, 0.008),
		"pos": Vector3(0.026, -0.055, -0.44), "rot": Vector3(0, 0, -18)},
]

const PARTS_MARSHAL: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.058, 0.082, 0.24),
		"pos": Vector3(0, -0.016, 0.04)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.016, 0.34, 0),
		"pos": Vector3(0, 0.004, -0.26), "rot": Vector3(90, 0, 0)},
	{"name": "scope", "role": "optic", "kind": "cyl", "size": Vector3(0.026, 0.16, 0),
		"pos": Vector3(0, 0.072, 0.0), "rot": Vector3(90, 0, 0)},
	{"name": "scope_lens", "role": "lens", "kind": "cyl", "size": Vector3(0.022, 0.010, 0),
		"pos": Vector3(0, 0.072, -0.083), "rot": Vector3(90, 0, 0)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.034, 0.075, 0.05),
		"pos": Vector3(0, -0.086, -0.01), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.040, 0.118, 0.052),
		"pos": Vector3(0, -0.102, 0.09), "rot": Vector3(12, 0, 0)},
	{"name": "bolt", "role": "metal", "kind": "box", "size": Vector3(0.046, 0.012, 0.026),
		"pos": Vector3(0.026, 0.016, 0.11), "anim": "bolt"},
	{"name": "accent", "role": "accent", "kind": "box", "size": Vector3(0.060, 0.006, 0.14),
		"pos": Vector3(0, 0.026, 0.0)},
]

const PARTS_ARES: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.085, 0.115, 0.36),
		"pos": Vector3(0, -0.02, 0.02)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.026, 0.52, 0),
		"pos": Vector3(0, 0.006, -0.40), "rot": Vector3(90, 0, 0)},
	{"name": "feed_tray", "role": "mag", "kind": "box", "size": Vector3(0.075, 0.05, 0.16),
		"pos": Vector3(0.004, 0.010, -0.06), "anim": "mag"},
	{"name": "belt", "role": "accent", "kind": "box", "size": Vector3(0.020, 0.10, 0.13),
		"pos": Vector3(-0.052, -0.055, -0.05)},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.05, 0.14, 0.07),
		"pos": Vector3(0, -0.13, 0.13), "rot": Vector3(12, 0, 0)},
	{"name": "stock", "role": "body", "kind": "box", "size": Vector3(0.06, 0.085, 0.20),
		"pos": Vector3(0, -0.012, 0.28), "anim": "stock"},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.032, 0.04, 0.06),
		"pos": Vector3(0, 0.075, -0.06)},
	{"name": "bipod", "role": "metal", "kind": "box", "size": Vector3(0.06, 0.012, 0.03),
		"pos": Vector3(0, -0.05, -0.55)},
]

const PARTS_ODIN: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.092, 0.125, 0.40),
		"pos": Vector3(0, -0.02, 0.02)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.030, 0.55, 0),
		"pos": Vector3(0, 0.008, -0.44), "rot": Vector3(90, 0, 0)},
	{"name": "feed_tray", "role": "mag", "kind": "box", "size": Vector3(0.082, 0.055, 0.18),
		"pos": Vector3(0.004, 0.012, -0.05), "anim": "mag"},
	{"name": "belt", "role": "accent", "kind": "box", "size": Vector3(0.022, 0.12, 0.15),
		"pos": Vector3(-0.058, -0.06, -0.04)},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.052, 0.15, 0.075),
		"pos": Vector3(0, -0.14, 0.15), "rot": Vector3(12, 0, 0)},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.034, 0.042, 0.062),
		"pos": Vector3(0, 0.082, -0.06)},
]

const PARTS_BANDIT: Array = [
	{"name": "slide", "role": "slide", "kind": "box", "size": Vector3(0.036, 0.040, 0.155),
		"pos": Vector3(0, 0.024, -0.045), "anim": "slide"},
	{"name": "frame", "role": "body", "kind": "box", "size": Vector3(0.034, 0.028, 0.15),
		"pos": Vector3(0, -0.006, -0.04)},
	{"name": "compensator", "role": "accent", "kind": "box", "size": Vector3(0.024, 0.024, 0.05),
		"pos": Vector3(0, 0.024, -0.14)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.026, 0.08, 0.038),
		"pos": Vector3(0, -0.058, -0.015), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.032, 0.095, 0.044),
		"pos": Vector3(0, -0.06, 0.032), "rot": Vector3(10, 0, 0)},
	{"name": "sight", "role": "optic", "kind": "box", "size": Vector3(0.018, 0.012, 0.012),
		"pos": Vector3(0, 0.048, -0.10)},
]

const PARTS_OUTLAW: Array = [
	{"name": "receiver", "role": "body", "kind": "box", "size": Vector3(0.056, 0.080, 0.22),
		"pos": Vector3(0, -0.014, 0.03)},
	{"name": "barrel", "role": "metal", "kind": "cyl", "size": Vector3(0.017, 0.38, 0),
		"pos": Vector3(0, 0.004, -0.26), "rot": Vector3(90, 0, 0)},
	{"name": "scope", "role": "optic", "kind": "cyl", "size": Vector3(0.028, 0.20, 0),
		"pos": Vector3(0, 0.076, 0.0), "rot": Vector3(90, 0, 0)},
	{"name": "mag", "role": "mag", "kind": "box", "size": Vector3(0.036, 0.09, 0.055),
		"pos": Vector3(0, -0.092, -0.01), "anim": "mag"},
	{"name": "grip", "role": "grip", "kind": "box", "size": Vector3(0.040, 0.12, 0.052),
		"pos": Vector3(0, -0.104, 0.085), "rot": Vector3(12, 0, 0)},
	{"name": "lever", "role": "accent", "kind": "box", "size": Vector3(0.016, 0.05, 0.02),
		"pos": Vector3(0.032, -0.048, 0.02), "anim": "charging"},
]

const PARTS_KNIFE: Array = [
	{"name": "blade", "role": "blade", "kind": "box", "size": Vector3(0.024, 0.014, 0.27),
		"pos": Vector3(0, 0.004, -0.20)},
	{"name": "blade_tip", "role": "blade", "kind": "prism", "size": Vector3(0.024, 0.014, 0.07),
		"pos": Vector3(0, 0.004, -0.365)},
	{"name": "fuller", "role": "accent", "kind": "box", "size": Vector3(0.006, 0.004, 0.18),
		"pos": Vector3(0, 0.012, -0.19)},
	{"name": "guard", "role": "metal", "kind": "box", "size": Vector3(0.085, 0.024, 0.018),
		"pos": Vector3(0, 0.0, -0.062)},
	{"name": "handle", "role": "grip", "kind": "box", "size": Vector3(0.032, 0.036, 0.125),
		"pos": Vector3(0, -0.004, 0.015)},
	{"name": "pommel", "role": "metal", "kind": "cyl", "size": Vector3(0.022, 0.022, 0),
		"pos": Vector3(0, -0.004, 0.087), "rot": Vector3(90, 0, 0)},
]

## 武器鍵 → 零件清單
const TABLES: Dictionary = {
	"vandal": PARTS_VANDAL, "phantom": PARTS_PHANTOM, "guardian": PARTS_GUARDIAN,
	"bulldog": PARTS_BULLDOG, "spectre": PARTS_SPECTRE, "stinger": PARTS_STINGER,
	"sheriff": PARTS_SHERIFF, "ghost": PARTS_GHOST, "classic": PARTS_CLASSIC,
	"frenzy": PARTS_FRENZY, "shorty": PARTS_SHORTY, "judge": PARTS_JUDGE,
	"bucky": PARTS_BUCKY, "operator": PARTS_OPERATOR, "marshal": PARTS_MARSHAL,
	"ares": PARTS_ARES, "odin": PARTS_ODIN, "bandit": PARTS_BANDIT,
	"outlaw": PARTS_OUTLAW, "knife": PARTS_KNIFE,
}

## 每把槍的「特效錨點」：槍口 / 拋殼口（本地方坐標，-Z 為前方）
const MUZZLE_ANCHORS: Dictionary = {
	"vandal": Vector3(0, 0.012, -0.65), "phantom": Vector3(0, 0.006, -0.55),
	"guardian": Vector3(0, 0.004, -0.60), "bulldog": Vector3(0, 0.008, -0.46),
	"spectre": Vector3(0, 0.0, -0.30), "stinger": Vector3(0, 0.0, -0.26),
	"sheriff": Vector3(0, 0.022, -0.24), "ghost": Vector3(0, 0.026, -0.27),
	"classic": Vector3(0, 0.024, -0.16), "frenzy": Vector3(0, 0.022, -0.15),
	"shorty": Vector3(0, 0.016, -0.22), "judge": Vector3(0, 0.018, -0.40),
	"bucky": Vector3(0, 0.014, -0.50), "operator": Vector3(0, 0.006, -0.70),
	"marshal": Vector3(0, 0.004, -0.44), "ares": Vector3(0, 0.006, -0.67),
	"odin": Vector3(0, 0.008, -0.72), "bandit": Vector3(0, 0.024, -0.17),
	"outlaw": Vector3(0, 0.004, -0.46), "knife": Vector3(0, 0.004, -0.40),
}
const EJECT_ANCHORS: Dictionary = {
	"vandal": Vector3(0.045, 0.03, 0.02), "phantom": Vector3(0.042, 0.028, 0.04),
	"guardian": Vector3(0.040, 0.026, 0.02), "bulldog": Vector3(0.045, 0.03, 0.0),
	"spectre": Vector3(0.036, 0.024, 0.02), "stinger": Vector3(0.034, 0.022, 0.02),
	"sheriff": Vector3(0.030, 0.024, -0.01), "ghost": Vector3(0.024, 0.045, -0.02),
	"classic": Vector3(0.022, 0.042, -0.02), "frenzy": Vector3(0.020, 0.040, -0.02),
	"operator": Vector3(0.040, 0.03, 0.10), "marshal": Vector3(0.032, 0.03, 0.08),
	"ares": Vector3(0.05, 0.03, 0.05), "odin": Vector3(0.055, 0.03, 0.05),
}

## 每把槍的視覺「重心/朝向」修正（讓視角模型看起來自然）
const POSE: Dictionary = {
	"operator": {"rot": Vector3(0, 0.0, 0), "scale": 1.0},
	"ares": {"scale": 1.02}, "odin": {"scale": 1.04},
	"knife": {"rot": Vector3(-6, 8, 0)},
}


static func parts_for(weapon_key: String) -> Array:
	if TABLES.has(weapon_key):
		return TABLES[weapon_key]
	return TABLES["phantom"]


static func muzzle_anchor(weapon_key: String) -> Vector3:
	return MUZZLE_ANCHORS.get(weapon_key, Vector3(0, 0, -0.5))


static func eject_anchor(weapon_key: String) -> Vector3:
	return EJECT_ANCHORS.get(weapon_key, Vector3(0.04, 0.03, 0.0))


static func has_weapon(weapon_key: String) -> bool:
	return TABLES.has(weapon_key)


static func weapon_keys() -> Array:
	return TABLES.keys()


## 依角色決定該零件使用哪套顏色（供 skin_material 對齊）
static func role_kind(role: String) -> String:
	match role:
		"body", "frame", "receiver":
			return "body"
		"slide", "bolt", "cylinder", "charging":
			return "moving"
		"metal", "mag":
			return "metal"
		"grip", "stock":
			return "grip"
		"optic", "lens":
			return "optic"
		"accent", "blade":
			return "accent"
		_:
			return "body"
