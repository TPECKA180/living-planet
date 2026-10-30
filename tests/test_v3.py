import copy
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch,MagicMock

from main import Runner
from planet.brain import Brain,AutomaticRetry,RULES,context_error
from planet.context import estimate
from planet.console_feed import ConsoleFeed
from planet.console_monitor import clean
from planet.engine import Store,World


def answer():
    return dict(thinking='Укрепляем влияние',notes='Публично дружелюбны, преследуем свою выгоду',plan='Выгодные переговоры',
                diplomacy=[dict(to='all',text='Предлагаем обсудить наши условия')],actions=[dict(type='do_nothing',args={})])


class RecoveryTests(unittest.TestCase):
    def test_single_huge_note_is_compacted_without_changing_saved_memory(self):
        context=dict(state='state_1',day=5,stocks=dict(money=500),notes='Характер и тайный замысел. '+'Ж'*500000,plan='П'*200000,
                     history=[dict(text='О'*200000)],messages=[dict(text='Сообщение '*100000)])
        before=copy.deepcopy(context)
        fitted=Brain(dict(max_tokens=4096)).fit_context(RULES,context,16384)
        self.assertEqual(context,before)
        self.assertLessEqual(fitted['context_info']['estimated_input_tokens'],16384-4096-1024)
        self.assertEqual(fitted['stocks'],context['stocks'])

    def test_actual_http_overflow_retries_shorter_and_streams_reasoning(self):
        requests=[]; events=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                if len(requests)==1:
                    self.send_response(400); self.send_header('Content-Type','application/json'); self.end_headers()
                    self.wfile.write(b'{"error":{"message":"context length exceeded"}}'); return
                self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
                chunks=[dict(choices=[dict(delta=dict(reasoning_content='Фрагмент от тестовой модели'),finish_reason=None)])]
                result=json.dumps(answer(),ensure_ascii=False)
                for i in range(0,len(result),37): chunks.append(dict(choices=[dict(delta=dict(content=result[i:i+37]),finish_reason=None)]))
                chunks.append(dict(choices=[dict(delta={},finish_reason='stop')]))
                chunks.append(dict(choices=[],usage=dict(prompt_tokens=100,completion_tokens=50)))
                for chunk in chunks:
                    self.wfile.write(('data: '+json.dumps(chunk,ensure_ascii=False)+'\n\n').encode()); self.wfile.flush()
                self.wfile.write(b'data: [DONE]\n\n')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            brain=Brain(dict(host=f'http://127.0.0.1:{server.server_port}/v1',model='test',context_window=32768,max_tokens=4096),observer=lambda kind,text='',**data:events.append((kind,text)))
            context=dict(notes='Память',plan='Переговоры',map=[[i,'x'*200] for i in range(2000)])
            result=brain.complete(RULES,context,'test')
            self.assertEqual(result,answer()); self.assertEqual(len(requests),2)
            size=lambda request:sum(len(m['content'].encode('utf-8')) for m in request['messages'])
            self.assertLess(size(requests[1]),size(requests[0]))
            self.assertTrue(requests[1]['stream'])
            self.assertIn(('reasoning','Фрагмент от тестовой модели'),events)
            self.assertEqual(''.join(text for kind,text in events if kind=='content'),json.dumps(answer(),ensure_ascii=False))
        finally: server.shutdown(); server.server_close()

    def test_persistent_overflow_retains_turn_and_uses_retry_status(self):
        with tempfile.TemporaryDirectory() as temp:
            world=World(size=24,count=2); runner=Runner(world,Store(Path(temp)/'world.db'),{})
            with patch.object(runner.brain,'think',side_effect=AutomaticRetry('Контекст сокращается')):
                runner.work(); stocks=copy.deepcopy(world.states[0].stocks); runner.work()
            kinds=[]
            while not runner.messages.empty(): kinds.append(runner.messages.get()[0])
            self.assertIn('retry',kinds); self.assertNotIn('error',kinds)
            self.assertEqual(world.cursor,0); self.assertEqual(world.day,1); self.assertEqual(world.states[0].stocks,stocks)

    def test_repeated_context_errors_remain_recoverable(self):
        brain=Brain(dict(model='test',context_window=32768,context_retry_attempts=2,stream=False))
        with patch.object(brain,'request',side_effect=RuntimeError('context window exceeded')):
            with self.assertRaises(AutomaticRetry): brain.complete(RULES,dict(notes='Память'),'test')
        self.assertLess(brain.context_limits['test'],32768)

    def test_cut_off_generation_retries_with_more_output_and_does_not_apply_partial_json(self):
        brain=Brain(dict(model='test',context_window=98304,max_tokens=8192,stream=False))
        payloads=[]
        def request(path,payload):
            payloads.append(payload)
            if len(payloads)==1: return dict(choices=[dict(message=dict(content='{"thinking":'),finish_reason='length')])
            return dict(choices=[dict(message=dict(content=json.dumps(answer(),ensure_ascii=False)),finish_reason='stop')])
        with patch.object(brain,'request',side_effect=request): result=brain.complete(RULES,dict(notes='Память'),'test')
        self.assertEqual(result,answer()); self.assertEqual(payloads[1]['max_tokens'],16384)

    def test_non_context_http_error_is_not_misreported_as_overflow(self):
        self.assertFalse(context_error('HTTP 401 Unauthorized'))
        self.assertTrue(context_error('Requested tokens exceed context length'))
        self.assertTrue(context_error('Cannot truncate prompt with n_keep >= n_ctx'))

    def test_minimal_context_uses_short_rules_and_fits_total_budget(self):
        brain=Brain(dict(model='test',context_window=2048,max_tokens=8192,stream=False))
        payloads=[]
        def request(path,payload):
            payloads.append(payload)
            return dict(choices=[dict(message=dict(content=json.dumps(answer(),ensure_ascii=False)),finish_reason='stop')])
        world=World(size=24,count=2)
        # 6.8.4 refuses to erase the actual decision data to fit an unusable window.
        with patch.object(brain,'request',side_effect=request):
            with self.assertRaises(AutomaticRetry):brain.complete(RULES,world.context(world.states[0]),'test')
        self.assertEqual(payloads,[])


class LanguageTests(unittest.TestCase):
    def test_translation_changes_only_prose(self):
        value=answer(); value['notes']='We conceal our intentions and seek advantage.'
        value['diplomacy'][0]['text']='We offer you a mutually beneficial agreement.'
        original=copy.deepcopy(value)
        brain=Brain({})
        translation={'notes':'Скрываем намерения и ищем выгоду.','diplomacy.0.text':'Предлагаем вам взаимовыгодное соглашение.'}
        with patch.object(brain,'complete',return_value=translation): result=brain.russify(value,'test')
        self.assertEqual(value,original); self.assertEqual(result['actions'],original['actions'])
        self.assertEqual(result['notes'],translation['notes']); self.assertEqual(result['diplomacy'][0]['to'],'all')

    def test_russian_with_technical_identifiers_needs_no_translation(self):
        self.assertTrue(Brain.russian('Изучаем navigation, строим lab и говорим со state_2.'))
        self.assertFalse(Brain.russian('We should expand our influence and make a deal.'))
        self.assertFalse(Brain.russian('Мы развиваем страну. We will propose a treaty.'))

    def test_failed_translation_is_automatic_retry(self):
        value=answer(); value['thinking']='We need to make a deal with our neighbors.'
        brain=Brain({})
        with patch.object(brain,'complete',return_value={'thinking':'We need a better deal.'}):
            with self.assertRaises(AutomaticRetry): brain.russify(value,'test')


class ConsoleTests(unittest.TestCase):
    def test_console_is_separate_and_chunks_are_saved(self):
        import os
        if os.name!='nt': self.skipTest('Windows console creation flags')
        with tempfile.TemporaryDirectory() as temp:
            process=MagicMock(); process.poll.return_value=None
            with patch('planet.console_feed.subprocess.Popen',return_value=process) as spawn:
                feed=ConsoleFeed(temp); feed.emit('progress',completed=0,total=4,day=1)
                feed.emit('reasoning','Полученный фрагмент'); feed.emit('content','Ответ'); feed.close()
                self.assertEqual(spawn.call_count,1)
                self.assertEqual(spawn.call_args.kwargs['creationflags'],__import__('subprocess').CREATE_NEW_CONSOLE)
            items=[json.loads(line) for line in (Path(temp)/'llm_stream.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual([item['kind'] for item in items],['progress','reasoning','content','close'])

    def test_model_output_cannot_inject_terminal_control_commands(self):
        self.assertEqual(clean('\x1b[2JТекст\x00\n'), 'Текст\n')


if __name__=='__main__': unittest.main()
