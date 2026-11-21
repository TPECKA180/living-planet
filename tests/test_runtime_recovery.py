"""Regression checks for bounded Runner recovery without a live server."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import App, Runner
from planet.brain import AutomaticRetry, Brain
from planet.engine import Store, World


class RuntimeRecoveryTests(unittest.TestCase):
    def runner(self, folder):
        return Runner(World(size=24,count=2,seed=2026),
                      Store(Path(folder)/'world.sqlite3'),
                      dict(external_console=False,local_execution=True,model='test'))

    def test_persistent_errors_stop_after_three_attempts_and_keep_world(self):
        for error in (RuntimeError('LM Studio HTTP 401'),AutomaticRetry('invalid JSON')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as folder:
                runner=self.runner(folder)
                with patch.object(runner.brain,'think',side_effect=error):
                    runner.work();first=runner.world.data()
                    runner.work();runner.work()
                messages=list(runner.messages.queue)
                self.assertEqual(sum(k=='retry' for k,_ in messages),2)
                self.assertEqual(sum(k=='error' for k,_ in messages),1)
                self.assertEqual(runner.world.data(),first)
                self.assertEqual(runner.store.load().data(),first)

    def test_success_resets_consecutive_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            runner=self.runner(folder)
            with patch.object(runner.brain,'think',side_effect=RuntimeError('offline')):
                runner.work();runner.work()
            state=runner.world.states[0]
            decision=dict(thinking='Проверка',notes=state.notes,plan=state.plan,diplomacy=[],actions=[])
            with patch.object(runner.brain,'think',return_value=decision):runner.work()
            self.assertEqual(runner.retry_count,0)
            self.assertEqual(runner.world.cursor,1)
            self.assertIn(state.id,runner.world.pending_decisions)

    def test_manual_resume_resets_retry_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            runner=self.runner(folder);runner.retry_count=3
            view=App.__new__(App);view.runner=runner;view.world=runner.world
            view.config=runner.config;view.running=False;view.retry_after=999;view.error='old error'
            view.action('run')
            self.assertEqual(runner.retry_count,0);self.assertEqual(view.retry_after,0)
            self.assertTrue(view.running);self.assertEqual(view.error,'')

    def test_output_diagnostics_preserve_legacy_fields_and_label_estimate(self):
        events=[];brain=Brain(dict(model='m',stream=False,context_window=262144),
                            observer=lambda kind,text='',**data:events.append((kind,data)))
        with patch.object(brain,'request',return_value=dict(choices=[dict(message=dict(content='{}'),finish_reason='stop')])):
            brain.complete('JSON',{},'m')
        row=next(data for kind,data in events if kind=='request_start')
        self.assertEqual(row['actual_output'],row['requested_output'])
        self.assertEqual(row['estimated_remaining_tokens'],max(0,row['window']-row['estimated_input']-2048))
