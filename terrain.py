"""
Populous Python - Terrain (vertex-based heightmap)

The world is a VERTS×VERTS grid of HEIGHT vertices.
Each "tile" occupies the space between four adjacent vertices.
"""

import numpy as np
import random
import math
from constants import VERTS, MIN_H, MAX_H, WATER_LEVEL


class Terrain:
    """Vertex-based heightmap with diamond-square generation."""

    def __init__(self, size: int = VERTS):
        self.size = size           # number of vertices on each axis
        self.tiles = size - 1      # number of tiles on each axis
        self.h = np.zeros((size, size), dtype=np.int32)
        self._dirty = True         # signals renderer to rebuild surface
        self.generate()

    # ------------------------------------------------------------------ #
    #  Generation                                                          #
    # ------------------------------------------------------------------ #

    def generate(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)

        # diamond-square needs (2^n + 1) sized grid
        sz = self.size  # already 65 = 2^6 + 1
        grid = np.zeros((sz, sz), dtype=float)

        # seed corners
        for r, c in [(0, 0), (0, sz-1), (sz-1, 0), (sz-1, sz-1)]:
            grid[r, c] = random.uniform(4, 14)

        step = sz - 1
        roughness = 0.6
        scale = 8.0

        while step > 1:
            half = step // 2

            # Diamond step
            for r in range(0, sz - 1, step):
                for c in range(0, sz - 1, step):
                    avg = (grid[r, c] + grid[r, c+step] +
                           grid[r+step, c] + grid[r+step, c+step]) / 4.0
                    grid[r+half, c+half] = avg + random.uniform(-scale, scale)

            # Square step
            for r in range(0, sz, half):
                for c in range((r // half) % 2 * half, sz, step):
                    vals, cnt = 0.0, 0
                    for dr, dc in ((-half, 0), (half, 0), (0, -half), (0, half)):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < sz and 0 <= nc < sz:
                            vals += grid[nr, nc]
                            cnt += 1
                    grid[r, c] = vals / cnt + random.uniform(-scale, scale)

            step = half
            scale *= roughness

        # Normalise to [2, MAX_H]
        lo, hi = grid.min(), grid.max()
        if hi > lo:
            grid = (grid - lo) / (hi - lo) * (MAX_H - 2) + 2
        self.h[:] = np.clip(np.round(grid), MIN_H, MAX_H).astype(np.int32)

        self._taper_edges()
        self._dirty = True

    def _taper_edges(self):
        """Pull map edges below water to create a natural island."""
        n = self.size
        margin = n * 0.18
        for r in range(n):
            for c in range(n):
                dist = min(r, c, n - 1 - r, n - 1 - c)
                if dist < margin:
                    t = dist / margin          # 0 at edge → 1 at margin
                    t = t * t                  # ease in
                    self.h[r, c] = int(self.h[r, c] * t)

    # ------------------------------------------------------------------ #
    #  Queries                                                             #
    # ------------------------------------------------------------------ #

    def vertex_h(self, col: int, row: int) -> int:
        col = max(0, min(self.size - 1, col))
        row = max(0, min(self.size - 1, row))
        return int(self.h[row, col])

    def height_at(self, col: float, row: float) -> float:
        """Bilinear-interpolated height at a continuous grid position."""
        c0 = max(0, min(self.size - 2, int(col)))
        r0 = max(0, min(self.size - 2, int(row)))
        c1, r1 = c0 + 1, r0 + 1
        fc, fr = col - c0, row - r0
        return (self.h[r0, c0] * (1 - fc) * (1 - fr) +
                self.h[r0, c1] * fc       * (1 - fr) +
                self.h[r1, c0] * (1 - fc) * fr +
                self.h[r1, c1] * fc       * fr)

    def tile_avg_h(self, tc: int, tr: int) -> float:
        """Average height of the four vertices bounding tile (tc, tr)."""
        return (self.h[tr,   tc] + self.h[tr,   tc+1] +
                self.h[tr+1, tc] + self.h[tr+1, tc+1]) / 4.0

    def is_above_water(self, col: float, row: float) -> bool:
        return self.height_at(col, row) > WATER_LEVEL + 0.3

    def flatness(self, col: int, row: int, radius: int = 1) -> int:
        """Return max vertex height difference in the area (lower = flatter)."""
        n = self.size
        vals = []
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                r, c = row + dr, col + dc
                if 0 <= r < n and 0 <= c < n:
                    vals.append(self.h[r, c])
        if not vals:
            return 99
        return int(max(vals) - min(vals))

    # ------------------------------------------------------------------ #
    #  Modification                                                        #
    # ------------------------------------------------------------------ #

    def _clamp(self, v: int) -> int:
        return int(max(MIN_H, min(MAX_H, v)))

    def raise_area(self, col: float, row: float, radius: float = 2.5, amount: int = 1):
        n = self.size
        ri, ci = int(round(row)), int(round(col))
        ir = int(math.ceil(radius))
        for dr in range(-ir, ir + 1):
            for dc in range(-ir, ir + 1):
                r, c = ri + dr, ci + dc
                if 0 <= r < n and 0 <= c < n:
                    d = math.hypot(dr, dc)
                    if d <= radius:
                        factor = 1.0 - d / (radius + 0.001)
                        delta = max(1, round(amount * factor))
                        self.h[r, c] = self._clamp(self.h[r, c] + delta)
        self._dirty = True

    def lower_area(self, col: float, row: float, radius: float = 2.5, amount: int = 1):
        n = self.size
        ri, ci = int(round(row)), int(round(col))
        ir = int(math.ceil(radius))
        for dr in range(-ir, ir + 1):
            for dc in range(-ir, ir + 1):
                r, c = ri + dr, ci + dc
                if 0 <= r < n and 0 <= c < n:
                    d = math.hypot(dr, dc)
                    if d <= radius:
                        factor = 1.0 - d / (radius + 0.001)
                        delta = max(1, round(amount * factor))
                        self.h[r, c] = self._clamp(self.h[r, c] - delta)
        self._dirty = True

    def flatten_area(self, col: int, row: int, radius: int = 1):
        """Level the area to its current average (for building construction)."""
        n = self.size
        vals, cells = [], []
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                r, c = row + dr, col + dc
                if 0 <= r < n and 0 <= c < n:
                    vals.append(self.h[r, c])
                    cells.append((r, c))
        if vals:
            target = int(round(sum(vals) / len(vals)))
            for r, c in cells:
                self.h[r, c] = self._clamp(target)
        self._dirty = True

    def quake(self, col: float, row: float, radius: float = 6.0):
        """Randomise heights in an area (earthquake)."""
        n = self.size
        ri, ci = int(round(row)), int(round(col))
        ir = int(math.ceil(radius))
        for dr in range(-ir, ir + 1):
            for dc in range(-ir, ir + 1):
                r, c = ri + dr, ci + dc
                if 0 <= r < n and 0 <= c < n:
                    d = math.hypot(dr, dc)
                    if d <= radius:
                        delta = random.randint(-3, 3)
                        self.h[r, c] = self._clamp(self.h[r, c] + delta)
        self._dirty = True

    def volcano_erupt(self, col: float, row: float):
        """Raise a cone of rock around the eruption point."""
        n = self.size
        radius = 5.0
        peak = min(MAX_H, int(self.height_at(col, row)) + 8)
        ri, ci = int(round(row)), int(round(col))
        ir = int(math.ceil(radius))
        for dr in range(-ir, ir + 1):
            for dc in range(-ir, ir + 1):
                r, c = ri + dr, ci + dc
                if 0 <= r < n and 0 <= c < n:
                    d = math.hypot(dr, dc)
                    if d <= radius:
                        t = 1.0 - d / radius
                        target = int(WATER_LEVEL + 1 + (peak - WATER_LEVEL - 1) * t)
                        if target > self.h[r, c]:
                            self.h[r, c] = self._clamp(target)
        self._dirty = True

    def flood(self, col: float, row: float, radius: float = 7.0):
        """Lower land near water (simulates flood encroachment)."""
        n = self.size
        ri, ci = int(round(row)), int(round(col))
        ir = int(math.ceil(radius))
        for dr in range(-ir, ir + 1):
            for dc in range(-ir, ir + 1):
                r, c = ri + dr, ci + dc
                if 0 <= r < n and 0 <= c < n:
                    d = math.hypot(dr, dc)
                    if d <= radius and self.h[r, c] <= WATER_LEVEL + 2:
                        self.h[r, c] = self._clamp(self.h[r, c] - 2)
        self._dirty = True
