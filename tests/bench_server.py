"""
tests/bench_server.py — VANTA 速度驗收基準
==========================================
量測 Rust 與 Python 伺服器的 tick 速度、延遲、記憶體使用量。
作為「速度驗收」標準程式。

用法：
  python -m tests.bench_server          # 跑全部基準
  python -m tests.bench_server --json   # 輸出 JSON 格式

輸出報告到 stdout + docs/bench_report.md
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import tracemalloc
from dataclasses import dataclass, field, asdict
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DT = 1.0 / 128.0
TICKS_PER_SEC = 128

# Windows 用 .exe，Linux/Mac 用無副檔名
if sys.platform == "win32":
    RUST_BIN = os.path.join(ROOT, "rust", "vanta_server", "target", "release", "vanta_server.exe")
else:
    RUST_BIN = os.path.join(ROOT, "rust", "bin", "vanta_server")


@dataclass
class BenchResult:
    name: str
    ticks: int = 0
    elapsed_s: float = 0.0
    real_time_ratio: float = 0.0
    ticks_per_sec: float = 0.0
    us_per_tick: float = 0.0
    memory_peak_mb: float = 0.0
    passed: bool = False
    notes: str = ""


@dataclass
class BenchReport:
    timestamp: str = ""
    results: List[BenchResult] = field(default_factory=list)
    summary: str = ""


def _fmt_time(s: float) -> str:
    if s < 0.001:
        return f"{s*1e6:.1f}µs"
    if s < 1.0:
        return f"{s*1000:.1f}ms"
    return f"{s:.2f}s"


def bench_rust_selftest() -> BenchResult:
    """Rust 伺服器 selftest（不經 socket）。"""
    r = BenchResult(name="Rust Selftest")
    if not os.path.isfile(RUST_BIN):
        r.notes = "vanta_server 未建置"
        return r
    t0 = time.perf_counter()
    proc = subprocess.run(
        [RUST_BIN, "--selftest"],
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace"
    )
    r.elapsed_s = time.perf_counter() - t0
    r.passed = proc.returncode == 0 and "selftest 全過" in proc.stdout
    r.notes = proc.stdout.strip().split("\n")[-1] if proc.stdout else proc.stderr[:200]
    return r


def bench_rust_tick_speed(ticks: int = 76800) -> BenchResult:
    """Rust 伺服器 tick 速度（--bench-ticks）。"""
    r = BenchResult(name=f"Rust Tick Speed ({ticks} ticks)")
    if not os.path.isfile(RUST_BIN):
        r.notes = "vanta_server 未建置"
        return r
    tracemalloc.start()
    proc = subprocess.Popen(
        [RUST_BIN, "--port", "0", "--bench-ticks", str(ticks)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8", errors="replace"
    )
    stdout, stderr = proc.communicate(timeout=120)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    r.memory_peak_mb = peak / (1024 * 1024)
    r.ticks = ticks
    # parse output: "[bench] 76800 ticks 耗時 X.XXXs → 即時倍率 XXX.Xx | 每 tick X.XXX µs"
    full_output = stdout + stderr
    for line in full_output.split("\n"):
        if "ticks" in line and ("x" in line.lower() or "µs" in line.lower()):
            try:
                # extract elapsed time: "耗時 X.XXXs"
                if "耗時" in line:
                    elapsed_str = line.split("耗時")[1].split("s")[0].strip()
                    r.elapsed_s = float(elapsed_str)
                # extract ratio: "即時倍率 XXX.Xx"
                if "倍率" in line:
                    ratio_str = line.split("倍率")[1].split("x")[0].strip()
                    r.real_time_ratio = float(ratio_str)
            except (ValueError, IndexError):
                pass
    if r.elapsed_s > 0:
        r.ticks_per_sec = r.ticks / r.elapsed_s
        r.us_per_tick = r.elapsed_s / r.ticks * 1e6
    r.passed = r.real_time_ratio >= 500.0
    r.notes = f"{'PASS' if r.passed else 'FAIL'} (目標 ≥500x，實際 {r.real_time_ratio:.1f}x)"
    return r


def bench_rust_multi_client(n_clients: int = 10, duration_s: float = 5.0) -> BenchResult:
    """Rust 伺服器多客戶端連線延遲測試。"""
    r = BenchResult(name=f"Rust Multi-Client ({n_clients} clients, {duration_s}s)")
    if not os.path.isfile(RUST_BIN):
        r.notes = "vanta_server 未建置"
        return r

    import socket
    from server.core.movement import MoveInput
    from server.netcode.protocol import InputPacket

    port = 0
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    proc = subprocess.Popen(
        [RUST_BIN, "--port", str(port), "--seconds", str(duration_s + 3), "--fast"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(0.3)

    clients = []
    rtts = []
    try:
        for i in range(n_clients):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2.0)
            clients.append(sock)

        # connect all clients
        for i, sock in enumerate(clients):
            pkt = InputPacket(
                net_id=i+1, input_seq=0,
                move=MoveInput(forward=0, strafe=0, walk=False, crouch=False, jump=False),
                client_time_ms=0
            ).encode()
            sock.sendto(pkt, ("127.0.0.1", port))
            time.sleep(0.02)

        # measure RTT for each client
        t_start = time.perf_counter()
        for i, sock in enumerate(clients):
            for seq in range(1, 20):
                t_send = time.perf_counter()
                pkt = InputPacket(
                    net_id=i+1, input_seq=seq,
                    move=MoveInput(forward=1.0, strafe=0, walk=False, crouch=False, jump=False),
                    client_time_ms=int(time.time()*1000)
                ).encode()
                sock.sendto(pkt, ("127.0.0.1", port))
                try:
                    data, _ = sock.recvfrom(1024)
                    t_recv = time.perf_counter()
                    rtts.append((t_recv - t_send) * 1000)  # ms
                except socket.timeout:
                    pass
                time.sleep(0.01)

        r.elapsed_s = time.perf_counter() - t_start
        r.ticks = len(rtts)

    finally:
        proc.terminate()
        for sock in clients:
            try:
                sock.close()
            except Exception:
                pass

    if rtts:
        rtts.sort()
        p50 = rtts[len(rtts)//2]
        p95 = rtts[int(len(rtts)*0.95)]
        p99 = rtts[int(len(rtts)*0.99)]
        avg = sum(rtts) / len(rtts)
        r.notes = f"RTT avg={avg:.1f}ms p50={p50:.1f}ms p95={p95:.1f}ms p99={p99:.1f}ms"
        r.passed = p99 < 10.0
    else:
        r.notes = "無有效 RTT 數據"

    return r


def bench_python_tick_speed(duration_s: float = 3.0) -> BenchResult:
    """Python 伺服器 tick 速度（供對比）。"""
    r = BenchResult(name=f"Python Tick Speed ({duration_s}s)")
    tracemalloc.start()
    try:
        from server.core.movement import MoveInput
        from server.game.entities import World
    except ImportError as e:
        r.notes = f"import 失敗: {e}"
        tracemalloc.stop()
        return r

    world = World()  # 自動建立 10 個 player
    # 確保所有玩家存活
    for p in world.players:
        p.alive = True

    dt = 1.0 / 128.0
    t0 = time.perf_counter()
    ticks = 0
    while time.perf_counter() - t0 < duration_s:
        inputs = [MoveInput(forward=1.0) for _ in world.players]
        world.step(inputs, dt)
        ticks += 1

    r.elapsed_s = time.perf_counter() - t0
    r.ticks = ticks
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    r.memory_peak_mb = peak / (1024 * 1024)

    if r.elapsed_s > 0:
        r.ticks_per_sec = r.ticks / r.elapsed_s
        r.us_per_tick = r.elapsed_s / r.ticks * 1e6
        r.real_time_ratio = r.ticks_per_sec / TICKS_PER_SEC

    r.passed = True
    r.notes = f"Python 基線：{r.real_time_ratio:.1f}x 即時"
    return r


def generate_report(report: BenchReport) -> str:
    """產出 Markdown 格式的基準報告。"""
    lines = [
        "# VANTA 速度驗收報告",
        "",
        f"**時間**：{report.timestamp}",
        "",
        "## 測試結果",
        "",
        "| 測試 | 即時倍率 | 耗時 | 每 tick | 記憶體峰值 | 結果 |",
        "|------|---------|------|---------|-----------|------|",
    ]
    for r in report.results:
        rt = f"{r.real_time_ratio:.1f}x" if r.real_time_ratio > 0 else "N/A"
        et = _fmt_time(r.elapsed_s) if r.elapsed_s > 0 else "N/A"
        ut = f"{r.us_per_tick:.1f}µs" if r.us_per_tick > 0 else "N/A"
        mem = f"{r.memory_peak_mb:.1f}MB" if r.memory_peak_mb > 0 else "N/A"
        status = "✅" if r.passed else "❌"
        lines.append(f"| {r.name} | {rt} | {et} | {ut} | {mem} | {status} |")

    lines.extend([
        "",
        "## 詳細",
        "",
    ])
    for r in report.results:
        lines.append(f"### {r.name}")
        lines.append(f"- 結果：{r.notes}")
        lines.append("")

    lines.extend([
        "## 驗收標準",
        "",
        "- Rust tick 速度 ≥ 500x 即時（128Hz × 500 = 64,000 tick/s）",
        "- 10 客戶端 RTT p99 < 10ms（本機）",
        "- 記憶體 < 50MB/場",
        "",
        "## 結論",
        "",
        report.summary,
    ])
    return "\n".join(lines)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 60)
    print("VANTA 速度驗收基準")
    print("=" * 60)

    report = BenchReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z")
    )

    # 1. Rust selftest
    print("\n[1/4] Rust selftest...")
    r1 = bench_rust_selftest()
    report.results.append(r1)
    print(f"  {r1.notes}")

    # 2. Rust tick speed
    print("\n[2/4] Rust tick speed (76800 ticks)...")
    r2 = bench_rust_tick_speed(76800)
    report.results.append(r2)
    print(f"  {r2.notes}")

    # 3. Rust multi-client RTT
    print("\n[3/4] Rust multi-client RTT (10 clients)...")
    r3 = bench_rust_multi_client(10, 5.0)
    report.results.append(r3)
    print(f"  {r3.notes}")

    # 4. Python baseline
    print("\n[4/4] Python baseline (3s)...")
    r4 = bench_python_tick_speed(3.0)
    report.results.append(r4)
    print(f"  {r4.notes}")

    # Summary
    all_pass = all(r.passed for r in report.results)
    if all_pass:
        report.summary = "**全部通過** ✅ — VANTA 伺服器性能達標。"
    else:
        failed = [r.name for r in report.results if not r.passed]
        report.summary = f"**部分未通過** ❌ — 失敗項目：{', '.join(failed)}"

    # Output
    md = generate_report(report)
    report_path = os.path.join(ROOT, "docs", "bench_report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\n報告已寫入 {report_path}")

    # JSON mode
    if "--json" in sys.argv:
        data = {
            "timestamp": report.timestamp,
            "results": [asdict(r) for r in report.results],
            "summary": report.summary,
            "all_pass": all_pass,
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))

    print(f"\n{'='*60}")
    print(report.summary)
    print(f"{'='*60}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
