"""Godot 客戶端：素材匯出器測試。"""

import json
import os

import pytest

import tools.godot.export as gexp


@pytest.fixture()
def tmp_export(tmp_path, monkeypatch):
    """把匯出目標導向暫存目錄。"""
    monkeypatch.setattr(gexp, "CLIENT_ASSETS", str(tmp_path / "assets"))
    return tmp_path


def test_export_copies_assets(tmp_export):
    n = gexp.export()
    assert n >= 60
    assert os.path.isdir(str(tmp_export / "assets" / "sfx"))
    assert os.path.isdir(str(tmp_export / "assets" / "bgm"))
    assert os.path.isdir(str(tmp_export / "assets" / "maps"))
    assert os.path.isdir(str(tmp_export / "assets" / "weapons"))
    assert os.path.isdir(str(tmp_export / "assets" / "vfx" / "svg"))
    assert os.path.isdir(str(tmp_export / "assets" / "fx"))


def test_asset_index_valid(tmp_export):
    gexp.export()
    with open(str(tmp_export / "assets" / "asset_index.json"), encoding="utf-8") as f:
        index = json.load(f)
    assert len(index["sfx"]) >= 20
    assert len(index["bgm"]) >= 5
    assert len(index["bgm_meta"]) >= 5
    assert len(index["maps"]) >= 1
    assert len(index["weapons"]) >= 1
    assert len(index["agents"]) >= 4
    assert len(index["agent_portraits"]) >= 4
    # 角色頭像 SVG 已匯出
    for path in index["agent_portraits"][:2]:
        assert path.endswith(".svg")
        assert os.path.isfile(os.path.join(str(tmp_export), path[len("res://"):]))
    for path in index["sfx"][:3]:
        assert path.startswith("res://assets/")
        assert path.endswith((".wav", ".mp3"))
        assert os.path.isfile(os.path.join(str(tmp_export), path[len("res://"):]))


def test_export_dry_does_not_write(tmp_export):
    gexp.export(dry=True)
    assert not os.path.isdir(str(tmp_export / "assets"))


def test_exported_map_loadable(tmp_export):
    gexp.export()
    from tools.maps.export import load_map
    from tools.maps.generator import validate_map

    maps_dir = str(tmp_export / "assets" / "maps")
    for f in os.listdir(maps_dir):
        m = load_map(os.path.join(maps_dir, f))
        ok, issues = validate_map(m)
        assert ok, f


# --------------------------------------------------------------------- #
# 提交進 repo 的 client/assets：必須自洽（匯出器會整個重建，容易留下孤兒檔）
# --------------------------------------------------------------------- #
CLIENT_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client")
COMMITTED_ASSETS = os.path.join(CLIENT_ROOT, "assets")


def test_committed_asset_index_points_at_real_files():
    """`asset_index.json` 裡每個 res:// 都要真的存在——否則遊戲會靜默少素材。"""
    index_path = os.path.join(COMMITTED_ASSETS, "asset_index.json")
    if not os.path.exists(index_path):
        pytest.skip("尚未執行 tools.godot.export（client/assets 未產生）")
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)
    assert index, "asset_index.json 是空的"
    missing = []
    for cat, paths in index.items():
        for rel in paths:
            local = os.path.join(CLIENT_ROOT, rel[len("res://"):].replace("/", os.sep))
            if not os.path.exists(local):
                missing.append(f"{cat}:{rel}")
    assert not missing, f"索引指向不存在的檔案：{missing[:8]}"


def test_committed_assets_include_skin_and_vfx_layers():
    """槍皮/特效資料是渲染層的依賴，缺了就只剩純色方塊。"""
    index_path = os.path.join(COMMITTED_ASSETS, "asset_index.json")
    if not os.path.exists(index_path):
        pytest.skip("尚未執行 tools.godot.export")
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)
    assert "skins" in index and index["skins"], "缺少 client/assets/skins/skins.json"
    assert len(index.get("vfx2", [])) >= 3, "缺少分層特效藍圖（vfx2）"
    assert len(index.get("skin_cards", [])) >= 10, "系列卡數量不對"


def test_no_orphan_import_metadata():
    """不該有「`.svg.import` 留著、來源 SVG 已刪除」的孤兒元資料。"""
    if not os.path.isdir(COMMITTED_ASSETS):
        pytest.skip("client/assets 未產生")
    orphans = []
    for root, _dirs, files in os.walk(COMMITTED_ASSETS):
        for name in files:
            if name.endswith(".import"):
                src = os.path.join(root, name[: -len(".import")])
                if not os.path.exists(src):
                    orphans.append(os.path.relpath(os.path.join(root, name), COMMITTED_ASSETS))
    assert not orphans, f"孤兒 .import（Godot 每次開專案都重新匯入）：{orphans[:8]}"


def test_export_is_deterministic(tmp_export):
    """同一份工具鏈跑兩次要产出位元組相同的素材（否則 diff 會無止盡翻滾）。"""
    import hashlib

    def snapshot():
        gexp.export()
        out = {}
        for root, _dirs, files in os.walk(str(tmp_export / "assets")):
            for name in files:
                path = os.path.join(root, name)
                with open(path, "rb") as f:
                    out[os.path.relpath(path, str(tmp_export))] = hashlib.sha256(f.read()).hexdigest()
        return out

    first = snapshot()
    second = snapshot()
    assert first == second, "匯出不確定：素材內容每次都會變"


def test_export_never_deletes_unmanaged_files(tmp_export, monkeypatch):
    """迴歸防護：`client/assets/` 裡混放者工具鏈不管的素材（手工 MP3、
    `weapons_models/` 貼圖、別人放的地圖）。匯出器曾經一句 rmtree 把它們全殺掉，
    所以「不得刪除未受管理的檔案」要有測試釘住。
    """
    assets = tmp_export / "assets"
    foreign = {
        "sfx/handmade_kill.mp3": "MP3",           # 同目錄、同受管理副檔名
        "maps/map_haven.json": "{}",              # 受管理目錄裡的非產出 JSON
        "weapons_models/BUNDLE_body.png": "PNG",  # 完全不受管理的目錄
        "characters/README.md": "hand notes",
    }
    for rel, body in foreign.items():
        f = assets / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    gexp.export()
    for rel in foreign:
        assert (assets / rel).exists(), f"匯出器刪掉了 {rel}"
    # 但預設不會主動清舊檔；--clean 才會
    assert (assets / "agents").is_dir()


def test_export_clean_flag_removes_stale_generated_files(tmp_export):
    """`--clean` 依 `.export_manifest.json` 回收「上次寫過、這次不再產出」的素材。

    所有權以清單為準，所以同目錄裡別人放的手-work 檔案永遠安全（這正是
    舊 `rmtree` 做不到的地方）。
    """
    assets = tmp_export / "assets"
    gexp.export()
    manifest = assets / ".export_manifest.json"
    assert manifest.exists(), "沒寫出匯出清單，--clean 無依據可循"
    entries = json.loads(manifest.read_text(encoding="utf-8"))["files"]
    assert len(entries) >= 60

    # 模擬「世代更替」：產生器改名字後，舊檔仍在磁碟、但這次不再產出
    stale_rel = os.path.join("agents", "old_roster_name.json")
    with open(os.path.join(str(assets), stale_rel), "w", encoding="utf-8") as f:
        f.write("{}")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["files"].append(stale_rel)            # 假裝上次匯出寫過它
    with open(str(manifest), "w", encoding="utf-8") as f:
        json.dump(payload, f)
    foreign = assets / "maps" / "map_haven.json"  # 手工檔：清單裡沒有 → 不能動
    foreign.write_text("{}", encoding="utf-8")

    gexp.export(clean=True)
    assert not os.path.exists(os.path.join(str(assets), stale_rel)), "--clean 沒收回舊素材"
    assert foreign.exists(), "--clean 誤殺非工具鏈檔案"
