"""M1 移動控制器工廠：Rust/純 Python 選擇邏輯。"""

import os
from unittest.mock import patch

from server.core.movement import MovementConfig, MovementController
from server.core.movement_factory import create_controller


def test_default_returns_python_controller():
    ctrl = create_controller()
    assert isinstance(ctrl, MovementController)


def test_config_passthrough():
    cfg = MovementConfig()
    ctrl = create_controller(cfg)
    assert ctrl.cfg is cfg
    assert ctrl.cfg is not MovementConfig()


def test_vanta_use_rs_without_extension_falls_back_to_python():
    with patch.dict(os.environ, {"VANTA_USE_RS": "1"}, clear=False):
        from server.core import rs_bridge

        ctrl = create_controller()
        if rs_bridge.rs_available():
            assert ctrl.__class__.__name__ == "RustMovementController"
        else:
            assert isinstance(ctrl, MovementController)


def test_vanta_use_rs_rs_bridge_failure_falls_back_to_python():
    with patch.dict(os.environ, {"VANTA_USE_RS": "1"}, clear=False):
        with patch("server.core.rs_bridge.rs_available", return_value=False):
            ctrl = create_controller()
            assert isinstance(ctrl, MovementController)


def test_controller_steps_identically_through_factory():
    a = create_controller()
    b = MovementController()
    from server.core.movement import MoveInput

    for _ in range(10):
        a.step(MoveInput(forward=1.0), 1.0 / 128.0)
        b.step(MoveInput(forward=1.0), 1.0 / 128.0)
    assert (a.pos - b.pos).length() < 1e-12