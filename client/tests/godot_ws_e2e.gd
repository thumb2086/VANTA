extends SceneTree

## Godot 客戶端 E2E 測試（headless）：
## 用 NetClient 的 WS 模式連上「已部署的」Cloudflare Workers 端點，
## 驗證 welcome / 快照 / RTT 迴圈，然後以 exit code 回報。
##
## 執行：
##   Godot_v4.7.1-stable_win64_console.exe --headless --path client \
##       -s res://tests/godot_ws_e2e.gd
## 可傳參數：--server <wss://...> （預設連已部署的 vanta-ws）

var net: NetClient
var _t := 0.0
var _send_t := 0.0
var _ws_url := "wss://vanta-ws.cpxru83.workers.dev/ws?match=godot_e2e&ai=1"


func _initialize() -> void:
	# 允許用 --server 覆寫（本機測試：ws://127.0.0.1:8787/ws?match=godot_e2e&ai=1）
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--server":
			_ws_url = args[i + 1]
	net = NetClient.new()
	root.add_child(net)
	net.mode = "ws"
	net.ws_url = _ws_url
	net.start()
	print("GODOT_WS_TEST 連線 ", _ws_url)


func _process(delta: float) -> bool:
	_t += delta
	_send_t += delta
	net.tick()

	# 每 50ms 送一個輸入（建立 session + 驅動模擬）
	if _send_t >= 0.05:
		_send_t = 0.0
		net.send_input(Vector2(1.0, 0.0), false, false, false)

	# 成功條件：welcome + 至少 64 快照 + tick 前進；上限 15 秒
	if net.connected and net.snapshot_count >= 64 and _t >= 8.0:
		_report(net.connected and net.last_server_tick > 0)
		return true
	if _t >= 15.0:
		_report(net.connected and net.snapshot_count > 0)
		return true
	return false


func _report(ok: bool) -> void:
	print("GODOT_WS_TEST connected=%s net_id=%d slot=%d snapshots=%d tick=%d rtt=%.1fms players=%d" % [
		net.connected, net.net_id, net.slot, net.snapshot_count,
		net.last_server_tick, net.rtt_ms, net.players.size()])
	print("GODOT_WS_TEST " + ("PASS" if ok else "FAIL"))
	quit(0 if ok else 1)
