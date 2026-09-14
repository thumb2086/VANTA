# VANTA 回放系統設計（Valorant 風格）

## 🎯 目標

建立完整的對戰回放系統，讓玩家可以：
- 觀看自己的對戰錄影
- 學習高玩操作
- 分析失誤
- 製作精彩鏡頭

---

## 📐 架構設計

### 1. 錄影系統（Recording）

**資料來源**：
- 伺服器端的遊戲狀態（位置/動作/事件）
- 客戶端的攝影機視角
- 聊天記錄

**錄影格式**：
```
replay/
├── meta.json          # 對戰元資料（地圖/玩家/結果）
├── ticks/             # 每 tick 狀態
│   ├── 000001.bin     # tick 1 的完整狀態
│   ├── 000002.bin     # tick 2
│   └── ...
├── events/            # 關鍵事件
│   ├── kills.jsonl    # 擊殺事件
│   ├── abilities.jsonl # 技能使用
│   └── spikes.jsonl   # Spike 事件
└── camera.jsonl       # 攝影機軌跡
```

**資料結構**：
```python
class ReplayTick:
    tick: int              # tick 編號
    time: float            # 時間戳（秒）
    players: list[PlayerState]  # 所有玩家狀態
    projectiles: list      # 彈道/投擲物
    smokes: list           # 煙霧
    spike_state: dict      # Spike 狀態

class PlayerState:
    slot: int
    pos: Vec3
    vel: Vec3
    yaw: float
    pitch: float
    health: int
    shield: int
    weapon: str
    alive: bool
    crouching: bool
    walking: bool
    reloading: bool

class ReplayEvent:
    tick: int
    event_type: str        # "kill", "ability", "spike_plant", etc.
    data: dict             # 事件詳細資料
```

---

### 2. 播放系統（Playback）

**功能**：
- 時間軸控制（播放/暫停/快轉/倒轉）
- 攝影機模式（自由/玩家/鳥瞰）
- 資訊面板（玩家狀態/技能冷卻/經濟）
- 標記系統（精彩時刻/關鍵轉折）

**攝影機模式**：
| 模式 | 說明 |
|---|---|
| 🎯 玩家視角 | 跟隨特定玩家的第一人稱 |
| 🦅 鳥瞰視角 | 高處俯視全場 |
| 🎬 自由視角 | 自由移動的第三人稱 |
| 📹 跟隨子彈 | 跟隨子彈/投擲物視角 |
| 🔍 重播模式 | 多角度慢動作回放 |

**UI 佈局**：
```
┌─────────────────────────────────────────────────────────┐
│  ⏪ ⏸ ▶ ⏩  1:23 / 15:42  │  🎯 玩家 1  │  1x 2x 4x  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                                                         │
│                   遊戲畫面                               │
│                                                         │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  時間軸（可拖曳）                                        │
│  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│  ▲ 擊殺  ▲ 技能  ▲ Spike                              │
├─────────────────────────────────────────────────────────┤
│  [玩家1] [玩家2] [玩家3] [玩家4] [玩家5]                │
│  [玩家6] [玩家7] [玩家8] [玩家9] [玩家10]               │
└─────────────────────────────────────────────────────────┘
```

---

### 3. 儲存系統（Storage）

**本地儲存**：
- 使用 Godot 的 `user://` 目錄
- 自動儲存最近 10 場對戰
- 可手動收藏重要回放

**雲端儲存**（可選）：
- 上傳到 Cloudflare R2
- 與帳號綁定
- 跨裝置觀看

**儲存格式優化**：
- 差異化儲存（只記錄變化）
- 壓縮（gzip）
- 分段儲存（每回合一個檔案）

---

### 4. 分析系統（Analytics）

**統計功能**：
- 擊殺熱點圖
- 移動路徑
- 準星移動軌跡
- 技能使用時機
- 經濟曲線

**視覺化**：
- 小地圖上的軌跡
- 時間軸上的事件標記
- 玩家對比圖表

---

## 🎮 使用場景

### 場景 1：賽後檢討
```
對戰結束 → 點「觀看回放」→ 選擇玩家 → 觀看第一人稱
→ 暫停分析失誤 → 確認改進方向
```

### 場景 2：學習高玩
```
排行榜 → 選擇高段位玩家 → 觀看其回放
→ 學習走位/技能使用/槍法
```

### 場景 3：製作精彩鏡頭
```
觀看回放 → 標記精彩時刻 → 導出為影片
→ 分享到社群媒體
```

### 場景 4：教練分析
```
教練觀看學員回放 → 標記問題
→ 註解說明 → 分享給學員
```

---

## 🔧 技術實現

### 錄影實現

```gdscript
class_name ReplayRecorder
extends Node

var recording := false
var current_tick := 0
var tick_data: Array[PackedByteArray] = []
var events: Array[Dictionary] = []

func start_recording() -> void:
    recording = true
    current_tick = 0
    tick_data.clear()
    events.clear()

func record_tick(world_state: Dictionary) -> void:
    if not recording:
        return
    # 壓縮 tick 資料
    var compressed := _compress_tick(world_state)
    tick_data.append(compressed)
    current_tick += 1

func record_event(event_type: String, data: Dictionary) -> void:
    events.append({
        "tick": current_tick,
        "type": event_type,
        "data": data,
    })

func stop_recording() -> ReplayData:
    recording = false
    return ReplayData.new(tick_data, events)

func _compress_tick(state: Dictionary) -> PackedByteArray:
    # 差異化壓縮：只記錄與上一 tick 的差異
    var buffer := PackedByteArray()
    # ... 壓縮邏輯
    return buffer
```

### 播放實現

```gdscript
class_name ReplayPlayer
extends Node

var replay_data: ReplayData
var current_tick := 0
var playback_speed := 1.0
var is_playing := false
var camera_mode := "player"  # player / free / overview

signal tick_updated(tick: int, time: float)
signal playback_started()
signal playback_paused()

func load_replay(data: ReplayData) -> void:
    replay_data = data
    current_tick = 0

func play() -> void:
    is_playing = true
    playback_started.emit()

func pause() -> void:
    is_playing = false
    playback_paused.emit()

func seek(tick: int) -> void:
    current_tick = clampi(tick, 0, replay_data.tick_count - 1)
    _apply_tick(current_tick)

func set_speed(speed: float) -> void:
    playback_speed = speed

func set_camera_mode(mode: String) -> void:
    camera_mode = mode

func _process(delta: float) -> void:
    if not is_playing:
        return
    current_tick += int(128.0 * delta * playback_speed)
    if current_tick >= replay_data.tick_count:
        current_tick = 0  # 循環播放
    _apply_tick(current_tick)
    tick_updated.emit(current_tick, float(current_tick) / 128.0)

func _apply_tick(tick: int) -> void:
    var state := replay_data.get_tick(tick)
    # 更新所有玩家位置
    # 更新攝影機
    # 更新特效
```

### 資料結構

```gdscript
class_name ReplayData
extends Resource

@export var meta: Dictionary  # 對戰元資料
@export var ticks: Array[PackedByteArray]  # 壓縮的 tick 資料
@export var events: Array[Dictionary]  # 關鍵事件
@export var duration: float  # 總時長（秒）

func get_tick(index: int) -> Dictionary:
    if index < 0 or index >= ticks.size():
        return {}
    return _decompress_tick(ticks[index])

func get_events_in_range(start_tick: int, end_tick: int) -> Array:
    return events.filter(func(e): return e["tick"] >= start_tick and e["tick"] <= end_tick)

func get_kill_events() -> Array:
    return events.filter(func(e): return e["type"] == "kill")

func _decompress_tick(data: PackedByteArray) -> Dictionary:
    # ... 解壓縮邏輯
    return {}
```

---

## 📱 UI 設計

### 回放選擇畫面

```
┌─────────────────────────────────────────────────────────┐
│  📹 回放列表                               [篩選 ▼]    │
├─────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────┐ │
│  │ 🏆 勝利  Bind  一般模式  13-8  15:42  thumb      │ │
│  │    12/8/15  KDA: 25/12/8  Agent: 夜露            │ │
│  │                              [觀看] [刪除] [分享] │ │
│  └───────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────┐ │
│  │ ❌ 敗利  Hasen  競技模式  10-13  18:21  thumb     │ │
│  │    12/10  KDA: 18/15/12  Agent: 幽影             │ │
│  │                              [觀看] [刪除] [分享] │ │
│  └───────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 🏆 勝利  死鬥  死鬥模式  20-15  08:45  thumb     │ │
│  │    12/08  KDA: 20/8/2  Agent: 捷提               │ │
│  │                              [觀看] [刪除] [分享] │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  共 3 場回放  │  已使用 125 MB / 500 MB               │
└─────────────────────────────────────────────────────────┘
```

### 回放播放器

```
┌─────────────────────────────────────────────────────────┐
│  ← 返回  │  Bind - 一般模式  │  13-8 勝利  │  ⚙ 設定  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                                                         │
│                   遊戲畫面（全屏）                       │
│                                                         │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  ⏪ ⏸ ▶ ⏩  05:23 / 15:42  │  🎯 thumb  │  1x 2x 4x  │
├─────────────────────────────────────────────────────────┤
│  時間軸                                                  │
│  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│  ▲ 擊殺  ▲ 技能  ▲ Spike  ▲ 回合結束                   │
├─────────────────────────────────────────────────────────┤
│  攻方：thumb(AI-01) AI-02 AI-03 AI-04 AI-05            │
│  守方：AI-06 AI-07 AI-08 AI-09 AI-10                   │
│  [_thumb] [AI-01] [AI-02] ... [AI-10]                  │
└─────────────────────────────────────────────────────────┘
```

---

## 🗄️ 資料庫 Schema（雲端儲存）

```sql
-- 回放元資料
CREATE TABLE replays (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    map_name VARCHAR(50),
    mode VARCHAR(20),
    result VARCHAR(10),  -- win/loss
    score_a INT,
    score_b INT,
    duration FLOAT,
    file_size INT,
    storage_path VARCHAR(255),
    created_at TIMESTAMP,
    is_favorite BOOLEAN DEFAULT FALSE,
    view_count INT DEFAULT 0,
    share_count INT DEFAULT 0
);

-- 回放統計
CREATE TABLE replay_stats (
    replay_id UUID REFERENCES replays(id),
    player_slot INT,
    player_name VARCHAR(50),
    agent VARCHAR(30),
    kills INT,
    deaths INT,
    assists INT,
    damage INT,
    headshots INT,
    score INT  -- 戰鬥評分
);

-- 回放標記
CREATE TABLE replay_markers (
    id UUID PRIMARY KEY,
    replay_id UUID REFERENCES replays(id),
    tick INT,
    marker_type VARCHAR(20),  -- kill, ace, clutch, etc.
    description TEXT,
    created_by UUID
);
```

---

## 📊 效能考量

| 項目 | 目標 | 實現方式 |
|---|---|---|
| 錄影大小 | < 10 MB/15分鐘 | 差異化壓縮 + 量化 |
| 載入時間 | < 2 秒 | 分段載入 + 預緩衝 |
| 播放流暢度 | 60 FPS | 增量更新 + LOD |
| 搜尋速度 | < 100 ms | 索引 + 二分搜尋 |
| 儲存空間 | 500 MB 上限 | 自動清理最舊回放 |

---

## 🔮 未來擴展

### Phase 2（v2.0）
- [ ] 雲端同步（跨裝置觀看）
- [ ] 社群分享（上傳精彩鏡頭）
- [ ] 教練註解系統
- [ ] AI 自動標記精彩時刻

### Phase 3（v3.0）
- [ ] 即時觀戰（觀看進行中的比賽）
- [ ] 多視角同步播放
- [ ] VR 觀看模式
- [ ] 匯出為影片（MP4）

---

## 📋 實現優先順序

| 階段 | 功能 | 工作量 | 優先度 |
|---|---|---|---|
| **Phase 1** | 基礎錄影/播放 | 大 | ⭐⭐⭐ |
| **Phase 1** | 時間軸控制 | 中 | ⭐⭐⭐ |
| **Phase 1** | 攝影機切換 | 中 | ⭐⭐⭐ |
| **Phase 1** | 回放列表 UI | 中 | ⭐⭐ |
| **Phase 2** | 雲端儲存 | 大 | ⭐⭐ |
| **Phase 2** | 社群分享 | 中 | ⭐⭐ |
| **Phase 2** | 教練註解 | 中 | ⭐ |
| **Phase 3** | 即時觀戰 | 大 | ⭐ |
| **Phase 3** | 影片匯出 | 大 | ⭐ |

---

## 🎯 總結

回放系統是提升遊戲體驗的關鍵功能：
1. **學習工具**：讓新手快速進步
2. **社群內容**：產生精彩影片
3. **教練系統**：專業訓練支援
4. **賽事觀賞**：電子競技基礎

預計 Phase 1 需要 **2-3 週**開發時間。
