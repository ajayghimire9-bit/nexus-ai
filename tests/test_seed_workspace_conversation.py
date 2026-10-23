"""Workspace conversation integration: mocked orchestration vs live-model probe.

Development fixtures only. Closed assistant-benchmark artifacts are not reused.
"""
from copy import deepcopy
import csv
import json
from pathlib import Path
import uuid

import pytest

from nexus.seed.conversation import INITIAL, interpret
from nexus.seed.lab import SeedWorkspace
from nexus.seed.storage import load


SAMPLE_A = [
    {'region': ' East ', 'amount': '12'},
    {'region': 'WEST', 'amount': '8'},
    {'region': 'north', 'amount': '17'},
    {'region': ' East ', 'amount': '4'},
]
SAMPLE_B = [
    {'region': 'SOUTH', 'amount': '3'},
    {'region': 'SOUTH', 'amount': '9'},
    {'region': 'west', 'amount': '20'},
]


class ScriptedRuntime:
    """Deterministic stand-in. Never counted as live inference."""

    def __init__(self, structured=None, chat=None):
        self.structured = list(structured or [])
        self.chat = list(chat or [])
        self.calls = []
        self.cancelled = False
        self.closed = False

    def complete(self, prompt, schema):
        self.calls.append({'schema': schema, 'prompt': prompt})
        if self.cancelled:
            raise TimeoutError('inference cancelled or timed out')
        if schema is None:
            content = self.chat.pop(0) if self.chat else 'A notebook per project is a simple local habit.'
        else:
            content = self.structured.pop(0) if self.structured else '{"op":"clarify","min":null,"order":"desc"}'
        return dict(content=content, request_sha256='0'*64, telemetry=dict(
            inference_ran=False, application_cache_hit=True, input_tokens=0, generated_tokens=0,
            prompt_cache_tokens=None, runtime_timings=None, request_wall_s=0.0,
            creation_request_sha256=None))

    def cancel(self):
        self.cancelled = True

    def close(self):
        self.closed = True


def write_csv(path, rows):
    path = Path(path)
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def pair(tmp_path):
    runtime = ScriptedRuntime()
    workspace = SeedWorkspace(tmp_path, local_runtime=runtime)
    sid = workspace.dispatch(dict(session_id=None, request={'op': 'new'}))['session_id']
    return workspace, sid, runtime


def send(pair, text, identifier=None):
    workspace, sid = pair[0], pair[1]
    return workspace.dispatch(dict(session_id=sid, request=dict(
        op='chat_send', text=text, id=identifier or uuid.uuid4().hex)))['response']


def cards(result):
    return result['chat']['messages'][-1]['cards']


def execution_card(result):
    return next(card['data'] for card in cards(result) if card['data'].get('source') == 'execution_backed')


def test_existing_teaching_intents_unchanged():
    assert interpret('Buy stocks for me', deepcopy(INITIAL)).kind == 'unsupported'
    assert interpret('Hello!', deepcopy(INITIAL)).kind == 'hello'
    assert interpret('Save this conversation.', deepcopy(INITIAL)).kind == 'save'


def test_follow_up_same_file_and_other_file(pair, tmp_path):
    first = write_csv(tmp_path / 'east.csv', SAMPLE_A)
    second = write_csv(tmp_path / 'south.csv', SAMPLE_B)
    original = first.read_bytes()
    send(pair, 'Summarize amounts by region using '+str(first))
    again = send(pair, 'Now do the same for '+str(second))
    card = execution_card(again)
    assert card['executed'] is True
    assert card['source_file_unchanged'] is True
    assert first.read_bytes() == original
    assert Path(card['output_path']).is_file()
    assert Path(card['source_file']).name == 'south.csv'
    totals = {row['region']: row['total'] for row in json.loads(Path(card['output_path']).read_text())}
    assert totals['south'] == 12.0
    assert pair[0].sessions[pair[1]].world  # session still intact
    assert pair[2].calls == []  # heuristic multi-turn, no model schema


def test_correction_smallest_first(pair, tmp_path):
    path = write_csv(tmp_path / 'regions.csv', SAMPLE_A)
    send(pair, 'Summarize amounts by region using '+str(path))
    result = send(pair, 'Actually, smallest first.')
    card = execution_card(result)
    rows = json.loads(Path(card['output_path']).read_text())
    totals = [row['total'] for row in rows]
    assert totals == sorted(totals)
    assert result['chat']['context']['workspace']['last_intent']['order'] == 'asc'
    changed = send(pair, 'What did you change?')
    assert 'order=asc' in changed['text']
    assert changed['chat']['messages'][-1]['cards'][0]['data']['executed'] is False


def test_ambiguity_asks_before_acting(pair):
    result = send(pair, 'Summarize amounts by region.')
    assert result['chat']['messages'][-1]['status'] == 'clarification'
    assert not list(Path(pair[0].directory).joinpath('outputs').glob('*')) if Path(pair[0].directory).joinpath('outputs').exists() else True
    assert result['chat']['context']['workspace']['pending_clarification']['kind'] == 'file'


def test_unsupported_request_does_not_execute(pair, tmp_path):
    path = write_csv(tmp_path / 'regions.csv', SAMPLE_A)
    send(pair, 'Use file '+str(path))
    before = list((pair[0].outputs_dir()).glob('*')) if Path(pair[0].directory, 'outputs').exists() else []
    result = send(pair, 'Buy stocks for me and delete my files')
    assert result['chat']['messages'][-1]['status'] == 'clarification'
    assert 'No file was changed' in result['text']
    after = list(pair[0].outputs_dir().glob('*'))
    assert after == before
    assert path.read_text(encoding='utf-8').startswith('region,amount')


def test_generated_python_is_not_a_tool(pair):
    result = send(pair, '__import__("os").system("no")')
    assert result['chat']['messages'][-1]['status'] == 'clarification'
    assert 'Nothing ran' in result['text'] or 'No file was changed' in result['text']


def test_cancellation_writes_nothing(pair, tmp_path):
    path = write_csv(tmp_path / 'regions.csv', SAMPLE_A)
    workspace, sid, _ = pair
    send(pair, 'Use file '+str(path))
    workspace.sessions[sid].cancelled.set()
    workspace.sessions[sid].stopped = True
    result = send(pair, 'Summarize amounts by region.')
    assert result['chat']['messages'][-1]['status'] == 'error'
    assert not list(workspace.outputs_dir().glob('*.json'))


def test_ordinary_chat_is_not_forced_into_sum_rows_schema(pair):
    result = send(pair, 'How should I organize local research notes?')
    assert result['chat']['messages'][-1]['status'] == 'reply'
    assert pair[2].calls and pair[2].calls[-1]['schema'] is None
    card = cards(result)[0]['data']
    assert card['source'] == 'model_generated'
    assert card['executed'] is False
    assert 'not an executed file result' in result['text']
    assert card.get('workspace_header', {}).get('consumes_model_input_tokens') is True
    prompt = pair[2].calls[-1]['prompt']
    assert 'Workspace state (generated from the store' in prompt


def test_missing_coding_workspace_asks_the_needed_question(pair):
    result = send(pair, 'Implement midpoint(a, b) as the average of the two numbers.')
    assert result['chat']['messages'][-1]['status'] == 'clarification'
    assert 'coding workspace' in result['text'].lower()
    pending = result['chat']['context']['workspace']['pending_clarification']
    assert pending['kind'] == 'coding_workspace'


def test_workspace_state_question_names_the_selected_resource(pair, tmp_path):
    root = tmp_path / 'coding_workspaces' / 'demo_mid'
    root.mkdir(parents=True)
    (root / 'm.py').write_text('def noop(x):\n    return x\n', encoding='utf-8')
    send(pair, 'use coding workspace demo_mid')
    result = send(pair, 'What workspace is selected?')
    assert result['chat']['messages'][-1]['status'] == 'reply'
    assert 'demo_mid' in result['text']


def test_model_unavailable_is_reported_not_templated(tmp_path):
    workspace = SeedWorkspace(tmp_path, attach_local_runtime=False)
    sid = workspace.dispatch(dict(session_id=None, request={'op': 'new'}))['session_id']
    result = workspace.dispatch(dict(session_id=sid, request=dict(
        op='chat_send', text='Explain daylight color in two sentences.', id=uuid.uuid4().hex)))['response']
    assert result['chat']['messages'][-1]['status'] == 'clarification'
    assert 'not available' in result['text'] or 'unavailable' in result['text']
    assert 'not a template' in result['text']


def test_save_inspect_reuse_delete_and_restart(pair, tmp_path):
    first = write_csv(tmp_path / 'east.csv', SAMPLE_A)
    second = write_csv(tmp_path / 'south.csv', SAMPLE_B)
    send(pair, 'Summarize amounts by region using '+str(first))
    saved = send(pair, 'Save this procedure.')
    assert saved['chat']['messages'][-1]['status'] == 'success'
    identifier = saved['chat']['context']['workspace']['last_procedure_id']
    assert saved['chat']['context']['workspace']['last_saved_explicit'] is True
    inspected = send(pair, 'Inspect the procedure.')
    assert identifier in json.dumps(inspected['chat']['messages'][-1]['cards'])
    assert inspected['chat']['messages'][-1]['cards'][0]['data']['learning_to_learn'] is False
    receipt = send(pair, 'Save this conversation.')['saved']
    workspace, sid, _ = pair
    restored = load(workspace.directory, sid, receipt['hash'])
    fresh = SeedWorkspace(workspace.directory, local_runtime=ScriptedRuntime())
    fresh.sessions[sid] = restored
    reused = fresh.dispatch(dict(session_id=sid, request=dict(
        op='chat_send', text='Reuse the saved procedure on '+str(second), id=uuid.uuid4().hex)))['response']
    card = execution_card(reused)
    assert card['executed'] is True
    assert card['saved_explicitly'] is True
    assert Path(card['source_file']).name == 'south.csv'
    deleted = fresh.dispatch(dict(session_id=sid, request=dict(
        op='chat_send', text='Delete the saved procedure now.', id=uuid.uuid4().hex)))['response']
    assert deleted['chat']['messages'][-1]['status'] == 'success'
    assert not (workspace.procedures_dir() / (identifier + '.json')).exists()


def test_incompatible_reuse_is_rejected(pair, tmp_path):
    first = write_csv(tmp_path / 'east.csv', SAMPLE_A)
    bad = write_csv(tmp_path / 'wide.csv', [
        {'region': 'east', 'amount': '4', 'extra': '9'},
        {'region': 'west', 'amount': '5', 'extra': '1'},
    ])
    send(pair, 'Summarize amounts by region using '+str(first))
    send(pair, 'Save this procedure.')
    result = send(pair, 'Reuse the saved procedure on '+str(bad))
    assert result['chat']['messages'][-1]['status'] == 'clarification'
    assert 'Nothing ran' in result['text']
    assert not any(card['data'].get('executed') for card in cards(result))


def test_unclear_data_request_uses_runtime_schema_not_ordinary_chat(pair, tmp_path):
    path = write_csv(tmp_path / 'regions.csv', SAMPLE_A)
    send(pair, 'Use file '+str(path))
    pair[2].structured.append('{"op":"clarify","min":null,"order":"desc"}')
    result = send(pair, 'Make the regional view nicer.')
    assert result['chat']['messages'][-1]['status'] == 'clarification'
    assert pair[2].calls and pair[2].calls[-1]['schema'] is not None
    assert pair[2].calls[-1]['schema']['required'] == ['op', 'min', 'order']
    assert 'Nothing ran' in result['text'] or 'grouped totals' in result['text']


def model_ready():
    from shutil import which
    from nexus.seed.local_model_runtime import RuntimeConfig
    cfg = RuntimeConfig.from_environment()
    return Path(cfg.model_path).expanduser().is_file() and which(cfg.executable) is not None


def test_unsupported_modifier_is_not_silently_dropped(pair, tmp_path):
    path = write_csv(tmp_path / 'regions.csv', SAMPLE_A)
    result = send(pair, 'Summarize amounts below 10 using '+str(path))
    assert result['chat']['messages'][-1]['status'] == 'clarification'
    assert 'Nothing ran' in result['text']
    assert not any(card['data'].get('executed') for card in cards(result))
    assert not list(pair[0].outputs_dir().glob('*.json'))


def test_fresh_request_does_not_inherit_threshold_or_order(pair, tmp_path):
    path = write_csv(tmp_path / 'regions.csv', SAMPLE_A)
    first = send(pair, 'Summarize amounts by region at least 5, smallest first, using '+str(path))
    assert first['chat']['context']['workspace']['last_intent'] == {'op': 'sum', 'min': 5.0, 'order': 'asc'}
    fresh = send(pair, 'Summarize amounts by region using '+str(path))
    intent = fresh['chat']['context']['workspace']['last_intent']
    assert intent['min'] is None
    assert intent['order'] == 'desc'
    preview = next(card['data'] for card in cards(fresh) if card['data'].get('source') == 'transformation_preview')
    assert preview['request_kind'] == 'fresh'
    assert preview['inherited_constraints'] is False
    assert preview['resolved']['inclusive_minimum'] is None


def test_conflicting_order_and_two_files_clarify(pair, tmp_path):
    first = write_csv(tmp_path / 'east.csv', SAMPLE_A)
    second = write_csv(tmp_path / 'south.csv', SAMPLE_B)
    clash = send(pair, 'Summarize amounts by region smallest first and largest first using '+str(first))
    assert clash['chat']['messages'][-1]['status'] == 'clarification'
    assert 'Nothing ran' in clash['text']
    both = send(pair, 'Summarize amounts by region using '+str(first)+' and '+str(second))
    assert both['chat']['messages'][-1]['status'] == 'clarification'
    assert 'more than one file' in both['text']


def test_cancellation_after_execute_does_not_commit(pair, tmp_path):
    path = write_csv(tmp_path / 'regions.csv', SAMPLE_A)
    workspace, sid, _ = pair

    def hook(stage, turn):
        if stage == 'after_execute':
            turn.session.cancelled.set()

    workspace.execution_checkpoint = hook
    result = send(pair, 'Summarize amounts by region using '+str(path))
    assert result['chat']['messages'][-1]['status'] == 'error'
    assert not list(workspace.outputs_dir().glob('*.json'))
    assert not list(workspace.outputs_dir().glob('*.tmp-*'))


def test_cancellation_after_commit_preserves_receipt_and_workspace_state(pair, tmp_path):
    path = write_csv(tmp_path / 'regions.csv', SAMPLE_A)
    workspace, sid, _ = pair

    def hook(stage, turn):
        if stage == 'after_commit':
            turn.session.cancelled.set()

    workspace.execution_checkpoint = hook
    result = send(pair, 'Summarize amounts by region using '+str(path))
    assert result['chat']['messages'][-1]['status'] == 'success'
    card = execution_card(result)
    assert card['executed'] is True
    assert card['committed'] is True
    assert card['cancelled_after_commit'] is True
    assert Path(card['output_path']).is_file()
    assert result['chat']['context']['workspace']['last_output_path'] == card['output_path']
    assert result['chat']['context']['workspace']['last_program'] is not None
    assert 'not undone' in result['text']



def test_atomic_publish_removes_temp_on_cancel(tmp_path):
    from nexus.seed.workspace_conversation import publish_json
    target = tmp_path / 'out.json'
    cancelled = {'flag': False}

    def after_tmp(_):
        cancelled['flag'] = True

    try:
        publish_json(target, [{'ok': 1}], cancelled=lambda: cancelled['flag'], after_tmp=after_tmp)
    except ValueError as exc:
        assert str(exc) == 'cancel'
    else:
        raise AssertionError('expected cancel')
    assert not target.exists()
    assert not list(tmp_path.glob('*.tmp-*'))


def test_save_persists_executed_ast_not_prescribed_skeleton(tmp_path):
    from nexus.seed.conversation import Conversation, WORKSPACE, INITIAL
    from nexus.seed.core import Session
    from nexus.seed.shared_brain import SharedBrain
    from nexus.seed.assistant_benchmark_v2 import skeleton
    from nexus.seed.workspace_conversation import WorkspaceTurn, abstract_executed_ast
    path = write_csv(tmp_path / 'regions.csv', SAMPLE_A)
    store = SeedWorkspace(tmp_path, attach_local_runtime=False)
    conv = Conversation(SharedBrain(Session()), store=store, session_id='ab'*16)
    ctx = deepcopy(INITIAL)
    ctx['workspace'] = deepcopy(WORKSPACE)
    unusual = [
        dict(op='ParseNumberField', field='amount', target_field='amount', num_type='float', on_error='drop_row'),
        dict(op='NormalizeTextField', field='region', target_field='region', ops=['strip', 'lower']),
        dict(op='NormalizeTextField', field='region', target_field='region', ops=['strip']),
        dict(op='GroupByField', key_field='region'),
        dict(op='AggregateGroups', key_field='region', aggregations=[dict(out_col='total', agg_fn='sum', src_col='amount')]),
        dict(op='OrderByFields', keys=[dict(field='total', direction='DESC'), dict(field='region', direction='ASC')]),
    ]
    bindings = dict(key_col='region', metric_col='amount', status_col='region', required_output_columns=['region', 'total'])
    ctx['workspace'].update(selected_file=str(path), last_intent=dict(op='sum', min=None, order='desc'),
                            last_program=unusual, last_bindings=bindings, last_source_sha='a'*64,
                            last_request_kind='fresh')
    collected = []
    reply, status, _ = WorkspaceTurn(conv, ctx, lambda title, data: collected.append(dict(title=title, data=data)),
                                     'Save this procedure.').save_procedure()
    assert status == 'success'
    identifier = ctx['workspace']['last_procedure_id']
    saved = json.loads((store.procedures_dir() / (identifier + '.json')).read_text())
    abstracted = abstract_executed_ast(unusual, bindings)
    assert saved['skeleton_ops'] == abstracted
    assert saved['skeleton_ops'] != skeleton(dict(op='sum', min=None, order='desc'))
    assert saved['provenance']['revision'] == 'explicit_save_executed_ast'
    assert 'executed AST' in reply or 'executed AST' in json.dumps(collected)


def test_live_model_probe_or_explicit_unavailable(tmp_path):
    """Live inference only when the configured local model is actually present."""
    report = dict(kind='development_smoke_not_confirmation', live_inference=False, reason=None)
    if not model_ready():
        from nexus.seed.local_model_runtime import RuntimeConfig
        cfg = RuntimeConfig.from_environment()
        report['reason'] = 'local_model_unavailable'
        report['model_path'] = cfg.model_path
        assert report['live_inference'] is False
        return
    from nexus.seed.local_model_runtime import PersistentLocalRuntime, RuntimeConfig
    cfg = RuntimeConfig.from_environment()
    runtime = PersistentLocalRuntime(cfg)
    workspace = SeedWorkspace(tmp_path, local_runtime=runtime)
    sid = workspace.dispatch(dict(session_id=None, request={'op': 'new'}))['session_id']
    path = write_csv(tmp_path / 'live.csv', SAMPLE_A)
    try:
        executed = workspace.dispatch(dict(session_id=sid, request=dict(
            op='chat_send', text='Summarize amounts by region using '+str(path),
            id=uuid.uuid4().hex)))['response']
        assert execution_card(executed)['executed'] is True
        chat = workspace.dispatch(dict(session_id=sid, request=dict(
            op='chat_send', text='Reply with a short greeting only.',
            id=uuid.uuid4().hex)))['response']
        card = cards(chat)[0]['data']
        assert card['source'] == 'model_generated'
        assert card['executed'] is False
        assert chat['text'].strip()
        assert 'not an executed file result' in chat['text']
        report.update(live_inference=True, inference_ran=card.get('inference_ran'),
                      reply_chars=len(chat['text']))
    finally:
        runtime.close()
    assert report['live_inference'] is True
