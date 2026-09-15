"""
server/game/practice.py — Practice Range (static/moving bots, DPS tracking)
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field

@dataclass
class BotConfig:
    health: int = 100
    armor: int = 0  # 0=none, 25=light, 50=heavy
    speed: float = 0.0  # 0=static, 1.5/3.0/5.0 = strafe speed
    jump: bool = False

@dataclass
class Bot:
    slot: int; x: float; z: float; alive: bool = True
    hp: int = 100; armor: int = 0
    vel_x: float = 0.0; vel_z: float = 0.0
    strafe_timer: float = 0.0

@dataclass
class DamageRecord:
    shots: int = 0; hits: int = 0; headshots: int = 0
    total_damage: float = 0.0; kills: int = 0
    start_time: float = 0.0

    @property
    def accuracy(self) -> float:
        return self.hits / max(1, self.shots) * 100

    @property
    def dps(self) -> float:
        elapsed = max(0.01, time.time() - self.start_time) if self.start_time else 0.01
        return self.total_damage / elapsed

    @property
    def ttk(self) -> float:
        if self.kills == 0: return 0.0
        elapsed = max(0.01, time.time() - self.start_time) if self.start_time else 0.01
        return elapsed / self.kills

class PracticeRange:
    def __init__(self, config: BotConfig | None = None):
        self.config = config or BotConfig()
        self.bots: list[Bot] = []
        self.stats = DamageRecord()
        self.best_ttk: float = 999.0
        self.round_active: bool = False

    def spawn_bots(self, count: int = 10, radius: float = 20.0) -> None:
        import math
        self.bots.clear()
        for i in range(count):
            angle = 2 * math.pi * i / count
            self.bots.append(Bot(
                slot=i,
                x=math.cos(angle) * radius,
                z=math.sin(angle) * radius,
                hp=self.config.health, armor=self.config.armor
            ))
        self.stats = DamageRecord(start_time=time.time())
        self.round_active = True

    def reset(self) -> None:
        self.spawn_bots(len(self.bots) if self.bots else 10)

    def hit_bot(self, slot: int, damage: float, headshot: bool = False) -> bool:
        if slot < 0 or slot >= len(self.bots): return False
        bot = self.bots[slot]
        if not bot.alive: return False
        self.stats.shots += 1; self.stats.hits += 1
        if headshot: self.stats.headshots += 1
        actual = damage * (2.0 if headshot else 1.0)
        if bot.armor > 0:
            absorbed = min(bot.armor, actual * 0.66)
            bot.armor -= int(absorbed); actual -= absorbed
        bot.hp -= int(actual)
        self.stats.total_damage += actual
        if bot.hp <= 0:
            bot.alive = False; self.stats.kills += 1
            self._check_all_dead()
        return True

    def record_shot(self) -> None:
        self.stats.shots += 1

    def _check_all_dead(self) -> None:
        if all(not b.alive for b in self.bots):
            self.round_active = False
            elapsed = time.time() - self.stats.start_time
            if elapsed < self.best_ttk:
                self.best_ttk = elapsed

    def update_bots(self, dt: float) -> None:
        for bot in self.bots:
            if not bot.alive: continue
            if self.config.speed > 0:
                bot.strafe_timer -= dt
                if bot.strafe_timer <= 0:
                    import random
                    bot.vel_x = random.uniform(-1, 1) * self.config.speed
                    bot.vel_z = random.uniform(-1, 1) * self.config.speed
                    bot.strafe_timer = random.uniform(0.5, 2.0)
                bot.x += bot.vel_x * dt
                bot.z += bot.vel_z * dt
                bot.x = max(-40, min(40, bot.x))
                bot.z = max(-40, min(40, bot.z))

    def summary(self) -> dict:
        return {
            "shots": self.stats.shots, "hits": self.stats.hits,
            "headshots": self.stats.headshots,
            "accuracy": round(self.stats.accuracy, 1),
            "dps": round(self.stats.dps, 1),
            "kills": self.stats.kills,
            "ttk": round(self.stats.ttk, 3),
            "best_ttk": round(self.best_ttk, 3),
            "bots_alive": sum(1 for b in self.bots if b.alive),
        }
