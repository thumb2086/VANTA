# 09 · 槍皮與特效：品質架構（Visual Polish）

> 目標：把「有造型可換」變成「讓人想收集、想在 Armory 裡轉槍看」；
> 同時守住本專案的底線——**伺服器權威、外觀永不進入網路協定、素材由工具鏈產生**。

---

## 1. 為什麼資料驅動（而不是把 PNG 塞進 Repo）

一把槍皮的視覺 = **一組參數**（配色、金屬度、粗糙度、發光強度、磨損、圖案）＋**一段程式**。
因此全鏈路只搬資料，不搬圖檔：

```
tools/skins/patterns.py      14 種可平鋪圖案（carbon/cracks/hex/scales/…）
tools/skins/catalog.py       系列 → 造型 → colorway/fx/升級（140 支 / 14 系列）
tools/skins/emit.py          TEX 常數（貼圖規格）+ compose_maps() → 四通道貼圖
tools/vfx/blueprints.py      58 張分層特效藍圖 + 粒子預設 94 / 精靈 18 / 貼花 14
        │
        ▼  python3 -m tools.cli skins / vfx2
tools/assets/skins/skins.json ──┐
tools/assets/vfx/*.json ────────┤
tools/assets/skin_cards/*.svg ──┘
        ▼  python3 -m tools.godot.export
client/assets/…（目前 131 個）+ asset_index.json + .export_manifest.json
        ▼  執行期
SkinRegistry → ProceduralTexture → SkinMaterial → WeaponFinish → 槍身
                                  ↘ FxManager（開火/命中/擊殺）↗ ScreenFX（創傷相机/閃光/FOV）
```

**匯出器只擁有它寫過的檔案**。`client/assets/` 裡同時放著非工具鏈產出的素材
（手工 MP3、`weapons_models/` 的 2048px 貼圖、`maps/map_haven.json`），所以
`tools/godot/export.py` 預設「只覆蓋、不刪除」；要收回世代更替後的舊素材用
`--clean`，它照 `.export_manifest.json`（上次寫出的清單）精確回收，連帶清掉孤兒
`.import` 元資料。同理，粒子預設**不全部預烘福模擬影格**：只有 `vfx_manager.gd`
直接載入的 9 個會寫出影格檔（94 個全烘 = 24 MB、單檔 145k 行），其餘由 `FxManager`
依參數在執行期生成，`tools.cli vfx --prebake-all` 才產生離線分析用的完整影格。舊實作是一句 `shutil.rmtree(client/assets)`——曾一次蒸發 92 個
MP3 與整包 `weapons_models/`，這條紀律由 `tests/test_godot_export.py` 釘死。

**代價與取捨**：`tools/assets/` 與 `client/assets/skins/textures/` 都在 `.gitignore` 內
（256² 噪訊 PNG × 140 支 ≈ 36 MB，不該進 Git）。要預先烘圖時用
`python3 -m tools.cli skins --textures --texture-size 128`，Godot 端會自動改讀 PNG，
讀不到才即時生成（`ProceduralTexture.textures_for()`）。

---

## 2. 一條不能破的契約：`TEX`

`tools/skins/emit.py::TEX` 是**貼圖演算法的唯一事實來源**；Godot 的
`client/scripts/procedural_texture.gd` 是它的**逐運算式 GDScript 移植**。
兩邊不同步，就會出現「Web 展示很漂亮、遊戲裡很Plain」這種查不出來的爛帳。

契約內容：

| 契約 | 內容 | 守護者 |
|------|------|--------|
| 噪音週期 | `TILE = 8`、`OCTAVES = 4`、`GAIN = 0.5` | `test_noise_primitives_match_constants` + `test_godot_noise_constants_match_python`（直接 grep `.gd`） |
| 圖案函式 | `pat_<name>` 一一对應、簽名 `(size, params)` | `test_godot_implements_every_pattern` |
| 貼圖規格 | `texture_spec` 每個鍵都要被 GDScript 讀取 | `test_godot_reads_every_texture_spec_key` |
| 版本 | `TEX["version"] = 2`；不符時 Godot `push_warning` | 執行期警示 |

**規格 v2 的關鍵修正**：發光（emissive）改為只看**結構脊線**——
先對圖案做 `edge_blur` 次模糊 → 中心差分 → 以 **90 分位數正規化** → 再乘 `emissive_strength`。
舊作法（v1）把高頻細節算進邊緣，結果 `cracks` 有 **91% 的像素飽和成一片燈箱**；
修正後平均亮度落在 0.02–0.27、飽和（>200）像素不到 25%。這條由
`test_emission_hugs_edges_instead_of_flooding` 釘死：`0.01 < 平均亮度 < 0.45` 且飽和比例 `< 0.35`；
`test_standard_skin_does_not_glow` 另外要求預設造型發光全零（不該有免費的燈）。

同理，圖案一律要求**可無縫平鋪**：判準是「接縫處的跳躍 ≤ 內部最大跳躍 × 1.25」，
而不是「跳躍要很小」——方格類圖案（carbon/circuit）天生有大階梯，重點是別比內部更差。
`camo`/`nebula` 的團塊與星點因此改用**環面距離**（`min(|d|, 1-|d|)`）。

---

## 3. 造型不只是顏色

`colorway` 決定的是**材質行爲**：`metalness / roughness / clearcoat / iridescence /
pattern_mix / emissive_strength / rim_color / rim_strength / wear / tint_variance`。

* `wear` 同時攪拌 roughness↑、metalness↓、磨穿露底材（ORM 的 R/G 通道），所以「同一支皮的磨損」是看得出來的。
* `extras[]`（刀刃能量裂縫、鏡片光暈、彈匣發光條…）由 `SkinMaterial` 產生附加混合的發光疊加件；
  升級到更高 `level` 時 `rim` 色會參與外圈色調，光暈才不會一整個等級都是同一色。
* `chroma[]` 是**另一組 colorway**，不是換貼圖：換色時只重組材質，不重算幾何。
* 升級（Radianite）四種 `kind`：`vfx`（特效加料）/ `finish`（材質）/ `banner`（擊殺圖幀）/ `charm`（吊飾），
  在 `upgrades[]` 裡逐級宣告，UI 與實作都讀同一份資料。

---

## 4. 特效（VFX）與手感

`FxManager` 讀 `effects.blueprints`：一張藍圖 = 多個圖層
（`particles / mesh / light / decal / camera / hud / sound`），每層宣告掛點
（`muzzle / eject / tracer / impact / victim / weapon / ground / world / camera / screen`）、
延遲、TTL、縮放與**取自 skin.fx 的顏色鍵**（`color_key: "muzzle_color"` 之類）。
于是「換皮 → 開火特效跟著換」不需要任何手寫對應表；`when_style` / `when_smoke`
讓同一張藍圖依 style 自動增減圖層。

* GL Compatibility 沒有可用的 3D Decal / Bloom → 貼花用**面向相機的四边形**模擬，
  輝光用 **CanvasLayer 疊加**（`screen_fx.gd`）而非 `WorldEnvironment`。
* 開火流程（`main.gd`）：射線命中 → `fx2.fire()` + 命中藍圖 → 雙層合成音 →
  `screen_fx.add_trauma(0.035)`；擊殺 → 擊殺藍圖 + `screen_fx.on_kill()`（暈影、慢速脈衝）。
* `hud.gd` 新增 `hit_marker(color, headshot, scale)` 與
  `show_kill_banner_fx(victim, skin_name, color, frame, level)`；**舊簽名原樣保留**，
  既有測試與呼叫端不破。
* 品質分級 `fx2.quality ∈ {0,1,2}`：剝減粒子數、燈光、鏡頭圖層；由
  `vanta/graphics/high_fx`（`client/project.godot`）控制。

---

## 5. Armory（兵工廠 UI）

`client/armory.tscn` + `client/scripts/armory.gd`（選單左上 🛡 進入）。三欄式：
系列 → 造型清單（卡片顏色由 colorway 直接 `_draw()`，不依賴 SVG import）→ 3D 預覽。

預覽用 `SubViewport`（`own_world_3d`）掛一套獨立的 `WeaponFinish` + `FxManager` + `AudioManager`，
所以**在選單裡試射不會動到對戰狀態**；`Y` 觸發 2.4 秒檢視動畫（傾身、舉槍、慢轉），
`SPACE/T` 試射並打出完整開火特效。

| 鍵 | 動作 | 鍵 | 動作 |
|----|------|----|------|
| `Enter` | 裝備 | `C` | 切換 Chroma |
| `F` | 購買（VP 餘額來自 `SkinProgression`） | `U` | 升級一級（Radianite） |
| `A/D` `←/→` | 換造型 | `W/S` `↑/↓` | 換系列 |
| `Space/T` | 試射 | `Y` | 檢視動畫 |
| `Esc` | 返回主選單 | | |

裝備後 `VantaGlobal.notify_skins_changed()` → 對戰中的 `main.gd` 立即重掛材質
（`skin_revision` 機制），不用重進對戰。

---

## 6. 驗證方式（無 Godot runtime 的環境也能守品質）

* `python3 -m pytest -q tests/test_tools_skins.py` — 78 項：目錄完整性、價格規則
  （`_price_for()` 可重算）、圖案確定性與平鋪、`compose_maps` 通道尺寸、發光分佈、
  磨損對 ORM 的影響、卡片 SVG 可解析、匯出計數，以及**跨語言契約**（grep `.gd`）。
* `python3 -m pytest -q tests/test_tools_vfx_fx.py` — 藍圖圖層/掛點/音效鍵、
  粒子上限（有重力的預設必須真的往下掉）、JSON 與產生器同步、錨點/圖層型別在
  `fx_manager.gd` 都有實作。
* `python3 -m tools.cli all` — 全素材重生 + `manifest`；`tests/test_godot_export.py` 守匯出。
* `client/tests/test_all.gd`（Suite2）把新腳本列入 gdparse/gdlint 清單；本機以
  `gdparse` 逐檔驗證（沙箱無 Godot 執行期）。
* 已知非本任務造成的環境性失敗：UDP bind（PermissionError）、Rust 執行檔、缺 node，
  共 11 項 + 1 error，與基準相同。

---

## 7. 還不做／故意不做

* **不碰二進位協定**：`server/netcode/protocol.py` ⇄ `client/scripts/net_client.gd`
  的位元級對應不變；造型是純客戶端狀態（本機存檔 `user://skin_progression.json`）。
* 不做 PBR 貼圖烘焙管線（無外部依赖）、不引入 Three.js；Web 展示走零依賴 Canvas2D。
* 枪身輪廓只有一份：`client/scripts/weapon_geometry.gd`（20 支槍的零件表），
  視角模型／Armory 預覽／第三人稱／Web 展示都從它派生——避免「四種輪廓各自演化」。
