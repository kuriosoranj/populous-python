"""
Populous: The Beginning — Terrain

Vertex-based heightmap with diamond-square generation, tree map, and swamp map.
"""

import numpy as np
import random
import math
from constants import VERTS, MIN_H, MAX_H, WATER_LEVEL


class Terrain:
    def __init__(self, size: int = VERTS):
        self.size  = size
        self.tiles = size - 1
        self.h     = np.zeros((size, size), dtype=np.int32)
        self.trees  = np.zeros((size, size), dtype=bool)   # tree at vertex
        self.swamp  = np.zeros((size, size), dtype=bool)   # swamp spell effect
        self._dirty = True
        self.generate()

    # ------------------------------------------------------------------ #
    #  Generation                                                          #
    # ------------------------------------------------------------------ #

    def generate(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        sz = self.size  # 65
        grid = np.zeros((sz, sz), dtype=float)

        # seed corners
        for r, c in [(0,0),(0,sz-1),(sz-1,0),(sz-1,sz-1)]:
            grid[r,c] = random.uniform(5, 12)

        step = sz - 1
        roughness = 0.58
        scale = 9.0

        while step > 1:
            half = step // 2
            # Diamond
            for r in range(0, sz-1, step):
                for c in range(0, sz-1, step):
                    avg = (grid[r,c]+grid[r,c+step]+grid[r+step,c]+grid[r+step,c+step])/4
                    grid[r+half, c+half] = avg + random.uniform(-scale, scale)
            # Square
            for r in range(0, sz, half):
                for c in range((r//half)%2*half, sz, step):
                    vals, cnt = 0.0, 0
                    for dr,dc in ((-half,0),(half,0),(0,-half),(0,half)):
                        nr,nc = r+dr,c+dc
                        if 0<=nr<sz and 0<=nc<sz:
                            vals+=grid[nr,nc]; cnt+=1
                    grid[r,c] = vals/cnt + random.uniform(-scale,scale)
            step=half; scale*=roughness

        # Normalise
        lo,hi=grid.min(),grid.max()
        if hi>lo:
            grid=(grid-lo)/(hi-lo)*(MAX_H-2)+2
        self.h[:]=np.clip(np.round(grid),MIN_H,MAX_H).astype(np.int32)
        self._taper_edges()
        self.h=np.clip(self.h,MIN_H,MAX_H).astype(np.int32)
        self._place_trees()
        self._dirty=True

    def _taper_edges(self):
        n=self.size
        margin=n*0.20
        for r in range(n):
            for c in range(n):
                dist=min(r,c,n-1-r,n-1-c)
                if dist<margin:
                    t=(dist/margin)**1.5
                    self.h[r,c]=int(self.h[r,c]*t)

    def _place_trees(self):
        """Scatter trees on mid-height grass tiles."""
        self.trees[:]=False
        n=self.size
        for r in range(n):
            for c in range(n):
                h=self.h[r,c]
                if WATER_LEVEL+1 < h < WATER_LEVEL+9:
                    if random.random()<0.14:
                        self.trees[r,c]=True

    # ------------------------------------------------------------------ #
    #  Queries                                                             #
    # ------------------------------------------------------------------ #

    def vertex_h(self, col:int, row:int)->int:
        return int(self.h[max(0,min(self.size-1,row)), max(0,min(self.size-1,col))])

    def height_at(self, col:float, row:float)->float:
        c0=max(0,min(self.size-2,int(col)))
        r0=max(0,min(self.size-2,int(row)))
        c1,r1=c0+1,r0+1
        fc,fr=col-c0,row-r0
        return (self.h[r0,c0]*(1-fc)*(1-fr)+self.h[r0,c1]*fc*(1-fr)+
                self.h[r1,c0]*(1-fc)*fr+self.h[r1,c1]*fc*fr)

    def tile_avg_h(self,tc:int,tr:int)->float:
        return (self.h[tr,tc]+self.h[tr,tc+1]+self.h[tr+1,tc]+self.h[tr+1,tc+1])/4.0

    def tile_slope_shade(self,tc:int,tr:int)->float:
        """Directional lighting: sun from NE. Returns shade multiplier 0.7-1.25."""
        h_nw=self.h[tr,tc]; h_ne=self.h[tr,tc+1]
        h_sw=self.h[tr+1,tc]; h_se=self.h[tr+1,tc+1]
        dx=(h_ne+h_se)/2-(h_nw+h_sw)/2
        dy=(h_nw+h_ne)/2-(h_sw+h_se)/2
        # Sun from upper-right → sun_x pos, sun_y pos in iso world
        dot=dx*0.6+dy*0.8
        mag=max(0.01,abs(dx)+abs(dy))
        shade=1.0+0.22*dot/mag
        return max(0.70,min(1.25,shade))

    def is_above_water(self,col:float,row:float)->bool:
        return self.height_at(col,row)>WATER_LEVEL+0.3

    def flatness(self,col:int,row:int,radius:int=1)->int:
        n=self.size; vals=[]
        for dr in range(-radius,radius+1):
            for dc in range(-radius,radius+1):
                r,c=row+dr,col+dc
                if 0<=r<n and 0<=c<n: vals.append(self.h[r,c])
        return int(max(vals)-min(vals)) if vals else 99

    def has_tree(self,col:float,row:float)->bool:
        c,r=int(round(col)),int(round(row))
        if 0<=r<self.size and 0<=c<self.size:
            return bool(self.trees[r,c])
        return False

    # ------------------------------------------------------------------ #
    #  Modification                                                        #
    # ------------------------------------------------------------------ #

    def _clamp(self,v)->int: return int(max(MIN_H,min(MAX_H,v)))

    def raise_area(self,col:float,row:float,radius:float=2.5,amount:int=1):
        n=self.size; ri,ci=int(round(row)),int(round(col)); ir=int(math.ceil(radius))
        for dr in range(-ir,ir+1):
            for dc in range(-ir,ir+1):
                r,c=ri+dr,ci+dc
                if 0<=r<n and 0<=c<n:
                    d=math.hypot(dr,dc)
                    if d<=radius:
                        f=1.0-d/(radius+0.001)
                        self.h[r,c]=self._clamp(self.h[r,c]+max(1,round(amount*f)))
                        if self.trees[r,c] and self.h[r,c]>WATER_LEVEL+9:
                            self.trees[r,c]=False
        self._dirty=True

    def lower_area(self,col:float,row:float,radius:float=2.5,amount:int=1):
        n=self.size; ri,ci=int(round(row)),int(round(col)); ir=int(math.ceil(radius))
        for dr in range(-ir,ir+1):
            for dc in range(-ir,ir+1):
                r,c=ri+dr,ci+dc
                if 0<=r<n and 0<=c<n:
                    d=math.hypot(dr,dc)
                    if d<=radius:
                        f=1.0-d/(radius+0.001)
                        self.h[r,c]=self._clamp(self.h[r,c]-max(1,round(amount*f)))
        self._dirty=True

    def flatten_area(self,col:int,row:int,radius:int=1):
        n=self.size; vals,cells=[],[]
        for dr in range(-radius,radius+1):
            for dc in range(-radius,radius+1):
                r,c=row+dr,col+dc
                if 0<=r<n and 0<=c<n:
                    vals.append(self.h[r,c]); cells.append((r,c))
        if vals:
            target=int(round(sum(vals)/len(vals)))
            for r,c in cells:
                self.h[r,c]=self._clamp(target)
                self.trees[r,c]=False
        self._dirty=True

    def landbridge(self,c0:float,r0:float,c1:float,r1:float):
        """Raise a straight line of terrain to form a land bridge."""
        steps=max(2,int(math.hypot(c1-c0,r1-r0)*2))
        for i in range(steps+1):
            t=i/steps
            c=c0+(c1-c0)*t; r=r0+(r1-r0)*t
            self.raise_area(c,r,radius=1.5,amount=2)
        self._dirty=True

    def quake(self,col:float,row:float,radius:float=7.0):
        n=self.size; ri,ci=int(round(row)),int(round(col)); ir=int(math.ceil(radius))
        for dr in range(-ir,ir+1):
            for dc in range(-ir,ir+1):
                r,c=ri+dr,ci+dc
                if 0<=r<n and 0<=c<n:
                    d=math.hypot(dr,dc)
                    if d<=radius:
                        self.h[r,c]=self._clamp(self.h[r,c]+random.randint(-3,3))
        self._dirty=True

    def volcano_erupt(self,col:float,row:float):
        n=self.size; peak=min(MAX_H,int(self.height_at(col,row))+10)
        radius=5.0; ri,ci=int(round(row)),int(round(col)); ir=int(math.ceil(radius))
        for dr in range(-ir,ir+1):
            for dc in range(-ir,ir+1):
                r,c=ri+dr,ci+dc
                if 0<=r<n and 0<=c<n:
                    d=math.hypot(dr,dc)
                    if d<=radius:
                        t=1.0-d/radius
                        target=int(WATER_LEVEL+1+(peak-WATER_LEVEL-1)*t)
                        if target>self.h[r,c]:
                            self.h[r,c]=self._clamp(target)
                            self.trees[r,c]=False
        self._dirty=True

    def flood(self,col:float,row:float,radius:float=8.0):
        n=self.size; ri,ci=int(round(row)),int(round(col)); ir=int(math.ceil(radius))
        for dr in range(-ir,ir+1):
            for dc in range(-ir,ir+1):
                r,c=ri+dr,ci+dc
                if 0<=r<n and 0<=c<n:
                    d=math.hypot(dr,dc)
                    if d<=radius and self.h[r,c]<=WATER_LEVEL+3:
                        self.h[r,c]=self._clamp(self.h[r,c]-2)
        self._dirty=True

    def apply_swamp(self,col:float,row:float,radius:float=4.0):
        n=self.size; ri,ci=int(round(row)),int(round(col)); ir=int(math.ceil(radius))
        for dr in range(-ir,ir+1):
            for dc in range(-ir,ir+1):
                r,c=ri+dr,ci+dc
                if 0<=r<n and 0<=c<n:
                    if math.hypot(dr,dc)<=radius:
                        self.swamp[r,c]=True

    def is_swamp(self,col:float,row:float)->bool:
        c,r=int(round(col)),int(round(row))
        if 0<=r<self.size and 0<=c<self.size:
            return bool(self.swamp[r,c])
        return False
