@tool
extends Node

## VANTA 批次測試執行器
## 在 Godot 編輯器中：選此節點 → 右鍵 → Run Tests
## 或在 console 呼叫：get_node("/root/TestRunner").run_all()

var _visual_test_script = preload("res://tests/visual_test.gd")
var _results_summary := ""


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	# 非 tool 模式自動執行
	call_deferred("run_all")


func run_all() -> void:
	print("")
	print("╔══════════════════════════════════════════════╗")
	print("║   VANTA 批次測試執行器               ║")
	print("║   %s                           ║" % Time.get_datetime_string_from_system(false, true))
	print("╚══════════════════════════════════════════════╝")
	print("")

	# --- Suite 1: 視覺化綜合測試 ---
	print(">>> Suite 1: 視覺化綜合測試 <<<")
	var vt = Node.new()
	vt.set_script(_visual_test_script)
	vt.name = "VisualTest"
	add_child(vt)
	# 等待測試完成
	await vt.tests_completed
	var suite1_results: Array = vt._results.duplicate()
	vt.queue_free()
	await get_tree().process_frame

	# --- Suite 2: Script 語法驗證 ---
	print("")
	print(">>> Suite 2: Script 語法驗證 <<<")
	var suite2_results := _run_syntax_check()
	# 手感契約：後座/準度 bundle 必須載入得動且與伺服器同源（資料驅動，非寫死）
	suite2_results.append_array(_run_recoil_bundle_check())

	# --- Suite 3: 場景結構完整性 ---
	print("")
	print(">>> Suite 3: 場景結構完整性 <<<")
	var suite3_results := _run_scene_structure_check()

	# --- 彙總 ---
	_print_final_summary(suite1_results, suite2_results, suite3_results)


func _run_syntax_check() -> Array:
	var results := []
	var scripts := [
		"res://scripts/main.gd",
		"res://scripts/render_world.gd",
		"res://scripts/player_rig.gd",
		"res://scripts/hud.gd",
		"res://scripts/recoil_model.gd",
		"res://scripts/buy_menu.gd",
		"res://scripts/net_client.gd",
		"res://scripts/audio_manager.gd",
		"res://scripts/vfx_manager.gd",
		"res://scripts/weapon_viewmodel.gd",
		"res://scripts/weapon_viewmodel_v2.gd",
		"res://scripts/weapon_geometry.gd",
		"res://scripts/skin_registry.gd",
		"res://scripts/skin_material.gd",
		"res://scripts/skin_progression.gd",
		"res://scripts/procedural_texture.gd",
		"res://scripts/weapon_finish.gd",
		"res://scripts/fx_manager.gd",
		"res://scripts/screen_fx.gd",
		"res://scripts/armory.gd",
		"res://scripts/movement_local.gd",
		"res://scripts/vanta_global.gd",
	]
	for path in scripts:
		var script = load(path)
		var ok := script != null
		var detail := "可載入" if ok else "載入失敗"
		if ok and script is GDScript:
			var err := script.reload()
			ok = err == OK
			detail = "語法正確 (err=%d)" % err
		_add_suite_result(results, path.get_file(), ok, detail)
	return results


func _run_scene_structure_check() -> Array:
	var results := []
	var scenes := [
		{"path": "res://main.tscn", "expected_nodes": ["RenderWorld", "Camera3D", "HUDLayer"]},
		{"path": "res://buy_menu.tscn", "expected_nodes": []},
		{"path": "res://menu.tscn", "expected_nodes": []},
	]
	for sc in scenes:
		var packed = load(sc["path"])
		if packed == null:
			_add_suite_result(results, sc["path"], false, "場景載入失敗")
			continue
		var inst = packed.instantiate()
		var ok := true
		var missing := []
		for node_name in sc["expected_nodes"]:
			if inst.get_node_or_null(node_name) == null:
				ok = false
				missing.append(node_name)
		inst.queue_free()
		var detail := "通過" if ok else "缺少: %s" % str(missing)
		_add_suite_result(results, sc["path"], ok, detail)
	return results


func _run_recoil_bundle_check() -> Array:
	var results := []
	var bundle: Dictionary = RecoilModel.bundle()
	var weapons: Dictionary = bundle.get("weapons", {})
	_add_suite_result(results, "recoil.json 存在", not bundle.is_empty(),
			"%d 把槍" % weapons.size() if not bundle.is_empty()
			else "缺件：請跑 python3 -m tools.cli recoil && python3 -m tools.godot.export")
	_add_suite_result(results, "bundle 版本", int(bundle.get("version", 0)) == 1,
			"version=%s" % str(bundle.get("version", "?")))
	var m := RecoilModel.new()
	var ok := m.setup("vandal")
	_add_suite_result(results, "vandal 圖案載入", ok and m.pitch_pattern.size() > 0,
			"%d 發，首發 %.2f°" % [m.pitch_pattern.size(), m.pitch_pattern[0]] if ok else "setup 失敗")
	m.fire(0.0)
	var first := m.pitch
	m.hard_reset()
	m.fire(0.0)
	m.fire(0.03)
	_add_suite_result(results, "图案單調上升", m.pitch > first,
			"%.2f° > %.2f°" % [m.pitch, first])
	# 恢復：停火超過 reset_time 後必須回吐到 0（這是「放開扳機」的手感來源）
	var t := 0.03 + m.reset_time + 0.02
	for i in range(600):
		t += 0.01
		m.update(t, 0.01)
	_add_suite_result(results, "停火後完全恢復", m.recovered(),
			"pitch=%.3f yaw=%.3f" % [m.pitch, m.yaw])
	# 移動準度排序：蹲（0.35）比跑動好、空中（1.25）最差
	var run_d := m.movement_error_deg(1.0, false, false, false, 9.9)
	var crouch_d := m.movement_error_deg(1.0, false, true, false, 9.9)
	var air_d := m.movement_error_deg(0.0, false, false, true, 9.9)
	_add_suite_result(results, "移動準度排序", crouch_d < run_d and air_d > run_d,
			"蹲 %.2f < 跑 %.2f < 空中 %.2f" % [crouch_d, run_d, air_d])
	# 準星=真擴散圓：連射後必須比首發大
	var d0 := m.spread_deg(0.0, false, false, false, 9.9, false)
	for i in range(4):
		m.fire(10.0 + float(i) * 0.1)
	var d1 := m.spread_deg(0.0, false, false, false, 9.9, false)
	_add_suite_result(results, "連射準星擴張", d1 > d0, "%.4f° → %.4f°" % [d0, d1])
	return results


func _add_suite_result(results: Array, name: String, passed: bool, detail: String) -> void:
	var icon := "PASS" if passed else "FAIL"
	_results_summary += "[%s] %s — %s\n" % [icon, name, detail]
	results.append({"name": name, "passed": passed, "detail": detail})
	print("[%s] %s — %s" % [icon, name, detail])


func _print_final_summary(suite1: Array, suite2: Array, suite3: Array) -> void:
	var all_results := suite1 + suite2 + suite3
	var total := all_results.size()
	var passed := 0
	for r in all_results:
		if r["passed"]:
			passed += 1
	var failed := total - passed

	print("")
	print("╔══════════════════════════════════════════════╗")
	print("║       VANTA 完整測試報告                 ║")
	print("╠══════════════════════════════════════════════╣")
	print("║  Suite 1 (視覺化): %d/%d PASS               ║" % [
		suite1.filter(func(r): return r["passed"]).size(), suite1.size()])
	print("║  Suite 2 (語法):   %d/%d PASS               ║" % [
		suite2.filter(func(r): return r["passed"]).size(), suite2.size()])
	print("║  Suite 3 (場景):   %d/%d PASS               ║" % [
		suite3.filter(func(r): return r["passed"]).size(), suite3.size()])
	print("║──────────────────────────────────────────────║")
	print("║  總計: %d | PASS: %d | FAIL: %d              ║" % [total, passed, failed])
	if failed == 0:
		print("║  ALL TESTS PASSED                       ║")
	else:
		print("║  %d TEST(S) FAILED                      ║" % failed)
	print("╚══════════════════════════════════════════════╝")
	print("")

	if failed > 0:
		print("--- 失敗項 ---")
		for r in all_results:
			if not r["passed"]:
				print("  FAIL: %s — %s" % [r["name"], r["detail"]])
		print("")
