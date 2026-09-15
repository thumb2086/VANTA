# Valorant 版本更新日誌研究：為什麼好玩

> 研究日期：2026-09-15。資料來源：官方 patch notes、VALORANT Wiki、Dot Esports、Hotspawn。
> 目的：萃取「好玩」的設計原則，落地到 VANTA。

## 一、版本年表（Beta → Episode → Season）

| 版本 | 時間 | 頭條內容 |
|------|------|---------|
| Closed Beta (0.47–0.50) | 2020-04～05 | 核心驗證：射擊/技能/經濟循環成立 |
| **Ep1 Act1 (1.0)** IGNITION | 2020-06 | Reyna、Ascent、**Competitive、Spike Rush、投降**、首個 Battle Pass |
| Ep1 Act2 (1.05) | 2020-08 | Killjoy、**Deathmatch**、Guardian 調整 |
| Ep1 Act3 (1.10) | 2020-10 | Skye、Icebox、Act Rank、**Snowball Fight、Night Market**、經濟調整 |
| **Ep2 Act1 (2.0)** FORMATION | 2021-01 | Yoru、Split 重做、Classic 削弱、排行榜 |
| Ep2 Act2 (2.04) | 2021-03 | Astra、Viper 重做、Bucky 削弱 |
| Ep2 Act3 (2.08) | 2021-04 | Breeze、**Replication** 模式 |
| **Ep3 Act1 (3.0)** REFLECTION | 2021-06 | KAY/O、武器價格調整、排位帳號等級門檻 |
| Ep3 Act2 (3.05) | 2021-09 | Fracture、閃光調整、AFK 懲罰 |
| Ep3 Act3 (3.10) | 2021-11 | Chamber（後來證明過強→連續削弱） |
| **Ep4 Act1 (4.0)** DISRUPTION | 2022-01 | Neon、Ares/Guardian buff |
| Ep4 Act2 (4.04) | 2022-03 | **Yoru 大重做**（失敗設計敢砍掉重練） |
| Ep4 Act3 (4.08) | 2022-04 | Fade、Jett dash 調整 |
| **Ep5 Act1 (5.0)** DIMENSION | 2022-06 | Pearl、Split 移出輪換、**地圖輪換制確立** |
| Ep5 Act2/3 | 2022-08～10 | Fracture 重做、Phoenix buff、Harbor |
| **Ep6 (6.0–6.11)** REVELATION | 2023-01～06 | Lotus、**Gekko（Wingman 可安包/拆包）**、Bind 重做 |
| **Ep7 Act1 (7.0)** EVOLUTION | 2023-06 | Deadlock、**Team Deathmatch、Premier 公測** |
| Ep7 Act2 (7.04) | 2023-08 | Sunset、**7.04 大砍（Jett/Raze/Killjoy）** |
| Ep7 Act3 (7.09) | 2023-10 | Iso、Cypher buff、Breeze 重做 |
| **Ep8 Act1 (8.0)** DEFIANCE | 2024-01 | **Outlaw（睽違 4 年的新武器）**、Sage 削弱 |
| Ep8 Act2 (8.05) | 2024-03 | Clove（死後還能放煙——死亡也有參與感） |
| Ep8 Act3 (8.08) | 2024-04 | Abyss（會摔死的地圖——環境擊殺的樂趣） |
| **Ep9 (9.0–9.11)** COLLISION | 2024-06～2025-01 | 主機版、Vyse、Glitch（TDM 地圖）、Regen Shield |
| **S25 Act1 (10.00)** | 2025-01 | **Tejo、Flex 表情小物、自動重賽投票**、賽季制取代 Episode |
| S25 Act2 (10.04) | 2025-03 | **Waylay** |
| S25 Act3 (10.08) | 2025-04 | **贈禮系統**、排位槍枝吊飾 |
| S25 Act4 (11.00) | 2025-06 | **Corrode、UE5 升級**（老遊戲敢換引擎） |
| S25 Act5 (11.04–11.07) | 2025-08～10 | **Veto、Skirmish 新模式、Rank Shields、作弊場 RR 回溯、重播系統 PC 上線(11.06)** |
| S25 Act6 (11.08–11.11) | 2025-10～2026-01 | 槍法精通更新、**Harbor 重做**、充值技能冷卻標準化 |
| **S26 Act1 (12.00/13.00)** | 2026-01 | **Bandit 新手槍**、Breeze 史詩重做、**AR1S 限時模式**、MMR 重做、重播擴展 |
| S26 Act2 | 2026-03 | **Miks、Knockout 模式（殺人救隊友）**、**助攻橫幅進 HUD**、Lotus A 點重做 |
| S26 Act3 | 2026-04 | **Skirmish: Ascension（1v1/2v2 天梯）** |
| S26 Act4 | 2026-06 | **Summit 新地圖** |

## 二、好玩設計原則（萃取 10 條）

### P1. 時間預算分層：永遠有適合你現在的模式
Spike Rush（8–12 分鐘）→ Swiftplay（~15 分鐘）→ Unrated（~30 分鐘）→ Competitive（~40 分鐘），外加 Deathmatch/TDM 純暖槍。
**教訓**：只有 40 分鐘標準賽的射擊遊戲，會把 80% 沒時間的玩家擋在門外。
→ VANTA 落地：Spike Rush + Swiftplay。

### P2. 每回合都有新鮮感：隨機配裝 + 能量球
Spike Rush 每回合全場同隨機槍＋1–5 顆 Powerup Orb（武器升級、金色短槍、治療、刺激、欺敵）。輸贏之外還有「開獎」的樂趣。
→ VANTA 落地：Spike Rush 配裝表 + 簡化版 orbs。

### P3. 失敗也有參與感：助攻、Clove 死後放煙、Knockout 殺人救隊友
S26 把助攻做成 HUD 橫幅；Clove 讓陣亡玩家還能貢獻；Knockout 模式殺人就能救活隊友。**「我雖然死了但我有用」是留存關鍵。**
→ VANTA 落地：助攻系統 + assist banner 事件（目前 assists 欄位存在但永遠是 0——先修這個）。

### P4. 高光時刻要被看見：重播 + 時間軸標記 + Play of the Match
重播是 2020 年許願、2025 年 11.06 才上線的功能——Riot 寧願晚 5 年也要做對。時間軸標記擊殺/死亡/大絕，0.1x–8x 變速。
→ VANTA 落地：Replay MVP 資料層（meta + tick 快照 + 事件 JSONL + 回放 API），對齊既有 REPLAY_SYSTEM_DESIGN.md。

### P5. 每天都有回來的理由：每日/每週任務 + 戰鬥通行證
每 2 個月一個 Act 就換 Battle Pass；每日任務給 XP；Night Market 打折刺激登入。
→ VANTA 落地：每日任務系統（日期種子、進度追蹤、XP 獎勵）。

### P6. 敢於大改：Yoru 重做、Harbor 重做、Breeze 重做、UE5 升級
不好玩的東西不修小數點，直接砍掉重練；連引擎都敢換。**平衡補丁是「調參數」，重做是「承認設計失敗」。**
→ VANTA 落地：本次不重做，但把「模式」做成可插拔配置，方便以後大改。

### P7. 經濟是第二條血條：連敗補償 + Swiftplay 濃縮經濟
1900/2400/2900 連敗補償讓連輸也有翻盤希望；Swiftplay 用固定配給表（800 → 2400+600 → 4250 → 4250 → 5000）壓縮決策但保留買槍樂趣。
→ VANTA 落地：Swiftplay 經濟表（VANTA 標準經濟數值已與官方一致，經核對無需改）。

### P8. 公平感就是好玩：Rank Shields、作弊場 RR 回溯、AFK 懲罰、重賽投票
S25 的 Rank Shields + 作弊對局 RR 回溯，直接修復「輸給掛」的最差體驗。
→ VANTA 落地：本次先做作弊對局標記（anti-cheat 已有框架），RR 回溯記入 ranked 待辦。

### P9. 地圖輪換保鮮：每 Act 輪換 + 限時模式地圖
同樣的槍，在新地圖就是新遊戲。AR1S（全隨機單點）、Snowball Fight（雪球大戰）證明：**限時亂鬥模式是留存神器。**
→ VANTA 落地：模式配置化，為限時模式留接口。

### P10. 槍法手感是 1，其他是 0：命中回饋、擊殺確認、槍聲
所有模式、特務、地圖都建立在「開槍爽」上：準星擴散、命中標記、爆頭音效、擊殺橫幅。VANTA 已有基礎（kill_confirm 音效、hitmarker），保持並在新模式沿用。

## 三、VANTA 落地清單（本 goal 實作）

| # | 功能 | 對應原則 | 驗收 |
|---|------|---------|------|
| 1 | Spike Rush 模式（BO7、隨機同槍、orbs、2 ult 點→改為技能充能） | P1, P2, P9 | `test_fun_modes.py`：配裝表/回合數/全員 spike |
| 2 | Swiftplay 模式（BO9 先到 5、濃縮經濟表） | P1, P7 | `test_fun_modes.py`：回合上限/經濟配給 |
| 3 | 助攻系統（傷害歸因→助攻判定→banner 事件） | P3 | `test_fun_highlights.py`：助攻正確頒發 |
| 4 | Highlights（連殺/殘局/首殺追蹤＋Play of the Match） | P4 | `test_fun_highlights.py`：ACE/殘局/POTM 判定 |
| 5 | 每日任務＋XP | P5 | `test_fun_missions.py`：日期種子/進度/獎勵 |
| 6 | Replay MVP（錄製 meta+ticks+events，回放 API） | P4 | `test_fun_replay.py`：錄→播 round-trip 一致 |

## 四、已核對、無需改的項目
- 武器價格/數值：VANTA `weapons.py` 已與官方一致（Classic 免費、Ghost 500、Sheriff 800、Spectre 1600、Vandal/Phantom 2900、Operator 4700…）
- 標準經濟：800 開局、1900/2400/2900 連敗、3000 勝场、9000 上限——與官方一致
- 128 tick、伺服器權威、OIN  Report（bench 6277x 即時）
