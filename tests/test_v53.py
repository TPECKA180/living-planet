import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from planet.engine import World,Store,RuleError
from planet.brain import Brain,AutomaticRetry
from planet.brain_errors import IsolationError
from planet.isolation import checked_context
from planet.decision_format import decision_schema
from planet.deliberation import validate_assessment
try:
    from .test_v52 import decision,conclusion
except ImportError:
    from test_v52 import decision,conclusion


def action(name,**args): return dict(type=name,args=args)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=3); self.s,self.other,self.third=self.w.states; self.u=self.w.units[0]
        for cell in self.w.cells: cell.terrain='grass'
        for state in self.w.states:
            state.operations.update(explore=False,recruit=False); state.stocks.update(money=10000,resource=10000,food=10000,metal=1000,matter=1000)
    def tower(self,level=1):
        p=list(self.u['cell']); cell=self.w.cell(p); cell.building='tower'; cell.building_level=level; return p
    def train(self,level=1):
        self.tower(level); self.w.start_day(); self.w.finish_tower_day(); self.w.in_day=False; self.w.start_day()


class TowerTests(Fixture):
    def test_full_day_gives_bonus_for_exactly_next_three_days(self):
        self.tower(); self.w.start_day(); self.assertEqual(self.w.effective_strength(self.u),5)
        self.w.finish_tower_day(); self.assertEqual(self.u['tower_buff']['starts_day'],2); self.assertEqual(self.u['tower_buff']['expires_day'],4)
        for day in (2,3,4): self.w.day=day; self.assertEqual(self.w.effective_strength(self.u),6.25)
        self.w.day=5; self.assertEqual(self.w.effective_strength(self.u),5)
    def test_departure_and_return_does_not_count_as_full_stay(self):
        source=self.tower(); self.w.start_day(); target=self.w.adjacent(source)[0]
        self.w.units=[self.u]; self.w.step_unit(self.u,target); self.w.step_unit(self.u,source); self.w.finish_tower_day()
        self.assertIsNone(self.u.get('tower_buff'))
    def test_new_tower_does_not_train_retroactively(self):
        p=self.u['cell']; self.w.cell(p).building=None; self.w.start_day()
        self.w.execute(self.s,action('build',cell=p,building='tower',level=1)); self.w.finish_tower_day(); self.assertIsNone(self.u.get('tower_buff'))
    def test_higher_level_and_nonstacking_and_lower_tower_cannot_extend_stronger_buff(self):
        self.train(3); self.assertEqual(self.w.effective_strength(self.u),8.75)
        self.w.finish_tower_day(); self.w.finish_tower_day(); self.assertEqual(self.u['tower_buff']['percent'],75)
        expiry=self.u['tower_buff']['expires_day']; self.w.cell(self.u['cell']).building_level=1
        self.w.in_day=False; self.w.start_day(); self.w.finish_tower_day(); self.assertEqual(self.u['tower_buff']['expires_day'],expiry)
    def test_bonus_changes_combat_not_permanent_base_health(self):
        self.train(); target=self.w.adjacent(self.u['cell'])[0]; self.w.cell(target).owner=self.other.id
        self.w.units=[self.u]; self.w.spawn(self.other.id,target,'army',5)
        self.w.step_unit(self.u,target)
        self.assertIn(self.u,self.w.units); self.assertEqual(self.u['strength'],1); self.assertEqual(self.w.effective_strength(self.u),1.25)
        self.w.day=5; self.assertEqual(self.w.effective_strength(self.u),1)
    def test_buff_survives_save_and_resets_only_after_expiry(self):
        self.train(2)
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'world.sqlite3'); store.save(self.w); loaded=store.load()
            unit=next(u for u in loaded.units if u['id']==self.u['id']); self.assertEqual(loaded.effective_strength(unit),7.5)
            loaded.day=6; self.assertEqual(loaded.effective_strength(unit),5)
    def test_fractional_wounds_can_be_reinforced_without_exceeding_original_strength(self):
        self.s.tech=['military_medicine']; self.u['strength']=4.75
        self.w.execute(self.s,action('reinforce',unit_id=self.u['id'],amount=.25)); self.assertEqual(self.u['strength'],5)
        with self.assertRaises(RuleError): self.w.execute(self.s,action('reinforce',unit_id=self.u['id'],amount=.25))


class WallTests(Fixture):
    def wall(self,level=1,defender=False):
        self.w.units=[self.u]; target=self.w.adjacent(self.u['cell'])[0]; cell=self.w.cell(target)
        cell.owner=self.other.id; cell.building='wall'; cell.building_level=level; cell.wall_hp=20*level
        if defender: self.w.spawn(self.other.id,target,'army',3)
        return target,cell
    def test_scout_cannot_cross_wall_or_pay_for_attempt(self):
        target,wall=self.wall(); money=self.s.stocks['money']; self.assertIsNone(self.w.find_route(self.u,target))
        self.assertIsNotNone(self.w.step_unit(self.u,target)); self.assertEqual(self.s.stocks['money'],money); self.assertEqual(wall.wall_hp,20)
    def test_army_siege_persists_across_days_and_captures_only_after_breach(self):
        target,wall=self.wall(); self.u['type']='army'; source=list(self.u['cell']); money=self.s.stocks['money']
        self.w.start_day(); self.w.execute(self.s,action('move',unit_id=self.u['id'],target_cell=target))
        self.assertEqual(wall.wall_hp,10); self.assertEqual(self.u['cell'],source)
        after=self.s.stocks['money']; self.assertGreaterEqual(after,money) # Today's normal income also arrived.
        self.w.in_day=False; self.w.start_day(); self.w.run_operations()
        self.assertIsNone(wall.building); self.assertEqual(self.u['cell'],target); self.assertEqual(wall.owner,self.s.id)
        siege=[m for m in self.w.movement_log if m.get('kind')=='siege']; self.assertEqual(len(siege),4); self.assertEqual(sum(m['cost'] for m in siege),88)
    def test_garrison_counterattack_and_surviving_wall_block_entry(self):
        target,wall=self.wall(defender=True); self.u['type']='army'; source=list(self.u['cell'])
        self.w.step_unit(self.u,target); self.assertEqual(self.u['strength'],2); self.assertEqual(self.u['cell'],source); self.assertEqual(wall.wall_hp,15)
    def test_wall_repair_and_upgrade_preserve_damage_without_free_full_heal(self):
        target,wall=self.wall(); wall.owner=self.s.id; wall.wall_hp=7
        before=self.s.stocks.copy(); self.w.execute(self.s,action('repair_wall',cell=target,amount=5))
        self.assertEqual(wall.wall_hp,12); self.assertEqual(before['money']-self.s.stocks['money'],5); self.assertEqual(before['resource']-self.s.stocks['resource'],1.25)
        self.s.tech=['aether_forging']; self.w.execute(self.s,action('improve_building',cell=target)); self.assertEqual(wall.wall_hp,32); self.assertEqual(wall.building_level,2)
    def test_new_military_buildings_do_not_produce_fake_matter_or_money(self):
        p=self.u['cell']; cell=self.w.cell(p); baseline=self.w.production_for_cell(self.s,cell)
        for kind in ('tower','wall'):
            cell.building=kind; cell.building_level=3
            current=self.w.production_for_cell(self.s,cell)
            self.assertEqual(current['matter'],0); self.assertEqual(current['money'],4+cell.population)


class ConstructionTests(Fixture):
    def test_rich_country_gets_affordable_arsenal_and_exact_legal_sites(self):
        self.s.tech=['lab','scholarship']; self.w.cell(self.u['cell']).building='lab'
        c=self.w.construction_context(self.s); arsenal=next(p for p in c['critical_projects'] if p['building']=='arsenal')
        self.assertTrue(arsenal['affordable_with_reserve']); self.assertFalse(self.w.cell(arsenal['cell']).building)
        before=self.w.data(); self.w.construction_context(self.s); self.assertEqual(before,self.w.data())
        self.w.execute(self.s,action('build',cell=arsenal['cell'],building='arsenal',level=arsenal['level']))
        self.assertGreater(self.w.economic_forecast(self.s)['resources']['matter']['production'],0)
    def test_productive_building_changes_economic_power_score(self):
        before=next(r for r in self.w.strategic_context(self.s)['ranking'] if r['state']==self.s.id)['score']
        p=next(p for p in self.w.positions(self.s.id) if self.w.cell(p).population and not self.w.cell(p).building)
        self.w.execute(self.s,action('build',cell=p,building='arsenal',level=3))
        after=next(r for r in self.w.strategic_context(self.s)['ranking'] if r['state']==self.s.id)['score']; self.assertGreater(after,before)
    def test_construction_reserve_disallows_spending_food_crisis_reserve(self):
        self.s.stocks['money']=200; self.s.operations['reserve_money']=200
        self.assertFalse(any(p['affordable_with_reserve'] for p in self.w.construction_context(self.s)['projects']))


class MockServer:
    def __init__(self): self.instances=[]; self.counter=0; self.calls=[]; self.fail_unload=False
    def request(self,path,payload=None):
        self.calls.append((path,copy.deepcopy(payload)))
        if path=='/api/v1/models': return dict(models=[dict(key='model',type='llm',max_context_length=131072,loaded_instances=copy.deepcopy(self.instances))])
        if path.endswith('/unload'):
            if self.fail_unload: raise RuntimeError('unload failed')
            self.instances=[i for i in self.instances if i['id']!=payload['instance_id']]; return dict(instance_id=payload['instance_id'])
        if path.endswith('/load'):
            self.counter+=1; name=f'instance_{self.counter}'; self.instances.append(dict(id=name,config=dict(context_length=payload['context_length'])))
            return dict(instance_id=name,load_config=dict(context_length=payload['context_length']))
        raise AssertionError(path)


class PrivacyTests(Fixture):
    def brain(self):
        brain=Brain(dict(model='model',strict_state_isolation=True,context_window=98304)); server=MockServer(); brain.request=server.request; return brain,server
    def test_a_b_a_requires_three_fresh_instances_with_verified_unloads(self):
        brain,server=self.brain(); ids=[]
        for actor in (self.s.id,self.other.id,self.s.id): brain.bind_actor(actor); ids.append(brain.prepare_model('model')[0])
        self.assertEqual(len(set(ids)),3); self.assertEqual(sum(p.endswith('/unload') for p,_ in server.calls),2)
    def test_same_actor_supplement_reuses_only_its_own_clean_instance(self):
        brain,server=self.brain(); brain.bind_actor(self.s.id); first=brain.prepare_model('model')[0]; second=brain.prepare_model('model')[0]
        self.assertEqual(first,second); self.assertEqual(server.counter,1)
    def test_failed_unload_never_sends_chat_to_next_actor(self):
        brain,server=self.brain(); brain.bind_actor(self.s.id); brain.prepare_model('model'); server.fail_unload=True; brain.bind_actor(self.other.id)
        with patch.object(brain,'stream_request') as send:
            with self.assertRaises(IsolationError): brain.complete('JSON',dict(notes='B only'),'model')
        send.assert_not_called()
    def test_foreign_archive_owner_and_wrong_identity_are_rejected_before_network(self):
        brain,_=self.brain(); context=self.w.context(self.s); context['memory']=[dict(owner=self.other.id,notes='SECRET_OTHER')]
        with patch.object(brain,'complete') as send:
            with self.assertRaises(IsolationError): brain.think(self.s,context)
        send.assert_not_called()
        context=self.w.context(self.s); context['identity']['id']=self.other.id
        with self.assertRaises(IsolationError): checked_context(self.s,context)
    def test_foreign_notes_plans_reviews_and_private_action_reasons_never_enter_request(self):
        for key in ('notes','plan','thinking'): setattr(self.other,key,'PRIVATE_OTHER_'+key)
        self.other.memory=[dict(day=0,notes='PRIVATE_OTHER_MEMORY',plan='PRIVATE_OTHER_PLAN')]
        self.other.strategic_assessment=conclusion(self.other,self.s); self.other.strategic_assessment['rival_plan']['private_intent']='PRIVATE_OTHER_SCHEME'
        self.w.log('action',self.other.name+': trade PRIVATE_OTHER_REASON') # Legacy untagged action event.
        context=self.w.context(self.s); text=json.dumps(checked_context(self.s,context),ensure_ascii=False)
        self.assertNotIn('PRIVATE_OTHER_',text)
    def test_trade_risk_reason_is_private_to_its_author(self):
        offer=dict(id=1,seller=self.s.id,partner=self.other.id,resource='food',amount=1,price=1,status='open',day=0,expires=5,seller_reason='PRIVATE_SELLER_CALCULATION')
        self.w.trade_offers=[offer]
        self.assertNotIn('seller_reason',self.w.context(self.other)['trade_offers'][0]); self.assertIn('seller_reason',self.w.context(self.s)['trade_offers'][0])
    def test_own_context_and_diplomacy_remain_available(self):
        self.s.notes='OWN_MEMORY_MARKER'; self.w.send_message(self.other,self.s.id,'Разрешённое дипломатическое письмо')
        context=checked_context(self.s,self.w.context(self.s)); self.assertEqual(context['notes'],'OWN_MEMORY_MARKER'); self.assertEqual(len(context['messages']),1)
    def test_public_states_cannot_carry_private_fields_and_third_party_mail_is_blocked(self):
        context=self.w.context(self.s); context['states'][1]['notes']='PRIVATE_OTHER'; self.assertRaises(IsolationError,checked_context,self.s,context)
        context=self.w.context(self.s); context['messages']=[dict(sender=self.other.id,recipient=self.third.id,text='PRIVATE_MAIL')]
        self.assertRaises(IsolationError,checked_context,self.s,context)
    def test_primary_schema_keeps_all_deep_fields_and_building_review(self):
        schema=decision_schema(self.s,self.w.context(self.s),['build','hold'],True)['json_schema']['schema']
        self.assertIn('construction_review',schema['required']); self.assertIn('strategic_assessment',schema['required'])
        self.assertEqual(schema['properties']['strategic_assessment']['properties']['alternatives']['minItems'],3)
    def test_compact_world_export_roundtrips_every_field(self):
        before=self.w.data()
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'world.sqlite3',export=True); store.save(self.w)
            exported=json.loads((Path(temp)/'world.json').read_text(encoding='utf-8')); self.assertEqual(exported,before); self.assertEqual(store.load().data(),before)


class ConstructionChoiceTests(Fixture):
    def chosen(self):
        context=self.w.context(self.s); project=next(p for p in context['construction']['projects'] if p['building']=='arsenal')
        result=decision(self.s,self.other); result.update(owner=self.s.id,origin_patch='5.3',actions=[],construction_review=dict(choice='build',project_id=project['project_id'],reason='Нужен собственный источник материи для дальнейшего развития.',revisit_day=self.w.day+1))
        return context,project,result
    def test_selected_project_is_real_paid_build_and_idempotent(self):
        context,project,result=self.chosen(); brain=Brain({}); compiled=brain.compile_construction(context,result)
        self.assertEqual(compiled,brain.compile_construction(context,compiled)); self.assertEqual(result['actions'],[])
        before=self.s.stocks['money']; self.w.apply_decision(self.s,compiled)
        self.assertEqual(self.w.cell(project['cell']).building,'arsenal'); self.assertEqual(before-self.s.stocks['money'],project['cost']['money'])
    def test_defer_never_builds_automatically(self):
        context,_,result=self.chosen(); result['construction_review'].update(choice='defer',project_id=None)
        self.assertEqual(Brain({}).compile_construction(context,result)['actions'],[])
    def test_cross_state_project_and_promise_without_action_are_rejected(self):
        context,_,result=self.chosen(); result['construction_review']['project_id']='state_999/arsenal/0:0/L1'
        self.assertRaises(ValueError,Brain({}).compile_construction,context,result)
        result['construction_review']['project_id']=None; self.assertRaises(ValueError,Brain({}).compile_construction,context,result)
    def test_full_action_list_never_silently_drops_existing_orders(self):
        context,_,result=self.chosen(); result['actions']=[action('do_nothing') for _ in range(12)]
        self.assertRaises(ValueError,Brain({}).compile_construction,context,result); self.assertEqual(len(result['actions']),12)
    def test_focused_repair_preserves_core_and_legacy_pending(self):
        context,project,result=self.chosen(); result['construction_review']['project_id']=None; original=copy.deepcopy(result)
        brain=Brain({}); reply=dict(construction_review=dict(original['construction_review'],project_id=project['project_id']))
        with patch.object(brain,'complete',return_value=reply) as call:
            repaired=brain.review_construction(self.s,context,result)
        self.assertEqual(call.call_count,1); self.assertEqual(repaired['notes'],original['notes']); self.assertEqual(repaired['diplomacy'],original['diplomacy'])
        self.assertEqual(result,original); result.pop('origin_patch'); self.assertIs(brain.review_construction(self.s,context,result),result)
    def test_foreign_pending_is_blocked_before_construction_repair(self):
        context,_,result=self.chosen(); result['owner']=self.other.id; brain=Brain({})
        with patch.object(brain,'complete') as send:
            self.assertRaises(IsolationError,brain.review_construction,self.s,context,result)
        send.assert_not_called()
    def test_runner_persists_core_before_retry_and_finishes_same_actor_before_advancing(self):
        from main import Runner
        self.w.start_day(); _,_,result=self.chosen()
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'world.sqlite3'); runner=Runner(self.w,store,dict(external_console=False,deep_strategy=True)); order=[]
            def construction(*args):
                order.append('construction')
                if order.count('construction')==1: raise AutomaticRetry('Уточняем проект')
                return result
            def strategy(*args): order.append('strategy'); return result
            with patch.object(runner.brain,'think',return_value=result) as think,patch.object(runner.brain,'review_construction',side_effect=construction),patch.object(runner.brain,'review_strategy',side_effect=strategy):
                runner.work(); self.assertEqual(self.w.cursor,0); self.assertEqual(store.load().pending_decisions[self.s.id],result)
                runner.work(); self.assertEqual(self.w.cursor,1); self.assertEqual(think.call_count,1)
            self.assertEqual(order,['construction','construction','strategy'])


if __name__=='__main__': unittest.main()
