"""
Populous: The Beginning — Game (3D perspective camera)

Controls:
  WASD          move camera (in the direction it faces)
  Q / E         rotate camera left / right
  Scroll wheel  camera pitch / zoom
  LMB shaman    select your shaman
  RMB terrain   move selected shaman
  LMB terrain   cast selected spell
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
from renderer import Renderer, screen_ray, project
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
            if 0 < c < terrain.tiles-1 and 0 < r < terrain.tiles-1:
                if terrain.is_above_water(c, r) and terrain.flatness(c, r, 2) <= 2:
                    return c, r
    return col_hint, row_hint


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen    = screen
        self._running  = True
        self.game_over = False
        self.winner    = None
        self._new_game()

    # ------------------------------------------------------------------ #
    #  Init                                                                #
    # ------------------------------------------------------------------ #

    def _new_game(self):
        self.terrain   = Terrain(VERTS)
        self.renderer  = Renderer(self.screen)
        self.particles = ParticleSystem()
        self.hud       = HUD(self.screen)
        self.victory   = VictoryScreen(self.screen)
        self.ai        = AIPlayer()

        self.mana        = 60.0
        self.mana_enemy  = 60.0
        self.selected_spell  = SP_BLAST
        self.screen_shake    = 0.0

        self.settlers:  list = []
        self.buildings: list[Building] = []

        self.player_shaman: Shaman | None = None
        self.enemy_shaman:  Shaman | None = None
        self.selected_entity = None
        self._lb_start: tuple | None = None   # land-bridge first click

        self.game_over = False
        self.winner    = None
        self._cursor_world: tuple | None = None

        self._spawn_tribes()

    def _spawn_tribes(self):
        n  = self.terrain.tiles
        pc, pr = _find_start(self.terrain, n // 4,     n // 4)
        ec, er = _find_start(self.terrain, 3*n//4, 3*n//4)

        self.terrain.flatten_area(pc, pr, radius=3)
        self.terrain.flatten_area(ec, er, radius=3)
        self.terrain._dirty = True

        self.player_shaman = Shaman(pc, pr, PLAYER)
        self.enemy_shaman  = Shaman(ec, er, ENEMY)

        # Starting huts
        for dc, dr, f, col, row in [
            (-3,-3,PLAYER,pc,pr),(3,-3,PLAYER,pc,pr),(-3,3,PLAYER,pc,pr),
            (-3,-3,ENEMY, ec,er),(3,-3,ENEMY, ec,er),(-3,3,ENEMY, ec,er),
        ]:
            hc,hr = int(col+dc), int(row+dr)
            if self.terrain.is_above_water(hc,hr):
                b=Building(hc,hr,f,B_HUT); b.built=True; b.build_progress=1.0
                self.buildings.append(b)

        for _ in range(8):
            self.settlers.append(Brave(pc+random.uniform(-4,4),pr+random.uniform(-4,4),PLAYER))
        for _ in range(8):
            self.settlers.append(Brave(ec+random.uniform(-4,4),er+random.uniform(-4,4),ENEMY))

        # Position 3-D camera behind the player's starting area
        cam = self.renderer.cam
        cam.yaw   = 0.0          # facing +Y (north on map)
        cam.x     = float(pc)
        cam.y     = max(2.0, pr - 10.0)
        terrain_h = self.terrain.height_at(cam.x, cam.y)
        cam.z     = terrain_h / 10.0 + 1.8
        cam._update_trig()

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
                result = screen_ray(sx, sy, self.renderer.cam, self.terrain)
                if result:
                    col, row = result
                    self._cursor_world = (
                        max(0, min(self.terrain.tiles-1, col)),
                        max(0, min(self.terrain.tiles-1, row)),
                    )
            else:
                self._cursor_world = None
        elif ev.type == pygame.MOUSEWHEEL:
            # Tilt camera pitch up/down
            cam = self.renderer.cam
            cam.pitch = max(0.2, min(0.8, cam.pitch - ev.y * 0.04))
            cam._update_trig()

    def _handle_key(self, key: int):
        if self.game_over:
            if key == pygame.K_r: self._new_game()
            elif key == pygame.K_q: self._running = False
            return
        spell_map = {
            pygame.K_1: SP_BLAST,     pygame.K_2: SP_LIGHTNING,
            pygame.K_3: SP_LANDBRIDGE,pygame.K_4: SP_SWAMP,
            pygame.K_5: SP_VOLCANO,   pygame.K_6: SP_FLATTEN,
            pygame.K_7: SP_FIRESTORM, pygame.K_8: SP_ARMAGEDDON,
        }
        if key in spell_map:
            self.selected_spell = spell_map[key]
            self._lb_start = None
        if key == pygame.K_ESCAPE:
            self.selected_entity = None
            self._lb_start = None

    def _handle_mouse(self, button: int, pos: tuple):
        sx, sy = pos

        # HUD spell icon click
        clicked = self.hud.handle_click(sx, sy)
        if clicked is not None:
            self.selected_spell = clicked
            self._lb_start = None
            return

        if sy >= SCREEN_H - HUD_H:
            return

        result = screen_ray(sx, sy, self.renderer.cam, self.terrain)
        if result is None:
            return
        col, row = max(0,min(self.terrain.tiles-1,result[0])), \
                   max(0,min(self.terrain.tiles-1,result[1]))

        if button == 1:
            self._lmb(col, row)
        elif button == 3:
            self._rmb(col, row)
        elif button == 2:
            self.terrain.lower_area(col, row, radius=2.0)

    def _lmb(self, col, row):
        # Click near player shaman → select it
        if self.player_shaman and self.player_shaman.alive:
            d = math.hypot(self.player_shaman.col - col, self.player_shaman.row - row)
            if d < 2.5:
                self.selected_entity = self.player_shaman
                self.hud.notify("Shaman selected", C_PLAYER)
                return

        # Landbridge two-click
        if self.selected_spell == SP_LANDBRIDGE:
            if self._lb_start is None:
                self._lb_start = (col, row)
                self.hud.notify("Click destination for Land Bridge", (150,200,255))
                return
            else:
                c0,r0 = self._lb_start
                self._lb_start = None
                if not use_spell(SP_LANDBRIDGE, self, c0, r0, col, row):
                    self.hud.notify("Not enough mana!", (255,80,80))
                return

        if not use_spell(self.selected_spell, self, col, row):
            self.hud.notify("Not enough mana!", (255,80,80))

    def _rmb(self, col, row):
        if self.selected_entity and isinstance(self.selected_entity, Shaman):
            if self.terrain.is_above_water(col, row):
                self.selected_entity.send_to(col, row)
            else:
                self.hud.notify("Can't walk on water!", (255,200,80))

    # ------------------------------------------------------------------ #
    #  Update                                                              #
    # ------------------------------------------------------------------ #

    def _update(self, dt: float):
        self._move_camera(dt)
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

    def _move_camera(self, dt: float):
        keys = pygame.key.get_pressed()
        cam  = self.renderer.cam
        spd  = 12.0 * dt

        # Forward/right vectors in world XY (no Z component)
        fwd_x = math.sin(cam.yaw);  fwd_y = math.cos(cam.yaw)
        rgt_x = math.cos(cam.yaw);  rgt_y = -math.sin(cam.yaw)

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            cam.x += fwd_x*spd; cam.y += fwd_y*spd
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            cam.x -= fwd_x*spd; cam.y -= fwd_y*spd
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            cam.x -= rgt_x*spd; cam.y -= rgt_y*spd
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            cam.x += rgt_x*spd; cam.y += rgt_y*spd
        if keys[pygame.K_q]:
            cam.rotate(-1.8 * dt)
        if keys[pygame.K_e]:
            cam.rotate( 1.8 * dt)

        # Edge-of-screen auto-scroll
        mx, my = pygame.mouse.get_pos()
        margin = 20
        if   mx < margin:                    cam.x -= rgt_x*spd*1.5; cam.y -= rgt_y*spd*1.5
        elif mx > SCREEN_W - margin:         cam.x += rgt_x*spd*1.5; cam.y += rgt_y*spd*1.5
        if   my < margin:                    cam.x += fwd_x*spd*1.5; cam.y += fwd_y*spd*1.5
        elif my > SCREEN_H - HUD_H - margin: cam.x -= fwd_x*spd*1.5; cam.y -= fwd_y*spd*1.5

        # Keep camera on map
        cam.x = max(1.0, min(self.terrain.tiles-1, cam.x))
        cam.y = max(1.0, min(self.terrain.tiles-1, cam.y))

        # Camera height tracks terrain below it
        th = self.terrain.height_at(cam.x, cam.y)
        cam.z = th / 10.0 + 1.8

    def _update_mana(self, dt: float):
        p_cnt = sum(1 for s in self.settlers if s.alive and s.faction==PLAYER)
        e_cnt = sum(1 for s in self.settlers if s.alive and s.faction==ENEMY)
        if self.player_shaman and self.player_shaman.alive: p_cnt += 3
        if self.enemy_shaman  and self.enemy_shaman.alive:  e_cnt += 3
        self.mana       = min(MAX_MANA, self.mana       + p_cnt * MANA_RATE * dt)
        self.mana_enemy = min(MAX_MANA, self.mana_enemy + e_cnt * MANA_RATE * dt)

    def _update_shamans(self, dt: float):
        if self.player_shaman and self.player_shaman.alive:
            self.player_shaman.update(dt, self.terrain, self)
        if self.enemy_shaman  and self.enemy_shaman.alive:
            self.enemy_shaman.update(dt, self.terrain, self)

    def _update_entities(self, dt: float):
        new_settlers, new_buildings = [], []
        for b in self.buildings:
            if b.alive:
                new_settlers.extend(b.update(dt, self))
        for s in self.settlers:
            if s.alive:
                result = s.update(dt, self.terrain, self)
                if isinstance(result, Building):
                    new_buildings.append(result)
                    pt = self.renderer.world_to_screen(result.col, result.row,
                                                       self.terrain.height_at(result.col,result.row))
                    if pt: self.particles.emit_construction(*pt)
        self.settlers.extend(new_settlers)
        self.buildings.extend(new_buildings)

    def _cull_dead(self):
        cam = self.renderer.cam
        for s in self.settlers:
            if not s.alive and not getattr(s,'_death_emitted',False):
                s._death_emitted = True
                h  = self.terrain.height_at(s.col, s.row)
                pt = self.renderer.world_to_screen(s.col, s.row, h)
                if pt: self.particles.emit_death(pt[0], pt[1], s.faction)
        self.settlers  = [s for s in self.settlers  if s.alive]
        self.buildings = [b for b in self.buildings if b.alive]

    def _check_victory(self):
        p_alive = ((self.player_shaman and self.player_shaman.alive) or
                   any(s.alive for s in self.settlers if s.faction==PLAYER))
        e_alive = ((self.enemy_shaman  and self.enemy_shaman.alive)  or
                   any(s.alive for s in self.settlers if s.faction==ENEMY))
        if not e_alive: self.game_over=True; self.winner=PLAYER
        elif not p_alive: self.game_over=True; self.winner=ENEMY

    # ------------------------------------------------------------------ #
    #  Draw                                                                #
    # ------------------------------------------------------------------ #

    def _draw(self):
        shake_x = shake_y = 0
        if self.screen_shake > 0:
            shake_x = int(random.uniform(-1,1) * self.screen_shake * 3)
            shake_y = int(random.uniform(-1,1) * self.screen_shake * 3)
            cam = self.renderer.cam
            cam.x += shake_x * 0.02; cam.y += shake_y * 0.02

        all_entities = list(self.settlers) + list(self.buildings)
        if self.player_shaman: all_entities.append(self.player_shaman)
        if self.enemy_shaman:  all_entities.append(self.enemy_shaman)

        self.renderer.draw_world(
            self.terrain, all_entities, self.particles.active,
            self.selected_spell, self._cursor_world,
            selected_entity=self.selected_entity,
        )
        self.hud.draw(self)
        if self.game_over and self.winner is not None:
            self.victory.draw(self.winner)

        if self.screen_shake > 0:
            cam = self.renderer.cam
            cam.x -= shake_x * 0.02; cam.y -= shake_y * 0.02

    # ------------------------------------------------------------------ #
    #  Helpers for powers.py / ai_opponent.py                             #
    # ------------------------------------------------------------------ #

    def _kill_settlers_near(self, col, row, radius, faction):
        targets = list(self.settlers)
        if faction == PLAYER and self.player_shaman: targets.append(self.player_shaman)
        if faction == ENEMY  and self.enemy_shaman:  targets.append(self.enemy_shaman)
        for s in targets:
            if s and s.alive and s.faction == faction:
                if math.hypot(s.col-col, s.row-row) < radius:
                    h  = self.terrain.height_at(s.col, s.row)
                    pt = self.renderer.world_to_screen(s.col, s.row, h)
                    if pt: self.particles.emit_death(pt[0], pt[1], s.faction)
                    s.take_damage(s.max_hp * 3)

    def _drown_settlers_below_water(self, faction):
        for s in self.settlers:
            if s and s.alive and s.faction == faction:
                if not self.terrain.is_above_water(s.col, s.row):
                    h  = self.terrain.height_at(s.col, s.row)
                    pt = self.renderer.world_to_screen(s.col, s.row, h)
                    if pt: self.particles.emit_death(pt[0], pt[1], s.faction)
                    s.take_damage(s.max_hp * 3)
