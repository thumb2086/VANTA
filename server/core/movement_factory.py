"""
server/core/movement_factory.py — 移動控制器工廠
=================================================
選擇實作：Rust 擴展（VANTA_USE_RS=1 或預設可用時）或純 Python。
兩者位元組級一致（parity 鎖定）→ 換核心不改變行為。
"""

from __future__ import annotations

import os

from server.core.movement import MovementConfig, MovementController


def create_controller(cfg: MovementConfig | None = None, ground_y: float = 0.0):
    """建立移動控制器。

    預設：純 Python（效能實測：細粒度單步跨 pyo3 邊界無淨增益，見 docs/07 M3）。
    可選：VANTA_USE_RS=1 強制 Rust 單步（正確性雙軌驗證用）。
    高效能路徑：RustMovementBatch（批次一次跨邊界）——見 docs/07 M4 路線。
    """
    if os.environ.get("VANTA_USE_RS") == "1":
        try:
            from server.core import rs_bridge

            if rs_bridge.rs_available():
                return rs_bridge.RustMovementController(cfg, ground_y)
        except Exception:
            pass
    return MovementController(cfg, ground_y)
