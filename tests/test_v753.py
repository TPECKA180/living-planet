import copy,json,unittest
from unittest.mock import patch
from planet.brain import Brain,AutomaticRetry
from planet.intelligence import RepeatedOutput
from planet.generation_recovery import GenerationStalled,unfinished_field
from planet.runtime_config import upgrade_config


class RecoveryTests(unittest.TestCase):
    def test_unfinished_top_level_field_handles_nested_and_escaped_values(self):
        self.assertEqual(unfinished_field('{"thinking":"ok", "learning_review":{"hypothesis":"loop'), 'learning_review')
        self.assertEqual(unfinished_field('{"thinking":"a \\" quote", "actions":[{"type":"hold"}],"learning_notes":"loop'), 'learning_notes')
        self.assertIsNone(unfinished_field('{"ok":true}'))

    def test_repeated_learning_keeps_existing_state_and_original_budgets(self):
        config=dict(model='m',stream=True,input_tokens=56000,max_tokens=196608,context_window=262144)
        brain=Brain(config);before=copy.deepcopy(config);calls=[]
        schema=dict(type='json_schema',json_schema=dict(name='test',schema=dict(type='object',properties=dict(learning_review=dict(type=['object','null']),thinking=dict(type='string')))))
        ctx=dict(stocks={'money':123},learning={'notes':'original memory','active_experiment':{'baseline':123}},_response_schema=schema)
        def send(payload):
            calls.append(copy.deepcopy(payload))
            if len(calls)==1:
                e=RepeatedOutput('NEVER_ECHO_THIS_LOOP'*100);e.field='learning_review';raise e
            return dict(choices=[dict(message=dict(content='{"learning_review":null,"thinking":"готово"}'),finish_reason='stop')])
        with patch.object(brain,'stream_request',side_effect=send):result=brain.complete('JSON',ctx,'m')
        self.assertIsNone(result['learning_review']);self.assertEqual(config,before)
        self.assertEqual(calls[0]['max_tokens'],calls[1]['max_tokens'])
        self.assertEqual(calls[1]['response_format']['json_schema']['schema']['properties']['learning_review'],{'type':'null'})
        self.assertNotIn('NEVER_ECHO_THIS_LOOP',json.dumps(calls[1]))
        self.assertEqual(json.loads(calls[0]['messages'][1]['content'])['learning'],json.loads(calls[1]['messages'][1]['content'])['learning'])
        self.assertNotEqual(schema['json_schema']['schema']['properties']['learning_review'],{'type':'null'})

    def test_persistent_repetition_is_terminal_without_unbounded_outer_retry(self):
        brain=Brain(dict(model='m',stream=True,context_window=262144,context_retry_attempts=2))
        with patch.object(brain,'stream_request',side_effect=RepeatedOutput('loop')) as send:
            with self.assertRaises(GenerationStalled):brain.complete('JSON',{},'m')
        self.assertEqual(send.call_count,2)
        self.assertFalse(issubclass(GenerationStalled,(AutomaticRetry,RuntimeError,ValueError)))

    def test_recent_config_migration_changes_only_patch(self):
        for v in ('7.5.1','7.5.2','7.5.3'):
            cfg=dict(runtime_patch=v,input_tokens=56000,max_tokens=196608,context_window=262144,temperature=.7)
            old=copy.deepcopy(cfg);upgrade_config(cfg);old['runtime_patch']='7.5.6';self.assertEqual(cfg,old)
