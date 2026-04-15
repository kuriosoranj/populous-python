"""
Populous: The Beginning — Spells
"""

from __future__ import annotations
import math, random
from typing import TYPE_CHECKING
from constants import (
    SP_BLAST,SP_LIGHTNING,SP_LANDBRIDGE,SP_SWAMP,SP_VOLCANO,
    SP_FLATTEN,SP_FIRESTORM,SP_ARMAGEDDON,
    SPELL_COSTS, PLAYER, ENEMY,
)

if TYPE_CHECKING:
    from game import Game


def use_spell(spell_id:int, game:'Game', col:float, row:float,
              col2:float=None, row2:float=None) -> bool:
    cost=SPELL_COSTS[spell_id]
    if game.mana<cost:return False
    game.mana-=cost
    cam=game.renderer.cam

    if spell_id==SP_BLAST:       _blast(game,col,row,cam)
    elif spell_id==SP_LIGHTNING: _lightning(game,col,row,cam)
    elif spell_id==SP_LANDBRIDGE:
        c2=col2 if col2 is not None else col+5
        r2=row2 if row2 is not None else row
        _landbridge(game,col,row,c2,r2,cam)
    elif spell_id==SP_SWAMP:     _swamp(game,col,row,cam)
    elif spell_id==SP_VOLCANO:   _volcano(game,col,row,cam)
    elif spell_id==SP_FLATTEN:   _flatten(game,col,row)
    elif spell_id==SP_FIRESTORM: _firestorm(game,col,row,cam)
    elif spell_id==SP_ARMAGEDDON:_armageddon(game,cam)
    return True


def _blast(game,col,row,cam):
    h=game.terrain.height_at(col,row)
    game.particles.emit_explosion(col,row,h,cam)
    _quake(game,1.8)
    for e in game.settlers+[game.enemy_shaman]:
        if e and e.alive:
            d=math.hypot(e.col-col,e.row-row)
            if d<4:
                e.take_damage(6*(1-d/4))
                if e.alive:
                    angle=math.atan2(e.row-row,e.col-col)
                    e.col+=math.cos(angle)*2;e.row+=math.sin(angle)*2

def _lightning(game,col,row,cam):
    h=game.terrain.height_at(col,row)
    game.particles.emit_lightning(col,row,h,cam)
    _quake(game,2.5)
    candidates=[e for e in game.settlers+[game.enemy_shaman]
                if e and e.alive and e.faction==ENEMY]
    target=None;best=5.0
    for c in candidates:
        d=math.hypot(c.col-col,c.row-row)
        if d<best:best=d;target=c
    if target:
        _emit_death(game,target,cam)
        target.take_damage(target.max_hp*3)

def _landbridge(game,col,row,col2,row2,cam):
    game.terrain.landbridge(col,row,col2,row2)
    _quake(game,1.0)

def _swamp(game,col,row,cam):
    game.terrain.apply_swamp(col,row,radius=4.0)
    h=game.terrain.height_at(col,row)
    game.particles.emit_swamp(col,row,h,cam)

def _volcano(game,col,row,cam):
    game.terrain.volcano_erupt(col,row)
    h=game.terrain.height_at(col,row)
    game.particles.emit_volcano(col,row,h,cam)
    _quake(game,4.5)
    _kill_near(game,col,row,5.0,ENEMY,cam)

def _flatten(game,col,row):
    game.terrain.flatten_area(int(round(col)),int(round(row)),radius=3)
    _quake(game,0.5)

def _firestorm(game,col,row,cam):
    _quake(game,5.5)
    for _ in range(8):
        dc=random.uniform(-6,6);dr=random.uniform(-6,6)
        c2=col+dc;r2=row+dr
        h=game.terrain.height_at(c2,r2)
        game.particles.emit_explosion(c2,r2,h,cam)
        _kill_near(game,c2,r2,2.5,ENEMY,cam)

def _armageddon(game,cam):
    _quake(game,8.0)
    for s in game.settlers:
        if not s.alive:continue
        ef=ENEMY if s.faction==PLAYER else PLAYER
        s.fight_target=None
        for o in game.settlers:
            if o.alive and o.faction==ef:
                if s.fight_target is None or (
                        math.hypot(s.col-o.col,s.row-o.row)<
                        math.hypot(s.col-s.fight_target.col,s.row-s.fight_target.row)):
                    s.fight_target=o
        s.state='fight'
    game.particles.emit_armageddon_flash(cam)

# ---------------------------------------------------------------------------

def _quake(game,intensity):
    game.screen_shake=max(game.screen_shake,intensity)

def _kill_near(game,col,row,radius,faction,cam):
    for e in game.settlers+[game.enemy_shaman,game.player_shaman]:
        if e and e.alive and e.faction==faction:
            if math.hypot(e.col-col,e.row-row)<radius:
                _emit_death(game,e,cam)
                e.take_damage(e.max_hp*3)

def _emit_death(game,entity,cam):
    h=game.terrain.height_at(entity.col,entity.row)
    pt=game.renderer.world_to_screen(entity.col,entity.row,h)
    if pt:game.particles.emit_death(pt[0],pt[1],entity.faction)
