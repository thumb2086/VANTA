"""server/game/world.py — 相容性 re-export（實作已移至 entities.py）。"""

from server.game.entities import PlayerMoveState, World

__all__ = ["World", "PlayerMoveState"]
