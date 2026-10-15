"""Frozen H=16 objective versus longer continuation value; source diagnostic only."""
from __future__ import annotations
import hashlib
import itertools
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from nexus.cl.serialize import json_sanitize
from nexus.tasks.pendulum_family import pendulum_context_train, pendulum_physics_key
from nexus.world.long_continuation import continuation_trace, paired_interval
from nexus.world.long_continuation_execution import ExecutionMeter, frozen_hash, context_hash
from nexus.world.prediction_control_gap import candidate_sequences, decision_metrics
from nexus.world.receding_horizon import (rollout_actions, true_state, restore_state,
    chunked_scores, _models_for_task, _context_snapshot, _same_context)

CONFIG = Path('configs/planning_value.yaml')
PROTOCOL = Path('docs/NEXUS_PLANNING_VALUE.md')
OUTPUT = Path('artifacts/planning_value.json')
NAMES = ('zero', '0', '1', '2', '3', '4')
CONFIG_SHA256 = '3a4f1ebcf774209401496bc8a3dc077fead5f1ec79697d518737656679e2d085'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_config():
    if sha(CONFIG) != CONFIG_SHA256: raise ValueError('locked configuration changed')
    cfg = yaml.safe_load(CONFIG.read_text())
    expected = [[s.task_id, *pendulum_physics_key(s)] for s in pendulum_context_train()]
    if cfg['tasks'] != expected or cfg['decoders'] != list(range(10)) or cfg['students'] != list(range(5)):
        raise ValueError('locked source grid drift')
    fixed = dict(states_per_task=1, horizon=16, candidates=16, suffix_steps=48,
                 support_budget=128, env_cap=64512, model_cap=15851520, time_cap_s=600,
                 env_seed_base=1200000, support_env_base=1210000, support_action_base=1211000,
                 candidate_seed_base=1220000, continuation_seed_base=1230000, practical_margin=5.0)
    if any(type(cfg.get(k)) is not type(v) or cfg[k] != v for k, v in fixed.items()):
        raise ValueError('locked budget/controller/seed drift')
    if sha(cfg['parent_artifact']) != cfg['parent_sha256']:
        raise ValueError('closed parent changed')
    if sha('artifacts/control_replication_checkpoints/manifest.json') != cfg['manifest_sha256']:
        raise ValueError('manifest changed')
    return cfg


def suffix_seeds(cfg, task):
    # No candidate index or selected action can change continuation randomness.
    return list(range(cfg['continuation_seed_base'] + task * 64,
                      cfg['continuation_seed_base'] + task * 64 + 48))


def seed_groups(cfg):
    return [set(cfg['env_seed_base'] + t for t in range(8)),
            set(cfg['support_env_base'] + t * 10 for t in range(8)),
            set(cfg['support_action_base'] + t for t in range(8)),
            set(cfg['candidate_seed_base'] + t for t in range(8)),
            set(x for t in range(8) for x in suffix_seeds(cfg, t))]


def assert_seeds(cfg):
    from nexus.world.policy_switch import assert_seeds as prior_check, load_config as prior_config, seeds
    from nexus.world.prediction_control_gap import diagnostic_seed_groups, load_prediction_config
    from nexus.world.receding_horizon import horizon_seed_groups, load_horizon_config
    from nexus.world.return_phase import phase_seed_groups, load_phase_config
    from nexus.world.late_control_gap_design import design_seed_groups
    from nexus.world.long_continuation import proposed_seeds, load_config as long_config
    prior = prior_config(); prior_check(prior)
    a, b = diagnostic_seed_groups(load_prediction_config()); blocked = set()
    for group in (a, b, horizon_seed_groups(load_horizon_config()), phase_seed_groups(load_phase_config()),
                  design_seed_groups(), proposed_seeds(long_config())):
        for values in group.values(): blocked.update(values)
    blocked.update([prior['env_seed'], prior['planner_seed']])
    blocked.update(x for p in range(2) for slot in range(6) for x in seeds(prior, p, slot))
    for group in seed_groups(cfg):
        if blocked & group: raise ValueError('closed or overlapping registered seed')
        blocked.update(group)


class ValueMeter(ExecutionMeter):
    def __init__(self, cfg):
        self.deadline = time.perf_counter() + cfg['time_cap_s']
        self.env_cap, self.model_cap = cfg['env_cap'], cfg['model_cap']
        self.counts = dict(support=0, prefix=0, suffix=0, model_states=0)
        self.bucket = 'prefix'
    def check(self):
        if time.perf_counter() >= self.deadline: raise TimeoutError('600-second planning-value cap reached')


def finite_array(value, shape):
    # Validate JSON leaf types before numpy can coerce strings/bools to numbers.
    def leaves(x):
        if isinstance(x, (list, tuple)):
            for item in x: yield from leaves(item)
        else: yield x
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in leaves(value)):
        raise ValueError('nonfinite/non-numeric data')
    arr = np.asarray(value, dtype=np.float64)
    if arr.shape != shape or not np.isfinite(arr).all(): raise ValueError('missing/invalid array shape')
    return arr


def compare(scores, actual16, actual64, sequences):
    short = decision_metrics(scores, actual16, sequences)
    long = decision_metrics(scores, actual64, sequences)
    return dict(index=short['selected'], regret16=short['regret'], regret64=long['regret'],
                rank16=short['spearman'], rank64=long['spearman'], reward16_mae=short['reward_mae'],
                selected64=float(actual64[short['selected']]))


def build_metrics(scores, actual16, actual64, sequences):
    exact = int(np.argmax(actual16)); best64 = float(max(actual64))
    conditions = {k: compare(scores[k], actual16, actual64, sequences) for k in NAMES}
    student64 = statistics.mean(conditions[str(s)]['selected64'] for s in range(5))
    zero64 = conditions['zero']['selected64']
    result = dict(primary=best64-float(actual64[exact]), student_minus_zero64=student64-zero64,
                  exact16_minus_zero64=float(actual64[exact])-zero64,
                  exact16_minus_student64=float(actual64[exact])-student64,
                  zero_regret64=conditions['zero']['regret64'],
                  student_regret64=statistics.mean(conditions[str(s)]['regret64'] for s in range(5)),
                  exact16_best64_agreement=float(exact == int(np.argmax(actual64))),
                  student_zero_first_action_disagreement=statistics.mean(
                      float(sequences[conditions[str(s)]['index']][0] != sequences[conditions['zero']['index']][0]) for s in range(5)))
    for metric in ('reward16_mae', 'rank16', 'rank64', 'regret16'):
        result['student_' + metric] = statistics.mean(conditions[str(s)][metric] for s in range(5))
        result['zero_' + metric] = conditions['zero'][metric]
    return result, conditions


def validate_and_summarize(payload, cfg):
    expected = set(itertools.product(cfg['decoders'], range(len(cfg['tasks']))))
    prefixes = {}; rows = {}
    for prefix in payload['prefixes']:
        t = prefix['task']
        if type(t) is not int or t not in range(8) or t in prefixes: raise ValueError('invalid prefix task grid')
        if prefix['env_seed'] != cfg['env_seed_base'] + t or prefix['candidate_seed'] != cfg['candidate_seed_base'] + t:
            raise ValueError('unpaired reset/candidate seed')
        seq = finite_array(prefix['sequences'], (16, 16))
        if not np.array_equal(seq, candidate_sequences(cfg['candidate_seed_base']+t)):
            raise ValueError('candidate set drift')
        state = finite_array(prefix['state'], (2,)); obs = finite_array(prefix['obs'], (3,))
        if not np.allclose(obs, [np.cos(state[0]), np.sin(state[0]), state[1]], atol=1e-6):
            raise ValueError('observation/state mismatch')
        if len(prefix['rollouts']) != 16: raise ValueError('missing candidate prefix')
        for r in prefix['rollouts']:
            finite_array(r['rewards'], (16,)); finite_array(r['next_obs'], (16,3))
            end = finite_array(r['endpoint'], (2,))
            if not np.allclose(r['next_obs'][-1], [np.cos(end[0]),np.sin(end[0]),end[1]], atol=1e-6):
                raise ValueError('endpoint mismatch')
        prefixes[t] = prefix
    if set(prefixes) != set(range(8)): raise ValueError('missing source task')
    for row in payload['cells']:
        key = (row['decoder'], row['task'])
        if any(type(x) is not int for x in key) or key not in expected or key in rows:
            raise ValueError('invalid/duplicate decoder-task cell')
        d,t = key; prefix = prefixes[t]
        if set(row['scores']) != set(NAMES): raise ValueError('missing model condition')
        scores = {k: finite_array(v, (16,)) for k,v in row['scores'].items()}
        if len(row['suffixes']) != 16: raise ValueError('missing candidate continuation')
        actual16 = np.array([sum(r['rewards']) for r in prefix['rollouts']])
        actual64 = []
        for trace, early in zip(row['suffixes'], actual16):
            rewards = finite_array(trace['rewards'], (48,)); actions = trace['actions']; decisions = trace['decisions']
            if len(actions) != 48 or any(type(a) is not int or a not in (0,1,2) for a in actions):
                raise ValueError('invalid continuation actions')
            if len(decisions) != 48: raise ValueError('missing decision trace')
            for k, (action, decision) in enumerate(zip(actions,decisions)):
                seed = suffix_seeds(cfg,t)[k]; idx = decision['selected_index']
                if type(idx) is not int or not 0 <= idx < 16 or decision['seed'] != seed:
                    raise ValueError('unpaired decision randomness')
                if action != int(candidate_sequences(seed)[idx,0]): raise ValueError('candidate/action mismatch')
                if decision['original_step'] != 16+k or decision['terminated'] is not False or decision['truncated'] is not False:
                    raise ValueError('episode clock/boundary mismatch')
                finite_array([decision['predicted_score']], (1,))
            actual64.append(float(early+sum(rewards)))
        metrics, conditions = build_metrics(scores, actual16, np.array(actual64), prefix['sequences'])
        if set(row['metrics']) != set(metrics) or set(row['conditions']) != set(NAMES): raise ValueError('missing metrics')
        for k,v in metrics.items():
            finite_array([row['metrics'][k]], (1,))
            if not math.isclose(row['metrics'][k],v,abs_tol=1e-8): raise ValueError('raw/metric mismatch')
        for name in NAMES:
            if set(row['conditions'][name]) != set(conditions[name]): raise ValueError('missing condition metric')
            for k,v in conditions[name].items():
                finite_array([row['conditions'][name][k]], (1,))
                if not math.isclose(row['conditions'][name][k],v,abs_tol=1e-8): raise ValueError('raw/condition mismatch')
        rows[key] = row
    if set(rows) != expected: raise ValueError('missing planned decoder/task cells')
    checks = payload['frozen_checks']
    if any(type(r[k]) is not int for r in checks for k in ('decoder','task')) or [(r['decoder'],r['task']) for r in checks] != sorted(expected): raise ValueError('missing/duplicate frozen checks')
    if any(set(r['before']) != set(NAMES) or r['before'] != r['after'] for r in checks):
        raise ValueError('network/normalization/context changed')
    if payload['counts'] != dict(support=1024,prefix=2048,suffix=61440,model_states=cfg['model_cap']):
        raise ValueError('resource mismatch')
    if len(payload['supports']) != 8 or [r['task'] for r in payload['supports']] != list(range(8)):
        raise ValueError('missing support hash grid')
    if any(type(r['task']) is not int or len(r['sha256']) != 64 or r['rows'] != 128 for r in payload['supports']): raise ValueError('invalid support hash')
    if any(payload.get(k) != dict(verified=120,missing=0,mismatched=0) for k in ('checkpoint_before','checkpoint_after')):
        raise ValueError('missing/failed checkpoint audit')
    finite_array([payload['wall_clock_s']], (1,))
    if payload['wall_clock_s'] > cfg['time_cap_s']: raise ValueError('time cap exceeded')
    comparisons = {}
    for metric in next(iter(rows.values()))['metrics']:
        values = [statistics.mean(rows[(d,t)]['metrics'][metric] for t in range(8)) for d in cfg['decoders']]
        comparisons[metric] = dict(per_decoder=values, interval=paired_interval(values))
    ci = comparisons['primary']['interval']
    label = 'short_objective_misses_practical_value' if ci['mean'] >= cfg['practical_margin'] and ci['lo'] > 0 else 'objective_mismatch_inconclusive'
    task_means = {str(t): {m: statistics.mean(rows[(d,t)]['metrics'][m] for d in cfg['decoders']) for m in comparisons} for t in range(8)}
    return dict(label=label,comparisons=comparisons,per_task=task_means,valid=True)


def save(payload):
    tmp = OUTPUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(json_sanitize(payload), separators=(',',':'), allow_nan=False)+'\n')
    tmp.replace(OUTPUT)


def execute():
    cfg = load_config(); assert_seeds(cfg)
    if OUTPUT.exists(): raise RuntimeError('refusing repeated evaluation or artifact overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip(): raise RuntimeError('commit clean implementation first')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    started = time.perf_counter(); meter = ValueMeter(cfg)
    payload = dict(complete=False,label='incomplete',source_dirty=False,
        implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),parent_sha256=cfg['parent_sha256'],
        manifest_sha256=cfg['manifest_sha256'],prefixes=[],cells=[],frozen_checks=[],supports=[],counts=meter.counts)
    try:
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        from nexus.world.prediction_control_gap import verify_provenance, load_prediction_config
        from nexus.world.control_replication import load_replication_config,_confirmation_artifact,_collect_named
        from nexus.world.context_pilot import prefix_hash
        from nexus.world.latent_generalization import load_generalization_config
        from nexus.tasks.spec import make_task_env
        import gymnasium
        payload['dependencies'] = dict(python=sys.version,torch=torch.__version__,numpy=np.__version__,gymnasium=gymnasium.__version__)
        payload['checkpoint_before'] = verify_checkpoint_integrity()
        provenance = verify_provenance(load_prediction_config()); payload['provenance'] = provenance
        fingerprints = {int(r['seed']):r['decoder_digest'] for r in provenance['decoder_fingerprints']}
        rep = load_replication_config(); confirmation = _confirmation_artifact(rep)
        supports = []; specs = pendulum_context_train()
        for t,spec in enumerate(specs):
            meter.check()
            support = _collect_named(spec,128,cfg['support_env_base']+t*10,cfg['support_action_base']+t,
                                     set(load_generalization_config()['forbidden_task_ids']))
            if len(support) != 128: raise ValueError('short support')
            supports.append(support); meter.counts['support'] += len(support)
            payload['supports'].append(dict(task=t,rows=128,sha256=prefix_hash(support,128)))
            env = make_task_env(spec); obs,_ = env.reset(seed=cfg['env_seed_base']+t)
            meter.instrument_env(env); meter.bucket = 'prefix'
            try:
                state = true_state(env); seq = candidate_sequences(cfg['candidate_seed_base']+t)
                cache = []
                for actions in seq:
                    roll = rollout_actions(env,state,actions)
                    cache.append(dict(rewards=roll['rewards'].tolist(),next_obs=roll['next_obs'].tolist(),endpoint=true_state(env).tolist()))
                if not np.array_equal(restore_state(env,state),obs): raise ValueError('restore not exact')
                payload['prefixes'].append(dict(task=t,env_seed=cfg['env_seed_base']+t,candidate_seed=cfg['candidate_seed_base']+t,
                    state=state.tolist(),obs=obs.tolist(),sequences=seq.tolist(),rollouts=cache))
            finally: env.close()
        for d in cfg['decoders']:
            for t,spec in enumerate(specs):
                meter.check()
                models = _models_for_task(d,rep,dict(n_student_seeds=5,student_kind='broad',support_budget=128),confirmation,supports[t],fingerprints[d])
                models = {str(k):v for k,v in models.items()}
                before = {k:[frozen_hash(m),context_hash(m)] for k,m in models.items()}
                snapshots = {k:_context_snapshot(m) for k,m in models.items()}
                for m in models.values(): meter.instrument_model(m)
                p = payload['prefixes'][t]; seq = np.asarray(p['sequences'],dtype=np.int64)
                scores = {k:chunked_scores(m,np.array(p['obs'],dtype=np.float32),seq).tolist() for k,m in models.items()}
                actual16 = np.array([sum(r['rewards']) for r in p['rollouts']]); actual64 = []; suffixes = []
                env = make_task_env(spec); env.reset(seed=cfg['env_seed_base']+t); meter.instrument_env(env);meter.bucket='suffix'
                try:
                    for i,prefix in enumerate(p['rollouts']):
                        trace = continuation_trace(env,models['zero'],prefix['endpoint'],suffix_seeds(cfg,t),horizon=48,original_phase=16)
                        actual64.append(float(actual16[i]+sum(trace['rewards']))); suffixes.append(trace)
                    metrics,conditions = build_metrics(scores,actual16,np.array(actual64),p['sequences'])
                    for k,m in models.items(): _same_context(m,snapshots[k])
                    after = {k:[frozen_hash(m),context_hash(m)] for k,m in models.items()}
                    if before != after: raise RuntimeError('frozen network/context mutated')
                    payload['frozen_checks'].append(dict(decoder=d,task=t,before=before,after=after))
                    payload['cells'].append(dict(decoder=d,task=t,scores=scores,suffixes=suffixes,metrics=metrics,conditions=conditions))
                finally: env.close()
            payload['wall_clock_s']=time.perf_counter()-started; save(payload)
            print(f'planning value decoder={d} seconds={payload["wall_clock_s"]:.1f}',flush=True)
        payload['checkpoint_after']=verify_checkpoint_integrity(); payload['wall_clock_s']=time.perf_counter()-started
        payload.update(validate_and_summarize(payload,cfg)); meter.check(); payload['complete']=True
    except Exception as exc:
        payload['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',payload['failure'],flush=True)
    payload['wall_clock_s']=time.perf_counter()-started;save(payload)
    print(payload['label'],payload.get('comparisons',{}).get('primary'),flush=True)
    return payload
