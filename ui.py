"""
Populous: The Beginning — HUD

Bottom spell bar (PTB-style icon row), mana bar, follower count, minimap.
"""

from __future__ import annotations
import math, pygame
from typing import TYPE_CHECKING
from constants import (
    SCREEN_W, SCREEN_H, HUD_H, MINIMAP_SZ,
    SPELL_NAMES, SPELL_COSTS, MAX_MANA, SPELL_KEYS,
    SP_BLAST,SP_LIGHTNING,SP_LANDBRIDGE,SP_SWAMP,
    SP_VOLCANO,SP_FLATTEN,SP_FIRESTORM,SP_ARMAGEDDON,
    PLAYER, ENEMY, C_PLAYER, C_ENEMY,
)
if TYPE_CHECKING:
    from game import Game

_SPELL_ICONS = {
    SP_BLAST:      ((255,160,40),   'blast'),
    SP_LIGHTNING:  ((200,220,255),  'bolt'),
    SP_LANDBRIDGE: ((150,200,120),  'bridge'),
    SP_SWAMP:      ((80, 140, 50),  'swamp'),
    SP_VOLCANO:    ((255,100,30),   'volcano'),
    SP_FLATTEN:    ((180,200,120),  'flatten'),
    SP_FIRESTORM:  ((255,60, 20),   'firestorm'),
    SP_ARMAGEDDON: ((200,40, 200),  'arma'),
}


class HUD:
    def __init__(self, screen:pygame.Surface):
        self.screen=screen
        pygame.font.init()
        self._f12=pygame.font.SysFont("monospace",12)
        self._f14=pygame.font.SysFont("monospace",14,bold=True)
        self._f20=pygame.font.SysFont("monospace",20,bold=True)
        self._f26=pygame.font.SysFont("monospace",26,bold=True)
        self._tick=0.0
        self._spell_rects=[]
        self._notifications=[]
        self._panel=pygame.Surface((SCREEN_W,HUD_H),pygame.SRCALPHA)

    def update(self,dt):
        self._tick+=dt
        self._notifications=[n for n in self._notifications if n['life']>0]
        for n in self._notifications: n['life']-=dt

    def draw(self,game:'Game'):
        self._panel.fill((0,0,0,0))
        self._bg()
        self._mana(game.mana)
        self._spells(game.selected_spell,game.mana)
        self._population(game)
        self.screen.blit(self._panel,(0,SCREEN_H-HUD_H))

        mm=game.renderer.draw_minimap(game.terrain,
                                       game.settlers+game.buildings+
                                       ([game.player_shaman] if game.player_shaman else [])+
                                       ([game.enemy_shaman]  if game.enemy_shaman  else []))
        self.screen.blit(mm,(SCREEN_W-MINIMAP_SZ-8,8))
        self._draw_notifications()

    def notify(self,text,colour=(255,240,80)):
        self._notifications.append({'text':text,'colour':colour,'life':3.5})

    def handle_click(self,sx,sy)->int|None:
        py=sy-(SCREEN_H-HUD_H)
        if py<0: return None
        for i,rect in enumerate(self._spell_rects):
            if rect.collidepoint(sx,py): return i
        return None

    # ------------------------------------------------------------------ #

    def _bg(self):
        pygame.draw.rect(self._panel,(12,10,22,240),(0,0,SCREEN_W,HUD_H))
        # Ornate top edge
        for i in range(3):
            a=110-i*35
            pygame.draw.line(self._panel,(80,150,255,a),(0,i),(SCREEN_W,i))

    def _mana(self,mana):
        # Globe-style mana indicator on the left
        gx,gy=60,HUD_H//2; gr=36
        # Outer ring
        pygame.draw.circle(self._panel,(30,20,60),  (gx,gy),gr)
        pygame.draw.circle(self._panel,(60,40,120), (gx,gy),gr,2)
        # Fill based on mana
        frac=mana/MAX_MANA
        fill_h=int(gr*2*frac)
        fill_y=gy+gr-fill_h
        clip=pygame.Surface((gr*2,gr*2),pygame.SRCALPHA)
        pygame.draw.circle(clip,(0,0,0,0),(gr,gr),gr)  # clear
        pulse=0.8+0.2*math.sin(self._tick*2.5)
        bc=int(60*pulse); gc=int(160*pulse); rc=int(255*pulse)
        pygame.draw.rect(clip,(rc,gc,bc,220),(0,gr*2-fill_h,gr*2,fill_h))
        # Clip to circle
        mask=pygame.Surface((gr*2,gr*2),pygame.SRCALPHA)
        pygame.draw.circle(mask,(255,255,255,255),(gr,gr),gr-2)
        clip.blit(mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
        self._panel.blit(clip,(gx-gr,gy-gr))
        # Shine
        pygame.draw.circle(self._panel,(140,180,255,60),(gx-gr//3,gy-gr//3),gr//3)
        pygame.draw.circle(self._panel,(80,100,200),    (gx,gy),gr,2)
        # Label
        lbl=self._f12.render(f"{int(mana)}/{int(MAX_MANA)}",True,(160,210,255))
        self._panel.blit(lbl,(gx-lbl.get_width()//2,gy+gr+4))

    def _spells(self,selected,mana):
        n_spells=8; btn=70; gap=6
        total=n_spells*(btn+gap)-gap
        start_x=(SCREEN_W-total)//2; start_y=8

        self._spell_rects=[]
        for i in range(n_spells):
            x=start_x+i*(btn+gap)
            rect=pygame.Rect(x,start_y,btn,btn-4)
            self._spell_rects.append(rect)

            icol,itype=_SPELL_ICONS[i]
            cost=SPELL_COSTS[i]
            can=mana>=cost; sel=(selected==i)

            # Background
            bg_alpha=220 if sel else 160
            bg=tuple(max(0,c-70) for c in icol)
            pygame.draw.rect(self._panel,(*bg,bg_alpha),rect,border_radius=7)

            # Selected highlight
            if sel:
                p=0.6+0.4*math.sin(self._tick*5)
                bc=tuple(min(255,int(c*p)) for c in icol)
                pygame.draw.rect(self._panel,bc,rect,2,border_radius=7)
                # Glow
                glow=pygame.Surface((btn+8,btn+4),pygame.SRCALPHA)
                pygame.draw.rect(glow,(*bc,40),(0,0,btn+8,btn+4),border_radius=9)
                self._panel.blit(glow,(x-4,start_y-2))
            else:
                pygame.draw.rect(self._panel,(50,50,70),rect,1,border_radius=7)

            if not can:
                grey=pygame.Surface((btn,btn-4),pygame.SRCALPHA)
                grey.fill((0,0,0,100))
                self._panel.blit(grey,rect.topleft)

            # Icon drawing
            cx2=x+btn//2; cy2=start_y+(btn-4)//2
            self._draw_spell_icon(cx2,cy2,itype,icol,can)

            # Cost
            if cost>0:
                ct=self._f12.render(str(cost),True,
                                    (220,220,80) if can else (80,80,80))
                self._panel.blit(ct,(x+4,start_y+btn-18))

            # Key hint
            kt=self._f12.render(f"[{SPELL_KEYS[i]}]",True,(100,100,130))
            self._panel.blit(kt,(x+btn-kt.get_width()-3,start_y+btn-18))

    def _draw_spell_icon(self,cx,cy,itype,col,enabled):
        c=col if enabled else (80,80,80)
        if itype=='blast':
            for r in [14,10,6]:
                pygame.draw.circle(self._panel,c,(cx,cy),r,max(1,r//4))
        elif itype=='bolt':
            pts=[(cx,cy-15),(cx+4,cy-3),(cx+8,cy-3),(cx,cy+6),(cx-4,cy-2),(cx-8,cy-2)]
            pygame.draw.polygon(self._panel,c,pts)
        elif itype=='bridge':
            for i in range(-12,13,4):
                pygame.draw.rect(self._panel,c,(cx+i-2,cy-4,4,8))
            pygame.draw.line(self._panel,c,(cx-12,cy-8),(cx+12,cy-8),2)
        elif itype=='swamp':
            pygame.draw.ellipse(self._panel,c,(cx-12,cy-6,24,12))
            pygame.draw.ellipse(self._panel,c,(cx-8,cy-10,8,8))
            pygame.draw.ellipse(self._panel,c,(cx+2,cy-10,8,8))
        elif itype=='volcano':
            pts=[(cx,cy-14),(cx-10,cy+6),(cx+10,cy+6)]
            pygame.draw.polygon(self._panel,c,pts)
            pygame.draw.polygon(self._panel,(255,80,20),[(cx,cy-14),(cx-3,cy-6),(cx+3,cy-6)])
        elif itype=='flatten':
            pygame.draw.line(self._panel,c,(cx-12,cy),(cx+12,cy),3)
            for ix in [-10,-4,2,8]:
                pygame.draw.line(self._panel,c,(cx+ix,cy-8),(cx+ix+2,cy),2)
        elif itype=='firestorm':
            for ix,iy in [(-8,-10),(0,-14),(8,-10),(-4,-4),(4,-4)]:
                r=3+(abs(ix)+abs(iy))//8
                pygame.draw.circle(self._panel,c,(cx+ix,cy+iy),r)
        elif itype=='arma':
            pygame.draw.circle(self._panel,c,(cx,cy),14,2)
            for a in range(0,360,45):
                ra=math.radians(a)
                pygame.draw.line(self._panel,c,
                                  (cx+int(math.cos(ra)*6),cy+int(math.sin(ra)*6)),
                                  (cx+int(math.cos(ra)*13),cy+int(math.sin(ra)*13)),2)

    def _population(self,game:'Game'):
        pc=sum(1 for s in game.settlers if s.alive and s.faction==PLAYER)
        ec=sum(1 for s in game.settlers if s.alive and s.faction==ENEMY)
        pb=sum(1 for b in game.buildings if b.alive and b.faction==PLAYER and b.built)
        eb=sum(1 for b in game.buildings if b.alive and b.faction==ENEMY and b.built)

        x=SCREEN_W-MINIMAP_SZ-300; y=12
        self._panel.blit(self._f14.render(f"YOUR TRIBE",True,C_PLAYER),(x,y))
        self._panel.blit(self._f20.render(f"{pc} followers  {pb} huts",True,C_PLAYER),(x,y+16))

        self._panel.blit(self._f14.render(f"ENEMY TRIBE",True,C_ENEMY),(x,y+42))
        self._panel.blit(self._f20.render(f"{ec} followers  {eb} huts",True,C_ENEMY),(x,y+58))

        # Shaman status
        if game.player_shaman:
            sh=game.player_shaman
            hp_t=self._f12.render(f"Shaman HP: {int(sh.hp)}/{int(sh.max_hp)}",
                                   True,(160,210,255))
            self._panel.blit(hp_t,(x,y+82))

    def _draw_notifications(self):
        y=0
        for n in reversed(self._notifications[-4:]):
            txt=self._f26.render(n['text'],True,n['colour'])
            shadow=self._f26.render(n['text'],True,(0,0,0))
            cx=SCREEN_W//2-txt.get_width()//2
            wy=SCREEN_H//2-80+y
            self.screen.blit(shadow,(cx+2,wy+2))
            self.screen.blit(txt,   (cx,  wy))
            y+=36


class VictoryScreen:
    def __init__(self,screen):
        self.screen=screen
        pygame.font.init()
        self._f48=pygame.font.SysFont("monospace",48,bold=True)
        self._f22=pygame.font.SysFont("monospace",22)

    def draw(self,winner):
        ov=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        ov.fill((0,0,0,170)); self.screen.blit(ov,(0,0))
        if winner==PLAYER:
            msg="VICTORY!"; sub="Your tribe reigns supreme!"; col=(80,180,255)
        else:
            msg="DEFEATED!"; sub="Your shaman has fallen."; col=(255,80,80)
        t=self._f48.render(msg,True,col)
        self.screen.blit(t,(SCREEN_W//2-t.get_width()//2,SCREEN_H//2-60))
        s=self._f22.render(sub,True,(220,220,220))
        self.screen.blit(s,(SCREEN_W//2-s.get_width()//2,SCREEN_H//2+10))
        r=self._f22.render("Press R to restart  |  Q to quit",True,(150,150,150))
        self.screen.blit(r,(SCREEN_W//2-r.get_width()//2,SCREEN_H//2+50))
