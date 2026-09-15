class_name PracticeUI
extends Control

## Practice Range UI — bot settings, DPS stats, spray pattern

var practice: Node = null  # PracticeRange (set from server or simulated locally)
var _show := false
var stats: Dictionary = {}

func toggle() -> void:
    _show = not _show
    visible = _show
    if _show: queue_redraw()

func _draw() -> void:
    if not _show: return
    var vp := get_viewport_rect().size
    var font := get_theme_default_font()
    if font == null: return
    # Panel background
    draw_rect(Rect2(vp.x - 280, 40, 260, 320), Color(0.03, 0.04, 0.08, 0.92))
    draw_rect(Rect2(vp.x - 280, 40, 260, 320), Color(0.2, 0.25, 0.35, 0.6), false, 1.0)
    var x := vp.x - 268.0; var y := 62.0
    draw_string(font, Vector2(x, y), "練習靶場", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(1,0.85,0.2)); y += 26
    var keys := ["命中數", "爆頭", "命中率", "DPS", "擊殺", "TTK", "最佳TTK", "存活Bot"]
    var vals := [stats.get("hits",0), stats.get("headshots",0),
        str(stats.get("accuracy",0))+"%", stats.get("dps",0),
        stats.get("kills",0), str(stats.get("ttk",0))+"s",
        str(stats.get("best_ttk",0))+"s", stats.get("bots_alive",0)]
    for i in range(keys.size()):
        draw_string(font, Vector2(x, y), keys[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.7,0.75,0.85))
        draw_string(font, Vector2(x + 140, y), str(vals[i]), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1,1,1))
        y += 18
    # Crosshair visualization (spray pattern placeholder)
    y += 10
    draw_string(font, Vector2(x, y), "後座力圖", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.6,0.65,0.75)); y += 16
    var cx := x + 70.0; var cy := y + 60.0
    draw_circle(Vector2(cx, cy), 70.0, Color(0.1, 0.12, 0.18, 0.5))
    draw_line(Vector2(cx - 70, cy), Vector2(cx + 70, cy), Color(0.3,0.3,0.35), 1.0)
    draw_line(Vector2(cx, cy - 70), Vector2(cx, cy + 70), Color(0.3,0.3,0.35), 1.0)
