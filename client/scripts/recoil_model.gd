## recoil_model.gd — 後座／準度：客戶端鏡像層
##
## 資料來源是 `res://assets/recoil/recoil.json`，那是 `tools.cli recoil` 從
## 伺服器唯一事實來源（`server/game/recoil.py` + `server/core/accuracy.py`）匯出的副本。
## 算式與 `RecoilController` / `SpreadEngine` / `MovementErrorEngine` 一致，因此：
##   - 準星大小 = **真的**擴散圓（不是憑空 +1.5°）
##   - 槍身上跳 = **真的**图案（每把槍不同、首發保護彈、停火恢復）
##   - 換彈 → 图案回到第 1 發，跟伺服器同一件事
## 隨機 yaw 只有伺服器知道（協定不傳視覺雜訊），所以尾段左右抖動這裡是「視覺用」，
## 但**不進準星**：準星顯示的是可練的包絡線，跟《特戰英豪》一樣。
class_name RecoilModel
extends RefCounted

const BUNDLE_PATH := "res://assets/recoil/recoil.json"
const BUNDLE_VERSION := 1
## 客戶端只重放前 N 發（其餘由伺服器的隨機 yaw 決定），與 SpreadEngine 的 growth 上限同步
const GROWTH_CAP := 8

static var _bundle: Dictionary = {}
static var _bundle_read := false

var weapon_key := ""
var wclass := "rifle"
var pitch_pattern: PackedFloat64Array = PackedFloat64Array()
var yaw_pattern: PackedFloat64Array = PackedFloat64Array()
var protected_bullets := 1
var reset_time := 0.55
var recover_rate := 6.0
var random_yaw_scale := 0.3
var fire_interval := 1.0 / 9.75
var first_shot_accuracy := 0.0
var spread_per_bullet := 0.0
var ads_spread_mult := 1.0
var move_speed_mult := 1.0
var mag_size := 25
var reload_time := 2.5
var automatic := true
var burst_count := 1
var pellets := 1
var scoped := false
var has_data := false

var bullet_index := 0
var pitch := 0.0
var yaw := 0.0
var last_fire := -1.0e9
var _rng := RandomNumberGenerator.new()
var _max_err := 2.4
var _walk_ratio := 0.5
var _crouch_ratio := 0.35
var _air_ratio := 1.25
var _land_err := 7.0
var _land_time := 0.225


static func bundle() -> Dictionary:
	if not _bundle_read:
		_bundle_read = true
		_bundle = _read_json(BUNDLE_PATH)
	return _bundle


static func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		push_warning("RecoilModel: 缺少 " + path
				+ "（請執行 python3 -m tools.cli recoil && python3 -m tools.godot.export）")
		return {}
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_warning("RecoilModel: 無法開啟 " + path)
		return {}
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		push_warning("RecoilModel: " + path + " 不是合法 JSON 物件")
		return {}
	var data: Dictionary = parsed
	if int(data.get("version", 0)) != BUNDLE_VERSION:
		push_warning("RecoilModel: bundle 版本 %d 與客戶端期望 %d 不符"
				% [int(data.get("version", 0)), BUNDLE_VERSION])
	return data


## 載入一把槍的參數；找不到就退回 class 圖案／預設值（絕不崩潰）
func setup(key: String) -> bool:
	weapon_key = key
	has_data = false
	var data := bundle()
	var weapons: Dictionary = data.get("weapons", {})
	_apply_accuracy(data.get("accuracy", {}))
	var entry: Dictionary = weapons.get(key, {})
	if entry.is_empty():
		push_warning("RecoilModel: bundle 沒有武器 '%s'，使用內建預設" % key)
		return false
	var rec: Dictionary = entry.get("recoil", {})
	pitch_pattern = _to_floats(rec.get("pitch_deg", []))
	yaw_pattern = _to_floats(rec.get("yaw_deg", []))
	protected_bullets = int(rec.get("protected_bullets", 1))
	reset_time = float(rec.get("reset_time", 0.55))
	recover_rate = float(rec.get("recover_rate", 6.0))
	random_yaw_scale = float(rec.get("random_yaw_scale", 0.3))
	wclass = String(entry.get("class", "rifle"))
	automatic = bool(entry.get("automatic", true))
	burst_count = int(entry.get("burst", 1))
	pellets = int(entry.get("pellets", 1))
	scoped = bool(entry.get("scoped", false))
	fire_interval = 1.0 / maxf(float(entry.get("fire_rate_rps", 9.75)), 0.1)
	mag_size = int(entry.get("mag_size", 25))
	reload_time = float(entry.get("reload_time", 2.5))
	first_shot_accuracy = float(entry.get("first_shot_accuracy", 0.0))
	spread_per_bullet = float(entry.get("spread_per_bullet", 0.0))
	ads_spread_mult = float(entry.get("ads_spread_mult", 1.0))
	move_speed_mult = float(entry.get("move_speed_mult", 1.0))
	has_data = true
	reset_pattern()
	return true


func _apply_accuracy(cfg: Dictionary) -> void:
	if cfg.is_empty():
		return
	var by_class: Dictionary = cfg.get("max_error_deg_by_class", {})
	_max_err = float(by_class.get(wclass, 2.0))
	_walk_ratio = float(cfg.get("walk_error_ratio", 0.5))
	_crouch_ratio = float(cfg.get("crouch_error_ratio", 0.35))
	_air_ratio = float(cfg.get("airborne_error_ratio", 1.25))
	_land_err = float(cfg.get("land_error_deg", 7.0))
	_land_time = float(cfg.get("land_error_time", 0.225))


static func _to_floats(arr: Variant) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	if typeof(arr) == TYPE_ARRAY:
		for v in arr:
			out.append(float(v))
	return out


## 這一發的偏移增量（呼叫时机＝你按下扳機、伺服器也會在同一刻推進图案）
func fire(now: float) -> Vector2:
	var n := pitch_pattern.size()
	var dp := 0.0
	var dy := 0.0
	if n > 0:
		var i := mini(bullet_index, n - 1)
		dp = pitch_pattern[i]
		var yn := yaw_pattern.size()
		if yn > 0:
			var yi := mini(i, yn - 1)
			dy = yaw_pattern[yi]
			# 保護彈之後才有隨機左右擺動（視覺用；準星不含它）
			if i >= protected_bullets:
				dy += _rng.randf_range(-random_yaw_scale, random_yaw_scale)
		bullet_index += 1
	pitch += dp
	yaw += dy
	last_fire = now
	return Vector2(dp, dy)


## 每幀：停火超過 reset_time 就以 recover_rate 度/秒回吐（= 伺服器 RecoilController.update）
func update(now: float, delta: float) -> void:
	if now - last_fire <= reset_time:
		return
	var step := recover_rate * delta
	pitch = maxf(0.0, pitch - step)
	yaw = 0.0 if absf(yaw) <= step else yaw - step * signf(yaw)


func reset_pattern() -> void:
	bullet_index = 0


## 整包重設（換槍／回合開始）
func hard_reset() -> void:
	reset_pattern()
	pitch = 0.0
	yaw = 0.0
	last_fire = -1.0e9


func recovered() -> bool:
	return is_zero_approx(pitch) and is_zero_approx(yaw)


func protected_left() -> int:
	return maxi(0, protected_bullets - bullet_index)


## 圖標／指示器用：第 i 發的累積偏移（度，+y = 上）
func pattern_point(i: int) -> Vector2:
	var acc_x := 0.0
	var acc_y := 0.0
	var n := pitch_pattern.size()
	var yn := yaw_pattern.size()
	for k in range(mini(i + 1, n)):
		acc_y += pitch_pattern[k]
		if k < yn:
			acc_x += yaw_pattern[k]
	return Vector2(acc_x, acc_y)


func pattern_length() -> int:
	return pitch_pattern.size()


## 移動誤差（度）——鏡像 server/core/accuracy.py::MovementErrorEngine.error_deg
func movement_error_deg(speed_ratio: float, walking: bool, crouching: bool,
		airborne: bool, since_land: float) -> float:
	var ratio := clampf(speed_ratio, 0.0, 1.0)
	var base := 0.0
	if airborne:
		base = _max_err * _air_ratio
	elif crouching:
		base = _max_err * _crouch_ratio * ratio
	elif walking:
		base = _max_err * _walk_ratio * ratio
	else:
		base = _max_err * ratio
	var land := 0.0
	if _land_time > 0.0 and since_land < _land_time:
		land = _land_err * (1.0 - since_land / _land_time)
	return base + land


## 真的擴散圓（度）——鏡像 server/game/recoil.py::SpreadEngine.spread_deg
func spread_deg(speed_ratio: float, walking: bool, crouching: bool, airborne: bool,
		since_land: float, ads: bool) -> float:
	var mv := movement_error_deg(speed_ratio, walking, crouching, airborne, since_land)
	if ads:
		mv *= ads_spread_mult
	if crouching and not airborne:
		mv *= 0.7   # 與伺服器相同：ADS 與蹲的減成可疊加
	return first_shot_accuracy + mini(bullet_index, GROWTH_CAP) * spread_per_bullet + mv
