"""
Populous Python - HUD & UI

Bottom panel with mana bar, power selector, and population counters.
Also draws the minimap overlay.
"""

from __future__ import annotations

import math
import pygame
from typing import TYPE_CHECKING

from constants import (
    SCREEN_W, SCREEN_H, HUD_H, MINIMAP_SZ,
    POWER_NAMES, POWER_COSTS, MAX_MANA,
    P_RAISE, P_LOWER, P_QUAKE, P_VOLCANO, P_FLOOD, P_ARMA,
    PLAYER, ENEMY,
    C_PLAYER, C_ENEMY,
)

if TYPE_CHECKING:
    from game import Game

# Power icon colours
POWER_COLOURS = {
    P_RAISE:   (80,  200,  80),
    P_LOWER:   (200,  80,  80),
    P_QUAKE:   (255, 200,  50),
    P_VOLCANO: (255, 120,  30),
    P_FLOOD:   (50,  100, 255),
    P_ARMA:    (200,  50, 200),
}


class HUD:
    """Renders the bottom HUD panel and minimap."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        pygame.font.init()
        self._font_sm = pygame.font.SysFont("monospace", 13)
        self._font_md = pygame.font.SysFont("monospace", 16, bold=True)
        self._font_lg = pygame.font.SysFont("monospace", 22, bold=True)

        self._panel_surf = pygame.Surface((SCREEN_W, HUD_H), pygame.SRCALPHA)
        self._power_rects: list[pygame.Rect] = []
        self._tick = 0.0

        # Notification messages
        self._notifications: list[dict] = []

    # ------------------------------------------------------------------ #
    #  Public draw                                                         #
    # ------------------------------------------------------------------ #

    def update(self, dt: float):
        self._tick += dt
        self._notifications = [n for n in self._notifications
                                if n['life'] > 0]
        for n in self._notifications:
            n['life'] -= dt

    def draw(self, game: 'Game'):
        self._panel_surf.fill((0, 0, 0, 0))
        self._draw_panel_bg()
        self._draw_mana_bar(game.mana)
        self._draw_power_buttons(game.selected_power, game.mana)
        self._draw_population(game)
        self._draw_notifications()

        self.screen.blit(self._panel_surf, (0, SCREEN_H - HUD_H))

        # Minimap (top-right corner)
        mm = game.renderer.draw_minimap(game.terrain, game.settlers + game.buildings)
        self.screen.blit(mm, (SCREEN_W - MINIMAP_SZ - 8, 8))

    def notify(self, text: str, colour=(255, 255, 100)):
        self._notifications.append({'text': text, 'colour': colour, 'life': 3.0})

    # ------------------------------------------------------------------ #
    #  Click handling                                                      #
    # ------------------------------------------------------------------ #

    def handle_click(self, sx: int, sy: int) -> int | None:
        """Return selected power index if a power button was clicked, else None."""
        panel_y = sy - (SCREEN_H - HUD_H)
        if panel_y < 0:
            return None
        for i, rect in enumerate(self._power_rects):
            if rect.collidepoint(sx, panel_y):
                return i
        return None

    # ------------------------------------------------------------------ #
    #  Internal drawing                                                    #
    # ------------------------------------------------------------------ #

    def _draw_panel_bg(self):
        # Dark translucent panel
        pygame.draw.rect(self._panel_surf, (12, 10, 22, 230),
                         (0, 0, SCREEN_W, HUD_H))
        # Top edge glow
        for i in range(4):
            alpha = 120 - i * 25
            pygame.draw.line(self._panel_surf, (80, 140, 255, alpha),
                             (0, i), (SCREEN_W, i))

    def _draw_mana_bar(self, mana: float):
        # Label
        lbl = self._font_md.render("MANA", True, (140, 180, 255))
        self._panel_surf.blit(lbl, (16, 12))

        bar_x, bar_y = 16, 34
        bar_w, bar_h = 280, 18

        # Background
        pygame.draw.rect(self._panel_surf, (20, 20, 40), (bar_x, bar_y, bar_w, bar_h))

        # Fill
        fill = int(bar_w * mana / MAX_MANA)
        pulse = 0.85 + 0.15 * math.sin(self._tick * 3)
        r = int(60  * pulse)
        g = int(160 * pulse)
        b = int(255 * pulse)
        if fill > 0:
            pygame.draw.rect(self._panel_surf, (r, g, b), (bar_x, bar_y, fill, bar_h))

        # Shimmer highlight
        pygame.draw.rect(self._panel_surf, (180, 220, 255, 60),
                         (bar_x, bar_y, fill, bar_h // 2))

        # Border
        pygame.draw.rect(self._panel_surf, (80, 120, 200), (bar_x, bar_y, bar_w, bar_h), 1)

        # Value text
        val = self._font_sm.render(f"{int(mana)}/{int(MAX_MANA)}", True, (200, 230, 255))
        self._panel_surf.blit(val, (bar_x + bar_w + 6, bar_y + 2))

    def _draw_power_buttons(self, selected: int, mana: float):
        powers = list(range(6))  # P_RAISE … P_ARMA
        btn_w, btn_h = 105, 70
        start_x = 320
        start_y = 8
        gap = 8

        self._power_rects = []

        for i, pid in enumerate(powers):
            x = start_x + i * (btn_w + gap)
            rect = pygame.Rect(x, start_y, btn_w, btn_h)
            self._power_rects.append(rect)

            col = POWER_COLOURS[pid]
            cost = POWER_COSTS[pid]
            can_afford = mana >= cost
            is_selected = (selected == pid)

            # Button background
            bg_alpha = 200 if is_selected else 140
            bg = (*[max(0, c - 60) for c in col], bg_alpha)
            pygame.draw.rect(self._panel_surf, bg, rect, border_radius=6)

            # Selected highlight
            if is_selected:
                pulse = 0.7 + 0.3 * math.sin(self._tick * 5)
                border_c = tuple(min(255, int(c * pulse)) for c in col)
                pygame.draw.rect(self._panel_surf, border_c, rect, 2, border_radius=6)
            else:
                pygame.draw.rect(self._panel_surf, (60, 60, 80), rect, 1, border_radius=6)

            # Greyed if unaffordable
            if not can_afford:
                grey = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
                grey.fill((0, 0, 0, 100))
                self._panel_surf.blit(grey, rect.topleft)

            # Power name
            name_lns = POWER_NAMES[pid].split()
            for li, ln in enumerate(name_lns):
                txt = self._font_sm.render(ln, True,
                                           col if can_afford else (100, 100, 100))
                tw = txt.get_width()
                self._panel_surf.blit(txt, (x + btn_w // 2 - tw // 2,
                                            start_y + 6 + li * 15))

            # Cost label
            if cost > 0:
                cost_txt = self._font_sm.render(f"{cost}⚡", True,
                                                (200, 220, 100) if can_afford else (80, 80, 80))
                self._panel_surf.blit(cost_txt, (x + 4, start_y + btn_h - 18))

            # Keyboard shortcut
            keys = ['R', 'L', 'Q', 'V', 'F', 'A']
            key_txt = self._font_sm.render(f"[{keys[i]}]", True, (120, 120, 140))
            kw = key_txt.get_width()
            self._panel_surf.blit(key_txt, (x + btn_w - kw - 4, start_y + btn_h - 18))

    def _draw_population(self, game: 'Game'):
        p_count = sum(1 for s in game.settlers
                      if s.alive and s.faction == PLAYER)
        e_count = sum(1 for s in game.settlers
                      if s.alive and s.faction == ENEMY)
        p_bldg  = sum(1 for b in game.buildings
                      if b.alive and b.faction == PLAYER and b.built)
        e_bldg  = sum(1 for b in game.buildings
                      if b.alive and b.faction == ENEMY and b.built)

        x = SCREEN_W - MINIMAP_SZ - 220
        y = 10

        # Player
        lbl = self._font_md.render(f"YOU  {p_count:>3} followers  {p_bldg} buildings",
                                   True, C_PLAYER)
        self._panel_surf.blit(lbl, (x, y))

        # Enemy
        lbl = self._font_md.render(f"FOE  {e_count:>3} followers  {e_bldg} buildings",
                                   True, C_ENEMY)
        self._panel_surf.blit(lbl, (x, y + 22))

        # Controls hint
        hint = self._font_sm.render(
            "WASD: scroll  Scroll: zoom  LMB: use power  RMB: raise  MMB: lower",
            True, (100, 100, 130))
        self._panel_surf.blit(hint, (x, y + 50))

    def _draw_notifications(self):
        y = 20
        for n in reversed(self._notifications):
            alpha = min(255, int(255 * n['life']))
            txt = self._font_lg.render(n['text'], True, n['colour'])
            # Shadow
            shadow = self._font_lg.render(n['text'], True, (0, 0, 0))
            cx = SCREEN_W // 2 - txt.get_width() // 2
            self.screen.blit(shadow, (cx + 2, (SCREEN_H - HUD_H) // 2 + y + 2))
            self.screen.blit(txt,    (cx,     (SCREEN_H - HUD_H) // 2 + y))
            y += 30


class VictoryScreen:
    """Full-screen overlay shown when the game ends."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        pygame.font.init()
        self._font = pygame.font.SysFont("monospace", 48, bold=True)
        self._sub  = pygame.font.SysFont("monospace", 22)

    def draw(self, winner: int):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        if winner == PLAYER:
            msg   = "VICTORY!"
            sub   = "Your followers have triumphed!"
            colour = (80, 180, 255)
        else:
            msg   = "DEFEAT!"
            sub   = "The enemy has crushed your people."
            colour = (255, 80, 80)

        txt = self._font.render(msg, True, colour)
        self.screen.blit(txt, (SCREEN_W // 2 - txt.get_width() // 2,
                                SCREEN_H // 2 - 60))
        sub_txt = self._sub.render(sub, True, (220, 220, 220))
        self.screen.blit(sub_txt, (SCREEN_W // 2 - sub_txt.get_width() // 2,
                                   SCREEN_H // 2 + 10))
        restart = self._sub.render("Press R to restart or Q to quit", True, (150, 150, 150))
        self.screen.blit(restart, (SCREEN_W // 2 - restart.get_width() // 2,
                                   SCREEN_H // 2 + 50))
