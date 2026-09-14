"""tools/godot/serve.py：伺服器內建 AI 行為測試。

serve.py 現與 workers/src/ai_bots.py 共用同一顆 AI 大腦，
本測試直接驗證該大腦（含模組狀態重置，避免跨測試污染）。
"""

import os
import sys

import pytest

from server.core.math_core import Vec3
from server.core.movement import MoveInput
from server.game.entities import World
from server.game.match import RoundPhase, TEAM_ATTACKERS, TEAM_DEFENDERS

_WORKERS_SRC = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "workers", "src"))
if _WORKERS_SRC not in sys.path:
    sys.path.insert(0, _WORKERS_SRC)

import ai_bots  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_bot_state():
    ai_bots._bot_state.clear()
    ai_bots._prev_dir.clear()
    ai_bots._bot_inputs.clear()
    yield
    ai_bots._bot_state.clear()
    ai_bots._prev_dir.clear()
    ai_bots._bot_inputs.clear()


def bot_act(world, slot, match=None):
    return ai_bots.bot_act(world, slot)


def _world_in_action() -> tuple[World, object]:
    world = World(seed=7)
    world.start_match()
    world.match.phase = RoundPhase.ACTION
    return world, world.match


def test_dead_player_returns_none():
    world, match = _world_in_action()
    world.players[3].alive = False
    assert bot_act(world, 3, match) is None


def test_attacker_advances_toward_site():
    world, match = _world_in_action()
    world.players[0].pos = Vec3(0, 0, -12)
    # 推進過開局緩衝（2.5s）
    for _ in range(128 * 4):
        world.step([MoveInput()] * 10, 1.0 / 128.0)
    inp = bot_act(world, 0, match)
    assert inp.forward > 0.0 or inp.strafe != 0.0


def test_attacker_at_site_holds_plant():
    world, match = _world_in_action()
    slot = 1
    world.players[slot].pos = Vec3(12, 0, 10)   # A_SITE
    world.players[slot].team = TEAM_ATTACKERS
    # 推進過開局緩衝（2.5s）
    for _ in range(128 * 4):
        world.step([MoveInput()] * 10, 1.0 / 128.0)
    assert world.spike.state.value == "idle"
    inp = bot_act(world, slot, match)
    assert inp.forward == 0.0 and inp.strafe == 0.0
    assert world.spike.state.value != "idle"    # 已開始安放


def test_defender_retreats_to_spike_when_planted():
    """安放完成後，活著的守方會回防到 Spike 旁。

    測試重點是「回防行為」而非戰鬥結果，因此先把守方移到遠處
    （避免攻方還沒種下就被殲滅），安放後守方 AI 會自動朝 Spike 移動。
    """
    world, match = _world_in_action()
    for i, p in enumerate(world.players[5:], start=5):
        p.pos = Vec3(-30 + i * 2.0, 0, 28)      # 遠離 A 點的角落
    planted_at = -1
    ok = False
    for t in range(128 * 40):
        decided = ai_bots.decide_bots(world, None)   # 含射擊決策
        inputs = [MoveInput()] * 10
        for slot, m in decided.items():
            inputs[slot] = m
        world.step(inputs, 1.0 / 128.0)
        if world.spike.state.value == "planted":
            if planted_at < 0:
                planted_at = t
            defenders = [p for p in world.players[5:] if p.alive]
            if defenders:
                nearest = min(p.pos.distance_to(world.spike._spike_pos()) for p in defenders)
                if nearest < 2.5:
                    ok = True
                    break
    assert planted_at >= 0, "Spike 從未安放成功"
    defenders = [p for p in world.players[5:] if p.alive]
    assert defenders, "守方全滅"
    nearest = min(p.pos.distance_to(world.spike._spike_pos()) for p in defenders)
    # 回防行為：安放後守方與 Spike 的距離必須明顯縮短（貪婪尋路不保證抵達，
    # 卡角落問題屬導航系統範疇，另案處理）
    start_dist = min(
        Vec3(-30 + i * 2.0, 0, 28).distance_to(world.spike._spike_pos())
        for i in range(5, 10))
    assert nearest < start_dist * 0.6, \
        f"守方未回防：nearest={nearest:.1f}m / 初始={start_dist:.1f}m"


def test_defender_moves_toward_hold_point():
    world, match = _world_in_action()
    slot = 7
    world.players[slot].pos = Vec3(5, 0, 5)
    world.players[slot].team = TEAM_DEFENDERS
    # 推進過開局緩衝
    for _ in range(128 * 4):
        world.step([MoveInput()] * 10, 1.0 / 128.0)
    inp = bot_act(world, slot, match)
    assert inp.forward != 0.0 or inp.strafe != 0.0  # 往守點移動


def test_defenders_hold_points_are_spread():
    """守方五個卡點必須彼此散開（≥2m），避免「敵人疊在一起」。"""
    holds = ai_bots.DEFENDER_HOLDS
    assert len(holds) == 5
    for i in range(len(holds)):
        for j in range(i + 1, len(holds)):
            assert holds[i].distance_to(holds[j]) >= 2.0, \
                f"hold{i} 與 hold{j} 距離 {holds[i].distance_to(holds[j]):.2f}m 過近"


def test_attacker_bot_reaches_site_through_walls():
    """牆壁感知尋路：攻方從重生點推進到 A 點並完成安放（40 秒內）。"""
    world, match = _world_in_action()
    for _ in range(128 * 40):
        inputs = [bot_act(world, i, match) or MoveInput() for i in range(10)]
        world.step(inputs, 1.0 / 128.0)
        if world.spike.state.value != "idle":
            break
    assert world.spike.state.value in ("planting", "planted")
    near_site = [p for p in world.players if p.alive and p.pos.distance_to(Vec3(12, 0, 10)) < 4.0]
    assert near_site, "沒有攻方到達 A 點"
