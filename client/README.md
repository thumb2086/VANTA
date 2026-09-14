# VANTA Godot 客戶端（渲染層）

連線到 Python 權威伺服器，渲染工具鏈產生的地圖/武器/音效/特效。

## 執行步驟

```bash
# 1) 產生素材並匯出到 client/assets/
python -m tools.cli all
python -m tools.godot.export

# 2) 啟動本機權威伺服器（另一終端）
python -m tools.godot.serve --ai      # AI 對戰，客戶端可直接觀戰/加入

# 3) 用 Godot 4.4 開啟本資料夾（client/project.godot）按 F5
```

## 操作

| 按鍵 | 動作 |
|---|---|
| W/A/S/D | 移動 |
| Shift | 靜步 |
| Ctrl | 下蹲 |
| Space | 跳躍 |
| 滑鼠 | 視角 / 左鍵開火 |
| Esc | 釋放滑鼠 |

## 架構

- `scripts/net_client.gd` — UDP 協定客戶端（與 `server/netcode/protocol.py` 位元級相容）
- `scripts/movement_local.gd` — 客戶端預測（與伺服器移動模型一致）
- `scripts/render_world.gd` — 地圖 JSON → 3D 世界、玩家膠囊渲染與插值
- `scripts/audio_manager.gd` — 播放工具鏈音效 + 事件綁定
- `scripts/vfx_manager.gd` — 粒子 JSON → CPUParticles3D
- `scripts/hud.gd` — 準星 / 擊殺訊息 / 連殺宣告 / Spike 狀態
- `scripts/main.gd` — 主迴圈：輸入→預測→快照→和解→事件

## Cloudflare Workers 部署版（WebSocket 模式）

後端已可部署到 Cloudflare Workers（`workers/`，WebSocket + Durable Object，
確定性模擬核心原樣運行）。客戶端切換傳輸只需在 `project.godot` 或
ProjectSettings 覆寫兩個設定：

```text
vanta/net_mode = "ws"
vanta/ws_url   = "wss://vanta-ws.<你的subdomain>.workers.dev/ws?match=demo&ai=1"
```

本機開發（`wrangler dev` 起在 8787）：

```text
vanta/net_mode = "ws"
vanta/ws_url   = "ws://127.0.0.1:8787/ws?match=demo&ai=1"
```

預設仍為本機 UDP（`vanta/net_mode = "udp"`），行為不變。

## 驗證

```bash
python -m pytest -q tests/test_godot_export.py tests/test_netcode_udp.py
```

### Godot 客戶端 WS E2E（headless，連已部署的 Workers 端點）

```bash
Godot_v4.7.1-stable_win64_console.exe --headless --path client \
    -s res://tests/godot_ws_e2e.gd
# 本機（先 wrangler dev）：加 --server ws://127.0.0.1:8787/ws?match=godot_e2e&ai=1
```

成功會印 `GODOT_WS_TEST PASS`（welcome + 快照 + RTT），exit code 0。
