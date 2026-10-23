"""Source-development evidence audit over existing controllers; never a live-agent promotion.

Public learner views deliberately cannot contain target programs or assessment
rows. A single meter covers training, acquisition, selection and assessment.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, asdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import tempfile
import time

from .combined_investigation_engine import (
    AlgebraicPropertySynthesizer, EpisodeCallLedger, EqualizedControllerConfig,
    EqualizedInvestigationEngineV2, InvestigationPolicyV2Parameters,
    VersionedCapsule, execute_pipeline,
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


class EventMeter:
    """One event per actual invocation, not one per bundle of invocations.

    This is an auditable instrumented trace, not remote attestation. Assessment
    events are evaluator-only at execution time, published after choices lock.
    """
    def __init__(self, emit):
        self.emit, self.previous, self.index = emit, '0'*64, 0

    def call(self, scope, kind, identity, fn, argument):
        started = time.perf_counter()
        status = 'ok'
        try:
            output = fn(deepcopy(argument))
        except Exception as exc:
            status, output = 'error', 'ERR:'+type(exc).__name__
        self.index += 1
        event = dict(kind='execution', index=self.index, previous=self.previous,
                     scope=scope, operation=kind, identity=identity,
                     argument=argument, output=output, status=status,
                     elapsed_s=time.perf_counter()-started)
        event['hash'] = digest(event)
        self.previous = event['hash']
        self.emit(event)
        return output


@dataclass(frozen=True)
class PublicInvestigation:
    task_id: str
    cohort: str
    domain: str
    ticket_request: str
    support_examples: list
    probe_pool_inputs: list
    candidate_pool: list


def catalogue(config):
    # Same target-independent space and order for every source and target task.
    ops = config['operators']
    programs = [seq for n in config['program_lengths'] for seq in itertools.product(ops, repeat=n)]
    return [('p'+str(i), seq, lambda xs, seq=seq: execute_pipeline(seq, xs))
            for i, seq in enumerate(programs)]


def make_task(config, seed, cohort, i, meter=None):
    pool = catalogue(config)
    n = 2 if cohort == 'source' else 3
    sequences = list(itertools.product(config['operators'], repeat=n))
    random.Random(seed + (1000 if cohort == 'assessment' else 0)).shuffle(sequences)
    target = sequences[i]
    rng = random.Random(seed*10000+i+(900 if cohort == 'assessment' else 0))
    support = [[rng.randint(1, 8) for _ in range(4)] for _ in range(2)]
    probes = deepcopy(config['probes'])
    rng.shuffle(probes)  # Content, never position, defines learned/fixed priorities.
    assessment = [[-13-i, 0, 11, 11, 17], [19, -17, 0, 19, 23], [29, -31, 0, 29]]
    assert not ({digest(x) for x in support} & {digest(x) for x in probes+assessment})
    assert not ({digest(x) for x in probes} & {digest(x) for x in assessment})
    def observed(x):
        fn = lambda x: execute_pipeline(target, x)
        return (meter.call(f'{seed}:generation:{cohort}:{i}', 'support_reference', str(target), fn, x)
                if meter else fn(x))
    public = PublicInvestigation(f'{seed}:{cohort}:{i}', cohort, 'sequence_pipeline',
                                 'Infer the observed list transform.',
                                 [(x, observed(x)) for x in support], probes, pool)
    # Only evaluator gets the target and final rows. Learner gets public alone.
    return public, target, assessment


class SharedLedger(EpisodeCallLedger):
    def __init__(self, meter, scope):
        super().__init__()
        self.meter, self.scope = meter, scope

    def invoke_candidate(self, candidate_id, fn, inp, phase):
        def wrapped(x):
            return self.meter.call(self.scope, phase, candidate_id, fn, x)
        return super().invoke_candidate(candidate_id, wrapped, inp, phase)

    def invoke_oracle(self, active_env, task_id, probe_input):
        class Counted:
            def request_answer(_, tid, inp):
                return self.meter.call(self.scope, 'oracle', tid,
                                       lambda x: active_env.request_answer(tid, x), inp)
        return super().invoke_oracle(Counted(), task_id, probe_input)


def train_public(tasks, answers, meter, seed, config):
    """No target labels. Credit all answer-consistent hypotheses fractionally.

    Probe utility is source-only entropy keyed by content, not probe position.
    The old v2 trainer and its manually supplied repository mappings are unused.
    """
    weights, freq, probe_credit, capsules = {}, {}, {}, []
    for task in tasks:
        scope = f'{seed}:train:{task.task_id}'
        survivors = []
        for cid, ops, fn in task.candidate_pool:
            if all(meter.call(scope, 'support_check', cid, fn, x) == y for x, y in task.support_examples):
                survivors.append((cid, ops, fn))
        signatures = []
        for x in task.probe_pool_inputs:
            outs = {cid: meter.call(scope, 'probe_construction', cid, fn, x) for cid, _, fn in survivors}
            counts = Counter(digest(y) for y in outs.values())
            entropy = -sum((v/len(survivors))*math.log2(v/len(survivors)) for v in counts.values())
            probe_credit[digest(x)] = probe_credit.get(digest(x), 0)+entropy
            signatures.append((entropy, x, outs))
        for _, x, outs in sorted(signatures, key=lambda item: -item[0])[:config['controller']['max_questions_per_task']]:
            y = meter.call(scope, 'oracle', task.task_id, answers[task.task_id], x)
            survivors = [(cid, ops, fn) for cid, ops, fn in survivors if outs[cid] == y]
        if not survivors:
            continue
        sig = AlgebraicPropertySynthesizer.extract_behavioral_signature(task.support_examples)
        for _, ops, _ in survivors:
            for op in ops:
                freq[op] = freq.get(op, 0)+1/len(survivors)
                for k, v in sig.items():
                    weights.setdefault(op, {})[k] = weights.get(op, {}).get(k, 0)+v/len(survivors)
        cid, ops, fn = survivors[0]
        # Acquired source candidate requires fresh SOURCE validation, not a target injection.
        checks = []
        for x in config['source_validation']:
            expected = meter.call(scope, 'source_validation_oracle', task.task_id, answers[task.task_id], x)
            checks.append(meter.call(scope, 'source_validation', cid, fn, x) == expected)
        if all(checks):
            capsules.append(VersionedCapsule(capsule_id='cap_'+task.task_id, name=cid,
                             domain='sequence_pipeline', skeleton_ops=list(ops),
                             schema_assumptions={'audit':1}, source_code=' -> '.join(ops)))
    return weights, freq, probe_credit, capsules


def parameters(method, learned, task, seed):
    weights, freq, credit, _ = learned
    params = InvestigationPolicyV2Parameters()
    mode = 'untrained_default_active'
    if method in ('learned', 'capsules_reset', 'shuffled'):
        params.trained = True
        params.behavioral_rank_weights = deepcopy(weights)
        values = [credit.get(digest(x), 0) for x in task.probe_pool_inputs]
        if method == 'shuffled':
            random.Random(seed).shuffle(values)
            keys = list(params.behavioral_rank_weights)
            random.Random(seed).shuffle(keys)
            params.behavioral_rank_weights = dict(zip(keys, weights.values()))
        params.learned_probe_scores = {'sequence_pipeline': values}
        params.probe_eval_window = 2
        mode = 'learned_policy_curriculum_active'
    elif method == 'frequency':
        params.trained, params.operator_frequencies = True, freq
        mode = 'simple_frequency_active'
    elif method in ('boundary_first', 'cost_aware'):
        params.trained = True
        def score(x):
            value = len(set(x)) + 2*(0 in x) + 2*any(v < 0 for v in x)
            return value/(len(x) or 1) if method == 'cost_aware' else value
        params.learned_probe_scores = {'sequence_pipeline':[score(x) for x in task.probe_pool_inputs]}
        params.probe_eval_window = 2
        mode = 'learned_policy_curriculum_active'
    return params, mode


def run(config, emit):
    meter = EventMeter(emit)
    emit(dict(kind='audit_manifest', config_hash=digest(config), catalogue_hash=digest(
        [(cid, ops) for cid, ops, _ in catalogue(config)]), target_in_candidates_by_construction=False,
        gemini='NOT_RUN: no authorized credential/spending allocation',
        result_label='authored_source_development_pilot_not_confirmation'))
    for seed in config['seeds']:
        source = [make_task(config, seed, 'source', i, meter) for i in range(config['source_tasks'])]
        answers = {t.task_id: lambda x, ops=ops: execute_pipeline(ops, x) for t, ops, _ in source}
        learned = train_public([t for t, _, _ in source], answers, meter, seed, config)
        # Save/restore exact learned data; this is persistence, not an extra replicate.
        state = dict(weights=learned[0], frequencies=learned[1], probe_credit=learned[2],
                     capsules=[asdict(c) for c in learned[3]])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'policy.json'
            path.write_text(json.dumps(state, allow_nan=False))
            restored = json.loads(path.read_text())
            assert digest(state) == digest(restored)
        emit(dict(kind='learned_state', seed=seed, state=state, state_hash=digest(state), restart_equal=True))
        for i in range(config['assessment_tasks']):
            task, ops, rows = make_task(config, seed, 'assessment', i, meter)
            for method in config['methods']:
                scope = f'{seed}:{method}:{i}'
                engine = EqualizedInvestigationEngineV2(
                    ledger_factory=lambda: SharedLedger(meter, scope), strict_controller_bounds=True)
                params, mode = parameters(method, learned, task, seed)
                engine.set_strategy_params(params)
                keep_caps = method in ('learned', 'cache', 'prior_reset')
                if keep_caps:
                    engine.knowledge.skills.capsules = {c.capsule_id: deepcopy(c) for c in learned[3]}
                before = engine.knowledge.skills.state_hash()
                meter.call(scope, 'retrieval', 'source_capsules', lambda _: len(learned[3]) if keep_caps else 0, None)
                class Answers:
                    def request_answer(self, tid, x):
                        assert tid == task.task_id
                        return execute_pipeline(ops, x)
                episode = engine.investigate_v2(task, Answers(), EqualizedControllerConfig(**config['controller']),
                      mode, allow_compositional_capsules=keep_caps)
                # Durable lock precedes assessment outcomes. No evaluator data in params/view.
                lock = dict(kind='choice', scope=scope, selected=episode['selected_candidate_id'],
                            selected_ops=episode['selected_ops'], policy_hash=digest(asdict(params)),
                            capsule_hash=before, frozen_capsules=before == engine.knowledge.skills.state_hash())
                emit(lock)
                for j, x in enumerate(rows):
                    meter.call(scope, 'assessment_reference', str(j), lambda x: execute_pipeline(ops, x), x)
                    meter.call(scope, 'assessment_candidate', episode['selected_candidate_id'], episode['selected_fn'], x)
                emit(dict(kind='episode', scope=scope, seed=seed, method=method, task=i,
                          training_cost_charged_separately=True))
    # Reuse real chat/data/repair/restart paths, with runtime disabled explicitly.
    run_capability_checks(config, meter, emit)


def run_capability_checks(config, meter, emit):
    from unittest.mock import patch
    from .symbiotic_agent_loop import SymbioticAgentLoop, AgentTaskPublicView
    from .agent_loop_worker import run_worker_subprocess
    with tempfile.TemporaryDirectory() as tmp:
        for spec in config['coding']:
            registry = None  # Same tools, no target-supplied capsules/edits.
            task = AgentTaskPublicView(spec['id'], 'development', spec['domain'], spec['language'],
                                       spec['request'], spec['files'], spec['public'], spec.get('docs', []))
            scope = 'coding:'+spec['id']
            def worker(payload, timeout_s=10):
                payload = dict(payload, trace=True)
                out = meter.call(scope, 'worker', spec['id'],
                                 lambda data: run_worker_subprocess(data, timeout_s), payload)
                if isinstance(out, dict):
                    for j, row in enumerate(out.get('results', [])):
                        # Observations of real calls, not a second execution.
                        emit(dict(kind='worker_case', scope=scope, index=j, result=row,
                                  execution_hash=meter.previous))
                return out
            with patch('nexus.seed.symbiotic_agent_loop.run_worker_subprocess', worker):
                result = meter.call(scope, 'agent', spec['id'],
                                    lambda _: SymbioticAgentLoop(Path(tmp)/spec['id'], registry).solve(task), None)
            if type(result) is dict:
                for call in result.get('tool_calls', []):
                    emit(dict(kind='tool_trace', scope='coding:'+spec['id'], record=call))
                final = meter.call('coding:'+spec['id'], 'assessment_worker', spec['id'],
                            lambda payload: run_worker_subprocess(dict(payload, trace=True)),
                            dict(language=spec['language'], files=result['final_files'], cases=spec['assessment']))
                emit(dict(kind='capability', id=spec['id'], category='coding',
                          outcome=result['outcome_category'], final=final,
                          counts_unit='worker invocations; nested case/function traces reported separately',
                          attempts=len(result.get('patch_attempts', []))))
        from .lab import SeedWorkspace
        from .conversation_capability import send, probe_json, probe_sqlite, probe_conversation, write_files
        ws = SeedWorkspace(Path(tmp)/'chat', attach_local_runtime=False)
        sid = ws.dispatch(dict(session_id=None, request={'op':'new'}))['session_id']
        for spec in config['chat']:
            result = meter.call('chat:'+spec['id'], 'chat', spec['id'], lambda text: send(ws, sid, text), spec['text'])
            emit(dict(kind='capability', id=spec['id'], category='language', response=result,
                      scoring='review_actual_response_and_cards; no keyword conversation score'))
        for name, fn in [('json',probe_json), ('sqlite',probe_sqlite)]:
            out = meter.call('tools:'+name, 'tool', name, fn, str(Path(tmp)/name))
            emit(dict(kind='capability', id=name, category='tools', response=out))
        from .symbiotic_workbench import StatefulZ3Coordinator, SymPySymbolicBackend
        def constraints(_):
            coord=StatefulZ3Coordinator()
            coord.add_variable('x')
            coord.add_constraint('positive','x > 3')
            coord.add_constraint('negative','x < 1')
            return coord.check()
        for name,fn,arg in [('z3',constraints,None),('sympy',SymPySymbolicBackend.solve_or_simplify,
                                   dict(op='solve',expression='3*x + 2 = 17',variable='x',domain='real'))]:
            result=meter.call('reasoning:'+name,'reasoning',name,fn,arg)
            emit(dict(kind='capability',id=name,category='reasoning',response=result,
                      supplied_formalization=True,automatic_language_formalization=False))
        paths = write_files(Path(tmp)/'files', [dict(id='alpha', key='region', value='amount', rows=[['east','4']]),
                                                dict(id='beta', key='region', value='amount', rows=[['west','6']])])
        out = meter.call('restart', 'tool', 'restart', lambda _: probe_conversation(paths, Path(tmp)/'restart'), None)
        emit(dict(kind='capability', id='restart', category='retention', response=out))
    # Live runtime is a separate connectivity/structured-intent probe, not the solver above.
    from .local_model_runtime import PersistentLocalRuntime, RuntimeConfig, file_hash
    model = Path(config['model_path'])
    if not model.is_file():
        emit(dict(kind='capability', id='live_model', category='runtime', outcome='BLOCKED_MISSING_MODEL'))
        return
    if file_hash(model) != config['model_sha256']:
        raise ValueError('frozen_model_hash_mismatch')
    runtime = PersistentLocalRuntime(RuntimeConfig(str(model), max_tokens=48, application_cache=False))
    try:
        meter.call('runtime', 'startup', 'llama_cpu', lambda _: runtime.start(), None)
        from .assistant_benchmark_v2 import SCHEMA, intent_prompt
        reply = meter.call('runtime', 'inference', 'qwen',
                    lambda text: runtime.complete(text, schema=SCHEMA),
                    intent_prompt('Show individual rows with amount at least 4, largest first.', ['region','amount']))
        emit(dict(kind='capability', id='live_model', category='runtime', response=reply,
                  model_hash=file_hash(model), inference_is_separate_probe=True))
    finally:
        runtime.close()
        if file_hash(model) != config['model_sha256']:
            raise ValueError('frozen_model_changed')


def summarize(records, config):
    events = [r for r in records if r.get('kind') == 'execution']
    episodes = [r for r in records if r.get('kind') == 'episode']
    expected = {(s,m,i) for s in config['seeds'] for m in config['methods'] for i in range(config['assessment_tasks'])}
    actual = [(r['seed'],r['method'],r['task']) for r in episodes]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('incomplete_or_duplicate_episode_grid')
    by_method = {}
    for method in config['methods']:
        scopes = {r['scope'] for r in episodes if r['method']==method}
        subset = [e for e in events if e['scope'] in scopes]
        correct = 0
        for scope in scopes:
            refs = [e['output'] for e in subset if e['scope']==scope and e['operation']=='assessment_reference']
            outs = [e['output'] for e in subset if e['scope']==scope and e['operation']=='assessment_candidate']
            if len(refs)!=3 or len(outs)!=3:
                raise ValueError('assessment_missing')
            correct += refs == outs
        counts = dict(Counter(e['operation'] for e in subset))
        by_method[method] = dict(correct=correct, tasks=len(scopes), operations=counts,
             candidate_calls=sum(counts.get(k,0) for k in ('support_check','probe_construction')))
    return dict(declared_complete=True, methods=by_method,
                training_operations=dict(Counter(e['operation'] for e in events if ':train:' in e['scope'])),
                all_operations=dict(Counter(e['operation'] for e in events)),
                learning_to_learn_established=False, verdict='DEVELOPMENT_PILOT_ONLY',
                capability_ids=[r['id'] for r in records if r.get('kind')=='capability'])
