# 10. 槍支手感（後座／準度）— gunplay feel

> 目標：把「開槍」從**動畫**變成**可練習的機制**。玩家看到的準星、槍身上跳、
> 收合速度，必須與伺服器判定命中與否用的是同一套數字。

## 為什麼要這一層

`server/game/recoil.py` 是權威：後座決定弹道偏移、`SpreadEngine` 決定擴散圓半徑。
但協定裡**沒有** recoil/spread 欄位（`grep recoil server/netcode/protocol.py` = 0），
也不該有——把偏移交給客戶端等於交出反作弊。所以客戶端只能**重放同一套算式**。

在這一輪之前，客戶端是「憑空猜」：

| 舊行為 | 後果 |
|---|---|
| `hud.spread_angle = minf(spread_angle + 1.5, 5.0)` | 所有槍準星擴張一模一樣，且與真實擴散圓無關 |
| `viewmodel.play_fire(randf_range(0.5, 1.0))` | 槍身抖動是亂數，不是该槍的图案 |
| 只有 6 套 class 級 `RecoilPattern` | Vandal 與 Phantom 手感相同，「练壓槍」沒有意義 |
| `aim_pitch_offset += p` 只增不減（Python/Rust 同） | 壓完一彈匣準線**永久**停在上緣，之後每發都跟著歪 |
| 客戶端只在**點擊**時開火 | 全自動槍要手動狂點才能連射 |

## 資料流（工具鏈是唯一事實來源）

```
server/game/recoil.py (RecoilPattern × 23)        server/core/accuracy.py (AccuracyConfig)
              └────────────┬────────────┘                       │
                 pattern_for(stats) / PATTERNS                   │
                           ▼                                    ▼
              tools/weapons/recoil_bundle.py  build_payload() + verify()
                           │  python3 -m tools.cli recoil        （資料表不合格就中止）
                           ▼
              tools/assets/recoil/recoil.json
                           │  python3 -m tools.godot.export（CATEGORIES["recoil"]）
                           ▼
              client/assets/recoil/recoil.json
                           │
                           ▼
              client/scripts/recoil_model.gd  ← 同一套公式的 GDScript 移植
                           ├── main._refresh_spread() → hud.set_spread_deg(真實擴散圓)
                           ├── main._try_fire()       → viewmodel.play_fire/set_recoil(图案)
                           └── main._pump_autofire()  → automatic / burst 的射速
```

`tools.cli recoil` 會先跑 `verify()`：**資料表本身不合格就不產出**（峰值必須在前 40%、
保護彈不得超過图案長度、全自動图案至少 1/4 彈匣、兩把槍不得同形、數值範圍…).
這一輪它當場抓到 `ghost` 被標成 `automatic` 卻只有 3 發圖案 → 補成 8 發。

## 每把槍的指紋（設計原則）

- **前幾發最猛、之後收斂成平台**：`pitch_deg` 峰值一定落在前 40% 內。
- **保護彈（`protected_bullets`）＝不疊隨機 yaw**：前 N 發只有確定性分量 →
  `tests/test_recoil_data.py::test_protected_bullets_have_no_random_jitter`
  用兩個不同種子跑出相同結果來釘死。（注意：保護彈不等於 `yaw_deg` 前段為 0。）
- **`reset_time` / `recover_rate` 决定點射流派**：Odin/Ares 慢收（3.0/3.4）、
  Sheriff 快收（13）、Operator 4.2° 巨 kick + 2.4° 隨機 yaw + 慢收（5.5）。
- **射速决定图案長度**：20 發（Vandal/Phantom）→ 30 發（Ares/Odin，180/200  rpm）。
- 19/19 非 melee 武器都有**自己**的 `RecoilPattern`；`knife` 走 class 退回表（不該有图案）。
- Vandal／Phantom 的數字**一個字都沒改**：`rust/parity/golden_recoil.py` 用
  `PATTERNS["vandal"]` 產生 golden，改到就等於跨語言位元級比對作廢。

## 換彈與恢復語意

`WeaponState` 現在是這樣，而且 **Python 與 Rust 一字不差**：

```python
self.recoil.fire(now)
self.aim_pitch_offset = self.recoil.pitch   # ← 取控制器累積值（會回吐）
self.aim_yaw_offset   = self.recoil.yaw
...
def update(...):
    self.recoil.update(now, dt)             # 停火 > reset_time → 以 recover_rate 度/秒回吐
    self.aim_pitch_offset = self.recoil.pitch
    ...
    if 換彈完成: self.recoil.reset_pattern()   # 图案回到第 1 發＝「首發最準」
```

實測（`tests/test_recoil_data.py`）：Vandal 連射 12 發 → 累積 8°+；停火 6 秒 → **歸零**；
換彈完成 → `bullet_index == 0`，下一發的**增量**恰為图案第 1 發 1.1°。

## 客戶端只做視覺，不碰瞄準線

**紅線**：不要把 recoil 疊進相機的 `_pitch/_yaw`。伺服器已經把 `aim_*_offset` 疊在
`send_shot(yaw, pitch)` 上，客戶端再疊一次就是 double-count（准星會自己亂跑、
且與命中判定不一致）。所以回饋只走兩條通道：

1. `HUD.set_spread_deg()` → 準星間距 = `rad_to_deg(真實擴散圓) × px_per_deg`
   （`crosshair_spread_scale`，預設 8）；並依狀態畫四角括號：蹲＝綠（准度加成）、
   空中/剛落地＝紅（劣化）。落地懲罰（`land_error_deg 7.0°`，0.225s 線性衰減）
   就在這裡看得見。
2. `WeaponViewModel.set_recoil(pitch, yaw)` → 槍身 kick，比例 `RECOIL_VIS_SCALE = 0.22`
   （17° 噴完 ≈ 3.7° 視角，看得見但不暈）。模型驅動時**關掉**視角自己的 lerp 恢復，
   避免兩套恢復曲線互搶。

`recoil_indicator`（設定面板「後座图案預覽」，預設關）把该槍整串花紋畫在準星上：
已打出的發＝亮點、往後的花紋＝淡線、目前累積偏移（含隨機 yaw）＝橘點、
保護彈剩餘＝綠色光圈。這是練習/訓練場用的教學層，不影響判定。

## 連發（automatic）與連點（burst）

`_pump_autofire()` 依 bundle 的 `fire_rate_rps` 補發；`automatic=False` 就**只發一槍**
（半自動必須放開再按），`burst>1` 在按下時排入 `burst-1` 發。
射速取自同一份資料，而伺服器 `next_fire_time` 以同速限流 → 客戶端不可能超發。
彈匣見底時客戶端直接停（`weapon.mag <= 0`）並清旗標，讓伺服器自己觸發換彈。

## 契約測試（`tests/test_recoil_data.py`，25 條）

| 鎖住什麼 | 測試 |
|---|---|
| 每槍有自己图案、刀走退回表 | `test_every_gun_has_its_own_pattern` / `test_melee_falls_back_to_class_bucket` |
| 图案互不重複、形狀規則、長度隨彈匣 | `test_signatures_are_unique_across_guns` / `test_pattern_shape_rules` / `test_spray_length_scales_with_magazine` |
| Vandal/Phantom 數字不被動到（parity 根基） | `test_vandal_and_phantom_numbers_are_frozen` |
| Rust `VANDAL` 常數 == Python 表 | `test_rust_vandal_constants_match_python` |
| Python ⇄ Rust 恢復/換彈語意同步 | `test_python_and_rust_recoil_recovery_stay_in_sync` |
| 工具鏈驗證器通過、bundle 未過期 | `test_payload_passes_validator` / `test_exported_bundle_is_up_to_date` |
| 匯出值 == 伺服器表 | `test_bundle_pattern_equals_server_pattern` |
| **GDScript 必讀每個 key**（加欄位就紅燈） | `test_gdscript_reads_every_bundle_key` |
| 兩條公式的結構移植正確 | `test_gdscript_ports_the_two_formulas` / `test_client_spread_formula_matches_server_engine`（6 把槍 × 5 個連射段 × 4 種狀態逐位比對 `SpreadEngine`） |
| 手感行為（回吐、換彈重置、槍間差異） | `test_recoil_recovers_to_zero_after_stop` / `test_reload_restarts_the_pattern` / `test_gun_specific_kick_differs_between_weapons` |

Godot 端另有 `client/tests/test_all.gd::_run_recoil_bundle_check()`：載入 bundle、
图案單調上升、停火完全恢復、移動準度排序（蹲 < 跑 < 空中）、連射準星必須擴張。

## 已知取捨

- 隨機 yaw 由伺服器決定，客戶端**視覺**用了自己的 RNG → 尾段的左右抖動「看起來有」
  但與命中不同相；這是 VALORANT 式設計（图案可練、尾段有機），代價是客戶端無法
  100% 重現尾段。準星不含隨機分量，顯示的是可練的包絡線。
- 客戶端用 `Time.get_ticks_msec()` 當時鐘，與伺服器 tick 有單程延遲差 → kick 相位
  可能差 1 發以內；判定不受影響（偏移由伺服器自己算）。
- 協定未變（0 欄位增減）：`tests/test_godot_protocol_parity.py`、`test_parity_m2.py`
  仍全綠。
- `main.gd` 已超 `gdlint` 的 `max-file-lines`（遷移前就 1003 行）；本輪沒有讓它變成
  另一類問題，新增的只有 `class-definitions-order`（本 repo 既有風格，共 18/6 條基線）。

## 下一步（尚未做）

- 把 `first_shot_accuracy` 的「首發最準」在訓練場做成計分（10 發計分板）。
- 角色補到 4 顆技能 + 終點球充能（要碰 snapshot/event 協定，需先定協定改法）。
- 聲音材質／ping 通訊（track 2）。
