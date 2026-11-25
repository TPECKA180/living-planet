import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import Runner
from planet.brain import Brain
from planet.console_feed import ConsoleFeed
from planet.engine import Store, World
from planet.local_model import parse_runtime_rate
from planet.runtime_config import upgrade_config


class LiveStreamTests(unittest.TestCase):
    def test_sse_fragments_are_emitted_before_the_response_finishes(self):
        events = []
        thought = ''.join(f'наблюдение-{index:03d} ' for index in range(60))
        frames = [
            {'choices': [{'delta': {'reasoning_content': thought}}]},
            {'choices': [{'delta': {'content': '{"ok":true}'}}]},
            {'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 50, 'completion_tokens': 8}},
        ]
        raw = b''.join(b'data: ' + json.dumps(frame, ensure_ascii=False).encode('utf-8') + b'\n\n' for frame in frames)

        class StreamingResponse(io.BytesIO):
            headers = {'Content-Type': 'text/event-stream'}

        brain = Brain(dict(host='http://127.0.0.1:32124/v1', stream=True, response_max_bytes=100000),
                      observer=lambda kind, text='', **data: events.append((kind, text)))
        with patch('urllib.request.urlopen', return_value=StreamingResponse(raw)):
            response = brain.stream_request(dict(model='fixture'))

        self.assertEqual(response['choices'][0]['message']['content'], '{"ok":true}')
        reasoning = [text for kind, text in events if kind == 'reasoning']
        self.assertGreaterEqual(len(reasoning), 1)
        self.assertEqual(''.join(reasoning), thought)
        self.assertIn(('content', '{"ok":true}'), events)

    def test_llama_log_reports_live_prompt_and_generation_rates(self):
        self.assertEqual(parse_runtime_rate('prompt processing, n_tokens = 2049, progress = 0.27, t = 12.69 s / 161.50 tokens per second'), ('read', 161.5))
        self.assertEqual(parse_runtime_rate('n_gen = 514, tg = 34.04 t/s, tg_3s = 34.11 t/s'), ('generate', 34.04))
        self.assertEqual(parse_runtime_rate('prompt eval time = 493262.98 ms / 54841 tokens (8.99 ms per token, 111.18 tokens per second)'), ('read', 111.18))
        self.assertIsNone(parse_runtime_rate('server is ready'))

    def test_853_config_migration_turns_streaming_on_once(self):
        config = dict(runtime_patch='8.5.3', stream=False, context_window=262144,
                      input_tokens=72000, max_tokens=56000, model='private.gguf')
        self.assertTrue(upgrade_config(config))
        self.assertEqual(config['runtime_patch'], '8.5.4')
        self.assertTrue(config['stream'])
        self.assertEqual(config['model'], 'private.gguf')
        self.assertEqual(config['context_window'], 262144)
        self.assertEqual(config['input_tokens'], 72000)
        self.assertFalse(upgrade_config(config))

    def test_prompt_and_generation_rates_are_reported_separately(self):
        events = []
        brain = Brain(dict(model='fixture', stream=True, context_window=262144,
                           input_tokens=24000, max_tokens=1024),
                      observer=lambda kind, text='', **data: events.append((kind, data)))
        response = dict(choices=[dict(message=dict(content='{"ok":true}'), finish_reason='stop')],
                        usage=dict(prompt_tokens=120, completion_tokens=40),
                        prompt_seconds=3, generation_seconds=2)
        with patch.object(brain, 'prepare_model', return_value=('fixture', 262144)), \
                patch.object(brain, 'stream_request', return_value=response):
            self.assertEqual(brain.complete('JSON', {}, 'fixture'), {'ok': True})
        metrics = next(data for kind, data in events if kind == 'request_end')
        self.assertEqual(metrics['prompt_tokens_per_second'], 40)
        self.assertEqual(metrics['tokens_per_second'], 20)

    def test_runner_forwards_stream_fragments_to_the_game_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            runner = Runner(World(size=24, count=2), Store(Path(folder) / 'world.sqlite3'),
                            dict(external_console=False))
            runner.observe('request_start', 'День 4 · Аврора', estimated_input=1200)
            runner.observe('reasoning', 'Думаю о границах. ')
            runner.observe('content', '{"actions":[]}')
            runner.observe('request_end', 'done', tokens_per_second=32, prompt_tokens_per_second=110)
            self.assertEqual(runner.messages.get_nowait()[0], 'stream_start')
            self.assertEqual(runner.messages.get_nowait(), ('stream_delta', ('reasoning', 'Думаю о границах. ')))
            self.assertEqual(runner.messages.get_nowait(), ('stream_delta', ('content', '{"actions":[]}')))
            self.assertEqual(runner.messages.get_nowait(), ('speed', (32, 110)))

    def test_console_fragment_is_flushed_without_waiting_for_request_end(self):
        with tempfile.TemporaryDirectory() as folder:
            feed = ConsoleFeed(folder, enabled=True)
            feed.emit('reasoning', 'Живой фрагмент.')
            row = json.loads((Path(folder) / 'llm_stream.jsonl').read_text(encoding='utf-8'))
            self.assertEqual((row['kind'], row['text']), ('reasoning', 'Живой фрагмент.'))
            feed.close()


if __name__ == '__main__':
    unittest.main()
