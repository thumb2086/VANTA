# VANTA 速度驗收報告

**時間**：2026-09-15T23:10:27+0800

## 測試結果

| 測試 | 即時倍率 | 耗時 | 每 tick | 記憶體峰值 | 結果 |
|------|---------|------|---------|-----------|------|
| Rust Selftest | N/A | 106.1ms | N/A | N/A | ✅ |
| Rust Tick Speed (76800 ticks) | 6167.2x | 97.0ms | 1.3µs | 0.0MB | ✅ |
| Rust Multi-Client (10 clients, 5.0s) | N/A | 1.97s | N/A | N/A | ✅ |
| Python Tick Speed (3.0s) | 3.8x | 3.00s | 2078.9µs | 1.4MB | ✅ |

## 詳細

### Rust Selftest
- 結果：✅ vanta_server selftest 全過（移動/射擊/經濟/Spike/購買/拆除/回合）

### Rust Tick Speed (76800 ticks)
- 結果：PASS (目標 ≥500x，實際 6167.2x)

### Rust Multi-Client (10 clients, 5.0s)
- 結果：RTT avg=0.1ms p50=0.1ms p95=0.1ms p99=0.1ms

### Python Tick Speed (3.0s)
- 結果：Python 基線：3.8x 即時

## 驗收標準

- Rust tick 速度 ≥ 500x 即時（128Hz × 500 = 64,000 tick/s）
- 10 客戶端 RTT p99 < 10ms（本機）
- 記憶體 < 50MB/場

## 結論

**全部通過** ✅ — VANTA 伺服器性能達標。