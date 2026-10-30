import copy,json,math,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from planet.engine import World,Store,RuleError
from planet.brain import Brain,AutomaticRetry
from planet.deliberation import validate_assessment,needed_reviews


def action(action_type,**args): return dict(type=action_type,args=args)
def conclusion(state,peer):
    return dict(objective='Увеличить преимущество в доходах',horizon_days=5,
                alternatives=[dict(mode=mode,gain='Рост собственного влияния',risk='Сосед может ответить давлением',opponent_response='Будет искать союзника и новые источники дохода') for mode in ('development','war','economic_pressure')],chosen='development',
                risk_limits=dict(min_food_days=3,money_reserve=30,stop_condition='При дефиците остановить расширение'),
                rival_plan=dict(partner=peer.id,method='containment',phase='preparation',leverage='Контроль приграничных ресурсов',public_position='Предлагаем взаимовыгодный обмен',private_intent='Сократить относительный рост соперника',trigger='Если сосед лишится поставщика',fallback='Подготовить коалицию с третьей страной'),success_metric='Прирост добычи и территории за пять дней')
def decision(state,peer):
    return dict(thinking='Расширяем влияние',notes=state.notes,plan='Рост и борьба за превосходство',diplomacy=[dict(to='all',text='Обсудим условия сотрудничества')],actions=[],strategic_assessment=conclusion(state,peer))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=3); self.lord,self.subject,self.third=self.w.states
        for cell in self.w.cells: cell.terrain='grass'
        for state in self.w.states:
            state.operations.update(explore=False,recruit=False); state.stocks.update(money=10000,food=10000,resource=10000,metal=1000)
        self.w.day=1
    def contract(self,rate=20,duration=5):
        self.w.execute(self.lord,action('offer_vassalage',partner=self.subject.id,tribute_percent=rate,duration=duration,reason='Обмен защиты на часть дохода'))
        self.w.execute(self.subject,action('accept_vassalage',offer_id=self.w.vassal_offers[-1]['id'],reason='Сохранить самостоятельные земли и армию'))
        return self.w.vassal_treaties[-1]
    def own_cell(self,state): return self.w.positions(state.id)[0]
    def pledge(self,kind='delivery',public=False,amount=20):
        self.w.execute(self.lord,action('pledge',partner=self.subject.id,kind=kind,duration=2,public=public,resource='food',amount=amount))
        return self.w.pledges[-1]


class VassalTests(Fixture):
    def test_offer_has_no_forced_submission_or_asset_transfer(self):
        before=copy.deepcopy(self.subject)
        self.w.execute(self.lord,action('offer_vassalage',partner=self.subject.id,tribute_percent=20,duration=5,reason='Защита за денежный доход'))
        self.assertEqual(self.subject.stocks,before.stocks); self.assertEqual(self.subject.notes,before.notes); self.assertIsNone(self.subject.vassal_of)
    def test_consent_preserves_land_army_stocks_and_character(self):
        positions=self.w.positions(self.subject.id); stocks=self.subject.stocks.copy(); notes=self.subject.notes
        count=sum(u['owner']==self.subject.id for u in self.w.units)
        treaty=self.contract(); self.assertEqual(self.subject.vassal_of,self.lord.id)
        self.assertEqual(self.w.positions(self.subject.id),positions); self.assertEqual(self.subject.stocks,stocks); self.assertEqual(self.subject.notes,notes)
        self.assertEqual(sum(u['owner']==self.subject.id for u in self.w.units),count); self.assertEqual(treaty['status'],'active')
    def test_only_addressee_can_accept_and_expired_offer_is_rejected_atomically(self):
        self.w.execute(self.lord,action('offer_vassalage',partner=self.subject.id,tribute_percent=20,duration=5,reason='Защита за денежный доход')); before=self.w.data()
        with self.assertRaises(RuleError): self.w.execute(self.third,action('accept_vassalage',offer_id=1,reason='Проверка чужого договора'))
        self.assertEqual(self.w.data(),before); self.w.day=7
        with self.assertRaises(RuleError): self.w.execute(self.subject,action('accept_vassalage',offer_id=1,reason='Проверка просроченного договора'))
        self.assertIsNone(self.subject.vassal_of)
    def test_cycles_and_nested_lords_are_rejected(self):
        self.contract(); before=self.w.data()
        with self.assertRaises(RuleError): self.w.execute(self.subject,action('offer_vassalage',partner=self.lord.id,tribute_percent=20,duration=5,reason='Попытка создать цикл'))
        with self.assertRaises(RuleError): self.w.execute(self.third,action('offer_vassalage',partner=self.lord.id,tribute_percent=20,duration=5,reason='Попытка вложить иерархию'))
        self.assertEqual(self.w.data(),before)
    def test_tribute_forecast_matches_next_income_and_conserves_money(self):
        self.contract(); before={s.id:s.stocks.copy() for s in self.w.states}; forecasts={s.id:self.w.economic_forecast(s) for s in self.w.states}
        own_gross=sum(self.w.production_for_cell(self.subject,self.w.cell(p))['money'] for p in self.w.positions(self.subject.id))
        expected=round(own_gross*.2,2); self.w.start_day()
        self.assertEqual(self.w.vassal_treaties[0]['last_payment']['amount'],expected)
        for state in self.w.states:
            for key,item in forecasts[state.id]['resources'].items(): self.assertAlmostEqual(state.stocks[key]-before[state.id][key],item['base_net'])
        self.assertEqual(forecasts[self.subject.id]['tribute_balance'],-expected)
    def test_term_pays_exact_number_of_days_and_expires_before_next_income(self):
        treaty=self.contract(duration=5); gross=sum(self.w.production_for_cell(self.subject,self.w.cell(p))['money'] for p in self.w.positions(self.subject.id))
        for _ in range(5): self.w.in_day=False; self.w.start_day()
        self.assertEqual(treaty['paid_total'],round(gross*.2*5,2)); self.assertEqual(self.w.tribute_forecast()[self.subject.id],0)
        self.w.in_day=False; self.w.start_day(); self.assertIsNone(self.subject.vassal_of); self.assertEqual(treaty['status'],'expired')
    def test_attack_on_subject_automatically_brings_lord_into_war(self):
        self.contract(); self.w.set_war(self.third.id,self.subject.id,'Нападение на вассала')
        self.assertTrue(self.w.at_war(self.third.id,self.lord.id)); self.assertTrue(self.w.at_war(self.third.id,self.subject.id))
    def test_vassal_cannot_start_independent_war_or_pay_for_illegal_attack(self):
        self.contract(); before=self.w.data()
        with self.assertRaises(RuleError): self.w.execute(self.subject,action('declare_war',partner=self.third.id,reason='Самовольная война'))
        self.assertEqual(self.w.data(),before)
        unit=next(u for u in self.w.units if u['owner']==self.subject.id); p=self.w.adjacent(unit['cell'])[0]
        self.w.cell(p).owner=self.third.id; money=self.subject.stocks['money']
        self.assertIsNotNone(self.w.step_unit(unit,p)); self.assertEqual(self.subject.stocks['money'],money)
    def test_rebellion_stops_tribute_and_begins_independence_war(self):
        treaty=self.contract(); self.w.execute(self.subject,action('rebel'))
        self.assertIsNone(self.subject.vassal_of); self.assertEqual(treaty['status'],'rebelled'); self.assertTrue(self.w.at_war(self.subject.id,self.lord.id))
        self.assertEqual(self.w.tribute_forecast()[self.subject.id],0)
    def test_release_and_lord_defeat_leave_subject_independent(self):
        self.contract(); self.w.execute(self.lord,action('release_vassal',partner=self.subject.id)); self.assertIsNone(self.subject.vassal_of)
        self.w.vassal_offers[0]['status']='closed'; self.contract(); self.w.eliminate_state(self.lord)
        self.assertIsNone(self.subject.vassal_of); self.assertFalse(self.subject.eliminated)
    def test_accepting_lord_who_would_have_to_attack_own_subject_is_atomic(self):
        self.contract(); self.w.set_war(self.third.id,self.subject.id,'Атака защищённой страны')
        self.w.execute(self.lord,action('offer_vassalage',partner=self.third.id,tribute_percent=20,duration=5,reason='Предложение прекратить конфликт'))
        before=self.w.data()
        with self.assertRaises(RuleError): self.w.execute(self.third,action('accept_vassalage',offer_id=2,reason='Попытка недопустимого договора'))
        self.assertEqual(self.w.data(),before)
    def test_save_roundtrip_keeps_contract_and_private_history(self):
        self.contract(); self.pledge(); before=self.w.data()
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'world.sqlite3',export=True); store.save(self.w); loaded=store.load()
            self.assertEqual(loaded.data(),before); self.assertTrue((Path(temp)/'vassalage.json').exists()); self.assertTrue((Path(temp)/'pledges.json').exists())
    def test_political_influence_rewards_lord_but_retains_subjects_real_assets(self):
        before={r['state']:r for r in self.w.strategic_context(self.lord)['ranking']}; self.contract()
        after={r['state']:r for r in self.w.strategic_context(self.lord)['ranking']}
        self.assertGreater(after[self.lord.id]['score'],before[self.lord.id]['score']); self.assertLess(after[self.subject.id]['score'],before[self.subject.id]['score'])
        self.assertEqual(after[self.subject.id]['territory'],before[self.subject.id]['territory'])
    def test_political_context_cannot_modify_real_payment_history(self):
        treaty=self.contract(); self.w.start_day(); payment=treaty['last_payment']['amount']
        context=self.w.political_context(self.subject); context['treaties'][0]['last_payment']['amount']=999999
        self.assertEqual(treaty['last_payment']['amount'],payment)


class PromiseTests(Fixture):
    def test_promise_is_not_escrow_or_automatic_delivery(self):
        stocks=self.lord.stocks.copy(); pledge=self.pledge(); self.assertEqual(self.lord.stocks,stocks); self.assertEqual(pledge['delivered'],0)
    def test_one_delivery_is_allocated_once_across_two_promises(self):
        first=self.pledge(amount=20); second=self.pledge(amount=20)
        self.w.execute(self.lord,action('transfer',cell=self.own_cell(self.lord),partner=self.subject.id,resource='food',amount=25))
        self.assertEqual(first['status'],'fulfilled'); self.assertEqual(second['delivered'],5); self.assertEqual(second['status'],'open')
    def test_real_trade_fulfills_delivery_obligation(self):
        pledge=self.pledge(amount=20); p=self.own_cell(self.lord)
        self.w.execute(self.lord,action('trade',cell=p,partner=self.subject.id,resource='food',amount=20,price=1))
        self.assertEqual(pledge['status'],'open')
        self.w.execute(self.subject,action('accept_trade',cell=self.own_cell(self.subject),offer_id=1)); self.assertEqual(pledge['status'],'fulfilled')
    def test_expired_public_lie_costs_receiver_and_witness_trust(self):
        pledge=self.pledge(public=True); self.w.day=pledge['due_day']+1; self.w.process_contracts()
        self.assertEqual(pledge['status'],'broken'); self.assertEqual(self.w.relation(self.subject.id,self.lord.id)['trust'],-20)
        self.assertEqual(self.w.relation(self.third.id,self.lord.id)['trust'],-5)
        self.w.process_contracts(); self.assertEqual(self.w.relation(self.third.id,self.lord.id)['trust'],-5)
    def test_private_pledge_and_private_action_are_not_exposed_to_third_state(self):
        result=decision(self.lord,self.subject); result['actions']=[action('pledge',partner=self.subject.id,kind='delivery',duration=2,public=False,resource='food',amount=20)]
        self.w.apply_decision(self.lord,result)
        self.assertEqual(self.w.political_context(self.third)['pledges'],[])
        events=self.w.context(self.third)['events']; self.assertFalse(any('Зарегистрировано обещание' in e['text'] for e in events))
        self.assertEqual(len(self.w.political_context(self.subject)['pledges']),1)
        self.w.day=4; self.w.process_contracts(); self.assertEqual(self.w.relation(self.third.id,self.lord.id)['trust'],0)
    def test_non_aggression_can_be_betrayed_but_is_recorded(self):
        pledge=self.pledge(kind='non_aggression',public=True); self.w.set_war(self.lord.id,self.subject.id,'Внезапное нападение')
        self.assertEqual(pledge['status'],'broken'); self.assertTrue(self.w.at_war(self.lord.id,self.subject.id))
        self.assertTrue(any(f['kind']=='promise_broken' for f in self.w.relation(self.subject.id,self.lord.id)['facts']))
    def test_defending_against_attack_does_not_count_as_breaking_own_pledge(self):
        pledge=self.pledge(kind='non_aggression'); self.w.set_war(self.subject.id,self.lord.id,'Нападение адресата обещания')
        self.assertEqual(pledge['status'],'open'); self.w.day=4; self.w.process_contracts(); self.assertEqual(pledge['status'],'fulfilled')
    def test_past_transfer_cannot_retroactively_fulfil_future_promise(self):
        self.w.execute(self.lord,action('transfer',cell=self.own_cell(self.lord),partner=self.subject.id,resource='food',amount=20))
        pledge=self.pledge(); self.assertEqual(pledge['delivered'],0)


class AnalysisTests(Fixture):
    def test_brief_predicts_shortage_and_affordable_population_without_mutation(self):
        self.lord.stocks['resource']=5
        before=self.w.data(); brief=self.w.decision_brief(self.lord)
        self.assertEqual(brief['affordable_settlers_now'],0); self.assertEqual(self.w.data(),before)
        self.assertIn('after_7_days',brief['resource_horizon']['food'])
        self.assertTrue(all(self.w.cell(p).owner==self.lord.id and not self.w.cell(p).population and self.w.cell(p).terrain!='water' for p in brief['settlement_sites']))
    def test_counterfactual_ally_war_plan_is_legal_to_analyse_but_not_execute(self):
        unit=self.w.units[0]; target=self.w.adjacent(unit['cell'])[0]; self.w.cell(target).owner=self.subject.id
        self.w.units=[u for u in self.w.units if u['cell']!=target]; self.w.spawn(self.subject.id,target,'army',2)
        self.lord.allies=[self.subject.id]; self.subject.allies=[self.lord.id]; before=self.w.data()
        brief=self.w.decision_brief(self.lord); option=next(o for o in brief['war_options'] if o['target']==target)
        self.assertTrue(option['captures_on_first_exchange']); self.assertEqual(option['minimum_cost'],22)
        self.assertEqual(self.w.data(),before); self.assertIsNone(self.w.find_route(unit,target))
        money=self.lord.stocks['money']; self.assertIsNotNone(self.w.step_unit(unit,target)); self.assertEqual(self.lord.stocks['money'],money)
    def test_context_never_exposes_enemy_private_scheme_or_budget(self):
        self.subject.strategic_assessment=conclusion(self.subject,self.lord); self.subject.strategic_assessment['rival_plan']['private_intent']='SECRET_SCHEME_MARKER'
        self.subject.stocks['money']=987654321; text=json.dumps(self.w.context(self.lord),ensure_ascii=False)
        self.assertNotIn('SECRET_SCHEME_MARKER',text); self.assertNotIn('987654321',text)
    def deep_result(self):
        result=decision(self.lord,self.subject)
        result['relation_reviews']={peer.id:dict(trust=0,stance='neutral',trade_policy='normal',memo='Осторожное сотрудничество с проверкой выгоды') for peer in (self.subject,self.third)}
        return result
    def test_deep_response_integrates_dossiers_without_another_llm_request(self):
        brain=Brain(dict(model='test',deep_strategy=True)); context=self.w.context(self.lord); result=self.deep_result()
        with patch.object(brain,'complete',return_value=result) as call:
            actual=brain.think(self.lord,context); reviewed=brain.review_relationships(self.lord,context,actual)
        self.assertEqual(call.call_count,1); self.assertEqual(actual,reviewed); self.assertEqual(actual['relation_review_attempted'],self.w.day)
        self.w.apply_decision(self.lord,actual); self.assertEqual(self.lord.strategic_assessment,actual['strategic_assessment'])
    def test_missing_deep_risk_analysis_receives_precise_correction(self):
        brain=Brain(dict(model='test',deep_strategy=True)); bad=self.deep_result(); bad['strategic_assessment'].pop('risk_limits')
        with patch.object(brain,'complete',side_effect=[bad,self.deep_result()]) as call:
            draft=brain.think(self.lord,self.w.context(self.lord)); actual=brain.review_strategy(self.lord,self.w.context(self.lord),draft)
        self.assertIn('risk_limits',call.call_args_list[1].args[1]['section_error']); self.assertIn('risk_limits',actual['strategic_assessment'])
        self.assertEqual(draft['actions'],actual['actions']); self.assertIn('_response_schema',call.call_args_list[1].args[1])
    def test_border_requires_explicit_comparison_with_war(self):
        result=self.deep_result(); result['strategic_assessment']['alternatives'][1]['mode']='coalition'
        context=self.w.context(self.lord); context['strategy']['border_targets']={self.subject.id:[dict(cell=[1,1])]}
        with self.assertRaises(ValueError): validate_assessment(result,self.lord,context)
    def test_rival_plan_cannot_target_own_country_in_natural_language(self):
        result=self.deep_result(); result['strategic_assessment']['rival_plan']['private_intent']='Превзойти '+self.lord.name+' по территории и богатству'
        with self.assertRaisesRegex(ValueError,'собственная|собственна'): validate_assessment(result,self.lord,self.w.context(self.lord))
    def test_fixing_identity_changes_only_private_intent_not_the_rest_of_plan(self):
        result=self.deep_result(); result['strategic_assessment']['rival_plan']['private_intent']='Удерживать '+self.lord.name+' в роли зависимого поставщика'
        old=copy.deepcopy(result); brain=Brain(dict(model='test',deep_strategy=True))
        supplement=dict(relation_reviews={},strategic_assessment=dict(rival_plan=dict(private_intent='Сделать выбранного соперника зависимым от наших поставок')))
        with patch.object(brain,'complete',return_value=supplement) as complete:
            fixed=brain.review_strategy(self.lord,self.w.context(self.lord),result)
        expected=old['strategic_assessment']['rival_plan']; expected['private_intent']=supplement['strategic_assessment']['rival_plan']['private_intent']
        self.assertEqual(fixed['strategic_assessment']['rival_plan'],expected); self.assertEqual(fixed['actions'],old['actions'])
        schema=complete.call_args.args[1]['_response_schema']['json_schema']['schema']
        self.assertEqual(schema['properties']['strategic_assessment']['properties']['rival_plan']['required'],['private_intent'])
    def test_invalid_risk_numbers_or_unknown_target_are_rejected(self):
        for key,value in [('money_reserve',math.nan),('min_food_days',-1)]:
            result=self.deep_result(); result['strategic_assessment']['risk_limits'][key]=value
            with self.assertRaises(ValueError): validate_assessment(result,self.lord,self.w.context(self.lord))
        result=self.deep_result(); result['strategic_assessment']['rival_plan']['partner']=self.lord.id
        with self.assertRaises(ValueError): validate_assessment(result,self.lord,self.w.context(self.lord))
    def test_failure_of_supplement_does_not_reroll_or_execute_saved_primary(self):
        from main import Runner
        brain=Brain(dict(model='test',deep_strategy=True,decision_repair_attempts=1)); draft=self.deep_result(); draft['strategic_assessment']['alternatives']=draft['strategic_assessment']['alternatives'][:2]
        with patch.object(brain,'complete',return_value=draft): provisional=brain.think(self.lord,self.w.context(self.lord))
        self.assertIn('strategic_review_required',provisional)
        self.w.in_day=True; self.w.phase='resolution'; self.w.cursor=3; self.w.pending_decisions={self.lord.id:provisional}
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'world.sqlite3'); store.save(self.w); runner=Runner(self.w,store,dict(deep_strategy=True,external_console=False))
            with patch.object(runner.brain,'review_strategy',side_effect=AutomaticRetry('Уточнение временно недоступно')),patch.object(runner.brain,'think') as think:
                runner.work()
            think.assert_not_called(); loaded=store.load(); self.assertEqual(loaded.pending_decisions,self.w.pending_decisions)
            self.assertEqual(loaded.phase,'preparing'); self.assertEqual(len(loaded.decisions),0)
            self.assertTrue(any(kind=='retry' for kind,_ in list(runner.messages.queue)))
    def test_structured_supplement_schema_is_sent_only_to_supplement(self):
        from planet.deliberation import supplement_schema
        brain=Brain(dict(model='test',manage_model_context=False)); result=dict(done='Готово'); response=dict(choices=[dict(message=dict(content=json.dumps(result)),finish_reason='stop')]); schema=supplement_schema([],False)
        with patch.object(brain,'stream_request',return_value=response) as send:
            brain.complete('Только JSON',dict(_response_schema=schema), 'test')
            self.assertEqual(send.call_args.args[0]['response_format'],schema)
            self.assertNotIn('_response_schema',send.call_args.args[0]['messages'][1]['content'])
            brain.complete('Основной JSON',dict(day=1),'test'); self.assertNotIn('response_format',send.call_args.args[0])


class OptimisationTests(Fixture):
    def test_analysis_cache_is_cleared_after_read_and_after_mutation(self):
        with self.w.analysis_scope():
            self.assertIsNotNone(self.w._analysis_index)
            unit=self.w.units[0]; target=self.w.adjacent(unit['cell'])[0]; self.w.cell(target).owner=None
            self.w.step_unit(unit,target); self.assertIsNone(self.w._analysis_index)
            self.assertIn(target,self.w.positions(self.lord.id))
        self.assertIsNone(self.w._analysis_index)
    def test_data_and_restore_do_not_alias_live_world_or_input(self):
        data=self.w.data(); restored=World.restore(data)
        restored.cells[0].terrain='water'; restored.states[0].memory.append(dict(day=1,notes='Отдельная память',plan='Отдельный план'))
        self.assertNotEqual(restored.cells[0].terrain,data['cells'][0]['terrain']); self.assertEqual(data['states'][0]['memory'],[])
        data['cells'][1]['terrain']='water'; self.assertNotEqual(self.w.cells[1].terrain,'water')
    def test_unchanged_exports_are_not_rewritten_but_checkpoint_still_contains_pending(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'world.sqlite3',export=True); store.save(self.w)
            statefile=Path(temp)/'states'/self.lord.id/'state.json'; modified=statefile.stat().st_mtime_ns
            self.w.cursor=1; self.w.pending_decisions[self.lord.id]=decision(self.lord,self.subject); store.save(self.w)
            self.assertEqual(statefile.stat().st_mtime_ns,modified); loaded=store.load()
            self.assertEqual(loaded.pending_decisions,self.w.pending_decisions); self.assertEqual(loaded.cursor,1)
            self.assertEqual(json.loads((Path(temp)/'world.json').read_text(encoding='utf-8'))['pending_decisions'],self.w.pending_decisions)
    def test_route_is_searched_once_per_multistep_move_without_losing_validation(self):
        unit=self.w.units[0]; target=[unit['cell'][0]+4,unit['cell'][1]]
        self.w.units=[unit]; self.lord.operations['explore']=False
        with patch.object(self.w,'find_route',wraps=self.w.find_route) as find:
            self.w.execute(self.lord,action('move',unit_id=unit['id'],target_cell=target))
        # One validation search and one execution search, not one BFS for each of4 steps.
        self.assertLessEqual(find.call_count,2); self.assertEqual(unit['cell'],target); self.assertEqual(len(self.w.movement_log),4)
    def test_relations_reader_reuses_unchanged_snapshot_and_detects_commit(self):
        from planet.relations_window import SnapshotReader
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'world.sqlite3'; store=Store(path); store.save(self.w); reader=SnapshotReader(path)
            try:
                first=reader.read(); self.assertIs(reader.read(),first)
                self.w.day+=1; store.save(self.w); latest=reader.read(); self.assertIsNot(latest,first); self.assertEqual(latest.day,self.w.day)
            finally: reader.close()


if __name__=='__main__': unittest.main()
