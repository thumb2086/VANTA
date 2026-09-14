"""買槍區：買槍階段可在出生區移動但不可越界；行動期解除。"""

from server.core.math_core import Vec3
from server.core.movement import MoveInput
from server.game.entities import World
from server.game.match import RoundPhase

DT = 1.0 / 128.0


def _in_action(world):
    world.start_match()
    world.match.phase = RoundPhase.ACTION


def test_buy_phase_movement_allowed_but_clamped():
    """買槍階段：攻方出生點可動，但無法越過買槍區邊界（z=-13）。"""
    world = World()
    world.start_match()                      # phase = buy
    p = world.players[0]                     # 攻方（team 0）
    p.pos = Vec3(0, 0, -16)
    inp = [MoveInput(forward=1.0)] + [None] * 9
    for _ in range(int(3.0 / DT)):           # 3 秒衝刺 → 若無邊界會到 z≈0.2
        world.step(inp, DT)
    assert p.pos.z < -13.0 + 0.05            # 卡在買槍區邊界（門檻 z=-13）
    assert p.pos.z > -16.0                   # 確實有移動（不是凍結）


def test_buy_zone_allows_lateral_movement():
    """買槍階段：水平移動不受限（在區內自由走動）。"""
    world = World()
    world.start_match()
    p = world.players[0]
    p.pos = Vec3(0, 0, -16)
    inp = [MoveInput(strafe=1.0)] + [None] * 9
    for _ in range(int(1.5 / DT)):
        world.step(inp, DT)
    assert p.pos.x > 5.0                     # 區內水平可自由移動


def test_action_phase_unrestricted():
    """行動期：出生區限制解除。"""
    world = World()
    _in_action(world)
    p = world.players[0]
    p.pos = Vec3(0, 0, -16)
    inp = [MoveInput(forward=1.0)] + [None] * 9
    for _ in range(int(3.0 / DT)):
        world.step(inp, DT)
    assert p.pos.z > -10.0                   # 穿越門檻推進


def test_defender_zone_mirrored():
    """守方買槍區：卡在 z=+14 門檻內。"""
    world = World()
    world.start_match()
    p = world.players[5]                     # 守方（team 1）
    p.pos = Vec3(10, 0, 16)                  # 空位（避開其它守方出生點）
    inp = [None] * 10
    inp[5] = MoveInput(forward=-1.0)         # 往 -z（朝向場中）
    for _ in range(int(3.0 / DT)):
        world.step(inp, DT)
    assert p.pos.z > 14.0 - 0.05
    assert p.pos.z < 16.0


def test_buy_zone_in_map_json():
    """匯出 JSON 含買槍區（客戶端偵測要用）。"""
    from server.game.mapdata import default_map
    from tools.maps.export import map_to_dict, dict_to_map

    d = map_to_dict(default_map())
    # VANTA-1：攻方買區 = 出生大樓 z[-20.9,-13]；守方 = CT 房 z[13,20.9]
    assert d["buy_zone_attackers"][0]["z"] == -20.9
    assert d["buy_zone_attackers"][1]["z"] == -13.0
    assert d["buy_zone_defenders"][0]["z"] == 13.0
    m2 = dict_to_map(d)
    assert m2.buy_zone_defenders[1].z == 20.9
    # 往返序列化必須位元級一致（伺服器/客戶端同幾何）
    assert len(m2.walls) == len(default_map().walls)