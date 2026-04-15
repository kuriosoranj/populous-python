"""
Populous Python - Enemy AI (god player)

A simple AI that uses god powers to help its settlers and hinder the player.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from constants import (
    ENEMY, PLAYER,
    P_RAISE, P_LOWER, P_QUAKE, P_VOLCANO, P_FLOOD,
    POWER_COSTS, WATER_LEVEL,
)

if TYPE_CHECKING:
    from game import Game


class AIPlayer:
    """Controls the enemy god's actions."""

    def __init__(self):
        self._think_timer = random.uniform(8, 15)   # seconds between actions
        self._action_weights = {
            'raise_for_settler': 40,
            'raise_enemy_land':  20,
            'quake_player':      15,
            'volcano_player':    10,
            'flood_player':      15,
        }

    def update(self, dt: float, game: 'Game'):
        self._think_timer -= dt
        if self._think_timer > 0:
            return

        self._think_timer = random.uniform(6, 18)
        self._take_action(game)

    # ------------------------------------------------------------------ #

    def _take_action(self, game: 'Game'):
        mana = game.mana_enemy

        # Collect enemy settlers and player settlers
        e_settlers = [s for s in game.settlers if s.faction == ENEMY and s.alive]
        p_settlers = [s for s in game.settlers if s.faction == PLAYER and s.alive]

        options = []

        # Raise land near an enemy settler who needs flat ground
        for s in e_settlers[:5]:
            if (game.terrain.flatness(int(round(s.col)), int(round(s.row)), 1) > 1 and
                    game.terrain.is_above_water(s.col, s.row)):
                options.append(('raise_ally', s.col, s.row))

        # Volcano on player cluster
        if mana >= POWER_COSTS[P_VOLCANO] and p_settlers:
            target = max(p_settlers,
                         key=lambda s: self._density(s, p_settlers, 4))
            options.append(('volcano', target.col, target.row))

        # Earthquake on player cluster
        if mana >= POWER_COSTS[P_QUAKE] and p_settlers:
            target = random.choice(p_settlers)
            options.append(('quake', target.col, target.row))

        # Flood player's low-lying land
        if mana >= POWER_COSTS[P_FLOOD] and p_settlers:
            low = [s for s in p_settlers
                   if game.terrain.height_at(s.col, s.row) < WATER_LEVEL + 3]
            if low:
                target = random.choice(low)
                options.append(('flood', target.col, target.row))

        # Raise land to help settlers get to player
        if e_settlers:
            s = random.choice(e_settlers)
            options.append(('raise_ally', s.col, s.row))

        if not options:
            return

        # Pick an action
        action, col, row = random.choice(options)

        if action == 'raise_ally':
            if mana >= POWER_COSTS[P_RAISE]:
                game.terrain.raise_area(col, row, radius=2.0, amount=1)
                game.mana_enemy -= POWER_COSTS[P_RAISE]
        elif action == 'volcano':
            game.terrain.volcano_erupt(col, row)
            h = game.terrain.height_at(col, row)
            game.particles.emit_volcano(col, row, h,
                                        game.renderer.cam_x, game.renderer.cam_y)
            game.mana_enemy -= POWER_COSTS[P_VOLCANO]
            game.screen_shake = max(game.screen_shake, 3.0)
            game._kill_settlers_near(col, row, radius=4.5, faction=PLAYER)
        elif action == 'quake':
            game.terrain.quake(col, row, radius=6.0)
            game.mana_enemy -= POWER_COSTS[P_QUAKE]
            game.screen_shake = max(game.screen_shake, 2.0)
            game.particles.emit_quake(col, row,
                                      game.terrain.height_at(col, row),
                                      game.renderer.cam_x, game.renderer.cam_y)
        elif action == 'flood':
            game.terrain.flood(col, row)
            game.mana_enemy -= POWER_COSTS[P_FLOOD]
            game.particles.emit_flood(col, row,
                                      game.terrain.height_at(col, row),
                                      game.renderer.cam_x, game.renderer.cam_y)
            game._drown_settlers_below_water(PLAYER)

    @staticmethod
    def _density(settler, group, radius: float) -> int:
        return sum(1 for s in group
                   if math.hypot(s.col - settler.col, s.row - settler.row) < radius)
