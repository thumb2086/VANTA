class_name AnimationController
extends RefCounted

## Procedural animation controller — Valorant-quality without external .glb files.
## Works with CharacterGeneratorV2 (45-part rig) and falls back to old box rig.
##
## Usage:
##   var anim := AnimationController.new()
##   anim.bind(root_node)        # auto-discovers parts by name
##   anim.update(dt, speed, on_ground, crouch, alive, shooting, reloading, ability_active)

# ── Part references (discovered by name matching) ──
var _head: Node3D
var _visor: Node3D
var _jaw: Node3D
var _neck: Node3D
var _chest: Node3D
var _chest_plate: Node3D
var _abdomen: Node3D
var _belt: Node3D
var _collar: Node3D
var _backpack: Node3D
var _neck_guard: Node3D

var _upper_arm_l: Node3D
var _upper_arm_r: Node3D
var _elbow_l: Node3D
var _elbow_r: Node3D
var _forearm_l: Node3D
var _forearm_r: Node3D
var _forearm_guard_l: Node3D
var _forearm_guard_r: Node3D
var _wrist_l: Node3D
var _wrist_r: Node3D
var _hand_l: Node3D
var _hand_r: Node3D
var _shoulder_pad_l: Node3D
var _shoulder_pad_r: Node3D

var _hip_l: Node3D
var _hip_r: Node3D
var _upper_leg_l: Node3D
var _upper_leg_r: Node3D
var _knee_l: Node3D
var _knee_r: Node3D
var _knee_guard_l: Node3D
var _knee_guard_r: Node3D
var _shin_l: Node3D
var _shin_r: Node3D
var _ankle_l: Node3D
var _ankle_r: Node3D
var _foot_l: Node3D
var _foot_r: Node3D

# ── State ──
var _time := 0.0
var _walk_cycle := 0.0
var _bob := 0.0
var _breath := 0.0
var _death_progress := 0.0
var _recoil_progress := 0.0
var _reload_progress := 0.0
var _reload_phase := 0  # 0=none, 1=drop mag, 2=insert
var _ability_progress := 0.0
var _strafe_lean := 0.0
var _landing_squash := 0.0
var _prev_on_ground := true

# ── Original positions for reset ──
var _orig_positions := {}
var _orig_rotations := {}
var _root: Node3D = null
var _bound := false


func bind(root: Node3D) -> void:
	_root = root
	_discover_parts(root)
	_snapshot_originals()
	_bound = true


func is_bound() -> bool:
	return _bound and _root != null and is_instance_valid(_root)


func update(dt: float, speed: float, on_ground: bool, crouch: bool,
		alive: bool, shooting: bool = false, reloading: bool = false,
		ability_active: bool = false, strafe_dir: float = 0.0) -> void:
	if not is_bound():
		return

	_time += dt

	# ── State transitions ──
	if not alive:
		_update_death(dt)
		return
	if _death_progress > 0.0:
		_reset_all()

	_recoil_progress = maxf(0.0, _recoil_progress - dt * 4.0)

	if reloading and _reload_phase == 0:
		_reload_phase = 1
		_reload_progress = 0.0
	if _reload_phase > 0:
		_reload_progress += dt * 2.0
		if _reload_progress >= 1.0:
			_reload_progress = 0.0
			_reload_phase = (_reload_phase + 1) % 3  # 1→2→0

	if ability_active:
		_ability_progress = minf(1.0, _ability_progress + dt * 3.0)
	else:
		ability_active = false
		_ability_progress = maxf(0.0, _ability_progress - dt * 2.0)

	if shooting:
		_recoil_progress = 1.0

	# ── Strafe lean ──
	var target_lean := strafe_dir * 0.08
	_strafe_lean = lerpf(_strafe_lean, target_lean, 1.0 - exp(-6.0 * dt))

	# ── Landing squash ──
	if on_ground and not _prev_on_ground:
		_landing_squash = 1.0
	_prev_on_ground = on_ground
	_landing_squash = maxf(0.0, _landing_squash - dt * 5.0)

	# ── Walk cycle ──
	if speed > 0.3 and on_ground:
		var cycle_speed := 6.0 + speed * 1.2
		_walk_cycle += dt * cycle_speed
	elif not on_ground:
		# slow cycle in air
		_walk_cycle += dt * 2.0

	# ── Breathing ──
	_breath += dt * 2.2

	# ── Apply ──
	_apply_idle(dt, speed, on_ground, crouch)
	_apply_limbs(dt, speed, on_ground, crouch)
	_apply_arms(dt, speed, on_ground, crouch, shooting, reloading)
	_apply_strafe(dt, speed, on_ground)
	_apply_recoil(dt)
	_apply_reload(dt)
	_apply_ability(dt, ability_active)
	_apply_landing_squash(dt, speed, on_ground, crouch)


# ═══════════════════ Animation Phases ═══════════════════

func _apply_idle(dt: float, speed: float, on_ground: bool, crouch: bool) -> void:
	if _chest == null:
		return

	var breath_sin := sin(_breath) * 0.003
	var breath_scale := 1.0 + sin(_breath) * 0.008

	# Head micro-movement
	if _head:
		var hx := sin(_time * 0.7) * 0.008
		var hz := cos(_time * 0.5) * 0.005
		_set_pos(_head, "Head", hx, 0, hz)

	# Torso breathing
	_chest.scale = Vector3(1.0, breath_scale, 1.0)

	# Crouch offset
	var crouch_y := -0.28 if crouch else 0.0
	if not on_ground:
		crouch_y -= 0.05

	_apply_body_offset(crouch_y, crouch, on_ground)


func _apply_body_offset(crouch_y: float, crouch: bool, on_ground: bool) -> void:
	# Move entire body down for crouch
	if _chest:
		_set_pos(_chest, "Chest", 0, CHEST_Y + crouch_y, 0)
	if _abdomen:
		_set_pos(_abdomen, "Abdomen", 0, ABDOMEN_Y + crouch_y, 0)
	if _head:
		_set_pos(_head, "Head", _head.position.x, HEAD_Y + crouch_y, _head.position.z)
	if _visor:
		_set_pos(_visor, "Visor", 0, HEAD_Y + 0.015 + crouch_y, HEAD_R * 0.88)
	if _jaw:
		_set_pos(_jaw, "Jaw", 0, HEAD_Y - HEAD_R * 0.6 + crouch_y, HEAD_R * 0.45)
	if _neck:
		_set_pos(_neck, "Neck", 0, NECK_Y + crouch_y, 0)
	if _collar:
		_set_pos(_collar, "Collar", 0, CHEST_Y + CHEST_H * 0.52 + crouch_y, 0)
	if _chest_plate:
		_set_pos(_chest_plate, "ChestPlate", 0, CHEST_Y + 0.04 + crouch_y, CHEST_D * 0.52)
	if _belt:
		_set_pos(_belt, "Belt", 0, ABDOMEN_Y - ABDOMEN_H * 0.45 + crouch_y, 0)
	if _backpack:
		_set_pos(_backpack, "Backpack", 0, CHEST_Y + 0.02 + crouch_y, -CHEST_D * 0.5 - BACKPACK_D * 0.5)
	if _neck_guard:
		_set_pos(_neck_guard, "NeckGuard", 0, NECK_Y + NECK_H * 0.1 + crouch_y, 0)

	# Shoulder pads
	if _shoulder_pad_l:
		_set_pos(_shoulder_pad_l, "ShoulderPadL", -SHOULDER_SPREAD, SHOULDER_Y + crouch_y, 0)
	if _shoulder_pad_r:
		_set_pos(_shoulder_pad_r, "ShoulderPadR", SHOULDER_SPREAD, SHOULDER_Y + crouch_y, 0)

	# Arms
	if _upper_arm_l:
		_set_pos(_upper_arm_l, "UpperArmL", -SHOULDER_SPREAD, SHOULDER_Y - UPPER_ARM_LEN * 0.5 + crouch_y, 0)
	if _upper_arm_r:
		_set_pos(_upper_arm_r, "UpperArmR", SHOULDER_SPREAD, SHOULDER_Y - UPPER_ARM_LEN * 0.5 + crouch_y, 0)

	var elbow_y := SHOULDER_Y - UPPER_ARM_LEN + crouch_y
	if _elbow_l:
		_set_pos(_elbow_l, "ElbowL", -SHOULDER_SPREAD, elbow_y, 0)
	if _elbow_r:
		_set_pos(_elbow_r, "ElbowR", SHOULDER_SPREAD, elbow_y, 0)
	if _forearm_l:
		_set_pos(_forearm_l, "ForearmL", -SHOULDER_SPREAD, elbow_y - FOREARM_LEN * 0.5, 0)
	if _forearm_r:
		_set_pos(_forearm_r, "ForearmR", SHOULDER_SPREAD, elbow_y - FOREARM_LEN * 0.5, 0)
	if _forearm_guard_l:
		_set_pos(_forearm_guard_l, "ForearmGuardL", -SHOULDER_SPREAD, elbow_y - FOREARM_LEN * 0.45, FOREARM_R * 1.2)
	if _forearm_guard_r:
		_set_pos(_forearm_guard_r, "ForearmGuardR", SHOULDER_SPREAD, elbow_y - FOREARM_LEN * 0.45, FOREARM_R * 1.2)

	var wrist_y := elbow_y - FOREARM_LEN
	if _wrist_l:
		_set_pos(_wrist_l, "WristL", -SHOULDER_SPREAD, wrist_y, 0)
	if _wrist_r:
		_set_pos(_wrist_r, "WristR", SHOULDER_SPREAD, wrist_y, 0)
	if _hand_l:
		_set_pos(_hand_l, "HandL", -SHOULDER_SPREAD, wrist_y - HAND_H * 0.5, 0)
	if _hand_r:
		_set_pos(_hand_r, "HandR", SHOULDER_SPREAD, wrist_y - HAND_H * 0.5, 0)

	# Legs
	var leg_y_offset := crouch_y * 0.5
	if _hip_l:
		_set_pos(_hip_l, "HipL", -HIP_SPREAD, HIP_Y + leg_y_offset, 0)
	if _hip_r:
		_set_pos(_hip_r, "HipR", HIP_SPREAD, HIP_Y + leg_y_offset, 0)
	if _upper_leg_l:
		_set_pos(_upper_leg_l, "UpperLegL", -HIP_SPREAD, HIP_Y - UPPER_LEG_LEN * 0.5 + leg_y_offset, 0)
	if _upper_leg_r:
		_set_pos(_upper_leg_r, "UpperLegR", HIP_SPREAD, HIP_Y - UPPER_LEG_LEN * 0.5 + leg_y_offset, 0)

	var knee_y := HIP_Y - UPPER_LEG_LEN + leg_y_offset
	if _knee_l:
		_set_pos(_knee_l, "KneeL", -HIP_SPREAD, knee_y, KNEE_R * 0.6)
	if _knee_r:
		_set_pos(_knee_r, "KneeR", HIP_SPREAD, knee_y, KNEE_R * 0.6)
	if _knee_guard_l:
		_set_pos(_knee_guard_l, "KneeGuardL", -HIP_SPREAD, knee_y, KNEE_R * 1.2)
	if _knee_guard_r:
		_set_pos(_knee_guard_r, "KneeGuardR", HIP_SPREAD, knee_y, KNEE_R * 1.2)
	if _shin_l:
		_set_pos(_shin_l, "ShinL", -HIP_SPREAD, knee_y - SHIN_LEN * 0.5, 0)
	if _shin_r:
		_set_pos(_shin_r, "ShinR", HIP_SPREAD, knee_y - SHIN_LEN * 0.5, 0)

	var ankle_y := knee_y - SHIN_LEN
	if _ankle_l:
		_set_pos(_ankle_l, "AnkleL", -HIP_SPREAD, ankle_y, 0)
	if _ankle_r:
		_set_pos(_ankle_r, "AnkleR", HIP_SPREAD, ankle_y, 0)
	if _foot_l:
		_set_pos(_foot_l, "FootL", -HIP_SPREAD, ankle_y + FOOT_H * 0.5, FOOT_LEN * 0.3)
	if _foot_r:
		_set_pos(_foot_r, "FootR", HIP_SPREAD, ankle_y + FOOT_H * 0.5, FOOT_LEN * 0.3)


func _apply_limbs(dt: float, speed: float, on_ground: bool, crouch: bool) -> void:
	if speed < 0.3 or not on_ground:
		# Reset leg/arm rotations
		_reset_rotation(_upper_leg_l, "UpperLegL")
		_reset_rotation(_upper_leg_r, "UpperLegR")
		_reset_rotation(_shin_l, "ShinL")
		_reset_rotation(_shin_r, "ShinR")
		_reset_rotation(_foot_l, "FootL")
		_reset_rotation(_foot_r, "FootR")
		if not on_ground:
			# Tuck legs in air
			if _upper_leg_l: _upper_leg_l.rotation.x = -0.5
			if _upper_leg_r: _upper_leg_r.rotation.x = 0.3
			if _shin_l: _shin_l.rotation.x = 0.4
			if _shin_r: _shin_r.rotation.x = 0.2
		return

	var amp := clampf(speed / 5.0, 0.0, 1.0)
	var swing := sin(_walk_cycle) * 0.7 * amp
	var lunge := maxf(0.0, -sin(_walk_cycle)) * 0.10 * amp

	# Legs — walk cycle
	if _upper_leg_l:
		_upper_leg_l.rotation.x = swing
		_upper_leg_l.position.y = HIP_Y - UPPER_LEG_LEN * 0.5 - absf(swing) * 0.10 + lunge
	if _upper_leg_r:
		_upper_leg_r.rotation.x = -swing
		_upper_leg_r.position.y = HIP_Y - UPPER_LEG_LEN * 0.5 - absf(swing) * 0.10 - lunge

	# Shin bend
	if _shin_l:
		_shin_l.rotation.x = maxf(0.0, -swing * 0.6)
	if _shin_r:
		_shin_r.rotation.x = maxf(0.0, swing * 0.6)

	# Feet flat
	if _foot_l:
		_foot_l.rotation.x = maxf(0.0, -swing * 0.25)
	if _foot_r:
		_foot_r.rotation.x = maxf(0.0, swing * 0.25)

	# Arms — opposite to legs
	if _upper_arm_l:
		_upper_arm_l.rotation.x = -swing * 0.55
	if _upper_arm_r:
		_upper_arm_r.rotation.x = swing * 0.55

	# Forearm slight bend
	if _forearm_l:
		_forearm_l.rotation.x = maxf(0.0, swing * 0.3)
	if _forearm_r:
		_forearm_r.rotation.x = maxf(0.0, -swing * 0.3)

	# Torso lean into movement
	if _chest:
		_chest.rotation.x = speed * 0.015


func _apply_arms(dt: float, speed: float, on_ground: bool, crouch: bool,
		shooting: bool, reloading: bool) -> void:
	# Crouch arms forward
	if crouch and on_ground:
		if _upper_arm_l:
			_upper_arm_l.rotation.x = -0.5
		if _upper_arm_r:
			_upper_arm_r.rotation.x = -0.5
		if _forearm_l:
			_forearm_l.rotation.x = -0.4
		if _forearm_r:
			_forearm_r.rotation.x = -0.4


func _apply_strafe(dt: float, speed: float, on_ground: bool) -> void:
	if _chest:
		_chest.rotation.z = _strafe_lean
	if _head:
		_head.rotation.z = _strafe_lean * 0.5


func _apply_recoil(dt: float) -> void:
	if _recoil_progress <= 0.0:
		return
	var t := _recoil_progress
	var kick := sin(t * PI) * 0.06
	# Torso backward lean
	if _chest:
		_chest.rotation.x -= kick
	# Right arm raise (gun hand)
	if _upper_arm_r:
		_upper_arm_r.rotation.x -= kick * 1.5
	# Head slight jerk back
	if _head:
		_head.rotation.x -= kick * 0.3


func _apply_reload(dt: float) -> void:
	if _reload_phase == 0:
		return

	if _reload_phase == 1:
		# Phase 1: drop magazine — right hand moves down
		var t := _reload_progress
		if _hand_r:
			_hand_r.position.y -= sin(t * PI) * 0.08
		if _forearm_r:
			_forearm_r.rotation.x = -0.6 * sin(t * PI)
	elif _reload_phase == 2:
		# Phase 2: insert magazine — right hand moves up
		var t := _reload_progress
		if _hand_r:
			_hand_r.position.y += sin(t * PI) * 0.08
		if _forearm_r:
			_forearm_r.rotation.x = 0.4 * sin(t * PI)


func _apply_ability(dt: float, active: bool) -> void:
	if _ability_progress <= 0.0:
		return
	# Left arm raise with glow
	var t := _ability_progress
	if _upper_arm_l:
		_upper_arm_l.rotation.x = -lerpf(0.0, 1.2, t)
		_upper_arm_l.rotation.z = lerpf(0.0, 0.3, t)
	if _forearm_l:
		_forearm_l.rotation.x = lerpf(0.0, -0.8, t)
	if _hand_l:
		_hand_l.position.z = lerpf(0.0, 0.15, t)
	# Head looks toward raised hand
	if _head:
		_head.rotation.z = lerpf(0.0, -0.15, t)


func _update_death(dt: float) -> void:
	_death_progress = minf(1.0, _death_progress + dt * 2.5)
	var t := _death_progress

	# Torso falls forward
	if _chest:
		_chest.rotation.x = lerpf(0.0, -PI * 0.45, t)
		_chest.position.y = lerpf(_chest.position.y, CHEST_Y * 0.3, t)

	# Head drops
	if _head:
		_head.rotation.x = lerpf(0.0, -PI * 0.3, minf(1.0, t * 1.5))
		_head.position.y = lerpf(_head.position.y, 0.5, t)

	# Arms go limp (outward)
	if _upper_arm_l:
		_upper_arm_l.rotation.x = lerpf(0.0, -0.8, t)
		_upper_arm_l.rotation.z = lerpf(0.0, 0.6, t)
	if _upper_arm_r:
		_upper_arm_r.rotation.x = lerpf(0.0, -0.6, t)
		_upper_arm_r.rotation.z = lerpf(0.0, -0.5, t)

	# Legs buckle
	if _upper_leg_l:
		_upper_leg_l.rotation.x = lerpf(0.0, 0.5, t)
	if _upper_leg_r:
		_upper_leg_r.rotation.x = lerpf(0.0, 0.7, t)
	if _shin_l:
		_shin_l.rotation.x = lerpf(0.0, 0.8, t)
	if _shin_r:
		_shin_r.rotation.x = lerpf(0.0, 0.6, t)

	# Squash
	var squash := lerpf(1.0, 0.5, t)
	if _root:
		_root.scale = Vector3(1.0, squash, 1.0)


func _reset_all() -> void:
	_death_progress = 0.0
	if _root:
		_root.scale = Vector3.ONE
	_reset_all_rotations()


# ═══════════════════ Part Discovery ═══════════════════

func _discover_parts(root: Node3D) -> void:
	_head = _find(root, "Head")
	_visor = _find(root, "Visor")
	_jaw = _find(root, "Jaw")
	_neck = _find(root, "Neck")
	_chest = _find(root, "Chest")
	_chest_plate = _find(root, "ChestPlate")
	_abdomen = _find(root, "Abdomen")
	_belt = _find(root, "Belt")
	_collar = _find(root, "Collar")
	_backpack = _find(root, "Backpack")
	_neck_guard = _find(root, "NeckGuard")

	_upper_arm_l = _find(root, "UpperArmL")
	_upper_arm_r = _find(root, "UpperArmR")
	_elbow_l = _find(root, "ElbowL")
	_elbow_r = _find(root, "ElbowR")
	_forearm_l = _find(root, "ForearmL")
	_forearm_r = _find(root, "ForearmR")
	_forearm_guard_l = _find(root, "ForearmGuardL")
	_forearm_guard_r = _find(root, "ForearmGuardR")
	_wrist_l = _find(root, "WristL")
	_wrist_r = _find(root, "WristR")
	_hand_l = _find(root, "HandL")
	_hand_r = _find(root, "HandR")
	_shoulder_pad_l = _find(root, "ShoulderPadL")
	_shoulder_pad_r = _find(root, "ShoulderPadR")

	_hip_l = _find(root, "HipL")
	_hip_r = _find(root, "HipR")
	_upper_leg_l = _find(root, "UpperLegL")
	_upper_leg_r = _find(root, "UpperLegR")
	_knee_l = _find(root, "KneeL")
	_knee_r = _find(root, "KneeR")
	_knee_guard_l = _find(root, "KneeGuardL")
	_knee_guard_r = _find(root, "KneeGuardR")
	_shin_l = _find(root, "ShinL")
	_shin_r = _find(root, "ShinR")
	_ankle_l = _find(root, "AnkleL")
	_ankle_r = _find(root, "AnkleR")
	_foot_l = _find(root, "FootL")
	_foot_r = _find(root, "FootR")


func _find(root: Node, target_name: String) -> Node3D:
	if root.name == target_name:
		return root
	for child in root.get_children():
		var found := _find(child, target_name)
		if found:
			return found
	return null


# ═══════════════════ Snapshot & Reset ═══════════════════

func _snapshot_originals() -> void:
	_orig_positions.clear()
	_orig_rotations.clear()
	_snapshot_node(_head, "Head")
	_snapshot_node(_visor, "Visor")
	_snapshot_node(_jaw, "Jaw")
	_snapshot_node(_neck, "Neck")
	_snapshot_node(_chest, "Chest")
	_snapshot_node(_chest_plate, "ChestPlate")
	_snapshot_node(_abdomen, "Abdomen")
	_snapshot_node(_belt, "Belt")
	_snapshot_node(_collar, "Collar")
	_snapshot_node(_backpack, "Backpack")
	_snapshot_node(_neck_guard, "NeckGuard")
	_snapshot_node(_upper_arm_l, "UpperArmL")
	_snapshot_node(_upper_arm_r, "UpperArmR")
	_snapshot_node(_forearm_l, "ForearmL")
	_snapshot_node(_forearm_r, "ForearmR")
	_snapshot_node(_hand_l, "HandL")
	_snapshot_node(_hand_r, "HandR")
	_snapshot_node(_upper_leg_l, "UpperLegL")
	_snapshot_node(_upper_leg_r, "UpperLegR")
	_snapshot_node(_shin_l, "ShinL")
	_snapshot_node(_shin_r, "ShinR")
	_snapshot_node(_foot_l, "FootL")
	_snapshot_node(_foot_r, "FootR")
	_snapshot_node(_shoulder_pad_l, "ShoulderPadL")
	_snapshot_node(_shoulder_pad_r, "ShoulderPadR")


func _snapshot_node(node: Node3D, key: String) -> void:
	if node:
		_orig_positions[key] = node.position
		_orig_rotations[key] = node.rotation


func _reset_all_rotations() -> void:
	for key in _orig_rotations:
		var node := _find(_root, key) if _root else null
		if node:
			node.rotation = _orig_rotations[key]
	for key in _orig_positions:
		var node := _find(_root, key) if _root else null
		if node:
			node.position = _orig_positions[key]


func _reset_rotation(node: Node3D, key: String) -> void:
	if node and _orig_rotations.has(key):
		node.rotation = _orig_rotations[key]


func _set_pos(node: Node3D, key: String, x: float, y: float, z: float) -> void:
	if node:
		node.position = Vector3(x, y, z)


# ═══════════════════ Ratio Constants (for _apply_body_offset) ═══════════════════
# Duplicated from CharacterGeneratorV2 so AnimationController works standalone.
const HEAD_R := 0.10
const HEAD_Y := 1.64
const NECK_R := 0.038
const NECK_H := 0.055
const NECK_Y := 1.56
const CHEST_W := 0.34
const CHEST_H := 0.28
const CHEST_D := 0.19
const CHEST_Y := 1.32
const ABDOMEN_W := 0.30
const ABDOMEN_H := 0.18
const ABDOMEN_D := 0.17
const ABDOMEN_Y := 1.10
const SHOULDER_Y := 1.44
const SHOULDER_SPREAD := 0.21
const UPPER_ARM_LEN := 0.27
const UPPER_ARM_R := 0.045
const ELBOW_R := 0.038
const FOREARM_LEN := 0.25
const FOREARM_R := 0.040
const WRIST_R := 0.032
const HAND_W := 0.065
const HAND_H := 0.08
const HAND_D := 0.035
const HIP_Y := 1.00
const HIP_SPREAD := 0.11
const UPPER_LEG_LEN := 0.38
const UPPER_LEG_R := 0.065
const KNEE_R := 0.050
const SHIN_LEN := 0.36
const SHIN_R := 0.050
const ANKLE_R := 0.035
const FOOT_W := 0.09
const FOOT_H := 0.05
const FOOT_LEN := 0.14
const BELT_H := 0.045
const COLLAR_H := 0.04
const BACKPACK_W := 0.22
const BACKPACK_H := 0.24
const BACKPACK_D := 0.08
