class_name MissionUI
extends Control
## 每日任務面板 — 對接 server/game/missions.py（to_dict/from_dict）
## 顯示當日 3 任務進度與 XP，等同 Valorant 每日任務條

var tracker: Dictionary = {} # {date, xp, progress:{key:{p,c}}, defs:[{key,desc,target,xp}]}
var save_path := "user://missions.json"

func _ready() -> void:
	_load()

func _load() -> void:
	if FileAccess.file_exists(save_path):
		var t := FileAccess.get_file_as_string(save_path)
		var d = JSON.parse_string(t)
		if d is Dictionary and "date" in d:
			tracker = d

func save() -> void:
	var f := FileAccess.open(save_path, FileAccess.WRITE)
	if f: f.store_string(JSON.stringify(tracker))

func set_missions(summary: Array, xp: int, level: int) -> void:
	# summary: [{key,desc,progress,target,xp,claimed},...]
	tracker["summary"] = summary
	tracker["xp"] = xp
	tracker["level"] = level
	queue_redraw()

func _draw() -> void:
	var vp := get_viewport_rect().size
	var font := get_theme_default_font()
	if font == null: return
	var y := 20.0; var x := 20.0
	var title := "每日任務  Lv.%d (%d XP)" % [tracker.get("level",1), tracker.get("xp",0)]
	draw_string(font, Vector2(x, y), title, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color(1,1,1))
	y += 28
	for row in tracker.get("summary", []):
		var pct := float(row.get("progress",0)) / max(1.0, float(row.get("target",1)))
		var w := 260.0 * pct
		draw_rect(Rect2(x, y, 260, 14), Color(0.2,0.2,0.25))
		draw_rect(Rect2(x, y, w, 14), Color(0.2,0.8,0.5) if pct >=1.0 else Color(0.9,0.8,0.2))
		var label := "%s %d/%d" % [row.get("desc",""), row.get("progress",0), row.get("target",1)]
		draw_string(font, Vector2(x+4, y+11), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(1,1,1))
		if pct >= 1.0:
			draw_string(font, Vector2(x+268, y+11), "+%d XP" % row.get("xp",0), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.4,1,0.6))
		y += 22
