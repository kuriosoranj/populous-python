"""
Populous: The Beginning — Game

Shaman-centric gameplay:
  • LMB on shaman      → select shaman
  • RMB on terrain     → move selected shaman there
  • LMB on terrain     → cast selected spell
  • Followers automatically follow shaman
  • Braves build when shaman is stationary
"""

from __future__ import annotations

import math, random, sys
import pygame

from constants import (
    SCREEN_W, SCREEN_H, FPS, TITLE, HUD_H,
    PLAYER, ENEMY,
    SP_BLAST,SP_LIGHTNING,SP_LANDBRIDGE,SP_SWAMP,
    SP_VOLCANO,SP_FLATTEN,SP_FIRESTORM,SP_ARMAGEDDON,
    SPELL_COSTS, MAX_MANA, MANA_RATE, VERTS,
    C_PLAYER, C_ENEMY,
)
from terrain import Terrain
from renderer import Renderer, iso, screen_to_world
from entities import Shaman, Brave, Warrior, Firewarrior, Building, B_HUT, B_WARRIOR_HUT
from particles import ParticleSystem
from powers import use_spell
from ai_opponent import AIPlayer
from ui import HUD, VictoryScreen


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_start(terrain: Terrain, col_hint: int, row_hint: int):
    for radius in range(1, 20):
        for _ in range(40):
            c = col_hint + random.randint(-radius, radius)
            r = row_hint + random.randint(-radius, radius)
            if 0 < c < terrain.tiles and 0 < r < terrain.tiles:
                if terrain.is_above_water(c, r) and terrain.flatness(c, r, 2) <= 2:
                    return c, r
    return col_hint, row_hint


def _entity_at(entities, col: float, row: float, radius: float = 1.8):
    best, bd = None, radius
    for e in entities:
        if e.alive:
            d = math.hypot(e.col - col, e.row - row)
            if d < bd:
                best, bd = e, d
    return best


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen   = screen
        self._running = True
        self.game_over = False
        self.winner: int | None = None
        self._new_game()

    # ------------------------------------------------------------------ #
    #  Init                                                                #
    # ------------------------------------------------------------------ #

    def _new_game(self):
        self.terrain    = Terrain(VERTS)
        self.renderer   = Renderer(self.screen)
        self.particles  = ParticleSystem()
        self.hud        = HUD(self.screen)
        self.victory    = VictoryScreen(self.screen)
        self.ai         = AIPlayer()

        self.mana        = 60.0
        self.mana_enemy  = 60.0
        self.selected_spell = SP_BLAST
        self.screen_shake   = 0.0

        self.settlers:  list = []
        self.buildings: list[Building] = []

        self.player_shaman: Shaman | None = None
        self.enemy_shaman:  Shaman | None = None

        self.selected_entity = None    # currently selected unit (shaman)
        self._lb_bridge_start: tuple | None = None  # landbridge first click

        self.game_over = False
        self.winner    = None

        self._scroll_speed = 320.0
        self._cursor_world: tuple | None = None

        self._spawn_tribes()

    def _spawn_tribes(self):
        n = self.terrain.tiles
        pc, pr = _find_start(self.terrain, n // 4,     n // 4)
        ec, er = _find_start(self.terrain, 3*n//4, 3*n//4)

        # Shamans
        self.player_shaman = Shaman(pc, pr, PLAYER)
        self.enemy_shaman  = Shaman(ec, er, ENEMY)

        # Flatten starting zones
        self.terrain.flatten_area(pc, pr, radius=3)
        self.terrain.flatten_area(ec, er, radius=3)
        self.terrain._dirty = True

        # Starting huts
        for dc, dr, f, col, row in [
            (-3, -3, PLAYER, pc, pr), (3, -3, PLAYER, pc, pr),
            (-3,  3, PLAYER, pc, pr),
            (-3, -3, ENEMY,  ec, er), (3, -3, ENEMY,  ec, er),
            (-3,  3, ENEMY,  ec, er),
        ]:
            hc, hr = int(col+dc), int(row+dr)
            if self.terrain.is_above_water(hc, hr):
                b = Building(hc, hr, f, B_HUT)
                b.built = True; b.build_progress = 1.0
                self.buildings.append(b)

        # Starting braves
        for _ in range(8):
            self.settlers.append(Brave(pc + random.uniform(-4,4),
                                       pr + random.uniform(-4,4), PLAYER))
        for _ in range(8):
            self.settlers.append(Brave(ec + random.uniform(-4,4),
                                       er + random.uniform(-4,4), ENEMY))

        # Centre camera on player
        mid_sx, mid_sy = iso(pc, pr, self.terrain.height_at(pc, pr),
                              self.renderer.cam_x, self.renderer.cam_y)
        self.renderer.cam_x += SCREEN_W//2 - mid_sx
        self.renderer.cam_y += (SCREEN_H - HUD_H)//2 - mid_sy

    # ------------------------------------------------------------------ #
    #  Main loop                                                           #
    # ------------------------------------------------------------------ #

    def run(self):
        clock = pygame.time.Clock()
        while self._running:
            dt = min(clock.tick(FPS) / 1000.0, 0.05)
            for event in pygame.event.get():
                self._handle_event(event)
            if not self.game_over:
                self._update(dt)
            self._draw()
            pygame.display.flip()

    # ------------------------------------------------------------------ #
    #  Events                                                              #
    # ------------------------------------------------------------------ #

    def _handle_event(self, ev: pygame.event.Event):
        if ev.type == pygame.QUIT:
            self._running = False

        elif ev.type == pygame.KEYDOWN:
            self._handle_key(ev.key)

        elif ev.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse(ev.button, ev.pos)

        elif ev.type == pygame.MOUSEMOTION:
            sx, sy = ev.pos
            if sy < SCREEN_H - HUD_H:
                col, row = screen_to_world(sx, sy, self.renderer.cam_x,
                                           self.renderer.cam_y, self.terrain)
                self._cursor_world = (
                    max(0, min(self.terrain.tiles-1, col)),
                    max(0, min(self.terrain.tiles-1, row)),
                )
            else:
                self._cursor_world = None

        elif ev.type == pygame.MOUSEWHEEL:
            self.renderer.cam_y += ev.y * 18

    def _handle_key(self, key: int):
        if self.game_over:
            if key == pygame.K_r: self._new_game()
            elif key == pygame.K_q: self._running = False
            return

        spell_map = {
            pygame.K_1: SP_BLAST,    pygame.K_2: SP_LIGHTNING,
            pygame.K_3: SP_LANDBRIDGE,pygame.K_4: SP_SWAMP,
            pygame.K_5: SP_VOLCANO,  pygame.K_6: SP_FLATTEN,
            pygame.K_7: SP_FIRESTORM,pygame.K_8: SP_ARMAGEDDON,
        }
        if key in spell_map:
            self.selected_spell = spell_map[key]
            self._lb_bridge_start = None

        if key == pygame.K_ESCAPE:
            self.selected_entity = None
            self._lb_bridge_start = None

    def _handle_mouse(self, button: int, pos: tuple):
        sx, sy = pos

        # HUD click → spell select
        clicked = self.hud.handle_click(sx, sy)
        if clicked is not None:
            self.selected_spell = clicked
            self._lb_bridge_start = None
            return

        if sy >= SCREEN_H - HUD_H:
            return

        col, row = screen_to_world(sx, sy, self.renderer.cam_x,
                                   self.renderer.cam_y, self.terrain)
        col = max(0, min(self.terrain.tiles-1, col))
        row = max(0, min(self.terrain.tiles-1, row))

        if button == 1:   # LMB
            self._lmb(col, row)
        elif button == 3: # RMB — move selected shaman
            self._rmb(col, row)
        elif button == 2: # MMB — lower terrain
            self.terrain.lower_area(col, row, radius=2.0)

    def _lmb(self, col: float, row: float):
        # Check if clicking near player shaman → select
        if self.player_shaman and self.player_shaman.alive:
            d = math.hypot(self.player_shaman.col - col,
                           self.player_shaman.row - row)
            if d < 2.5:
                self.selected_entity = self.player_shaman
                self.hud.notify("Shaman selected", C_PLAYER)
                return

        # Landbridge needs two clicks
        if self.selected_spell == SP_LANDBRIDGE:
            if self._lb_bridge_start is None:
                self._lb_bridge_start = (col, row)
                self.hud.notify("Click destination for Land Bridge", (150,200,255))
                return
            else:
                c0, r0 = self._lb_bridge_start
                self._lb_bridge_start = None
                ok = use_spell(SP_LANDBRIDGE, self, c0, r0, col, row)
                if not ok: self.hud.notify("Not enough mana!", (255,80,80))
                return

        # Cast spell
        ok = use_spell(self.selected_spell, self, col, row)
        if not ok:
            self.hud.notify("Not enough mana!", (255,80,80))

    def _rmb(self, col: float, row: float):
        if self.selected_entity and isinstance(self.selected_entity, Shaman):
            if self.terrain.is_above_water(col, row):
                self.selected_entity.send_to(col, row)
            else:
                self.hud.notify("Can't walk on water!", (255,200,80))

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
        self._update_shamans(dt)
        self._update_entities(dt)
        self._cull_dead()
        self._check_victory()

        self.screen_shake = max(0.0, self.screen_shake - dt * 3.5)

    def _scroll_camera(self, dt: float):
        keys = pygame.key.get_pressed()
        spd  = self._scroll_speed * dt
        if keys[pygame.K_w] or keys[pygame.K_UP]:    self.renderer.cam_y += spd
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  self.renderer.cam_y -= spd
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  self.renderer.cam_x += spd
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: self.renderer.cam_x -= spd

        # Edge scroll
        mx, my = pygame.mouse.get_pos()
        margin = 20
        if mx < margin:            self.renderer.cam_x += spd * 1.5
        elif mx > SCREEN_W-margin: self.renderer.cam_x -= spd * 1.5
        if my < margin:            self.renderer.cam_y += spd * 1.5
        elif my > SCREEN_H-HUD_H-margin: self.renderer.cam_y -= spd * 1.5

    def _update_mana(self, dt: float):
        p_cnt = sum(1 for s in self.settlers if s.alive and s.faction == PLAYER)
        e_cnt = sum(1 for s in self.settlers if s.alive and s.faction == ENEMY)
        # Shaman counts as 3 followers
        if self.player_shaman and self.player_shaman.alive: p_cnt += 3
        if self.enemy_shaman  and self.enemy_shaman.alive:  e_cnt += 3

        self.mana       = min(MAX_MANA, self.mana       + p_cnt * MANA_RATE * dt)
        self.mana_enemy = min(MAX_MANA, self.mana_enemy + e_cnt * MANA_RATE * dt)

    def _update_shamans(self, dt: float):
        if self.player_shaman and self.player_shaman.alive:
            self.player_shaman.update(dt, self.terrain, self)
        if self.enemy_shaman and self.enemy_shaman.alive:
            self.enemy_shaman.update(dt, self.terrain, self)

    def _update_entities(self, dt: float):
        new_settlers  = []
        new_buildings = []

        for b in self.buildings:
            if b.alive:
                ns = b.update(dt, self)
                new_settlers.extend(ns)

        for s in self.settlers:
            if s.alive:
                result = s.update(dt, self.terrain, self)
                if result is not None:
                    if isinstance(result, Building):
                        new_buildings.append(result)
                        h  = self.terrain.height_at(result.col, result.row)
                        bx, by = iso(result.col, result.row, h,
                                     self.renderer.cam_x, self.renderer.cam_y)
                        self.particles.emit_construction(bx, by)

        self.settlers.extend(new_settlers)
        self.buildings.extend(new_buildings)

    def _cull_dead(self):
        for s in self.settlers:
            if not s.alive and not getattr(s, '_death_emitted', False):
                h  = self.terrain.height_at(s.col, s.row)
                sx, sy = iso(s.col, s.row, h,
                              self.renderer.cam_x, self.renderer.cam_y)
                self.particles.emit_death(sx, sy, s.faction)
                s._death_emitted = True

        self.settlers  = [s for s in self.settlers  if s.alive]
        self.buildings = [b for b in self.buildings if b.alive]

    def _check_victory(self):
        p_alive = ((self.player_shaman and self.player_shaman.alive) or
                   any(s.alive for s in self.settlers if s.faction == PLAYER))
        e_alive = ((self.enemy_shaman  and self.enemy_shaman.alive)  or
                   any(s.alive for s in self.settlers if s.faction == ENEMY))

        if not e_alive:
            self.game_over = True; self.winner = PLAYER
        elif not p_alive:
            self.game_over = True; self.winner = ENEMY

    # ------------------------------------------------------------------ #
    #  Draw                                                                #
    # ------------------------------------------------------------------ #

    def _draw(self):
        shake_x = shake_y = 0
        if self.screen_shake > 0:
            import random as _r
            shake_x = int(_r.uniform(-1,1) * self.screen_shake * 4)
            shake_y = int(_r.uniform(-1,1) * self.screen_shake * 4)
            self.renderer.cam_x += shake_x
            self.renderer.cam_y += shake_y

        all_entities = list(self.settlers) + list(self.buildings)
        if self.player_shaman: all_entities.append(self.player_shaman)
        if self.enemy_shaman:  all_entities.append(self.enemy_shaman)

        self.renderer.draw_world(
            self.terrain,
            all_entities,
            self.particles.active,
            self.selected_spell,
            self._cursor_world,
            selected_entity=self.selected_entity,
        )
        self.hud.draw(self)

        if self.game_over and self.winner is not None:
            self.victory.draw(self.winner)

        if self.screen_shake > 0:
            self.renderer.cam_x -= shake_x
            self.renderer.cam_y -= shake_y

    # ------------------------------------------------------------------ #
    #  Helpers for powers.py / ai_opponent.py                             #
    # ------------------------------------------------------------------ #

    def _kill_settlers_near(self, col, row, radius, faction):
        from renderer import iso as _iso
        for s in self.settlers + ([self.player_shaman] if faction == PLAYER else
                                   [self.enemy_shaman]):
            if s and s.alive and s.faction == faction:
                if math.hypot(s.col-col, s.row-row) < radius:
                    h = self.terrain.height_at(s.col, s.row)
                    sx, sy = _iso(s.col, s.row, h,
                                   self.renderer.cam_x, self.renderer.cam_y)
                    self.particles.emit_death(sx, sy, s.faction)
                    s.take_damage(s.max_hp * 3)

    def _drown_settlers_below_water(self, faction):
        self._kill_settlers_near(0, 0, 9999,  # handled by water check below
                                  faction)     # overridden — use water check
        for s in self.settlers:
            if s and s.alive and s.faction == faction:
                if not self.terrain.is_above_water(s.col, s.row):
                    h = self.terrain.height_at(s.col, s.row)
                    from renderer import iso as _iso
                    sx, sy = _iso(s.col, s.row, h,
                                   self.renderer.cam_x, self.renderer.cam_y)
                    self.particles.emit_death(sx, sy, s.faction)
                    s.take_damage(s.max_hp * 3)
