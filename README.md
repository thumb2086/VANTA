# VANTA — 開源 5v5 戰術英雄射擊 (Valorant-Like)

> 「伺服器權威 (Server-Side Authority)」防作弊架構的開源重現專案。
> 以《特戰英豪》機制為藍圖：128Hz 高 Tickrate 伺服器、客戶端預測與延遲補償、
> 固定後座力圖案、混合彈道 (Hitscan + 拋物線)、回合經濟、Spike 目標、技能框架。

## 專案狀態 — 全模組完成 ✅

| 階段 | 模組 | 狀態 |
|---|---|---|
| 一：核心與網路 | M1 移動控制器 / M2 伺服器與傳輸 / M3 預測·和解·Rollback | ✅ |
| 二：射擊體驗 | M4 武器庫 / M5 後座力與擴散 / M6 彈道·Hitbox·穿透 | ✅ |
| 三：經濟與回合 | M7 回合狀態機 / M8 經濟 / M9 Spike | ✅ |
| 四：技能框架 | M10 投擲物 / M11 煙霧 / M12 部署物 / M13 Debuff | ✅ |
| 五：內容整合 | M14 地圖（含**移動碰撞**）/ M15 Agent / M16 Meta | ✅ |
| 附加 | **全自動 AI 對戰示範**（`scripts/demo_match.py`） | ✅ |
| 附加 | **可程式化素材工具鏈**（`tools/`：音效/**BGM**/武器模組/地圖編輯/VFX/擊殺特效/**人物**/CLI） | ✅ |
| 附加 | **Godot 4 客戶端渲染層**（`client/`：UDP 連線、預測、HUD、音效/BGM/VFX 播放） | ✅ |
| 附加 | **槍支手感資料鏈**（19/19 每槍專屬後座图案、準星＝伺服器真實擴散圓、自動／連點射速、換彈重置图案） | ✅ |
| 附加 | **程序化動畫系統**（`client/`：武器視角模型換槍/換彈/開火/切刀/**檢視(Y)**/bob/ADS、第三人稱動作、動畫展示場） | ✅ |
| 附加 | **伺服器權威反作弊**（`server/netcode/anticheat.py`：輸入/行動/射速洪水、傳送/加速/出界偵測＋修正＋踢除） | ✅ |
| 附加 | **Rust 遷移藍圖＋跨語言 parity 實證（M1-M6, 純 Rust 伺服器完整對戰閉環）**（`rust/parity/`：移動/後座力(RNG)/彈道(Hitbox/穿透)/封包 SerDe 全數位元組級一致，~560x 加速） | ✅ |

**307 個單元/整合測試全綠**（含純 Rust 伺服器 selftest：移動/射擊/經濟/Spike/購買/拆除/回合；workers 部署測試納入同一 pytest 執行）。端到端：10 客戶端打完整場回合；
AI 示範：5v5 整場比賽 + Spike 安放/拆除/爆炸展示；
工具鏈：一鍵產生 70+ 素材，生成的地圖與武器可直接進遊戲；
Godot 客戶端：透過 UDP 連線權威伺服器實時渲染（地圖/玩家/HUD/音效/特效）。

## 快速開始

```bash
python -m pytest -q                    # 全部測試（282 個）
python3 scripts/demo_match.py          # 全自動 AI 對戰示範（含 Spike 展示）
python3 scripts/demo_pipeline.py       # 素材工具鏈閉環示範
python -m tools.cli all                # 一鍵產生全部素材（音效/BGM/武器/地圖/VFX/擊殺特效/人物）
python -m tools.cli bgm                # 只產生程序化 BGM（5 首，含循環點）
python -m tools.cli agents             # 只產生程序化人物（8 名 + 肖像 SVG）

# Godot 客戶端（渲染層）— 兩終端
python -m tools.godot.serve --ai       # 終端 1：本機權威伺服器（AI 對戰）
godot -e --path client                 # 終端 2：Godot 開啟 client/ 按 F5
                                       #   1/2/3 切槍、Q 循環、R 換彈、Y 檢視武器、F 撿武器(預留)

# 動畫展示場（換槍/換彈/開火/切刀 逐項預覽）
godot -e --path client scenes/../showcase.tscn   # 編輯器開 showcase.tscn 按 F5

# Rust 遷移 parity（伺服器熱路徑）
bash scripts/run_parity.sh           # Python 黃金資料 ↔ Rust 核心位元組級比對 + 基準
python3 scripts/profile_server.py 20 # 伺服器熱路徑剖析
```

## Godot 版本相容性（實測）

| 版本 | 狀態 |
|---|---|
| **Godot 4.4.x** | ✅ 開發基準，匯入/編譯/執行零錯誤 |
| **Godot 4.7.x**（2026-06-18 stable） | ✅ **相容**：4.7 開啟 4.4 專案零錯誤、`project.godot` 不會被強制改寫（features 仍標 4.4）、main + showcase 兩場景執行零錯誤 |
| 4.5 / 4.6 | 依 4.x 向後相容慣例應可開啟（未逐一實測） |

> 4.7 首次開啟時若提示「upgrade project」，選「否/稍後」即可繼續用 4.4 標記；
> 隨時可升級（升級後仍可用 4.4 開啟）。4.7 會更嚴格地抓作用域錯誤
> ——本專案已用 4.7 複驗並修掉 1 個錯位程式碼。

Python 3.11+，零第三方依賴（測試用 pytest）。

## 武器造型 / 特效（槍皮系統）

140 支造型、14 個系列、Chroma 變色、Radianite 升級、兵工廠預覽與試射——全部
**由工具鏈產生、由測試守護**，仓库裡沒有一張人工貼圖：

```bash
python3 -m tools.cli skins            # 槍皮目錄 + 系列卡 → tools/assets/
python3 -m tools.cli vfx2             # 分層特效藍圖 / 精靈 / 貼花
python3 -m tools.godot.export         # 匯入 client/assets/（全部素材（目前 132 個））
python3 -m pytest -q tests/test_tools_skins.py   # 78 項（含跨語言契約）
```

主選單 `🛡` 進兵工廠（`Esc` 返回）。完整設計與取捨見 `docs/09_visual_polish.md`。

## 槍支手感：後座／準度（資料驅動）

開槍的三件事——準星、槍身、彈道——現在讀的是**同一份**由工具鏈匯出的數字：

```bash
python3 -m tools.cli recoil           # 伺服器後座表 + 移動準度 → recoil.json（先驗資料表）
python3 -m tools.godot.export          # → client/assets/recoil/recoil.json
python3 -m pytest -q tests/test_recoil_data.py    # 25 項契約（含 Python⇄Rust⇄GDScript）
```

- 19 把槍各有專屬 spray pattern（Vandal ≠ Phantom ≠ Guardian），前幾發直上、尾段有機
- 準星半徑 = `SpreadEngine.spread_deg()` 的真值；蹲/靜步/空中/剛落地都會反映在準星與四角指示
- 停火 → 後座依 `recover_rate` 回吐到 0；換彈 → 图案回到第 1 發（「首發最準」）
- 全自動按住連射、連發槍自動打完整組（射速取自 bundle，伺服器同速限流）
- 設定面板（`Esc`）可開「後座图案預覽」與「準星反映真實準度」

細節、取捨與守門測試清單見 `docs/10_gunplay_feel.md`。

## Cloudflare Workers 部署（後端線上版）

遊戲後端已移植到 Cloudflare Workers（`workers/`）：WebSocket + Durable Object，
確定性模擬核心（`server/`）原樣運行，反作弊 / Rollback / 快照廣播零改動。

```bash
# 本機開發
cd workers && bash scripts/build.sh && wrangler dev --port 8787

# 部署
cd workers && bash scripts/build.sh && wrangler deploy

# 連線測試（本機或已部署 wss://）
../.venv/Scripts/python workers/tests/ws_probe.py ws://127.0.0.1:8787/ws?match=demo&ai=1
```

**已部署位址**：https://vanta-ws.cpxru83.workers.dev （`/ws?match=<名稱>&ai=1`）

Godot 客戶端切換：ProjectSettings 設 `vanta/net_mode = "ws"`、
`vanta/ws_url = "wss://vanta-ws.cpxru83.workers.dev/ws?match=demo&ai=1"`（預設仍為本機 UDP）。
詳見 `workers/README.md` 與 `client/README.md`。

## 目錄結構

```
server/
  core/          # 引擎無關純邏輯（Vec3、移動、移動準度懲罰）
  netcode/       # 128Hz 迴圈、二進位協定、傳輸、伺服器/客戶端迴圈
  game/          # 武器、後座力、彈道、經濟、回合、Spike、技能、地圖、實體
tools/           # 可程式化素材工具鏈（音效/武器模組/地圖/VFX/擊殺特效/槍皮目錄/CLI）
  skins/         #   槍皮：14 種可平鋪圖案 → 14 系列 140 造型 → 即時程序貼圖規格
  vfx/           #   特效：58 張分層藍圖 + 94 粒子預設 + 精靈/貼花
  assets/        # 工具鏈產出的素材（WAV/SVG/JSON + manifest）
client/          # Godot 4 客戶端（渲染層）：UDP 連線、預測、HUD、音效/VFX
tests/           # 每模組對應測試 + 端到端整合測試
docs/            # 研究筆記、技術選型、任務清單、工具鏈、Godot 客戶端、視覺品質（09）
```

## 核心架構（防作弊 = 伺服器權威）

1. 客戶端只上送「淨輸入 + 序號 + 時間戳」與「行動（射擊/購買/技能/Spike）」。
2. 所有位置、傷害、命中、經濟、Spike、技能冷卻都由伺服器計算，客戶端狀態永不採信。
3. 命中判定走 **Rollback 延遲補償**：射擊封包附帶「所見快照的 input_seq」，
   伺服器以 seq→tick 對應回滾目標位置後判定（50/100/200ms 延遲測試驗證）。
4. 確定性模擬：固定 tick 順序、float64、種子化 RNG → 錄製→重放位元級一致。

## 已知限制（誠實聲明）

- 機制數值為社群量測近似（Riot 未公開），全部集中在資料表，可後續校正。
- 純 Python 原型約 31x 即時（10 玩家含完整對戰與 AI）；正式版熱路徑移植 Rust。
- 渲染層為 Godot 4.4（GL Compatibility）程序化實作：無外部模型/貼圖資產，槍皮與特效
  全部由工具鏈規格在執行期生成（見 `docs/09_visual_polish.md`）。
- 移動碰撞目前為「位置修正」（圓柱 vs AABB 推離 + 玩家間推離）；
  階梯攀爬 / 斜坡 / 複雜 BSP 碰撞為後續工作。
