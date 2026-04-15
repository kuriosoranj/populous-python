"""
Populous — Python Edition
A god game inspired by the 1989 classic by Bullfrog Productions.

Controls:
  WASD / Arrows  — scroll camera
  Mouse scroll   — vertical camera shift
  LMB            — use selected power at cursor
  RMB            — quick raise land
  MMB            — quick lower land
  R              — select Raise Land
  L              — select Lower Land
  Q              — select Earthquake
  V              — select Volcano
  F              — select Flood
  A              — Armageddon (costs 100 mana)
  Escape         — quit
"""

import sys
import pygame
from constants import SCREEN_W, SCREEN_H, TITLE


def main():
    pygame.init()
    pygame.display.set_caption(TITLE)
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.DOUBLEBUF)

    from game import Game
    game = Game(screen)
    game.run()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
