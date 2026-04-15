"""
Populous: The Beginning — Particle Effects
"""

from __future__ import annotations
import math, random
from typing import Tuple
from renderer import iso


class Particle:
    def __init__(self,sx,sy,vx,vy,colour,life,size=2.0,gravity=0.0):
        self.sx=sx; self.sy=sy
        self.vx=vx; self.vy=vy
        self.colour=colour; self.life=life; self.max_life=life
        self.size=size; self.gravity=gravity; self.alive=True

    def update(self,dt):
        self.sx+=self.vx*dt; self.sy+=self.vy*dt
        self.vy+=self.gravity*dt
        self.vx*=(1-0.9*dt); self.life-=dt
        if self.life<=0: self.alive=False
        self.size=max(0.5,self.size*(0.994**(dt*60)))


class ParticleSystem:
    MAX=2200
    def __init__(self): self.particles=[]

    def update(self,dt):
        for p in self.particles:
            if p.alive: p.update(dt)
        if len(self.particles)>600:
            self.particles=[p for p in self.particles if p.alive]

    @property
    def active(self): return [p for p in self.particles if p.alive]

    def _add(self,p):
        if len(self.particles)<self.MAX: self.particles.append(p)

    # ------------------------------------------------------------------ #

    def emit_volcano(self,col,row,h,cx,cy):
        sx,sy=iso(col,row,h,cx,cy)
        for _ in range(70):
            a=random.uniform(-math.pi,0); sp=random.uniform(80,250)
            vx=math.cos(a)*sp*random.uniform(0.4,1.0); vy=math.sin(a)*sp
            c=_lava()
            self._add(Particle(sx,sy,vx,vy,c,random.uniform(1.0,2.5),
                                random.uniform(2,6),gravity=220))
        for _ in range(30):
            vx=random.uniform(-25,25); vy=random.uniform(-90,-30)
            g=random.randint(80,155)
            self._add(Particle(sx,sy,vx,vy,(g,g,g),random.uniform(1.5,4.0),
                                random.uniform(3,8)))

    def emit_explosion(self,col,row,h,cx,cy):
        sx,sy=iso(col,row,h,cx,cy)
        for _ in range(50):
            a=random.uniform(0,2*math.pi); sp=random.uniform(60,220)
            vx=math.cos(a)*sp; vy=math.sin(a)*sp*0.5
            c=random.choice([(255,200,60),(255,130,30),(255,80,20),(255,255,140)])
            self._add(Particle(sx,sy,vx,vy,c,random.uniform(0.3,0.8),
                                random.uniform(2,5),gravity=80))
        for _ in range(15):
            vx=random.uniform(-30,30); vy=random.uniform(-60,-10)
            g=random.randint(100,180)
            self._add(Particle(sx,sy,vx,vy,(g,g,g),random.uniform(0.4,1.2),
                                random.uniform(2,5)))

    def emit_lightning(self,col,row,h,cx,cy):
        sx,sy=iso(col,row,h,cx,cy)
        # Bolt from sky
        for _ in range(25):
            vx=random.uniform(-20,20); vy=random.uniform(30,150)
            self._add(Particle(sx,sy-200,vx,vy,(200,220,255),
                                random.uniform(0.15,0.4),random.uniform(1,3)))
        # Flash at impact
        for _ in range(30):
            a=random.uniform(0,2*math.pi); sp=random.uniform(30,120)
            self._add(Particle(sx,sy,math.cos(a)*sp,math.sin(a)*sp*0.5,
                                (220,240,255),random.uniform(0.2,0.5),
                                random.uniform(1,4)))

    def emit_swamp(self,col,row,h,cx,cy):
        sx,sy=iso(col,row,h,cx,cy)
        for _ in range(25):
            a=random.uniform(0,2*math.pi); sp=random.uniform(10,50)
            self._add(Particle(sx,sy,math.cos(a)*sp,math.sin(a)*sp*0.3,
                                (60,100,30),random.uniform(0.8,2.0),
                                random.uniform(3,7)))

    def emit_flood(self,col,row,h,cx,cy):
        sx,sy=iso(col,row,h,cx,cy)
        for _ in range(35):
            a=random.uniform(0,2*math.pi); sp=random.uniform(15,80)
            shade=random.randint(50,110)
            c=(shade//4,shade//2,shade+random.randint(80,140))
            self._add(Particle(sx,sy,math.cos(a)*sp,math.sin(a)*sp*0.35,c,
                                random.uniform(0.6,1.8),random.uniform(2,5)))

    def emit_fire_bolt(self,c0,r0,h0,c1,r1,h1,cx,cy):
        sx0,sy0=iso(c0,r0,h0,cx,cy)
        sx1,sy1=iso(c1,r1,h1,cx,cy)
        dx=(sx1-sx0); dy=(sy1-sy0)
        steps=max(3,int(math.hypot(dx,dy)//8))
        for i in range(steps):
            t=i/steps
            px=sx0+dx*t; py=sy0+dy*t
            c=random.choice([(255,160,0),(255,80,0),(255,220,60)])
            self._add(Particle(px,py,random.uniform(-8,8),random.uniform(-8,8),
                                c,random.uniform(0.1,0.3),random.uniform(1.5,3)))

    def emit_quake(self,col,row,h,cx,cy,n=40):
        sx,sy=iso(col,row,h,cx,cy)
        for _ in range(n):
            a=random.uniform(0,2*math.pi); sp=random.uniform(20,100)
            g=random.randint(100,175)
            self._add(Particle(sx,sy,math.cos(a)*sp,math.sin(a)*sp*0.5,
                                (g,g-10,g-20),random.uniform(0.4,1.2),
                                random.uniform(1.5,4)))

    def emit_construction(self,sx,sy):
        for _ in range(10):
            a=random.uniform(0,2*math.pi); sp=random.uniform(10,45)
            self._add(Particle(sx,sy,math.cos(a)*sp,math.sin(a)*sp,
                                (255,215,60),random.uniform(0.3,0.7),
                                random.uniform(1.5,3)))

    def emit_death(self,sx,sy,faction):
        from constants import PLAYER
        c=(80,120,255) if faction==PLAYER else (255,80,80)
        for _ in range(12):
            a=random.uniform(0,2*math.pi); sp=random.uniform(20,65)
            self._add(Particle(sx,sy,math.cos(a)*sp,math.sin(a)*sp,c,
                                random.uniform(0.2,0.5),random.uniform(1,3)))

    def emit_armageddon_flash(self,cx,cy):
        from constants import SCREEN_W,SCREEN_H
        for _ in range(60):
            px=random.uniform(0,SCREEN_W); py=random.uniform(0,SCREEN_H-100)
            r=random.randint(160,220); b=random.randint(200,255)
            self._add(Particle(px,py,random.uniform(-50,50),random.uniform(-80,80),
                                (r,30,b),random.uniform(0.4,1.2),random.uniform(1,5)))


def _lava():
    r=random.random()
    if r<0.5: return (255,random.randint(80,140),20)
    elif r<0.8: return (255,random.randint(30,80),10)
    else: return (220,220,random.randint(60,100))
