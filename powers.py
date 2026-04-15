"""
Populous Python - God Powers

Each power is a callable that modifies terrain, entities, and particles.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from constants import (
    P_RAISE, P_LOWER, P_QUAKE, P_VOLCANO, P_FLOOD, P_ARMA,
    POWER_COSTS, MAX_MANA, PLAYER, ENEMY,
)
from renderer import iso

if TYPE_CHECKING:
    from game import Game


def use_power(power_id: int, game: 'Game', col: float, row: float) -> bool:
    """
    Attempt to use a god power.
    Returns True if the power was successfully used (mana deducted).
    """
    cost = POWER_COSTS[power_id]
    if game.mana < cost:
        return False

    game.mana -= cost

    if power_id == P_RAISE:
        _raise_land(game, col, row)
    elif power_id == P_LOWER:
        _lower_land(game, col, row)
    elif power_id == P_QUAKE:
        _earthquake(game, col, row)
    elif power_id == P_VOLCANO:
        _volcano(game, col, row)
    elif power_id == P_FLOOD:
        _flood(game, col, row)
    elif power_id == P_ARMA:
        _armageddon(game)

    return True


# ---------------------------------------------------------------------------
# Individual powers
# ---------------------------------------------------------------------------

def _raise_land(game: 'Game', col: float, row: float):
    game.terrain.raise_area(col, row, radius=2.5, amount=1)
    _quake_camera(game, 0.5)


def _lower_land(game: 'Game', col: float, row: float):
    game.terrain.lower_area(col, row, radius=2.5, amount=1)
    _quake_camera(game, 0.5)


def _earthquake(game: 'Game', col: float, row: float):
    game.terrain.quake(col, row, radius=7.0)
    _quake_camera(game, 4.0)

    h = game.terrain.height_at(col, row)
    r = game.renderer
    sx, sy = iso(col, row, h, r.cam_x, r.cam_y)

    # Spawn quake particles at multiple spots in the area
    ps = game.particles
    for _ in range(8):
        dc = random.uniform(-6, 6)
        dr = random.uniform(-6, 6)
        nh = game.terrain.height_at(col + dc, row + dr)
        nsx, nsy = iso(col + dc, row + dr, nh, r.cam_x, r.cam_y)
        ps.emit_quake(col + dc, row + dr, nh, r.cam_x, r.cam_y)

    # Kill any settlers caught in a severe quake
    for s in game.settlers:
        if s.alive:
            d = math.hypot(s.col - col, s.row - row)
            if d < 4 and random.random() < 0.3:
                _kill_settler(game, s)


def _volcano(game: 'Game', col: float, row: float):
    game.terrain.volcano_erupt(col, row)
    _quake_camera(game, 3.0)

    h = game.terrain.height_at(col, row)
    game.particles.emit_volcano(col, row, h, game.renderer.cam_x, game.renderer.cam_y)

    # Lava flow kills nearby settlers
    for s in game.settlers:
        if s.alive:
            d = math.hypot(s.col - col, s.row - row)
            if d < 4:
                _kill_settler(game, s)


def _flood(game: 'Game', col: float, row: float):
    game.terrain.flood(col, row, radius=8.0)

    h = game.terrain.height_at(col, row)
    game.particles.emit_flood(col, row, h, game.renderer.cam_x, game.renderer.cam_y)

    # Drown settlers now below water
    for s in game.settlers:
        if s.alive and not game.terrain.is_above_water(s.col, s.row):
            _kill_settler(game, s)


def _armageddon(game: 'Game'):
    """All-out war: every settler fights every other settler to the death,
    plus terrain-wide devastation."""
    _quake_camera(game, 8.0)

    # Terrain upheaval across whole map
    n = game.terrain.tiles
    for _ in range(30):
        c = random.uniform(0, n)
        r = random.uniform(0, n)
        game.terrain.quake(c, r, radius=5.0)

    # Particle storm
    ps = game.particles
    ren = game.renderer
    for _ in range(20):
        c = random.uniform(0, n)
        r = random.uniform(0, n)
        h = game.terrain.height_at(c, r)
        ps.emit_armageddon(c, r, h, ren.cam_x, ren.cam_y)

    # Kill half of all settlers outright
    for s in game.settlers:
        if s.alive and random.random() < 0.5:
            _kill_settler(game, s)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kill_settler(game: 'Game', settler):
    from renderer import iso
    h = game.terrain.height_at(settler.col, settler.row)
    r = game.renderer
    sx, sy = iso(settler.col, settler.row, h, r.cam_x, r.cam_y)
    game.particles.emit_death(sx, sy, settler.faction)
    settler.hp = 0
    settler.alive = False
    if settler.home:
        settler.home.remove_occupant(settler)


def _quake_camera(game: 'Game', intensity: float):
    game.screen_shake = max(game.screen_shake, intensity)
