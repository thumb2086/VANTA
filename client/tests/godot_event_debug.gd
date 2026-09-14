extends SceneTree

## 專門偵錯：Godot WS 客戶端是否收到遊戲事件（KILL / ROUND_WIN / ROUND_LOSS）
## 執行55秒（跨越至少 1 回合買槍+行動），記錄所有收到的事件。

var net: NetClient
var _t := 0.0
var _send_t := 0.0
var _ws_url := "wss://vanta-ws.cpxru83.workers.dev/ws?match=eventdebug&ai=1"
var _events_received: Array = []
var _snap_count := 0


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--server":
			_ws_url = args[i + 1]
	net = NetClient.new()
	root.add_child(net)
	net.mode = "ws"
	net.ws_url = _ws_url
	net.start()
	print("EVENT_DEBUG 連線 ", _ws_url)


func _process(delta: float) -> bool:
	_t += delta
	_send_t += delta
	net.tick()

	# 每50ms 送一個輸入
	if _send_t >= 0.05:
		_send_t = 0.0
		net.send_input(Vector2(0, 1), false, false, false)

	# 記錄所有事件
	for ev in net.events:
		var ev_type: int = int(ev["event"])
		var ev_tick: int = int(ev["tick"])
		_events_received.append({"type": ev_type, "tick": ev_tick})

	_snap_count = net.snapshot_count

	# 55 秒後報告
	if _t >= 55.0:
		_report()
		return true
	return false


func _report() -> void:
	var ev_names := {1: "KILL", 2: "PLANT", 3: "DEFUSE", 4: "DETONATE",
		5: "ROUND_WIN", 6: "ROUND_LOSS", 7: "MATCH_END"}
	print("EVENT_DEBUG snap_count=%d total_events=%d" % [_snap_count, _events_received.size()])
	for ev in _events_received:
		var name: String = ev_names.get(ev["type"], "?" + str(ev["type"]))
		print("  %s at tick %d" % [name, ev["tick"]])
	var has_round := false
	for ev in _events_received:
		if ev["type"] >= 5:
			has_round = true
	if has_round:
		print("EVENT_DEBUG PASS — 收到回合事件")
	else:
		print("EVENT_DEBUG FAIL — 未收到回合事件（%d 個事件全是 KILL）" % _events_received.size())
	quit(0 if has_round else 1)
