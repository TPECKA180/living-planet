"""32px industrial sprites drawn on the same dark-fantasy atlas as the first era."""
import pygame as pg


def building_sprite(kind,color):
    s=pg.Surface((32,32),pg.SRCALPHA); r=lambda c,b:pg.draw.rect(s,c,b)
    ink=(14,19,25); steel=(91,108,116); light=(150,165,166); gold=(224,177,89); glass=(83,171,186)
    r((6,10,15,180),(2,27,29,4)); tone=sum(map(ord,kind)); accent=(100+tone%45,77+tone%30,63+tone%35)
    if kind in ('housing_block','skyscraper','financial_center'):
        for x,h in ((4,20 if kind=='housing_block' else 25),(15,26 if kind!='housing_block' else 17)):
            r(ink,(x,30-h,12,h)); r(steel,(x+1,31-h,9,h-2)); r(light,(x+1,31-h,2,h-2))
            for y in range(33-h,27,4):
                for wx in (x+4,x+7): r(gold if (y+wx)%3 else glass,(wx,y,2,2))
        r(color,(7,27,15,2)); r(ink,(20,0,1,6))
    elif kind=='industrial_farm':
        for y in range(13,30,4):
            pg.draw.line(s,(82,65,38),(2,y),(29,y),2)
            for x in range(3,29,4): r((132,147,65),(x,y-2,2,2))
        r(ink,(4,6,13,12)); r((110,80,56),(5,8,11,9)); pg.draw.polygon(s,(138,78,60),[(2,9),(10,2),(19,9)]); r(color,(20,11,7,4))
    elif kind in ('radiation_test_range','radiation_station'):
        pg.draw.ellipse(s,(46,57,44),(1,12,30,18)); pg.draw.ellipse(s,(103,126,66),(3,14,26,14),2)
        if kind=='radiation_station':
            r(ink,(10,7,15,19)); r(steel,(11,8,13,17)); pg.draw.ellipse(s,light,(10,3,15,9)); r(glass,(14,12,7,5))
        else: pg.draw.ellipse(s,(20,26,24),(7,18,18,8))
        pg.draw.circle(s,(214,198,77),(8,14),4); pg.draw.circle(s,ink,(8,14),1)
        for points in ([(8,13),(5,10),(8,9)],[(9,14),(13,12),(12,16)],[(7,15),(7,19),(4,17)]): pg.draw.polygon(s,ink,points)
        r(color,(24,23,6,3))
    elif kind in ('concrete_wall','bunker','fortress','anti_tank_line','shelter'):
        for x in range(2,30,7): r(ink,(x,15,7,14)); r(steel,(x+1,14,5,14)); r(light,(x+1,13,5,3))
        if kind in ('bunker','fortress','shelter'):
            pg.draw.ellipse(s,ink,(6,5,22,20)); pg.draw.ellipse(s,steel,(7,6,20,17)); r(ink,(12,15,12,5)); r(color,(15,24,6,3))
            if kind=='fortress': r(light,(18,10,12,3))
        if kind=='anti_tank_line':
            for x in (6,16,26): pg.draw.line(s,light,(x-4,11),(x+4,22),2); pg.draw.line(s,light,(x+4,11),(x-4,22),2)
    elif kind in ('air_defense_site','missile_defense_site','radar','missile_silo'):
        r(ink,(4,23,25,7)); r(steel,(6,24,21,4)); r(color,(9,26,14,2))
        if kind=='radar':
            r(light,(15,9,2,16)); pg.draw.arc(s,glass,(4,1,22,17),3.2,6.1,3); pg.draw.line(s,light,(15,13),(24,3),1)
        elif kind=='missile_silo':
            pg.draw.ellipse(s,ink,(5,15,23,12)); pg.draw.ellipse(s,light,(6,16,21,9),2); r(steel,(14,7,5,17)); pg.draw.polygon(s,gold,[(14,7),(16,1),(19,7)])
        else:
            for x in (10,19): pg.draw.line(s,light,(x,23),(x+7,6),4); pg.draw.line(s,color,(x+5,10),(x+7,6),3)
    elif kind in ('engineering_institute','physics_lab','computing_center','university','hospital'):
        r(ink,(3,14,26,15)); r(steel,(5,15,22,12)); r(light,(6,17,2,9)); r(color,(8,25,17,2))
        if kind in ('physics_lab','university'): pg.draw.ellipse(s,ink,(7,3,19,16)); pg.draw.ellipse(s,glass,(9,5,15,12)); r(steel,(9,13,15,4))
        elif kind=='hospital': r((217,108,96),(15,7,3,9)); r((217,108,96),(12,10,9,3))
        else:
            for x in (8,14,20): r(ink,(x,8,5,15)); r(glass,(x+1,10,2,9))
        for x in (10,18): r(gold,(x,19,3,3))
    elif kind in ('oil_well','gas_well'):
        pg.draw.polygon(s,ink,[(6,29),(13,2),(20,2),(27,29)]); pg.draw.lines(s,light,False,[(8,28),(14,4),(19,4),(25,28)],2)
        for y in (10,17,24): pg.draw.line(s,steel,(11,y),(22,y),2)
        r(color,(12,26,11,3)); pg.draw.circle(s,gold,(19,6),2)
    elif kind=='solar_power':
        for x,y in ((2,10),(15,10),(2,21),(15,21)):
            r(ink,(x,y,13,10)); r((50,88,125),(x+1,y+1,11,7)); pg.draw.line(s,glass,(x+6,y+1),(x+6,y+7),1)
    else:
        r(ink,(2,15,28,14)); r(accent,(4,17,24,10)); pg.draw.polygon(s,steel,[(2,17),(8,10),(15,16),(21,10),(30,17)])
        for x in (7,16,24): r(gold,(x,20,3,4))
        for i in range(1+tone%3):
            x=5+i*8; h=10+(tone+i*3)%8; r(ink,(x,4,5,h+10)); r(steel,(x+1,5,3,h+8)); r(light,(x+1,4,4,2))
        if 'power' in kind: pg.draw.line(s,gold,(22,10),(18,17),2); pg.draw.line(s,gold,(18,17),(24,17),2)
        if 'weapons' in kind or 'missile_factory' in kind:
            tier=int(kind[-1]); r(ink,(18,3,12,8))
            for n in range(tier): r(color,(20+n*3,5,1,4))
        r(color,(4,27,24,2))
    return s


def unit_sprite(kind,color):
    s=pg.Surface((32,32),pg.SRCALPHA); r=lambda c,b:pg.draw.rect(s,c,b); ink=(14,19,25); steel=(123,135,136)
    if kind=='drone_swarm':
        for x,y in ((8,9),(22,10),(16,23)):
            pg.draw.line(s,steel,(x-5,y-4),(x+5,y+4),2); pg.draw.line(s,steel,(x-5,y+4),(x+5,y-4),2); r(color,(x-2,y-2,5,5))
            for a,b in ((-5,-4),(5,4),(-5,4),(5,-4)): pg.draw.circle(s,ink,(x+a,y+b),3,1)
    else:
        r(ink,(3,17,26,12)); r((70,75,76),(4,18,24,9)); r(color,(6,17,20,7))
        for x in range(6,28,5): pg.draw.circle(s,steel,(x,27),2)
        r(ink,(10,11,14,9)); r(steel,(12,12,10,6))
        if kind in ('rocket_corps','mobile_air_defense'):
            for x in (12,17,22): pg.draw.line(s,steel,(x,15),(x+4,4),3)
        elif kind in ('tank_corps','artillery'): pg.draw.line(s,steel,(19,12),(30,7),3)
        else: r(ink,(15,8,2,7)); r(color,(16,8,8,4))
    return s
