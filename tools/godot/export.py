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
    "skins": ("skins", "skins", ".json"),
    "skin_cards": (os.path.join("skins", "cards"), os.path.join("skins", "cards"), ".svg"),
    # vfx2 的三個單檔 JSON（蓝图 / 精靈 / 貼花）；完整資料亦已內嵌在 skins.json
    "vfx2": ("vfx", "vfx", ("blueprints.json", "sprites.json", "decals.json")),
}

# 上一次匯出寫了哪些檔（相對 client/assets 的路徑）。`--clean` 只照這份清單回收，
# 於是「同目錄的手工素材」永遠安全——副檔名不是判斷依據，所有權才是。
MANIFEST = ".export_manifest.json"

# 選配：`tools/cli.py skins --textures` 產出的槍皮貼圖（預設不匯出，
# 客戶端會依同一組常數即時生成；要預先烘焙再加 --textures）
SKIN_TEXTURE_DIR = os.path.join("skins", "textures")


def ensure_generated() -> None:
    """若 tools/assets 不存在，先跑 `python -m tools.cli all`。"""
    if not os.path.isdir(TOOLS_ASSETS):
        print("  [export] tools/assets 不存在 → 執行工具鏈產生…")
        from tools.cli import main as cli_main

        cli_main(["all"])


def _ext_tuple(exts) -> tuple:
    return exts if isinstance(exts, tuple) else (exts,)


def _read_manifest() -> set[str]:
    path = os.path.join(CLIENT_ASSETS, MANIFEST)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, encoding="utf-8") as fh:
            return set(json.load(fh).get("files", []))
    except (OSError, ValueError):
        return set()


def _write_manifest(files: set[str]) -> None:
    payload = {"files": sorted(files), "count": len(files),
               "note": "tools.godot.export 產出清單；--clean 只照此清單回收"}
    write_json(os.path.join(CLIENT_ASSETS, MANIFEST), payload)


def _reclaim_stale(keep: set[str]) -> int:
    """`--clean`：刪掉「上次匯出寫過、這次不再產出」的檔案。

    為什麼不掃副檔名：`client/assets/` 混放者工具鏈不管的素材（手工 MP3、
    `weapons_models/` 的 2048px 貼圖、別人放的 `maps/map_haven.json`、
    `characters/README.md`）。舊實作直接 `shutil.rmtree(CLIENT_ASSETS)`，一次匯出
    就把它們全蒸發。用匯出清單當所有權依據，才能既清掉舊世代素材、
    又不誤殺任何人-work 檔案。
    """
    removed = 0
    for rel in sorted(_read_manifest() - keep):
        path = os.path.join(CLIENT_ASSETS, rel)
        if os.path.isfile(path):
            os.remove(path)
            removed += 1
            imp = path + ".import"
            if os.path.isfile(imp):          # Godot 匯入元資料一起帶走
                os.remove(imp)
    return removed


def _prune_orphan_imports() -> int:
    """來源檔已不存在的 `.import` 元資料一併清掉（Godot 才不會一直重匯入／報錯）。"""
    removed = 0
    for root, _dirs, files in os.walk(CLIENT_ASSETS):
        for name in files:
            if name.endswith(".import"):
                src = os.path.join(root, name[: -len(".import")])
                if not os.path.exists(src):
                    os.remove(os.path.join(root, name))
                    removed += 1
    return removed


def export(dry: bool = False, with_textures: bool = False, clean: bool = False) -> int:
    ensure_generated()
    if not dry:
        os.makedirs(CLIENT_ASSETS, exist_ok=True)

    index: dict[str, list[str]] = {}
    written: dict[str, set[str]] = {}      # 目的目錄 → 這次真的寫出的檔名
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
            written.setdefault(dst_rel, set()).add(f)
            # Godot 資源路徑（res:// 開頭）
            res_path = "res://assets/" + os.path.join(dst_rel, f).replace(os.sep, "/")
            index.setdefault(cat, []).append(res_path)
            total += 1

    # 選配：槍皮貼圖（存在才匯出）
    if with_textures:
        tex_src = os.path.join(TOOLS_ASSETS, SKIN_TEXTURE_DIR)
        if os.path.isdir(tex_src):
            pngs = sorted(f for f in os.listdir(tex_src) if f.endswith(".png"))
            for f in pngs:
                dst = os.path.join(CLIENT_ASSETS, SKIN_TEXTURE_DIR, f)
                if not dry:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(os.path.join(tex_src, f), dst)
                written.setdefault(SKIN_TEXTURE_DIR, set()).add(f)
                index.setdefault("skin_textures", []).append(
                    "res://assets/" + os.path.join(SKIN_TEXTURE_DIR, f).replace(os.sep, "/"))
            total += len(pngs)
            if not dry:
                print(f"  [export] 槍皮貼圖 {len(pngs)} 張（已烘焙，Godot 可直接載入）")

    # 伺服器權威地圖（特戰風格）→ 客戶端優先載入，視覺與碰撞一致
    from server.game.mapdata import default_map
    from tools.maps.export import map_to_dict

    map_rel = os.path.join("maps", "map_default.json")
    if not dry:
        os.makedirs(os.path.join(CLIENT_ASSETS, "maps"), exist_ok=True)
        write_json(os.path.join(CLIENT_ASSETS, map_rel), map_to_dict(default_map()))
    index.setdefault("maps", []).insert(0, "res://assets/" + map_rel.replace(os.sep, "/"))
    total += 1

    # 本次寫出的檔案（相對 client/assets）
    keep: set[str] = set()
    for paths in index.values():
        for rel in paths:
            keep.add(rel[len("res://assets/"):].replace("/", os.sep))
    if not dry:
        if clean:
            removed = _reclaim_stale(keep)
            if removed:
                print(f"  [export] --clean 收回 {removed} 個不再產出的舊素材")
        _write_manifest(keep)
    orphans = 0 if dry else _prune_orphan_imports()

    # asset_index.json
    if not dry:
        with open(os.path.join(CLIENT_ASSETS, "asset_index.json"), "w", encoding="utf-8") as fh:
            json.dump(index, fh, ensure_ascii=False, indent=2)
        note = f"（清除 {orphans} 個孤兒 .import）" if orphans else ""
        print(f"  [export] 匯出 {total} 個素材 → client/assets/ + asset_index.json{note}")
    else:
        print(f"  [export] 計畫匯出 {total} 個素材")
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vanta-godot-export")
    parser.add_argument("--dry", action="store_true", help="只印計畫")
    parser.add_argument("--textures", action="store_true",
                        help="一併匯出已烘焙的槍皮貼圖（tools/assets/skins/textures）")
    args = parser.parse_args(argv)
    export(dry=args.dry, with_textures=args.textures)
    print("完成 ✔ 在 Godot 中開啟 client/project.godot 即可遊玩")
    return 0


if __name__ == "__main__":
    sys.exit(main())
