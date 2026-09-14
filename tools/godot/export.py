"""
tools/godot/export.py — 工具鏈 → Godot 客戶端 素材匯出
======================================================
把 tools/assets/ 的產物複製/整理到 client/assets/，
並寫出 asset_index.json（Godot 客戶端載入素材的索引）。

用法：
    python -m tools.godot.export            # 匯出全部（若缺素材先自動產生）
    python -m tools.godot.export --dry      # 只印計畫
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from tools.schema import write_json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS_ASSETS = os.path.join(ROOT, "tools", "assets")
CLIENT_ROOT = os.path.join(ROOT, "client")
CLIENT_ASSETS = os.path.join(CLIENT_ROOT, "assets")

# 類別 → (來源子目錄, 目的子目錄, 副檔名)
CATEGORIES = {
    "sfx": ("sfx", "sfx", (".wav", ".mp3")),
    "bgm": ("bgm", "bgm", ".wav"),
    "bgm_meta": ("bgm", "bgm", ".json"),
    "maps": ("maps", "maps", ".json"),
    "weapons": ("weapons", "weapons", ".json"),
    "vfx_particles": (os.path.join("vfx", "particles"), os.path.join("vfx", "particles"), ".json"),
    "vfx_svg": (os.path.join("vfx", "svg"), os.path.join("vfx", "svg"), ".svg"),
    "agents": ("agents", "agents", ".json"),
    "agent_portraits": (os.path.join("agents", "portraits"), os.path.join("agents", "portraits"), ".svg"),
    "fx": ("fx", "fx", ".json"),
}


def ensure_generated() -> None:
    """若 tools/assets 不存在，先跑 `python -m tools.cli all`。"""
    if not os.path.isdir(TOOLS_ASSETS):
        print("  [export] tools/assets 不存在 → 執行工具鏈產生…")
        from tools.cli import main as cli_main

        cli_main(["all"])


def export(dry: bool = False) -> int:
    ensure_generated()
    if not dry:
        shutil.rmtree(CLIENT_ASSETS, ignore_errors=True)
        os.makedirs(CLIENT_ASSETS, exist_ok=True)

    index: dict[str, list[str]] = {}
    total = 0
    for cat, (src_rel, dst_rel, exts) in CATEGORIES.items():
        src = os.path.join(TOOLS_ASSETS, src_rel)
        if not os.path.isdir(src):
            continue
        exts = exts if isinstance(exts, (tuple, list)) else (exts,)
        files = sorted(f for f in os.listdir(src) if f.endswith(exts))
        for f in files:
            dst = os.path.join(CLIENT_ASSETS, dst_rel, f)
            if dry:
                print(f"  [plan] {cat}: {f}")
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(src, f), dst)
            # Godot 資源路徑（res:// 開頭）
            res_path = "res://assets/" + os.path.join(dst_rel, f).replace(os.sep, "/")
            index.setdefault(cat, []).append(res_path)
            total += 1

    # 伺服器權威地圖（特戰風格）→ 客戶端優先載入，視覺與碰撞一致
    from server.game.mapdata import default_map
    from tools.maps.export import map_to_dict

    map_rel = os.path.join("maps", "map_default.json")
    if not dry:
        os.makedirs(os.path.join(CLIENT_ASSETS, "maps"), exist_ok=True)
        write_json(os.path.join(CLIENT_ASSETS, map_rel), map_to_dict(default_map()))
    index.setdefault("maps", []).insert(0, "res://assets/" + map_rel.replace(os.sep, "/"))
    total += 1

    # asset_index.json
    if not dry:
        with open(os.path.join(CLIENT_ASSETS, "asset_index.json"), "w", encoding="utf-8") as fh:
            json.dump(index, fh, ensure_ascii=False, indent=2)
        print(f"  [export] 匯出 {total} 個素材 → client/assets/ + asset_index.json")
    else:
        print(f"  [export] 計畫匯出 {total} 個素材")
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vanta-godot-export")
    parser.add_argument("--dry", action="store_true", help="只印計畫")
    args = parser.parse_args(argv)
    export(dry=args.dry)
    print("完成 ✔ 在 Godot 中開啟 client/project.godot 即可遊玩")
    return 0


if __name__ == "__main__":
    sys.exit(main())
