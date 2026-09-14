# Characters 目錄

放置角色 .glb 模型檔案。

## 命名規則

| 檔名格式 | 說明 |
|----------|------|
| `char_0_0.glb` | 攻方(team 0) 第 0 槽位 專用模型 |
| `char_1_3.glb` | 守方(team 1) 第 3 槽位 專用模型 |
| `char_0.glb` | 攻方共用模型 |
| `char_1.glb` | 守方共用模型 |
| `char_default.glb` | 所有角色共用模型（最終 fallback） |

## 載入優先順序

1. `char_<team>_<slot>.glb` — 特定槽位
2. `char_<team>.glb` — 隊伍共用
3. `char_default.glb` — 全域共用
4. 若都不存在 → 使用程序化方塊骨架（目前的 fallback）

## 模型要求

- 格式：GLTF/GLB（Godot 原生支援）
- 建議：Mixamo 免費模型（CC0 授權）
- 需包含：Skeleton3D + AnimationPlayer
- 建議動畫：Idle, Run, Walk, Crouch, Jump, Death, Shoot, Reload

## Mixamo 使用方式

1. 前往 https://www.mixamo.com
2. 選擇角色模型 → 下載（格式: FBX, Pose: T-Pose）
3. 用 Blender 匯入 FBX → 匯出為 GLB
4. 放入此目錄

## 動畫名稱對應

PlayerRig 會尋找以下動畫名稱（可在 player_rig.gd 中修改）：

| 動畫名稱 | 觸發條件 |
|----------|----------|
| `Idle` | 靜止站立 |
| `Walk` | 慢速移動（speed < 3） |
| `Run` | 快速移動（speed >= 3） |
| `Crouch` | 蹲伏狀態 |
| `Jump` | 空中 |
| `Death` | 死亡 |
| `Shoot` | 開火（預留） |
| `Reload` | 換彈（預留） |
