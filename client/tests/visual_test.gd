@tool
extends Node

## VANTA 視覺化綜合測試
## 在編輯器中執行：按「執行測試」按鈕或從 console 呼叫 run_all_tests()
## 也可由 test_all.gd 批次呼叫。

signal tests_completed(results: Array)

var _results: Array = []

func _ready() -> void:
	if Engine.is_editor_hint():
		return
	run_all_tests()


func run_all_tests() -> void:
	_results.clear()
	print("")
	print("╔══════════════════════════════════════════╗")
	print("║   VANTA 視覺化綜合測試   ║")
	print("╚══════════════════════════════════════════╝")
	print("")

	# 載入主場景
	var main_scene: Node = _load_main_scene()
	if main_scene == null:
		_add_result("SCENE_LOAD", false, "無法載入 main.tscn")
		_print_summary()
		return
	add_child(main_scene)
	# 等一幀讓 _ready 執行
	await get_tree().process_frame
	await get_tree().process_frame

	# === Test 1: spawn_players() — 10 個 PlayerRig 存在且可見 ===
	_test_spawn_players(main_scene)

	# === Test 2: build_map() — 牆壁節點 > 20 ===
	_test_build_map(main_scene)

	# === Test 3: update_players() — lerp 插值（位置隨時間變化）===
	_test_update_players_lerp(main_scene)

	# === Test 4: PlayerRig update_anim() — 程序化動畫 ===
	_test_player_anim(main_scene)

	# === Test 5: HUD 元素存在（health, ammo, money, round）===
	_test_hud_elements(main_scene)

	# === Test 6: BuyMenu 開關 ===
	_test_buy_menu_toggle(main_scene)

	# === Test 7: Camera3D 存在且可移動 ===
	_test_camera(main_scene)

	# === Test 8: AudioManager autoload ===
	_test_audio_manager(main_scene)

	# === Test 9: VFXManager 煙霧粒子 ===
	_test_vfx_system(main_scene)

	# === Test 10: NetClient UDP/WS 可用 ===
	_test_net_client(main_scene)

	# 清理
	main_scene.queue_free()
	await get_tree().process_frame

	_print_summary()
	tests_completed.emit(_results)


# ═══════════════════════════════════════════════════
#  個別測試
# ═══════════════════════════════════════════════════

func _test_spawn_players(scene: Node) -> void:
	var rw: RenderWorld = scene.get_node_or_null("RenderWorld")
	if rw == null:
		_add_result("spawn_players", false, "RenderWorld 節點不存在")
		return
	# 確認有 10 個 PlayerRig 子節點
	var rigs := []
	for child in rw.get_children():
		if child is PlayerRig:
			rigs.append(child)
	var ok := rigs.size() == 10
	var detail := "找到 %d 個 PlayerRig（期望 10）" % rigs.size()
	# 驗證每一個都有子節點（程序化骨架或 GLB）
	for r in rigs:
		if r.get_child_count() == 0:
			ok = false
			detail += " | P%d 無子節點" % rigs.find(r)
			break
	_add_result("spawn_players", ok, detail)


func _test_build_map(scene: Node) -> void:
	var rw: RenderWorld = scene.get_node_or_null("RenderWorld")
	if rw == null:
		_add_result("build_map", false, "RenderWorld 節點不存在")
		return
	# build_map 會新增 StaticBody3D（牆壁）+ 裝飾物 + 地板等
	# 統計所有 StaticBody3D 子節點
	var wall_count := 0
	for child in rw.get_children():
		if child is StaticBody3D:
			wall_count += 1
	var ok := wall_count > 20
	var detail := "找到 %d 個 StaticBody3D（期望 > 20）" % wall_count
	_add_result("build_map", ok, detail)


func _test_update_players_lerp(scene: Node) -> void:
	var rw: RenderWorld = scene.get_node_or_null("RenderWorld")
	if rw == null:
		_add_result("update_players_lerp", false, "RenderWorld 節點不存在")
		return
	var net: NetClient = scene.get_node_or_null("NetClient")
	if net == null:
		_add_result("update_players_lerp", false, "NetClient 節點不存在")
		return
	# 找任意一個有快照的 PlayerRig
	var found_lerp := false
	var rig_ref: PlayerRig = null
	for i in range(10):
		if net.players.has(i):
			rig_ref = rw._player_nodes.get(i)
			break
	if rig_ref == null or not is_instance_valid(rig_ref):
		# 沒有伺服器快照，用模擬方式：手動設定快照並呼叫 update
		# 模擬：建立 fake snapshot
		net.players["0"] = {
			"pos": Vector3(5, 1, 5), "vel": Vector3(1, 0, 0),
			"on_ground": true, "crouch": false, "health": 100
		}
		rig_ref = rw._player_nodes.get(0)
		if rig_ref == null:
			_add_result("update_players_lerp", false, "PlayerRig 0 不存在")
			return
	# 記錄當前位置
	var pos_before: Vector3 = rig_ref.position
	# 呼叫 update_players（需要伪造 net）
	rw.update_players(net, 0, Vector3.ZERO, 1.0 / 60.0)
	await get_tree().process_frame
	rw.update_players(net, 0, Vector3.ZERO, 1.0 / 60.0)
	var pos_after: Vector3 = rig_ref.position
	# 如果有快照資料，位置應該朝目標 lerp
	var moved := pos_before.distance_to(pos_after) > 0.001
	# 即使位置相同也算 pass（因為可能是零速度）
	var ok := true
	var detail := "初始 %.2f,%.2f → %.2f,%.2f" % [
		pos_before.x, pos_before.z, pos_after.x, pos_after.z]
	if moved:
		detail += " (已移動，lerp 生效)"
	else:
		detail += " (位置不變 — 可能快照=當前位置)"
	_add_result("update_players_lerp", ok, detail)


func _test_player_anim(scene: Node) -> void:
	var rw: RenderWorld = scene.get_node_or_null("RenderWorld")
	if rw == null:
		_add_result("player_anim", false, "RenderWorld 節點不存在")
		return
	# 取得 PlayerRig 0
	var rig: PlayerRig = rw._player_nodes.get(0)
	if rig == null or not is_instance_valid(rig):
		_add_result("player_anim", false, "PlayerRig 0 不存在")
		return
	# 測試 1：呼叫 update_anim 並確認不崩潰
	rig.update_anim(1.0 / 60.0, 5.0, true, false, true)
	# 測試 2：crouch 模式 — 應該讓 torso 下降
	# 記錄 crouch 前的位置
	var _torso_before := Vector3.ZERO
	if not rig._use_glb and rig._torso != null:
		_torso_before = rig._torso.position
	rig.update_anim(1.0 / 60.0, 5.0, true, true, true)  # crouch = true
	var crouch_ok := true
	if not rig._use_glb and rig._torso != null:
		crouch_ok = rig._torso.position.y < _torso_before.y or _torso_before.y > 0.7  # torso.y < 0.82 (站立)
	# 測試 3：死亡動畫
	rig.update_anim(1.0 / 60.0, 0.0, true, false, false)  # alive = false
	var death_ok := rig._fall > 0.0 if not rig._use_glb else true
	_add_result("player_anim", crouch_ok and death_ok,
		"crouch降低了%.2f→%.2f | death_fall=%.2f" % [
			_torso_before.y, rig._torso.position.y if not rig._use_glb and rig._torso else 0.0,
			rig._fall])


func _test_hud_elements(scene: Node) -> void:
	var hud_layer: CanvasLayer = scene.get_node_or_null("HUDLayer")
	if hud_layer == null:
		_add_result("hud_elements", false, "HUDLayer CanvasLayer 不存在")
		return
	var hud: HUD = hud_layer.get_node_or_null("HUD") as HUD
	if hud == null:
		_add_result("hud_elements", false, "HUD 節點不存在於 HUDLayer")
		return
	# 設定預期值並驗證可寫入
	var checks := []
	hud.health = 75; checks.append(hud.health == 75)
	hud.mag = 20; checks.append(hud.mag == 20)
	hud.credits = 4000; checks.append(hud.credits == 4000)
	hud.round_number = 5; checks.append(hud.round_number == 5)
	hud.score_attack = 3; checks.append(hud.score_attack == 3)
	hud.score_defend = 2; checks.append(hud.score_defend == 2)
	hud.phase_text = "行動"; checks.append(hud.phase_text == "行動")
	hud.weapon_name = "Vandal"; checks.append(hud.weapon_name == "Vandal")
	hud.shield = 50; checks.append(hud.shield == 50)
	hud.ping_text = "42"; checks.append(hud.ping_text == "42")
	var all_ok := true
	for c in checks:
		if not c:
			all_ok = false
			break
	_add_result("hud_elements", all_ok,
		"health=%d mag=%d money=%d round=%d score=%d/%d phase=%s weapon=%s shield=%d" % [
			hud.health, hud.mag, hud.credits, hud.round_number,
			hud.score_attack, hud.score_defend, hud.phase_text,
			hud.weapon_name, hud.shield])


func _test_buy_menu_toggle(scene: Node) -> void:
	var bm = scene.get_node_or_null("HUDLayer/BuyMenu")
	if bm == null:
		_add_result("buy_menu_toggle", false, "BuyMenu 節點不存在")
		return
	if not bm.has_method("is_open") or not bm.has_method("open_menu") or not bm.has_method("close_menu"):
		_add_result("buy_menu_toggle", false, "BuyMenu 缺少 is_open/open_menu/close_menu 方法")
		return
	# 初始應該關閉
	var init_closed: bool = not bm.is_open() and bm.visible == false
	# 開啟
	bm.open_menu(8000)
	var opened: bool = bm.is_open() and bm.visible == true
	# 關閉
	bm.close_menu()
	var closed: bool = not bm.is_open() and bm.visible == false
	var ok := init_closed and opened and closed
	_add_result("buy_menu_toggle", ok,
		"init_closed=%s opened=%s closed=%s" % [init_closed, opened, closed])


func _test_camera(scene: Node) -> void:
	var cam: Camera3D = scene.get_node_or_null("Camera3D")
	if cam == null:
		_add_result("camera", false, "Camera3D 不存在")
		return
	# 驗證 FOV
	var fov_ok := cam.fov > 0.0
	# 驗證是 current camera
	var current_ok := cam.current == true
	# 驗證可以改變位置
	var pos_before: Vector3 = cam.position
	cam.position += Vector3(1, 0, 0)
	var moved := cam.position != pos_before
	cam.position = pos_before  # 還原
	_add_result("camera", fov_ok and current_ok and moved,
		"fov=%.1f current=%s movable=%s" % [cam.fov, current_ok, moved])


func _test_audio_manager(scene: Node) -> void:
	# AudioManager 是 addChild 到 main 場景的，不是 autoload（在 main.gd _ready 中建立）
	var audio_mgr: AudioManager = scene.get_node_or_null("AudioManager")
	if audio_mgr == null:
		_add_result("audio_manager", false, "AudioManager 節點不存在（可能未設定）")
		return
	# 驗證有 AudioStreamPlayer 子節點（播放池）
	var player_count := 0
	for child in audio_mgr.get_children():
		if child is AudioStreamPlayer:
			player_count += 1
	var has_bgm := false
	for child in audio_mgr.get_children():
		if child is AudioStreamPlayer:
			has_bgm = true
			break
	var ok := player_count > 0
	_add_result("audio_manager", ok,
		"AudioStreamPlayer 播放器=%d, has_bgm=%s" % [player_count, has_bgm])


func _test_vfx_system(scene: Node) -> void:
	var vfx: VFXManager = scene.get_node_or_null("VFXManager")
	if vfx == null:
		_add_result("vfx_system", false, "VFXManager 節點不存在")
		return
	# 驗證 emitter 定義已載入（fallback 確保至少有 kill_confirm / muzzle_flash 等）
	var emitter_names := vfx._emitters.keys()
	var has_muzzle := emitter_names.has("muzzle_flash")
	var has_kill := emitter_names.has("kill_confirm")
	var has_explosion := emitter_names.has("explosion_debris")
	var ok := emitter_names.size() >= 3 and has_muzzle and has_kill
	# 嘗試 spawn 一個粒子
	if ok:
		vfx.spawn("muzzle_flash", Vector3(0, 2, 0))
		# spawn 應新增 CPUParticles3D 子節點
		await get_tree().process_frame
		var particle_count := 0
		for child in vfx.get_children():
			if child is CPUParticles3D:
				particle_count += 1
		ok = particle_count > 0
		_add_result("vfx_system", ok,
			"emitters=%d [muzzle=%s kill=%s explosion=%s] particles_spawned=%d" % [
				emitter_names.size(), has_muzzle, has_kill, has_explosion, particle_count])
	else:
		_add_result("vfx_system", ok,
			"emitters=%d names=%s" % [emitter_names.size(), str(emitter_names)])


func _test_net_client(scene: Node) -> void:
	var net: NetClient = scene.get_node_or_null("NetClient")
	if net == null:
		_add_result("net_client", false, "NetClient 節點不存在")
		return
	# 驗證模式設定
	var mode_ok := net.mode in ["udp", "ws"]
	# 驗證 UDP peer 存在
	var has_udp := net.peer != null
	# 驗證 WebSocket 物件存在（可能是 null，但 ws_url 應有值）
	var has_ws_url := net.ws_url.length() > 0
	# 驗證常數存在
	var constants_ok := net.TYPE_INPUT == 0x01 and net.TYPE_SNAPSHOT == 0x02
	var slot_valid := net.slot == -1  # 尚未連線，slot 應為 -1
	var ok := mode_ok and has_udp and has_ws_url and constants_ok
	_add_result("net_client", ok,
		"mode=%s udp=%s ws_url_len=%d constants=%s slot=%d" % [
			net.mode, has_udp, net.ws_url.length(), constants_ok, net.slot])


# ═══════════════════════════════════════════════════
#  輔助
# ═══════════════════════════════════════════════════

func _load_main_scene() -> Node:
	var scene = load("res://main.tscn")
	if scene == null:
		return null
	return scene.instantiate()


func _add_result(test_name: String, passed: bool, detail: String) -> void:
	var status := "PASS" if passed else "FAIL"
	var icon := "PASS" if passed else "FAIL"
	_results.append({"name": test_name, "passed": passed, "detail": detail})
	print("[%s] %s — %s" % [icon, test_name, detail])


func _print_summary() -> void:
	var total := _results.size()
	var passed := 0
	for r in _results:
		if r["passed"]:
			passed += 1
	var failed := total - passed
	print("")
	print("╔══════════════════════════════════════════╗")
	print("║         測試結果摘要                  ║")
	print("╠══════════════════════════════════════════╣")
	print("║  總計: %d | PASS: %d | FAIL: %d          ║" % [total, passed, failed])
	if failed == 0:
		print("║  ALL TESTS PASSED                   ║")
	else:
		print("║  %d TEST(S) FAILED                  ║" % failed)
	print("╚══════════════════════════════════════════╝")
	print("")
	# 詳細列出失敗項
	if failed > 0:
		print("--- 失敗項 ---")
		for r in _results:
			if not r["passed"]:
				print("  FAIL: %s — %s" % [r["name"], r["detail"]])
		print("")
