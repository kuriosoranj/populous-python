"""
Populous Python - Game Entities

Settler: autonomous follower with state-machine AI
Building: structures erected by settlers
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from constants import (
    PLAYER, ENEMY,
    SETTLER_SPEED, SETTLER_VISION, FIGHT_RANGE, BUILD_FLAT_THRESH,
    BUILD_TIME, SPAWN_INTERVAL, FIGHT_DAMAGE, SETTLER_MAX_HP,
    B_HUT, B_HOUSE, B_MANSION, B_CASTLE,
    BUILDING_CAPACITY, BUILDING_UPGRADE_T,
    WATER_LEVEL,
)

if TYPE_CHECKING:
    from terrain import Terrain


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

class Building:
    """A structure that houses settlers and generates population."""

    def __init__(self, col: int, row: int, faction: int, btype: int = B_HUT):
        self.col = float(col)
        self.row = float(row)
        self.faction = faction
        self.btype = btype

        self.alive = True
        self.build_progress = 0.0   # 0 → 1 (under construction)
        self.built = False

        self.capacity = BUILDING_CAPACITY[btype]
        self.occupants: list[Settler] = []
        self.spawn_timer = SPAWN_INTERVAL
        self.upgrade_timer = BUILDING_UPGRADE_T.get(btype, None)

    @property
    def is_full(self) -> bool:
        return len(self.occupants) >= self.capacity

    def update(self, dt: float, game) -> list[Settler]:
        """Update building; returns any newly spawned settlers."""
        spawned: list[Settler] = []

        if not self.built:
            self.build_progress += dt / BUILD_TIME
            if self.build_progress >= 1.0:
                self.build_progress = 1.0
                self.built = True
            return spawned

        # Upgrade over time
        if self.upgrade_timer is not None:
            self.upgrade_timer -= dt
            if self.upgrade_timer <= 0 and self.btype < B_CASTLE:
                self.btype += 1
                self.capacity = BUILDING_CAPACITY[self.btype]
                self.upgrade_timer = BUILDING_UPGRADE_T.get(self.btype, None)

        # Spawn new settlers periodically
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer = SPAWN_INTERVAL
            if not self.is_full:
                s = Settler(self.col + random.uniform(-1, 1),
                            self.row + random.uniform(-1, 1),
                            self.faction)
                s.home = self
                self.occupants.append(s)
                spawned.append(s)

        return spawned

    def remove_occupant(self, settler: Settler):
        if settler in self.occupants:
            self.occupants.remove(settler)


# ---------------------------------------------------------------------------
# Settler
# ---------------------------------------------------------------------------

_WANDER   = 'wander'
_SEEK_FLAT = 'seek_flat'
_BUILD    = 'build'
_FIGHT    = 'fight'
_FLEE     = 'flee'
_GO_HOME  = 'go_home'


class Settler:
    """Autonomous follower with state-machine AI."""

    def __init__(self, col: float, row: float, faction: int):
        self.col = col
        self.row = row
        self.faction = faction

        self.alive = True
        self.hp = SETTLER_MAX_HP
        self.max_hp = SETTLER_MAX_HP

        self.state = _WANDER
        self.home: Building | None = None
        self.target_col: float = col
        self.target_row: float = row
        self.build_timer: float = 0.0
        self.build_site: tuple[int, int] | None = None
        self.fight_target: Settler | None = None

        self._wander_timer: float = 0.0
        self._think_timer: float = random.uniform(0.5, 1.5)

    # ------------------------------------------------------------------ #

    def update(self, dt: float, terrain: Terrain, all_settlers: list[Settler],
               all_buildings: list[Building]) -> Building | None:
        """Advance state machine; returns a new Building if one was just placed."""
        if not self.alive:
            return None

        self._think_timer -= dt
        new_building: Building | None = None

        if self._think_timer <= 0:
            self._think_timer = random.uniform(0.3, 0.8)
            new_building = self._think(terrain, all_settlers, all_buildings)

        self._act(dt, terrain)
        return new_building

    # ------------------------------------------------------------------ #
    #  State machine: think                                                #
    # ------------------------------------------------------------------ #

    def _think(self, terrain: Terrain, all_settlers: list[Settler],
               all_buildings: list[Building]) -> Building | None:

        # Always check for enemies first
        enemy_faction = ENEMY if self.faction == PLAYER else PLAYER
        nearest_enemy = self._nearest(
            [s for s in all_settlers if s.faction == enemy_faction and s.alive],
            SETTLER_VISION)

        if nearest_enemy and self._dist(nearest_enemy) < FIGHT_RANGE * 2:
            self.fight_target = nearest_enemy
            self.state = _FIGHT
            return None

        if self.state == _FIGHT and (
                self.fight_target is None or not self.fight_target.alive or
                self._dist(self.fight_target) > FIGHT_RANGE * 3):
            self.fight_target = None
            self.state = _WANDER

        if self.state == _WANDER or self.state == _GO_HOME:
            return self._think_wander(terrain, all_buildings)

        if self.state == _SEEK_FLAT:
            return self._think_seek_flat(terrain, all_buildings)

        if self.state == _BUILD:
            return self._think_build(terrain)

        return None

    def _think_wander(self, terrain, all_buildings) -> Building | None:
        # Already at a decent flat spot above water — decide whether to build
        if terrain.is_above_water(self.col, self.row):
            if terrain.flatness(int(round(self.col)), int(round(self.row)), 1) <= BUILD_FLAT_THRESH:
                # Check no building too close
                too_close = any(
                    math.hypot(b.col - self.col, b.row - self.row) < 4
                    for b in all_buildings if b.alive
                )
                if not too_close and random.random() < 0.4:
                    self.state = _BUILD
                    self.build_timer = 0.0
                    self.build_site = (int(round(self.col)), int(round(self.row)))
                    return None

        # Pick a random wander target
        self._wander_timer -= 0.3
        if self._wander_timer <= 0:
            self._wander_timer = random.uniform(2, 5)
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(3, 8)
            self.target_col = self.col + math.cos(angle) * dist
            self.target_row = self.row + math.sin(angle) * dist
            self.state = _WANDER

        return None

    def _think_seek_flat(self, terrain, all_buildings) -> Building | None:
        if (math.hypot(self.col - self.target_col, self.row - self.target_row) < 0.5):
            self.state = _WANDER
        return None

    def _think_build(self, terrain) -> Building | None:
        if self.build_site is None:
            self.state = _WANDER
            return None

        bc, br = self.build_site
        terrain.flatten_area(bc, br, radius=1)

        self.build_timer += 0.3   # called every ~0.5s
        if self.build_timer >= 1.0:
            self.state = _WANDER
            self.build_site = None
            b = Building(bc, br, self.faction, B_HUT)
            if self.home is None:
                self.home = b
                b.occupants.append(self)
            return b

        return None

    # ------------------------------------------------------------------ #
    #  State machine: act                                                  #
    # ------------------------------------------------------------------ #

    def _act(self, dt: float, terrain: Terrain):
        if self.state == _FIGHT and self.fight_target and self.fight_target.alive:
            self._move_towards(self.fight_target.col, self.fight_target.row, dt, terrain)
            if self._dist(self.fight_target) < FIGHT_RANGE:
                self.fight_target.take_damage(FIGHT_DAMAGE * dt)
            return

        if self.state in (_WANDER, _SEEK_FLAT, _GO_HOME):
            self._move_towards(self.target_col, self.target_row, dt, terrain)

        # Stay in place while building
        if self.state == _BUILD:
            pass  # building is handled in _think_build

    def _move_towards(self, tc: float, tr: float, dt: float, terrain: Terrain):
        dx = tc - self.col
        dy = tr - self.row
        dist = math.hypot(dx, dy)
        if dist < 0.05:
            return

        speed = SETTLER_SPEED * dt
        frac = min(1.0, speed / dist)
        nc = self.col + dx * frac
        nr = self.row + dy * frac

        # Don't walk into water
        if terrain.is_above_water(nc, nr):
            self.col, self.row = nc, nr
        else:
            # Deflect sideways
            self.target_col = self.col + random.uniform(-3, 3)
            self.target_row = self.row + random.uniform(-3, 3)

        # Keep in bounds
        n = terrain.tiles - 1
        self.col = max(1, min(n, self.col))
        self.row = max(1, min(n, self.row))

    # ------------------------------------------------------------------ #
    #  Utility                                                             #
    # ------------------------------------------------------------------ #

    def take_damage(self, amount: float):
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            if self.home:
                self.home.remove_occupant(self)

    def _dist(self, other) -> float:
        return math.hypot(self.col - other.col, self.row - other.row)

    def _nearest(self, candidates, max_dist: float):
        best, best_d = None, max_dist
        for c in candidates:
            d = self._dist(c)
            if d < best_d:
                best, best_d = c, d
        return best
