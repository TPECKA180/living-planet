"""Seeded coastlines and six separated, connected large islands."""
import math,random
from functools import lru_cache

MODES=('normal','archipelago')

@lru_cache(maxsize=131072)
def lattice(x,y,seed):
    n=(x*374761393+y*668265263+seed*1274126177)&0xffffffff
    n=((n^(n>>13))*1274126177)&0xffffffff
    return ((n^(n>>16))&0xffffffff)/4294967295

def noise(x,y,scale,seed):
    x/=scale;y/=scale;ix=math.floor(x);iy=math.floor(y);fx=x-ix;fy=y-iy
    fx=fx*fx*(3-2*fx);fy=fy*fy*(3-2*fy)
    return ((1-fx)*lattice(ix,iy,seed)+fx*lattice(ix+1,iy,seed))*(1-fy)+((1-fx)*lattice(ix,iy+1,seed)+fx*lattice(ix+1,iy+1,seed))*fy

def biome(x,y,seed):
    height=.7*noise(x,y,9,seed+19)+.3*noise(x,y,4,seed+91)
    moisture=noise(x,y,7,seed+73)
    rare=noise(x,y,3,seed+131)
    terrain='mountain' if height>.66 else 'science' if rare>.77 else 'resource' if height>.57 and rare>.52 else 'forest' if moisture>.52 else 'grass'
    return terrain,max(1,min(5,1+int(height*5)))

def clean_islands(cells,size,seed):
    from collections import deque
    keep=set();queue=deque(island_centres(size,seed))
    while queue:
        x,y=queue.popleft()
        if (x,y) in keep or not (0<=x<size and 0<=y<size) or cells[y*size+x].terrain=='water':continue
        keep.add((x,y));queue.extend(((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
    for i,cell in enumerate(cells):
        if (i%size,i//size) not in keep:cell.terrain='water'

@lru_cache(maxsize=128)
def island_centres(size,seed):
    rng=random.Random(seed^0x67A1)
    points=[(int((x+.5+rng.uniform(-.025,.025))*size/3),int((y+.5+rng.uniform(-.025,.025))*size/2)) for y in range(2) for x in range(3)]
    rng.shuffle(points)
    return tuple(points)

@lru_cache(maxsize=128)
def phases(seed):
    rng=random.Random(seed^0x67A1)
    return tuple(rng.uniform(-math.pi,math.pi) for _ in range(3))

def is_water(x,y,size,seed,mode):
    if mode=='archipelago':
        if x in (size//3,2*size//3) or y==size//2:return True
        for index,(cx,cy) in enumerate(island_centres(size,seed)):
            dx=(x-cx)/(size/3*.35);dy=(y-cy)/(size/2*.35)
            angle=math.atan2(dy,dx);phase=(seed%1000000)*.137+index
            radius=1+.17*math.sin(3*angle+phase)+.07*math.sin(5*angle+index)+.025*math.sin(9*angle-phase)
            if dx*dx+dy*dy<=radius*radius:return False
        return True
    px,py,pz=phases(seed)
    warp=(noise(x,y,20,seed+337)-.5)*1.2
    return math.sin(x*.10+px+warp)+math.cos(y*.085+py-warp*.6)+math.sin((x+y)*.045+pz)+.35*(noise(x,y,5,seed+467)-.5)<-1.2
