"""scripts/ 示範腳本煙霧測試：驗證 sys.path 引導（可在任何 cwd 執行）。"""

import subprocess
import sys

import pytest

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("script", ["demo_agents.py", "demo_pipeline.py"])
def test_demo_script_runs_from_any_cwd(script, tmp_path):
    """從非專案目錄執行 → 不再 ModuleNotFoundError（regression）。"""
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script)],
        cwd=tmp_path,
        capture_output=True,
        timeout=60,
        env={"PYTHONIOENCODING": "utf-8"},
    )
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert r.stdout  # 有輸出


def test_demo_match_syntax_and_bootstrap():
    """demo_match 較慢，只驗證語法 + sys.path 引導存在。"""
    src = (ROOT / "scripts" / "demo_match.py").read_text(encoding="utf-8")
    compile(src, "demo_match.py", "exec")
    assert 'sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))' in src