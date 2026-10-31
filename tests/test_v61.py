import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from planet.engine import World,Store,RuleError
from planet.brain import Brain,AutomaticRetry
from planet.commerce import ECONOMIC_ACTIONS
from planet.economic_ai import signature
from planet.isolation import checked_context


def action(action_type,**args): return dict(type=action_type,args=args)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.w=World(size=32,count=3); self.a,self.b,self.c=self.w.states; self.w.day=10
        for s in self.w.states: s.stocks.update(food=10000,resource=10000,money=10000,metal=10000,science=10000,matter=10000); s.operations.update(explore=False,recruit=False)
    def offer(self,**args):
        self.w.execute(self.a,action('trade',partner=self.b.id,resource='metal',amount=40,price=2,**args)); return self.w.trade_offers[-1]
    def exchange(self,mode='advance',give=None,receive=None):
        self.w.execute(self.a,action('offer_exchange',partner=self.b.id,give=give or dict(food=100),receive=receive or dict(money=200),mode=mode,due_days=3,reason='Частный расчёт: получим преимущество перед соперником.'))
        return self.w.exchanges[-1]
    def accept(self,deal): return self.w.execute(self.b,action('accept_exchange',exchange_id=deal['id'],allow_risk=True,reason='Осознанно принимаю риск необеспеченного обмена ради текущей выгоды.'))
    def decision(self,**extra):
        value=dict(thinking='Решение ради превосходства.',notes='Сохраняем собственный характер и память.',plan='Получить реальную экономическую выгоду.',diplomacy=[dict(to=self.b.id,text='Готовы обсудить поставку.')],actions=[],owner=self.a.id,origin_patch='6.1',economic_review=dict(mode='none',reason='Сегодня нет необходимых казначейских операций, продолжаем переговоры.',orders=[]))
        value.update(extra); return value


class TreasuryTests(Fixture):
    def test_actual_accept_trade_works_without_any_cell_and_creates_two_real_receipts(self):
        offer=self.offer(); before={s.id:dict(s.stocks) for s in (self.a,self.b)}
        self.w.execute(self.b,action('accept_trade',offer_id=offer['id']))
        self.assertEqual(self.b.stocks['metal'],before[self.b.id]['metal']+40); self.assertEqual(self.a.stocks['metal'],before[self.a.id]['metal']-40)
        self.assertEqual(self.b.stocks['money'],before[self.b.id]['money']-80); self.assertEqual(self.a.stocks['money'],before[self.a.id]['money']+80)
        self.assertEqual(len(self.w.settlements),2); self.assertEqual(offer['receipt_ids'],[1,2])
    def test_offer_is_not_a_transfer_and_seller_cannot_accept_on_behalf_of_buyer(self):
        before=self.w.data(); offer=self.offer(); self.assertEqual(self.a.stocks,before['states'][0]['stocks']); self.assertEqual(self.b.stocks,before['states'][1]['stocks'])
        self.assertRaises(RuleError,self.w.execute,self.a,action('accept_trade',offer_id=offer['id'])); self.assertEqual(self.w.settlements,[])
    def test_transfer_is_cell_free_even_with_an_irrelevant_stale_coordinate(self):
        before=self.b.stocks['food']; self.w.execute(self.a,action('transfer',partner=self.b.id,resource='food',amount=500,cell=[9999,9999])); self.assertEqual(self.b.stocks['food'],before+500)
        self.assertEqual(self.w.settlements[-1]['resources'],dict(food=500))
    def test_cannot_spend_or_multiply_nonexistent_resources_or_replay_acceptance(self):
        offer=self.offer(); self.b.stocks['money']=1; before=self.w.data()
        self.assertRaises(RuleError,self.w.execute,self.b,action('accept_trade',offer_id=offer['id'],allow_risk=True,reason='Сознательно согласны на экономический риск.')); self.assertEqual(self.w.data(),before)
        self.b.stocks['money']=10000; self.w.execute(self.b,action('accept_trade',offer_id=offer['id'])); after=self.w.data()
        self.assertRaises(RuleError,self.w.execute,self.b,action('accept_trade',offer_id=offer['id'])); self.assertEqual(after,self.w.data())
    def test_receipt_deltas_agree_with_before_after_balances_and_decimal_price(self):
        self.w.execute(self.a,action('trade',partner=self.b.id,resource='metal',amount=3,price=.125)); self.w.execute(self.b,action('accept_trade',offer_id=1))
        for r in self.w.settlements:
            for sid,items in r['balances'].items():
                for k,v in items.items(): self.assertAlmostEqual(v['after']-v['before'],r['deltas'][sid][k],places=4)
        self.assertEqual(self.w.settlements[1]['resources']['money'],.375)
    def test_letter_claiming_payment_does_not_conjure_a_delivery(self):
        before=[dict(s.stocks) for s in self.w.states]; self.w.send_message(self.a,self.b.id,'Всё уже отправлено!')
        self.assertEqual(before,[s.stocks for s in self.w.states]); self.assertEqual(self.w.settlements,[])
    def test_single_trade_is_not_double_credited_to_two_delivery_promises(self):
        for _ in range(2): self.w.execute(self.a,action('pledge',partner=self.b.id,kind='delivery',resource='metal',amount=40,duration=3))
        self.offer(); self.w.execute(self.b,action('accept_trade',offer_id=1)); self.assertEqual([p['delivered'] for p in self.w.pledges],[40,0])
    def test_bad_reference_bool_negative_or_nonfinite_is_rejected_without_changes(self):
        self.offer()
        for args in (dict(offer_id=True),dict(offer_id=-1),dict(offer_id=9999)):
            before=self.w.data(); self.assertRaises(RuleError,self.w.execute,self.b,action('accept_trade',**args)); self.assertEqual(self.w.data(),before)
        self.assertRaises(RuleError,self.w.execute,self.a,action('trade',partner=self.b.id,resource='metal',amount=10,price=float('nan')))


class UnsecuredTests(Fixture):
    def test_secure_barter_settles_both_bundles_at_once(self):
        deal=self.exchange('secure',give=dict(food=100,metal=50),receive=dict(money=200,resource=30)); before={s.id:dict(s.stocks) for s in (self.a,self.b)}; self.accept(deal)
        self.assertEqual(deal['status'],'fulfilled'); self.assertEqual(self.a.stocks['money'],before[self.a.id]['money']+200); self.assertEqual(self.b.stocks['metal'],before[self.b.id]['metal']+50)
        self.assertRaises(RuleError,self.w.execute,self.a,action('breach_exchange',exchange_id=deal['id']))
    def test_secure_exchange_does_not_send_first_leg_if_second_leg_cannot_pay(self):
        deal=self.exchange('secure'); self.b.stocks['money']=0; before=self.w.data(); self.assertRaises(RuleError,self.accept,deal); self.assertEqual(self.w.data(),before)
    def test_advance_can_really_be_taken_and_goods_deliberately_withheld_for_profit(self):
        deal=self.exchange(); before=dict(self.a.stocks); self.accept(deal)
        self.assertEqual(self.a.stocks['money'],before['money']+200); self.assertEqual(self.a.stocks['food'],before['food'])
        self.w.execute(self.a,action('breach_exchange',exchange_id=deal['id'],reason='Оставляем чужой аванс и усиливаем собственную казну.'))
        self.assertEqual(self.a.stocks['money'],before['money']+200); self.assertEqual(self.a.stocks['food'],before['food']); self.assertEqual(deal['status'],'repudiated')
        self.assertLessEqual(self.w.relation(self.b.id,self.a.id)['trust'],-35); self.assertTrue(self.w.relation(self.b.id,self.a.id)['grievances'])
    def test_credit_buyer_can_keep_goods_and_refuse_payment(self):
        deal=self.exchange('credit'); before=dict(self.b.stocks); self.accept(deal); self.w.execute(self.b,action('breach_exchange',exchange_id=deal['id']))
        self.assertEqual(self.b.stocks['food'],before['food']+100); self.assertEqual(self.b.stocks['money'],before['money']); self.assertEqual(deal['owed'],dict(money=200))
    def test_unsecured_first_leg_requires_explicit_risk_acceptance(self):
        deal=self.exchange(); before=self.w.data(); self.assertRaises(RuleError,self.w.execute,self.b,action('accept_exchange',exchange_id=deal['id'])); self.assertEqual(before,self.w.data())
    def test_advance_can_be_offered_even_when_seller_does_not_have_the_promised_goods(self):
        self.a.stocks['food']=0; deal=self.exchange(); self.accept(deal); self.assertEqual(self.a.stocks['food'],0); self.assertEqual(deal['status'],'awaiting_delivery')
        self.assertRaises(RuleError,self.w.execute,self.a,action('deliver_exchange',exchange_id=deal['id']))
    def test_honest_completion_moves_real_resources_and_closes_only_once(self):
        deal=self.exchange(); self.accept(deal); self.w.execute(self.a,action('deliver_exchange',exchange_id=deal['id'])); before=self.w.data()
        self.assertEqual(deal['status'],'fulfilled'); self.assertEqual(len(deal['receipt_ids']),2); self.assertRaises(RuleError,self.w.execute,self.a,action('deliver_exchange',exchange_id=deal['id'])); self.assertEqual(before,self.w.data())
    def test_due_day_is_inclusive_default_is_once_and_does_not_force_a_refund(self):
        deal=self.exchange(); self.accept(deal); money=self.a.stocks['money']; food=self.a.stocks['food']; self.w.day=deal['due_day']; self.w.process_exchanges(); self.assertEqual(deal['status'],'awaiting_delivery')
        self.w.day+=1; self.w.process_exchanges(); trust=self.w.relation(self.b.id,self.a.id)['trust']; self.w.process_exchanges()
        self.assertEqual(deal['status'],'defaulted'); self.assertEqual(self.a.stocks['money'],money); self.assertEqual(self.a.stocks['food'],food); self.assertEqual(trust,self.w.relation(self.b.id,self.a.id)['trust'])
    def test_late_delivery_is_possible_but_does_not_erase_the_betrayal(self):
        deal=self.exchange(); self.accept(deal); self.w.execute(self.a,action('breach_exchange',exchange_id=deal['id'])); self.w.execute(self.a,action('deliver_exchange',exchange_id=deal['id']))
        self.assertEqual(deal['status'],'settled_late'); self.assertTrue(self.w.relation(self.b.id,self.a.id)['grievances']); self.assertLess(self.w.relation(self.b.id,self.a.id)['trust'],0)
    def test_wrong_party_cannot_fulfil_breach_or_accept_for_someone_else(self):
        deal=self.exchange()
        self.assertRaises(RuleError,self.w.execute,self.a,action('accept_exchange',exchange_id=deal['id'])); self.accept(deal)
        self.assertRaises(RuleError,self.w.execute,self.b,action('breach_exchange',exchange_id=deal['id'])); self.assertRaises(RuleError,self.w.execute,self.c,action('deliver_exchange',exchange_id=deal['id']))
    def test_cancel_offer_never_recovers_an_already_received_advance(self):
        deal=self.exchange(); self.accept(deal); before=self.w.data(); self.assertRaises(RuleError,self.w.execute,self.a,action('cancel_exchange',exchange_id=deal['id'])); self.assertEqual(before,self.w.data())
    def test_new_resources_and_overlapping_or_invalid_bundles_remain_gated(self):
        self.assertRaises(RuleError,self.w.execute,self.a,action('offer_exchange',partner=self.b.id,give=dict(weapons_i=10),receive=dict(money=50),mode='credit'))
        self.assertRaises(RuleError,self.exchange,'secure',dict(food=100),dict(food=50))
        self.assertRaises(RuleError,self.exchange,'secure',dict(food=-1),dict(money=50))


class CompilerTests(Fixture):
    def test_runner_saves_primary_before_economic_retry_and_does_not_reroll_personality(self):
        from main import Runner
        self.w.start_day(); base=self.decision(economic_review=dict(mode='execute',reason='Передаём металл ради политического преимущества и давления.',orders=[]))
        fixed=copy.deepcopy(base); fixed['economic_review']['orders']=[action('transfer',partner=self.b.id,resource='metal',amount=10)]; fixed=Brain({}).compile_economy(self.a,self.w.context(self.a),fixed)
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'world.sqlite3'); runner=Runner(self.w,store,dict(external_console=False,deep_strategy=False))
            with patch.object(runner.brain,'think',return_value=base) as think,patch.object(runner.brain,'review_construction',side_effect=lambda *a:a[-1]),patch.object(runner.brain,'review_economy',side_effect=[AutomaticRetry('Нужно уточнить казначейство'),fixed]):
                runner.work(); self.assertEqual(self.w.cursor,0); self.assertEqual(store.load().pending_decisions[self.a.id],base)
                runner.work(); self.assertEqual(self.w.cursor,1); self.assertEqual(think.call_count,1); self.assertEqual(self.w.pending_decisions[self.a.id]['notes'],base['notes'])
    def test_explicit_economic_orders_become_paid_actions_without_double_execution(self):
        order=action('transfer',partner=self.b.id,resource='metal',amount=20); result=self.decision(actions=[dict(type='transfer',args=dict(order['args'],cell=[1,1],reason='Прежняя причина'))],economic_review=dict(mode='execute',reason='Отправляем реальный металл для политического преимущества.',orders=[dict(type='transfer',args=dict(order['args'],reason='Переведённая новая причина',allow_risk=True))]))
        brain=Brain({}); compiled=brain.compile_economy(self.a,self.w.context(self.a),result); self.assertEqual(len(compiled['actions']),1); self.assertEqual(compiled,brain.compile_economy(self.a,self.w.context(self.a),compiled))
        before=self.b.stocks['metal']; self.w.apply_decision(self.a,compiled); self.assertEqual(self.b.stocks['metal'],before+20)
    def test_deliberate_bluff_is_not_automatically_turned_into_an_honest_transfer(self):
        result=self.decision(diplomacy=[dict(to=self.b.id,text='Мы уже отправили обещанное золото.')],economic_review=dict(mode='deceive',reason='Ничего не отправляем, используем ложь ради дипломатической уступки.',orders=[]))
        compiled=Brain({}).compile_economy(self.a,self.w.context(self.a),result); before=dict(self.a.stocks); self.w.apply_decision(self.a,compiled)
        self.assertEqual(self.a.stocks,before); self.assertEqual(self.w.settlements,[])
    def test_execute_without_order_and_wrong_buyer_are_rejected_before_model_is_marked_complete(self):
        result=self.decision(economic_review=dict(mode='execute',reason='Действительно переводим ресурсы прямо в этом общем ходе.',orders=[])); brain=Brain({}); self.assertRaises(ValueError,brain.compile_economy,self.a,self.w.context(self.a),result)
        self.offer(); result['economic_review']['orders']=[action('accept_trade',offer_id=1)]; self.assertRaises(ValueError,brain.compile_economy,self.a,self.w.context(self.a),result)
    def test_full_budget_never_silently_drops_an_existing_order(self):
        result=self.decision(actions=[action('do_nothing') for _ in range(12)],economic_review=dict(mode='execute',reason='Передать металл ради собственного экономического преимущества.',orders=[action('transfer',partner=self.b.id,resource='metal',amount=1)]))
        before=copy.deepcopy(result); self.assertRaises(ValueError,Brain({}).compile_economy,self.a,self.w.context(self.a),result); self.assertEqual(before,result)
    def test_only_missing_treasury_is_repaired_while_identity_letters_and_memory_stay_saved(self):
        order=action('transfer',partner=self.b.id,resource='metal',amount=1); result=self.decision(economic_review=dict(mode='execute',reason='Передать металл ради собственного экономического преимущества.',orders=[])); brain=Brain({})
        with patch.object(brain,'complete',return_value=dict(economic_review=dict(result['economic_review'],orders=[order]),actions=[])) as call:
            fixed=brain.review_economy(self.a,self.w.context(self.a),result)
        self.assertEqual(call.call_count,1); self.assertEqual(fixed['notes'],result['notes']); self.assertEqual(fixed['diplomacy'],result['diplomacy']); self.assertEqual(fixed['actions'],[order]); self.assertEqual(result['actions'],[])
    def test_old_prepared_decisions_are_not_rewritten_by_the_new_review(self):
        result=self.decision(); result['origin_patch']='6.0'; self.assertIs(Brain({}).review_economy(self.a,self.w.context(self.a),result),result)


class PrivacyAndSaveTests(Fixture):
    def test_old_settle_cannot_sneak_people_into_a_radioactive_site(self):
        p=next(p for p in self.w.positions(self.a.id) if not self.w.cell(p).population); self.w.cell(p).radiation=100
        before=self.w.data(); self.assertRaises(RuleError,self.w.execute,self.a,action('settle',cell=p,amount=1)); self.assertEqual(before,self.w.data())
    def test_radiation_harms_first_era_units_and_is_not_an_epoch_based_immunity(self):
        unit=next(u for u in self.w.units if u['owner']==self.a.id); self.w.cell(unit['cell']).radiation=100; before=unit['strength']; self.w.income()
        self.assertEqual(unit['strength'],round(before*.85,4))
    def test_tribute_is_real_and_receipted_but_does_not_falsely_complete_a_gift_promise(self):
        self.w.execute(self.b,action('pledge',partner=self.a.id,kind='delivery',resource='money',amount=200,duration=3))
        self.w.vassal_treaties=[dict(id=1,lord=self.a.id,subject=self.b.id,status='active',tribute_percent=20,until_day=self.w.day+10,paid_total=0)]
        before=self.a.stocks['money']; self.w.pay_tribute({self.b.id:1000})
        self.assertEqual(self.a.stocks['money'],before+200); self.assertEqual(self.w.settlements[-1]['kind'],'tribute'); self.assertEqual(self.w.pledges[0]['delivered'],0)
    def test_every_commerce_tab_renders_and_does_not_advance_or_mutate_the_world(self):
        import os
        os.environ.setdefault('SDL_VIDEODRIVER','dummy'); os.environ.setdefault('SDL_AUDIODRIVER','dummy')
        import pygame as pg
        from planet.industry_window import IndustryView
        from main import App
        deal=self.exchange(); self.accept(deal); self.w.execute(self.a,action('breach_exchange',exchange_id=1)); before=self.w.data()
        view=IndustryView(self.w,self.a.id); view.tab=5; view.draw()
        with tempfile.TemporaryDirectory() as temp:
            app=App(self.w,Store(Path(temp)/'view.sqlite3'),dict(external_console=False)); app.tab=3; app.draw()
        self.assertEqual(self.w.data(),before); pg.quit()
    def test_receipts_hide_counterparty_balances_and_private_exchange_motives(self):
        self.w.execute(self.a,action('offer_exchange',partner=self.b.id,give=dict(food=100),receive=dict(money=200),mode='advance',reason='PRIVATE_SCAM_INTENT'))
        self.accept(self.w.exchanges[0]); a=checked_context(self.a,self.w.context(self.a)); b=checked_context(self.b,self.w.context(self.b)); c=checked_context(self.c,self.w.context(self.c))
        self.assertIn('PRIVATE_SCAM_INTENT',json.dumps(a)); self.assertNotIn('PRIVATE_SCAM_INTENT',json.dumps(b)); self.assertEqual(c['commerce']['receipts'],[]); self.assertEqual(c['commerce']['exchanges'],[])
        self.assertEqual(set(b['commerce']['receipts'][0]['balances']),{self.b.id})
    def test_all_new_balances_statuses_and_receipt_ids_survive_exact_roundtrip(self):
        deal=self.exchange(); self.accept(deal); self.w.execute(self.a,action('breach_exchange',exchange_id=1)); before=self.w.data()
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'world.sqlite3',export=True); store.save(self.w); loaded=store.load()
            self.assertEqual(loaded.data(),before); self.assertEqual(json.loads((Path(temp)/'exchanges.json').read_text(encoding='utf-8')),before['exchanges']); self.assertTrue((Path(temp)/'settlements.jsonl').is_file())
    def test_six_zero_snapshot_adds_defaults_without_replaying_old_trade(self):
        self.offer(); self.w.execute(self.b,action('accept_trade',offer_id=1)); data=self.w.data(); data['patch']='6.0'
        for key in ('exchanges','next_exchange','settlements','next_receipt'): data.pop(key)
        for s in data['states']: s.pop('economic_review')
        loaded=World.restore(data); self.assertEqual(loaded.trade_offers,data['trade_offers']); self.assertEqual(loaded.states[0].stocks,data['states'][0]['stocks']); self.assertEqual(loaded.settlements,[])


class DeliberateDefaultTests(Fixture):
    def setUp(self):
        super().setUp()
        from planet.modern_catalog import MODERN_RESOURCES
        for s in (self.a,self.b): s.tech.append('industrialization'); s.era=2; s.modern=dict(entered_day=0,unrest=0,debt=0); s.stocks.update(dict.fromkeys(MODERN_RESOURCES,10000))
        self.w.execute(self.a,action('supply_pact',partner=self.b.id,resource='fuel',amount=100,price=10,duration=3,penalty=500)); self.pact=self.w.supply_pacts[0]
        self.w.execute(self.b,action('accept_supply',pact_id=1,allow_risk=True,reason='Осознанно создаём снабжение и принимаем договорный риск.'))
    def test_seller_can_deliberately_stop_delivery_even_with_available_stock(self):
        self.w.execute(self.a,action('withhold_supply',pact_id=1,duration=1)); self.w.day+=1; before=self.b.stocks['fuel']; self.w.process_supply()
        self.assertEqual(self.pact['last_delivery']['amount'],0); self.assertEqual(self.b.stocks['fuel'],before); self.assertEqual(self.pact['defaults'],1)
        self.assertTrue(self.a.stocks['fuel']>=100); self.w.execute(self.a,action('resume_supply',pact_id=1)); self.w.day+=1; self.w.process_supply(); self.assertEqual(self.pact['last_delivery']['amount'],100)
    def test_buyer_can_stop_payment_and_primary_responsibility_is_the_buyers(self):
        self.w.execute(self.b,action('withhold_supply',pact_id=1,duration=1)); money=self.b.stocks['money']; self.w.day+=1; self.w.process_supply()
        self.assertEqual(self.pact['last_delivery']['amount'],0); self.assertEqual(self.b.stocks['money'],money-500); self.assertTrue(any(f['kind']=='supply_default' for f in self.w.relation(self.a.id,self.b.id)['facts']))
    def test_unannounced_foreign_withholding_is_not_leaked_by_context_or_forecast(self):
        before=self.w.economic_forecast(self.b)['resources']['fuel']['signed_pact_net']; self.w.execute(self.a,action('withhold_supply',pact_id=1,duration=3))
        context=checked_context(self.b,self.w.context(self.b)); self.assertNotIn('withheld',context['modern']['supply_pacts'][0]); self.assertEqual(context['economy']['resources']['fuel']['signed_pact_net'],before)
        own=self.w.economic_forecast(self.a); self.assertEqual(own['resources']['fuel']['signed_pact_net'],0)
    def test_contract_debt_can_be_repudiated_without_erasing_it_or_auto_spending_again(self):
        self.a.stocks.update(money=0,fuel=0); self.w.day+=1; self.w.process_supply(); self.w.execute(self.a,action('cancel_supply',pact_id=1)); self.a.stocks['money']=1000
        self.w.execute(self.a,action('repudiate_debt',partner=self.b.id,pact_id=1)); debt=sum(c['amount'] for c in self.a.modern['claims']); self.w.day+=1; self.w.process_supply()
        self.assertEqual(self.a.stocks['money'],1000); self.assertEqual(sum(c['amount'] for c in self.a.modern['claims']),debt); self.assertTrue(all(c['repudiated'] for c in self.a.modern['claims']))
    def test_daily_pact_deliveries_have_receipts_and_never_double_close_a_promise(self):
        self.w.day+=1; self.w.process_supply(); self.w.process_supply(); self.assertEqual(len(self.w.settlements),2); self.assertEqual(self.pact['last_delivery']['receipt_ids'],[1,2])
    def test_forecast_does_not_read_the_other_countrys_hidden_cash_balance(self):
        before=self.w.economic_forecast(self.a)['resources']['money']['signed_pact_net']; self.b.stocks['money']=0
        self.assertEqual(self.w.economic_forecast(self.a)['resources']['money']['signed_pact_net'],before)


if __name__=='__main__': unittest.main()
