"""
Populous Python - Isometric Renderer

Draws the vertex-based heightmap as a coloured isometric landscape
with per-face shading, side walls, and animated water.
"""

import math
import pygame
from typing import Tuple

from constants import (
    SCREEN_W, SCREEN_H, TILE_W, TILE_H, H_SCALE,
    WATER_LEVEL, HUD_H, C_PLAYER, C_ENEMY,
    B_HUT, B_HOUSE, B_MANSION, B_CASTLE,
    PLAYER, ENEMY,
)
from terrain import Terrain

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def _clamp_colour(r, g, b) -> Tuple[int, int, int]:
    return (max(0, min(255, int(r))),
            max(0, min(255, int(g))),
            max(0, min(255, int(b))))

def _shade(colour: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return _clamp_colour(colour[0] * factor, colour[1] * factor, colour[2] * factor)

def terrain_colour(avg_h: float) -> Tuple[int, int, int]:
    """Map average tile height → top-face RGB colour."""
    wl = WATER_LEVEL
    if avg_h <= wl - 1.5:
        t = max(0.0, (avg_h + 1) / (wl - 0.5))
        return _clamp_colour(_lerp(8, 18, t), _lerp(42, 65, t), _lerp(108, 160, t))
    if avg_h <= wl:
        t = (avg_h - (wl - 1.5)) / 1.5
        return _clamp_colour(_lerp(18, 42, t), _lerp(65, 110, t), _lerp(160, 215, t))
    if avg_h <= wl + 1:
        t = avg_h - wl
        return _clamp_colour(_lerp(42, 205, t), _lerp(110, 180, t), _lerp(215, 115, t))
    if avg_h <= wl + 7:
        t = (avg_h - wl - 1) / 6.0
        return _clamp_colour(_lerp(98, 52, t), _lerp(170, 112, t), _lerp(52, 26, t))
    if avg_h <= wl + 12:
        t = (avg_h - wl - 7) / 5.0
        return _clamp_colour(_lerp(105, 130, t), _lerp(97, 120, t), _lerp(87, 110, t))
    t = min(1.0, (avg_h - wl - 12) / 4.0)
    v = _lerp(130, 225, t)
    return _clamp_colour(v, v, v * 1.06)


def water_colour(tick: float) -> Tuple[int, int, int]:
    """Animated water colour."""
    wave = 0.5 + 0.5 * math.sin(tick * 1.8)
    return _clamp_colour(25 + wave * 15, 85 + wave * 20, 190 + wave * 20)


# ---------------------------------------------------------------------------
# Isometric projection
# ---------------------------------------------------------------------------

def iso(col: float, row: float, h: float, cam_x: float, cam_y: float) -> Tuple[int, int]:
    """World (col, row, height) → screen pixel (sx, sy)."""
    sx = (col - row) * (TILE_W // 2) + cam_x
    sy = (col + row) * (TILE_H // 2) - h * H_SCALE + cam_y
    return (int(sx), int(sy))


def screen_to_world(sx: float, sy: float, cam_x: float, cam_y: float,
                    terrain: Terrain) -> Tuple[float, float]:
    """Approximate screen pixel → world (col, row), ignoring height offset."""
    # Invert the flat iso projection (height=0 approximation then refine)
    rx = (sx - cam_x) / (TILE_W // 2)
    ry = (sy - cam_y) / (TILE_H // 2)
    col_f = (rx + ry) / 2.0
    row_f = (ry - rx) / 2.0

    # Refine up to 4 times using the actual height under the cursor
    for _ in range(4):
        h = terrain.height_at(col_f, row_f)
        rx2 = (sx - cam_x) / (TILE_W // 2)
        ry2 = ((sy + h * H_SCALE) - cam_y) / (TILE_H // 2)
        col_f = (rx2 + ry2) / 2.0
        row_f = (ry2 - rx2) / 2.0

    return col_f, row_f


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

class Renderer:
    """Handles all drawing for the game world."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._terrain_surf: pygame.Surface | None = None
        self._last_terrain_dirty = False

        # Default camera: centred on map
        tiles = 64  # VERTS - 1
        self.cam_x = SCREEN_W // 2
        self.cam_y = (SCREEN_H - HUD_H) // 2

        self._tick = 0.0

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def update(self, dt: float):
        self._tick += dt

    def draw_world(self, terrain: Terrain, entities, particles, selected_power: int,
                   cursor_world: Tuple[float, float] | None):
        """Draw everything in the world (terrain + entities + effects)."""
        view_surf = pygame.Surface((SCREEN_W, SCREEN_H - HUD_H))
        view_surf.fill((20, 12, 35))

        self._draw_terrain(view_surf, terrain)
        self._draw_entities(view_surf, terrain, entities)
        self._draw_particles(view_surf, particles)

        if cursor_world is not None:
            self._draw_cursor(view_surf, terrain, cursor_world, selected_power)

        self.screen.blit(view_surf, (0, 0))

    def draw_minimap(self, terrain: Terrain, entities):
        from constants import MINIMAP_SZ
        sz = MINIMAP_SZ
        mm = pygame.Surface((sz, sz))
        tiles = terrain.tiles

        for tr in range(tiles):
            for tc in range(tiles):
                avg = terrain.tile_avg_h(tc, tr)
                c = terrain_colour(avg)
                px = int(tc * sz / tiles)
                py = int(tr * sz / tiles)
                pw = max(1, int(sz / tiles))
                mm.fill(c, (px, py, pw, pw))

        # Draw entities as dots
        for e in entities:
            if not e.alive:
                continue
            px = int(e.col * sz / tiles)
            py = int(e.row * sz / tiles)
            dot_c = C_PLAYER if e.faction == PLAYER else C_ENEMY
            pygame.draw.circle(mm, dot_c, (px, py), 2)

        # Border
        pygame.draw.rect(mm, (200, 200, 200), (0, 0, sz, sz), 1)
        return mm

    # ------------------------------------------------------------------ #
    #  Terrain drawing                                                     #
    # ------------------------------------------------------------------ #

    def _draw_terrain(self, surf: pygame.Surface, terrain: Terrain):
        wl_colour = water_colour(self._tick)
        tiles = terrain.tiles

        # Painter's algorithm: draw back-to-front (low col+row first)
        for s in range(tiles * 2):
            for tc in range(max(0, s - tiles + 1), min(s + 1, tiles)):
                tr = s - tc
                if not (0 <= tr < tiles):
                    continue
                self._draw_tile(surf, terrain, tc, tr, wl_colour)

    def _draw_tile(self, surf, terrain: Terrain, tc: int, tr: int,
                   wl_colour: Tuple[int, int, int]):
        cx, cy = self.cam_x, self.cam_y

        # Four corner vertices
        h_nw = terrain.vertex_h(tc,     tr)
        h_ne = terrain.vertex_h(tc + 1, tr)
        h_se = terrain.vertex_h(tc + 1, tr + 1)
        h_sw = terrain.vertex_h(tc,     tr + 1)
        avg  = (h_nw + h_ne + h_se + h_sw) / 4.0

        s_nw = iso(tc,     tr,     h_nw, cx, cy)
        s_ne = iso(tc + 1, tr,     h_ne, cx, cy)
        s_se = iso(tc + 1, tr + 1, h_se, cx, cy)
        s_sw = iso(tc,     tr + 1, h_sw, cx, cy)

        # Skip if completely off-screen
        xs = (s_nw[0], s_ne[0], s_se[0], s_sw[0])
        ys = (s_nw[1], s_ne[1], s_se[1], s_sw[1])
        if max(xs) < 0 or min(xs) > surf.get_width():
            return
        if max(ys) < 0 or min(ys) > surf.get_height():
            return

        # Pick top-face colour
        if avg <= WATER_LEVEL:
            top_c = wl_colour
        else:
            top_c = terrain_colour(avg)

        # Top face
        pygame.draw.polygon(surf, top_c, [s_nw, s_ne, s_se, s_sw])

        # Outline for crisp look (very subtle)
        if avg > WATER_LEVEL:
            edge_c = _shade(top_c, 0.75)
            pygame.draw.polygon(surf, edge_c, [s_nw, s_ne, s_se, s_sw], 1)

        # --- Side walls (only when above water, facing SW and SE) ---
        if avg > WATER_LEVEL:
            wall_base_sw = iso(tc,     tr,     WATER_LEVEL, cx, cy)
            wall_base_nw = iso(tc,     tr + 1, WATER_LEVEL, cx, cy)
            wall_base_se = iso(tc + 1, tr + 1, WATER_LEVEL, cx, cy)

            # Left (SW-facing) wall: s_nw → s_sw → ground_sw → ground_nw
            left_c = _shade(top_c, 0.62)
            left_pts = [s_nw, s_sw, wall_base_nw, wall_base_sw]
            pygame.draw.polygon(surf, left_c, left_pts)

            # Right (SE-facing) wall: s_sw → s_se → ground_se → ground_sw
            right_c = _shade(top_c, 0.45)
            right_pts = [s_sw, s_se, wall_base_se, wall_base_nw]
            pygame.draw.polygon(surf, right_c, right_pts)

    # ------------------------------------------------------------------ #
    #  Entity drawing                                                      #
    # ------------------------------------------------------------------ #

    def _draw_entities(self, surf: pygame.Surface, terrain: Terrain, entities):
        # Sort by row+col so front entities overdraw back ones
        visible = [e for e in entities if e.alive]
        visible.sort(key=lambda e: e.col + e.row)

        for e in visible:
            h = terrain.height_at(e.col, e.row)
            sx, sy = iso(e.col, e.row, h, self.cam_x, self.cam_y)

            if e.__class__.__name__ == 'Building':
                self._draw_building(surf, e, sx, sy)
            else:
                self._draw_settler(surf, e, sx, sy, h)

    def _draw_settler(self, surf, settler, sx, sy, h):
        col = C_PLAYER if settler.faction == PLAYER else C_ENEMY

        # Shadow
        pygame.draw.ellipse(surf, (0, 0, 0, 80), (sx - 5, sy - 2, 10, 5))

        # Body (simple pixel-art style)
        body_top = sy - 18
        pygame.draw.ellipse(surf, col, (sx - 4, body_top + 8, 8, 10))     # body
        pygame.draw.circle(surf, _shade(col, 1.3), (sx, body_top + 5), 5) # head

        # HP bar
        if settler.hp < settler.max_hp:
            bar_w = 12
            fill = int(bar_w * settler.hp / settler.max_hp)
            pygame.draw.rect(surf, (180, 30, 30), (sx - 6, body_top - 4, bar_w, 3))
            pygame.draw.rect(surf, (60, 220, 80), (sx - 6, body_top - 4, fill, 3))

    def _draw_building(self, surf, building, sx, sy):
        col = C_PLAYER if building.faction == PLAYER else C_ENEMY
        dark = _shade(col, 0.55)
        light = _shade(col, 1.4)

        btype = building.btype
        if btype == B_HUT:
            # Small hut
            pts = [(sx, sy - 14), (sx - 8, sy - 6), (sx - 8, sy + 2),
                   (sx + 8, sy + 2), (sx + 8, sy - 6)]
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, dark, [(sx, sy - 14), (sx - 8, sy - 6), (sx + 8, sy - 6)])
        elif btype == B_HOUSE:
            pts = [(sx, sy - 20), (sx - 12, sy - 10), (sx - 12, sy + 4),
                   (sx + 12, sy + 4), (sx + 12, sy - 10)]
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, dark, [(sx, sy - 20), (sx - 12, sy - 10), (sx + 12, sy - 10)])
        elif btype == B_MANSION:
            pts = [(sx, sy - 28), (sx - 16, sy - 14), (sx - 16, sy + 6),
                   (sx + 16, sy + 6), (sx + 16, sy - 14)]
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, dark, [(sx, sy - 28), (sx - 16, sy - 14), (sx + 16, sy - 14)])
            # Windows
            for wx in (-8, 2):
                pygame.draw.rect(surf, light, (sx + wx, sy - 10, 5, 6))
        else:  # CASTLE
            # Tower silhouette
            pygame.draw.rect(surf, col,  (sx - 16, sy - 30, 32, 34))
            pygame.draw.rect(surf, dark, (sx - 16, sy - 30, 32, 8))  # battlements row
            for tx in range(-14, 16, 8):
                pygame.draw.rect(surf, _shade(col, 1.1), (sx + tx, sy - 38, 5, 10))
            pygame.draw.rect(surf, (20, 10, 5), (sx - 4, sy - 14, 8, 16))  # gate

        # Construction progress ring
        if hasattr(building, 'build_progress') and building.build_progress < 1.0:
            angle = building.build_progress * 360
            pygame.draw.arc(surf, (255, 220, 50),
                            (sx - 14, sy - 14, 28, 28), 0, math.radians(angle), 3)

    # ------------------------------------------------------------------ #
    #  Particles                                                           #
    # ------------------------------------------------------------------ #

    def _draw_particles(self, surf: pygame.Surface, particles):
        for p in particles:
            if not p.alive:
                continue
            sx, sy = int(p.sx), int(p.sy)
            alpha = int(255 * p.life / p.max_life)
            r, g, b = p.colour
            size = max(1, int(p.size))
            if size == 1:
                if 0 <= sx < surf.get_width() and 0 <= sy < surf.get_height():
                    surf.set_at((sx, sy), (r, g, b))
            else:
                pygame.draw.circle(surf, (r, g, b), (sx, sy), size)

    # ------------------------------------------------------------------ #
    #  Cursor highlight                                                    #
    # ------------------------------------------------------------------ #

    def _draw_cursor(self, surf, terrain, cursor_world, power):
        col_f, row_f = cursor_world
        col_i, row_i = int(round(col_f)), int(round(row_f))

        h = terrain.vertex_h(col_i, row_i)
        sx, sy = iso(col_f, row_f, h, self.cam_x, self.cam_y)

        # Power colour hint
        power_colours = {
            0: (100, 200, 100),  # raise - green
            1: (200, 100, 100),  # lower - red
            2: (255, 200, 50),   # quake - yellow
            3: (255, 120, 30),   # volcano - orange
            4: (50, 100, 255),   # flood - blue
            5: (200, 50, 200),   # arma - purple
        }
        c = power_colours.get(power, (200, 200, 200))

        # Pulsing ring
        pulse = 0.6 + 0.4 * math.sin(self._tick * 5)
        r_size = int(18 + pulse * 6)
        pygame.draw.circle(surf, c, (sx, sy), r_size, 2)
        pygame.draw.circle(surf, (*c, 60), (sx, sy), r_size - 4, 1)
