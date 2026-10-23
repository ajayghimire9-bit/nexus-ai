"""Development capability runner. Reuses chat, adapters, config repair and Session.

Not a parallel executor. Closed study artifacts are not read or rewritten.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import time
import uuid
from copy import deepcopy
from pathlib import Path

from .assistant_benchmark_v2 import bind, reference, skeleton
from .lab import SeedWorkspace
from .real_data_adapter_learning import ParameterizedAdapterTemplate, SchemaProfileAndBindingValidator
from nexus.evolution1.catalogue import digest


def load_manifest(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('study_id') != 'seed-conversation-capability-v1':
        raise ValueError('unexpected_study_id')
    return data


def write_files(root, specs):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    paths = {}
    for spec in specs:
        path = root / (spec['id'] + '.csv')
        fields = [spec['key'], spec['value']] + ([spec['extra']] if spec.get('extra') else [])
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in spec['rows']:
                writer.writerow({fields[i]: row[i] for i in range(len(fields))})
        paths[spec['id']] = path
    return paths


def send(workspace, sid, text):
    return workspace.dispatch(dict(session_id=sid, request=dict(
        op='chat_send', text=text, id=uuid.uuid4().hex)))['response']


def score_csv(path, expected, result):
    status, output = reference(path, expected)
    cards = result['chat']['messages'][-1]['cards']
    executed = any(card['data'].get('executed') for card in cards)
    actual_path = next((card['data'].get('output_path') for card in cards if card['data'].get('output_path')), None)
    actual = json.loads(Path(actual_path).read_text()) if actual_path and Path(actual_path).is_file() else None
    turn_status = result['chat']['messages'][-1]['status']
    if expected['op'] in ('clarify', 'unsupported'):
        correct = (not executed) and turn_status in ('clarification', 'error')
        observed = 'unsupported' if expected['op'] == 'unsupported' else 'clarification'
    else:
        correct = executed and actual == output
        observed = 'success' if correct else ('incorrect_execution' if executed else turn_status)
    return dict(correct=correct, expected_status=status, observed_status=observed,
                executed=executed, output=actual, reference_output=output,
                last_intent=result['chat']['context']['workspace'].get('last_intent'))


class ExactCache:
    def __init__(self):
        self.store = {}
        self.hits = 0

    def get(self, key):
        row = self.store.get(key)
        if row is not None:
            self.hits += 1
        return deepcopy(row)

    def put(self, key, value):
        self.store[key] = deepcopy(value)


def run_csv_method(manifest, paths, directory, method):
    workspace = SeedWorkspace(Path(directory) / method, attach_local_runtime=False)
    sid = workspace.dispatch(dict(session_id=None, request={'op': 'new'}))['session_id']
    cache = ExactCache()
    rows = []
    saved = False
    for task in manifest['csv_tasks']:
        started = time.perf_counter()
        path = paths[task['file']]
        text = task['request'].format(path=path)
        if task.get('prior_request'):
            send(workspace, sid, task['prior_request'].format(path=path))
        key = digest([hashlib.sha256(path.read_bytes()).hexdigest(), task['expected']])
        cached = cache.get(key) if method == 'ordinary_cache' else None
        if cached:
            result = cached['result']
            scored = cached['scored']
            scored = dict(scored, cache_hit=True)
        else:
            if method == 'nexus_procedures' and task['id'] == 'csv_inappropriate' and not saved:
                send(workspace, sid, 'Save this procedure.')
                saved = True
            result = send(workspace, sid, text)
            scored = score_csv(path, task['expected'], result)
            scored['cache_hit'] = False
            if method == 'ordinary_cache' and scored['executed']:
                cache.put(key, dict(result=result, scored=scored))
            if method == 'nexus_procedures' and task['id'] == 'csv_easy_sum' and scored['executed']:
                send(workspace, sid, 'Save this procedure.')
                saved = True
        rows.append(dict(kind='csv_trial', method=method, task_id=task['id'], family=task['family'],
                         integration='chat_integrated', environment='csv', scored=scored,
                         wall_s=time.perf_counter()-started,
                         library_bytes=sum(p.stat().st_size for p in workspace.procedures_dir().glob('*.json')),
                         model_calls=0))
    return rows


def run_nexus_reset(manifest, paths, directory):
    """Same prior source task, then a fresh workspace with no capsules."""
    prior = SeedWorkspace(Path(directory) / 'nexus_reset_prior', attach_local_runtime=False)
    sid = prior.dispatch(dict(session_id=None, request={'op': 'new'}))['session_id']
    source = next(task for task in manifest['csv_tasks'] if task['id'] == 'csv_easy_sum')
    send(prior, sid, source['request'].format(path=paths[source['file']]))
    send(prior, sid, 'Save this procedure.')
    fresh = SeedWorkspace(Path(directory) / 'nexus_reset', attach_local_runtime=False)
    sid = fresh.dispatch(dict(session_id=None, request={'op': 'new'}))['session_id']
    target = next(task for task in manifest['csv_tasks'] if task['id'] == 'csv_transfer_same')
    started = time.perf_counter()
    result = send(fresh, sid, target['request'].format(path=paths[target['file']]))
    scored = score_csv(paths[target['file']], target['expected'], result)
    return [dict(kind='csv_trial', method='nexus_reset', task_id=target['id'], family=target['family'],
                 integration='chat_integrated', environment='csv', scored=scored,
                 wall_s=time.perf_counter()-started, library_bytes=0, model_calls=0,
                 capsules_available=False)]


def probe_json(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'probe.json'
    path.write_text(json.dumps([{'region': 'east', 'amount': '4'}, {'region': 'east', 'amount': '6'}]), encoding='utf-8')
    rows = json.loads(path.read_text(encoding='utf-8'))
    profiles = SchemaProfileAndBindingValidator.compute_compact_column_profiles(rows)
    intent = dict(op='sum', min=None, order='desc')
    program = ParameterizedAdapterTemplate('json', 'sum', skeleton(intent)).instantiate(bind(profiles, intent), 0)
    output = program.execute(rows)
    return dict(kind='coverage', id='json_api_sum', environment='json', integration='api_only',
                chat_supported=False, executed=True, output=output, model_calls=0,
                supplied='JSON list + two-op adapter', inferred='column roles')


def probe_sqlite(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'probe.sqlite'
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE facts (region TEXT, amount TEXT)')
    conn.executemany('INSERT INTO facts VALUES (?, ?)', [('east', '4'), ('east', None), ('west', '8')])
    conn.commit()
    rows = [dict(region=r, amount=a) for r, a in conn.execute('SELECT region, amount FROM facts')]
    conn.close()
    profiles = SchemaProfileAndBindingValidator.compute_compact_column_profiles(rows)
    intent = dict(op='sum', min=None, order='desc')
    program = ParameterizedAdapterTemplate('sqlite', 'sum', skeleton(intent)).instantiate(bind(profiles, intent), 0)
    output = program.execute(rows)
    return dict(kind='coverage', id='sqlite_api_read', environment='sqlite', integration='api_only',
                chat_supported=False, executed=True, output=output, model_calls=0,
                join_through_chat=False, supplied='one-table SQLite + adapter',
                inferred='column roles; null amounts dropped by ParseNumberField')


def probe_repair():
    from .config_repair_baseline import Baseline, fixture
    task, _final = fixture(dict(key='limit', default=4, parser='or', core='or', caller='or'))
    result = Baseline().solve(task)
    return dict(kind='coverage', id='repair_api_null_default', environment='repair', integration='api_only',
                chat_supported=False, executed=True, public_passed=result.get('public_passed'),
                cache_hit=result.get('cache_hit'), model_calls=0,
                supplied='public tests + RepositoryModel + source-free AST edits',
                inferred='null/default contract from public tests')


def probe_world():
    from tempfile import TemporaryDirectory
    tmp = TemporaryDirectory()
    workspace = SeedWorkspace(tmp.name, attach_local_runtime=False)
    sid = workspace.dispatch(dict(session_id=None, request={'op': 'new'}))['session_id']
    result = send(workspace, sid, 'Move o1 to the top-right corner.')
    world = workspace.sessions[sid].world
    obj = next(item for item in world if item['id'] == 'o1')
    correct = obj['x'] == 5 and obj['y'] == 0
    return dict(kind='coverage', id='world_chat_goal', environment='world', integration='chat_integrated',
                chat_supported=True, executed=result['chat']['messages'][-1]['status'] == 'success',
                correct=correct, position=[obj['x'], obj['y']], model_calls=0,
                supplied='authored 6x6 world and move/goal grammar', inferred='object id o1')


def probe_conversation(paths, directory):
    workspace = SeedWorkspace(Path(directory) / 'conversation_probe', attach_local_runtime=False)
    sid = workspace.dispatch(dict(session_id=None, request={'op': 'new'}))['session_id']
    send(workspace, sid, 'Summarize amounts by region using '+str(paths['alpha']))
    saved = send(workspace, sid, 'Save this procedure.')
    receipt = send(workspace, sid, 'Save this conversation.')['saved']
    from .storage import load
    restored = load(workspace.directory, sid, receipt['hash'])
    fresh = SeedWorkspace(workspace.directory, attach_local_runtime=False)
    fresh.sessions[sid] = restored
    reused = send(fresh, sid, 'Reuse the saved procedure on '+str(paths['beta']))
    executed = any(card['data'].get('executed') for card in reused['chat']['messages'][-1]['cards'])
    return dict(kind='coverage', id='conversation_restart', environment='conversation',
                integration='chat_integrated', chat_supported=True, executed=executed,
                saved_explicitly=saved['chat']['context']['workspace']['last_saved_explicit'],
                model_calls=0, supplied='session journal + executed AST capsule',
                inferred='last_procedure_id after reload')


def run(manifest, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = write_files(directory / 'files', manifest['files'])
    records = [dict(kind='startup', study_id=manifest['study_id'], methods=manifest['methods'],
                    aggregate_score=False)]
    for method in manifest['methods']:
        records.extend(run_csv_method(manifest, paths, directory, method))
    records.extend(run_nexus_reset(manifest, paths, directory))
    records.append(probe_json(directory / 'json'))
    records.append(probe_sqlite(directory / 'sqlite'))
    records.append(probe_repair())
    records.append(probe_world())
    records.append(probe_conversation(paths, directory))
    return records


def summarize(records):
    csv_rows = [row for row in records if row.get('kind') == 'csv_trial']
    by_method = {}
    for row in csv_rows:
        by_method.setdefault(row['method'], []).append(row['scored']['correct'])
    coverage = [row for row in records if row.get('kind') == 'coverage']
    return dict(
        csv_correctness={method: dict(correct=sum(flags), n=len(flags)) for method, flags in by_method.items()},
        coverage=[{'id': row['id'], 'environment': row['environment'], 'integration': row['integration'],
                   'chat_supported': row.get('chat_supported'), 'executed': row.get('executed'),
                   'correct': row.get('correct')} for row in coverage],
        aggregate_score=None,
        learning_to_learn=False,
        agi=False,
    )
