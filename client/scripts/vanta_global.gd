extends Node

## VANTA 全域狀態（AutoLoad）— 在場景之間傳遞連線參數
## project.godot 設定 [autoload] VantaGlobal="*res://scripts/vanta_global.gd"

var ws_url := "wss://vanta-ws.cpxru83.workers.dev/ws?match=demo&ai=1"
var net_mode := "ws"
var player_name := "thumb"
var selected_mode := ""

# 社交系統
var social_system: Node = null

func get_social() -> Node:
	if social_system == null:
		social_system = preload("res://scripts/social_system.gd").new()
		social_system.name = "SocialSystem"
		add_child(social_system)
	return social_system

# 武器工坊配色（由 workshop.gd 寫入，main.gd 讀取）
var weapon_palette := {
	"primary": Color(0.25, 0.27, 0.32),
	"accent": Color(0.85, 0.4, 0.25),
	"skin_name": "原始本色"
}

# 槍皮收藏（SkinProgression / SkinRegistry 由軍械庫與對局共用）
var skin_revision := 0
var skin_progression_node: Node = null


func get_skin_progression() -> Node:
	if skin_progression_node == null:
		skin_progression_node = preload("res://scripts/skin_progression.gd").new()
		skin_progression_node.name = "SkinProgression"
		add_child(skin_progression_node)
	return skin_progression_node


func get_skin_registry() -> RefCounted:
	return preload("res://scripts/skin_registry.gd").shared()


## 軍械庫換裝／升級後呼叫：對局中的 main.gd 會在下幀重建視角模型與特效色
func notify_skins_changed() -> void:
	skin_revision += 1
	if weapon_palette.has("primary"):
		var prog := get_skin_progression()
		if prog != null and prog.has_method("resolve_current"):
			var res: Dictionary = prog.call("resolve_current", "phantom", 0)
			if not res.is_empty():
				var cw: Dictionary = res.get("colorway", {})
				weapon_palette["primary"] = SkinRegistry.hex_color(
					cw.get("primary", "#2b2f38"), weapon_palette["primary"])
				weapon_palette["accent"] = SkinRegistry.hex_color(
					cw.get("accent", "#ff7a35"), weapon_palette["accent"])
				weapon_palette["skin_name"] = String(res.get("name", ""))


# 自訂地圖資料（由 map_generator.gd 寫入，main.gd 讀取）
var custom_map_data: Dictionary = {}

# 角色選擇（由 agent_select.gd 寫入，main.gd 讀取）
var selected_agent := 0
var selected_agent_name := "夜露 Yoru"

# 購買指令（由 buy_menu.gd 寫入，main.gd 讀取並發送 item_id）
var pending_buy_item_id := -1

# 設定（由 settings_menu.gd 寫入）
var sensitivity := 0.35
var ads_sensitivity := 1.0
var scoped_sens := 0.35
var crosshair_color := Color(0.22, 1.0, 0.08)
var crosshair_size := 4.0
var crosshair_gap := 4.0
var crosshair_thickness := 2.0
var crosshair_outline := false
var crosshair_dot := true
var crosshair_style := 0
var fov := 90
