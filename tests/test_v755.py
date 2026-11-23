import copy,json,unittest
from unittest.mock import patch
from planet.brain import AutomaticRetry,Brain,RULES
from planet.context import ContextCapacityError
from planet.generation_recovery import GenerationStalled
from planet.runtime_config import upgrade_config
from planet.context import fit


def answer(text='{"ok":true}',finish='stop'):
    return dict(choices=[dict(message=dict(content=text),finish_reason=finish)])


class OutputCeilingTests(unittest.TestCase):
    def test_server_validates_conservative_overflow_without_losing_current_facts(self):
        source=dict(stocks={'money':1},military={'current_forces':'X'*200000})
        with self.assertRaises(ContextCapacityError):fit('rules',source,100000,0)
        packed=fit('rules',source,100000,0,allow_estimated_overflow=True)
        self.assertEqual(packed['military'],source['military']);self.assertGreater(packed['context_info']['estimated_overflow_tokens'],0)

    def test_mandatory_prompt_may_exceed_target_inside_actual_window(self):
        brain=Brain(dict(input_tokens=72000,context_window=262144,max_tokens=56000))
        packed=dict(context_info=dict(estimated_input_tokens=95917,trimmed={}))
        with patch('planet.brain.fit',side_effect=[ContextCapacityError('target exceeded',95917,95106),packed]) as pack:
            result=brain.fit_context('rules',{'decision':'mandatory'},262144,0,input_budget=72000)
        self.assertEqual(result['context_info']['input_budget_spill_tokens'],811)
        self.assertTrue(result['context_info']['expanded_for_actionable_data'])
        self.assertTrue(pack.call_args.kwargs['allow_estimated_overflow'])

    def test_real_server_rejection_of_estimated_overflow_regenerates_smaller_window(self):
        brain=Brain(dict(model='m',stream=True,context_window=110755,max_tokens=196608,context_retry_attempts=3))
        packed=dict(context_info=dict(estimated_input_tokens=111000,trimmed={},estimated_overflow_tokens=1000))
        with patch.object(brain,'fit_context',return_value=packed),patch.object(brain,'stream_request',side_effect=RuntimeError('context length exceeded')) as send:
            with self.assertRaises(AutomaticRetry):brain.complete('JSON',{},'m')
        self.assertEqual(send.call_count,3);self.assertLess(brain.context_limits['m'],110755)
    def test_ceiling_is_sent_without_preallocating_or_halving_input(self):
        config=dict(model='m',stream=True,context_window=110755,input_tokens=56000,max_tokens=196608)
        before=copy.deepcopy(config);brain=Brain(config);brain.capacity_signature=('unused',)
        calls=[]
        def send(payload):calls.append(payload);return answer()
        with patch.object(brain,'stream_request',side_effect=send):
            self.assertEqual(brain.complete(RULES,dict(stocks={'money':123},notes='Память. '*1000),'m'),{'ok':True})
        self.assertEqual(len(calls),1);self.assertLessEqual(calls[0]['max_tokens'],110755)
        self.assertEqual(config,before)
        facts=json.loads(calls[0]['messages'][1]['content'])
        self.assertEqual(facts['stocks'],{'money':123});self.assertEqual(facts['context_info']['requested_user_input_tokens'],56000)
        self.assertEqual(facts['context_info']['server_output_limit'],calls[0]['max_tokens'])

    def test_old_small_cached_reserve_does_not_constrain_next_request(self):
        brain=Brain(dict(model='m',stream=True,context_window=110755,max_tokens=196608,input_tokens=56000));calls=[]
        with patch.object(brain,'stream_request',side_effect=lambda p:(calls.append(p) or answer())):
            brain.complete('JSON',{},'m');brain.response_limits['m']=1961;brain.complete('JSON',{},'m')
        self.assertEqual(len(calls),2);self.assertTrue(all(0<x['max_tokens']<=110755 for x in calls))

    def test_complete_length_labelled_json_still_gets_normal_validation(self):
        brain=Brain(dict(model='m',stream=True,context_window=110755,max_tokens=196608))
        with patch.object(brain,'stream_request',return_value=answer(finish='length')) as send:
            self.assertEqual(brain.complete('JSON',{},'m'),{'ok':True})
        self.assertEqual(send.call_count,1)

    def test_incomplete_length_is_not_regenerated_forever(self):
        brain=Brain(dict(model='m',stream=True,context_window=110755,max_tokens=196608))
        with patch.object(brain,'stream_request',return_value=answer('{"actions":[','length')) as send:
            with self.assertRaises(GenerationStalled):brain.complete('JSON',{},'m')
        self.assertEqual(send.call_count,2);self.assertNotIn('m',brain.response_limits)

    def test_input_capacity_failure_never_halves_output(self):
        brain=Brain(dict(model='m',stream=True,context_window=110755,max_tokens=196608))
        with patch.object(brain,'fit_context',side_effect=ContextCapacityError('mandatory current facts')) as fit,patch.object(brain,'stream_request') as send:
            with self.assertRaises(GenerationStalled):brain.complete('JSON',{},'m')
        self.assertEqual(fit.call_count,1);send.assert_not_called();self.assertFalse(brain.response_limits)

    def test_minimum_ceiling_and_migration_leave_input_and_sampling_unchanged(self):
        cfg=dict(runtime_patch='7.5.4',max_tokens=3922,input_tokens=56000,context_window=262144,temperature=.7,model='m',stream=True)
        before=copy.deepcopy(cfg);upgrade_config(cfg)
        self.assertEqual(cfg['max_tokens'],110000)
        for k in before:
            if k not in ('runtime_patch','max_tokens','input_tokens','context_window','host','manage_model_context','strict_state_isolation','api_key'):self.assertEqual(cfg[k],before[k])
        self.assertEqual(cfg['input_tokens'],12000);self.assertEqual(cfg['context_window'],262144);self.assertEqual(cfg['host'],'http://127.0.0.1:32124/v1')
        brain=Brain(cfg)
        with patch.object(brain,'stream_request',return_value=answer()) as send:brain.complete('JSON',{},'m')
        self.assertLessEqual(send.call_args.args[0]['max_tokens'],cfg['context_window'])
