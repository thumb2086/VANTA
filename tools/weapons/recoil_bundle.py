"""
tools/weapons/recoil_bundle.py — 後座／準度資料匯出
====================================================
把「唯一事實來源」（伺服器的 `RecoilPattern` 表 + 移動準度模型）匯成一份 JSON
給客戶端，讓 **你看到的**（準星擴張、槍身上跳）等於 **你打出去的**（伺服器擴散圓）。

為什麼需要這層：後座與準度是「權威在伺服器」的機制，客戶端不可能收到每發偏移
（協定沒有這個欄位，也不該有——那等於把反作弊交給客戶端）。所以兩邊共用同一份
資料、同一套算式，客戶端只重放「確定性部分」（前 N 發保護彈與花紋本身），
隨機 yaw 由伺服器決定——這與《特戰英豪》的「图案可練、尾段有機」一致。

用法：
    python3 -m tools.cli recoil          # → tools/assets/recoil/recoil.json
"""

from __future__ import annotations

import math
from typing import Any

# 客戶端目前讀取的規格版本；欄位增減時要一起升級（GDScript 會比對並警示）
BUNDLE_VERSION = 1

# 一把槍的「指紋」合法性範圍（超出就代表資料寫錯，而不是「設計大膽」）
PITCH_RANGE = (0.05, 6.0)
RESET_RANGE = (0.2, 2.0)
RECOVER_RANGE = (1.0, 20.0)
YAW_RANGE = (0.0, 3.0)


def _pattern_dict(pat) -> dict[str, Any]:
    return {
        "pitch_deg": [round(float(v), 4) for v in pat.pitch_deg],
        "yaw_deg": [round(float(v), 4) for v in pat.yaw_deg],
        "protected_bullets": int(pat.protected_bullets),
        "reset_time": round(float(pat.reset_time), 4),
        "recover_rate": round(float(pat.recover_rate), 4),
        "random_yaw_scale": round(float(pat.random_yaw_scale), 4),
    }


def build_payload() -> dict[str, Any]:
    """從伺服器資料表產生客戶端 bundle（不含任何只有後端才需要的欄位）。"""
    from server.core.accuracy import AccuracyConfig
    from server.game.weapons import WEAPONS
    from server.game.recoil import PATTERNS, pattern_for

    cfg = AccuracyConfig()
    acc = {
        "max_error_deg_by_class": {k: round(float(v), 4)
                                   for k, v in sorted(cfg.max_error_deg_by_class.items())},
        "walk_error_ratio": round(float(cfg.walk_error_ratio), 4),
        "crouch_error_ratio": round(float(cfg.crouch_error_ratio), 4),
        "airborne_error_ratio": round(float(cfg.airborne_error_ratio), 4),
        "land_error_deg": round(float(cfg.land_error_deg), 4),
        "land_error_time": round(float(cfg.land_error_time), 4),
    }

    weapons: dict[str, Any] = {}
    for key in sorted(WEAPONS):
        st = WEAPONS[key]
        pat = pattern_for(st)
        weapons[key] = {
            "class": st.wclass,
            "automatic": bool(st.automatic),
            "burst": int(st.burst),
            "pellets": int(st.pellets),
            "scoped": bool(st.scoped),
            "fire_rate_rps": round(float(st.fire_rate_rps), 4),
            "mag_size": int(st.mag_size),
            "reload_time": round(float(st.reload_time), 4),
            "first_shot_accuracy": round(float(st.first_shot_accuracy), 4),
            "spread_per_bullet": round(float(st.spread_per_bullet), 4),
            "ads_spread_mult": round(float(st.ads_spread_mult), 4),
            "move_speed_mult": round(float(st.move_speed_mult), 4),
            "recoil": _pattern_dict(pat),
            # 有自己指紋（而不是退回 class 圖案）→ 客戶端可據此決定要不要顯示「可練」提示
            "own_pattern": PATTERNS.get(key) is not None and PATTERNS[key].key == key,
        }

    fallback = {k: _pattern_dict(v) for k, v in sorted(PATTERNS.items()) if k not in WEAPONS}
    return {
        "version": BUNDLE_VERSION,
        "unit": "degree",
        "note": "server/game/recoil.py 與 server/core/accuracy.py 的匯出副本；"
                "不要手改，改資料表後重跑 python3 -m tools.cli recoil",
        "accuracy": acc,
        "weapons": weapons,
        "fallback_patterns": fallback,
    }


def verify(payload: dict[str, Any]) -> list[str]:
    """回傳問題清單（空＝通過）。客戶端載入前也可自行呼叫類似檢查。"""
    from server.game.weapons import WEAPONS

    issues: list[str] = []
    weapons = payload.get("weapons", {})
    if set(weapons) != set(WEAPONS):
        issues.append(f"武器覆蓋不完整：bundle {len(weapons)} vs 資料庫 {len(WEAPONS)}")

    signatures: dict[tuple, str] = {}
    for key, data in sorted(weapons.items()):
        rec = data.get("recoil", {})
        pitch = rec.get("pitch_deg", ())
        yaw = rec.get("yaw_deg", ())
        if not pitch:
            issues.append(f"{key}: 沒有 pitch_deg")
            continue
        for i, v in enumerate(pitch):
            if not PITCH_RANGE[0] <= abs(v) <= PITCH_RANGE[1]:
                issues.append(f"{key}: pitch[{i}]={v} 超出 {PITCH_RANGE}")
        for i, v in enumerate(yaw):
            if abs(v) > YAW_RANGE[1]:
                issues.append(f"{key}: yaw[{i}]={v} 超出 ±{YAW_RANGE[1]}")
        prot = int(rec.get("protected_bullets", 0))
        if not 1 <= prot <= len(pitch):
            issues.append(f"{key}: protected_bullets={prot} 不在 1..{len(pitch)}")
        if len(yaw) and len(yaw) != len(pitch):
            issues.append(f"{key}: pitch({len(pitch)}) 與 yaw({len(yaw)}) 長度不同")
        rt = float(rec.get("reset_time", 0.0))
        rr = float(rec.get("recover_rate", 0.0))
        if not RESET_RANGE[0] <= rt <= RESET_RANGE[1]:
            issues.append(f"{key}: reset_time={rt} 超出 {RESET_RANGE}")
        if not RECOVER_RANGE[0] <= rr <= RECOVER_RANGE[1]:
            issues.append(f"{key}: recover_rate={rr} 超出 {RECOVER_RANGE}")
        peak = max(abs(v) for v in pitch)
        if abs(pitch[-1]) > peak + 1e-9:
            issues.append(f"{key}: 尾段比峰值還大（應該收斂成平台）")
        # 峰值必須在前段（連射是「先最猛、之後收斂」；越噴越猛是資料寫錯）
        split = max(4, int(len(pitch) * 0.4))
        if len(pitch) > split and max(abs(v) for v in pitch[:split]) < \
                max(abs(v) for v in pitch[split:]):
            issues.append(f"{key}: 峰值出現在後段 → 像「越噴越猛」，不符合手感")
        # 真・全自動要有可練的長度（至少 1/4 彈匣）；連發武器打完就停，不適用
        if data.get("automatic") and int(data.get("burst", 1)) <= 1:
            need = max(6, int(data["mag_size"] * 0.25))
            if len(pitch) < need:
                issues.append(f"{key}: 全自動但图案只有 {len(pitch)} 發（需 ≥{need}，"
                              "否則壓槍沒有學習曲線）")
        sig = (tuple(pitch), tuple(yaw), prot, rt, rr)
        if data.get("own_pattern") and sig in signatures:
            issues.append(f"{key} 與 {signatures[sig]} 指紋完全相同")
        signatures[sig] = key

    acc = payload.get("accuracy", {})
    for f in ("walk_error_ratio", "crouch_error_ratio", "airborne_error_ratio"):
        v = float(acc.get(f, -1))
        if not 0.0 <= v <= 2.0:
            issues.append(f"accuracy.{f}={v} 不合理")
    if not 0.0 < float(acc.get("land_error_time", 0)) <= 1.0:
        issues.append("accuracy.land_error_time 需在 0..1s")
    if not 0.0 <= float(acc.get("land_error_deg", -1)) <= 20.0:
        issues.append("accuracy.land_error_deg 不合理")
    if any(not math.isfinite(float(v)) for v in [acc.get("land_error_deg", 0)]):
        issues.append("accuracy 含非有限數值")
    return issues
