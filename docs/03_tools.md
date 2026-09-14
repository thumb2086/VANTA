# 素材工具鏈文件 — Programmable Asset Pipeline

> VANTA 的「可程式化一切素材產生器」：以程式碼（seed + 規則）產生
> 音效、武器、地圖、視覺特效、擊殺特效等全部素材，無需任何 DCC 工具。
> 全部確定性（同 seed 同產物）、零第三方依賴、與 `server.game` 直接相容。

## 統一入口

```bash
python -m tools.cli init                 # 建立 assets/
python -m tools.cli all                  # 產生全部素材 + manifest（70+ 素材）
python -m tools.cli sfx                  # 32 個音效 WAV
python -m tools.cli vfx                  # 9 粒子特效 JSON + 12 SVG 貼圖
python -m tools.cli weapons --count 12   # 12 把模組化武器 JSON
python -m tools.cli maps --seeds 1 7 42  # 3 張程序化地圖 JSON
python -m tools.cli fx                   # 事件綁定表 + 擊殺特效範例
```

## 子系統

### 1. 可程式化音效（`tools/sfx/`）
DSP 數學合成（wave 標準庫寫檔），32 種音效：
`gunshot_*`（6 類武器音色）/ `reload` / `headshot_confirm` / `kill_confirm` /
`multi_kill_2..4`（連殺遞升）/ `explosion` / `footstep` / `landing` /
`ability_cast` / `flash_explode` / `smoke_puff` / `trap_trigger` /
`spike_beep/planted/defused/exploded` / `round_win/loss` / `ui_*`。

- 每個音效是「函式」→ 可程式化調整（音量/音高/長度）
- `synth.reseed(n)` → 確定性合成

### 1b. 程序化 BGM（`tools/sfx/bgm.py`）
以「音樂理論 + 種子化隨機」產生背景音樂：
- 十二平均律、音階（minor/phrygian/dorian/major）、級數和弦進行（i-VI-III-VII 等）
- 旋律隨機漫步（重拍吸附和弦音）、貝斯跟根音、鋪底 Pad（失諧鋸齒）、鼓組
  （four_floor / half_time 種子化節奏圖案）
- 5 種風格：**combat**（142BPM 弗里吉安）/ **tension**（安放後緊張）/ **menu**（大廳）/
  **victory** / **defeat**
- 結構 = 前奏 + 主循環 → 輸出 **loop_start_sec** 循環點 → 客戶端無縫 loop
- 命令：`python -m tools.cli bgm` → `assets/bgm/bgm_*.wav` + 元資料 JSON

### 1c. 可程式化人物（角色）產生器（`tools/agents/`）
以 seed 產生完整角色：
- **身分**：代號（批內唯一）、本名、代稱、陣營、簡介（模板組裝）
- **角色定位**：duelist（決鬥者）/ controller（控場者）/ sentinel（哨衛）/ initiator（先鋒），
  含定位描述、速度倍率、護甲偏好
- **技能組**：由技能池（flash/frag/smoke/trap/stim/heal）依定位模板組合
- **配色**：seed 驅動主色/強調色/背景 → 肖像與 UI 用
- **肖像**：程序化 SVG 頭像（背景漸層/面罩護目鏡/肩甲/定位圖騰/代號條）
- **進遊戲**：`register_agent(def)` → `Player(agent_key=key)` 即可使用；
  新增 StimAbility（移動加速）+ HealAbility（治療）進入技能池
- 命令：`python -m tools.cli agents --count 8` → `assets/agents/*.json` + 肖像 SVG

### 2. 可程式化槍械模組化（`tools/weapons/`）
- `WeaponFrame`（接收器）+ `Mod`（模組：barrel/muzzle/mag/grip/sight/stock）
- 修正規則：`<stat>_mult`（乘算）/ `<stat>_add`（加算）
- `generate_weapon(seed, frame)` → seed 驅動隨機組合模組
- `validate_balance()` → 數值平衡驗證（超出上下限即警告）
- `register_to_game(mw)` → 註冊進 `server.game.weapons.WEAPONS`，**可直接裝備開火**

### 3. 可程式化地圖編輯器（`tools/maps/`）
- `generate_map(seed, ...)` → 對稱 A/B 點位、三路線、隨機掩體、重生區
- `validate_map()` → 界內/點位敞開/重生不卡牆 結構驗證
- `save_map / load_map` → JSON 往返 → 直接餵給 `World(map_data=...)`

### 4. 可程式化視覺特效（`tools/vfx/`）
- 粒子發射器（point/cone/sphere/directional）：數量/速度/壽命/重力/顏色漸變/拖尾
- 9 種預設：muzzle_flash / shell_casing / spark / explosion_debris / smoke_puff /
  blood / hit_marker / tracer / kill_confirm
- `animate_frames(emitter, seed)` → 確定性關鍵幀（渲染層直接補間）
- SVG 產生器：12 種貼圖（粒子 sprite、準星、擊殺確認框、技能/Spike 圖示）

### 5. 可程式化擊殺特效（`tools/fx/`）
- `kill_feed_entry()` → 擊殺訊息（兇手/武器/爆頭/連殺）
- `kill_confirm_sequence(streak)` → 確認動畫關鍵幀（縮放/淡入淡出）
- `multi_kill_label()` → Double/Triple/Quadra/ACE 里程碑
- 26 個遊戲事件 → (音效, VFX, HUD 回饋) 綁定表 + 完整性驗證

## 設計原則

1. **確定性**：所有產生器 seed 驅動 → 相同 seed 產生位元級相同素材
2. **程式即素材**：素材 = 函式/資料定義，可參數化、可組合、可版本控管
3. **遊戲相容**：WAV 直接播放；武器 JSON 可註冊進遊戲武器庫；
   地圖 JSON 可直接載入 `World`；事件綁定表對齊 `server.game` 事件名
4. **自我驗證**：`validate_map` / `validate_balance` / `validate_bindings`
   保證產生器輸出合理

## 整合示範

```bash
python3 scripts/demo_pipeline.py
```
生成 3 張地圖 + 8 把武器 → 載入地圖、註冊武器 → 用生成素材實際跑一局對戰
（閉環驗證：地圖 → 碰撞/視線 → 武器 → 射擊 → Spike → 回合）。
