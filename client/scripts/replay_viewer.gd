class_name ReplayViewer
extends Control
## 回放檢視器 — 對接 server/game/replay.py 存檔（meta/ticks/events）
## 支援 state_at / events_between / jump_to_event + 逐 tick 播放
## 存檔路徑：replays/<match_id>/ (meta.json, ticks.jsonl, events.jsonl)

var ticks: Array = []
var events: Array = []
var meta: Dictionary = {}
var cur_tick: int = 0
var playing: bool = false
var play_speed: float = 1.0 # 1.0 = 實速（128 tick/s -> 視覺 30 fps 抽稀）

func load_replay(dir: String) -> bool:
	var f := FileAccess.open(dir.path_join("meta.json"), FileAccess.READ)
	if f == null: return false
	var m = JSON.parse_string(f.get_as_string())
	if not (m is Dictionary): return false
	meta = m
	ticks.clear(); events.clear()
	var tf := FileAccess.open(dir.path_join("ticks.jsonl"), FileAccess.READ)
	if tf:
		while not tf.eof_reached():
			var line := tf.get_line().strip_edges()
			if line.is_empty(): continue
			var d = JSON.parse_string(line)
			if d is Dictionary: ticks.append(d)
	var ef := FileAccess.open(dir.path_join("events.jsonl"), FileAccess.READ)
	if ef:
		while not ef.eof_reached():
			var line := ef.get_line().strip_edges()
			if line.is_empty(): continue
			var d2 = JSON.parse_string(line)
			if d2 is Dictionary: events.append(d2)
	cur_tick = 0
	queue_redraw()
	return ticks.size() > 0

func state_at(tick: int) -> Dictionary:
	var best := {}
	for t in ticks:
		if int(t.get("tick", 0)) <= tick: best = t
		else: break
	return best

func events_between(a: int, b: int) -> Array:
	var out: Array = []
	for e in events:
		var tk := int(e.get("tick", 0))
		if a <= tk and tk <= b: out.append(e)
	return out

func jump_to_event(kind: String, idx: int = 0) -> Dictionary:
	var c := 0
	for e in events:
		if str(e.get("kind","")) == kind or str(e.get("log","")).begins_with(kind + ":"):
			if c == idx:
				cur_tick = int(e.get("tick", cur_tick))
				queue_redraw()
				return e
			c += 1
	return {}

func _process(delta: float) -> void:
	if not playing or ticks.is_empty(): return
	cur_tick += int(ceil(8 * play_speed)) # 抽稀：約 8 tick/frame
	if cur_tick > int(ticks[-1].get("tick", cur_tick)): cur_tick = int(ticks[-1].get("tick", 0))
	queue_redraw()

func _draw() -> void:
	var vp := get_viewport_rect().size
	var font := get_theme_default_font()
	if font == null: return
	var s := state_at(cur_tick)
	var title := "%s  tick %d/%d  %s" % [meta.get("match_id",""), cur_tick, meta.get("total_ticks", ticks.size()), "▶" if playing else "⏸"]
	draw_string(font, Vector2(16, 24), title, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(1,1,1))
	if not s.is_empty():
		var y := 48.0
		for p in s.get("players", []):
			var label := "P%02d T%d %s HP%d %s" % [int(p.get("slot",0)), int(p.get("team",0)), str(p.get("weapon","")), int(p.get("hp",0)), "●" if bool(p.get("alive",true)) else "✕"]
			draw_string(font, Vector2(16, y), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.85,0.9,0.95) if bool(p.get("alive",true)) else Color(0.5,0.5,0.55))
			y += 14
			if y > vp.y - 20: break
	var evs := events_between(cur_tick - 64, cur_tick + 64)
	var y2 := 24.0; var x2 := vp.x - 260
	for e in evs.slice(0, 8):
		var txt := "%d %s" % [int(e.get("tick",0)), str(e.get("kind", e.get("log",""))).left(28)]
		draw_string(font, Vector2(x2, y2), txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(1,0.85,0.3))
		y2 += 14

func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_SPACE: playing = not playing
			KEY_RIGHT: cur_tick = mini(cur_tick + 64, int(ticks[-1].get("tick", cur_tick)) if ticks.size() else cur_tick)
			KEY_LEFT: cur_tick = maxi(cur_tick - 64, 0)
			KEY_J: jump_to_event("kill")
