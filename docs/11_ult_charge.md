# 11. 終點球充能（X 槽）— ultimate charge economy

> track 1 第 3 件。重點不是「多一颗技能」，而是**讓終極技有代價**：
> 沒打死人、沒佔點，就開不下去；開完歸零，得再掙。

## 現況盤點（先修正一條舊結論）

之前的差距分析寫「每人 2 顆技能、無終點球」——**那句不準確**：
`server/game/abilities.py::AGENTS` 裡 10 個命名角色早就有 **C/Q/E/X 四槽**，
第 4 槽就是終極技（`ThrownKnifeAbility`＝Jett 刃暴、`ResurrectionAbility`＝Sage 復活、
`OrbitalStrikeAbility`＝Brimstone 天火…）。真正缺的是：

1. **沒有充能經濟**：X 跟小技能一樣免費，開完就走冷卻 → 沒有「這回合要省著用」的決策。
2. **協定沒帶技能狀態**：`0x07 ABILITY_STATE` 只有 4 個冷卻秒，客戶端不知道使用次數、
   更不知道終點球進度 → HUD 那條技能條是裝飾。
3. **通用原型/產生器只有 3 招**：`tools/agents/generator.py` 匯出的 roster 是
   `flash/frag/smoke` 三格，跟命名角色不同形。

## 充能規則（權威在伺服器）

| 來源 | 點數 | 常數 |
|---|---|---|
| 擊殺 | +2 | `ULT_POINTS_KILL`（`server/game/entities.py`）|
| 助攻（≥25 傷害的同隊非兇手）| +1 | `ULT_POINTS_ASSIST` |
| Spike 安放 | +1（只給安放者）| `ULT_POINTS_SPIKE` |
| Spike 拆除 | +1（只給拆除者）| `ULT_POINTS_SPIKE` |
| 回合敗北 | +1（敗方每人）| `ULT_POINTS_ROUND_LOSS` |

- 上限 `ULT_MAX_POINTS = 8`，**跨回合保留**（贏了不清零，死了也不清零）。
- 每颗終點球有 `ult_cost`（多數 8，Yoru/Sova/Omen/Brim/Kayo 系為 7）→ 滿 cost 才能放。
- 放完 `ult_points = 0`（溢充不保留）。
- 只有 `IAbility.is_ultimate = True` 的招生效 → **AI 用的通用原型不受影響**
  （`assault/sentinel/duelist/controller` 的 slot3 是普通招，不需要 8 點）。
- Spike Rush 的 `refill()` 視同直接充滿。

## 傳輸：為什麼放 0x07 而不是塞進 Snapshot

你選的是「加進 snapshot 的玩家欄位」；實作上选了**同類但更合適**的週期狀態封包：
`AbilityStatePacket`（0x07）已經是「伺服器每秒廣播的技能狀態」，而 `SnapshotPacket`
是 20Hz 命中/預測熱路徑（270B，且被 `rust/parity` 的 golden 鎖死）。把充能塞進
snapshot 會讓每 tick 每人多 2B、還要重生成 Rust golden；放 0x07 則：

- 延遲最多 1 秒（終點球進度本來就是慢變量）
- **Rust 端 0 變動**（`grep 0x07 rust/` 零命中 → 不在位元組級 parity 範圍內）
- 丟包只延遲更新，不會錯值（狀態式而非事件式）

每人 8 bytes（`ABILITY_STATE_ENTRY_SIZE`）：

```
+0..3  四槽冷卻（0.1s 解析度，最大 25.5s）      ← 舊版語意完全不變
+4     終點球點數 0..15
+5     終點球所需點數（0 = 這角沒有終點球）
+6     各槽剩餘使用次數，2 bits/槽（Q0 E1 C2 X3）
+7     旗標：bit0 終點球就緒、bit1 技能被壓制（KAY/O）
```

整包 `6 + 10×8 = 86B`（舊 46B）。`SNAPSHOT_PACKET_SIZE` 仍是 270B，
`tests/test_ult_charge.py::test_snapshot_hot_path_untouched` 就是釘這一点的。

## 這輪順手修掉的兩個真 bug

**(1) 強化技完全繞過使用次數／冷卻**
`AbilitySystem.cast()` 先試 `_ENHANCED_DISPATCH`（Jett 的 cloudburst/tailwind/blade storm、
Sage 的四招、Brimstone 的四招），那條路徑直接 `charges_left -= 1` 而**從不檢查**
`AbilitySlot.can_cast()` → 這些角色的強化技可以無限施放、也不受終點球門控。
修法：把閘門提到函式開頭統一檢查（`tests/test_agent_abilities.py` 34 項全過，
其中 10 處測試現在要先 `_arm_ult()` 才放得出去，正是門生效的證明）。

**(2) 新增音效會改到鄰居的位元組**
`cmd_sfx` 依 key 排序產生、全部共用同一條 `_rng` 隨機流。我把 `ult_*` 插在
`ability_cast` 前後時，**字母序在後的 `venom_shot.wav` 跟著變了**。修法：新鍵一律
附加在註冊表尾端，且這兩個函式自備 `random.Random(seed)`（不吃全域流）。
這是可重現性的契約，`test_ult_charge.py` 有對應斷言註解說明。

## 客戶端

- `net_client.gd::_parse_ability_state`：8 bytes/人 → `ability_cooldowns` /
  `ability_charges` / `ability_ult`（`{points, cost, ready, blocked}`）。
- `main.gd`
  - `_sync_ult()`：把权威值推給 HUD；`ready` 的**上升沿**才播就緒回饋
    （`fx2.play("ult_ready")`，藍圖自帶 `ult_ready_chime` 音效；沒有 fx2 才退回純音效）。
  - `_try_cast_ult()`：未就緒 → `ui_error` + `終點球尚未就緒 5 / 8`，**不發包**；
    就緒 → 發包 + `ult_cast` 藍圖（衝擊波＋環＋光）+ 鏡頭 `add_trauma(0.22)`。
  - `_cast_ability()`：Q/E/C 的提示改用真實剩餘次數（`技能 E 發動（剩 1）`），
    沒次數時直說「沒有可用次數」而不是假稱成功。
  - 最大冷卻不再寫死 `[10,10,0,0]`，改由封包第一個觀測到的冷卻值推得。
- `hud.gd`：X 槽不畫「OK」，改畫 `ult_cost` 個充能格（已填 = 琥珀色），
  就緒時整格外框呼吸發光；其他槽上方畫使用次數點點；被壓制時整條蓋紫。
- 素材：`tools/sfx/synth.py` 新增 `ult_ready_chime`（0.5s 三音上行鐘聲）、
  `ult_cast`（0.75s 低頻軀體 + 2.1kHz 閃音）；`tools/vfx/blueprints.py` 新增
  `ult_ready`（shield_ring + 金光）、`ult_cast`（spike_shockwave + 大環 + 強光），
  藍圖 58 → 60。

## 產生器（程序化角色）

`tools/agents/generator.py`：`ULT_POOL`（刃暴/猎魂之怒/震地/奔流光矛/毒蝰之巢，
cost 7-8）→ 每個定位有 `ults` 池，匯出的 `kit` 變成 4 格，另有
`slots: ["C","Q","E","X"]` 與 `ultimate: {key,label,cost}`；`validate_agent()`
把「四槽 + 第 4 槽必須是終點球 + cost ∈ 6..9」變成硬契約。
`register_agent()` 產出的技能組因此自動受充能門控（类别本身带 `is_ultimate`）。

> 舊的 `client/assets/agents/*.json`（不同種子/批次的 legacy roster）仍是 3 格，
> 客戶端 `agent_gallery.gd` 依陣列長度畫，混用不會壞；要刷新就跑
> `python3 -m tools.cli agents --count N --seed S`。

## 契約測試（`tests/test_ult_charge.py`，17 項）

門控（未滿不能放/放完歸零/溢充不保留/上限 8）、來源常數 (2,1,1,1)、
`_on_player_killed` 實際給分、非終點球槽不受閘、原型無終點球、
命名角色恰一顆終極技且在 index 3、`wire_tuple` 佈局逐欄、封包 round-trip 10 人對齊、
解碼器對壞包安全、**GDScript 解析器逐運算式比對**、HUD/main 名稱對齊、
sfx 鍵註冊、波形包絡（用 RMS 驗，不靠聽）。

## 已知取捨／後續

- 終點球 HUD 只顯示自己那份（封包有 10 人的狀態，隊友的就緒動畫留給下一輪）。
- 終點球目前沒有「開場 cinematics」或角色專屬施放动作；`ult_cast` 藍圖是通用的
  （藍圖可依皮肤 `fx.style` 再做風格化分層，資料結構已支援 `when_style`）。
- 語音播報（「X 已就緒」VO）尚未接：需先在 `tools/sfx` 加 VO 通道（track 2）。
- `cmd_sfx` 的全域隨機流仍是共用的（這次靠「新鍵放尾端 + 自備 rng」繞過）；
  根治法是每鍵 `reseed(key)`，但那會一次性改掉全部 48 個 wav 的位元組，留給专门一輪。
