class_name LocalMovement
extends RefCounted

## 客戶端預測：與 server/core/movement.py 完全相同的移動模型（確定性對齊）。
## dir.x = strafe（D+ / A-），dir.y = forward（W+ / S-）。

const RUN_SPEED := 5.4
const WALK_RATIO := 0.70
const CROUCH_RATIO := 0.43
const JUMP_SPEED := 4.6
const GRAVITY := 11.5
const GROUND_ACCEL := 72.0
const GROUND_FRICTION := 48.0
const OPPOSITE_DECEL := 140.0
const AIR_ACCEL := 26.0
const JUMP_BUFFER_TIME := 0.10
const COYOTE_TIME := 0.10

var pos := Vector3.ZERO
var vel := Vector3.ZERO
var on_ground := true
var crouching := false
var walking := false
var ads_speed_mult := 1.0  # 開鏡時降為 0.6
var time_since_land := 999.0
var _jump_buffer := 0.0
var _coyote := 0.0

# 牆壁碰撞（與伺服器 collision.py 相同的圓柱推離，維持預測一致）
# walls: [{mn: {x,y,z}, mx: {x,y,z}}]（來自地圖 JSON）
var walls: Array = []
const PLAYER_RADIUS := 0.35
const PLAYER_HEIGHT := 1.8
const COLLISION_PASSES := 3

# 買槍區（與伺服器 _clamp_buy_zones 對齊）：{mn: Vector3, mx: Vector3}；空 = 不限制
var buy_zone := {}


func set_walls(map_walls: Array) -> void:
	walls = map_walls


func set_buy_zone(mn: Vector3, mx: Vector3) -> void:
	buy_zone = {"mn": mn, "mx": mx}


func clear_buy_zone() -> void:
	buy_zone = {}


func max_speed() -> float:
	var base := RUN_SPEED
	if crouching:
		base = RUN_SPEED * CROUCH_RATIO
	elif walking:
		base = RUN_SPEED * WALK_RATIO
	return base * ads_speed_mult


func step(dir: Vector2, walk: bool, crouch: bool, jump: bool, dt: float) -> void:
	# 1) 計時器
	_jump_buffer = maxf(0.0, _jump_buffer - dt)
	_coyote = maxf(0.0, _coyote - dt)
	if jump:
		_jump_buffer = JUMP_BUFFER_TIME
	# 2) 姿態
	crouching = crouch
	walking = walk
	# 3) 水平移動
	var md := Vector3(dir.x, 0.0, dir.y)
	if md.length_squared() > 0.0:
		md = md.normalized()
	if on_ground:
		_coyote = COYOTE_TIME
		_ground_move(md, dt)
	else:
		_air_move(md, dt)
	# 4) 重力
	if not on_ground:
		vel.y -= GRAVITY * dt
	# 5) 跳躍
	if on_ground and _jump_buffer > 0.0:
		vel.y = JUMP_SPEED
		on_ground = false
		_jump_buffer = 0.0
	# 6) 積分
	pos += vel * dt
	# 7) 牆壁碰撞（水平推離 + 消除朝牆速度 → 沿牆滑移）
	for pass_i in range(COLLISION_PASSES):
		if not _resolve_walls():
			break
	# 8) 買槍區限制（與伺服器 _clamp_buy_zones 對齊）
	if not buy_zone.is_empty():
		var mn: Vector3 = buy_zone["mn"]
		var mx: Vector3 = buy_zone["mx"]
		var old_x := pos.x
		var old_z := pos.z
		pos.x = clampf(pos.x, mn.x, mx.x)
		pos.z = clampf(pos.z, mn.z, mx.z)
		if pos.x != old_x:
			if (vel.x > 0.0) == (pos.x > old_x):
				vel.x = 0.0
		if pos.z != old_z:
			if (vel.z > 0.0) == (pos.z > old_z):
				vel.z = 0.0
	# 9) 地面夾取
	if pos.y <= 0.0 and vel.y <= 0.0:
		if not on_ground:
			time_since_land = 0.0
		else:
			time_since_land += dt
		pos.y = 0.0
		vel.y = 0.0
		on_ground = true
	else:
		time_since_land += dt


func _ground_move(md: Vector3, dt: float) -> void:
	var ms := max_speed()
	var hvel := Vector3(vel.x, 0.0, vel.z)
	var new_h: Vector3
	if md.length_squared() > 0.0:
		var decel := GROUND_ACCEL
		if hvel.length_squared() > 0.0 and hvel.normalized().dot(md) < -0.3:
			decel = OPPOSITE_DECEL
		new_h = _approach(hvel, md * ms, decel * dt)
	else:
		new_h = _approach(hvel, Vector3.ZERO, GROUND_FRICTION * dt)
	if new_h.length_squared() > ms * ms:
		new_h = new_h.normalized() * ms
	vel.x = new_h.x
	vel.z = new_h.z


func _air_move(md: Vector3, dt: float) -> void:
	var hvel := Vector3(vel.x, 0.0, vel.z)
	var new_h := _approach(hvel, md * RUN_SPEED, AIR_ACCEL * dt)
	vel.x = new_h.x
	vel.z = new_h.z


func _resolve_walls() -> bool:
	"""與 server/game/collision.py resolve_player_wall 對齊：推離 + 速度消解。"""
	var any_hit := false
	for wall in walls:
		var mn := Vector3(wall["mn"].x, wall["mn"].y, wall["mn"].z)
		var mx := Vector3(wall["mx"].x, wall["mx"].y, wall["mx"].z)
		# 垂直區間重疊（玩家 [y, y+height] vs 牆 [mn.y, mx.y]）
		if pos.y + PLAYER_HEIGHT <= mn.y or pos.y >= mx.y:
			continue
		# 最近點推離（圓心在 AABB 外）
		var cx := clampf(pos.x, mn.x, mx.x)
		var cz := clampf(pos.z, mn.z, mx.z)
		var dx := pos.x - cx
		var dz := pos.z - cz
		var d2 := dx * dx + dz * dz
		if d2 >= PLAYER_RADIUS * PLAYER_RADIUS - 1e-12:
			continue
		var nx: float
		var nz: float
		var push: float
		if d2 > 1e-12:
			var d := sqrt(d2)
			push = PLAYER_RADIUS - d
			nx = dx / d
			nz = dz / d
		else:
			# 圓心在 AABB 內 → 四個面取最小位移
			var cands := [
				[absf((mn.x - PLAYER_RADIUS) - pos.x), -1.0, 0.0],
				[absf((mx.x + PLAYER_RADIUS) - pos.x), 1.0, 0.0],
				[absf((mn.z - PLAYER_RADIUS) - pos.z), 0.0, -1.0],
				[absf((mx.z + PLAYER_RADIUS) - pos.z), 0.0, 1.0],
			]
			var best: Array = cands[0]
			for c in cands:
				if c[0] < best[0]:
					best = c
			nx = best[1]
			nz = best[2]
			push = best[0]
		pos.x += nx * push
		pos.z += nz * push
		# 消除朝牆速度分量（保留切線 → 滑移）
		var vn := vel.x * nx + vel.z * nz
		if vn < 0.0:
			vel.x -= vn * nx
			vel.z -= vn * nz
		any_hit = true
	return any_hit


func _approach(v: Vector3, target: Vector3, max_delta: float) -> Vector3:
	var diff := target - v
	var dist := diff.length()
	if dist <= max_delta or dist < 1e-9:
		return target
	return v + diff * (max_delta / dist)
