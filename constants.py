"""
Populous Python - Game Constants
"""

# Screen
SCREEN_W = 1280
SCREEN_H = 720
FPS = 60
TITLE = "Populous — Python Edition"

# Isometric tile dimensions (tile diamond)
TILE_W = 64       # full width of tile diamond
TILE_H = 32       # full height of tile diamond
H_SCALE = 7       # pixels per height unit (vertical exaggeration)

# Grid: VERTS×VERTS vertices → (VERTS-1)×(VERTS-1) tiles
VERTS = 65        # must give VERTS-1 tiles across

# Terrain height range
WATER_LEVEL = 3
MIN_H = 0
MAX_H = 18

# Factions
PLAYER = 0
ENEMY  = 1

# God powers
P_RAISE    = 0
P_LOWER    = 1
P_QUAKE    = 2
P_VOLCANO  = 3
P_FLOOD    = 4
P_ARMA     = 5

POWER_NAMES = [
    "Raise Land",
    "Lower Land",
    "Earthquake",
    "Volcano",
    "Flood",
    "Armageddon",
]

POWER_COSTS = {
    P_RAISE:   0,
    P_LOWER:   0,
    P_QUAKE:  10,
    P_VOLCANO:25,
    P_FLOOD:  20,
    P_ARMA:  100,
}

MAX_MANA = 100.0
MANA_RATE = 0.04   # mana gained per follower per second

# Settler behaviour
SETTLER_SPEED     = 1.8   # grid tiles per second
SETTLER_VISION    = 10.0  # grid tiles
FIGHT_RANGE       = 1.5
BUILD_FLAT_THRESH = 1     # max vertex height diff to start building
BUILD_TIME        = 6.0   # seconds to erect a building
SPAWN_INTERVAL    = 30.0  # seconds between new settlers from a house
FIGHT_DAMAGE      = 0.8   # HP per second
SETTLER_MAX_HP    = 5.0

# Building types
B_HUT      = 0
B_HOUSE    = 1
B_MANSION  = 2
B_CASTLE   = 3

BUILDING_CAPACITY  = {B_HUT: 1, B_HOUSE: 2, B_MANSION: 4, B_CASTLE: 8}
BUILDING_UPGRADE_T = {B_HUT: 20.0, B_HOUSE: 40.0, B_MANSION: 80.0}  # seconds till upgrade

# Colours  (kept as module-level tuples)
C_WATER_ABYSS   = (8,   42, 108)
C_WATER_DEEP    = (18,  65, 160)
C_WATER_SHALLOW = (42, 110, 215)
C_SAND          = (205, 180, 115)
C_GRASS_LO      = (98,  170,  52)
C_GRASS_MID     = (72,  142,  38)
C_GRASS_HI      = (52,  112,  26)
C_ROCK          = (105, 97,   87)
C_SNOW          = (218, 224, 248)

C_PLAYER        = (70,  130, 255)
C_ENEMY         = (255,  55,  55)

# HUD layout
HUD_H       = 110
MINIMAP_SZ  = 150
