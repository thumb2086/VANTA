# 研究筆記 — 機制數學模型與資料來源

> 本文件彙整實作所需的《特戰英豪》機制數據。**Riot 從未公開精確數值**，
> 以下為社群量測的近似值；所有常數都做成「可調參數」而非寫死，方便日後校正。

## 1. 移動模型 (M1)

| 參數 | 數值 | 來源/說明 |
|---|---|---|
| 跑速（步槍） | ≈ 5.4 m/s | 社群量測；持刀更快（≈6.7），SMG/輕武器更快 |
| 靜步 (Shift) | ≈ 3.8 m/s（≈跑速 ×0.70） | 社群量測 |
| 下蹲 | ≈ 跑速 × 0.43 | 近似 |
| 反切急停 | ≈ 40–50 ms | 對比純摩擦滑停 ≈ 200 ms |
| 落地準度懲罰 | +7° 擴散，持續 0.225 s | 官方 patch note 提及 |

相關連結：
- https://battlepooja.com/movement-guide/ （速度與誤差對照）
- https://valorant.fandom.com/wiki/Weapons （移動懲罰機制描述）

## 2. 射擊與後座力 (M5)

| 參數 | 數值 | 來源/說明 |
|---|---|---|
| 首發精確 | 靜止時首發必定精準命中十字中心 | 社群共識 |
| 固定後座力圖案 | 前 N 發完全確定（Vandal≈6、Phantom≈8 顆「保護彈」），之後 yaw 有機率性偏移 | 社群拆解 |
| 首發誤差 | Vandal 0.25°、Phantom 0.2°（近似） | 社群量測 |
| 擴散成長 | Phantom 前 8 發有保護、第 6 發後總擴散開始變寬 | 社群量測 |
| 後座恢復 | 停火約 0.7 s 後準心回到原點（recovery） | 近似 |

相關連結：
- https://www.switchbladegaming.com/valorant/spray-transfer-guide/
- https://blix.gg/blog/news/valorant/valorant-aim-guide-how-to-control-recoil-and-sharpen-your-accuracy/

## 3. 經濟系統 (M8)

| 事件 | 金額 | 對象 |
|---|---|---|
| 半場開始 | 800 | 全員 |
| 回合勝利 | 3,000 | 勝隊全員 |
| 回合敗北（連敗第 1 場） | 1,900 | 敗隊全員 |
| 回合敗北（連敗第 2 場） | 2,400 | 敗隊全員 |
| 回合敗北（連敗第 3 場起） | 2,900（上限） | 敗隊全員 |
| 擊殺 | 200 | 擊殺者 |
| 安放 Spike | 300 | 攻方全員 |
| 資金上限 | 9,000 | 超過即歸零 |

> 註：部分資料來源列出「存活帶槍獎勵 1,000」，但真實遊戲並無此機制，
> 我們預設關閉（經濟設定中保留欄位以供對照）。

相關連結：
- https://www.switchbladegaming.com/valorant/economy-cheat-sheet/
- https://www.gfinityesports.com/article/valorant-economy-guide-money-explained-resource-weapons-equipment-abilities-pc

## 4. Spike 目標機制 (M9)

| 參數 | 數值 |
|---|---|
| 安放時間 | 4 秒 |
| 拆除時間 | 7 秒 |
| 拆除過半記錄點 | 3.5 秒（可離開再回來繼續） |
| 爆炸倒數 | 45 秒 |
| 爆炸範圍 | 致死半徑 ≈ 25 m（受牆壁阻擋），可調 |

相關連結：
- https://valorfeed.gg/guides/how-long-does-it-take-to-plant-defuse-detonate-spike-valorant
- https://www.gamerevolution.com/guides/655332-valorant-how-long-take-defuse-spike

## 5. 網路 (M2/M3)

| 參數 | 數值 | 說明 |
|---|---|---|
| 伺服器 tick | 128 Hz | 官方宣稱值 |
| 輸入重傳/緩衝 | 客戶端送「淨輸入 + 時間戳」 | 伺服器不信任客戶端狀態 |
| 延遲補償視窗 | 上限 ≈ 250 ms (RTT) | 命中判定回滾到「射擊者看到敵人的過去位置」 |
| 快照 | 128 Hz，delta 壓縮 + 量化 | 減少頻寬 |

相關連結：
- https://nofrag.com/lanalyse-du-netcode-de-valorant-rien-a-signaler/
- https://www.reddit.com/r/programming/comments/ik7hq7/valorants_128tick_servers_riot_games_dev_blog_on/ （Rollback 僅用於命中判定，不解適用於移動）
