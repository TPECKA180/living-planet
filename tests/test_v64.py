import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from planet.engine import World,Store,PRICES
from planet.brain import Brain,AutomaticRetry
from planet.execution_ai import compile_orders,preview_orders,missing_today_build
from planet.intelligence import CONTRACTS,validate_actions
from main import Runner

def action(kind,**args): return json.loads(json.dumps(dict(type=kind,args=args)))

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=2); self.s,self.peer=self.w.states
        self.s.stocks.update(money=20000,resource=10000,science=10000,food=10000,metal=10000,matter=10000)
        self.ctx=self.w.context(self.s)
        self.p=next(p for p in self.w.positions(self.s.id) if not self.w.cell(p).building and self.w.cell(p).terrain!='water')
        self.brain=Brain(dict(decision_repair_attempts=1))
    def decision(self,actions=None):
        return dict(owner=self.s.id,origin_patch='6.3',thinking='Развиваем страну.',notes=self.s.notes,plan=self.s.plan,
                    diplomacy=[dict(to=self.peer.id,text='Обсудим условия.')],actions=actions or [])
    def project(self): return next(p for p in self.ctx['construction']['projects'] if p['building']=='castle' and p['level']==1)
    def review(self,p): return dict(choice='build',project_id=p['project_id'],reason='Выбран конкретный денежный проект для реального исполнения.',revisit_day=self.w.day)
    def test_selected_build_recovered_even_after_later_review_dropped_action(self):
        p=self.project(); d=self.decision();d['construction_review']=self.review(p)
        fixed=self.brain.prepare_execution(self.w,self.s,d)
        self.assertEqual(len(fixed['actions']),1); self.assertEqual(fixed['execution_preflight']['failed'],0)
        before=self.s.stocks['money'];self.w.apply_decision(self.s,fixed)
        self.assertEqual(self.w.cell(p['cell']).building,'castle');self.assertEqual(before-self.s.stocks['money'],200)
    def test_duplicate_build_alias_and_project_id_pay_only_once(self):
        p=self.project(); d=self.decision([action('build',project_id=p['project_id']),action('build',cell=p['cell'],type='castle',level=1)])
        d['construction_review']=self.review(p)
        fixed=compile_orders(self.ctx,d); self.assertEqual(len(fixed['actions']),1)
        self.assertEqual(fixed,compile_orders(self.ctx,fixed));self.w.apply_decision(self.s,fixed)
        self.assertEqual(self.s.decision_outcome['accepted'],1);self.assertFalse(self.s.decision_outcome['rejected'])
    def test_two_different_buildings_same_cell_are_not_silently_removed(self):
        d=self.decision([action('build',cell=self.p,building='castle',level=1),action('build',cell=self.p,building='tower',level=1)])
        fixed=compile_orders(self.ctx,d);self.assertEqual(len(fixed['actions']),2)
        self.assertEqual(preview_orders(self.w,self.s.id,fixed)['failed'],1)
    def test_preview_does_not_change_money_characters_map_or_receipts(self):
        d=self.decision([action('build',cell=self.p,building='castle',level=1),action('transfer',partner=self.peer.id,resource='money',amount=100)])
        before=self.w.data();report=preview_orders(self.w,self.s.id,d)
        self.assertEqual(report['failed'],0);self.assertEqual(before,self.w.data())
    def test_combined_budget_not_individual_affordability(self):
        self.s.stocks['money']=250
        q=next(q for q in self.w.positions(self.s.id) if q!=self.p and self.w.cell(q).terrain!='water' and not self.w.cell(q).building)
        d=self.decision([action('build',cell=self.p,building='castle',level=1),action('build',cell=q,building='tower',level=1)])
        report=preview_orders(self.w,self.s.id,d)
        self.assertEqual(report['failed'],1);self.assertEqual(report['stocks_after']['money'],50)
    def test_repair_changes_only_orders_not_character_letters_or_strategy(self):
        d=self.decision([action('build',cell=self.p,building='castle',level=10)])
        self.s.stocks['money']=100
        d['strategic_assessment']={'objective':'Сохранить нашу исходную стратегию'}
        update=dict(actions=[],construction_review=dict(choice='defer',project_id=None,reason='Недостаточно денег; собираем бюджет до следующего дня.',revisit_day=self.w.day+1),economic_review=dict(mode='none',reason='Реальных переводов не планируется, сохраняем казну.',orders=[]))
        with patch.object(self.brain,'complete',return_value=update) as complete:
            fixed=self.brain.prepare_execution(self.w,self.s,d)
        self.assertEqual(complete.call_count,1)
        for key in ('notes','plan','thinking','diplomacy','strategic_assessment'): self.assertEqual(fixed[key],d[key])
        self.assertEqual(fixed['actions'],[]);self.assertEqual(self.s.stocks['money'],100)
    def test_valid_decision_requires_no_additional_model_request(self):
        d=self.decision([action('build',cell=self.p,building='castle',level=1)])
        with patch.object(self.brain,'complete',side_effect=AssertionError('No extra model call')):
            self.assertEqual(self.brain.prepare_execution(self.w,self.s,d)['execution_preflight']['failed'],0)
    def test_invalid_repair_retries_without_applying_original_orders(self):
        d=self.decision([action('research',tech='not_a_technology',cell=self.p)]);before=self.w.data()
        with patch.object(self.brain,'complete',return_value={'actions':d['actions']}):
            with self.assertRaises(AutomaticRetry):self.brain.prepare_execution(self.w,self.s,d)
        self.assertEqual(before,self.w.data())
    def test_intent_only_is_clarified_never_automatically_purchased(self):
        d=self.decision();d['thinking']='Сегодня построю замок.'
        self.assertTrue(missing_today_build(d));before=self.w.data()
        update=dict(actions=[],construction_review=dict(choice='defer',project_id=None,reason='Стройку сегодня отменяем: необходим резерв перед угрозой.',revisit_day=self.w.day+1),economic_review=dict(mode='none',reason='Сохраняем средства для критического резерва страны.',orders=[]))
        with patch.object(self.brain,'complete',return_value=update):fixed=self.brain.prepare_execution(self.w,self.s,d)
        self.assertEqual(fixed['actions'],[]);self.assertIn('execution_intent_correction',fixed);self.assertEqual(before,self.w.data())
    def test_explicit_treasury_orders_recovered_without_duplicate_transfer(self):
        order=action('transfer',partner=self.peer.id,resource='money',amount=100)
        d=self.decision();d['economic_review']=dict(mode='execute',reason='Перевод выбран явно, исполняем обязательство страны.',orders=[order])
        fixed=compile_orders(self.ctx,d);self.assertEqual(fixed,compile_orders(self.ctx,fixed))
        before=self.peer.stocks['money'];self.w.apply_decision(self.s,fixed)
        self.assertEqual(self.peer.stocks['money']-before,100)
    def test_deceptive_letter_does_not_create_payment(self):
        d=self.decision();d['diplomacy'][0]['text']='Отправляю вам сто денег.'
        d['economic_review']=dict(mode='deceive',reason='Сознательно обещаем перевод без исполнения ради блефа.',orders=[])
        fixed=self.brain.prepare_execution(self.w,self.s,d);self.assertEqual(fixed['actions'],[])
        before=self.peer.stocks['money'];self.w.apply_decision(self.s,fixed)
        self.assertEqual(before,self.peer.stocks['money']);self.assertTrue(self.s.decision_outcome['message_results'][0]['success'])
    def test_policy_works_without_meaningless_cell(self):
        a=action('policy',explore=False,recruit=False)
        validate_actions(self.decision([a]),self.ctx);self.w.execute(self.s,a)
        self.assertFalse(self.s.operations['explore']);self.assertFalse(self.s.operations['recruit'])
    def adjacent_peer(self):
        q=next(q for q in self.w.adjacent(self.p) if self.w.cell(q).terrain!='water')
        self.w.cell(q).owner=self.peer.id;self.w.cell(self.p).population=1;self.w.cell(q).population=0
        return q
    def test_alliance_without_cell(self):
        self.adjacent_peer();self.w.execute(self.s,action('alliance',partner=self.peer.id))
        self.assertIn(self.peer.id,self.s.allies)
    def test_migration_without_cell(self):
        self.adjacent_peer();before=sum(self.w.cell(p).population for p in self.w.positions(self.peer.id))
        self.w.execute(self.s,action('migrate',partner=self.peer.id,amount=1))
        self.assertEqual(sum(self.w.cell(p).population for p in self.w.positions(self.peer.id)),before+1)
    def test_destroyed_science_building_cannot_research(self):
        p=next(p for p in self.w.positions(self.s.id) if self.w.cell(p).terrain=='science')
        self.w.cell(p).building='lab';self.w.cell(p).integrity=0
        d=self.decision([action('research',tech='agriculture',cell=p)])
        self.assertEqual(preview_orders(self.w,self.s.id,d)['failed'],1);self.assertNotIn('agriculture',self.s.tech)
    def test_legacy_building_on_radiation_is_rejected_without_payment(self):
        self.w.cell(self.p).radiation=20;before=self.s.stocks['money']
        d=self.decision([action('build',cell=self.p,building='castle',level=1)])
        self.assertEqual(preview_orders(self.w,self.s.id,d)['failed'],1);self.assertEqual(before,self.s.stocks['money'])
    def test_borrow_then_repay_and_roundtrip_real_debt(self):
        self.s.tech.extend(['industrialization','fiscal_stability']);self.s.era=2
        before=self.s.stocks['money'];self.w.execute(self.s,action('borrow',amount=500))
        self.assertEqual(self.s.stocks['money'],before+500);self.assertEqual(self.s.modern['debt'],500)
        restored=World.restore(json.loads(json.dumps(self.w.data())));s=restored.state(self.s.id)
        restored.execute(s,action('repay',amount=500))
        self.assertEqual(s.modern['debt'],0);self.assertEqual(s.stocks['money'],before)
    def test_cancel_exchange_changes_offer_status_and_does_not_transfer(self):
        before=self.s.stocks.copy()
        self.w.execute(self.s,action('offer_exchange',partner=self.peer.id,give={'metal':1},receive={'money':2},mode='secure',allow_risk=True,reason='Осознанно продаём малый объём из резерва.'))
        self.w.execute(self.s,action('cancel_exchange',exchange_id=self.w.exchanges[-1]['id']))
        self.assertEqual(self.w.exchanges[-1]['status'],'cancelled');self.assertEqual(before,self.s.stocks)
    def test_every_command_has_a_typed_contract(self):self.assertEqual(set(PRICES),set(CONTRACTS))
    def test_negated_build_and_future_plan_do_not_force_purchase_or_model_request(self):
        for text in ('Сегодня не строю, сохраняю резерв.','Сегодня не построю, средств недостаточно.','Через пять дней построю замок.'):
            d=self.decision();d['thinking']=text;self.assertFalse(missing_today_build(d))
    def test_all_building_types_really_build_and_pay(self):
        from planet.engine import BUILDINGS
        from planet.modern_catalog import BUILDINGS as MODERN,TECHNOLOGIES,MODERN_RESOURCES
        for kind in list(BUILDINGS)+list(MODERN):
            with self.subTest(building=kind):
                w=World(size=24,count=2);s=w.states[0]
                s.tech.extend(list(TECHNOLOGIES));s.era=2
                s.stocks.update({k:10**9 for k in list(s.stocks)+list(MODERN_RESOURCES)})
                info=MODERN.get(kind,{})
                p=w.positions(s.id)[0];c=w.cell(p);c.building=None;c.radiation=0
                c.terrain=(info.get('terrain') or ['science' if kind=='lab' else 'mountain' if kind=='mine' else 'grass'])[0]
                c.population=0
                if kind=='radiation_station':c.building='radiation_test_range';c.radiation=100
                before=s.stocks['money'];w.execute(s,action('build',cell=p,building=kind,level=1))
                self.assertEqual(c.building,kind);self.assertEqual(c.building_level,1);self.assertLess(s.stocks['money'],before)
    def test_all_technologies_really_research_and_pay(self):
        from planet.technology import TECHNOLOGIES as BASE
        from planet.modern_catalog import TECHNOLOGIES as MODERN,MODERN_RESOURCES
        for kind in list(BASE)+list(MODERN):
            with self.subTest(technology=kind):
                w=World(size=24,count=2);s=w.states[0]
                s.tech=[k for k in list(BASE)+list(MODERN) if k!=kind];s.era=2 if kind!='industrialization' else 1
                s.stocks.update({k:10**9 for k in list(s.stocks)+list(MODERN_RESOURCES)})
                p=w.positions(s.id)[0];c=w.cell(p);c.terrain='science';c.building='lab';c.integrity=100
                info=MODERN.get(kind,{})
                if info.get('site'):
                    q=w.positions(s.id)[1];w.cell(q).building=info['site'];w.cell(q).radiation=100
                before=s.stocks.copy();w.execute(s,action('research',cell=p,tech=kind))
                self.assertIn(kind,s.tech);self.assertLess(s.stocks['money'],before['money']);self.assertLess(s.stocks['science'],before['science'])
    def test_all_modern_unit_types_really_recruit(self):
        from planet.modern_catalog import UNITS,TECHNOLOGIES,MODERN_RESOURCES
        for kind in UNITS:
            with self.subTest(unit=kind):
                w=World(size=24,count=2);s=w.states[0];s.tech.extend(TECHNOLOGIES);s.era=2
                s.stocks.update({k:10**9 for k in list(s.stocks)+list(MODERN_RESOURCES)})
                p=w.positions(s.id)[0];w.cell(p).terrain='grass';w.cell(p).radiation=0;w.cell(p).population=10000
                w.units=[u for u in w.units if u['cell']!=p]
                before=s.stocks['money'];w.execute(s,action('recruit_modern',cell=p,unit=kind))
                self.assertEqual(w.units[-1]['type'],kind);self.assertLess(s.stocks['money'],before)
    def test_build_lab_then_research_without_cell_uses_that_lab(self):
        for q in self.w.positions(self.s.id):
            if self.w.cell(q).building=='lab':self.w.cell(q).building=None
        p=next(q for q in self.w.positions(self.s.id) if self.w.cell(q).terrain=='science')
        self.w.cell(p).building=None;self.ctx=self.w.context(self.s)
        d=self.decision([action('build',cell=p,building='lab',level=1),action('research',tech='agriculture')])
        fixed=compile_orders(self.ctx,d);self.assertEqual(fixed['actions'][1]['args']['cell'],p)
        self.assertEqual(preview_orders(self.w,self.s.id,fixed)['failed'],0)
    def test_invalid_message_and_relation_have_private_failure_receipts(self):
        d=self.decision();d['diplomacy']=[dict(to='missing',text='Письмо')];d['relation_reviews']={'missing':{'trust':0}}
        self.w.apply_decision(self.s,d)
        self.assertFalse(self.s.decision_outcome['message_results'][0]['success'])
        self.assertFalse(self.s.decision_outcome['relation_results'][0]['success'])
    def test_runner_resumes_old_selected_project_and_really_builds(self):
        p=self.project();d=self.decision();d['construction_review']=self.review(p)
        self.w.in_day=True;self.w.phase='resolution';self.w.cursor=2;self.w.pending_decisions={self.s.id:d}
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'world.sqlite3');store.save(self.w)
            runner=Runner(self.w,store,dict(external_console=False,decision_compiler=True))
            with patch.object(Brain,'complete',side_effect=AssertionError('Do not reroll personality')):runner.work()
            self.assertEqual(runner.world.cell(p['cell']).building,'castle')
            self.assertEqual(runner.world.state(self.s.id).notes,d['notes']);self.assertEqual(runner.world.phase,'manager')

if __name__=='__main__':unittest.main()
