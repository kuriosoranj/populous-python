"""
Populous: The Beginning — Renderer

Isometric renderer with slope-based lighting, trees, PTB-style building and
character sprites, animated water, and swamp tiles.
"""

import math
import random
import pygame
from typing import Tuple

from constants import (
    SCREEN_W, SCREEN_H, TILE_W, TILE_H, H_SCALE, HUD_H, VERTS,
    WATER_LEVEL, C_PLAYER, C_ENEMY, PLAYER, ENEMY,
    E_SHAMAN, E_BRAVE, E_WARRIOR, E_FIREWARRIOR,
    B_HUT, B_GUARD_POST, B_WARRIOR_HUT, B_FIREWARRIOR_HUT,
)
from terrain import Terrain

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _lerp(a, b, t): return a + (b-a)*t
def _clamp_c(r,g,b): return (max(0,min(255,int(r))),max(0,min(255,int(g))),max(0,min(255,int(b))))
def _shade(c, f): return _clamp_c(c[0]*f, c[1]*f, c[2]*f)

def terrain_colour(avg_h: float, slope_shade: float = 1.0) -> Tuple[int,int,int]:
    wl = WATER_LEVEL
    if avg_h <= wl-2:
        r,g,b = 10,45,115
    elif avg_h <= wl:
        t=(avg_h-(wl-2))/2
        r,g,b=_lerp(10,40,t),_lerp(45,105,t),_lerp(115,210,t)
    elif avg_h <= wl+1:
        t=avg_h-wl
        r,g,b=_lerp(40,210,t),_lerp(105,185,t),_lerp(210,115,t)
    elif avg_h <= wl+5:
        t=(avg_h-wl-1)/4
        r,g,b=_lerp(100,80,t),_lerp(195,165,t),_lerp(70,55,t)
    elif avg_h <= wl+9:
        t=(avg_h-wl-5)/4
        r,g,b=_lerp(80,55,t),_lerp(165,125,t),_lerp(55,38,t)
    elif avg_h <= wl+13:
        t=(avg_h-wl-9)/4
        r,g,b=_lerp(115,100,t),_lerp(105,95,t),_lerp(95,85,t)
    else:
        t=min(1.0,(avg_h-wl-13)/4)
        v=_lerp(130,230,t)
        r,g,b=v,v,v*1.05
    return _clamp_c(r*slope_shade, g*slope_shade, b*slope_shade)

def water_colour(tick: float) -> Tuple[int,int,int]:
    w=0.5+0.5*math.sin(tick*1.5)
    w2=0.5+0.5*math.sin(tick*2.3+1)
    return _clamp_c(18+w*12, 75+w2*18, 185+w*22)

def swamp_colour(avg_h: float) -> Tuple[int,int,int]:
    return _clamp_c(60,80,30)

# ---------------------------------------------------------------------------
# Iso projection
# ---------------------------------------------------------------------------

def iso(col, row, h, cam_x, cam_y):
    sx = (col-row)*(TILE_W//2)+cam_x
    sy = (col+row)*(TILE_H//2)-h*H_SCALE+cam_y
    return (int(sx), int(sy))

def screen_to_world(sx, sy, cam_x, cam_y, terrain: Terrain):
    """Screen pixel → approximate world (col, row)."""
    rx=(sx-cam_x)/(TILE_W//2); ry=(sy-cam_y)/(TILE_H//2)
    col_f=(rx+ry)/2.0; row_f=(ry-rx)/2.0
    for _ in range(5):
        h=terrain.height_at(col_f,row_f)
        ry2=((sy+h*H_SCALE)-cam_y)/(TILE_H//2)
        rx2=(sx-cam_x)/(TILE_W//2)
        col_f=(rx2+ry2)/2.0; row_f=(ry2-rx2)/2.0
    return col_f, row_f

# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.cam_x  = SCREEN_W // 2
        self.cam_y  = (SCREEN_H - HUD_H) // 2
        self._tick  = 0.0

        # Pre-baked per-tile random offsets for texture detail
        tiles = VERTS-1
        rng = random.Random(42)
        self._tile_noise = {}
        for tr in range(tiles):
            for tc in range(tiles):
                self._tile_noise[(tc,tr)] = [
                    (rng.randint(-TILE_W//2, TILE_W//2),
                     rng.randint(-4, 4),
                     rng.randint(160,220)) for _ in range(4)]

    def update(self, dt: float):
        self._tick += dt

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def draw_world(self, terrain: Terrain, entities, particles,
                   selected_spell: int, cursor_world, selected_entity=None):
        view = pygame.Surface((SCREEN_W, SCREEN_H-HUD_H))
        view.fill((8, 6, 20))

        self._draw_terrain(view, terrain)
        self._draw_entities_sorted(view, terrain, entities, selected_entity)
        self._draw_particles(view, particles)
        if cursor_world:
            self._draw_cursor(view, terrain, cursor_world, selected_spell)

        self.screen.blit(view, (0,0))

    def draw_minimap(self, terrain: Terrain, entities):
        from constants import MINIMAP_SZ
        sz=MINIMAP_SZ; tiles=terrain.tiles
        mm=pygame.Surface((sz,sz))
        for tr in range(tiles):
            for tc in range(tiles):
                avg=terrain.tile_avg_h(tc,tr)
                c=terrain_colour(avg)
                px=int(tc*sz/tiles); py=int(tr*sz/tiles)
                pw=max(1,int(sz/tiles))
                mm.fill(c,(px,py,pw,pw))
        for e in entities:
            if not e.alive: continue
            px=int(e.col*sz/tiles); py=int(e.row*sz/tiles)
            dc=C_PLAYER if e.faction==PLAYER else C_ENEMY
            pygame.draw.circle(mm,dc,(px,py),2)
        pygame.draw.rect(mm,(180,180,180),(0,0,sz,sz),1)
        return mm

    # ------------------------------------------------------------------ #
    #  Terrain                                                             #
    # ------------------------------------------------------------------ #

    def _draw_terrain(self, surf: pygame.Surface, terrain: Terrain):
        wl_c = water_colour(self._tick)
        tiles = terrain.tiles
        trees_to_draw = []  # collect (sx,sy,h,tree_type) for painter-order

        for s in range(tiles*2):
            for tc in range(max(0,s-tiles+1), min(s+1,tiles)):
                tr=s-tc
                if not (0<=tr<tiles): continue
                tree_screen = self._draw_tile(surf, terrain, tc, tr, wl_c)
                if tree_screen:
                    trees_to_draw.append(tree_screen)

        # Draw trees after all ground tiles
        for sx,sy,h,tt in trees_to_draw:
            self._draw_tree(surf, sx, sy, tt)

    def _draw_tile(self, surf, terrain: Terrain, tc:int, tr:int,
                   wl_c) -> tuple | None:
        cx,cy=self.cam_x,self.cam_y

        h_nw=terrain.vertex_h(tc,   tr)
        h_ne=terrain.vertex_h(tc+1, tr)
        h_se=terrain.vertex_h(tc+1, tr+1)
        h_sw=terrain.vertex_h(tc,   tr+1)
        avg=(h_nw+h_ne+h_se+h_sw)/4.0
        ss=terrain.tile_slope_shade(tc,tr) if avg>WATER_LEVEL else 1.0
        is_sw=terrain.swamp[tr,tc] or terrain.swamp[tr,tc+1] or \
              terrain.swamp[tr+1,tc] or terrain.swamp[tr+1,tc+1]

        s_nw=iso(tc,   tr,   h_nw,cx,cy)
        s_ne=iso(tc+1, tr,   h_ne,cx,cy)
        s_se=iso(tc+1, tr+1, h_se,cx,cy)
        s_sw=iso(tc,   tr+1, h_sw,cx,cy)

        # Cull offscreen
        xs=(s_nw[0],s_ne[0],s_se[0],s_sw[0])
        ys=(s_nw[1],s_ne[1],s_se[1],s_sw[1])
        sw,sh=surf.get_size()
        if max(xs)<0 or min(xs)>sw or max(ys)<0 or min(ys)>sh:
            return None

        # Choose top colour
        if is_sw:
            top_c=swamp_colour(avg)
        elif avg<=WATER_LEVEL:
            top_c=wl_c
        else:
            top_c=terrain_colour(avg, ss)

        # Top face
        pygame.draw.polygon(surf, top_c, [s_nw,s_ne,s_se,s_sw])

        # Grass texture dots (mid-level tiles)
        if WATER_LEVEL+1<avg<WATER_LEVEL+10 and not is_sw:
            noise=self._tile_noise.get((tc,tr),[])
            cx_tile=(s_nw[0]+s_se[0])//2; cy_tile=(s_nw[1]+s_se[1])//2
            for ox,oy,bri in noise:
                px=cx_tile+ox//4; py=cy_tile+oy
                if 0<=px<sw and 0<=py<sh:
                    lighter=_shade(top_c,min(1.4,ss*1.1))
                    surf.set_at((px,py), lighter)

        # Side walls
        if avg>WATER_LEVEL:
            wl=WATER_LEVEL
            wl_nw=iso(tc,   tr,   wl,cx,cy)
            wl_sw=iso(tc,   tr+1, wl,cx,cy)
            wl_se=iso(tc+1, tr+1, wl,cx,cy)

            left_c =_shade(top_c,0.58)
            right_c=_shade(top_c,0.40)
            pygame.draw.polygon(surf,left_c, [s_nw,s_sw,wl_sw,wl_nw])
            pygame.draw.polygon(surf,right_c,[s_sw,s_se,wl_se,wl_sw])

        # Swamp tint overlay
        if is_sw and avg>WATER_LEVEL:
            tint=pygame.Surface((sw,sh),pygame.SRCALPHA)
            pygame.draw.polygon(tint,(40,80,10,60),[s_nw,s_ne,s_se,s_sw])
            surf.blit(tint,(0,0))

        # Tree on this tile vertex?
        has_tree_here=terrain.trees[tr,tc]
        if has_tree_here and avg>WATER_LEVEL:
            h_here=terrain.vertex_h(tc,tr)
            sx,sy=iso(tc,tr,h_here,cx,cy)
            tt=0 if h_here<WATER_LEVEL+6 else 1
            return (sx,sy,h_here,tt)
        return None

    # ------------------------------------------------------------------ #
    #  Trees                                                               #
    # ------------------------------------------------------------------ #

    def _draw_tree(self, surf, sx:int, sy:int, tree_type:int=0):
        w,h=surf.get_size()
        if sx<-40 or sx>w+40 or sy<-60 or sy>h+10: return

        # Shadow
        shad=pygame.Surface((22,8),pygame.SRCALPHA)
        pygame.draw.ellipse(shad,(0,0,0,60),(0,0,22,8))
        surf.blit(shad,(sx-11,sy+1))

        # Trunk
        trunk_col=(75,48,22)
        pygame.draw.rect(surf,trunk_col,(sx-2,sy-12,4,13))

        if tree_type==0:  # Lush tropical round tree
            layers=[
                ((sx,sy-10), 14, (28,118,32)),
                ((sx-2,sy-17), 12, (38,138,42)),
                ((sx+1,sy-22), 10, (50,158,48)),
                ((sx-1,sy-28),  7, (62,170,55)),
            ]
            for (lx,ly),lr,lc in layers:
                pygame.draw.circle(surf,lc,(lx,ly),lr)
                hi=_clamp_c(lc[0]+35,lc[1]+35,lc[2]+20)
                pygame.draw.circle(surf,hi,(lx-lr//3,ly-lr//3),lr//3)
        else:  # Pine/conifer (higher altitude)
            for i,(sz2,gc) in enumerate([(15,(35,115,35)),(12,(45,135,40)),(8,(55,155,45))]):
                ty=sy-12-i*9
                pts=[(sx,ty-sz2),(sx-sz2,ty+4),(sx+sz2,ty+4)]
                pygame.draw.polygon(surf,gc,pts)
                hi=_clamp_c(gc[0]+30,gc[1]+30,gc[2]+15)
                pygame.draw.polygon(surf,hi,pts,1)

    # ------------------------------------------------------------------ #
    #  Entities                                                            #
    # ------------------------------------------------------------------ #

    def _draw_entities_sorted(self, surf, terrain: Terrain, entities, selected):
        alive=[e for e in entities if e.alive]
        alive.sort(key=lambda e:e.col+e.row)
        for e in alive:
            h=terrain.height_at(e.col,e.row)
            sx,sy=iso(e.col,e.row,h,self.cam_x,self.cam_y)
            cls=e.__class__.__name__
            is_sel=(e is selected)
            if cls=='Building':
                self._draw_building(surf,e,sx,sy)
            elif cls=='Shaman':
                self._draw_shaman(surf,e,sx,sy,is_sel)
            elif cls=='Brave':
                self._draw_brave(surf,e,sx,sy,is_sel)
            elif cls=='Warrior':
                self._draw_warrior(surf,e,sx,sy,is_sel)
            elif cls=='Firewarrior':
                self._draw_firewarrior(surf,e,sx,sy,is_sel)

    def _shadow(self,surf,sx,sy,w=10,h=5):
        s=pygame.Surface((w*2,h*2),pygame.SRCALPHA)
        pygame.draw.ellipse(s,(0,0,0,70),(0,0,w*2,h*2))
        surf.blit(s,(sx-w,sy-h))

    def _hp_bar(self,surf,sx,sy,hp,max_hp,width=14):
        if hp>=max_hp: return
        bx=sx-width//2; by=sy-2
        pygame.draw.rect(surf,(160,30,30),(bx,by,width,3))
        f=max(0,int(width*hp/max_hp))
        pygame.draw.rect(surf,(50,210,70),(bx,by,f,3))

    def _sel_ring(self,surf,sx,sy,r=14):
        pulse=0.6+0.4*math.sin(self._tick*6)
        c=_clamp_c(255*pulse,255*pulse,80*pulse)
        pygame.draw.circle(surf,c,(sx,sy),r,2)

    def _draw_shaman(self,surf,e,sx,sy,selected):
        col=C_PLAYER if e.faction==PLAYER else C_ENEMY
        dark=_shade(col,0.5); light=_clamp_c(col[0]+60,col[1]+60,col[2]+40)

        self._shadow(surf,sx,sy,12,5)
        if selected: self._sel_ring(surf,sx,sy,18)

        # Cape/robe
        cape_pts=[(sx,sy-6),(sx-7,sy+6),(sx+7,sy+6)]
        pygame.draw.polygon(surf,col,cape_pts)
        # Body
        pygame.draw.rect(surf,col,(sx-5,sy-14,10,12))
        # Head
        pygame.draw.circle(surf,light,(sx,sy-18),6)
        # Eyes
        pygame.draw.circle(surf,(10,10,10),(sx-2,sy-19),1)
        pygame.draw.circle(surf,(10,10,10),(sx+2,sy-19),1)
        # Staff
        pygame.draw.line(surf,(130,100,50),(sx+6,sy-20),(sx+6,sy+4),2)
        orb_c=(200,200,80) if e.faction==PLAYER else (255,120,50)
        pygame.draw.circle(surf,orb_c,(sx+6,sy-22),4)
        glow=pygame.Surface((12,12),pygame.SRCALPHA)
        pygame.draw.circle(glow,(*orb_c,80),(6,6),6)
        surf.blit(glow,(sx,sy-28))

        self._hp_bar(surf,sx,sy-28,e.hp,e.max_hp,18)

    def _draw_brave(self,surf,e,sx,sy,selected):
        col=C_PLAYER if e.faction==PLAYER else C_ENEMY
        dark=_shade(col,0.6)

        self._shadow(surf,sx,sy)
        if selected: self._sel_ring(surf,sx,sy,10)

        # Legs
        pygame.draw.line(surf,dark,(sx-2,sy),(sx-3,sy+6),2)
        pygame.draw.line(surf,dark,(sx+2,sy),(sx+3,sy+6),2)
        # Body
        pygame.draw.rect(surf,col,(sx-4,sy-12,8,10))
        # Head
        pygame.draw.circle(surf,_clamp_c(col[0]+40,col[1]+40,col[2]+20),(sx,sy-16),5)
        # Simple tool (digging stick)
        pygame.draw.line(surf,(140,100,50),(sx+4,sy-18),(sx+4,sy-6),2)

        self._hp_bar(surf,sx,sy-22,e.hp,e.max_hp)

        # Building progress ring
        if e.state=='build' and hasattr(e,'build_timer'):
            prog=min(1.0,e.build_timer/5.0)
            pygame.draw.arc(surf,(255,200,0),(sx-8,sy-8,16,16),
                            0,math.radians(prog*360),2)

    def _draw_warrior(self,surf,e,sx,sy,selected):
        col=C_PLAYER if e.faction==PLAYER else C_ENEMY
        dark=_shade(col,0.55); arm_c=(180,170,155)

        self._shadow(surf,sx,sy,11,5)
        if selected: self._sel_ring(surf,sx,sy,12)

        # Legs (wider stance)
        pygame.draw.line(surf,dark,(sx-3,sy),(sx-4,sy+7),2)
        pygame.draw.line(surf,dark,(sx+3,sy),(sx+4,sy+7),2)
        # Armoured body
        pygame.draw.rect(surf,arm_c,(sx-5,sy-14,10,13))
        pygame.draw.rect(surf,col,(sx-4,sy-13,8,11))
        # Helmet
        pygame.draw.circle(surf,arm_c,(sx,sy-18),6)
        pygame.draw.rect(surf,arm_c,(sx-6,sy-18,12,4))
        # Sword / club
        pygame.draw.line(surf,(200,190,170),(sx+5,sy-20),(sx+8,sy+2),3)
        pygame.draw.rect(surf,(200,190,170),(sx+3,sy-22,6,3))

        self._hp_bar(surf,sx,sy-26,e.hp,e.max_hp,16)

    def _draw_firewarrior(self,surf,e,sx,sy,selected):
        col=C_PLAYER if e.faction==PLAYER else C_ENEMY

        self._shadow(surf,sx,sy,10,4)
        if selected: self._sel_ring(surf,sx,sy,11)

        pygame.draw.line(surf,_shade(col,0.6),(sx-2,sy),(sx-3,sy+6),2)
        pygame.draw.line(surf,_shade(col,0.6),(sx+2,sy),(sx+3,sy+6),2)
        pygame.draw.rect(surf,col,(sx-4,sy-13,8,11))
        pygame.draw.circle(surf,_clamp_c(col[0]+40,col[1]+40,col[2]+20),(sx,sy-17),5)
        # Torch
        pygame.draw.line(surf,(120,90,40),(sx-6,sy-18),(sx-6,sy-6),2)
        flame_c=(255,160,0) if (int(self._tick*8)+id(e))%2==0 else (255,80,0)
        pygame.draw.circle(surf,flame_c,(sx-6,sy-20),3)

        self._hp_bar(surf,sx,sy-24,e.hp,e.max_hp)

    def _draw_building(self,surf,building,sx,sy):
        col=C_PLAYER if building.faction==PLAYER else C_ENEMY
        dark=_shade(col,0.5); straw=(185,150,65); straw_d=(145,115,45)

        prog=building.build_progress
        scale=0.6+0.4*prog

        btype=building.btype
        if btype==B_HUT:
            self._draw_hut(surf,sx,sy,col,straw,straw_d,scale)
        elif btype==B_GUARD_POST:
            self._draw_guard_post(surf,sx,sy,col,scale)
        elif btype==B_WARRIOR_HUT:
            self._draw_hut(surf,sx,sy,col,straw,straw_d,scale)
            # Red banner
            pygame.draw.line(surf,(220,30,30),(sx+10,sy-28),(sx+10,sy-16),2)
            pygame.draw.polygon(surf,(220,30,30),[(sx+10,sy-28),(sx+16,sy-25),(sx+10,sy-22)])
        elif btype==B_FIREWARRIOR_HUT:
            self._draw_hut(surf,sx,sy,col,straw,straw_d,scale)
            pygame.draw.circle(surf,(255,140,0),(sx+12,sy-28),4)

        if prog<1.0:
            pygame.draw.arc(surf,(255,210,40),(sx-14,sy-14,28,28),
                            0,math.radians(prog*360),3)

    def _draw_hut(self,surf,sx,sy,col,straw,straw_d,scale):
        bw=int(22*scale); bh=int(11*scale); rh=int(20*scale)

        # Base ring (round hut footprint)
        pygame.draw.ellipse(surf,(160,130,75),(sx-bw//2,sy-bh//2,bw,bh))

        # Walls
        wall_pts=[(sx-bw//2,sy),(sx+bw//2,sy),(sx+bw//3,sy-int(13*scale)),(sx-bw//3,sy-int(13*scale))]
        pygame.draw.polygon(surf,(165,135,80),wall_pts)
        # Faction stripe on wall
        pygame.draw.line(surf,col,(sx-bw//3,sy-int(10*scale)),(sx+bw//3,sy-int(10*scale)),2)

        # Thatched roof
        roof_y=sy-int(13*scale)
        roof_pts=[(sx,roof_y-rh),(sx-bw//2-4,roof_y),(sx+bw//2+4,roof_y)]
        pygame.draw.polygon(surf,straw,roof_pts)
        # Shading on roof
        mid_pts=[(sx,roof_y-rh),(sx-4,roof_y-int(rh*0.4)),(sx+4,roof_y-int(rh*0.4))]
        pygame.draw.polygon(surf,_clamp_c(straw[0]+25,straw[1]+20,straw[2]+10),mid_pts)
        # Thatch lines
        for i in range(1,4):
            t=i/4
            lx0=int(sx-t*(bw//2+4)); lx1=int(sx+t*(bw//2+4))
            ly=int(roof_y-rh*(1-t))
            pygame.draw.line(surf,straw_d,(lx0,ly),(lx1,ly),1)
        pygame.draw.polygon(surf,straw_d,roof_pts,1)

        # Door
        pygame.draw.rect(surf,(50,35,15),(sx-3,sy-int(10*scale),6,int(10*scale)))

    def _draw_guard_post(self,surf,sx,sy,col,scale):
        tw=int(14*scale); th=int(30*scale)
        stone=(110,100,90); stone_d=(80,72,65)
        # Tower body
        pygame.draw.rect(surf,stone,(sx-tw//2,sy-th,tw,th))
        pygame.draw.rect(surf,col,(sx-tw//2,sy-th,tw,4))
        # Battlements
        for bx in range(-tw//2,tw//2,6):
            pygame.draw.rect(surf,stone,(sx+bx,sy-th-5,4,6))
        # Arrow slit
        pygame.draw.rect(surf,(20,15,10),(sx-1,sy-th+8,2,6))

    # ------------------------------------------------------------------ #
    #  Particles                                                           #
    # ------------------------------------------------------------------ #

    def _draw_particles(self,surf,particles):
        sw,sh=surf.get_size()
        for p in particles:
            if not p.alive: continue
            px,py=int(p.sx),int(p.sy)
            sz=max(1,int(p.size))
            if sz==1:
                if 0<=px<sw and 0<=py<sh:
                    surf.set_at((px,py),p.colour)
            else:
                pygame.draw.circle(surf,p.colour,(px,py),sz)

    # ------------------------------------------------------------------ #
    #  Cursor / selection                                                  #
    # ------------------------------------------------------------------ #

    def _draw_cursor(self,surf,terrain,cursor_world,spell):
        col_f,row_f=cursor_world
        col_i,row_i=int(round(col_f)),int(round(row_f))
        h=terrain.vertex_h(col_i,row_i)
        sx,sy=iso(col_f,row_f,h,self.cam_x,self.cam_y)

        spell_cols={
            0:(100,220,100),1:(255,255,80),2:(150,200,255),
            3:(60,180,60),4:(255,130,30),5:(80,200,80),
            6:(255,80,80),7:(220,60,220),
        }
        c=spell_cols.get(spell,(200,200,200))
        pulse=0.55+0.45*math.sin(self._tick*5)
        r=int(20+pulse*6)
        pygame.draw.circle(surf,c,(sx,sy),r,2)
        inner=pygame.Surface((r*2,r*2),pygame.SRCALPHA)
        pygame.draw.circle(inner,(*c,40),(r,r),r-3)
        surf.blit(inner,(sx-r,sy-r))
