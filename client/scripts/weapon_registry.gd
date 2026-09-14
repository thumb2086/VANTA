class_name WeaponRegistry
extends RefCounted

## 讀取「工具鏈產生的武器 JSON」（assets/weapons/*.json）供 HUD/擊殺訊息顯示。

var weapons := {}


func setup(index: Dictionary) -> void:
	for path in index.get("weapons", []):
		var f := FileAccess.open(path, FileAccess.READ)
		if f == null:
			continue
		var data: Dictionary = JSON.parse_string(f.get_as_text())
		var stats: Dictionary = data.get("stats", {})
		weapons[stats.get("key", "")] = {
			"name": stats.get("name", "?"),
			"damage": stats.get("damage", 0),
			"price": stats.get("price", 0)
		}


func name_for(key: String) -> String:
	var w: Dictionary = weapons.get(key, {})
	return w.get("name", key)
