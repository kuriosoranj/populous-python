"""
Populous Python - Particle Effects

Visual effects for god powers (volcano, earthquake, flood, etc.)
"""

from __future__ import annotations

import math
import random
from typing import Tuple

from renderer import iso


class Particle:
    """Single particle: lives in screen space."""

    def __init__(self, sx: float, sy: float,
                 vx: float, vy: float,
                 colour: Tuple[int, int, int],
                 life: float, size: float = 2.0,
                 gravity: float = 0.0):
        self.sx = sx
        self.sy = sy
        self.vx = vx
        self.vy = vy
        self.colour = colour
        self.life = life
        self.max_life = life
        self.size = size
        self.gravity = gravity
        self.alive = True

    def update(self, dt: float):
        self.sx += self.vx * dt
        self.sy += self.vy * dt
        self.vy += self.gravity * dt
        self.vx *= (1 - 0.8 * dt)  # drag
        self.life -= dt
        if self.life <= 0:
            self.alive = False
        # Fade size
        self.size = max(0.5, self.size * (0.995 ** (dt * 60)))


class ParticleSystem:
    """Manages a pool of active particles."""

    MAX_PARTICLES = 2000

    def __init__(self):
        self.particles: list[Particle] = []

    def update(self, dt: float):
        for p in self.particles:
            if p.alive:
                p.update(dt)
        # Prune dead particles periodically
        if len(self.particles) > 500:
            self.particles = [p for p in self.particles if p.alive]

    @property
    def active(self) -> list[Particle]:
        return [p for p in self.particles if p.alive]

    def _add(self, p: Particle):
        if len(self.particles) < self.MAX_PARTICLES:
            self.particles.append(p)

    # ------------------------------------------------------------------ #
    #  Emitters                                                            #
    # ------------------------------------------------------------------ #

    def emit_volcano(self, col: float, row: float, h: float,
                     cam_x: float, cam_y: float):
        """Fountain of lava and ash from a volcano eruption."""
        sx, sy = iso(col, row, h, cam_x, cam_y)

        for _ in range(60):
            angle = random.uniform(-math.pi, 0)      # upward hemisphere
            speed = random.uniform(60, 220)
            vx = math.cos(angle) * speed * random.uniform(0.3, 1.0)
            vy = math.sin(angle) * speed
            # Lava
            c = _lava_colour()
            size = random.uniform(2, 5)
            self._add(Particle(sx, sy, vx, vy, c,
                                life=random.uniform(0.8, 2.0),
                                size=size, gravity=200))

        # Ash puffs
        for _ in range(25):
            vx = random.uniform(-30, 30)
            vy = random.uniform(-80, -30)
            grey = random.randint(90, 160)
            self._add(Particle(sx, sy, vx, vy, (grey, grey, grey),
                                life=random.uniform(1.5, 3.5),
                                size=random.uniform(3, 7)))

    def emit_quake(self, col: float, row: float, h: float,
                   cam_x: float, cam_y: float, n: int = 40):
        """Dust and debris particles for an earthquake."""
        sx, sy = iso(col, row, h, cam_x, cam_y)
        for _ in range(n):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(20, 100)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed * 0.5
            grey = random.randint(100, 180)
            self._add(Particle(sx, sy, vx, vy, (grey, grey - 10, grey - 20),
                                life=random.uniform(0.4, 1.2),
                                size=random.uniform(1.5, 4)))

    def emit_flood(self, col: float, row: float, h: float,
                   cam_x: float, cam_y: float):
        """Water splash / ripple particles."""
        sx, sy = iso(col, row, h, cam_x, cam_y)
        for _ in range(35):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(15, 80)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed * 0.35
            shade = random.randint(50, 110)
            c = (shade // 4, shade // 2, shade + random.randint(80, 140))
            self._add(Particle(sx, sy, vx, vy, c,
                                life=random.uniform(0.6, 1.8),
                                size=random.uniform(2, 5)))

    def emit_armageddon(self, col: float, row: float, h: float,
                        cam_x: float, cam_y: float):
        """Purple lightning / apocalyptic bolts."""
        sx, sy = iso(col, row, h, cam_x, cam_y)
        for _ in range(80):
            angle = random.uniform(-math.pi, 0)
            speed = random.uniform(80, 350)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            r = random.randint(160, 220)
            b = random.randint(200, 255)
            self._add(Particle(sx, sy, vx, vy, (r, 30, b),
                                life=random.uniform(0.3, 1.0),
                                size=random.uniform(1, 4), gravity=120))

    def emit_construction(self, sx: float, sy: float):
        """Small sparkles when a building is placed."""
        for _ in range(8):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(10, 40)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            self._add(Particle(sx, sy, vx, vy, (255, 220, 80),
                                life=random.uniform(0.3, 0.7),
                                size=random.uniform(1.5, 3)))

    def emit_death(self, sx: float, sy: float, faction: int):
        """Small burst when a settler dies."""
        from constants import PLAYER
        c = (80, 120, 255) if faction == PLAYER else (255, 80, 80)
        for _ in range(12):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(20, 60)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            self._add(Particle(sx, sy, vx, vy, c,
                                life=random.uniform(0.2, 0.5),
                                size=random.uniform(1, 3)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lava_colour() -> Tuple[int, int, int]:
    roll = random.random()
    if roll < 0.5:
        return (255, random.randint(80, 140), 20)   # bright orange
    elif roll < 0.8:
        return (255, random.randint(30, 80), 10)    # deep red-orange
    else:
        return (220, 220, random.randint(60, 100))  # bright flash
