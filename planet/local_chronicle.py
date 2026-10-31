"""Deterministic global events: no model, no privileged country selection."""
import random

def chapter_event(world):
    event=random.Random(f'{world.seed}:{world.day}:chapter-682').choice(('peace','harvest','drought','fair','epidemic','earthquake'))
    labels=dict(peace='Без мировых потрясений',harvest='Урожайный период',drought='Засушливый период',fair='Торговые ярмарки',epidemic='Волна болезни',earthquake='Землетрясения')
    active=[s for s in world.states if not s.eliminated]
    public='; '.join(f'{s.name}: {len(world.positions(s.id))} клеток, {sum(world.cell(p).population for p in world.positions(s.id))} жителей' for s in active)
    land=[c for c in world.cells if c.terrain!='water']
    expand=getattr(world,'map_mode','normal')=='normal' and world.size<512 and bool(land) and sum(c.owner is None for c in land)<len(land)*.05
    return dict(event=event,target=None,title=f'{labels[event]} · день {world.day}',description='Событие действует по одинаковым правилам для всех действующих государств. '+public,expand=expand)
