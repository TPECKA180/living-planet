import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from planet.engine import World,Store,PRICES
from planet.brain import Brain,RULES
from planet.context import fit,estimate
from planet.decision_format import decision_schema
from planet.intelligence import briefing,normalize_decision,validate_actions,repetitive_tail,RepeatedOutput,CONTRACTS


class Fixture(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=3); self.s,self.other=self.w.states[:2]; self.w.day=9
        self.s.stocks.update(money=10000,science=4000,metal=4000,food=4000,resource=4000,matter=1000)
        self.lab=next(p for p in self.w.positions(self.s.id) if self.w.cell(p).terrain=='science')
        self.w.cell(self.lab).building='lab'; self.w.cell(self.lab).building_level=1
        self.ctx=self.w.context(self.s)
    def decision(self,actions=None,mode='none'):
        return dict(owner=self.s.id,origin_patch='6.2',thinking='Развиваем собственное государство.',notes=self.s.notes,plan=self.s.plan,
            diplomacy=[dict(to=self.other.id,text='Предлагаем обсудить конкретные условия торговли.')],actions=actions or [],
            economic_review=dict(mode=mode,reason='Сохраняем бюджет и конкретные интересы собственной страны.',orders=[]))


class GroundingTests(Fixture):
    def test_missing_research_coordinate_is_grounded_and_research_really_pays(self):
        raw=self.decision([dict(type='research',args=dict(tech='agriculture'))]); old=copy.deepcopy(raw)
        fixed=normalize_decision(raw,self.ctx); validate_actions(fixed,self.ctx)
        before=self.s.stocks['science']; self.w.execute(self.s,fixed['actions'][0])
        self.assertIn('agriculture',self.s.tech); self.assertLess(self.s.stocks['science'],before)
        self.assertEqual(fixed['actions'][0]['args']['cell'],self.lab); self.assertEqual(raw,old)
    def test_no_science_site_is_not_invented(self):
        context=dict(self.ctx,action_sites=dict(research_cells=[]))
        fixed=normalize_decision(self.decision([dict(type='research',args=dict(tech='agriculture'))]),context)
        self.assertRaises(ValueError,validate_actions,fixed,context)
    def test_explicit_project_compiles_to_exact_paid_building(self):
        p=self.ctx['construction']['projects'][0]
        fixed=normalize_decision(self.decision([dict(type='build',args=dict(project_id=p['project_id']))]),self.ctx)
        validate_actions(fixed,self.ctx); before=dict(self.s.stocks); self.w.execute(self.s,fixed['actions'][0])
        self.assertEqual(self.w.cell(p['cell']).building,p['building']); self.assertLess(self.s.stocks['money'],before['money'])
    def test_another_countrys_project_is_not_resolved(self):
        fixed=normalize_decision(self.decision([dict(type='build',args=dict(project_id='state_2/secret/project'))]),self.ctx)
        self.assertRaises(ValueError,validate_actions,fixed,self.ctx)
    def test_compilation_is_idempotent_and_does_not_change_personality_or_letters(self):
        raw=self.decision([dict(type='research',args=dict(tech='agriculture')),dict(type='do_nothing',args={})])
        fixed=normalize_decision(raw,self.ctx)
        self.assertEqual(normalize_decision(fixed,self.ctx),fixed)
        for key in ('owner','thinking','notes','plan','diplomacy'): self.assertEqual(raw[key],fixed[key])
    def test_keep_marker_preserves_full_long_character_instead_of_erasing_or_regenerating_it(self):
        context=dict(self.ctx,notes='Уникальная старая память '*4000,plan='Старый план без изменений.')
        raw=self.decision(); raw.update(notes=None,plan=None)
        fixed=normalize_decision(raw,context); Brain({}).validate_decision(fixed,self.s,context)
        self.assertEqual(fixed['notes'],context['notes']); self.assertEqual(fixed['plan'],context['plan']); self.assertIsNone(raw['notes'])
    def test_noop_padding_no_longer_forces_a_model_call_for_a_selected_build(self):
        p=self.ctx['construction']['projects'][0]; raw=self.decision([dict(type='do_nothing',args={}) for _ in range(12)])
        raw['construction_review']=dict(choice='build',project_id=p['project_id'],reason='Это уже выбранный реальный проект с известной оплатой.',revisit_day=10)
        brain=Brain(dict(decision_compiler=True))
        with patch.object(brain,'complete',side_effect=AssertionError('Unnecessary model request')):
            fixed=brain.review_construction(self.s,self.ctx,raw)
        self.assertEqual(len(fixed['actions']),1); self.assertEqual(fixed['actions'][0]['type'],'build')
    def test_bookkeeping_mode_can_be_fixed_without_reroll_or_new_payment(self):
        raw=self.decision([dict(type='transfer',args=dict(partner=self.other.id,resource='food',amount=1))])
        brain=Brain(dict(decision_compiler=True))
        with patch.object(brain,'complete',side_effect=AssertionError('Unnecessary model request')):
            fixed=brain.review_economy(self.s,self.ctx,raw)
        self.assertEqual(fixed['economic_review']['mode'],'execute'); self.assertEqual(fixed['actions'],raw['actions'])
        self.assertEqual(self.w.settlements,[])
    def test_order_section_is_also_explicit_intent(self):
        raw=self.decision(); raw['economic_review']['orders']=[dict(type='trade',args=dict(partner=self.other.id,resource='metal',amount=1,price=2))]
        fixed=normalize_decision(raw,self.ctx)
        self.assertEqual(fixed['economic_review']['mode'],'negotiate'); self.assertEqual(fixed['actions'],[])
    def test_deceit_does_not_get_converted_into_an_honest_transfer(self):
        raw=self.decision(mode='deceive'); raw['diplomacy'][0]['text']='Деньги уже отправлены, ждите.'
        fixed=normalize_decision(raw,self.ctx)
        self.assertEqual(fixed['actions'],[]); self.assertEqual(fixed['economic_review']['mode'],'deceive')
        self.w.apply_decision(self.s,fixed); self.assertEqual(self.w.settlements,[])
    def test_explicit_breach_is_not_labeled_honest_execution(self):
        fixed=normalize_decision(self.decision([dict(type='breach_exchange',args=dict(exchange_id=1,reason='Оставим аванс ради собственной выгоды.'))]),self.ctx)
        self.assertEqual(fixed['economic_review']['mode'],'deceive')
    def test_ambiguous_settlement_site_is_not_chosen_for_the_player(self):
        raw=self.decision([dict(type='settle',args=dict(amount=2))]); fixed=normalize_decision(raw,self.ctx)
        self.assertNotIn('cell',fixed['actions'][0]['args']); self.assertRaises(ValueError,validate_actions,fixed,self.ctx)
    def test_enemy_unit_is_rejected_before_the_engine(self):
        enemy=next(u for u in self.w.units if u['owner']==self.other.id)
        self.assertRaises(ValueError,validate_actions,self.decision([dict(type='hold',args=dict(unit_id=enemy['id']))]),self.ctx)
    def test_known_water_is_rejected_even_with_navigation(self):
        unit=next(u for u in self.w.units if u['owner']==self.s.id)
        c=dict(self.ctx,map=[[0,0,'water',1,None,None,0,0]])
        self.assertRaises(ValueError,validate_actions,self.decision([dict(type='move',args=dict(unit_id=unit['id'],target_cell=[0,0]))]),c)
    def test_float_or_bool_coordinates_are_not_accepted_as_integers(self):
        for pos in ([True,1],[1.5,2],[9999,2]):
            self.assertRaises(ValueError,validate_actions,self.decision([dict(type='research',args=dict(tech='lab',cell=pos))]),self.ctx)
    def test_old_pending_decision_gets_coordinates_on_resolution_without_rerolling_character(self):
        from main import Runner
        self.w.in_day=True; self.w.phase='resolution'; self.w.cursor=len(self.w.states)
        prepared=self.decision([dict(type='research',args=dict(tech='agriculture'))]); prepared['origin_patch']='6.1'
        prepared['notes']='Наш старый уникальный характер полностью сохраняется.'
        self.w.pending_decisions={self.s.id:prepared}
        with tempfile.TemporaryDirectory() as folder:
            runner=Runner(self.w,Store(Path(folder)/'world.sqlite3'),dict(decision_compiler=True,external_console=False))
            with patch.object(runner.brain,'complete',side_effect=AssertionError('Saved character must not be regenerated')):
                runner.work()
            self.assertIn('agriculture',runner.world.state(self.s.id).tech)
            self.assertEqual(runner.world.state(self.s.id).notes,prepared['notes'])


class EvidenceTests(Fixture):
    def test_exact_unit_price_arithmetic_and_money_reserve(self):
        context=copy.deepcopy(self.ctx); context['stocks']['money']=300
        context['trade_offers']=[dict(id=1,partner=self.s.id,seller=self.other.id,amount=20,price=5,resource='food',status='open')]
        row=briefing(context)['trade_arithmetic'][0]
        self.assertEqual(row['total_payment'],100); self.assertEqual(row['money_after_if_buyer'],200); self.assertTrue(row['affordable_if_buyer'])
    def test_unaffordable_800_is_not_confused_with_unit_price_8(self):
        context=dict(self.ctx,stocks=dict(money=500),trade_offers=[dict(id=2,partner=self.s.id,amount=100,price=8,resource='food')])
        row=briefing(context)['trade_arithmetic'][0]; self.assertEqual(row['total_payment'],800); self.assertFalse(row['affordable_if_buyer'])
    def test_army_strength_is_separate_from_overall_ranking(self):
        context=dict(self.ctx,strategy=dict(ranking=[dict(state=self.other.id,military_strength=13,score=200),dict(state=self.s.id,military_strength=18,score=100)]))
        row=briefing(context)['military_comparison'][0]; self.assertEqual(row['military_balance'],'ours_stronger'); self.assertLess(row['our_score'],row['their_score'])
    def test_seller_does_not_learn_hidden_buyer_funds(self):
        context=dict(self.ctx,trade_offers=[dict(id=1,seller=self.s.id,partner=self.other.id,amount=20,price=5)])
        row=briefing(context)['trade_arithmetic'][0]; self.assertIsNone(row['money_after_if_buyer']); self.assertIsNone(row['affordable_if_buyer'])
    def test_other_private_personality_never_enters_context_or_briefing(self):
        self.other.notes='SECRET_OTHER_CHARACTER_991'; self.other.plan='SECRET_PLAN_552'
        text=json.dumps(self.w.context(self.s),ensure_ascii=False)
        self.assertNotIn(self.other.notes,text); self.assertNotIn(self.other.plan,text)
    def test_broken_labs_and_radioactive_settlement_sites_are_not_recommended(self):
        self.w.cell(self.lab).integrity=0
        p=next(p for p in self.w.positions(self.s.id) if not self.w.cell(p).population); self.w.cell(p).radiation=50
        c=self.w.context(self.s); self.assertNotIn(self.lab,c['action_sites']['research_cells']); self.assertNotIn(p,c['strategic_brief']['settlement_sites'])


class SchemaAndContextTests(Fixture):
    def test_every_action_stays_available_with_required_core_arguments(self):
        schema=decision_schema(self.s,self.ctx,PRICES,True,strict_actions=True)
        alternatives=schema['json_schema']['schema']['properties']['actions']['items']['anyOf']
        variants={a['properties']['type']['enum'][0]:a for a in alternatives}
        self.assertEqual(set(variants),set(PRICES)); self.assertIn('cell',variants['research']['properties']['args']['required'])
        self.assertIn('target_cell',variants['move']['properties']['args']['required']); self.assertNotIn('cell',variants['transfer']['properties']['args']['required'])
    def test_full_rules_are_not_discarded_at_one_third_when_they_fit(self):
        system='Я'*30000; brain=Brain(dict(context_window=83200,max_tokens=16384))
        with patch('planet.brain.RULES',system),patch.object(brain,'stream_request',return_value=dict(choices=[dict(message=dict(content='{"ok":true}'),finish_reason='stop')])) as call:
            brain.complete(system,dict(state='state_1',stocks={},notes='Характер'),'model')
        self.assertEqual(call.call_args.args[0]['messages'][0]['content'],system)
    def test_optimized_byte_accounting_matches_serialized_input_exactly(self):
        source=dict(identity=dict(id=self.s.id,name=self.s.name),stocks=self.s.stocks,notes='Сохрани характер',map=[[1,2,'grass']]*100)
        fitted=fit('Правила',source,100000,4000)
        metadata=fitted.pop('context_info')
        expected=estimate('Правила'+json.dumps(fitted,ensure_ascii=False,separators=(',',':')))
        self.assertEqual(metadata['estimated_input_tokens'],expected); self.assertEqual(fitted,source)
    def test_current_own_units_are_not_halved_to_make_room_for_history(self):
        units=[dict(id=i,owner='state_1',cell=[i,1]) for i in range(20)]
        source=dict(state='state_1',units=units,history=[dict(text='История'*1000) for _ in range(100)])
        fitted=fit('Правила',source,16384,4096)
        self.assertEqual(fitted['units'],units)
    def test_overflow_keeps_exact_owner_and_original_memory_is_immutable(self):
        source=dict(day=10,state='state_1',private_owner='state_1',identity=dict(id='state_1',name='Аврора'),stocks=dict(money=4),notes='Уникальная память'*10000,plan='План'*10000)
        before=copy.deepcopy(source); fitted=fit('Краткие правила',source,4096,1024)
        self.assertEqual(source,before); self.assertEqual(fitted['private_owner'],'state_1'); self.assertEqual(fitted['identity'],source['identity'])
    def test_short_english_narrative_is_no_longer_mistaken_for_russian(self):
        self.assertFalse(Brain.russian('neutral')); self.assertFalse(Brain.russian('Trade seeking')); self.assertTrue(Brain.russian('Готовы к выгодной торговле.'))
    def test_wrong_response_owner_cannot_be_silently_overwritten(self):
        d=self.decision(); d['owner']=self.other.id
        self.assertRaises(ValueError,Brain({}).validate_decision,d,self.s,self.ctx)


class StabilityTests(unittest.TestCase):
    def test_repeated_memo_is_detected_before_tens_of_thousands_of_tokens(self):
        line='Риск: зависимость от одного поставщика. Условия: согласие на цену. Выгода: экономия на логистике. '
        self.assertTrue(repetitive_tail(line*10)); self.assertFalse(repetitive_tail(' '.join(str(i)+' '+line for i in range(10))))
    def test_repeated_stream_is_repaired_without_increasing_output_budget(self):
        line='Риск: зависимость от одного поставщика. Условия: согласие на цену. Выгода: экономия на логистике. '
        counts=[0]
        class Response:
            headers={'Content-Type':'text/event-stream'}
            def readline(self,size=-1):
                if not hasattr(self,'lines'):self.lines=iter(self)
                line=next(self.lines,None)
                return line+b'\n' if line is not None else b''
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def __iter__(self):
                for _ in range(100):
                    counts[0]+=1
                    yield ('data: '+json.dumps(dict(choices=[dict(delta=dict(content=line),finish_reason=None)]))).encode('utf-8')
                    yield b''
        brain=Brain(dict(host='http://localhost:1234/v1',context_window=83200,max_tokens=16384)); original=brain.stream_request; calls=[0]
        def stream(payload):
            calls[0]+=1
            if calls[0]==1:
                with patch('urllib.request.urlopen',return_value=Response()): return original(payload)
            return dict(choices=[dict(message=dict(content='{"ok":true}'),finish_reason='stop')])
        with patch.object(brain,'stream_request',side_effect=stream): self.assertEqual(brain.complete('Правила',{},'model'),dict(ok=True))
        self.assertLess(counts[0],20); self.assertEqual(brain.response_limits,{})
    def test_import_preserves_old_characters_days_resources_and_pending_decisions(self):
        from planet.saves import WorldLibrary
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); w=World(size=24,count=2); w.day=30; w.states[0].notes='Долгая уникальная личность'; w.pending_decisions={'state_1':dict(owner='state_1',origin_patch='6.1',notes='Готовая память')}
            old=w.data(); old['patch']='6.1'; source=root/'old.sqlite3'
            with sqlite3.connect(source) as db:
                db.execute('create table snapshot(id integer primary key,data text)'); db.execute('insert into snapshot values(1,?)',(json.dumps(old,ensure_ascii=False),))
            db.close()
            before=source.read_bytes(); new,store=WorldLibrary(root/'saves').import_legacy(source,'Продолжение6.2')
            self.assertEqual(before,source.read_bytes()); self.assertEqual(new.data()['states'],old['states']); self.assertEqual(new.pending_decisions,old['pending_decisions']); self.assertEqual(new.day,30)
            self.assertEqual(new.data()['patch'],'7.5.1'); self.assertTrue(list((store.path.parent/'backups').glob('before-v7.5.1-*.sqlite3')))


if __name__=='__main__': unittest.main()
