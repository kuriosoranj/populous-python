"""
Populous: The Beginning — Entities

Shaman: hero unit (one per faction, player-controlled / AI-controlled)
Brave:  basic follower — follows shaman, builds huts, fights weakly
Warrior: combat unit — trained at warrior hut, fights aggressively
Firewarrior: ranged unit
Building: structures
"""

from __future__ import annotations
import math, random
from typing import TYPE_CHECKING
from constants import (
    PLAYER, ENEMY,
    SHAMAN_HP, BRAVE_HP, WARRIOR_HP, FIREWARRIOR_HP,
    BRAVE_SPEED, WARRIOR_SPEED, SHAMAN_SPEED, FIREWARRIOR_RANGE,
    FOLLOW_RADIUS, BUILD_RADIUS,
    FIGHT_RANGE, BRAVE_DMG, WARRIOR_DMG, SHAMAN_DMG, FIREWARRIOR_DMG,
    WATER_LEVEL,
    B_HUT, B_GUARD_POST, B_WARRIOR_HUT, B_FIREWARRIOR_HUT,
    BUILDING_CAPACITY, BUILD_TIME,
    TRAIN_TIME,
)
if TYPE_CHECKING:
    from terrain import Terrain

# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

SPAWN_INTERVAL = 22.0

class Building:
    def __init__(self, col, row, faction, btype=B_HUT):
        self.col=float(col); self.row=float(row)
        self.faction=faction; self.btype=btype
        self.alive=True
        self.build_progress=0.0; self.built=False
        self.capacity=BUILDING_CAPACITY.get(btype,0)
        self.occupants=[]
        self.spawn_timer=SPAWN_INTERVAL
        self.train_timer=TRAIN_TIME  # for warrior/fw huts

    @property
    def is_full(self): return len(self.occupants)>=self.capacity

    def update(self, dt, game):
        new=[]
        if not self.built:
            self.build_progress+=dt/BUILD_TIME.get(self.btype,5.0)
            if self.build_progress>=1.0:
                self.build_progress=1.0; self.built=True
            return new

        if self.btype==B_HUT:
            self.spawn_timer-=dt
            if self.spawn_timer<=0:
                self.spawn_timer=SPAWN_INTERVAL
                if not self.is_full:
                    b=Brave(self.col+random.uniform(-1.5,1.5),
                            self.row+random.uniform(-1.5,1.5),self.faction)
                    b.home=self; self.occupants.append(b); new.append(b)
        elif self.btype in (B_WARRIOR_HUT, B_FIREWARRIOR_HUT):
            self.train_timer-=dt
            if self.train_timer<=0:
                self.train_timer=TRAIN_TIME
                # Convert a nearby brave
                for e in game.settlers:
                    if isinstance(e,Brave) and e.alive and e.faction==self.faction:
                        d=math.hypot(e.col-self.col,e.row-self.row)
                        if d<6:
                            e.alive=False
                            if e.home: e.home.remove_occupant(e)
                            if self.btype==B_WARRIOR_HUT:
                                new.append(Warrior(self.col,self.row,self.faction))
                            else:
                                new.append(Firewarrior(self.col,self.row,self.faction))
                            break
        return new

    def remove_occupant(self,s):
        if s in self.occupants: self.occupants.remove(s)

# ---------------------------------------------------------------------------
# Base mixin
# ---------------------------------------------------------------------------

class _Entity:
    faction=PLAYER; alive=True; hp=1.0; max_hp=1.0
    col=0.0; row=0.0; speed=1.0

    def _dist(self,other): return math.hypot(self.col-other.col,self.row-other.row)

    def _nearest(self, seq, max_d):
        best=None; bd=max_d
        for s in seq:
            d=self._dist(s)
            if d<bd: best,bd=s,d
        return best

    def _move_to(self, tc, tr, dt, terrain:'Terrain'):
        dx=tc-self.col; dy=tr-self.row
        dist=math.hypot(dx,dy)
        if dist<0.08: return
        frac=min(1.0,self.speed*dt/dist)
        nc=self.col+dx*frac; nr=self.row+dy*frac
        if terrain.is_above_water(nc,nr):
            if not terrain.is_swamp(nc,nr):
                self.col,self.row=nc,nr
            else:
                # Swamp slows movement
                self.col+=dx*frac*0.25; self.row+=dy*frac*0.25
        else:
            self.col+=dx*frac*0.3; self.row+=dy*frac*0.3
        n=terrain.tiles-1
        self.col=max(1,min(n,self.col)); self.row=max(1,min(n,self.row))

    def take_damage(self,dmg):
        self.hp-=dmg
        if self.hp<=0: self.hp=0; self.alive=False

# ---------------------------------------------------------------------------
# Shaman
# ---------------------------------------------------------------------------

class Shaman(_Entity):
    def __init__(self, col, row, faction):
        self.col=float(col); self.row=float(row)
        self.faction=faction; self.alive=True
        self.hp=SHAMAN_HP; self.max_hp=SHAMAN_HP
        self.speed=SHAMAN_SPEED
        self.target_col=float(col); self.target_row=float(row)
        self.state='idle'
        self._cast_timer=0.0

    @property
    def is_moving(self):
        return math.hypot(self.col-self.target_col,self.row-self.target_row)>0.3

    def send_to(self, col, row):
        self.target_col=float(col); self.target_row=float(row); self.state='move'

    def update(self, dt, terrain:'Terrain', game):
        self._cast_timer-=dt
        if self.state=='move':
            self._move_to(self.target_col,self.target_row,dt,terrain)
            if not self.is_moving: self.state='idle'

        # Attack nearest enemy shaman/settler in range
        enemy_f=ENEMY if self.faction==PLAYER else PLAYER
        enemies=[e for e in game.settlers if e.alive and e.faction==enemy_f]
        target=self._nearest(enemies,FIGHT_RANGE*1.5)
        if target:
            self._move_to(target.col,target.row,dt,terrain)
            if self._dist(target)<FIGHT_RANGE:
                target.take_damage(SHAMAN_DMG*dt)

# ---------------------------------------------------------------------------
# Brave
# ---------------------------------------------------------------------------

_IDLE='idle'; _FOLLOW='follow'; _BUILD='build'; _FIGHT='fight'; _RETURN='return'

class Brave(_Entity):
    def __init__(self, col, row, faction):
        self.col=float(col); self.row=float(row)
        self.faction=faction; self.alive=True
        self.hp=BRAVE_HP; self.max_hp=BRAVE_HP
        self.speed=BRAVE_SPEED
        self.state=_IDLE; self.home=None
        self.build_timer=0.0; self.build_site=None
        self.fight_target=None
        self._think_t=random.uniform(0.3,1.0)
        self._wander_t=0.0
        self.target_col=float(col); self.target_row=float(row)

    def update(self, dt, terrain:'Terrain', game):
        self._think_t-=dt
        nb=None
        if self._think_t<=0:
            self._think_t=random.uniform(0.4,0.9)
            nb=self._think(terrain,game)
        self._act(dt,terrain,game)
        return nb

    def _think(self, terrain, game):
        shaman=game.player_shaman if self.faction==PLAYER else game.enemy_shaman

        # Check enemies
        ef=ENEMY if self.faction==PLAYER else PLAYER
        foes=[e for e in game.settlers+[game.enemy_shaman,game.player_shaman]
              if e and e.alive and e.faction==ef]
        foe=self._nearest(foes, FIGHT_RANGE*2.5)
        if foe:
            self.fight_target=foe; self.state=_FIGHT; return None

        if self.state==_FIGHT and (not self.fight_target or not self.fight_target.alive):
            self.fight_target=None; self.state=_IDLE

        # Follow shaman if nearby
        if shaman and shaman.alive:
            d=self._dist(shaman)
            if d<FOLLOW_RADIUS:
                if shaman.is_moving or d>BUILD_RADIUS*1.5:
                    self.target_col=shaman.col+random.uniform(-2,2)
                    self.target_row=shaman.row+random.uniform(-2,2)
                    self.state=_FOLLOW; return None
                # Shaman has stopped — try to build
                if (terrain.is_above_water(self.col,self.row) and
                    terrain.flatness(int(round(self.col)),int(round(self.row)),1)<=1):
                    no_building=all(math.hypot(b.col-self.col,b.row-self.row)>4
                                    for b in game.buildings if b.alive)
                    if no_building and random.random()<0.35:
                        self.state=_BUILD; self.build_timer=0.0
                        self.build_site=(int(round(self.col)),int(round(self.row)))
                        return None

        # Wander
        self._wander_t-=0.4
        if self._wander_t<=0:
            self._wander_t=random.uniform(2,6)
            a=random.uniform(0,2*math.pi); d=random.uniform(2,7)
            self.target_col=self.col+math.cos(a)*d
            self.target_row=self.row+math.sin(a)*d
            self.state=_IDLE
        return None

    def _act(self, dt, terrain, game):
        if self.state==_FIGHT and self.fight_target and self.fight_target.alive:
            self._move_to(self.fight_target.col,self.fight_target.row,dt,terrain)
            if self._dist(self.fight_target)<FIGHT_RANGE:
                self.fight_target.take_damage(BRAVE_DMG*dt)
            return

        if self.state in (_IDLE,_FOLLOW,_RETURN):
            self._move_to(self.target_col,self.target_row,dt,terrain)

        if self.state==_BUILD and self.build_site:
            bc,br=self.build_site
            terrain.flatten_area(bc,br,radius=1)
            self.build_timer+=0.4
            if self.build_timer>=1.0:
                self.state=_IDLE; self.build_site=None
                b=Building(bc,br,self.faction,B_HUT)
                if self.home is None: self.home=b; b.occupants.append(self)
                return b
        return None

# ---------------------------------------------------------------------------
# Warrior
# ---------------------------------------------------------------------------

class Warrior(_Entity):
    def __init__(self, col, row, faction):
        self.col=float(col); self.row=float(row)
        self.faction=faction; self.alive=True
        self.hp=WARRIOR_HP; self.max_hp=WARRIOR_HP
        self.speed=WARRIOR_SPEED
        self.target_col=float(col); self.target_row=float(row)
        self.fight_target=None
        self._think_t=random.uniform(0.2,0.6)

    def update(self, dt, terrain:'Terrain', game):
        self._think_t-=dt
        if self._think_t<=0:
            self._think_t=random.uniform(0.3,0.7)
            self._think(terrain,game)
        self._act(dt,terrain,game)
        return None

    def _think(self, terrain, game):
        ef=ENEMY if self.faction==PLAYER else PLAYER
        foes=[e for e in game.settlers if e.alive and e.faction==ef]
        sh=game.enemy_shaman if self.faction==PLAYER else game.player_shaman
        if sh and sh.alive: foes.append(sh)
        t=self._nearest(foes,20.0)
        if t: self.fight_target=t; self.target_col=t.col; self.target_row=t.row
        elif self.faction==ENEMY:
            # Follow enemy shaman toward player
            es=game.enemy_shaman
            if es and es.alive:
                self.target_col=es.col+random.uniform(-3,3)
                self.target_row=es.row+random.uniform(-3,3)

    def _act(self, dt, terrain, game):
        if self.fight_target and self.fight_target.alive:
            self._move_to(self.fight_target.col,self.fight_target.row,dt,terrain)
            if self._dist(self.fight_target)<FIGHT_RANGE:
                self.fight_target.take_damage(WARRIOR_DMG*dt)
        else:
            self._move_to(self.target_col,self.target_row,dt,terrain)

# ---------------------------------------------------------------------------
# Firewarrior
# ---------------------------------------------------------------------------

class Firewarrior(_Entity):
    def __init__(self, col, row, faction):
        self.col=float(col); self.row=float(row)
        self.faction=faction; self.alive=True
        self.hp=FIREWARRIOR_HP; self.max_hp=FIREWARRIOR_HP
        self.speed=BRAVE_SPEED
        self.target_col=float(col); self.target_row=float(row)
        self.fight_target=None
        self._shoot_t=0.0; self._think_t=random.uniform(0.3,0.8)

    def update(self, dt, terrain:'Terrain', game):
        self._think_t-=dt; self._shoot_t-=dt
        if self._think_t<=0:
            self._think_t=random.uniform(0.4,0.8)
            ef=ENEMY if self.faction==PLAYER else PLAYER
            foes=[e for e in game.settlers if e.alive and e.faction==ef]
            sh=game.enemy_shaman if self.faction==PLAYER else game.player_shaman
            if sh and sh.alive: foes.append(sh)
            t=self._nearest(foes,FIREWARRIOR_RANGE+4)
            if t: self.fight_target=t

        if self.fight_target and self.fight_target.alive:
            d=self._dist(self.fight_target)
            if d>FIREWARRIOR_RANGE:
                self._move_to(self.fight_target.col,self.fight_target.row,dt,terrain)
            elif self._shoot_t<=0:
                self._shoot_t=1.5
                self.fight_target.take_damage(FIREWARRIOR_DMG)
                # Spawn fire projectile particle
                h=terrain.height_at(self.col,self.row)
                game.particles.emit_fire_bolt(
                    self.col,self.row,h,
                    self.fight_target.col,self.fight_target.row,
                    terrain.height_at(self.fight_target.col,self.fight_target.row),
                    game.renderer.cam_x,game.renderer.cam_y)
        return None
