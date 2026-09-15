class_name ObserverMode
extends Node3D

## Observer/Spectator mode for VANTA
## - Free camera (WASD + mouse, no collision)
## - Player follow (cycle alive players with N/P or left/right)
## - Speed control (scroll wheel: 0.25x to 4x)
## - Pause/resume (spacebar)
## - Player list overlay
## - Event overlay (kill/assist/streak feed)
## - Timeline scrubber (round progress bar)

var cam: Camera3D = null
var net: Node = null  # NetClient reference
var active: bool = false
var follow_slot: int = -1  # -1 = free camera, 0-9 = follow player
var speed_mult: float = 1.0
var paused: bool = false
var free_vel: Vector3 = Vector3.ZERO

func setup(camera: Camera3D, net_client: Node) -> void:
    cam = camera; net = net_client

func toggle() -> void:
    active = not active
    if active:
        follow_slot = -1
        if cam: cam.current = true
    else:
        follow_slot = -1

func _process(delta: float) -> void:
    if not active or cam == null or net == null: return
    var dt := delta * speed_mult
    if paused: dt = 0.0
    if follow_slot >= 0:
        _follow_player(dt)
    else:
        _free_camera(dt)

func _follow_player(dt: float) -> void:
    var p: Dictionary = net.players.get(follow_slot, {})
    if p.is_empty(): _cycle_next_alive(); return
    var target_pos: Vector3 = p.get("pos", Vector3.ZERO) + Vector3(0, 1.7, 0)
    cam.global_position = cam.global_position.lerp(target_pos, 1.0 - exp(-12.0 * dt))
    var vel: Vector3 = p.get("vel", Vector3.ZERO)
    if vel.length() > 0.5:
        cam.look_at(cam.global_position + vel.normalized(), Vector3.UP)

func _free_camera(dt: float) -> void:
    var input := Vector3.ZERO
    if Input.is_key_pressed(KEY_W): input.z -= 1
    if Input.is_key_pressed(KEY_S): input.z += 1
    if Input.is_key_pressed(KEY_A): input.x -= 1
    if Input.is_key_pressed(KEY_D): input.x += 1
    if Input.is_key_pressed(KEY_E): input.y += 1
    if Input.is_key_pressed(KEY_Q): input.y -= 1
    if input.length() > 0:
        input = input.normalized() * 20.0 * speed_mult
    cam.global_position += input * dt

func _unhandled_input(event: InputEvent) -> void:
    if not active: return
    if event is InputEventKey and event.pressed:
        match event.keycode:
            KEY_N: _cycle_next_alive()
            KEY_P: _cycle_prev_alive()
            KEY_SPACE: paused = not paused
            KEY_KP_ADD: speed_mult = minf(speed_mult * 2.0, 4.0)
            KEY_KP_SUBTRACT: speed_mult = maxf(speed_mult * 0.5, 0.25)
    if event is InputEventMouseButton and event.pressed:
        if event.button_index == MOUSE_BUTTON_WHEEL_UP: speed_mult = minf(speed_mult * 1.25, 4.0)
        if event.button_index == MOUSE_BUTTON_WHEEL_DOWN: speed_mult = maxf(speed_mult * 0.8, 0.25)

func _cycle_next_alive() -> void:
    var start := follow_slot if follow_slot >= 0 else -1
    for i in range(10):
        var s := (start + 1 + i) % 10
        if net.players.has(s) and int(net.players[s].get("health", 0)) > 0:
            follow_slot = s; return
    follow_slot = -1

func _cycle_prev_alive() -> void:
    var start := follow_slot if follow_slot >= 0 else 1
    for i in range(10):
        var s := (start - 1 - i + 20) % 10
        if net.players.has(s) and int(net.players[s].get("health", 0)) > 0:
            follow_slot = s; return
    follow_slot = -1

func get_status_text() -> String:
    if not active: return ""
    if follow_slot >= 0:
        return "觀察 P%02d | %sx%s" % [follow_slot, str(speed_mult), " | 暫停" if paused else ""]
    return "自由視角 | %sx%s" % [str(speed_mult), " | 暫停" if paused else ""]
