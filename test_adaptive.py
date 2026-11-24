import asyncio
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

import council
from adaptive import State, classify, classify_http, lifecycle, score, sensitive
from test_council import model


class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.db = self.root/'usage.sqlite3'
        self.route = dict(provider='openrouter', model='a/x:free', family='a', daily_cap=8)
        self.cfg = {'providers': {'openrouter': {'confirmed_unbilled_free_account': True,
                     'checked_on': date.today().isoformat(), 'daily_cap': 8}}}

    def test_migrate_and_count_existing_requests(self):
        self.assertTrue(council.reserve(self.db, 'openrouter', 8))
        state = State(self.db)
        self.assertEqual(state.remaining(4), 3)
        self.assertIsNotNone(state.claim(self.route, 50, 'answer', 4, 100)[0])
        self.assertEqual(State(self.db).claim(self.route, 51, 'answer', 4, 100)[1], 'global local quota')
        state.refresh([self.route], {'openrouter/a/x:free': {'ok': 5, 'error': 1}})
        state.refresh([], {'openrouter/a/x:free': {'ok': 0, 'error': 5}})
        self.assertGreater(state.metrics()['openrouter/a/x:free'][0], 2)

    def test_parallel_reservations(self):
        state = State(self.db)
        with ThreadPoolExecutor(max_workers=8) as pool:
            reservations = list(pool.map(lambda _: state.claim(self.route, 100, 'answer', 3, 300), range(12)))
        self.assertEqual(sum(reservation is not None for reservation, _ in reservations), 3)

    def test_circuits_and_half_open_lease(self):
        state = State(self.db)
        other = dict(self.route, model='b/x:free')
        with patch('adaptive.time.time', return_value=200000) as clock:
            claim, _ = state.claim(self.route, 50, 'answer', 10, 1000)
            state.finish(claim, self.route, {'status': 'error'}, ('model', 'unknown_rate_limit', 120))
            self.assertFalse(state.eligible(self.route))
            self.assertTrue(state.eligible(other))
            clock.return_value += 121
            claim, _ = state.claim(self.route, 50, 'answer', 10, 1000)
            self.assertIsNotNone(claim)
            self.assertEqual(state.claim(self.route, 50, 'answer', 10, 1000)[1], 'circuit open')
            state.finish(claim, self.route, {'status': 'ok'})
            self.assertTrue(state.eligible(self.route))
            state.finish(claim, self.route, {'status': 'error'}, ('provider', 'quota', 180))
            self.assertFalse(state.eligible(other))

    def test_evaluation_cap_and_lifecycle(self):
        state = State(self.db)
        claim, _ = state.claim(self.route, 50, 'evaluation', 10, 1000)
        self.assertEqual(state.claim(self.route, 50, 'evaluation', 10, 1000)[1], 'evaluation quota')
        state.finish(claim, self.route, {'status': 'ok'}, quality=1)
        self.assertEqual(state.evaluation_index(self.route), 1)
        key = 'openrouter/a/x:free'
        self.assertEqual(lifecycle(self.route, {key: [6, 8, 0, 0, 3, 3]}), 'active')
        self.assertEqual(lifecycle(self.route, {key: [2, 8, 0, 0, 0, 3]}), 'demoted')

    def test_task_privacy_and_diversity(self):
        self.assertEqual(classify('Translate hello.')[0:2], ('translation', 'easy'))
        self.assertEqual(classify('Propose a system design.')[1], 'complex')
        self.assertEqual(classify('Write a story.', 'planning')[0], 'planning')
        self.assertTrue(sensitive('Call me at example@example.com'))
        other = dict(self.route, family='b', provider='groq')
        self.assertGreater(score(other, {}, 'general', [self.route]), score(self.route, {}, 'general', [self.route]))

    def test_classify_http(self):
        self.assertEqual(classify_http(429, {}, 'openrouter')[:2], ('model', 'unknown_rate_limit'))
        self.assertEqual(classify_http(429, {}, 'openrouter', 'upstream_limit')[:2], ('model', 'upstream_limit'))
        self.assertEqual(classify_http(429, {'x-ratelimit-remaining-requests': '0',
                         'x-ratelimit-reset-requests': '2m3s'}, 'groq'), ('provider', 'quota', 123))
        self.assertEqual(classify_http(401, {}, 'groq')[:2], ('provider', 'authorization'))
        self.assertEqual(classify_http(402, {}, 'groq')[:2], ('provider', 'billing'))
        self.assertEqual(classify_http(400, {}, 'groq', 'context_length_exceeded')[1], 'context_length_exceeded')

    def test_fallback_and_failed_synthesis(self):
        posts = []

        def handler(request):
            if request.method == 'GET':
                return httpx.Response(200, json={'data': [
                    dict(model(f'{name}/x:free'), context_length=32000) for name in 'abcd'
                ] + [model('paid/x'), model('unknown/x:free', prompt=None)]})
            body = json.loads(request.content)
            posts.append(body)
            if body['model'] == 'a/x:free':
                return httpx.Response(429, headers={'Retry-After': '90'})
            if len(posts) == 5:
                return httpx.Response(503)
            return httpx.Response(200, json={'choices': [{'message': {'content':
                'Original evidence passage from the model.'}, 'finish_reason': 'stop'}]})

        async def work():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                keys = {'openrouter': 'test-key'}
                candidates, notes = await council.discover(client, self.cfg, keys)
                args = SimpleNamespace(mode='quick', words=250, tokens=4096, synthesize=True)
                return await council.run_council(client, args, self.cfg, keys, 'Compare options.', candidates, notes)

        with patch.object(council, 'ROOT', self.root):
            self.assertEqual(asyncio.run(work()), 0)
        self.assertEqual(len(posts), 5)
        self.assertTrue(all(p['provider']['max_price']['completion'] == 0 for p in posts))
        self.assertTrue(all(p['provider']['allow_fallbacks'] is False for p in posts))
        result = next((self.root/'runs').iterdir())
        report = (result/'master_report.md').read_text(encoding='utf-8')
        self.assertIn('Replacement', report)
        self.assertIn('Local review', report)
        self.assertIn('Original evidence passage from the model.', report)
        self.assertEqual(json.loads((result/'synthesis.json').read_text())['category'], 'upstream_error')

    def test_privacy_blocks_before_http(self):
        args = SimpleNamespace(command='run', confidential=True)
        with patch.object(council.httpx, 'AsyncClient', side_effect=AssertionError):
            self.assertEqual(asyncio.run(council.main_run(args, self.cfg, {})), 2)

    def test_cancellation_and_recovery(self):
        async def work():
            marker = self.root/'cancel'
            marker.touch()
            with self.assertRaises(asyncio.CancelledError):
                await council.cancellable(asyncio.sleep(10), marker)
        asyncio.run(work())
        state = State(self.db)
        with patch('adaptive.time.time', return_value=200000) as clock:
            claim, _ = state.claim(self.route, 50, 'answer', 1, 1000)
            self.assertIsNotNone(claim)
            self.assertEqual(State(self.db).remaining(1), 0)
            clock.return_value += 86401
            self.assertEqual(State(self.db).remaining(1), 1)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute('SELECT outcome FROM inference').fetchone(), ('reserved',))

    def test_synthesis_dedup_preserves_sources_and_originals(self):
        text = 'a' * 1500
        answers = [dict(self.route, text=text, status='ok'), dict(self.route, model='b/x:free', text=text, status='partial')]
        payload = json.loads(council.synthesis_brief('brief', answers).split('\n', 1)[1])
        self.assertEqual(len(payload['answers']), 1)
        self.assertEqual(len(payload['answers'][0]['sources']), 2)
        self.assertEqual(answers[0]['text'], text)
