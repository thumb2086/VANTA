extends Node3D

## CharacterGenerator 測試腳本
## 實例化兩隊角色並輸出骨架結構，確認比例正確
##
## 執行方式：在 Godot 編輯器中載入此場景並按 Play

const CharacterGenerator = preload("res://tools/generate_character.gd")


func _ready() -> void:
	var gen = CharacterGenerator.new()

	# ── 隊伍 0（紅方） ──
	var char_a := gen.generate(0)
	char_a.position = Vector3(-0.6, 0, 0)
	add_child(char_a)

	# ── 隊伍 1（藍方） ──
	var char_b := gen.generate(1)
	char_b.position = Vector3(0.6, 0, 0)
	add_child(char_b)

	# ── 輸出骨架結構 ──
	print("\n===== CharacterGenerator Test =====")
	print("--- Team 0 (Red) ---")
	gen.print_tree(char_a)
	print("\n--- Team 1 (Blue) ---")
	gen.print_tree(char_b)

	# ── 驗證高度 ──
	var top_y := _find_top_y(char_a)
	print("\n--- Validation ---")
	print("Team 0 top Y: %.3f m (expected ~1.80)" % top_y)
	assert(absf(top_y - 1.80) < 0.15, "Character height out of range")
	print("Height check PASSED")

	# ── 驗證節點數 ──
	var count_a := _count_meshes(char_a)
	var count_b := _count_meshes(char_b)
	print("Team 0 mesh count: %d" % count_a)
	print("Team 1 mesh count: %d" % count_b)
	assert(count_a == count_b, "Both teams should have same mesh count")
	print("Symmetry check PASSED")
	print("===== All tests passed =====\n")


func _find_top_y(root: Node3D) -> float:
	var top := root.position.y
	for child in root.get_children():
		if child is MeshInstance3D:
			var y := root.position.y + child.position.y
			if child.mesh is SphereMesh:
				y += child.mesh.radius
			elif child.mesh is CylinderMesh:
				y += child.mesh.height * 0.5
			elif child.mesh is BoxMesh:
				y += child.mesh.size.y * 0.5
			top = maxf(top, y)
	return top


func _count_meshes(root: Node3D) -> int:
	var count := 0
	for child in root.get_children():
		if child is MeshInstance3D:
			count += 1
	return count
