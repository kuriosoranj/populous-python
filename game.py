"""
Populous Python - Main Game Logic
"""

from __future__ import annotations

import math
import random
import sys
import pygame

from constants import (
    SCREEN_W, SCREEN_H, FPS, TITLE, HUD_H,
    PLAYER, ENEMY,
    P_RAISE, P_LOWER, P_QUAKE, P_VOLCANO, P_FLOOD, P_ARMA,
    POWER_NAMES, MAX_MANA, MANA_RATE,
    VERTS,
)
from terrain import Terrain
from renderer import Renderer, iso, screen_to_world
from entities import Settler, Building, B_HUT, B_CASTLE
from particles import ParticleSystem
from powers import use_power
from ai_opponent import AIPlayer
from ui import HUD, VictoryScreen


# ---------------------------------------------------------------------------
# Initial settler placement
# ---------------------------------------------------------------------------

def _find_start(terrain: Terrain, col_hint: int, row_hint: int) -> tuple[int, int]:
    """Find a good above-water flat-ish tile near the hint location."""
    for radius in range(1, 15):
        for _ in range(30):
            c = col_hint + random.randint(-radius, radius)
            r = row_hint + random.randint(-radius, radius)
            if (0 < c < terrain.tiles and 0 < r < terrain.tiles and
                    terrain.is_above_water(c, r)):
                return c, r
    return col_hint, row_hint


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Game:
    """Top-level game object: owns all state and drives the main loop."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._running = True
        self.game_over = False
        self.winner: int | None = None

        self._new_game()

    # ------------------------------------------------------------------ #
    #  Initialise / restart                                                #
    # ------------------------------------------------------------------ #

    def _new_game(self):
        self.terrain    = Terrain(VERTS)
        self.renderer   = Renderer(self.screen)
        self.particles  = ParticleSystem()
        self.hud        = HUD(self.screen)
        self.victory    = VictoryScreen(self.screen)
        self.ai         = AIPlayer()

        self.mana        = 50.0
        self.mana_enemy  = 50.0
        self.selected_power = P_RAISE
        self.screen_shake   = 0.0

        self.settlers:  list[Settler]  = []
        self.buildings: list[Building] = []

        self.game_over = False
        self.winner    = None

        # Centre camera on map
        mid = self.terrain.tiles // 2
        self.renderer.cam_x = SCREEN_W // 2
        self.renderer.cam_y = (SCREEN_H - HUD_H) // 2

        self._spawn_initial_tribes()
        self._scroll_speed = 300   # pixels/sec
        self._zoom = 1.0
        self._cursor_world: tuple[float, float] | None = None

    def _spawn_initial_tribes(self):
        n = self.terrain.tiles
        # Player starts top-left quadrant, enemy bottom-right
        pc, pr = _find_start(self.terrain, n // 4, n // 4)
        ec, er = _find_start(self.terrain, 3 * n // 4, 3 * n // 4)

        # Give each side a starting castle
        pb = Building(pc, pr, PLAYER, B_CASTLE)
        pb.built = True
        pb.build_progress = 1.0
        self.buildings.append(pb)

        eb = Building(ec, er, ENEMY, B_CASTLE)
        eb.built = True
        eb.build_progress = 1.0
        self.buildings.append(eb)

        # Starting settlers
        for _ in range(6):
            self.settlers.append(Settler(
                pc + random.uniform(-3, 3),
                pr + random.uniform(-3, 3),
                PLAYER))
        for _ in range(6):
            self.settlers.append(Settler(
                ec + random.uniform(-3, 3),
                er + random.uniform(-3, 3),
                ENEMY))

        # Point camera at player start
        sx, sy = iso(pc, pr, self.terrain.height_at(pc, pr),
                     self.renderer.cam_x, self.renderer.cam_y)
        # Camera offset so player is centred
        self.renderer.cam_x += (SCREEN_W // 2) - sx
        self.renderer.cam_y += ((SCREEN_H - HUD_H) // 2) - sy

    # ------------------------------------------------------------------ #
    #  Main loop                                                           #
    # ------------------------------------------------------------------ #

    def run(self):
        clock = pygame.time.Clock()
        while self._running:
            dt = clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)   # cap at 50 ms to avoid spiral of death

            for event in pygame.event.get():
                self._handle_event(event)

            if not self.game_over:
                self._update(dt)

            self._draw()
            pygame.display.flip()

    # ------------------------------------------------------------------ #
    #  Events                                                              #
    # ------------------------------------------------------------------ #

    def _handle_event(self, event: pygame.event.Event):
        if event.type == pygame.QUIT:
            self._running = False

        elif event.type == pygame.KEYDOWN:
            self._handle_key(event.key, event.mod)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_down(event.button, event.pos)

        elif event.type == pygame.MOUSEWHEEL:
            self._handle_scroll(event.y)

        elif event.type == pygame.MOUSEMOTION:
            self._update_cursor(event.pos)

    def _handle_key(self, key: int, mod: int):
        if self.game_over:
            if key == pygame.K_r:
                self._new_game()
            elif key == pygame.K_q:
                self._running = False
            return

        mapping = {
            pygame.K_r: P_RAISE,
            pygame.K_l: P_LOWER,
            pygame.K_q: P_QUAKE,
            pygame.K_v: P_VOLCANO,
            pygame.K_f: P_FLOOD,
            pygame.K_a: P_ARMA,
        }
        if key in mapping:
            self.selected_power = mapping[key]

        if key == pygame.K_ESCAPE:
            self._running = False

    def _handle_mouse_down(self, button: int, pos: tuple[int, int]):
        sx, sy = pos

        # Check HUD click first
        clicked_power = self.hud.handle_click(sx, sy)
        if clicked_power is not None:
            self.selected_power = clicked_power
            return

        # World click
        if sy < SCREEN_H - HUD_H:
            col, row = screen_to_world(sx, sy, self.renderer.cam_x,
                                       self.renderer.cam_y, self.terrain)
            col = max(0, min(self.terrain.tiles - 1, col))
            row = max(0, min(self.terrain.tiles - 1, row))

            if button == 1:   # LMB: use selected power
                ok = use_power(self.selected_power, self, col, row)
                if not ok:
                    self.hud.notify("Not enough mana!", (255, 100, 100))
            elif button == 3:  # RMB: quick raise
                self.terrain.raise_area(col, row, radius=2.0)
            elif button == 2:  # MMB: quick lower
                self.terrain.lower_area(col, row, radius=2.0)

    def _handle_scroll(self, dy: int):
        # Zoom camera by adjusting tile size conceptually via cam offset nudge
        # Simple: shift cam Y to give zoom feel
        factor = 0.12
        self.renderer.cam_y += dy * 15 * factor * (SCREEN_H / 720)

    def _update_cursor(self, pos: tuple[int, int]):
        sx, sy = pos
        if sy < SCREEN_H - HUD_H:
            col, row = screen_to_world(sx, sy, self.renderer.cam_x,
                                       self.renderer.cam_y, self.terrain)
            self._cursor_world = (col, row)
        else:
            self._cursor_world = None

    # ------------------------------------------------------------------ #
    #  Update                                                              #
    # ------------------------------------------------------------------ #

    def _update(self, dt: float):
        self._scroll_camera(dt)
        self.renderer.update(dt)
        self.hud.update(dt)
        self.particles.update(dt)
        self.ai.update(dt, self)

        self._update_mana(dt)
        self._update_entities(dt)
        self._cull_dead()
        self._check_victory()

        # Screen shake decay
        self.screen_shake = max(0.0, self.screen_shake - dt * 3)

    def _scroll_camera(self, dt: float):
        keys = pygame.key.get_pressed()
        speed = self._scroll_speed * dt
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.renderer.cam_y += speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.renderer.cam_y -= speed
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.renderer.cam_x += speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.renderer.cam_x -= speed

    def _update_mana(self, dt: float):
        p_count = sum(1 for s in self.settlers
                      if s.alive and s.faction == PLAYER)
        e_count = sum(1 for s in self.settlers
                      if s.alive and s.faction == ENEMY)

        self.mana       = min(MAX_MANA, self.mana + p_count * MANA_RATE * dt)
        self.mana_enemy = min(MAX_MANA, self.mana_enemy + e_count * MANA_RATE * dt)

    def _update_entities(self, dt: float):
        # Update buildings, collect newly spawned settlers
        new_settlers: list[Settler] = []
        for b in self.buildings:
            if b.alive:
                ns = b.update(dt, self)
                new_settlers.extend(ns)
        self.settlers.extend(new_settlers)

        # Update settlers
        new_buildings: list[Building] = []
        for s in self.settlers:
            if s.alive:
                nb = s.update(dt, self.terrain, self.settlers, self.buildings)
                if nb is not None:
                    new_buildings.append(nb)
                    # Sparkle effect
                    h = self.terrain.height_at(nb.col, nb.row)
                    sx, sy = iso(nb.col, nb.row, h,
                                 self.renderer.cam_x, self.renderer.cam_y)
                    self.particles.emit_construction(sx, sy)

        self.buildings.extend(new_buildings)

    def _cull_dead(self):
        # Emit death particles for just-killed settlers
        for s in self.settlers:
            if not s.alive:
                h = self.terrain.height_at(s.col, s.row)
                sx, sy = iso(s.col, s.row, h,
                             self.renderer.cam_x, self.renderer.cam_y)
                # Only emit if we haven't already (check a flag)
                if not getattr(s, '_death_emitted', False):
                    self.particles.emit_death(sx, sy, s.faction)
                    s._death_emitted = True

        self.settlers  = [s for s in self.settlers  if s.alive]
        self.buildings = [b for b in self.buildings if b.alive]

    def _check_victory(self):
        p_alive = any(s.alive for s in self.settlers if s.faction == PLAYER)
        e_alive = any(s.alive for s in self.settlers if s.faction == ENEMY)

        if not e_alive and len(self.settlers) > 0:
            self.game_over = True
            self.winner = PLAYER
        elif not p_alive and len(self.settlers) > 0:
            self.game_over = True
            self.winner = ENEMY

    # ------------------------------------------------------------------ #
    #  Draw                                                                #
    # ------------------------------------------------------------------ #

    def _draw(self):
        # Apply screen shake offset
        shake_x = shake_y = 0
        if self.screen_shake > 0:
            import math as _m
            shake_x = int(random.uniform(-1, 1) * self.screen_shake * 4)
            shake_y = int(random.uniform(-1, 1) * self.screen_shake * 4)
            self.renderer.cam_x += shake_x
            self.renderer.cam_y += shake_y

        self.renderer.draw_world(
            self.terrain,
            self.settlers + self.buildings,
            self.particles.active,
            self.selected_power,
            self._cursor_world,
        )
        self.hud.draw(self)

        if self.game_over and self.winner is not None:
            self.victory.draw(self.winner)

        # Undo shake offset
        if self.screen_shake > 0:
            self.renderer.cam_x -= shake_x
            self.renderer.cam_y -= shake_y

    # ------------------------------------------------------------------ #
    #  Helpers used by powers.py and ai_opponent.py                       #
    # ------------------------------------------------------------------ #

    def _kill_settlers_near(self, col: float, row: float,
                             radius: float, faction: int):
        from powers import _kill_settler
        for s in self.settlers:
            if s.alive and s.faction == faction:
                if math.hypot(s.col - col, s.row - row) < radius:
                    _kill_settler(self, s)

    def _drown_settlers_below_water(self, faction: int):
        from powers import _kill_settler
        for s in self.settlers:
            if s.alive and s.faction == faction:
                if not self.terrain.is_above_water(s.col, s.row):
                    _kill_settler(self, s)
