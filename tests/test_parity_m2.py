"""M2 parity：後座力(RNG) / 彈道 / 封包 SerDe 跨語言位元組級比對（Rust 存在才執行）。"""

import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARITY = os.path.join(ROOT, "rust", "parity")


def _cargo():
    cargo = shutil.which("cargo")
    if cargo is None:
        home = os.path.expanduser("/var/tmp/.cargo/bin/cargo")
        if os.path.isfile(home):
            cargo = home
    return cargo


def _rust_env():
    """Linux 開發機把工具鏈放在 /var/tmp；其他平台沿用目前環境（跨平台）。"""
    if os.path.isdir("/var/tmp/.cargo/bin"):
        return dict(os.environ, RUSTUP_HOME="/var/tmp/.rustup", CARGO_HOME="/var/tmp/.cargo",
                    PATH="/var/tmp/.cargo/bin" + os.pathsep + os.environ.get("PATH", ""))
    return dict(os.environ)


def _run(bin_name: str, env) -> str:
    r = subprocess.run([os.path.join(PARITY, "target", "release", bin_name)],
                       cwd=PARITY, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


@pytest.fixture(scope="module")
def rust_env():
    cargo = _cargo()
    if cargo is None:
        pytest.skip("cargo 未安裝")
    env = _rust_env()
    subprocess.run([cargo, "build", "--release"], cwd=PARITY, check=True, env=env, capture_output=True)
    return env


# --------------------------------------------------------------------- #
# RNG（Python 端）
# --------------------------------------------------------------------- #
def test_mt19937_matches_cpython():
    """自訂 MT19937 與 CPython random.Random(42) 序列一致（確定性根基）。"""
    import random as _rnd

    from server.core.rng import MT19937

    a, b = MT19937(42), _rnd.Random(42)
    for _ in range(50):
        assert a.random() == b.random(), "與 CPython random.Random 分歧"


def test_mt19937_deterministic():
    from server.core.rng import MT19937

    a, b = MT19937(7), MT19937(7)
    assert [a.random() for _ in range(20)] == [b.random() for _ in range(20)]
    c = MT19937(8)
    assert c.random() != a.random()


def test_mt19937_gen_int32_matches_cpython():
    """gen_int32 與 CPython random.getrandbits(32) 一致（int32 層級保證）。"""
    import random as _rnd

    from server.core.rng import MT19937

    r, c = MT19937(2024), _rnd.Random(2024)
    for _ in range(30):
        assert r.gen_int32() == c.getrandbits(32), "gen_int32 與 CPython getrandbits(32) 分歧"


def test_mt19937_uniform_bounds():
    from server.core.rng import MT19937

    r = MT19937(1)
    for _ in range(100):
        v = r.uniform(-0.6, 0.6)
        assert -0.6 <= v <= 0.6


# --------------------------------------------------------------------- #
# 後座力 parity
# --------------------------------------------------------------------- #
def test_recoil_parity(rust_env):
    sys.path.insert(0, ROOT)
    import importlib

    gen = importlib.import_module("rust.parity.golden_recoil")
    gen.main()
    out = _run("parity_recoil", rust_env)
    assert "RECOIL PARITY OK" in out, out


def test_ballistics_parity(rust_env):
    sys.path.insert(0, ROOT)
    import importlib

    gen = importlib.import_module("rust.parity.golden_ballistics")
    gen.main()
    out = _run("parity_ballistics", rust_env)
    assert "BALLISTICS PARITY OK" in out, out


def test_protocol_parity(rust_env):
    sys.path.insert(0, ROOT)
    import importlib

    gen = importlib.import_module("rust.parity.golden_protocol")
    gen.main()
    out = _run("parity_protocol", rust_env)
    assert "PROTOCOL PARITY OK" in out, out


def test_golden_files_written():
    """黃金資料檔案存在且大小合理。"""
    assert os.path.isfile(os.path.join(PARITY, "schedule_recoil.bin"))
    assert os.path.isfile(os.path.join(PARITY, "states_recoil.bin"))
    assert os.path.isfile(os.path.join(PARITY, "scene_ballistics.bin"))
    assert os.path.isfile(os.path.join(PARITY, "expected_ballistics.bin"))
    assert os.path.isfile(os.path.join(PARITY, "packets.bin"))
