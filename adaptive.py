"""Transactional inference ledger and adaptive routing policy."""
import json
import math
import re
import sqlite3
import time
from contextlib import closing, contextmanager
from email.utils import parsedate_to_datetime

MODES = {'quick': (3, 5), 'council': (5, 8), 'supreme': (8, 12)}
TOPICS = {
    'architecture': r'architecture|system design|scalability',
    'coding': r'code|coding|python|javascript|debug|implement|function',
    'mathematics': r'math|calculate|equation|arithmetic|algebra',
    'research': r'research|sources|citations|literature',
    'creative writing': r'poem|story|fiction|screenplay',
    'translation': r'translate|translation',
    'summarization': r'summarize|summary|summarise',
    'planning': r'plan|roadmap|schedule',
    'critical evaluation': r'evaluate|critique|compare|review',
    'reasoning': r'reason|logic|prove|deduce',
}
CAPABILITY_TERMS = {
    'architecture': 'code|reason', 'coding': 'code|coder', 'mathematics': 'math|reason',
    'reasoning': 'reason', 'critical evaluation': 'reason', 'translation': 'multilingual',
}


def classify(prompt, override=None):
    matches = [topic for topic, pattern in TOPICS.items()
               if re.search(r'\b(?:' + pattern + r')\b', prompt, re.I)]
    words = len(prompt.split())
    difficulty = 'complex' if words >= 160 or len(matches) >= 3 or 'architecture' in matches else (
        'medium' if words >= 35 or matches and matches[0] not in {'translation', 'summarization'} else 'easy')
    return override or next(iter(matches), 'general'), difficulty, matches, words


def sensitive(prompt):
    return bool(re.search(r'-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk-|ghp_|gsk_)[\w-]{12,}|'
                          r'\b(?:password|api[_ -]?key|secret|access[_ -]?token)\s*[:=]\s*\S+|'
                          r'\b\d{3}-\d{2}-\d{4}\b|\b[^\s@]+@[^\s@]+\.[a-z]{2,}\b|'
                          r'\b(?:confidential|internal use only)\b', prompt, re.I))


def route(m):
    return m['provider'] + '/' + m['model']


class State:
    def __init__(self, path):
        self.path = path
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS requests(provider TEXT, ts REAL)')
            db.execute('CREATE INDEX IF NOT EXISTS requests_time ON requests(ts)')
            db.execute('CREATE TABLE IF NOT EXISTS council_schema(version INTEGER NOT NULL)')
            version = db.execute('SELECT version FROM council_schema').fetchone()
            if version is None:
                for statement in (
                    'CREATE TABLE inference (id INTEGER PRIMARY KEY, route TEXT, ts REAL, '
                    'tokens INTEGER, purpose TEXT, outcome TEXT, category TEXT, latency REAL, quality REAL)',
                    'CREATE INDEX inference_time ON inference(ts)',
                    'CREATE TABLE circuits (scope TEXT PRIMARY KEY, until REAL, category TEXT, probe INTEGER)',
                    'CREATE TABLE registry (route TEXT PRIMARY KEY, metadata TEXT, verified REAL)',
                    'CREATE TABLE legacy_health (route TEXT PRIMARY KEY, metadata TEXT)',
                    'INSERT INTO council_schema VALUES (1)',
                ):
                    db.execute(statement)
            elif version != (1,):
                raise sqlite3.DatabaseError('unsupported council schema')

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            yield db

    def refresh(self, models, legacy):
        with self.transaction() as db:
            db.executemany('INSERT OR REPLACE INTO registry VALUES (?,?,?)',
                           [(route(m), json.dumps(m), time.time()) for m in models])
            db.executemany('INSERT OR IGNORE INTO legacy_health VALUES (?,?)',
                           [(k, json.dumps(v)) for k, v in legacy.items() if isinstance(v, dict)])

    def remaining(self, daily):
        with self.transaction() as db:
            used, = db.execute('SELECT COUNT(*) FROM requests WHERE ts>?', (time.time()-86400,)).fetchone()
        return max(0, daily-used)

    def eligible(self, model):
        with self.transaction() as db:
            return not db.execute('SELECT 1 FROM circuits WHERE scope IN (?,?) AND until>?',
                                  (model['provider'], route(model), time.time())).fetchone()

    def claim(self, model, tokens, purpose, daily, token_cap):
        now = time.time()
        provider = model['provider']
        scopes = (provider, route(model))
        with self.transaction() as db:
            circuits = db.execute('SELECT scope,until,category FROM circuits WHERE scope IN (?,?)', scopes).fetchall()
            if any(until > now for _, until, _ in circuits):
                return None, 'circuit open'
            used, provider_day, minute = db.execute(
                'SELECT COUNT(*), COALESCE(SUM(provider=?),0), COALESCE(SUM(provider=? AND ts>?),0) '
                'FROM requests WHERE ts>?', (provider, provider, now-60, now-86400)).fetchone()
            spent, evaluations = db.execute(
                "SELECT COALESCE(SUM(tokens),0), COALESCE(SUM(purpose='evaluation'),0) FROM inference WHERE ts>?",
                (now-86400,)).fetchone()
            if used >= daily or spent + tokens > token_cap:
                return None, 'global local quota'
            if provider_day >= model['daily_cap'] or minute >= 8:
                return None, 'provider local quota'
            if purpose == 'evaluation' and evaluations >= daily // 10:
                return None, 'evaluation quota'
            db.execute('INSERT INTO requests VALUES (?,?)', (provider, now))
            reservation = db.execute(
                "INSERT INTO inference(route,ts,tokens,purpose,outcome) VALUES (?,?,?,?,'reserved')",
                (route(model), now, tokens, purpose)).lastrowid
            for scope, _, category in circuits:
                db.execute('UPDATE circuits SET until=?,category=?,probe=? WHERE scope=?',
                           (now+180, category, reservation, scope))
            return reservation, None

    def finish(self, reservation, model, response, failure=None, quality=None):
        now = time.time()
        with self.transaction() as db:
            db.execute('UPDATE inference SET outcome=?,category=?,latency=?,quality=? WHERE id=?',
                       (response['status'], response.get('category'), response.get('latency_seconds'),
                        quality, reservation))
            for scope in (model['provider'], route(model)):
                if response['status'] in ('ok', 'partial'):
                    db.execute('DELETE FROM circuits WHERE scope=? AND probe=?', (scope, reservation))
            if failure:
                scope, category, delay = failure
                target = model['provider'] if scope == 'provider' else route(model)
                db.execute(
                    'INSERT INTO circuits VALUES (?,?,?,NULL) ON CONFLICT(scope) DO UPDATE SET '
                    'until=MAX(CASE WHEN probe=? THEN 0 ELSE until END,excluded.until),category=excluded.category,probe=NULL',
                    (target, now+delay, category, reservation))

    def evaluation_index(self, model):
        with self.transaction() as db:
            count, = db.execute(
                "SELECT COUNT(*) FROM inference WHERE route=? AND purpose='evaluation' AND quality IS NOT NULL",
                (route(model),)).fetchone()
        return count % len(CHECKS)

    def metrics(self):
        now = time.time()
        scores = {}
        with self.transaction() as db:
            legacy = db.execute('SELECT route,metadata FROM legacy_health').fetchall()
            observations = db.execute(
                "SELECT route,ts,outcome,latency,quality FROM inference WHERE ts>? AND outcome IN ('ok','partial','error') AND COALESCE(category,'') NOT IN ('network','authorization','billing','quota')",
                (now-90*86400,)).fetchall()
        for name, metadata in legacy:
            history = json.loads(metadata)
            ok = history.get('ok', 0)
            errors = history.get('error', 0)
            if type(ok) is int and type(errors) is int:
                scores[name] = [2 + min(1, max(0, ok))*.25, 4 + min(2, max(0, ok+errors))*.25, 0, 0, 0, 0]
        for name, ts, outcome, latency, quality in observations:
            weight = math.exp(-(now-ts)/(14*86400))
            stat = scores.setdefault(name, [2, 4, 0, 0, 0, 0])
            stat[0] += weight * {'ok': 1, 'partial': .35}.get(outcome, 0)
            stat[1] += weight
            if latency is not None:
                stat[2] += weight * min(latency, 120)
                stat[3] += weight
            if quality is not None:
                stat[4] += weight * quality
                stat[5] += weight
        return scores


def lifecycle(model, metrics):
    success, trials, _, _, quality, evaluations = metrics.get(route(model), (2, 4, 0, 0, 0, 0))
    if evaluations >= 2.5 and (quality + 1)/(evaluations + 2) < .4 or trials >= 7 and success/trials < .38:
        return 'demoted'
    if evaluations >= 2.5 and (quality + 1)/(evaluations + 2) >= .65 and success/trials >= .6:
        return 'active'
    return 'probation' if trials > 4 else 'verified'


def score(model, metrics, topic, previous):
    success, evidence, latency_sum, latency_count, quality_sum, quality_count = metrics.get(
        route(model), (2, 4, 0, 0, 0, 0))
    latency = 1 / (1 + (latency_sum + 20)/(latency_count + 1)/20)
    terms = CAPABILITY_TERMS.get(topic)
    suitable = .8 if terms and re.search(terms, model['model'], re.I) else .5
    diversity = (.65 * all(m['family'] != model['family'] for m in previous)
                 + .35 * all(m['provider'] != model['provider'] for m in previous))
    quality = (quality_sum + 1)/(quality_count + 2)
    penalty = .10 if lifecycle(model, metrics) == 'demoted' else 0
    return .40*success/evidence + .25*suitable + .15*quality + .10*latency + .10*diversity - penalty


def retry_after(headers):
    value = headers.get('Retry-After', '')
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(value).timestamp() - time.time()
        except (TypeError, ValueError, OverflowError):
            return 0
    return max(0, seconds) if math.isfinite(seconds) else 0


def classify_http(status, headers, provider, code=None):
    if status in (401, 402, 403):
        return 'provider', 'billing' if status == 402 else 'authorization', 7*86400
    if status == 429:
        reset = headers.get('x-ratelimit-reset-requests', '') if provider == 'groq' else ''
        parts = re.findall(r'(\d+(?:\.\d+)?)(h|m|s)', reset)
        reset_delay = sum(float(amount) * {'h': 3600, 'm': 60, 's': 1}[unit] for amount, unit in parts)
        account = (code in {'insufficient_quota', 'account_rate_limit'}
                   or provider == 'groq' and headers.get('x-ratelimit-remaining-requests') == '0')
        delay = max(retry_after(headers), reset_delay if account else 0)
        return ('provider', 'quota', max(delay, 86400 if not delay else 60)) if account else (
            'model', 'upstream_limit' if code == 'upstream_limit' else 'unknown_rate_limit', max(delay, 90))
    category = {400: 'invalid_request', 404: 'unavailable', 408: 'timeout', 422: 'invalid_request'}.get(
        status, 'upstream_error' if status >= 500 else 'http_error')
    if code in {'context_length_exceeded', 'unsupported_parameter', 'model_decommissioned'}:
        category = code
    return 'model', category, max(retry_after(headers), 300 if status in (400, 404, 422) else 45)


CHECKS = (
    ('Answer only with the lowercase word violet.', lambda s: s.strip() == 'violet'),
    ('What is 17 times 23? Return only the integer.', lambda s: s.strip() == '391'),
    ('Return only a JSON object with the key ready set to true.', lambda s: json.loads(s) == {'ready': True}),
    ('What is len(set([1, 1, 2])) in Python? Return only the integer.', lambda s: s.strip() == '2'),
    ('Summarize in at most eight words: The train was cancelled because the tracks flooded.',
     lambda s: len(s.split()) <= 8 and 'flood' in s.lower() and 'train' in s.lower()),
    ('Name one primary color of light in exactly one English word.',
     lambda s: s.strip().lower().rstrip('.') in {'red', 'green', 'blue'}),
)
