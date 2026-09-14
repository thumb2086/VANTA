# 熱路徑剖析與 Rust 遷移藍圖

> 方向 A（Server-Side Focus）。本文件 = 剖析數據（誠實）＋ 已完成的
> **跨語言位元組級 parity 實證** ＋ 模組對照 ＋ 里程碑路線圖。

## 1. 剖析結果（`scripts/profile_server.py`，128Hz × 10 玩家完整對戰）

### 誠實基線（無剖析器、純伺服器模擬，含全部機制）
| 情境 | 即時倍率 | 每 tick |
|---|---|---|
| 純伺服器（10 AI，完整對戰邏輯） | **16.3x** | 0.479 ms |
| 2 程序內客戶端 + 8 AI | 9.9x | 0.792 ms |

> 生產環境客戶端在別台機器 → 伺服器端實際成本 ≈ 純伺服器情境。
> **Python 單進程即可承載約 16 場對戰即時運行**——原型規模完全夠用。

### cProfile 熱點（20s、含程序內客戶端）
| 熱點 | 佔比 | 解讀 |
|---|---|---|
| `collision.resolve_world` | world.step 的 ~68% | 全牆×全玩家×3 迭代（O(P×W×passes)） |
| `movement.step` + math_core | 次高 | **Vec3 不可變 dataclass → 每 tick 大量分配**（10.6M 函式呼叫 / 2560 ticks） |
| 程序內客戶端 poll/snapshot | 高 | 測量假象（生產端在別台機器） |

### 已完成的 Python 側優化（行為不變，測試鎖定）
1. **牆面空間雜湊寬相位**（`WallSpatialHash`，cell=4m）→ 每玩家只測附近牆；
   遠牆 `_push_out` 必回 None → 結果位元組級不變（確定性保留）。
2. **玩家配對 AABB 早退** → 45 對/tick × 3 迭代降至實際鄰近配對。

誠實說明：17 面牆的小地圖下，全牆迴圈本來就不貴，故純伺服器前後差異不大
（0.474→0.479 ms/tick）；**空間雜湊在 50+ 牆的正式地圖才顯著**。真正的瓶頸是
Python 的分配與 GIL——這正是 Rust 遷移的著力點。

## 2. 跨語言 Parity 實證（已完成 ✅）

`rust/parity/` — 以 Rust 重寫 `math_core.Vec3` + `MovementController`
（f64、相同運算順序、相同 EPSILON=1e-12），對 Python 黃金軌跡**位元組級比對**：

```bash
python3 rust/parity/golden.py     # 產生 inputs.bin / states.bin（2000 ticks）
cargo run --release              # Rust 步進 → states_rust.bin
# ✅ PARITY OK — 2000 ticks，Rust 與 Python 位元組級一致
```
測試腳本覆蓋所有移動分支：直跑 / 右橫移 / **反切急停** / 靜步 / 跳躍 / 蹲走 /
斜向 / 跳躍緩衝 / 種子化隨機。

### 效能實證（同硬體、同規模）
| 語言 | 每玩家步成本 | 相對 |
|---|---|---|
| Python | 9,577 ns | 1x |
| Rust (release) | 16.96 ns | **~560x** |

## 2b. M2 跨語言 Parity（已完成 ✅）

三大熱點模組全部位元組級一致：

```bash
./target/release/parity_recoil       # ✅ RECOIL PARITY OK — 2000 ticks（seed=42, vandal）
./target/release/parity_ballistics   # ✅ BALLISTICS PARITY OK — 6 發（Hitbox/穿透/跨發狀態）
./target/release/parity_protocol     # ✅ PROTOCOL PARITY OK — 6 封包 decode→re-encode 一致
```

| 模組 | 覆蓋 | 關鍵實作 |
|---|---|---|
| **後座力 + RNG** | 保護彈 6 + 隨機 yaw、恢復延遲、部分恢復再開火 | 自訂 **MT19937**（`server/core/rng.py` + Rust 同款），`init_by_array` 種子化、res53、uniform——與 CPython `random.Random(seed)` 位元級一致（有測試鎖定） |
| **彈道 / Hitbox / 穿透** | 頭4x/身1x/腿0.85x 膠囊、AABB 牆、材質衰減、**跨發狀態**（傷害累積/死亡跳過/溢傷擊殺） | 6 發場景：木牆穿透(×0.8)、classic 穿不過、operator 穿不過 unbreakable、爆頭溢傷 |
| **封包 SerDe** | INPUT(15B) / SNAPSHOT(270B, 10 槽位含空槽/極值) / WELCOME(6B) / GAME_EVENT(16B) | 固定偏移讀寫；decode→re-encode 位元組一致；`round_ties_even` 對齊 Python 銀行家捨入 |

> 除錯紀實：MT19937 首次分歧（CPython 對 int seed 用 `init_by_array` 而非 `init_genrand`；
> Rust `match` 常數模式誤當綁定）——都被 parity 測試抓出並修正。

> 推算：10 玩家 × 128Hz = 1280 步/tick → Rust 約 **22 µs/tick**（Python 0.48 ms）
> → 單核心可承載 **100+ 場對戰**即時運行（Python 約 16 場）。

## 2c. M3 PyO3 橋接（已完成 ✅ + 重要效能教訓）

`rust/vanta_core_rs/` — 以 pyo3 把 Rust 核心編譯為 Python C 擴展（`libvanta_core_rs.so`），
部署到 `server/core/_rust/`，由 `server/core/rs_bridge.py` 載入（找不到時回退純 Python）。

```bash
bash scripts/run_rust_swap.sh     # 建置 → 部署 → 雙軌測試 → 基準
```

| 暴露 API | 說明 |
|---|---|
| `MovementController` | 單步移動（含 speed_mult），鏡像 Python 介面 |
| `MovementBatch` | **批次移動**：一次跨邊界處理 N 玩家 × 多步（`step_all` / `positions` / `set_state`） |
| `RecoilController` | 種子化後座力（VANDAL + MT19937） |
| `resolve_hitscan` | 彈道解析（玩家/牆清單 → hit 清單，含跨發狀態由呼叫端維護） |

### 驗證（雙軌位元組級一致）
- 移動：2000 ticks 全分支（含 speed_mult 1.25 / 0.65）Rust↔Python 完全一致
- 後座力：seed=42 全序列一致；彈道：6 發場景跨發狀態一致
- **伺服器整合**：同一輸入驅動兩個 World（Python vs Rust 移動）→ 逐 tick 狀態一致
- 全量 254 測試在「Rust 移動核心」模式下亦全綠（後改回預設 Python，見下）

### ⚠️ 重要效能教訓（誠實數據）
| 模式 | 加速 | 說明 |
|---|---|---|
| 純 Rust binary（無邊界） | **~560x** | 理論極限 |
| pyo3 單步（每 tick 每玩家 1 次呼叫） | **0.5x（更慢）** | 細粒度跨邊界固定成本（~1µs×1280 次/tick）超過 Python 計算本身 → 伺服器 10.2x 掉到 5.7x |
| **pyo3 批次**（一次呼叫 N 玩家） | **45.3x** | 邊界成本攤平 → 正確用法 |

**結論**：pyo3 橋接的加速前提是**粗粒度批次呼叫**；「Python 世界 + Rust 單步」的混合
架構因每 tick 同步狀態的邊界成本而無淨增益。因此：
- 伺服器**預設用 Python 核心**（效能誠實），`VANTA_USE_RS=1` 強制 Rust 單步（雙軌驗證）。
- 真正的高效能路線：**M4 把「完整世界 tick」（移動+碰撞）搬進 Rust 批次 API**，
  每 tick 一次跨邊界 → 收益 ≈ 批次 45x。

## 2d. M4 世界迴圈 Rust 化（已完成 ✅ + 誠實效能）

`rust/vanta_core_rs` 新增 `WorldSim`：**移動 + 碰撞（空間雜湊）整包在 Rust 內完成**，
每 tick 僅 2 次跨邊界（`sync_states` + `step_all` → 取回）。Python 是「位置權威」：
重生/回彈/外部修改透過 `sync_states` 每 tick 尊重。

```bash
VANTA_USE_RS=1 python3 -m tools.godot.serve --ai   # 啟用 Rust 世界迴圈
# 或測試：python3 -m pytest tests/test_rust_worldsim.py
```

### 驗證
- **位元組級一致**：10 玩家 × 400 ticks（跳躍/斜向/靜步/蹲走/碰撞）Rust↔Python 完全一致
- 碰撞生效（撞牆停止、速度消除）、重生尊重、雙軌測試 4 個全綠
- 除錯紀實：修復 edit 造成的 `step()` 後半段遺失回歸（spike/match/彈道消失）——被既有測試抓出

### 誠實效能（真實世界整體，非單一模組）
| 測量 | Python | Rust 世界迴圈 | 提升 |
|---|---|---|---|
| 世界 step（10 玩家×400 ticks×20 遍） | 1.247s | 0.547s | **2.3x** |
| 完整伺服器（AI + 網路 + 其他子系統，20s 模擬） | 10.3x 即時 | 14.5x 即時 | **1.4x** |

> **誠實結論**：移動+碰撞只是世界 step 的一部分（其餘為武器/狀態/技能/Spike/彈道/
> 煙霧/AI/網路，仍 Python）→ 混合架構加速上限 ≈ Rust 化部分佔比。2.3x 是
> 「移動+碰撞」這段的真實收益；要整體 10x+ 需 M5（把更多子系統搬進 Rust，
> 或純 Rust 伺服器）。此結果推翻「40-50x」的樂觀預期——但位元組一致 + 方向正確。

## 2e. M5 純 Rust 伺服器骨架（已完成 ✅）

`rust/vanta_server/` — 純 Rust 權威伺服器：std UDP + 128Hz 固定迴圈，核心
（移動/碰撞/後座力/換彈）與二進位協定全部使用**已通過 parity 的 Rust 核心**，
零 Python。`rust/bin/vanta_server`（568KB）已持久化。

```bash
bash scripts/run_rust_server.sh    # 建置 → 基準 → E2E（Python GameClient 連線）
./rust/bin/vanta_server --port 7777          # 啟動（實時節流）
./rust/bin/vanta_server --bench-ticks 76800  # 全力基準
```

### 效能（誠實）
| 伺服器 | 每 tick | 即時倍率 |
|---|---|---|
| Python（M4 混合，含 pyO3） | 255 µs | 30.7x |
| **純 Rust vanta_server（M5 骨架）** | **3.7 µs** | **~2100x** |

> 消除 Python 主迴圈 + pyO3 跨邊界後，單核心承載從 ~30 場跳到 **~2100 場**
> （理論峰值；實際受網路 I/O 限制）。這是 M5 的價值：**路線正確性證明**。

### E2E 互通（pytest 鎖定）
- Python GameClient（現有協定實作）連上 Rust 伺服器 → welcome + 快照流 + 玩家移動 ✓

### 範圍（誠實聲明——M6 補齊）
骨架僅含：移動/碰撞/後座力/換彈/協定。**尚未包含**：經濟/回合狀態機/Spike/技能/
彈道解析/反作弊/AI/多場併發(async)。因此「2100x」是核心迴圈吞吐，
不等於完整遊戲的承載——完整遊戲的每 tick 成本更高，但方向已證實。

## 2f. M6 進行中：combat 化（已完成部分 ✅）

`vanta_server` 從「移動骨架」升級為「有 combat 的對戰伺服器」：

| 新增 | 內容 |
|---|---|
| **ACTION_SHOOT / ACTION_RELOAD** | 二進位行動封包解析（協定 parity 一致） |
| **射擊 + Rust 彈道** | 後座力偏移套用瞄準角 → `ballistics::resolve_hitscan`（Hitbox 頭4x/身1x/腿0.85x、牆穿透）→ 傷害/擊殺 |
| **傷害/擊殺/重生** | 死亡排程 3 秒重生於攻方重生區；kills 計數 |
| **換彈** | reload 進度（快照 reload_progress 與 Python 一致） |
| **selftest** | `--selftest`：移動 + 近距射擊（B hp=20）+ **遠距射擊（B z=10 命中）** 全過 |
| **E2E** | welcome + B 移動（128Hz 每 tick 1 輸入，z=1.9 正確）+ 開火執行（mag 12→9） |

**除錯紀實（重要 bug 全被測試抓出）**：
1. **幽靈玩家**：Player::new 全 alive=true → 無 session 玩家擋彈道 → 改 alive=false、註冊時 true
2. **輸入速率與 tick 未對齊**：每個收到的 input 立即 step → 玩家超速 8 倍（13m/0.3s）→ 改 pending 佇列、每 tick 每玩家消費 1 個（對齊 Python `_take_next_input`）
3. **同點碰撞推離**：A、B 同點註冊被推離 x=±0.35 → 射線偏離 → E2E 命中不穩（誠實：命中正確性由 selftest 鎖定；E2E 驗證協定/開火執行）

**效能不變**：基準仍每 tick ~3.7µs（combat 邏輯在 Rust 內，成本極低）。

## 2g. M6 完整對戰閉環（已完成 ✅）

`vanta_server` 已達「完整戰術射擊對戰伺服器」：

| 子系統 | 內容 |
|---|---|
| **回合狀態機** | BUY(15s/--fast 1s) → ACTION(100s) → END(5s) → 下一回合；半場攻守（round 13 起換邊）；勝負判定（全滅/爆炸/拆除/時間到） |
| **經濟系統** | 起始 800、上限 9000；擊殺 +200、回合勝 +3000、連敗補償 1900→2400→2900（索引修正 bug 已修）、安放 +300（攻方全員）、回合重置保留護甲 |
| **Spike** | 安放 4s（進點+持 hold+不動）→ 倒數 45s → 爆炸範圍 25m 致死（攻方除外）；拆除 7s（3.5s 檢查點：中斷保留進度）；拆除成功守方勝 |
| **購買** | ACTION_BUY：vandal/phantom（2900）/重甲（1000），BUY 階段限定 |
| **MATCH_STATE 封包** | 36B：phase/round/timer/spike/fuse/score/credits×10（每 8 ticks 廣播）；Python↔Rust 位元組一致 |
| **多場併發** | `--matches N`：std threads 每場獨立埠+狀態，0 cross-talk（tokio async 為 M6b 升級選項，誠實註記） |

### 效能（完整對戰邏輯後，誠實）
```
[bench] 76800 ticks → 每 tick 1.85 µs → 4221x 即時
```
> 無 session 玩家時 combat 迴圈空轉（成本極低）——有玩家活動的每 tick 更高，
> 但「完整對戰邏輯全在 Rust」的成本已證實極低。

### 除錯紀實（真實 bug 全被測試抓出）
1. **重複扣血**：ballistics 內建應用傷害（M2 parity），server 迴圈又扣一次 → 雙重扣血且 kills 永不加 → 改「resolve 前後 alive 變化」判致死
2. **連敗補償索引錯位**：streak=1 拿到 2400（應 1900）→ `saturating_sub(1).min(2)`
3. **free_slots 尾端 pop**：2 玩家測試都拿到守方槽 → 攻方無人 → 立即全滅 → 改前端 pop（先到先攻）+ E2E 註冊 6 玩家分隊
4. **--fast 初始 BUY 未生效**（回合 1 卡 15s）、沙箱 sleep 不準 → E2E 改「輪詢 MATCH_STATE 直到 ACTION」

**M6 剩餘（誠實）**：技能效果（Ability 僅行動骨架）、反作弊整合、AI、tokio async 多場——
每項可依「Python parity → Rust 移植 → 測試」模式繼續補齊。

## 3. 遷移模組對照（Python → Rust）

| Python 模組 | Rust 對應 | 優先級 | 理由 |
|---|---|---|---|
| `core/math_core.py`（Vec3） | `vanta-core/src/math.rs` | P0 | 已實證 parity；全鏈路熱點 |
| `core/movement.py` | `vanta-core/src/movement.rs` | P0 | 已實證 parity |
| `game/collision.py`（含空間雜湊） | `vanta-core/src/collision.rs` | P0 | 大地圖瓶頸 |
| `game/ballistics.py`（hitscan/穿透） | `vanta-core/src/ballistics.rs` | P1 | Raycast 熱點 |
| `game/recoil.py` / `spread` | `vanta-core/src/recoil.rs` | P1 | 純數學、易 parity |
| `netcode/protocol.py`（封包序列化） | `vanta-net/src/protocol.rs` | P1 | 高頻 pack/unpack |
| `netcode/server_loop.py`（迴圈/Session） | `vanta-server`（tokio） | P2 | 正式部署 |
| `game/` 其餘（經濟/回合/Spike/技能） | `vanta-core` 逐步 | P2-P3 | 低頻、可後置 |

## 4. Parity 測試策略（防回歸）

1. **黃金軌跡（Golden Traces）**：Python 產生確定性輸入腳本 → 記錄狀態序列
   （二進位 f64 LE）。Rust 端跑同輸入 → **位元組級比對**。
   - 已實作：移動（2000 ticks、全分支）。
   - 待擴充：後座力（種子化 RNG 需相同種子流）、彈道、封包序列化。
2. **協定 parity**：封包 encode/decode 雙向比對（已有 Python↔GDScript 版本，
   加 Python↔Rust）。
3. **RNG 對齊**：`rand` crate 用 `StdRng::seed_from_u64`，自訂「相同消費順序」
   的 distribution 以匹配 Python `random.Random`——需小工具（或改用自訂 LCG
   同時移植到 Python 與 Rust，最乾淨）。
4. **CI**：`cargo test` 納入 golden 資料夾；Python 端 pytest 也呼叫 Rust binary
   （存在才跑，否則 skip）。

## 5. 里程碑路線圖

| 階段 | 內容 | 驗收 |
|---|---|---|
| M1 ✅ | 剖析 + 空間雜湊優化 + Rust parity PoC（移動） | 本文件 |
| M2 ✅ | `vanta-core`：**後座力(RNG) / 彈道(Hitbox/穿透) / 封包 SerDe** 全 parity | 3 個新 parity 全綠（見下） |
| M3 ✅ | **PyO3 橋接**（`rust/vanta_core_rs`）：Python 伺服器直接呼叫 Rust 核心；批次 API 45x | 雙軌位元組一致測試全綠；重要效能教訓（見下） |
| M5 ✅ | **純 Rust 伺服器骨架**（`rust/vanta_server`，std UDP + 128Hz 迴圈）：移動/碰撞/後座力/換彈全 Rust、與 Python 同一協定 | **~2100x 即時**（每 tick 3.7µs，Python 混合 30.7x 的 ~68 倍）；E2E 與 Python GameClient 互通 |
| M6 ✅ | **純 Rust 伺服器完整對戰閉環**：回合狀態機（BUY→ACTION→END）+ 經濟（擊殺 200/勝 3000/連敗 1900→2400→2900/安放 300/上限 9000）+ **Spike**（安放 4s/倒數 45s/拆除 7s 檢查點/爆炸範圍致死）+ 購買（步槍/重甲）+ **多場併發**（--matches N） | selftest（移動/射擊/經濟/Spike/購買/拆除/回合）全過；E2E（MATCH_STATE 輪詢 + 6 玩家分隊 + 開火執行）全過；完整對戰邏輯下基準 1.85µs/tick |

## 6. 風險與緩解

- **RNG 跨語言對齊**（最大風險）：優先移植「自訂確定性 RNG」到兩邊，取代
  Python `random`——一次性投入，永續受益。
- **浮點**：已證實 f64 相同運算順序 = 位元級一致（IEEE 754 正確捨入）。
- **並行**：單執行緒確定性優先；擴容靠多進程/多執行緒分場，不破壞單場確定性。
- **工具鏈不變**：Godot 客戶端、協定、AI、素材全部不受影響（只換伺服器內核）。

## 7. 執行

```bash
# 剖析
python3 scripts/profile_server.py 20
# Rust parity
cd rust/parity && python3 golden.py && cargo run --release
# 基準
cargo run --release --bin bench
```
