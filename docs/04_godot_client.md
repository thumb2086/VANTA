# Godot 客戶端（渲染層）— 架構與驗證

> 工具鏈 → 素材 → Godot 客戶端 → UDP → Python 權威伺服器，完整閉環。

## 快速開始

```bash
# 1) 產生素材並匯出到 client/assets/
python -m tools.cli all
python -m tools.godot.export

# 2) 啟動本機權威伺服器（另一終端）
python -m tools.godot.serve --ai      # AI 對戰（客戶端可直接加入觀戰/遊玩）

# 3) 用 Godot 4.4 開啟 client/project.godot 按 F5
```

## 客戶端架構（client/scripts/）

| 腳本 | 職責 |
|---|---|
| `net_client.gd` | UDP 協定客戶端，與 `server/netcode/protocol.py` **位元級相容**（有測試鎖定） |
| `movement_local.gd` | 客戶端預測 — 與伺服器移動模型完全相同的移植 |
| `render_world.gd` | 工具鏈地圖 JSON → StaticBody3D 世界；玩家膠囊渲染 + 插值 |
| `audio_manager.gd` | 播放工具鏈音效 WAV + 事件→音效綁定 + **BGM 前奏→循環**播放 |
| `vfx_manager.gd` | 工具鏈粒子 JSON → CPUParticles3D（資料驅動特效） |
| `hud.gd` | 準星 / 擊殺訊息 / 連殺宣告 / Spike 狀態 / 記分板 |
| `main.gd` | 主迴圈：輸入 → 預測 → 快照 → 伺服器和解 → 事件消費 |

## 網路流程

```
[輸入] WASD/滑鼠 → 淨輸入封包(15B) ──UDP──▶ [權威伺服器]
[伺服器] 128Hz 模擬 → 快照(250B) + 遊戲事件(16B) ──UDP──▶ [客戶端]
[客戶端] 預測移動 + 快照插值 + 伺服器和解（差異>0.25m 才校正）
[事件]   擊殺/Spike/回合 → 音效 + 粒子 + HUD 擊殺訊息/連殺宣告
```

## 音訊

- 音效：32 種工具鏈 WAV，事件綁定播放
- **BGM**：工具鏈產生的 5 首（combat/tension/menu/victory/defeat），
  `AudioManager.set_bgm()` 從 sidecar JSON 讀 `loop_start_sec`，
  `finished` → `play(loop_from)` 形成無縫循環
- 動態切換：預設 combat → Spike 安放切 tension → 回合勝/敗切 victory/defeat

## 協定擴充（本輪新增）

- **快照條目 24B**：新增 `health`(u8) / `mag`(u8) → HUD 顯示生命/彈匣
- **GAME_EVENT 封包（16B）**：伺服器廣播 擊殺(兇手,受害者) / Spike 安放/拆除/爆炸 /
  回合勝利/敗北 / 比賽結束 → 客戶端表現層驅動音效與特效

## 驗證（全部自動化）

```bash
python -m pytest -q                                   # 174 個測試
python -m pytest tests/test_godot_protocol_parity.py  # GDScript↔Python 協定常數一致
python -m pytest tests/test_netcode_udp.py            # 真實 UDP 全流程
python -m pytest tests/test_godot_export.py           # 素材匯出器

# Godot 無頭驗證（需 Godot 4.4 二進位）
godot --headless --path client --import        # 匯入 + 腳本編譯
godot --headless --path client --quit-after 60 # 執行期驗證（零錯誤）
```

## 本輪修復的真實 bug

1. **serve.py 繞過 server.step()**：`on_step` 直接呼叫 `world.step()`，
   導致收包/快照/事件廣播完全失效 → 改為 `server.step(dt, ai_inputs=...)`，
   `GameServer.step` 新增 AI 輸入注入（真人 Session 優先）。
2. **EV_KILL 從未廣播**：擊殺 log 解析忘了剝 `slot` 前綴 → `int("slot5")` 失敗。
3. **Godot 4.4 API 差異**：`PackedByteArray` 編解碼無 little_endian 參數、
   `CPUParticles3D.initial_velocity_min` 等是 float 非 Vector3、`Vector3.length_squared()`。

## 已知限制（誠實聲明）

- 客戶端為「渲染示範」等級：無完整材質/動畫/音效空間化；命中回饋為客戶端視覺。
- 射擊由伺服器權威判定；客戶端只送瞄準角（Rollback seq = 所見快照 last_seq）。
- 正式部署：材質/燈光/後處理、角色模型動畫、音效 3D 定位為後續工作。
