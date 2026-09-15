"""
tools/cli.py — VANTA 素材產生工具鏈 CLI
=======================================
用法：
    python -m tools.cli init                    # 建立 assets/ 目錄
    python -m tools.cli sfx                     # 產生全部音效 WAV
    python -m tools.cli vfx                     # 產生粒子定義 + SVG 貼圖
    python -m tools.cli vfx2                    # 分層特效蓝图（v2）
    python -m tools.cli skins                   # 槍皮目錄 + 系列卡
    python -m tools.cli weapons --count 12      # 產生 seed 武器 JSON
    python -m tools.cli maps --seeds 1 2 3      # 產生程序化地圖 JSON
    python -m tools.cli fx                      # 產生擊殺特效 + 事件綁定表
    python -m tools.cli all                     # 全部產生 + manifest
    python -m tools.cli manifest                # 重新整理清單
"""

from __future__ import annotations

import argparse
import os
import sys

from tools.schema import AssetManifest, write_json

ASSETS_ROOT = os.path.join(os.path.dirname(__file__), "assets")


def _paths(*parts: str) -> str:
    return os.path.join(ASSETS_ROOT, *parts)


# --------------------------------------------------------------------- #
def cmd_sfx() -> AssetManifest:
    from tools.sfx import synth
    from tools.sfx.audio import write_wav

    synth.reseed(0)
    man = AssetManifest()
    for name, fn in sorted(synth.SFX_REGISTRY.items()):
        path = _paths("sfx", f"{name}.wav")
        write_wav(path, fn())
        man.add("sfx", os.path.relpath(path, ASSETS_ROOT))
    print(f"  [sfx] 產生 {len(synth.SFX_REGISTRY)} 個音效 → assets/sfx/")
    return man


def cmd_bgm(genres: list[str] | None = None) -> AssetManifest:
    """產生程序化 BGM（每種風格一個，主風格多 seed 變體）。"""
    from tools.sfx import bgm
    from tools.sfx.audio import write_wav

    man = AssetManifest()
    genres = genres or ["combat", "tension", "menu", "victory", "defeat"]
    seeds = {"combat": 11, "tension": 21, "menu": 31, "victory": 41, "defeat": 51}
    for g in genres:
        seed = seeds.get(g, 42)
        samples, meta = bgm.render_genre(seed=seed, genre=g)
        wav_path = _paths("bgm", f"{meta['name']}.wav")
        json_path = _paths("bgm", f"{meta['name']}.json")
        write_wav(wav_path, samples)
        write_json(json_path, meta)
        man.add("bgm", os.path.relpath(wav_path, ASSETS_ROOT))
        man.add("bgm_meta", os.path.relpath(json_path, ASSETS_ROOT))
        print(f"  [bgm] {meta['name']}  {meta['bpm']}BPM {meta['scale']}  "
              f"{meta['duration_sec']}s (loop@{meta['loop_start_sec']}s)")
    return man


def cmd_agents(count: int = 8, seed: int = 100) -> AssetManifest:
    """產生程序化角色（定義 JSON + 肖像 SVG）。"""
    from tools.agents.generator import generate_batch, validate_agent
    from tools.agents.portrait import write_portrait

    man = AssetManifest()
    agents = generate_batch(seed=seed, count=count)
    for a in agents:
        d = a.to_dict()
        issues = validate_agent(d)
        if issues:
            print(f"    ! 驗證警告 {a.key}: {issues}")
        json_path = _paths("agents", f"{a.key}.json")
        write_json(json_path, d)
        man.add("agents", os.path.relpath(json_path, ASSETS_ROOT))
        svg_path = _paths("agents", "portraits", f"{a.key}.svg")
        write_portrait(svg_path, d)
        man.add("agent_portraits", os.path.relpath(svg_path, ASSETS_ROOT))
        print(f"  [agents] {a.codename:<10} {a.role_label:<4} {a.role:<12} "
              f"技能={'/'.join(a.kit)}  主色{a.colors['primary']}")
    return man


# 只有這幾個「舊版客戶端 `vfx_manager.gd` 直接讀檔」的預設需要預烘福影格。
# 其餘預設由 FxManager 依參數在執行期生成：全部預烘焙 = 94 份模擬影格傾印
# （實測 24 MB、單檔 145k 行），既撐爆 repo 也拖慢工具鏈，而且每次改參數都要重跑。
CLIENT_PREBAKED = frozenset({
    "blood", "explosion_debris", "hit_marker", "kill_confirm", "muzzle_flash",
    "shell_casing", "smoke_puff", "spark", "tracer",
})


def cmd_vfx(prebake_all: bool = False) -> AssetManifest:
    from tools.schema import write_json
    from tools.vfx import particles, svg

    man = AssetManifest()
    names = (sorted(particles.PRESETS) if prebake_all
             else sorted(CLIENT_PREBAKED & set(particles.PRESETS)))
    out_dir = _paths("vfx", "particles")
    os.makedirs(out_dir, exist_ok=True)
    keep = {f"{n}.json" for n in names}
    for stale in os.listdir(out_dir):          # 此目錄為工具鏈獨有：先收回上次產物
        if stale.endswith(".json") and stale not in keep:
            os.remove(os.path.join(out_dir, stale))
    for name in names:
        em = particles.PRESETS[name]
        path = _paths("vfx", "particles", f"{name}.json")
        # indent=None：影格傾印是純機器輸出（單檔可達 3 萬行），壓成一行才不會
        # 每次參數微調都在 diff 裡刷掉幾萬行——真正該被審閱的是上面的 emitter 參數。
        write_json(path, {"emitter": particles.to_dict(em),
                          "frames": particles.animate_frames(em, seed=0)}, indent=None)
        man.add("vfx_particles", os.path.relpath(path, ASSETS_ROOT))
    # SVG 貼圖
    for name, fn in sorted(svg.VFX_SVG_REGISTRY.items()):
        path = _paths("vfx", "svg", f"{name}.svg")
        svg.write_svg(path, fn({}))
        man.add("vfx_svg", os.path.relpath(path, ASSETS_ROOT))
    print(f"  [vfx] 粒子預烘福 {len(names)}/{len(particles.PRESETS)} 個預設"
          f"（其餘執行期生成）+ {len(svg.VFX_SVG_REGISTRY)} 個 SVG 貼圖")
    return man


def cmd_vfx2() -> AssetManifest:
    """產生 v2 素材：分層蓝图 + 精靈/貼花定義 + 槍皮目录。"""
    from tools.schema import write_json
    from tools.vfx.blueprints import BLUEPRINTS
    from tools.vfx.decals import DECALS
    from tools.vfx.sprites import SPRITES

    man = AssetManifest()
    p1 = _paths("vfx", "blueprints.json")
    write_json(p1, {"version": 2, "count": len(BLUEPRINTS),
                    "blueprints": [BLUEPRINTS[k] for k in sorted(BLUEPRINTS)]})
    man.add("vfx_blueprints", os.path.relpath(p1, ASSETS_ROOT))
    p2 = _paths("vfx", "sprites.json")
    write_json(p2, {"sprites": [SPRITES[k] for k in sorted(SPRITES)]})
    man.add("vfx_sprites", os.path.relpath(p2, ASSETS_ROOT))
    p3 = _paths("vfx", "decals.json")
    write_json(p3, {"decals": [DECALS[k] for k in sorted(DECALS)]})
    man.add("vfx_decals", os.path.relpath(p3, ASSETS_ROOT))
    print(f"  [vfx2] 產生 {len(BLUEPRINTS)} 個分層特效蓝图 + "
          f"{len(SPRITES)} 個精靈 + {len(DECALS)} 個貼花")
    return man


def cmd_skins(textures: bool = False, texture_size: int = 256) -> AssetManifest:
    """產生槍皮目錄（skins.json）＋系列卡（SVG）＋選用工欲程序化貼圖。"""
    from tools.skins import emit as skins_emit
    from tools.skins.catalog import validate_catalog
    from tools.vfx.blueprints import validate_blueprints
    from tools.vfx.particles import validate_presets

    issues = validate_catalog() + validate_presets() + validate_blueprints()
    for i in issues:
        print(f"    ! 資料問題 {i}")
    if issues:
        print(f"  [skins] 資料問題 {len(issues)} 項（仍繼續輸出，以免阻斷管線）")

    out = skins_emit.emit(_paths("skins"), textures=textures, texture_size=texture_size)
    man = AssetManifest()
    rel = os.path.relpath(out["catalog"], ASSETS_ROOT)
    man.add("skins", rel)
    for c in out["cards"]:
        man.add("skin_cards", os.path.relpath(c, ASSETS_ROOT))
    for t in out["textures"]:
        man.add("skin_textures", os.path.relpath(t, ASSETS_ROOT))
    extra = f"，{len(out['textures'])} 張貼圖" if out["textures"] else ""
    print(f"  [skins] {out['collections']} 個系列 / {out['skins']} 個造型 + "
          f"{len(out['cards'])} 張系列卡{extra}")
    return man


def cmd_weapons(count: int = 12) -> AssetManifest:
    from server.game.weapons import WEAPONS
    from tools.schema import write_json
    from tools.weapons.generator import FRAME_KEYS, generate_batch, validate_balance

    man = AssetManifest()
    batch = generate_batch(seed=1000, count=count)
    for i, mw in enumerate(batch):
        issues = validate_balance(mw.stats())
        if issues:
            print(f"    ! 平衡警告 {mw.frame.key}@{i}: {issues}")
        path = _paths("weapons", f"weapon_{i:02d}_{mw.frame.key}.json")
        write_json(path, mw.summary())
        man.add("weapons", os.path.relpath(path, ASSETS_ROOT))
    print(f"  [weapons] 產生 {count} 把模組化武器（平衡驗證完成）")
    return man


def cmd_maps(seeds: list[int]) -> AssetManifest:
    from tools.maps.export import save_map
    from tools.maps.generator import generate_map, validate_map

    man = AssetManifest()
    for seed in seeds:
        m = generate_map(seed=seed)
        ok, issues = validate_map(m)
        path = _paths("maps", f"map_seed{seed}.json")
        save_map(path, m)
        status = "OK" if ok else f"問題: {issues}"
        print(f"  [maps] seed={seed}: {len(m.walls)} 牆, {len(m.sites)} 點位 → {status}")
        man.add("maps", os.path.relpath(path, ASSETS_ROOT))
    return man


def cmd_fx() -> AssetManifest:
    from tools.fx.events import EVENT_FX, all_events, validate_bindings
    from tools.fx.killfeed import KillEntry, kill_confirm_sequence, kill_feed_entry, multi_kill_thresholds
    from tools.schema import write_json
    from tools.sfx import synth
    from tools.vfx import particles, svg

    # 驗證綁定完整性
    issues = validate_bindings(set(synth.SFX_REGISTRY), set(particles.PRESETS) | set(svg.VFX_SVG_REGISTRY))
    for i in issues:
        print(f"    ! {i}")

    man = AssetManifest()
    # 事件綁定表
    p1 = _paths("fx", "event_bindings.json")
    write_json(p1, {"events": EVENT_FX, "count": len(EVENT_FX)})
    man.add("fx", os.path.relpath(p1, ASSETS_ROOT))

    # 擊殺特效範例
    demo = KillEntry(killer="Phoenix", victim="Jett", weapon="vandal", headshot=True, streak=3, tick=100)
    p2 = _paths("fx", "kill_feed_demo.json")
    write_json(p2, {
        "entry": kill_feed_entry(demo),
        "confirm_frames": kill_confirm_sequence(streak=3),
        "thresholds": multi_kill_thresholds(),
    })
    man.add("fx", os.path.relpath(p2, ASSETS_ROOT))
    print(f"  [fx] 產生事件綁定表 ({len(EVENT_FX)} 事件) + 擊殺特效範例")
    return man


def write_manifest(men: list[AssetManifest]) -> str:
    merged = AssetManifest()
    for m in men:
        for cat, items in m.assets.items():
            merged.assets.setdefault(cat, []).extend(items)
    path = _paths("manifest.json")
    write_json(path, merged.to_dict())
    total = sum(len(v) for v in merged.assets.values())
    print(f"  [manifest] 共 {total} 個素材 → assets/manifest.json")
    return path


# --------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="vanta-tools",
                                     description="VANTA 可程式化素材產生工具鏈")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="建立 assets/ 目錄")
    sub.add_parser("sfx", help="產生全部音效 WAV")
    sub.add_parser("bgm", help="產生程序化 BGM（5 種風格）")
    ag = sub.add_parser("agents", help="產生程序化角色")
    ag.add_argument("--count", type=int, default=8)
    ag.add_argument("--seed", type=int, default=100)
    pv = sub.add_parser("vfx", help="產生粒子定義 + SVG 貼圖")
    pv.add_argument("--prebake-all", action="store_true",
                    help="為每個粒子預設烘出模擬影格（體積大，僅供離線分析）")
    sub.add_parser("vfx2", help="產生分層特效蓝图 + 精靈/貼花定義")
    sk = sub.add_parser("skins", help="產生槍皮目錄 + 系列卡（可 --textures 輸出 PNG）")
    sk.add_argument("--textures", action="store_true", help="額外輸出程序化 PNG 貼圖")
    sk.add_argument("--texture-size", type=int, default=256)
    w = sub.add_parser("weapons", help="產生模組化武器")
    w.add_argument("--count", type=int, default=12)
    m = sub.add_parser("maps", help="產生程序化地圖")
    m.add_argument("--seeds", type=int, nargs="+", default=[1])
    sub.add_parser("fx", help="產生擊殺特效 + 事件綁定")
    sub.add_parser("all", help="產生全部素材 + manifest")
    sub.add_parser("manifest", help="重新整理素材清單")

    args = parser.parse_args(argv)
    os.makedirs(ASSETS_ROOT, exist_ok=True)

    if args.cmd == "init":
        print(f"  [init] 建立 {ASSETS_ROOT}")
    elif args.cmd == "sfx":
        write_manifest([cmd_sfx()])
    elif args.cmd == "bgm":
        write_manifest([cmd_bgm()])
    elif args.cmd == "agents":
        write_manifest([cmd_agents(args.count, args.seed)])
    elif args.cmd == "vfx":
        write_manifest([cmd_vfx(args.prebake_all)])
    elif args.cmd == "vfx2":
        write_manifest([cmd_vfx2()])
    elif args.cmd == "skins":
        write_manifest([cmd_skins(args.textures, args.texture_size)])
    elif args.cmd == "weapons":
        write_manifest([cmd_weapons(args.count)])
    elif args.cmd == "maps":
        write_manifest([cmd_maps(args.seeds)])
    elif args.cmd == "fx":
        write_manifest([cmd_fx()])
    elif args.cmd == "all":
        men = [cmd_sfx(), cmd_bgm(), cmd_agents(8), cmd_vfx(), cmd_vfx2(), cmd_skins(),
               cmd_weapons(12), cmd_maps([1, 7, 42]), cmd_fx()]
        write_manifest(men)
    elif args.cmd == "manifest":
        write_manifest([AssetManifest()])
    print("完成 ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
