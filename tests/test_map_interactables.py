"""tests/test_map_interactables.py — 地圖互動機制測試（傳送門/繩索/鐵門）"""

import pytest

from server.core.math_core import Vec3
from server.core.movement import MovementConfig
from server.game.entities import World
from server.game.mapdata import (
    MapData, Wall, SpikeSite, Teleporter, RopeZipline, DoorToggle,
)

DT = 1.0 / 128.0


def _world():
    return World(slots=10, cfg=MovementConfig(), ground_y=0.0, seed=42)


# ─── 傳送門測試 ───

class TestTeleporter:
    def test_teleporter_data_structure(self):
        tp = Teleporter(
            entrance=Vec3(1, 0, 1), exit=Vec3(10, 0, 10),
            radius=1.5, cooldown=3.0,
        )
        assert tp.entrance.x == 1
        assert tp.exit.x == 10
        assert tp.radius == 1.5
        assert tp.team_restricted == -1

    def test_teleporter_in_default_map(self):
        w = _world()
        assert len(w.map_data.teleporters) >= 1
        tp = w.map_data.teleporters[0]
        assert tp.entrance is not None
        assert tp.exit is not None

    def test_player_gets_teleported(self):
        w = _world()
        tp = w.map_data.teleporters[0]
        # 將玩家0放在傳送門入口
        w.players[0].pos = Vec3(tp.entrance.x, 0, tp.entrance.z)
        old_pos = w.players[0].pos
        # 跑一 tick → 應被傳送
        w.step([None] * 10, DT)
        assert w.players[0].pos.distance_to(tp.exit) < 1.0

    def test_teleporter_cooldown_prevents_reuse(self):
        w = _world()
        tp = w.map_data.teleporters[0]
        w.players[0].pos = Vec3(tp.entrance.x, 0, tp.entrance.z)
        w.players[0].vel = Vec3()
        # 第一次傳送
        w.step([None] * 10, DT)
        assert w.players[0].pos.distance_to(tp.exit) < 2.0
        cd1 = w._teleport_cooldowns.get(0, 0)
        assert cd1 > 0  # 冷卻生效
        # 把玩家移回入口 → 冷卻中不應再次傳送
        w.players[0].pos = Vec3(tp.entrance.x, 0, tp.entrance.z)
        w.players[0].vel = Vec3()
        w.step([None] * 10, DT)
        assert w._teleport_cooldowns.get(0, 0) > 0  # 冷卻仍在
        # 手動遞減冷卻（不透過 step，避免位置變動）
        while w._teleport_cooldowns.get(0, 0) > 0:
            w._teleport_cooldowns[0] = max(0, w._teleport_cooldowns[0] - DT)
        assert w._teleport_cooldowns.get(0, 0) == 0
        # 冷卻過期 → 玩家在入口 → 應傳送
        w.players[0].pos = Vec3(tp.entrance.x, 0, tp.entrance.z)
        w.players[0].vel = Vec3()
        w.step([None] * 10, DT)
        assert w.players[0].pos.distance_to(tp.exit) < 2.0

    def test_teleporter_event_logged(self):
        w = _world()
        tp = w.map_data.teleporters[0]
        w.players[0].pos = Vec3(tp.entrance.x, 0, tp.entrance.z)
        w.step([None] * 10, DT)
        assert any("teleport" in e for e in w.event_log)


# ─── 繩索攀爬測試 ───

class TestRopeZipline:
    def test_rope_data_structure(self):
        rope = RopeZipline(
            start=Vec3(0, 0, 0), end=Vec3(0, 4, 6),
            speed=8.0, radius=1.5,
        )
        assert rope.start.y == 0
        assert rope.end.y == 4
        assert rope.bidirectional is True

    def test_ropes_in_default_map(self):
        w = _world()
        assert len(w.map_data.ropes) >= 3  # 至少 3 條繩索

    def test_interact_starts_rope_climb(self):
        w = _world()
        rope = w.map_data.ropes[0]
        # 玩家靠近繩索起點
        w.players[0].pos = Vec3(rope.start.x, 0, rope.start.z)
        result = w.interact(0)
        assert result == True
        assert w._rope_active.get(0) == 0  # 正在攀爬

    def test_rope_climb_progresses_and_arrives(self):
        w = _world()
        rope = w.map_data.ropes[0]
        rope_len = rope.start.distance_to(rope.end)
        w.players[0].pos = Vec3(rope.start.x, 0, rope.start.z)
        w.interact(0)
        # 攀爬到完成
        steps_needed = int(rope_len / rope.speed / DT) + 10
        for _ in range(steps_needed):
            w.step([None] * 10, DT)
        # 應到達終點
        assert w.players[0].pos.distance_to(rope.end) < 1.0
        # 攀爬結束
        assert 0 not in w._rope_active

    def test_rope_bidirectional_from_end(self):
        w = _world()
        rope = w.map_data.ropes[0]
        assert rope.bidirectional
        # 從終點開始攀爬
        w.players[0].pos = Vec3(rope.end.x, rope.end.y, rope.end.z)
        result = w.interact(0)
        assert result == True

    def test_rope_event_logged(self):
        w = _world()
        rope = w.map_data.ropes[0]
        w.players[0].pos = Vec3(rope.start.x, 0, rope.start.z)
        w.interact(0)
        assert any("rope_start" in e for e in w.event_log)


# ─── 可動鐵門測試 ───

class TestDoorToggle:
    def test_door_data_structure(self):
        wall = Wall(Vec3(0, 0, 0), Vec3(1, 3, 1), "concrete")
        door = DoorToggle(
            wall=wall,
            toggle_pos=Vec3(2, 0, 0),
            toggle_radius=2.0,
            open=False,
            door_name="Test Door",
        )
        assert door.open is False
        assert door.door_name == "Test Door"

    def test_doors_in_default_map(self):
        w = _world()
        assert len(w.map_data.doors) >= 2  # A Market + B Market

    def test_closed_door_blocks_as_wall(self):
        w = _world()
        door = w.map_data.doors[0]
        assert not door.open
        # 關閉的門應在牆面列表中
        assert door.wall in w.map_data.walls

    def test_interact_opens_door(self):
        w = _world()
        door = w.map_data.doors[0]
        # 玩家靠近門開關
        w.players[0].pos = Vec3(door.toggle_pos.x, 0, door.toggle_pos.z)
        result = w.interact(0)
        assert result == True
        assert door.open is True
        # 開啟後牆面應從列表移除
        assert door.wall not in w.map_data.walls

    def test_interact_closes_door_again(self):
        w = _world()
        door = w.map_data.doors[0]
        # 先開啟
        w.players[0].pos = Vec3(door.toggle_pos.x, 0, door.toggle_pos.z)
        w.interact(0)
        assert door.open is True
        # 再關閉
        w.interact(0)
        assert door.open is False
        assert door.wall in w.map_data.walls

    def test_far_player_cannot_toggle_door(self):
        w = _world()
        door = w.map_data.doors[0]
        # 玩家遠離所有互動物件
        w.players[0].pos = Vec3(19.0, 0, 19.0)  # 遠離繩索和門
        result = w.interact(0)
        assert result == False
        assert door.open is False  # 狀態不變

    def test_door_toggle_event_logged(self):
        w = _world()
        door = w.map_data.doors[0]
        w.players[0].pos = Vec3(door.toggle_pos.x, 0, door.toggle_pos.z)
        w.interact(0)
        assert any("door_toggle" in e for e in w.event_log)

    def test_open_door_allows_passage(self):
        """開啟的門不應阻擋射線。"""
        w = _world()
        door = w.map_data.doors[0]
        # 先開門
        w.players[0].pos = Vec3(door.toggle_pos.x, 0, door.toggle_pos.z)
        w.interact(0)
        # 開啟後通過門的位置應無牆壁阻擋
        origin = door.wall.mn + Vec3(-1, 1, 0)
        end = door.wall.mx + Vec3(1, 1, 0)
        # LOS should be clear when door is open
        assert w.map_data.los_clear(origin, end)

    def test_closed_door_blocks_los(self):
        """關閉的門應阻擋視線。"""
        w = _world()
        door = w.map_data.doors[0]
        assert not door.open
        origin = door.wall.mn + Vec3(-1, 1, 0)
        end = door.wall.mx + Vec3(1, 1, 0)
        assert not w.map_data.los_clear(origin, end)


# ─── 整合測試 ───

class TestInteractableIntegration:
    def test_all_three_mechanisms_coexist(self):
        w = _world()
        assert len(w.map_data.teleporters) >= 1
        assert len(w.map_data.ropes) >= 1
        assert len(w.map_data.doors) >= 1

    def test_map_still_validated(self):
        """加入互動機制後地圖仍應通過密封/可達驗證。"""
        from server.game.map_vanta1 import validate_vanta1
        result = validate_vanta1()
        assert result["sealed"], "Map should be sealed"
        assert all(result["reachable_from_atk"].values()), "All targets should be reachable"
