# Godot 客戶端 C# 高頻路徑遷移計畫

> 方向 B（Client-Side Focus）。本文件是**計畫**：模組對照、記憶體對齊策略、
> 遷移順序與驗收。實際 C# 程式碼需在 Godot 4.4+ **.NET 版**編輯器中編譯驗證
> （本沙箱無 .NET 版 Godot，故以計畫 + 對照表交付，程式碼留待有 .NET 環境時落地）。

## 為什麼要遷 C#（誠實評估）

| 面向 | GDScript（現況） | C# |
|---|---|---|
| 封包解析（128Hz × 快照 270B） | 每次 Parse 產生 Dictionary 分配 → GC | 直接 `Span<byte>` 讀取，零分配 |
| 客戶端預測迴圈（128Hz） | 每 tick 物件分配 | struct 值型別，零 GC |
| Rollback 重算 | 同上 | 同上 |
| 與伺服器/Rust 共用邏輯 | 需重寫 | 可與 Rust 共用數值定義（DSL/原始檔） |
| 團隊熟悉度 | 低門檻 | 需 .NET 工具鏈 |

**關鍵點**：128Hz 下 GC Pause 會造成微卡頓。GDScript 的 Dictionary/Array
分配在高頻路徑是主要風險；C# 用 `Span<byte>` + struct 可做到**零分配**。

## 遷移模組對照（GDScript → C#）

| GDScript 模組 | C# 對應 | 優先級 | 內容 |
|---|---|---|---|
| `net_client.gd`（收包解析） | `NetClient.cs` | P0 | `Span<byte>` 直接讀快照欄位；事件佇列用 `struct GameEvent` |
| `movement_local.gd` | `LocalMovement.cs` | P0 | 純 struct 移植（與 Rust/Python 同公式——三語 parity） |
| `main.gd` 預測/和解迴圈 | `PredictionLoop.cs` | P0 | 固定步進 + 重放緩衝（`struct PendingInput` 陣列） |
| `weapon_viewmodel.gd` 動畫狀態 | 可留 GDScript（P2） | P2 | 動畫是渲染層，非高頻；GC 影響小 |
| `hud.gd` / `vfx_manager.gd` | 留 GDScript | — | 事件驅動，非每 tick 熱路徑 |

## 記憶體對齊策略（避免 GC Pause）

1. **快照解析零分配**：
   ```csharp
   // 範例：直接用 unsafe/Span 讀取，不建立 Dictionary
   ReadOnlySpan<byte> s = packet;                     // 270 bytes
   int off = SNAPSHOT_HEADER + slot * SNAPSHOT_ENTRY;
   float px = BitConverter.ToInt16(s.Slice(off + 2, 2)) * 0.01f;
   ```
2. **玩家狀態用 struct 陣列**：`PlayerState[10]`（pos/vel/health/mag…），
   取代 `Dictionary<int, Dictionary>` 每幀重建。
3. **預測緩衝固定陣列**：`PendingInput[N]` ring buffer（struct），無 List 分配。
4. **事件佇列 struct**：`GameEvent { int code; int tick; int p0; int p1; }` 固定大小。
5. **啟用 Server GC**（`GcServer=true`）＋ `--disable-gc` 熱點除外……不——
   保持預設，靠「零分配」從根本消除 Pause。

## 三語 Parity（新增維度）

Rust/Python 已位元級一致（見 docs/07）。C# 加入後：
- **移動**：相同 f64 公式 → 3 語 golden 比對（Python 產生黃金，Rust/C# 各自比對）。
- **協定**：已有 Python↔GDScript parity 測試；C# 解析器用同一份測試資料。

## 遷移順序（每步可獨立驗證）

| 步驟 | 內容 | 驗收 |
|---|---|---|
| S1 | Godot .NET 專案啟用（`project.godot` + csproj），`NetClient.cs` 先並行存在 | 封包 parity 測試（C# vs Python）全綠 |
| S2 | `LocalMovement.cs` + 三語 golden | 位元組級一致 |
| S3 | `PredictionLoop.cs` 取代 GDScript 預測迴圈 | 相同延遲測試（50/100/200ms）一致 |
| S4 | 移除 GDScript 熱路徑（net_client/movement_local），只留渲染層 | 記憶體分析：GC 分配 ≈ 0（128Hz） |
| S5 | （可選）視角模型動畫也遷 C# 以利 AnimationPlayer 程式化控制 | 展示場一致 |

## 執行環境需求

```bash
# Godot 4.4+ .NET 版（含 C# 支援）
# 需 .NET SDK 8+；csproj 引用 Godot.NET.Sdk/4.4.0
```

## 風險

- **雙語維護**：S1-S3 期間 GDScript/C# 並存 → 靠 parity 測試鎖定不漂移。
- **Godot C# 熱重載**：編輯器熱重載支援較弱 → 預測迴圈以 `--headless` 單測為主。
- **效能收益量級**：128Hz × 10 玩家的封包解析/預測，GDScript 其實已可跑；
  C# 的收益是「消除 GC Pause」而非「跑不動」——定位為商業化穩定性投資。
