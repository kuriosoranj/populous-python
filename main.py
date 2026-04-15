"""
Populous: The Beginning — Python Edition

Controls
────────
WASD / Arrows      Scroll camera
Mouse edge          Auto-scroll
Scroll wheel        Camera shift

LMB on YOUR shaman  Select shaman
RMB on terrain      Move selected shaman
LMB on terrain      Cast selected spell

1  Blast          (5 mana)   — explosive projectile
2  Lightning     (10 mana)   — instant kill near cursor
3  Land Bridge   (15 mana)   — two clicks: raise a path
4  Swamp         (15 mana)   — sticky terrain patch
5  Volcano       (35 mana)   — eruption cone
6  Flatten        (8 mana)   — level the land
7  Firestorm     (40 mana)   — rain of blasts
8  Armageddon   (100 mana)   — all-out war

Escape   Deselect / cancel
R        Restart (after game over)
Q        Quit
"""

import sys
import pygame
from constants import SCREEN_W, SCREEN_H, TITLE


def main():
    pygame.init()
    pygame.display.set_caption(TITLE)
    flags = pygame.DOUBLEBUF | pygame.HWSURFACE
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)

    from game import Game
    game = Game(screen)
    game.run()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
