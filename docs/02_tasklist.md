# 任務清單 — 全階段拆解

> 依循藍圖四階段順序逐一實作，**每個任務 = 實作 + 單元測試 + 通過驗證**。

## 階段一：核心基礎與網路同步

- [x] **M1 角色移動控制器** ✅
  - 跑 / 靜步 (Shift) / 下蹲 / 跳躍（拋物線）、反切急停 ≈40ms、斜向不超速
  - 跳躍緩衝 / 土狼時間、移動準度懲罰（靜止 0 / 跑 100% / 靜步 50% / 蹲走 35% / 空中 125% / 落地 +7°×0.225s）
  - 驗收：確定性 + 運動學測試全綠

- [x] **M2 伺服器主迴圈與傳輸層** ✅
  - 128Hz 固定時間步、二進位協定（INPUT/SNAPSHOT/WELCOME/ACTION）、類 UDP 傳輸（可注入延遲/遺失/抖動）
  - RTT(EWMA)、輸入去重、斷線逾時、無損回放（錄製→重放位元級一致）

- [x] **M3 同步三兄弟** ✅
  - 客戶端預測（本地 MovementController 提前模擬）
  - 伺服器和解（快照校正 + 重放未確認輸入）
  - Rollback 延遲補償（seq→tick 對應 + 位置歷史，命中回滾到射手所見時刻）
  - 驗收：50/100/200ms 延遲下補償命中、無補償落空；預測一致時零校正、偏差時收斂

## 階段二：極致射擊體驗

- [x] **M4 武器資料庫與 Hitscan** ✅
  - 20 把武器數據（射速/傷害/衰減/穿透等級/首發精度/價格，近似值集中於資料表）
  - Hitscan 射線 vs 膠囊命中判定、首發靜止精準

- [x] **M5 後座力與擴散引擎** ✅
  - 固定後座力圖案（Vandal 6 / Phantom 8 保護彈，之後機率性 yaw）、恢復延遲、連射懲罰
  - 隨機擴散圓（靜止首發近零、逐發成長、移動/ADS/蹲姿修正、落地懲罰疊加）

- [x] **M6 彈道與傷害** ✅
  - Hitbox 分離：頭 4.0x / 身 1.0x / 腿 0.85x（三顆膠囊）
  - 牆壁穿透衰減（材質等級 × 距離，步槍可穿木/混凝土、手槍不可、不可穿牆擋死）
  - 拋物線實體彈道（重力 + 反彈 + 地面碰撞）、爆炸範圍傷害（衰減/LOS/flat 模式）

## 階段三：經濟與回合系統

- [x] **M7 回合狀態機** ✅
  - Buy Phase (45/30s) → Action Phase (100s) → End Phase (4s)，半場攻守互換、13 分獲勝
  - 勝負判定：全滅 / Spike 爆炸 / 拆除 / 時間到守方勝

- [x] **M8 經濟運算核心** ✅
  - 擊殺 200 / 勝利 3000 / 連敗補償 1900→2400→2900 / 安放 +300（攻方全員）/ 上限 9000
  - 商店購買驗證（武器/輕重甲）

- [x] **M9 Spike 目標邏輯** ✅
  - 安放 4s（移動/離開點位即中斷）、拆除 7s（3.5s 檢查點）、倒數 45s
  - 爆炸範圍致死判定（半徑 25m 全傷，攻方除外）

## 階段四：英雄技能框架

- [x] **M10 IAbility 抽象 + 投擲物物理** ✅
  - 抽象介面（charges/cooldown/cast/update）+ AbilitySystem
  - 閃光彈（落地即爆，範圍致盲）與碎片手榴彈（反彈 + 引信 + 爆炸）

- [x] **M11 煙霧 (Smokes)** ✅
  - 球形（可多球體不規則化）LOS 阻斷器 + 持續時間控制器（15s 自動消退）

- [x] **M12 地圖部署物件 (Deployables)** ✅
  - 表面放置觸發型陷阱：敵方進入半徑 → 傷害 + 暈眩，單次觸發

- [x] **M13 狀態干擾 (Debuffs)** ✅
  - 閃瞎（不可開火 + 視野封鎖）、暈眩（移動 -35%）、易傷（受傷 ×1.5）
  - 疊加規則（長者勝出）、畫布渲染狀態輸出

## 階段五：內容與整合

- [x] **M14 地圖系統** ✅（含移動碰撞）
  - AABB 牆面 + 材質穿透表、視線判定、Spike 點位、重生點
  - **移動碰撞**：玩家圓柱 vs 牆面推離 + 沿牆滑移 + 天花板壓制 + 玩家間推離
    （`server/game/collision.py`，`tests/test_game_collision.py` 7 個測試）
  - 除錯收穫：修復 classic 手槍 reserve=0 導致「全場彈盡糧絕」的真實 bug；
    驗證「不壓槍 → 後座力漂移脫靶」機制（壓槍測試鎖定，見 test_game_combat.py）

- [x] **M15 Agent 原型** ✅
  - 4 名角色（assault/sentinel/duelist/controller）以 IAbility 組合

- [x] **M16 Meta 層** ✅（基礎版）
  - 記分板、半場交換、13 分獲勝、回合紀錄

## 整合驗證

- [x] 端到端測試：10 客戶端 → 128Hz 伺服器 → 買期 → 技能施放 → Spike 安放/爆炸
  → 回合結算 → 經濟發放 → 下一回合購買（`tests/test_end_to_end.py`）
- [x] **全自動 AI 對戰示範**（`scripts/demo_match.py`）：5v5 AI 買槍→交戰→回合結算，
  含 Spike 機制展示（安放→爆炸 / 安放→過半續拆→拆除）；AI 具備壓槍（後座力補償）
- [x] **可程式化素材工具鏈**（`tools/`，詳見 `docs/03_tools.md`）：
  音效合成（32 WAV）/ 程序化 BGM（5 首）/ 槍械模組化（12 武器）/ 地圖編輯器（3 地圖）/
  **人物產生器（8 名角色 + 肖像 SVG，可直接進遊戲）** / VFX 粒子 + SVG /
  擊殺特效 + 26 事件綁定 → `python -m tools.cli all` 一鍵產生 110+ 素材
  → `scripts/demo_pipeline.py` / `scripts/demo_agents.py` 閉環驗證（生成素材進遊戲跑對戰）
- [x] **槍皮系統 + 分層特效升級**（2026-09，詳見 `docs/09_visual_polish.md`）：
  14 系列 / 140 造型（程序化 colorway + 14 種可無縫平鋪圖案 + Chroma 變色 + Radianite 升級）
  → 執行期生成 albedo/emissive/detail 貼圖（規格 `TEX` 只寫在 Python 一份，Godot 逐運算式移植；
  v2 修正「發光整片糊掉」→ 只沿結構脊線）；58 張分層特效藍圖（particles/mesh/light/decal/camera/
  hud/sound）+ 94 粒子預設 + 18 精靈 + 14 貼花；**Armory 兵工廠**（3D 預覽／試射／檢視動畫／
  購買／升級）；`ScreenFX` 創傷相機、FOV 踢動、擊殺暈影與皮膚化 hit marker
  → 驗證：`tests/test_tools_skins.py`（78 項，含 Godot 跨語言契約）＋ `tests/test_tools_vfx_fx.py`
  ＋ gdparse/gdlint 全綠；協定零改動（外觀不入網路封包）
- [x] **Godot 4 客戶端渲染層**（`client/`，詳見 `docs/04_godot_client.md`）：
  UDP 協定客戶端（與 Python 位元級相容，parity 測試鎖定）、客戶端預測、快照插值與
  伺服器和解、工具鏈地圖/音效/粒子載入、HUD（準星/擊殺訊息/連殺/Spike）、
  遊戲事件→音效+特效；`tools/godot/serve.py` 本機權威伺服器（可 --ai）
  → 驗證：Godot headless 匯入/運行零錯誤 + 真實 UDP 整合測試
- [x] **程序化動畫系統**（`client/`，詳見 `docs/05_animations.md`）：
  武器切換系統（主/副/刀三槽位，伺服器權威）+ 快照擴充（weapon_slot/reloading/
  **reload_progress 伺服器權威進度**）+ 第一人稱視角模型（開火/換彈/換槍/切刀/
  **檢視武器 Y**/bob/ADS 動畫）+ **換彈里程碑音效（彈匣落地/拉滑套）由伺服器進度驅動** +
  第三人稱角色骨架 + 動畫展示場（showcase.tscn）
- [x] **伺服器權威反作弊**（`server/netcode/anticheat.py`，詳見 `docs/06_anticheat.md`）：
  輸入/行動/射速洪水偵測、瞬間移動/加速/出界偵測＋伺服器回彈修正＋踢除、
  回合重置防誤判、外部監聽回呼；13 個測試
- [x] **Rust 遷移藍圖＋parity 實證（M1-M3）**（`docs/07_rust_migration.md`）：
  伺服器熱路徑剖析（`scripts/profile_server.py`，誠實基線 16x 即時）＋
  碰撞空間雜湊寬相位優化（行為不變）＋ `rust/parity/` 跨語言位元組級 parity：
  M1 移動（2000 ticks 全分支，Rust 16.96ns vs Python 9,577ns ≈ 560x）＋
  M2 後座力(RNG) / 彈道(Hitbox/穿透/跨發狀態) / 封包 SerDe 全數位元組一致
  ＋自訂 MT19937（`server/core/rng.py`，與 CPython 位元級一致）＋
  **M3 PyO3 橋接**（`rust/vanta_core_rs` → `server/core/_rust/`，rs_bridge 載入）：
  移動/後座力/彈道雙軌位元組一致、批次 API **45.3x**、重要教訓（細粒度單步跨邊界
  無淨增益 → 伺服器預設 Python、批次化才是正確用法）＋
  **M4 世界迴圈 Rust 化**（`WorldSim`：移動+碰撞整包 Rust、每 tick 2 次跨邊界、
  Python 位置權威 sync_states；位元組一致；世界 step 2.3x、伺服器整體 1.4x——誠實
  低於樂觀預期，因其餘子系統仍 Python）＋
  **M5 純 Rust 伺服器骨架**（`rust/vanta_server`，std UDP + 128Hz 迴圈：
  移動/碰撞/後座力/換彈/協定全 Rust；**每 tick 3.7µs → ~2100x 即時**
  （Python 混合 30.7x 的 ~68 倍）；E2E 與 Python GameClient 互通測試鎖定）＋
  **M6 完整對戰閉環**（`vanta_server`：回合狀態機 BUY→ACTION→END + 經濟
  （擊殺 200/勝 3000/連敗 1900→2400→2900/安放 300/上限 9000）+ Spike
  （安放 4s/倒數 45s/拆除 7s 檢查點/爆炸範圍致死）+ 購買（步槍/重甲）+
  MATCH_STATE 封包（36B，Python↔Rust 位元組一致）+ 多場併發（--matches N）
  + selftest 全過（移動/射擊/經濟/Spike/購買/拆除/回合）+ E2E（MATCH_STATE 輪詢
  + 6 玩家分隊 + 開火執行）＋ 除錯紀實：重複扣血/連敗索引/free_slots 尾端/--fast
- [x] **Godot 客戶端 C# 遷移計畫**（`docs/08_csharp_migration.md`）：
  高頻路徑（封包解析/預測迴圈/Rollback）模組對照、零分配記憶體策略、5 步驗收順序
- [x] 總測試：**235 個全綠**（含 3 個 parity 測試）
- [x] 效能冒煙：10 玩家 × 128Hz 完整對戰 + AI → 31x 即時（純 Python；
  正式版熱路徑移植 Rust 可達更高）

## 追加（2026-09）：track 1「手感三件套」
- [x] **每槍獨立 spray pattern**：`RecoilPattern` 由 6 套 class 表擴充為 **19 把槍專屬**
  （+4 套 class 退回用，共 23 筆）；設計原則寫進碼表註解並由 `tools/weapons/recoil_bundle.py::verify()`
  執行（峰值在前 40%、保護彈不超過图案長度、全自動至少 1/4 彈匣、兩槍不得同形）
- [x] **修復後座永不恢復的實作 bug**：`WeaponState.aim_*_offset` 舊為 `+= p` 只增不減 →
  改取 `RecoilController` 累積值，停火即回吐；換彈完成 `reset_pattern()` 讓图案回到第 1 發
  （**Python 與 `rust/parity/src/weapon_state.rs` 同步修改**，golden 序列不受影響）
- [x] **手感資料鏈**：`tools.cli recoil` → `tools/assets/recoil/recoil.json` →
  `tools.godot.export`（新增 `recoil` 類別）→ `client/assets/recoil/`；協定 0 變動
- [x] **客戶端鏡像層** `client/scripts/recoil_model.gd`：GDScript 重放
  `RecoilController` + `SpreadEngine` + `MovementErrorEngine`；驅動 ①`HUD.set_spread_deg`
  準星＝真實擴散圓（蹲/靜步/空中/剛落地四種狀態回饋）②`WeaponViewModel.set_recoil(pitch, yaw)`
  槍身 kick（模型驅動時停用視角本地 lerp，避免雙重恢復）**不碰相機 _pitch/_yaw**（會 double-count）
- [x] **自動/連點射速**：`_pump_autofire()` 依 bundle 的 `automatic/burst/fire_rate_rps` 補發
- [x] 測試：`tests/test_recoil_data.py` **25 項**（含 `rust/parity` VANDAL 常數漂移守門、
  GDScript 必讀每個 bundle key、6 把槍 × 4 種狀態逐位比對 `SpreadEngine`）
  ＋ Godot 端 `client/tests/test_all.gd::_run_recoil_bundle_check()`
- [x] 文件：`docs/10_gunplay_feel.md`
- [ ] 尚未做：每角第 3/4 顆技能與終點球充能（需先定 snapshot/event 協定改法）、智慧 ping、
  訓練場首發準度計分
