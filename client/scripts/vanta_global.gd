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

# 輔助功能設定（由 settings_menu.gd 寫入）
var colorblind_mode := 0       # 0=None, 1=Protanopia, 2=Deuteranopia, 3=Tritanopia
var font_size_index := 1       # 0=Small(12), 1=Medium(14), 2=Large(16)
var subtitles_on := true
var master_volume := 1.0
var sfx_volume := 0.8
var bgm_volume := 0.6
var graphics_quality := 1      # 0=Low, 1=Medium, 2=High
