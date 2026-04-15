# Populous — Python Edition

A modern Python remake of the classic 1989 god game **Populous** by Bullfrog Productions, with enhanced isometric graphics.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Pygame](https://img.shields.io/badge/Pygame-2.5%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features

| Feature | Description |
|---|---|
| **Vertex-based heightmap** | 64×64 terrain of individually sculpted vertices with smooth colour gradients |
| **Isometric renderer** | Per-face shading (top / left / right wall), animated water, painter-order draw |
| **Terrain deformation** | Raise / lower / flatten land in real time |
| **Autonomous settlers** | State-machine AI: wander → seek flat → build → fight |
| **Buildings** | Hut → House → Mansion → Castle auto-upgrade over time |
| **God powers** | Raise Land, Lower Land, Earthquake, Volcano, Flood, Armageddon |
| **Enemy AI** | Opposing god uses powers against you strategically |
| **Mana system** | Population grows mana; powers cost mana |
| **Particle effects** | Lava fountains, ash clouds, water splashes, quake dust |
| **HUD & Minimap** | Live population counts, mana bar, minimap overview |
| **Screen shake** | Dynamic camera shake on powerful god events |

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/populous-python.git
cd populous-python

# Install dependencies
pip install -r requirements.txt

# Run the game
python main.py
```

---

## Controls

| Input | Action |
|---|---|
| `WASD` / Arrow keys | Scroll camera |
| Mouse scroll | Vertical camera shift |
| **LMB** | Use selected god power at cursor |
| **RMB** | Quick raise land |
| **MMB** | Quick lower land |
| `R` | Select **Raise Land** (free) |
| `L` | Select **Lower Land** (free) |
| `Q` | Select **Earthquake** (10 mana) |
| `V` | Select **Volcano** (25 mana) |
| `F` | Select **Flood** (20 mana) |
| `A` | **Armageddon** (100 mana) |
| `Escape` | Quit |

---

## How to Play

1. **Build your tribe** — Your blue followers spawn from your starting castle. They wander, find flat land, and build huts that grow into mansions over time.
2. **Shape the world** — Use **Raise** and **Lower Land** to create flat plateaus for your followers to settle, or build walls to separate them from the enemy.
3. **Earn mana** — The more followers you have, the faster your mana bar fills.
4. **Unleash god powers** — Use Earthquake, Volcano, and Flood to devastate enemy settlements. Save up for **Armageddon** to end the game decisively.
5. **Win** — Eliminate all red (enemy) followers to claim victory.

---

## Architecture

```
populous-python/
├── main.py          — Entry point
├── game.py          — Game loop, state, event handling
├── terrain.py       — Vertex heightmap + diamond-square generation
├── renderer.py      — Isometric projection & all drawing
├── entities.py      — Settler & Building classes
├── powers.py        — God power implementations
├── particles.py     — Particle effect system
├── ai_opponent.py   — Enemy AI god player
├── ui.py            — HUD, minimap, victory screen
└── constants.py     — All tunable constants
```

---

## Requirements

- Python 3.10+
- pygame 2.5+
- numpy 1.24+

---

## License

MIT — free to use, modify, and distribute.

*Populous was created by Peter Molyneux and Bullfrog Productions (1989). This project is an independent fan remake for educational purposes.*
