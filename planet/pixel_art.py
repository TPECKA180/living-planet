from .modern_catalog import BUILDINGS as MODERN_BUILDINGS,UNITS as MODERN_UNITS
from .modern_art import building_sprite,unit_sprite
"""Code-native 32px dark-fantasy atlas, rendered only inside the viewport."""
import math
from collections import OrderedDict
import pygame as pg

PALETTE={'grass':(44,53,43),'forest':(25,40,36),'mountain':(64,65,70),
         'water':(17,38,55),'science':(41,35,63),'resource':(63,48,37)}


class PixelAtlas:
    def __init__(self,scaled_budget=48*1024*1024):
        self.cache={}; self.scaled=OrderedDict()
        self.scaled_budget=max(0,int(scaled_budget)); self.scaled_bytes=0

    def tile(self,terrain,variant):
        variant%=16
        key=('tile',terrain,variant)
        if key in self.cache: return self.cache[key]
        s=pg.Surface((32,32)); motif=variant%4; tone=variant//4
        base=tuple(max(0,min(255,v+tone*3-4)) for v in PALETTE[terrain]); s.fill(base)
        def r(color,box): pg.draw.rect(s,color,box)
        for i in range(18):
            x=(i*13+variant*7)%30; y=(i*19+variant*11)%30
            shade=tuple(max(0,min(255,v+(6 if i%2 else -6))) for v in base)
            r(shade,(x,y,2+i%3,1+i%2))
        if terrain=='grass':
            for i in range(5):
                x=3+(i*7+tone*3)%26; y=5+(i*11+tone*5)%24
                r((29,40,34),(x-1,y+2,5,2)); r((73+tone*4,85,53),(x,y-2,1,5)); r((91,95,62),(x+2,y,1,3))
            if motif==0: # wind-swept meadow
                for x,y in ((7,9),(22,21),(13,27)): r((161,149,92),(x,y,2,1))
            elif motif==1: # mushrooms and heath
                for x,y in ((9,17),(22,8),(24,26)):
                    r((126,112,85),(x,y,1,4)); r((135+tone*10,73,68),(x-2,y-1,5,2))
            elif motif==2: # broken ancient stones
                for x,y in ((9,16),(21,20)):
                    r((26,32,32),(x-3,y+4,9,3)); r((82,86,79),(x-2,y-4,5,9)); r((130,127,108),(x-2,y-4,2,7))
            else: # low brambles
                for x,y in ((8,10),(22,24)):
                    pg.draw.ellipse(s,(36,54,43),(x-5,y-3,10,7)); r((137,119,99),(x-2,y-1,1,2)); r((121,87,88),(x+2,y,2,1))
        elif terrain=='forest':
            points=((8+tone,19),(23,26-tone),(21-tone,11))
            for x,y in points:
                r((13,23,24),(x-5,y+5,12,3)); r((76,57,43),(x-1,y-4,3,12))
                if motif in (0,1):
                    for level,width in ((-12,3),(-8,5),(-4,7),(0,8)):
                        pg.draw.polygon(s,(26+tone*4,55+tone*3+motif*5,43+motif*5),[(x,y+level-5),(x-width,y+level+3),(x+width,y+level+3)])
                        pg.draw.line(s,(56,78+tone*3,57),(x,y+level-4),(x-width+1,y+level+2),1)
                elif motif==2:
                    for dx,dy in ((-3,-7),(2,-10),(4,-4)):
                        pg.draw.ellipse(s,(37+tone*3,65,49),(x+dx-5,y+dy-6,10,9))
                    r((99,107,68),(x-3,y-12,2,2))
                else:
                    pg.draw.line(s,(105,99,83),(x,y-10),(x,y+6),2)
                    for dx,dy in ((-5,-7),(5,-10),(-4,-1),(4,-4)):
                        pg.draw.line(s,(91,88,76),(x,y+dy+4),(x+dx,y+dy),1)
                    r((66,79,57),(x-5,y+4,6,2))
        elif terrain=='mountain':
            peak=8+motif*4; height=2+tone
            pg.draw.polygon(s,(27,31,39),[(0,29),(peak,height),(25,12+motif),(32,29)])
            pg.draw.polygon(s,(111+tone*4,108+tone*3,107),[(2,27),(peak,height),(peak+2,28)])
            pg.draw.polygon(s,(68+motif*4,73,85),[(peak,height),(29,28),(peak+2,28)])
            if motif!=3: pg.draw.polygon(s,(160,158,149),[(peak-3,height+7),(peak,height),(peak+3,height+8),(peak,height+6)])
            if motif==1: pg.draw.line(s,(43,47,57),(peak,12),(peak+5,26),2)
            if motif==2: r((44,44,51),(5,23,8,5)); r((20,27,35),(7,24,5,4))
            if motif==3:
                for x,y in ((6,23),(14,27),(25,25)): r((131,105,71),(x,y,3,2))
        elif terrain=='water':
            for i in range(7):
                x=(i*11+variant*5)%25; y=2+i*4
                r((26+tone*3,58+motif*2,74),(x,y,5+motif,1)); r((43,77+tone*3,90),(x+2,y+1,4,1))
            if motif==1:
                pg.draw.arc(s,(38,72,88),(7,9,17,12),.3,4.7,1)
                pg.draw.arc(s,(49,83,96),(11,12,9,6),1,5.5,1)
            elif motif==2:
                for x,y in ((4,11),(17,25)): r((73,99,110),(x,y,8,1)); r((32,62,80),(x+2,y+2,6,1))
            elif motif==3: r((11,27,44),(0,18,32,3)); r((22,49,67),(0,22,32,2))
        elif terrain=='science':
            r((27,25,41),(3,26,27,3))
            points=(((8,25,11),(17,26,22),(26,24,12)),((10,25,21),(22,24,16)),((7,25,9),(15,24,14),(24,25,21)),((9,25,16),(22,26,23)))[motif]
            for x,y,h in points:
                pg.draw.polygon(s,(55+tone*5,44,86),[(x-4,y),(x-3,y-h+4),(x,y-h),(x+4,y-h+4),(x+3,y)])
                pg.draw.polygon(s,(142+tone*8,107+motif*7,198),[(x,y-h),(x-2,y-h+4),(x-1,y-1),(x+1,y)])
                pg.draw.line(s,(214,179,234),(x,y-h+2),(x+1,y-5),1)
            if motif==3:
                pg.draw.ellipse(s,(106,82,142),(2,23,28,7),1)
        elif terrain=='resource':
            ore=((204,140,65),(146,160,163),(174,99,67),(191,171,99))[motif]
            pg.draw.polygon(s,(30,32,36),[(2,28),(5,17-motif),(15,10+tone),(25,16),(30,29)])
            pg.draw.polygon(s,(84+tone*3,72,62),[(5,25),(13,12+tone),(19,26)])
            for i in range(5):
                x=6+(i*7+tone*3)%20; y=16+(i*5+motif*2)%12
                r((76,54,40),(x-1,y-1,5,4)); r(ore,(x,y,3,2)); r(tuple(min(255,v+35) for v in ore),(x,y,1,1))
            if motif==2: r((24,26,30),(18,23,8,5))
        self.cache[key]=s; return s

    def building(self,kind,color):
        key=('building',kind,tuple(color))
        if key in self.cache: return self.cache[key]
        if kind in MODERN_BUILDINGS:
            self.cache[key]=building_sprite(kind,color); return self.cache[key]
        s=pg.Surface((32,32),pg.SRCALPHA)
        def r(c,box): pg.draw.rect(s,c,box)
        ink=(14,17,24); stone=(98,96,99); light=(149,141,132); dark=(53,54,66); warm=(243,178,75)
        r((10,15,22,160),(3,25,27,5))
        if kind=='tower':
            r(ink,(9,5,16,25)); r(stone,(11,7,12,22)); r(light,(11,8,3,20))
            for x in (9,15,21): r(light,(x,2,4,6))
            r((55,45,73),(15,11,5,8)); r((212,164,244),(16,12,2,5)); r(ink,(15,24,5,6))
            r(color,(25,8,5,7)); r((156,139,109),(24,3,1,21))
            pg.draw.ellipse(s,(124,98,166),(5,25,23,6),1)
        elif kind=='wall':
            r(ink,(1,13,30,17)); r(stone,(2,15,28,14)); r(light,(2,14,28,2))
            for x in range(2,30,6): r(light,(x,9,4,7))
            for y in (19,24,28):
                pg.draw.line(s,dark,(2,y),(29,y),1)
                for x in range(4+(y%2)*4,29,8): pg.draw.line(s,dark,(x,y-4),(x,y),1)
            r(color,(13,17,5,7))
        elif kind=='castle':
            r(ink,(3,7,26,20)); r(stone,(5,11,22,15)); r(dark,(11,10,12,16))
            for x in (4,23):
                r(stone,(x,6,5,20)); r(light,(x,8,2,16))
                for bx in (x,x+3): r(light,(bx,3,2,5))
            for y in (12,18,24): pg.draw.line(s,(69,67,77),(5,y),(27,y),1)
            r(ink,(13,18,7,9)); r((63,48,39),(15,19,3,7)); r(warm,(7,12,2,3)); r(warm,(24,12,2,3))
            r((164,146,112),(16,0,1,12)); r(color,(17,1,7,5))
        elif kind=='lab':
            r(ink,(10,8,14,19)); r(stone,(12,9,10,17)); r(light,(12,10,2,14))
            pg.draw.polygon(s,ink,[(8,10),(17,0),(26,10)])
            pg.draw.polygon(s,(83,56,107),[(10,9),(17,2),(24,9)])
            r((157,112,204),(16,12,3,7)); r((219,183,245),(17,12,1,5)); r(ink,(15,23,4,4))
            r((53,42,76),(6,24,4,3)); r((177,130,218),(7,22,2,3)); r(color,(23,15,4,5))
        elif kind=='mine':
            pg.draw.polygon(s,ink,[(3,27),(5,10),(18,5),(28,16),(28,27)])
            pg.draw.polygon(s,(81,76,76),[(5,25),(7,12),(18,7),(26,17),(26,25)])
            r((30,24,26),(10,16,12,11)); r((116,81,48),(9,15,3,12)); r((158,116,63),(8,13,16,3)); r((110,77,49),(21,15,3,12))
            r((196,181,151),(13,23,1,9)); r((196,181,151),(20,23,1,9))
            for y in (24,28,31): r((110,88,63),(12,y,10,1))
            r(warm,(6,18,2,4)); r((211,140,56),(26,24,4,3))
        elif kind=='tavern':
            r(ink,(5,12,22,16)); r((103,76,56),(7,13,18,13)); r((145,110,75),(8,15,2,10))
            pg.draw.polygon(s,ink,[(3,14),(15,2),(29,14)])
            pg.draw.polygon(s,(113,49,52),[(5,12),(15,4),(27,12)])
            for y in (9,11): r((152,73,62),(8,y,15,1))
            r(ink,(14,20,5,7)); r(warm,(9,17,3,4)); r(warm,(21,17,3,4))
            r((73,69,70),(23,3,3,8)); r((128,119,111),(24,2,3,2)); r(color,(27,15,4,6))
        elif kind=='arsenal':
            r(ink,(4,11,25,17)); r(dark,(6,13,21,13))
            pg.draw.polygon(s,(113,105,103),[(3,13),(10,5),(23,5),(30,13)])
            r((68,53,46),(11,17,11,10)); r((161,145,117),(16,17,1,10))
            for x in (7,24): r((186,177,156),(x,15,1,12)); r((113,103,104),(x-2,14,5,2))
            r(color,(12,10,10,3))
        self.cache[key]=s; return s

    def unit(self,kind,color):
        key=('unit',kind,tuple(color))
        if key in self.cache: return self.cache[key]
        if kind in MODERN_UNITS:
            self.cache[key]=unit_sprite(kind,color); return self.cache[key]
        s=pg.Surface((32,32),pg.SRCALPHA)
        if kind=='ship':
            pg.draw.polygon(s,(91,63,44),[(2,22),(29,22),(24,29),(8,29)])
            pg.draw.line(s,(174,143,94),(15,4),(15,24),2)
            pg.draw.polygon(s,color,[(16,5),(27,19),(16,18)])
            pg.draw.polygon(s,(189,177,149),[(13,7),(5,18),(13,18)])
            self.cache[key]=s; return s
        pg.draw.ellipse(s,(7,12,18,180),(14,27,15,4))
        pg.draw.rect(s,(17,20,28),(19,14,8,15)); pg.draw.polygon(s,color,[(21,15),(25,15),(28,27),(17,27)])
        pg.draw.rect(s,(164,127,96),(21,13,4,4)); pg.draw.rect(s,(20,23,30),(21,27,2,4)); pg.draw.rect(s,(20,23,30),(25,27,2,4))
        if kind=='scout':
            pg.draw.polygon(s,(38,44,49),[(18,15),(22,8),(27,15)]); pg.draw.rect(s,color,(21,10,3,2))
            pg.draw.line(s,(173,130,74),(29,15),(29,27),1); pg.draw.line(s,(213,195,142),(28,16),(28,26),1)
        elif kind=='builder':
            pg.draw.rect(s,(130,112,77),(19,10,8,4)); pg.draw.line(s,(156,113,68),(29,14),(27,25),2)
            pg.draw.rect(s,(161,157,150),(25,13,7,3))
        else:
            pg.draw.rect(s,(153,155,155),(20,9,6,6)); pg.draw.rect(s,(37,41,48),(21,12,4,2))
            pg.draw.line(s,(206,206,187),(30,9),(29,25),2); pg.draw.rect(s,(113,105,86),(27,21,6,2))
            pg.draw.rect(s,(112,107,101),(15,19,5,7)); pg.draw.rect(s,color,(16,20,3,4))
        self.cache[key]=s; return s

    def sized(self,surface,size):
        key=(id(surface),size)
        if key in self.scaled:
            self.scaled.move_to_end(key)
            return self.scaled[key]
        # A count limit allowed gigabytes of large sprites after repeated zooms.
        # Evict BEFORE allocation; retain the original pixel art at every zoom.
        estimated=size*size*surface.get_bytesize()
        while self.scaled and self.scaled_bytes+estimated>self.scaled_budget:
            _,old=self.scaled.popitem(last=False)
            self.scaled_bytes-=old.get_pitch()*old.get_height()
        result=pg.transform.scale(surface,(size,size))
        actual=result.get_pitch()*result.get_height()
        while self.scaled and self.scaled_bytes+actual>self.scaled_budget:
            _,old=self.scaled.popitem(last=False)
            self.scaled_bytes-=old.get_pitch()*old.get_height()
        if actual<=self.scaled_budget:
            self.scaled[key]=result; self.scaled_bytes+=actual
        return result

    def draw_world(self,screen,world,rect,origin,scale):
        ox,oy=origin; size=max(1,int(math.ceil(scale)))
        x0=max(0,int(math.floor((rect.left-ox)/scale))); x1=min(world.size,int(math.ceil((rect.right-ox)/scale))+1)
        y0=max(0,int(math.floor((rect.top-oy)/scale))); y1=min(world.size,int(math.ceil((rect.bottom-oy)/scale))+1)
        colors={s.id:s.color for s in world.states}
        for y in range(y0,y1):
            for x in range(x0,x1):
                cell=world.cell([x,y]); px=int(ox+x*scale); py=int(oy+y*scale)
                variant=((x*73856093)^(y*19349663)^world.seed)%16
                screen.blit(self.sized(self.tile(cell.terrain,variant),size),(px,py))
                if cell.owner:
                    color=colors[cell.owner]
                    for point,edge in (([x-1,y],(px,py,1,size)),([x+1,y],(px+size-1,py,1,size)),([x,y-1],(px,py,size,1)),([x,y+1],(px,py+size-1,size,1))):
                        a,b=point
                        if not(0<=a<world.size and 0<=b<world.size) or world.cell(point).owner!=cell.owner:
                            pg.draw.rect(screen,color,edge)
                if cell.terrain=='water':
                    for point,edge in (([x-1,y],(px+1,py,2,size)),([x+1,y],(px+size-3,py,2,size)),([x,y-1],(px,py+1,size,2)),([x,y+1],(px,py+size-3,size,2))):
                        a,b=point
                        if 0<=a<world.size and 0<=b<world.size and world.cell(point).terrain!='water': pg.draw.rect(screen,(88,107,108),edge)
                if cell.radiation:
                    pg.draw.rect(screen,(154,166,57),(px+1,py+1,size-2,size-2),max(1,size//18))
                    pg.draw.circle(screen,(201,209,82),(px+size//5,py+size//5),max(1,size//12),1)
                if cell.building: screen.blit(self.sized(self.building(cell.building,colors.get(cell.owner,(151,144,117))),size),(px,py))
                if world.wall_hitpoints(cell)>0:
                    hp=world.wall_hitpoints(cell); bar=max(4,size-6)
                    pg.draw.rect(screen,(34,29,29),(px+3,py+3,bar,3))
                    pg.draw.rect(screen,(196,168,118),(px+3,py+3,int(bar*hp/((20 if cell.building=='wall' else MODERN_BUILDINGS[cell.building]['barrier'])*cell.building_level)),3))
                if cell.fortification:
                    pg.draw.rect(screen,(159,140,112),(px+3,py+size-5,max(3,size-6),max(2,cell.fortification)))
                if cell.population and scale>=22:
                    pg.draw.rect(screen,(189,162,125),(px+int(scale*.14),py+int(scale*.77),max(2,int(scale*.09)),max(3,int(scale*.16))))
