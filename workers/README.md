# VANTA — Cloudflare Workers 部署版後端

把 VANTA 的權威遊戲伺服器部署到 Cloudflare Workers 的完整移植。
**已部署**：https://vanta-ws.cpxru83.workers.dev （帳號：Cpxru83@gmail.com）

## 架構

```
Godot / 瀏覽器客戶端 (WebSocket, binary frames)
    │  /ws?match=<名稱>&ai=1&seed=42
    ▼
Default (WorkerEntrypoint)  ── getByName(match) ──►  MatchDO（每場比賽一個 DO 實例）
                                                      │
                                                      ▼
                                        MatchHost（確定性模擬核心，match_host.py）
                                        ├─ GameServer（server/netcode/server_loop.py）原樣重用
                                        │   反作弊 / Rollback / 去重 / 快照廣播 零改動
                                        ├─ 事件驅動 tick：每封包 + alarm 喚醒補跑固定步 1/128s
                                        └─ ai_mode：空槽由內建 AI 補位（觀戰/示範）
```

**為什麼能原樣跑**：`server/` 是零依賴純 stdlib Python，符合 Python Workers (Pyodide)
的要求；`protocol.py` 的二進位封包格式跨傳輸相容，只是把 UDP 換成 WebSocket binary frames。

## 本機開發

```bash
bash scripts/build.sh          # 複製 ../server → src/server（打包必要）
wrangler dev --port 8787
# 驗證：
../.venv/Scripts/python tests/ws_probe.py ws://127.0.0.1:8787/ws?match=demo&ai=1
# 瀏覽器：http://127.0.0.1:8787/ （內建測試台頁面）
```

## 測試

```bash
# MatchHost 核心（不碰 Workers API，可本機 pytest）
../.venv/Scripts/python -m pytest tests/test_match_host.py -q
```

覆蓋：welcome/快照流程、確定性（位元組一致）、AI 對戰擊殺、斷線槽位重用、
反作弊洪水踢除、射擊行動彈匣減少、封包格式與 UDP 版一致。

## 部署

```bash
bash scripts/build.sh
CLOUDFLARE_ACCOUNT_ID=<帳號ID> wrangler deploy
# 驗證
../.venv/Scripts/python tests/ws_probe.py wss://<name>.<subdomain>.workers.dev/ws?match=verify&ai=1
```

**Windows 部署注意**：
- wrangler 4.x 在 Node 24 會崩潰（STATUS_STACK_BUFFER_OVERRUN）→ 用 **Node 22 LTS**（
  下載 portable zip 後把其 bin 放 PATH 最前面再跑 `npx wrangler deploy`）。
- workers-py/pywrangler 需要 uv ≥0.12.3，但 uv 0.12.x 對 pyodide 直譯器的
  base_prefix 解析在 Windows 會壞（`//lib/python3.13/site-packages` 錯誤）→
  本機部署直接使用官方 wrangler 即可。
- 部署後用**新的 match 名稱**驗證（舊 DO 實例會保留舊程式碼直到被回收）。

## Godot 客戶端連線

在 `project.godot` / ProjectSettings 覆寫：

```text
vanta/net_mode = "ws"
vanta/ws_url   = "wss://vanta-ws.cpxru83.workers.dev/ws?match=demo&ai=1"
```

## 已知限制 / 注意事項

- **MatchDO 狀態在記憶體**：DO 重啟（閒置回收/部署）會讓比賽重置（同 seed 重新開始）。
  正式長比賽可把 seed 存進 `ctx.storage` 於重啟時重建。
- **快照只含已連線真人**（與本機 UDP 版行為一致）；觀戰要看到 AI 機器人需額外
  廣播全部槽位（增強選項）。
- **閒置推進約 ~115 ticks/s**（1s alarm 驅動）；活躍玩家以輸入驅動可達 128Hz 即時。
- Python Workers 為 open beta；`disable_python_external_sdk` flag 用於本機 runtime。
- 每場比賽一個 DO 實例（`getByName(match)`），同時段最多 10 玩家/場。
