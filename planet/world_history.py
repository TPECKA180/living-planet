"""Observer's factual, local poetic history; never an extra model request."""
import random


def write_history(world):
    if world.day <= 0 or world.day % 10:
        return None
    book = world.history_book
    if any(p['day'] == world.day for p in book):
        return None
    start = world.day - 9
    rng = random.Random(f'{world.seed}:{world.day}:history750')
    moves = [m for m in world.movement_log if start <= m.get('day', -1) <= world.day]
    captures = [m for m in moves if m.get('captured') and m.get('previous_owner') not in (None, m.get('owner'))]
    receipts = [r for r in world.settlements if start <= r.get('day', -1) <= world.day]
    builds = research = 0
    for record in world.learning.values():
        for episode in record.get('episodes', []):
            if not start <= episode.get('day', -1) <= world.day:
                continue
            for action in episode.get('actions', []):
                if action.get('success'):
                    builds += action.get('type') == 'build'
                    research += action.get('type') == 'research'
    wars = [' — '.join(world.state(sid).name for sid in pair) for pair in world.wars]
    leaders = sorted(((len(world.positions(s.id)), sum(c.population for c in world.cells if c.owner == s.id), s.name) for s in world.states), reverse=True)
    title = rng.choice(['Чернила и железо', 'Под медным небом', 'Там, где меняются границы', 'Пепел обещаний, свет мастерских', 'Реки времени'])
    text = [rng.choice(['Время шло по земле, как ветер по потемневшему серебру. За именами держав стояли хлеб, страх и надежда.', 'Десять дней легли между страницами мира. Одни обещания стали делами, другие остались эхом в залах совета.', 'Над картой медленно гасли звёзды. Ни одно знамя не могло остановить течение дней.']),
            f'На дорогах отмечено перемещений: {len(moves)}. Подтверждённых захватов чужих клеток: {len(captures)}. Так железо оставляло свои следы на карте.' if moves else 'Дороги молчали: за эти дни журнал не сохранил перемещений. Летописец не станет сочинять побед, которых не было.',
            f'В торговых книгах появились квитанции: {len(receipts)}. Каждая запись — исполненный расчёт, а не одно лишь обещание.' if receipts else 'Новых торговых квитанций нет. Слова могли летать между столицами, но книга расчётов хранит молчание.',
            f'В сохранённых отчётах об исполнении — построек: {builds}, исследований: {research}. У труда свой негромкий язык.',
            'К концу десятилетия дней продолжаются войны: '+ '; '.join(wars)+'. Мир слышит их тяжёлое дыхание.' if wars else 'К концу этого десятка дней действующих войн нет. Это лишь строка сегодняшней карты, а не обещание вечного мира.',
            'На последнем листе периода владения держав таковы: '+ '; '.join(f'{name} — {land} клеток, {pop} жителей' for land, pop, name in leaders)+'.',
            rng.choice(['И всё же за краем этой страницы уже светился следующий рассвет. История ещё не выбрала последнего имени.', 'Печати остывали на воске, а земля оставалась тёплой. Завтра у неё снова спросят цену величия.', 'Летописец отложил перо. Реки продолжали течь сквозь границы, которые люди считали вечными.'])]
    page = dict(day=world.day, from_day=start, title=f'Лист {len(book)+1}. {title}', text='\n\n'.join(text), facts=dict(movements=len(moves), enemy_cells_captured=len(captures), receipts=len(receipts), builds=builds, research=research, active_wars=len(wars)), method='local_poetic_factual', observer_only=True)
    book.append(page)
    return page
