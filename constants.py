"""
Populous: The Beginning — Python Edition
Constants
"""

# Screen
SCREEN_W = 1280
SCREEN_H = 720
FPS = 60
TITLE = "Populous: The Beginning — Python Edition"

# Isometric tile
TILE_W = 64
TILE_H = 32
H_SCALE = 8       # pixels per height unit — more dramatic than before

# Grid: VERTS×VERTS vertices → (VERTS-1)×(VERTS-1) tiles
VERTS = 65

# Terrain heights
WATER_LEVEL = 3
MIN_H = 0
MAX_H = 20

# Factions
PLAYER = 0
ENEMY  = 1

# Entity types
E_SHAMAN   = 0
E_BRAVE    = 1
E_WARRIOR  = 2
E_FIREWARRIOR = 3

# Building types
B_HUT        = 0   # basic dwelling, spawns braves
B_GUARD_POST = 1   # defensive tower
B_WARRIOR_HUT= 2   # trains warriors
B_FIREWARRIOR_HUT = 3

BUILDING_CAPACITY = {B_HUT: 5, B_GUARD_POST: 0, B_WARRIOR_HUT: 0, B_FIREWARRIOR_HUT: 0}
BUILDING_NAMES    = {B_HUT: "Hut", B_GUARD_POST: "Guard Post",
                     B_WARRIOR_HUT: "Warrior Hut", B_FIREWARRIOR_HUT: "Firewarrior Hut"}
BUILD_TIME        = {B_HUT: 5.0, B_GUARD_POST: 8.0,
                     B_WARRIOR_HUT: 10.0, B_FIREWARRIOR_HUT: 10.0}

# PTB Spells
SP_BLAST       = 0
SP_LIGHTNING   = 1
SP_LANDBRIDGE  = 2
SP_SWAMP       = 3
SP_VOLCANO     = 4
SP_FLATTEN     = 5
SP_FIRESTORM   = 6
SP_ARMAGEDDON  = 7

SPELL_NAMES = [
    "Blast", "Lightning", "Landbridge",
    "Swamp", "Volcano", "Flatten",
    "Firestorm", "Armageddon",
]
SPELL_COSTS = {
    SP_BLAST:      5,
    SP_LIGHTNING:  10,
    SP_LANDBRIDGE: 15,
    SP_SWAMP:      15,
    SP_VOLCANO:    35,
    SP_FLATTEN:    8,
    SP_FIRESTORM:  40,
    SP_ARMAGEDDON: 100,
}
SPELL_KEYS = ['1','2','3','4','5','6','7','8']

MAX_MANA  = 100.0
MANA_RATE = 0.03   # per follower per second (braves only)

# Entity stats
SHAMAN_HP   = 30.0
BRAVE_HP    = 3.0
WARRIOR_HP  = 8.0
FIREWARRIOR_HP = 5.0

BRAVE_SPEED    = 2.2   # tiles/sec
WARRIOR_SPEED  = 2.8
SHAMAN_SPEED   = 3.0
FOLLOW_RADIUS  = 12.0  # braves follow shaman if within this range
BUILD_RADIUS   = 5.0   # braves build within this distance of shaman

FIGHT_RANGE    = 1.8
BRAVE_DMG      = 0.4
WARRIOR_DMG    = 1.2
SHAMAN_DMG     = 2.0
FIREWARRIOR_DMG = 0.8
FIREWARRIOR_RANGE = 6.0

# Brave → Warrior conversion (at warrior hut)
TRAIN_TIME = 15.0

# Colours
C_PLAYER = (50,  140, 255)
C_ENEMY  = (255,  60,  60)

# HUD
HUD_H      = 100
MINIMAP_SZ = 150
