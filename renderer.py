"""
Populous: The Beginning — 3D Perspective Renderer

True perspective projection matching PTB's low-angle 3D camera.
Camera sits above the terrain looking slightly downward at ~28°.
Terrain quads are sorted back-to-front (painter's algorithm).
"""

import math, random
import pygame
from typing import Tuple

from constants import (
    SCREEN_W, SCREEN_H, HUD_H, VERTS, WATER_LEVEL,
    C_PLAYER, C_ENEMY, PLAYER, ENEMY,
    B_HUT, B_GUARD_POST, B_WARRIOR_HUT, B_FIREWARRIOR_HUT,
)
from terrain import Terrain

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _lerp(a, b, t):  return a + (b - a) * t
def _clamp_c(r,g,b): return (max(0,min(255,int(r))),max(0,min(255,int(g))),max(0,min(255,int(b))))
def _shade(c, f):    return _clamp_c(c[0]*f, c[1]*f, c[2]*f)

def terrain_colour(avg_h: float, shade: float = 1.0) -> Tuple[int,int,int]:
    """PTB-accurate earthy palette."""
    wl = WATER_LEVEL
    if avg_h < wl - 1:
        r,g,b = 22,42,95
    elif avg_h < wl:
        t = (avg_h-(wl-1))
        r,g,b = _lerp(22,32,t),_lerp(42,68,t),_lerp(95,140,t)
    elif avg_h < wl+1:
        t = avg_h-wl
        r,g,b = _lerp(32,155,t),_lerp(68,138,t),_lerp(140,85,t)
    elif avg_h < wl+4:
        t = (avg_h-wl-1)/3
        r,g,b = _lerp(80,70,t),_lerp(100,90,t),_lerp(42,36,t)
    elif avg_h < wl+9:
        t = (avg_h-wl-4)/5
        r,g,b = _lerp(70,62,t),_lerp(90,78,t),_lerp(36,30,t)
    elif avg_h < wl+13:
        t = (avg_h-wl-9)/4
        r,g,b = _lerp(88,105,t),_lerp(78,95,t),_lerp(65,82,t)
    else:
        t = min(1.0,(avg_h-wl-13)/4)
        v = _lerp(115,215,t)
        r,g,b = v,v,v*1.04
    return _clamp_c(r*shade, g*shade, b*shade)

def water_colour(tick: float):
    w = 0.5 + 0.5*math.sin(tick*1.4)
    return _clamp_c(22+w*10, 60+w*16, 148+w*24)

def swamp_colour(): return (55,72,28)

# ---------------------------------------------------------------------------
# 3D Camera
# ---------------------------------------------------------------------------

class Camera3D:
    """
    PTB-style perspective camera.
    x, y = horizontal world position (grid units)
    z    = world-space height (units above world origin)
    yaw  = horizontal rotation (radians; 0 = looking in +Y direction)
    pitch= downward tilt (radians; positive = looking down)
    focal= perspective focal length in pixels
    """
    def __init__(self, x=32.0, y=8.0, z=22.0):
        self.x     = float(x)
        self.y     = float(y)
        self.z     = float(z)
        self.yaw   = 0.0           # facing +Y (south)
        self.pitch = 0.46          # ~26° below horizontal
        self.focal = 380.0
        # Pre-compute trig
        self._update_trig()

    def _update_trig(self):
        self._cy  = math.cos(self.yaw)
        self._sy  = math.sin(self.yaw)
        self._cp  = math.cos(self.pitch)
        self._sp  = math.sin(self.pitch)

    def rotate(self, delta_yaw: float):
        self.yaw = (self.yaw + delta_yaw) % (2*math.pi)
        self._update_trig()

    def move(self, dx_world: float, dy_world: float):
        """Move in the XY plane respecting camera yaw."""
        self.x += dx_world * self._cy - dy_world * self._sy
        self.y += dx_world * self._sy + dy_world * self._cy

    @property
    def forward_vec(self):
        """Unit forward vector in world space."""
        return (self._sy * self._cp,
                self._cy * self._cp,
               -self._sp)


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def project(wx: float, wy: float, wz: float, cam: Camera3D):
    """
    World (wx, wy, wz) → screen (sx, sy).
    Returns None if the point is behind the camera.
    """
    dx = wx - cam.x
    dy = wy - cam.y
    dz = wz - cam.z          # positive = above camera

    # Yaw rotation (horizontal)
    rx  =  dx * cam._cy - dy * cam._sy
    ry  =  dx * cam._sy + dy * cam._cy  # depth before pitch

    # Pitch rotation (vertical tilt)
    fwd =  ry * cam._cp - dz * cam._sp  # forward (depth)
    up  =  ry * cam._sp + dz * cam._cp  # upward

    if fwd <= 0.05:
        return None           # behind camera

    f  = cam.focal / fwd
    sx = SCREEN_W  // 2 + rx  * f
    sy = (SCREEN_H - HUD_H) // 2 - up * f

    return (int(sx), int(sy))


def screen_ray(sx: float, sy: float, cam: Camera3D, terrain: Terrain):
    """Screen pixel → world (col, row) via iterative ray-terrain intersection."""
    # Ray direction in camera space
    rc = (sx - SCREEN_W/2)  / cam.focal
    uc = (sy - (SCREEN_H-HUD_H)/2) / cam.focal   # positive = downward on screen

    # Un-pitch: camera-space (rc, 1.0, -uc) → world-space direction
    # cam space: right=rx, forward=ry, up=rz
    # after pitch un-rotate:
    fwd_cam  =  1.0
    up_cam   = -uc
    fwd_w    =  fwd_cam * cam._cp + up_cam * cam._sp   # world-forward component
    dz_w     = -fwd_cam * cam._sp + up_cam * cam._cp   # world-vertical component

    # Un-yaw
    dx_w = rc  * cam._cy + fwd_w * cam._sy
    dy_w = -rc * cam._sy + fwd_w * cam._cy

    if dz_w >= 0:
        return None   # ray points upward — no ground hit

    col, row = cam.x, cam.y
    for _ in range(6):
        c = max(0, min(terrain.tiles-1, col))
        r = max(0, min(terrain.tiles-1, row))
        h = terrain.height_at(c, r)
        t = (cam.z - h) / (-dz_w + 1e-6)
        col = cam.x + dx_w * t
        row = cam.y + dy_w * t

    return max(0, min(terrain.tiles-1, col)), max(0, min(terrain.tiles-1, row))


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.cam    = Camera3D()
        self._tick  = 0.0
        self._view  = pygame.Surface((SCREEN_W, SCREEN_H - HUD_H))

        # Pre-bake per-tile texture offsets
        rng = random.Random(42)
        tiles = VERTS - 1
        self._tex = {}
        for tr in range(tiles):
            for tc in range(tiles):
                self._tex[(tc, tr)] = [(rng.randint(-6,6), rng.randint(-3,3),
                                        rng.uniform(0.85,1.15)) for _ in range(3)]

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def update(self, dt: float):
        self._tick += dt

    def world_to_screen(self, col: float, row: float, h: float):
        """Convenience: world position → screen pixel (or None)."""
        return project(col, row, h, self.cam)

    def draw_world(self, terrain: Terrain, entities, particles,
                   selected_spell: int, cursor_world, selected_entity=None):
        v = self._view
        self._draw_sky(v)
        self._draw_terrain(v, terrain)
        self._draw_entities(v, terrain, entities, selected_entity)
        self._draw_particles(v, particles)
        if cursor_world:
            self._draw_cursor(v, terrain, cursor_world, selected_spell)
        self.screen.blit(v, (0, 0))

    def draw_minimap(self, terrain: Terrain, entities):
        from constants import MINIMAP_SZ
        sz = MINIMAP_SZ; tiles = terrain.tiles
        mm = pygame.Surface((sz, sz))
        for tr in range(tiles):
            for tc in range(tiles):
                avg = terrain.tile_avg_h(tc, tr)
                mm.fill(terrain_colour(avg),
                        (int(tc*sz/tiles), int(tr*sz/tiles),
                         max(1,int(sz/tiles)), max(1,int(sz/tiles))))
        for e in entities:
            if not e.alive: continue
            px = int(e.col*sz/tiles); py = int(e.row*sz/tiles)
            pygame.draw.circle(mm, C_PLAYER if e.faction==PLAYER else C_ENEMY, (px,py), 2)
        # Camera frustum indicator
        cx = int(self.cam.x*sz/tiles); cy = int(self.cam.y*sz/tiles)
        pygame.draw.circle(mm, (255,255,255), (cx,cy), 3, 1)
        pygame.draw.rect(mm, (200,200,200), (0,0,sz,sz), 1)
        return mm

    # ------------------------------------------------------------------ #
    #  Sky                                                                 #
    # ------------------------------------------------------------------ #

    def _draw_sky(self, surf: pygame.Surface):
        h = surf.get_height()
        horizon = int(h * 0.38)   # horizon line (roughly where terrain meets sky)
        # Sky gradient: deep blue top → hazy light blue at horizon
        for y in range(horizon):
            t = y / max(1, horizon)
            r = int(_lerp(72, 152, t))
            g = int(_lerp(118, 188, t))
            b = int(_lerp(210, 228, t))
            pygame.draw.line(surf, (r,g,b), (0,y), (SCREEN_W,y))
        # Haze band at horizon
        for y in range(horizon, min(horizon+18, h)):
            t = (y - horizon) / 18
            r = int(_lerp(152, 90, t))
            g = int(_lerp(188, 108, t))
            b = int(_lerp(228, 55, t))
            pygame.draw.line(surf, (r,g,b), (0,y), (SCREEN_W,y))

    # ------------------------------------------------------------------ #
    #  Terrain                                                             #
    # ------------------------------------------------------------------ #

    def _draw_terrain(self, surf: pygame.Surface, terrain: Terrain):
        cam   = self.cam
        tiles = terrain.tiles
        wl_c  = water_colour(self._tick)

        # Build list of (depth, tc, tr) and sort farthest-first
        # depth = distance along camera forward direction
        fx, fy, _ = cam.forward_vec
        tile_list = []
        for tr in range(tiles):
            for tc in range(tiles):
                cx = tc + 0.5 - cam.x
                cy = tr + 0.5 - cam.y
                depth = cx*fx + cy*fy
                tile_list.append((depth, tc, tr))

        tile_list.sort(key=lambda x: -x[0])   # far first

        trees_deferred = []

        for depth, tc, tr in tile_list:
            result = self._draw_tile(surf, terrain, tc, tr, wl_c)
            if result:
                trees_deferred.append(result)

        for sx, sy, tt in trees_deferred:
            self._draw_tree(surf, sx, sy, tt)

    def _draw_tile(self, surf, terrain: Terrain, tc: int, tr: int, wl_c):
        cam = self.cam
        h_nw = terrain.vertex_h(tc,   tr)
        h_ne = terrain.vertex_h(tc+1, tr)
        h_se = terrain.vertex_h(tc+1, tr+1)
        h_sw = terrain.vertex_h(tc,   tr+1)
        avg  = (h_nw + h_ne + h_se + h_sw) / 4.0
        shade = terrain.tile_slope_shade(tc, tr) if avg > WATER_LEVEL else 1.0
        is_sw = bool(terrain.swamp[tr,tc] or terrain.swamp[tr,tc+1] or
                     terrain.swamp[tr+1,tc] or terrain.swamp[tr+1,tc+1])

        p_nw = project(tc,   tr,   h_nw/10.0, cam)
        p_ne = project(tc+1, tr,   h_ne/10.0, cam)
        p_se = project(tc+1, tr+1, h_se/10.0, cam)
        p_sw = project(tc,   tr+1, h_sw/10.0, cam)

        # Skip if all behind camera
        pts = [p for p in (p_nw, p_ne, p_se, p_sw) if p is not None]
        if len(pts) < 3:
            return None

        sw, sh = surf.get_size()
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        if max(xs) < 0 or min(xs) > sw or max(ys) < 0 or min(ys) > sh+80:
            return None

        poly = [p for p in (p_nw, p_ne, p_se, p_sw) if p is not None]

        if is_sw:
            col = swamp_colour()
        elif avg <= WATER_LEVEL:
            col = wl_c
        else:
            col = terrain_colour(avg, shade)

        if len(poly) >= 3:
            pygame.draw.polygon(surf, col, poly)

        # Subtle edge lines for definition
        if avg > WATER_LEVEL and len(poly) >= 3:
            edge = _shade(col, 0.72)
            pygame.draw.polygon(surf, edge, poly, 1)

        # Grass texture dots
        if WATER_LEVEL+1 < avg < WATER_LEVEL+9 and not is_sw and len(pts)==4:
            for ox, oy, sf in self._tex.get((tc,tr),()):
                cx2 = (xs[0]+xs[2])//2 + ox
                cy2 = (ys[0]+ys[2])//2 + oy
                if 0<=cx2<sw and 0<=cy2<sh:
                    surf.set_at((cx2,cy2), _shade(col, min(1.35, shade*sf)))

        # Tree on this vertex?
        if terrain.trees[tr,tc] and avg > WATER_LEVEL and p_nw:
            tt = 1 if h_nw > WATER_LEVEL+7 else 0
            return (p_nw[0], p_nw[1], tt)
        return None

    # ------------------------------------------------------------------ #
    #  Trees                                                               #
    # ------------------------------------------------------------------ #

    def _draw_tree(self, surf, sx: int, sy: int, tree_type: int = 0):
        w, h = surf.get_size()
        if sx < -50 or sx > w+50 or sy < -80 or sy > h+20:
            return

        # Estimate scale from screen Y position (perspective scaling)
        raw_scale = max(0.3, min(1.8, (sy + 80) / (h * 0.8)))
        sc = raw_scale

        # Shadow ellipse
        shad = pygame.Surface((int(24*sc), int(8*sc)), pygame.SRCALPHA)
        pygame.draw.ellipse(shad, (0,0,0,55), (0, 0, int(24*sc), int(8*sc)))
        surf.blit(shad, (sx - int(12*sc), sy))

        # Trunk
        tw = max(2, int(4*sc)); th = max(3, int(14*sc))
        pygame.draw.rect(surf, (65, 42, 18), (sx - tw//2, sy - th, tw, th))

        if tree_type == 0:  # tropical layered
            for radius, dy_off, gc in [
                (int(15*sc), int(-10*sc), (32,105,28)),
                (int(13*sc), int(-18*sc), (42,125,35)),
                (int(10*sc), int(-25*sc), (52,145,42)),
                (int(7 *sc), int(-31*sc), (62,162,48)),
            ]:
                pygame.draw.circle(surf, gc, (sx, sy+dy_off), radius)
                hi = _clamp_c(gc[0]+30, gc[1]+28, gc[2]+15)
                pygame.draw.circle(surf, hi, (sx - radius//3, sy+dy_off - radius//3), radius//4)
        else:  # pine / conifer
            for sz2, dy_off, gc in [
                (int(16*sc), int(-10*sc), (28,100,30)),
                (int(13*sc), int(-20*sc), (38,118,38)),
                (int( 9*sc), int(-29*sc), (48,135,44)),
            ]:
                pts = [(sx, sy+dy_off-sz2), (sx-sz2, sy+dy_off+4), (sx+sz2, sy+dy_off+4)]
                pygame.draw.polygon(surf, gc, pts)

    # ------------------------------------------------------------------ #
    #  Entities                                                            #
    # ------------------------------------------------------------------ #

    def _draw_entities(self, surf, terrain: Terrain, entities, selected):
        # Sort by depth (far first so near entities overdraw)
        cam = self.cam
        fx, fy, _ = cam.forward_vec
        alive = [e for e in entities if e.alive]
        alive.sort(key=lambda e: -(e.col-cam.x)*fx - (e.row-cam.y)*fy)

        for e in alive:
            h  = terrain.height_at(e.col, e.row) / 10.0
            pt = project(e.col, e.row, h, cam)
            if pt is None:
                continue
            sx, sy = pt
            if sx < -60 or sx > SCREEN_W+60 or sy < -80 or sy > SCREEN_H:
                continue

            # Perspective scale — entities nearer look bigger
            fwd = ((e.col-cam.x)*cam._sy + (e.row-cam.y)*cam._cy)
            scale = max(0.35, min(2.2, cam.focal / max(1.0, fwd * 18)))

            cls  = e.__class__.__name__
            isel = (e is selected)

            if   cls == 'Building':     self._draw_building(surf, e, sx, sy, scale)
            elif cls == 'Shaman':       self._draw_shaman(surf, e, sx, sy, scale, isel)
            elif cls == 'Brave':        self._draw_brave(surf, e, sx, sy, scale, isel)
            elif cls == 'Warrior':      self._draw_warrior(surf, e, sx, sy, scale, isel)
            elif cls == 'Firewarrior':  self._draw_firewarrior(surf, e, sx, sy, scale, isel)

    def _shadow(self, surf, sx, sy, w, h):
        s = pygame.Surface((w*2, h*2), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0,0,0,65), (0,0,w*2,h*2))
        surf.blit(s, (sx-w, sy-h))

    def _hp_bar(self, surf, sx, sy, hp, max_hp, w=14):
        if hp >= max_hp: return
        bx = sx - w//2
        pygame.draw.rect(surf, (150,25,25), (bx, sy-2, w, 3))
        fill = max(0, int(w * hp / max_hp))
        pygame.draw.rect(surf, (45,210,65), (bx, sy-2, fill, 3))

    def _sel_ring(self, surf, sx, sy, r, col=(255,255,60)):
        pulse = 0.6 + 0.4*math.sin(self._tick*6)
        c = _clamp_c(col[0]*pulse, col[1]*pulse, col[2]*pulse)
        pygame.draw.circle(surf, c, (sx,sy), int(r), 2)

    def _draw_shaman(self, surf, e, sx, sy, sc, sel):
        col   = C_PLAYER if e.faction==PLAYER else C_ENEMY
        light = _clamp_c(col[0]+55, col[1]+55, col[2]+40)
        h_off = int(26*sc)

        self._shadow(surf, sx, sy, int(11*sc), int(5*sc))
        if sel: self._sel_ring(surf, sx, sy, int(18*sc))

        # Robe / cape
        cape = [(sx, sy-int(5*sc)), (sx-int(8*sc), sy+int(7*sc)), (sx+int(8*sc), sy+int(7*sc))]
        pygame.draw.polygon(surf, col, cape)
        # Body
        pygame.draw.rect(surf, col, (sx-int(5*sc), sy-h_off+int(10*sc), int(10*sc), int(14*sc)))
        # Head
        pygame.draw.circle(surf, light, (sx, sy-h_off+int(6*sc)), int(6*sc))
        pygame.draw.circle(surf, (15,10,5), (sx-int(2*sc), sy-h_off+int(5*sc)), int(1*sc))
        pygame.draw.circle(surf, (15,10,5), (sx+int(2*sc), sy-h_off+int(5*sc)), int(1*sc))
        # Staff
        staff_x = sx + int(7*sc)
        pygame.draw.line(surf, (115,85,40), (staff_x, sy-h_off-int(8*sc)), (staff_x, sy+int(5*sc)), max(1,int(2*sc)))
        orb = (210,210,75) if e.faction==PLAYER else (255,115,45)
        orb_y = sy - h_off - int(10*sc)
        pygame.draw.circle(surf, orb, (staff_x, orb_y), int(4*sc))
        # Staff orb glow
        glow = pygame.Surface((int(14*sc), int(14*sc)), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*orb, 70), (int(7*sc), int(7*sc)), int(7*sc))
        surf.blit(glow, (staff_x-int(7*sc), orb_y-int(7*sc)))

        self._hp_bar(surf, sx, sy-h_off-int(12*sc), e.hp, e.max_hp, int(18*sc))

    def _draw_brave(self, surf, e, sx, sy, sc, sel):
        col  = C_PLAYER if e.faction==PLAYER else C_ENEMY
        dark = _shade(col, 0.6)
        h_off= int(18*sc)

        self._shadow(surf, sx, sy, int(8*sc), int(4*sc))
        if sel: self._sel_ring(surf, sx, sy, int(11*sc))

        # Legs
        pygame.draw.line(surf, dark, (sx-int(2*sc), sy), (sx-int(3*sc), sy+int(6*sc)), max(1,int(2*sc)))
        pygame.draw.line(surf, dark, (sx+int(2*sc), sy), (sx+int(3*sc), sy+int(6*sc)), max(1,int(2*sc)))
        # Body
        pygame.draw.rect(surf, col, (sx-int(4*sc), sy-h_off, int(8*sc), int(12*sc)))
        # Head
        pygame.draw.circle(surf, _clamp_c(col[0]+35,col[1]+35,col[2]+20),
                            (sx, sy-h_off-int(5*sc)), int(5*sc))
        # Stick
        pygame.draw.line(surf, (120,90,40),
                         (sx+int(5*sc), sy-h_off-int(6*sc)),
                         (sx+int(4*sc), sy-int(2*sc)), max(1,int(2*sc)))

        self._hp_bar(surf, sx, sy-h_off-int(10*sc), e.hp, e.max_hp, int(12*sc))

        if e.state=='build' and hasattr(e,'build_timer'):
            prog = min(1.0, e.build_timer/5.0)
            pygame.draw.arc(surf, (255,200,0),
                            (sx-int(9*sc), sy-int(9*sc), int(18*sc), int(18*sc)),
                            0, math.radians(prog*360), max(1,int(2*sc)))

    def _draw_warrior(self, surf, e, sx, sy, sc, sel):
        col  = C_PLAYER if e.faction==PLAYER else C_ENEMY
        arm  = (175,162,148)
        h_off= int(22*sc)

        self._shadow(surf, sx, sy, int(10*sc), int(4*sc))
        if sel: self._sel_ring(surf, sx, sy, int(13*sc))

        pygame.draw.line(surf, _shade(col,0.55), (sx-int(3*sc),sy), (sx-int(4*sc),sy+int(7*sc)), max(1,int(2*sc)))
        pygame.draw.line(surf, _shade(col,0.55), (sx+int(3*sc),sy), (sx+int(4*sc),sy+int(7*sc)), max(1,int(2*sc)))
        # Armoured body
        pygame.draw.rect(surf, arm,  (sx-int(6*sc), sy-h_off, int(12*sc), int(15*sc)))
        pygame.draw.rect(surf, col,  (sx-int(5*sc), sy-h_off+int(1*sc), int(10*sc), int(13*sc)))
        # Helmet
        pygame.draw.circle(surf, arm, (sx, sy-h_off-int(5*sc)), int(6*sc))
        pygame.draw.rect(surf, arm,   (sx-int(7*sc), sy-h_off-int(5*sc), int(14*sc), int(4*sc)))
        # Sword
        pygame.draw.line(surf, (195,185,165),
                         (sx+int(6*sc), sy-h_off-int(8*sc)),
                         (sx+int(9*sc), sy+int(2*sc)), max(1,int(3*sc)))
        pygame.draw.rect(surf, (195,185,165),
                         (sx+int(4*sc), sy-h_off-int(9*sc), int(7*sc), int(3*sc)))

        self._hp_bar(surf, sx, sy-h_off-int(12*sc), e.hp, e.max_hp, int(16*sc))

    def _draw_firewarrior(self, surf, e, sx, sy, sc, sel):
        col  = C_PLAYER if e.faction==PLAYER else C_ENEMY
        h_off= int(18*sc)

        self._shadow(surf, sx, sy, int(8*sc), int(4*sc))
        if sel: self._sel_ring(surf, sx, sy, int(11*sc))

        pygame.draw.line(surf, _shade(col,0.6), (sx-int(2*sc),sy), (sx-int(3*sc),sy+int(6*sc)), max(1,int(2*sc)))
        pygame.draw.line(surf, _shade(col,0.6), (sx+int(2*sc),sy), (sx+int(3*sc),sy+int(6*sc)), max(1,int(2*sc)))
        pygame.draw.rect(surf, col, (sx-int(4*sc), sy-h_off, int(8*sc), int(11*sc)))
        pygame.draw.circle(surf, _clamp_c(col[0]+40,col[1]+40,col[2]+20),
                            (sx, sy-h_off-int(4*sc)), int(5*sc))
        torch_x = sx - int(6*sc); torch_y = sy - h_off - int(6*sc)
        pygame.draw.line(surf, (110,82,34), (torch_x, torch_y), (torch_x, sy), max(1,int(2*sc)))
        fc = (255,155,0) if int(self._tick*8)%2==0 else (255,75,0)
        pygame.draw.circle(surf, fc, (torch_x, torch_y-int(3*sc)), max(1,int(3*sc)))

        self._hp_bar(surf, sx, sy-h_off-int(10*sc), e.hp, e.max_hp, int(12*sc))

    def _draw_building(self, surf, b, sx, sy, sc):
        col   = C_PLAYER if b.faction==PLAYER else C_ENEMY
        straw = (178,142,60); straw_d=(138,108,42)
        prog  = b.build_progress

        if b.btype == B_HUT:
            self._draw_hut_3d(surf, sx, sy, sc*prog, col, straw, straw_d)
        elif b.btype == B_GUARD_POST:
            self._draw_tower_3d(surf, sx, sy, sc*prog, col)
        else:
            self._draw_hut_3d(surf, sx, sy, sc*prog, col, straw, straw_d)
            # Banner
            bx = sx + int(12*sc*prog)
            by = sy - int(30*sc*prog)
            pygame.draw.line(surf, (180,160,60), (bx,by), (bx,by+int(16*sc*prog)), max(1,int(2*sc)))
            pygame.draw.polygon(surf, C_ENEMY if b.btype==B_WARRIOR_HUT else (255,140,0),
                                 [(bx,by),(bx+int(9*sc*prog),by+int(4*sc*prog)),(bx,by+int(8*sc*prog))])

        if prog < 1.0:
            r = int(16*sc)
            if r > 2:
                pygame.draw.arc(surf, (255,210,40),
                                (sx-r, sy-r, r*2, r*2), 0, math.radians(prog*360), 3)

    def _draw_hut_3d(self, surf, sx, sy, sc, col, straw, straw_d):
        bw = int(24*sc); bh = int(12*sc); rh = int(22*sc)
        if bw < 4: return

        # Round base
        pygame.draw.ellipse(surf, (148,122,72), (sx-bw//2, sy-bh//2, bw, bh))
        # Walls
        wall = [(sx-bw//2,sy),(sx+bw//2,sy),(sx+bw//3,sy-int(14*sc)),(sx-bw//3,sy-int(14*sc))]
        pygame.draw.polygon(surf, (158,128,78), wall)
        # Faction stripe
        pygame.draw.line(surf, col, (sx-bw//3, sy-int(11*sc)), (sx+bw//3, sy-int(11*sc)), max(1,int(2*sc)))
        # Thatched roof
        roof_y = sy - int(14*sc)
        roof = [(sx, roof_y-rh), (sx-bw//2-4, roof_y), (sx+bw//2+4, roof_y)]
        pygame.draw.polygon(surf, straw, roof)
        # Thatch highlight
        mid = [(sx, roof_y-rh), (sx-int(4*sc), roof_y-int(rh*0.35)), (sx+int(4*sc), roof_y-int(rh*0.35))]
        pygame.draw.polygon(surf, _clamp_c(straw[0]+22,straw[1]+18,straw[2]+8), mid)
        # Thatch lines
        for i in range(1,4):
            t = i/4
            lx0 = int(sx - t*(bw//2+4)); lx1 = int(sx + t*(bw//2+4))
            ly  = int(roof_y - rh*(1-t))
            pygame.draw.line(surf, straw_d, (lx0,ly),(lx1,ly), 1)
        pygame.draw.polygon(surf, straw_d, roof, 1)
        # Door
        pygame.draw.rect(surf, (45,30,12), (sx-int(3*sc), sy-int(10*sc), int(6*sc), int(10*sc)))

    def _draw_tower_3d(self, surf, sx, sy, sc, col):
        tw = int(15*sc); th = int(32*sc)
        if tw < 4: return
        stone = (105,95,82); stone_d=(75,68,58)
        pygame.draw.rect(surf, stone, (sx-tw//2, sy-th, tw, th))
        pygame.draw.rect(surf, col,   (sx-tw//2, sy-th, tw, 4))
        for bx in range(-tw//2, tw//2, max(2,int(6*sc))):
            pygame.draw.rect(surf, stone, (sx+bx, sy-th-int(5*sc), max(2,int(4*sc)), int(5*sc)))
        pygame.draw.rect(surf, (18,12,8), (sx-int(2*sc), sy-th+int(8*sc), int(4*sc), int(8*sc)))

    # ------------------------------------------------------------------ #
    #  Particles                                                           #
    # ------------------------------------------------------------------ #

    def _draw_particles(self, surf, particles):
        sw, sh = surf.get_size()
        for p in particles:
            if not p.alive: continue
            px,py = int(p.sx), int(p.sy)
            sz = max(1, int(p.size))
            if sz==1:
                if 0<=px<sw and 0<=py<sh:
                    surf.set_at((px,py), p.colour)
            else:
                pygame.draw.circle(surf, p.colour, (px,py), sz)

    # ------------------------------------------------------------------ #
    #  Cursor                                                              #
    # ------------------------------------------------------------------ #

    def _draw_cursor(self, surf, terrain: Terrain, cursor_world, spell):
        col_f, row_f = cursor_world
        col_i, row_i = int(round(col_f)), int(round(row_f))
        h = terrain.vertex_h(col_i, row_i) / 10.0
        pt = project(col_f, row_f, h, self.cam)
        if pt is None: return
        sx, sy = pt

        spell_cols = {
            0:(100,220,100), 1:(255,255,80), 2:(150,200,255),
            3:(65,175,65),   4:(255,130,30), 5:(80,200,80),
            6:(255,80,80),   7:(220,60,220),
        }
        c = spell_cols.get(spell, (200,200,200))
        pulse = 0.55 + 0.45*math.sin(self._tick*5)
        r = int(18 + pulse*7)
        pygame.draw.circle(surf, c, (sx,sy), r, 2)
        inner = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(inner, (*c, 38), (r,r), r-3)
        surf.blit(inner, (sx-r, sy-r))
