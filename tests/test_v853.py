import copy
import unittest
from unittest.mock import patch

from planet.brain import Brain, COMPACT_RULES, RULES
from planet.context import age_compress, fit


class AgeCompressionTests(unittest.TestCase):
    def test_compact_rules_are_the_rules_actually_sent_to_model(self):
        brain = Brain(dict(compact_prompt=True, context_window=262144, input_tokens=24000, max_tokens=1024))
        response = dict(choices=[dict(message=dict(content='{"ok":true}'), finish_reason='stop')])
        with patch.object(brain, 'prepare_model', return_value=('model', 262144)), \
                patch.object(brain, 'stream_request', return_value=response) as send:
            self.assertEqual(brain.complete(RULES, {}, 'model'), {'ok': True})

        self.assertEqual(send.call_args.args[0]['messages'][0]['content'], COMPACT_RULES)

    def test_old_letters_and_thoughts_are_summarized_recent_records_stay_verbatim(self):
        recent_letter = dict(day=95, sender='state_2', recipient='state_1', text='Свежие условия сделки.')
        recent_memory = dict(day=95, thinking='Текущая мысль.', notes='Текущие заметки.', plan='Текущий план.')
        letters = [dict(day=day, sender='state_2', recipient='state_1', text=f'Предложение {day}. ' * 30)
                   for day in range(1, 85)] + [recent_letter]
        memories = [dict(day=day, owner='state_1', thinking=f'Размышление {day}. ' * 20,
                         notes=f'Наблюдение {day}.', plan=f'План {day}.') for day in range(1, 85)] + [recent_memory]
        source = dict(day=95, messages=letters, memory=memories)
        before = copy.deepcopy(source)

        fitted = fit('Короткие правила.', source, 262144, 0)

        self.assertEqual(source, before)
        self.assertIn(recent_letter, fitted['messages'])
        self.assertIn(recent_memory, fitted['memory'])
        old_letter = next(row for row in fitted['messages'] if row.get('compressed'))
        self.assertEqual(old_letter['records'], 84)
        old_thought = next(row for row in fitted['memory'] if row.get('compressed'))
        self.assertIn('thinking', old_thought)
        self.assertIn('Размышление', old_thought['thinking'])
        self.assertIn('notes', old_thought)
        self.assertIn('plan', old_thought)

    def test_ten_day_boundary_keeps_exact_cutoff_day(self):
        rows = [dict(day=89, text='Старое'), dict(day=90, text='На границе'), dict(day=95, text='Сегодня')]
        result = age_compress(rows, day=100, retention=10)
        self.assertEqual([row['day'] for row in result if not row.get('compressed')], [90, 95])
        self.assertIn('Старое', result[0]['text'])

    def test_old_history_and_events_are_grouped_without_changing_source(self):
        history = [dict(day=day, owner='state_1', text=f'Событие {day}.') for day in range(1, 85)]
        events = [dict(day=day, kind='world', title=f'Глава {day}', description='Подробное описание. '*30)
                  for day in range(1, 85)]
        source = dict(day=95, history=history, events=events)
        before = copy.deepcopy(source)

        fitted = fit('Короткие правила.', source, 262144, 0)

        self.assertEqual(source, before)
        self.assertEqual(next(row for row in fitted['history'] if row.get('compressed'))['records'], 84)
        self.assertEqual(next(row for row in fitted['events'] if row.get('compressed'))['records'], 84)


if __name__ == '__main__':
    unittest.main()
