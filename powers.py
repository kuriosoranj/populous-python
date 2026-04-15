"""
Populous: The Beginning — Spells

SP_BLAST, SP_LIGHTNING, SP_LANDBRIDGE, SP_SWAMP, SP_VOLCANO,
SP_FLATTEN, SP_FIRESTORM, SP_ARMAGEDDON
"""

from __future__ import annotations
import math, random
from typing import TYPE_CHECKING
from constants import (
    SP_BLAST,SP_LIGHTNING,SP_LANDBRIDGE,SP_SWAMP,SP_VOLCANO,
    SP_FLATTEN,SP_FIRESTORM,SP_ARMAGEDDON,
    SPELL_COSTS, PLAYER, ENEMY,
)
from renderer import iso

if TYPE_CHECKING:
    from game import Game


def use_spell(spell_id:int, game:'Game', col:float, row:float,
              col2:float=None, row2:float=None) -> bool:
    """Cast a spell. Returns True if cast succeeded."""
    cost=SPELL_COSTS[spell_id]
    if game.mana<cost: return False
    game.mana-=cost

    if spell_id==SP_BLAST:       _blast(game,col,row)
    elif spell_id==SP_LIGHTNING: _lightning(game,col,row)
    elif spell_id==SP_LANDBRIDGE:
        c2=col2 if col2 is not None else col+5
        r2=row2 if row2 is not None else row
        _landbridge(game,col,row,c2,r2)
    elif spell_id==SP_SWAMP:     _swamp(game,col,row)
    elif spell_id==SP_VOLCANO:   _volcano(game,col,row)
    elif spell_id==SP_FLATTEN:   _flatten(game,col,row)
    elif spell_id==SP_FIRESTORM: _firestorm(game,col,row)
    elif spell_id==SP_ARMAGEDDON:_armageddon(game)
    return True


# ---------------------------------------------------------------------------

def _blast(game:'Game', col, row):
    """Explosive projectile — knocks back and damages settlers."""
    h=game.terrain.height_at(col,row)
    game.particles.emit_explosion(col,row,h,game.renderer.cam_x,game.renderer.cam_y)
    _quake(game,1.5)
    for e in game.settlers+[game.enemy_shaman]:
        if e and e.alive:
            d=math.hypot(e.col-col,e.row-row)
            if d<4:
                dmg=6*(1-d/4)
                e.take_damage(dmg)
                if e.alive:
                    # Knockback
                    angle=math.atan2(e.row-row,e.col-col)
                    e.col+=math.cos(angle)*2; e.row+=math.sin(angle)*2

def _lightning(game:'Game', col, row):
    """Instant-kill on nearest settler / shaman to the click."""
    h=game.terrain.height_at(col,row)
    sx,sy=iso(col,row,h,game.renderer.cam_x,game.renderer.cam_y)
    game.particles.emit_lightning(col,row,h,game.renderer.cam_x,game.renderer.cam_y)
    _quake(game,2.0)
    ef=ENEMY  # lightning always targets enemy faction when player casts
    candidates=[e for e in game.settlers+[game.enemy_shaman]
                if e and e.alive and e.faction==ef]
    target=None; best=5.0
    for c in candidates:
        d=math.hypot(c.col-col,c.row-row)
        if d<best: best=d; target=c
    if target:
        target.take_damage(target.max_hp*2)  # overkill = certain death
        _emit_death(game,target)

def _landbridge(game:'Game', c0, r0, c1, r1):
    """Raise a line of terrain between two points."""
    game.terrain.landbridge(c0,r0,c1,r1)
    _quake(game,1.0)

def _swamp(game:'Game', col, row):
    """Create a swampy patch that traps followers."""
    game.terrain.apply_swamp(col,row,radius=4.0)
    h=game.terrain.height_at(col,row)
    game.particles.emit_swamp(col,row,h,game.renderer.cam_x,game.renderer.cam_y)

def _volcano(game:'Game', col, row):
    game.terrain.volcano_erupt(col,row)
    h=game.terrain.height_at(col,row)
    game.particles.emit_volcano(col,row,h,game.renderer.cam_x,game.renderer.cam_y)
    _quake(game,4.0)
    _kill_near(game,col,row,5.0,ENEMY)

def _flatten(game:'Game', col, row):
    """Flatten a 3-radius area to average height."""
    game.terrain.flatten_area(int(round(col)),int(round(row)),radius=3)
    _quake(game,0.5)

def _firestorm(game:'Game', col, row):
    """Multiple blasts raining down in an area."""
    _quake(game,5.0)
    for _ in range(8):
        dc=random.uniform(-6,6); dr=random.uniform(-6,6)
        c2=col+dc; r2=row+dr
        h=game.terrain.height_at(c2,r2)
        game.particles.emit_explosion(c2,r2,h,game.renderer.cam_x,game.renderer.cam_y)
        _kill_near(game,c2,r2,2.5,ENEMY)

def _armageddon(game:'Game'):
    """All followers across the map fight to the death."""
    _quake(game,8.0)
    # Force every settler to target the nearest enemy
    for s in game.settlers:
        if not s.alive: continue
        ef=ENEMY if s.faction==PLAYER else PLAYER
        s.fight_target=None
        for o in game.settlers:
            if o.alive and o.faction==ef:
                if s.fight_target is None or (
                        math.hypot(s.col-o.col,s.row-o.row)<
                        math.hypot(s.col-s.fight_target.col,s.row-s.fight_target.row)):
                    s.fight_target=o
        s.state='fight'
    game.particles.emit_armageddon_flash(game.renderer.cam_x,game.renderer.cam_y)

# ---------------------------------------------------------------------------

def _quake(game, intensity):
    game.screen_shake=max(game.screen_shake,intensity)

def _kill_near(game:'Game', col, row, radius, faction):
    for e in game.settlers+[game.enemy_shaman]:
        if e and e.alive and e.faction==faction:
            if math.hypot(e.col-col,e.row-row)<radius:
                _emit_death(game,e)
                e.take_damage(e.max_hp*3)

def _emit_death(game:'Game', entity):
    h=game.terrain.height_at(entity.col,entity.row)
    sx,sy=iso(entity.col,entity.row,h,game.renderer.cam_x,game.renderer.cam_y)
    game.particles.emit_death(sx,sy,entity.faction)
