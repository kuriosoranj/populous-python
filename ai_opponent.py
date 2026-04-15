"""
Populous: The Beginning — Enemy AI
Controls the enemy shaman: moves toward player, uses spells, directs followers.
"""

from __future__ import annotations
import math, random
from typing import TYPE_CHECKING
from constants import (
    ENEMY, PLAYER,
    SP_BLAST,SP_LIGHTNING,SP_VOLCANO,SP_FIRESTORM,SP_FLATTEN,SP_SWAMP,
    SPELL_COSTS, MAX_MANA,
)
if TYPE_CHECKING:
    from game import Game


class AIPlayer:
    def __init__(self):
        self._think_t=random.uniform(6,12)
        self._move_t=random.uniform(3,8)
        self._phase='gather'  # gather → attack → gather

    def update(self,dt,game:'Game'):
        self._think_t-=dt
        self._move_t-=dt

        sh=game.enemy_shaman
        if not sh or not sh.alive: return

        # Periodically move shaman
        if self._move_t<=0:
            self._move_t=random.uniform(4,10)
            self._move_shaman(sh,game)

        if self._think_t<=0:
            self._think_t=random.uniform(5,14)
            self._cast(game)

    def _move_shaman(self,sh,game:'Game'):
        p_sh=game.player_shaman
        p_setl=[s for s in game.settlers if s.faction==PLAYER and s.alive]
        n=game.terrain.tiles

        p=self._phase
        if p=='attack' and (p_sh and p_sh.alive):
            # Move toward player shaman with some offset
            tc=p_sh.col+random.uniform(-5,5)
            tr=p_sh.row+random.uniform(-5,5)
            sh.send_to(tc,tr)
        elif p=='attack' and p_setl:
            t=random.choice(p_setl)
            sh.send_to(t.col+random.uniform(-3,3),t.row+random.uniform(-3,3))
        else:
            # Gather phase: wander near own followers
            e_setl=[s for s in game.settlers if s.faction==ENEMY and s.alive]
            if e_setl:
                s=random.choice(e_setl)
                sh.send_to(s.col+random.uniform(-4,4),s.row+random.uniform(-4,4))
            else:
                sh.send_to(random.uniform(10,n-10),random.uniform(10,n-10))

        # Alternate phases
        if random.random()<0.3:
            self._phase='attack' if self._phase=='gather' else 'gather'

    def _cast(self,game:'Game'):
        mana=game.mana_enemy
        p_sh=game.player_shaman
        p_setl=[s for s in game.settlers if s.faction==PLAYER and s.alive]

        # Pick target — player shaman preferred
        if p_sh and p_sh.alive:
            target_col,target_row=p_sh.col,p_sh.row
        elif p_setl:
            t=max(p_setl,key=lambda s:_density(s,p_setl,5))
            target_col,target_row=t.col,t.row
        else:
            return

        sh=game.enemy_shaman
        dist=math.hypot(sh.col-target_col,sh.row-target_row) if sh else 999

        options=[]
        if mana>=SPELL_COSTS[SP_BLAST] and dist<8:
            options+=[SP_BLAST]*3
        if mana>=SPELL_COSTS[SP_LIGHTNING] and dist<12:
            options+=[SP_LIGHTNING]*2
        if mana>=SPELL_COSTS[SP_SWAMP] and p_setl and dist<15:
            options+=[SP_SWAMP]*2
        if mana>=SPELL_COSTS[SP_VOLCANO]:
            options+=[SP_VOLCANO]
        if mana>=SPELL_COSTS[SP_FIRESTORM] and p_setl:
            options+=[SP_FIRESTORM]
        if mana>=SPELL_COSTS[SP_FLATTEN]:
            # Flatten near own followers to help them build
            e_setl=[s for s in game.settlers if s.faction==ENEMY and s.alive]
            if e_setl:
                t=random.choice(e_setl)
                options+=[('flatten',t.col,t.row)]

        if not options: return
        choice=random.choice(options)

        from powers import use_spell as _use
        if isinstance(choice,tuple):
            # Flatten
            game.mana_enemy-=SPELL_COSTS[SP_FLATTEN]
            game.terrain.flatten_area(int(round(choice[1])),int(round(choice[2])),radius=2)
        else:
            cost=SPELL_COSTS[choice]
            if game.mana_enemy>=cost:
                game.mana_enemy-=cost
                _cast_enemy(choice,target_col,target_row,game)


def _cast_enemy(spell_id,col,row,game:'Game'):
    """Execute the spell effect without deducting mana again."""
    from renderer import iso
    from particles import ParticleSystem
    h=game.terrain.height_at(col,row)
    cx,cy=game.renderer.cam_x,game.renderer.cam_y

    if spell_id==SP_BLAST:
        game.particles.emit_explosion(col,row,h,cx,cy)
        game.screen_shake=max(game.screen_shake,2.0)
        for e in game.settlers+[game.player_shaman]:
            if e and e.alive and e.faction==PLAYER:
                d=math.hypot(e.col-col,e.row-row)
                if d<4: e.take_damage(5*(1-d/4))
    elif spell_id==SP_LIGHTNING:
        game.particles.emit_lightning(col,row,h,cx,cy)
        game.screen_shake=max(game.screen_shake,3.0)
        targets=[e for e in game.settlers+[game.player_shaman]
                 if e and e.alive and e.faction==PLAYER]
        if targets:
            t=min(targets,key=lambda e:math.hypot(e.col-col,e.row-row))
            if math.hypot(t.col-col,t.row-row)<5:
                t.take_damage(t.max_hp*3)
    elif spell_id==SP_SWAMP:
        game.terrain.apply_swamp(col,row,4.0)
        game.particles.emit_swamp(col,row,h,cx,cy)
    elif spell_id==SP_VOLCANO:
        game.terrain.volcano_erupt(col,row)
        game.particles.emit_volcano(col,row,h,cx,cy)
        game.screen_shake=max(game.screen_shake,4.0)
        for e in game.settlers+[game.player_shaman]:
            if e and e.alive and e.faction==PLAYER:
                if math.hypot(e.col-col,e.row-row)<5: e.take_damage(e.max_hp)
    elif spell_id==SP_FIRESTORM:
        game.screen_shake=max(game.screen_shake,4.0)
        for _ in range(6):
            dc,dr=random.uniform(-5,5),random.uniform(-5,5)
            c2,r2=col+dc,row+dr
            h2=game.terrain.height_at(c2,r2)
            game.particles.emit_explosion(c2,r2,h2,cx,cy)
            for e in game.settlers+[game.player_shaman]:
                if e and e.alive and e.faction==PLAYER:
                    if math.hypot(e.col-c2,e.row-r2)<2.5: e.take_damage(4)


def _density(s,group,r):
    return sum(1 for o in group if math.hypot(s.col-o.col,s.row-o.row)<r)
