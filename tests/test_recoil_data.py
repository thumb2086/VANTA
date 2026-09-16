"""track 1「手感三件套」資料契約測試
=====================================
鎖住三件事，讓「手感」不會在之後的重構裡悄悄變樣：

1. **每把槍有自己的後座指紋**（不是只有 6 套 class 圖案），且簽名互不重複。
2. **伺服器的表 = 匯出的 bundle = 客戶端讀的 key**，任何一環走樣就紅燈
   （含 `rust/parity` 那份 VANDAL 常數——它和 Python 必須是同一個數字）。
3. **恢復/換彈語意**：停火會回吐到 0、換彈後图案回到第 1 發；Python 與 Rust 同步。
"""

from __future__ import annotations

import json
import pathlib
import random
import re

import pytest

from server.game.recoil import PATTERNS, RecoilController, SpreadEngine, pattern_for
from server.game.weapon_state import WeaponState
from server.game.weapons import WEAPONS
from tools.weapons.recoil_bundle import build_payload, verify

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLIENT_BUNDLE = ROOT / "client" / "assets" / "recoil" / "recoil.json"
RUST_RECOIL = ROOT / "rust" / "parity" / "src" / "recoil.rs"
RUST_WEAPON_STATE = ROOT / "rust" / "parity" / "src" / "weapon_state.rs"
GD_MODEL = ROOT / "client" / "scripts" / "recoil_model.gd"


# ---------------------------------------------------------------- 1. 每槍指紋 #
def test_every_gun_has_its_own_pattern() -> None:
    """非 melee 武器一律有專屬 RecoilPattern（不是退回 class 退回表）。"""
    missing = [k for k, st in WEAPONS.items()
               if st.wclass != "melee" and PATTERNS.get(k) is None]
    assert not missing, f"這些武器沒有專屬图案：{missing}"
    for k, st in WEAPONS.items():
        if st.wclass == "melee":
            continue
        assert pattern_for(st) is PATTERNS[k], f"{k} 取到的不是自己的图案"


def test_melee_falls_back_to_class_bucket() -> None:
    """刀沒有自己的图案（不該有）：它走 class 退回表，且必須拿得到東西。"""
    knife = WEAPONS["knife"]
    assert knife.wclass == "melee"
    assert PATTERNS.get("knife") is None
    pat = pattern_for(knife)
    assert pat is PATTERNS["semi"] and pat.pitch_deg


def test_signatures_are_unique_across_guns() -> None:
    """指紋＝(pitch 序列, yaw 序列, 保護彈, 恢復參數)；兩把槍完全同形＝抄錯。"""
    seen: dict[tuple, str] = {}
    for k, pat in PATTERNS.items():
        sig = (pat.pitch_deg, pat.yaw_deg, pat.protected_bullets,
               pat.reset_time, pat.recover_rate, pat.random_yaw_scale)
        if k in WEAPONS and WEAPONS[k].wclass == "melee":
            continue
        assert sig not in seen, f"{k} 與 {seen[sig]} 的图案完全相同"
        seen[sig] = k


def test_pattern_shape_rules() -> None:
    """設計原則寫在 recoil.py 的註解裡，這裡把它變成可執行規則。"""
    for k, pat in PATTERNS.items():
        n = len(pat.pitch_deg)
        assert n == len(pat.yaw_deg), f"{k}: pitch/yaw 長度不同"
        assert 1 <= pat.protected_bullets <= n, f"{k}: 保護彈數不合理"
        assert max(pat.pitch_deg) <= 6.0, f"{k}: 單發 pitch 過大"
        assert all(abs(v) <= 3.0 for v in pat.yaw_deg), f"{k}: 單發 yaw 過大"
        # 峰值要在前段：連射是「先最猛再收斂」，越噴越猛是資料寫錯
        peak = max(range(n), key=lambda i: pat.pitch_deg[i])
        assert peak <= max(3, int(n * 0.4)), f"{k}: 峰值落在第 {peak + 1} 發（太晚）"
        # 尾段不該比峰值高
        assert pat.pitch_deg[-1] <= max(pat.pitch_deg) + 1e-9, f"{k}: 尾段未收斂"


def test_spray_length_scales_with_magazine() -> None:
    """全自動（非連發）至少要覆蓋 1/4 彈匣，否則壓槍沒有學習曲線。"""
    for k, st in WEAPONS.items():
        if st.wclass == "melee" or not st.automatic or st.burst > 1:
            continue
        assert len(PATTERNS[k].pitch_deg) >= max(6, int(st.mag_size * 0.25)), k


# ------------------------------------------------------------ 2. 數字不可走樣 #
def test_vandal_and_phantom_numbers_are_frozen() -> None:
    """這兩把的數字是 rust/parity golden 的輸入，改到就等於跨語言比對失效。"""
    v = PATTERNS["vandal"]
    assert v.pitch_deg[:6] == (1.1, 2.0, 2.7, 2.4, 2.0, 1.5)
    assert v.yaw_deg[:6] == (0.0, 0.0, 0.0, 0.35, 0.55, 0.25)
    assert (v.protected_bullets, v.reset_time, v.recover_rate, v.random_yaw_scale) == (6, 0.7, 6.0, 0.6)
    p = PATTERNS["phantom"]
    assert p.pitch_deg[:6] == (0.9, 1.7, 2.2, 2.0, 1.7, 1.3)
    assert p.protected_bullets == 8


def _rust_vandal_field(src: str, field: str) -> list[float]:
    """從 `pub static VANDAL` 區塊取一個欄位（陣列或純數字）。"""
    m = re.search(r"pub static VANDAL[^{]*\{(.*?)\n\};", src, re.S)
    assert m, "rust/parity/src/recoil.rs 裡找不到 pub static VANDAL"
    block = m.group(1)
    arr = re.search(field + r"\s*:\s*&\[(.*?)\]", block, re.S)
    if arr:
        return [float(x) for x in re.findall(r"-?\d+\.?\d*", arr.group(1))]
    num = re.search(field + r"\s*:\s*(-?\d+(?:\.\d+)?)", block)
    assert num, f"VANDAL 區塊找不到欄位 {field}"
    return [float(num.group(1))]


@pytest.mark.skipif(not RUST_RECOIL.exists(), reason="沒有 rust/parity 原始碼")
def test_rust_vandal_constants_match_python() -> None:
    """漂移守門：Rust 那份 VANDAL 必須等於 Python 的 PATTERNS['vandal']。"""
    src = RUST_RECOIL.read_text(encoding="utf-8")
    pat = PATTERNS["vandal"]
    assert _rust_vandal_field(src, "pitch_deg") == pytest.approx(list(pat.pitch_deg))
    assert _rust_vandal_field(src, "yaw_deg") == pytest.approx(list(pat.yaw_deg))
    for field, want in (("protected_bullets", float(pat.protected_bullets)),
                        ("reset_time", pat.reset_time),
                        ("recover_rate", pat.recover_rate),
                        ("random_yaw_scale", pat.random_yaw_scale)):
        got = _rust_vandal_field(src, field)
        assert got[0] == pytest.approx(want), f"{field}: Rust {got} != Python {want}"


@pytest.mark.skipif(not RUST_WEAPON_STATE.exists(), reason="沒有 rust/parity 原始碼")
def test_python_and_rust_recoil_recovery_stay_in_sync() -> None:
    """`aim_*_offset` 必須在兩邊都跟著控制器回吐＋換彈重置——只修一邊就會 parity 分岔。"""
    py = (ROOT / "server" / "game" / "weapon_state.py").read_text(encoding="utf-8")
    rs = RUST_WEAPON_STATE.read_text(encoding="utf-8")
    assert py.count("self.aim_pitch_offset = self.recoil.pitch") == 2   # fire + update
    assert py.count("self.aim_yaw_offset = self.recoil.yaw") == 2
    assert "self.recoil.reset_pattern()" in py
    assert not re.search(r"self\.aim_pitch_offset \+=", py), "Python 又變回只增不減了"
    assert rs.count("self.aim_pitch_offset = self.recoil.pitch;") == 2
    assert rs.count("self.aim_yaw_offset = self.recoil.yaw;") == 2
    assert "self.recoil.reset_pattern();" in rs
    assert "+= p;" not in rs, "Rust 又變回只增不減了"


# ------------------------------------------------------------- 3. bundle 契約 #
def test_payload_passes_validator() -> None:
    assert verify(build_payload()) == []


def test_exported_bundle_is_up_to_date() -> None:
    """client 裡的 bundle 必須等於當下資料表——忘記重跑工具鏈要直接紅燈。"""
    assert CLIENT_BUNDLE.exists(), (
        "缺 client/assets/recoil/recoil.json：請跑 "
        "python3 -m tools.cli recoil && python3 -m tools.godot.export")
    got = json.loads(CLIENT_BUNDLE.read_text(encoding="utf-8"))
    assert got == build_payload(), "bundle 過期（改了資料表但沒重跑 tools.cli recoil）"


def test_bundle_pattern_equals_server_pattern() -> None:
    got = json.loads(CLIENT_BUNDLE.read_text(encoding="utf-8"))
    for key, st in WEAPONS.items():
        if st.wclass == "melee":
            continue
        rec = got["weapons"][key]["recoil"]
        pat = PATTERNS[key]
        assert rec["pitch_deg"] == pytest.approx(list(pat.pitch_deg)), key
        assert rec["yaw_deg"] == pytest.approx(list(pat.yaw_deg)), key
        assert rec["protected_bullets"] == pat.protected_bullets
        assert rec["recover_rate"] == pytest.approx(pat.recover_rate)


def test_gdscript_reads_every_bundle_key() -> None:
    """資料驅動的反向鎖：bundle 加了新 key 但 GDScript 沒讀 → 這裡就要响。"""
    payload = build_payload()
    src = GD_MODEL.read_text(encoding="utf-8")
    keys: set[str] = set()
    for entry in payload["weapons"].values():
        keys |= set(entry)
        keys |= set(entry["recoil"])
    keys |= set(payload["accuracy"])
    allowed_unread = {"version", "note", "unit", "own_pattern"}
    unread = sorted(k for k in keys - allowed_unread
                    if f'"{k}"' not in src and f'"{k}",' not in src)
    assert not unread, f"recoil_model.gd 沒讀這些 key：{unread}"


def test_gdscript_ports_the_two_formulas() -> None:
    """客戶端兩條算式的「結構」要與伺服器一致（growth 上限、落地懲罰、蹲乘 0.7）。"""
    src = GD_MODEL.read_text(encoding="utf-8")
    assert "GROWTH_CAP := 8" in src
    assert "mini(bullet_index, GROWTH_CAP) * spread_per_bullet" in src
    assert "mv *= 0.7" in src
    assert "elif crouching and not airborne" not in src, "ADS 與蹲應疊乘（伺服器是兩個獨立 if）"
    assert "_land_err * (1.0 - since_land / _land_time)" in src
    assert "recover_rate * delta" in src


# ---------------------------------------------------------- 4. 行為（手感本身）#
def _state(key: str) -> WeaponState:
    return WeaponState(WEAPONS[key], random.Random(7))


def _spray(ws: WeaponState, n: int, dt: float = 1.0 / 128.0) -> float:
    t = max(dt, ws.next_fire_time)
    for _ in range(n):
        while t < ws.next_fire_time:
            t += dt
        assert ws.attempt_fire(t)
        ws.update(t, dt)
    return t


def test_recoil_recovers_to_zero_after_stop() -> None:
    """停火 → 累積偏移回吐到 0（舊 bug：只增不減，壓完彈匣就永久歪）。"""
    ws = _state("vandal")
    t = _spray(ws, 12)
    assert ws.aim_pitch_offset > 8.0
    for _ in range(int(6.0 / (1 / 128.0))):
        t += 1 / 128.0
        ws.update(t, 1 / 128.0)
    assert ws.aim_pitch_offset == pytest.approx(0.0, abs=1e-6)
    assert ws.aim_yaw_offset == pytest.approx(0.0, abs=1e-6)


def test_reload_restarts_the_pattern() -> None:
    """換彈完成 → 图案回到第 1 發：「首發最準」是點射流派的根基。"""
    ws = _state("vandal")
    t = _spray(ws, 10)
    assert ws.recoil.bullet_index == 10
    ws.start_reload(t)
    need = WEAPONS["vandal"].reload_time
    for _ in range(int(need / (1 / 128.0)) + 4):
        t += 1 / 128.0
        ws.update(t, 1 / 128.0)
    assert not ws.reloading
    assert ws.recoil.bullet_index == 0
    before = ws.aim_pitch_offset
    _spray(ws, 1)
    # 換彈後第一發的「增量」＝图案第 1 發（不是尾巴的小值）
    assert ws.aim_pitch_offset - before == pytest.approx(PATTERNS["vandal"].pitch_deg[0])
    assert ws.mag == WEAPONS["vandal"].mag_size - 1


def test_gun_specific_kick_differs_between_weapons() -> None:
    """同為ライフル，Vandal 前 5 發就該比 Guardian 猛（不然「每槍獨有的手感」是假的）。"""
    van = sum(PATTERNS["vandal"].pitch_deg[:5])
    gua = sum(PATTERNS["guardian"].pitch_deg[:5])
    assert van > gua * 1.5
    # 狙擊槍單發最猛、恢復慢；手槍恢復快
    assert PATTERNS["operator"].pitch_deg[0] > PATTERNS["vandal"].pitch_deg[0]
    assert PATTERNS["operator"].recover_rate < PATTERNS["vandal"].recover_rate
    assert PATTERNS["sheriff"].recover_rate > PATTERNS["vandal"].recover_rate
    # 大彈匣重武器：yaw 漂移最隨性（難壓）
    assert PATTERNS["ares"].random_yaw_scale > PATTERNS["phantom"].random_yaw_scale


def test_protected_bullets_have_no_random_jitter() -> None:
    """保護彈＝「不疊随机 yaw」：同图案不同種子，前 N 發結果必須完全相同。

    這才是玩家能練的部分：前幾發可預測，尾段交給伺服器的有機抖動。
    """
    for k, pat in PATTERNS.items():
        if pat.random_yaw_scale <= 0.0 or pat.protected_bullets <= 0:
            continue
        outs = []
        for seed in (1, 999):
            c = RecoilController(pat, random.Random(seed))
            row = []
            for i in range(pat.protected_bullets):
                row.append(c.fire(0.01 * i))
            outs.append(row)
        assert outs[0] == outs[1], f"{k}: 保護彈段竟然受種子影響"
        # 超過保護段之後才該出現隨機分量（至少某個種子會不同）
        tail = []
        for seed in (1, 999):
            c = RecoilController(pat, random.Random(seed))
            for i in range(pat.protected_bullets + 6):
                tail.append(c.fire(0.01 * i))
        assert tail[len(tail) // 2 - 1] != tail[-1] or pat.random_yaw_scale == 0.0, \
            f"{k}: 尾段沒有任何隨機性"


@pytest.mark.parametrize("key", ["vandal", "phantom", "operator", "sheriff", "spectre", "ares"])
def test_client_spread_formula_matches_server_engine(key: str) -> None:  # noqa: PLR0913
    """recoil_model.gd 的 spread_deg = SpreadEngine.spread_deg（同 growth 上限/蹲/ADS）。

    這裡用 Python 重寫一遍 GDScript 那三行，確保兩邊公式不會各自漂移。
    """
    st = WEAPONS[key]
    eng = SpreadEngine(random.Random(1))
    for bullets in (0, 3, 8, 15, 40):
        for (mv, ads, crouch) in ((0.0, False, False), (1.8, True, False),
                                   (2.4, False, True), (3.0, True, True)):
            eff = mv
            if ads:
                eff *= st.ads_spread_mult
            if crouch:
                eff *= 0.7
            mine = st.first_shot_accuracy + min(bullets, 8) * st.spread_per_bullet + eff
            server = eng.spread_deg(st, mv, bullets, False, ads, crouch)
            assert mine == pytest.approx(server, abs=1e-9), (key, bullets, mv, ads, crouch)


def test_controller_fire_matches_pattern_then_keeps_last_value() -> None:
    """超出图案長度後沿用最後一發（平台段），不會 index 越界。"""
    pat = PATTERNS["vandal"]
    c = RecoilController(pat, random.Random(3))
    for _ in range(len(pat.pitch_deg)):
        c.fire(0.0)
    before = c.pitch
    c.fire(0.0)
    assert c.pitch - before == pytest.approx(pat.pitch_deg[-1])


def test_settings_names_line_up_across_scripts() -> None:
    """設定面板 → VantaGlobal → HUD 的名字必須一致（靠 grep 釘死，避免「開了沒用」）。"""
    menu = (ROOT / "client" / "scripts" / "settings_menu.gd").read_text(encoding="utf-8")
    glob = (ROOT / "client" / "scripts" / "vanta_global.gd").read_text(encoding="utf-8")
    hud = (ROOT / "client" / "scripts" / "hud.gd").read_text(encoding="utf-8")
    for name in ("recoil_indicator", "crosshair_spread_linked", "crosshair_spread_scale"):
        assert f"var {name}" in menu, f"settings_menu 少了 {name}"
        assert f"var {name}" in glob, f"VantaGlobal 少了 {name}"
        assert f"g.{name} = {name}" in menu, f"settings_menu 沒把 {name} 寫回 VantaGlobal"
        assert f'"{name}"' in hud, f"HUD 沒讀 {name}"
    # HUD 一定要真的用這兩個開關（不是讀了丟著）
    assert "if not spread_linked:" in hud
    assert "if recoil_indicator:" in hud
    # main 必須把模型接給 HUD、並在換槍時換图案
    main = (ROOT / "client" / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert "_ensure_recoil_model(" in main
    assert "hud.set_spread_deg(deg)" in main
    assert "recoil_model.reset_pattern()" in main
