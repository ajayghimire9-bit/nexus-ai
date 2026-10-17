"""Same-design confirmation of H12 ranking on unused MCC physics.

Freezes the H12/H10 recipe, four reset states, shared 16×16 candidates,
and sequence-regret primary. Only the holdout and seed block change.
Closed H12 data are not rewritten. Collection stays unauthorized until
a later one-run allocation.
"""
from __future__ import annotations
import hashlib
import importlib
import json
import re
import subprocess
import time
from pathlib import Path
import numpy as np
import torch
import yaml
from nexus.cl.metrics import seed_level_ci
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.terminal_value_execution import save
from nexus.world import mcc_planning_ranking as h12
from nexus.world import mcc_multitask_128 as h10
from nexus.world import xenv_transfer as rung1

CONFIG = Path('configs/mcc_planning_ranking_confirm.yaml')
PROTOCOL = Path('docs/NEXUS_MCC_PLANNING_RANKING_CONFIRM_PROTOCOL.md')
ALLOCATION = Path('configs/mcc_planning_ranking_confirm_allocation.json')
OUTPUT = Path('artifacts/mcc_planning_ranking_confirm.json')
HOLD_RULE = 'mcc_planning_ranking_confirm_v1'
CLOSED_H12 = (0.0027, 0.0015, 0.075)
FROZEN_H12_CODE = '2cc7342ca747f4a667f14171353dad36a89907ac38bb475a94a7a862ef85d817'
FROZEN_H12_CONFIG = '17a48088591e8c9316f5b6bffd7cefac48ea2daf158cac98555204b47546feb6'
FROZEN_H12_PROTOCOL = '6acea6f51bdc8ec0ce0f72ce08996f38a333e2e68f854b8fb6c77e218a57148b'
FROZEN_H12_RAW = 'c65bc9f42e3fbfe99b5b7dc4d68f8a08fb63fc04e08d374e619dba2f35bbcb8f'
FROZEN_H12_REPORT = '88370eafbeae6643648db32f575716f9c60276ce381204151d7522a29bc30c8d'
LOCKED_CONFIG = '30a6f3da0a550e1a3be079fe4183398a72d91200e5837cd10c9795ce3954dfb4'
LOCKED_PROTOCOL = '6e3f32b629e8f698ffdd7ec527e9541eb115ba3c44ae5bfbcf6bc39eb635ef43'
PRIMARY_BUDGET = h12.PRIMARY_BUDGET
N_SEEDS = h12.N_SEEDS
N_STATES = h12.N_STATES
HORIZON = h12.HORIZON
N_CAND = h12.N_CAND
N_ACTIONS = h12.N_ACTIONS
N_ARMS = h12.N_ARMS
REGISTRIES = h12.REGISTRIES
OTHER_BRANCH_BLOCKS = h12.OTHER_BRANCH_BLOCKS + (74_000_000,)
SEED_MARGIN = h12.SEED_MARGIN
ARMS = h12.ARMS
FROZEN_H12_FIELDS = (
    'n_model_seeds', 'source_family', 'target_family', 'target_budget',
    'n_source_physics', 'source_train', 'target_train', 'target_val',
    'pretrain_epochs', 'train_epochs', 'train_lr', 'term_weight', 'batch_size',
    'hidden', 'horizon', 'n_candidates', 'n_actions', 'n_states',
    'episode_steps', 'restore_method', 'closed_loop_horizon',
    'h10_negative_seeds_used', 'full_episode_primary', 'practical_margin',
    'time_cap_s', 'env_cap', 'model_cap',
    'cross_family_weights', 'new_architecture_family', 'retune_from_closed_splits',
    'claims_learning_to_learn', 'is_agi',
)


def source_specs():
    return h12.source_specs()


def source_physics_keys():
    return h12.source_physics_keys()


def occupied_physics():
    occupied = set(h12.occupied_physics())
    occupied.add(CLOSED_H12)
    return occupied


def holdout_from_rule(n=1, rule=HOLD_RULE):
    occupied = occupied_physics()
    gs = [round(x * 0.0001, 4) for x in range(15, 41)]
    ps = [round(x * 0.0001, 4) for x in range(8, 23)]
    ss = [round(x * 0.005, 3) for x in range(10, 19)]
    chosen = []; counter = 0
    while len(chosen) < int(n):
        digest = hashlib.sha256(f'{rule}:{counter}'.encode()).digest()
        idx = int.from_bytes(digest[:8], 'big')
        key = (float(gs[idx % len(gs)]), float(ps[(idx // len(gs)) % len(ps)]),
               float(ss[(idx // (len(gs) * len(ps))) % len(ss)]))
        if key not in occupied and key not in chosen:
            chosen.append(key)
        counter += 1
    return chosen


def target_spec(key):
    from nexus.tasks.mountaincar_continuous_family import _mcc
    return _mcc('mcc_planning_rank_cf0', 'mcc_planning_ranking_confirm',
        f'Same-state ranking confirmation target {key}.',
        gravity=key[0], power=key[1], max_speed=key[2])


def assert_h12_frozen():
    if sha('src/nexus/world/mcc_planning_ranking.py') != FROZEN_H12_CODE:
        raise ValueError('H12 implementation drifted')
    if sha(h12.CONFIG) != FROZEN_H12_CONFIG:
        raise ValueError('H12 configuration drifted')
    if sha(h12.PROTOCOL) != FROZEN_H12_PROTOCOL:
        raise ValueError('H12 protocol drifted')
    if sha(h12.OUTPUT) != FROZEN_H12_RAW:
        raise ValueError('closed H12 artifact drifted')
    if sha('docs/NEXUS_MCC_PLANNING_RANKING_RESULTS.md') != FROZEN_H12_REPORT:
        raise ValueError('closed H12 report drifted')
    if h12.holdout_from_rule() != [CLOSED_H12]:
        raise ValueError('H12 holdout drifted')
    if h12.source_physics_keys() != source_physics_keys():
        raise ValueError('confirmation source physics drifted from H12')
    if sha('src/nexus/world/mcc_multitask_128.py') != '79a26fed3d0b4a852cd8194492ae67977af41965a56effc01d7441b006dfc701':
        raise ValueError('H10 implementation drifted')


def budget(cfg):
    return h12.budget(cfg)


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'mcc_planning_ranking_confirm_multitask_better'
    if mean < 0 and hi < 0:
        return 'mcc_planning_ranking_confirm_scratch_better'
    return 'mcc_planning_ranking_confirm_not_established'


def load_config():
    assert_h12_frozen()
    cfg = yaml.safe_load(CONFIG.read_text())
    parent = yaml.safe_load(h12.CONFIG.read_text())
    locked = dict(starting_sha='4dbe664672eb5170e2a9848bf320c7750c5e869d',
        n_model_seeds=10, source_family='mountaincar_continuous',
        target_family='mountaincar_continuous', holdout_rule=HOLD_RULE,
        target_budget=PRIMARY_BUDGET, n_source_physics=3,
        source_train=512, target_train=128, target_val=32,
        pretrain_epochs=15, train_epochs=20, train_lr=.001, term_weight=.25,
        batch_size=128, hidden=[64, 64], horizon=HORIZON, n_candidates=N_CAND,
        n_actions=N_ACTIONS, n_states=N_STATES, episode_steps=16,
        restore_method='reset_same_seed', closed_loop_horizon=HORIZON,
        h10_negative_seeds_used=False, full_episode_primary=False,
        practical_margin=0.0, time_cap_s=300, env_cap=28480, model_cap=348160,
        reset_base=75000000, state_reset_base=75100000, candidate_base=75200000,
        collect_source_base=75300000, collect_target_base=75400000,
        closed_loop_step_base=75500000,
        cross_family_weights=False, new_architecture_family=False,
        retune_from_closed_splits=False, claims_learning_to_learn=False, is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError('locked ranking confirmation design/budget changed')
    for key in FROZEN_H12_FIELDS:
        if cfg[key] != parent[key]:
            raise ValueError(f'confirmation hyperparameter drifted from H12: {key}')
    if cfg['source_physics'] != parent['source_physics']:
        raise ValueError('confirmation source physics drifted from H12')
    if cfg['h10_negative_seeds_used'] is not False:
        raise ValueError('H11 seeds 4/5 must not select physics or candidates')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('confirmation rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('confirmation target collides with occupied physics')
    if tuple(cfg['target_physics'][0]) in {h12.CLOSED_H11, h10.holdout_from_rule()[0], CLOSED_H12}:
        raise ValueError('confirmation must not reuse H10, H11, or H12 holdouts')
    spec = target_spec(tuple(cfg['target_physics'][0]))
    if spec.family != 'mountaincar_continuous' or spec.n_actions != N_ACTIONS:
        raise ValueError('confirmation target is not MountainCarContinuous')
    for file, digest in cfg['parents'].items():
        if sha(file) != digest:
            raise ValueError(f'closed parent changed: {file}')
    if sha(CONFIG) != LOCKED_CONFIG:
        raise ValueError('locked configuration hash drifted')
    if sha(PROTOCOL) != LOCKED_PROTOCOL:
        raise ValueError('locked protocol hash drifted')
    budget(cfg); check_seeds(cfg)
    return cfg


def check_seeds(cfg):
    blocked = set()
    for name in REGISTRIES:
        module = importlib.import_module(f'nexus.world.{name}')
        other = yaml.safe_load(module.CONFIG.read_text())
        if hasattr(module, 'seed_groups'):
            blocked |= set().union(*module.seed_groups(other))
    for path in Path('configs').glob('*.yaml'):
        if path.name == CONFIG.name:
            continue
        for value in re.findall(r'[a-z_]*base:\s*(\d+)', path.read_text()):
            blocked |= {int(value) + i for i in range(SEED_MARGIN)}
    used = {cfg['state_reset_base'] + 10 * s + k for s in range(N_SEEDS) for k in range(N_STATES)}
    used |= {cfg['candidate_base'] + 10 * s + k for s in range(N_SEEDS) for k in range(N_STATES)}
    used |= {cfg['collect_source_base'] + 120 * s + i for s in range(N_SEEDS) for i in range(120)}
    used |= {cfg['collect_target_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    used |= {cfg['closed_loop_step_base'] + 1000 * s + 100 * arm + k
             for s in range(N_SEEDS) for arm in range(N_ARMS) for k in range(HORIZON)}
    used |= {cfg['reset_base'] + s for s in range(N_SEEDS)}
    if used & blocked:
        raise ValueError('confirmation seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base_id in OTHER_BRANCH_BLOCKS:
        if any(base_id <= u < base_id + 300000 for u in used):
            raise ValueError('confirmation seeds collide with another live branch block')
    parent = yaml.safe_load(h12.CONFIG.read_text())
    h12_used = {parent['state_reset_base'] + 10 * s + k for s in range(N_SEEDS) for k in range(N_STATES)}
    h12_used |= {parent['candidate_base'] + 10 * s + k for s in range(N_SEEDS) for k in range(N_STATES)}
    h12_used |= {parent['collect_source_base'] + 120 * s + i for s in range(N_SEEDS) for i in range(120)}
    h12_used |= {parent['collect_target_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    h12_used |= {parent['closed_loop_step_base'] + 1000 * s + 100 * arm + k
                 for s in range(N_SEEDS) for arm in range(N_ARMS) for k in range(HORIZON)}
    h12_used |= {parent['reset_base'] + s for s in range(N_SEEDS)}
    if used & h12_used:
        raise ValueError('confirmation seeds overlap the closed H12 block')


def summarize(cells, cfg):
    rows = {int(c['seed']): c for c in cells}
    if set(rows) != set(range(N_SEEDS)):
        raise ValueError('incomplete confirmation seed grid')
    diffs = [float(rows[s]['sequence_regret']['scratch']) - float(rows[s]['sequence_regret']['multitask'])
             for s in range(N_SEEDS)]
    primary = seed_level_ci(diffs)
    label = classify_primary(primary['mean'], primary['lo'], primary['hi'], N_SEEDS, True)
    fa = seed_level_ci([float(rows[s]['first_action_regret']['scratch'])
                        - float(rows[s]['first_action_regret']['multitask'])
                        for s in range(N_SEEDS)])
    return dict(label=label, groups=dict(primary=dict(per_seed=diffs, interval=primary,
        budget=PRIMARY_BUDGET, metric='scratch_minus_multitask_sequence_regret'),
        first_action_regret_gain=fa))


def execute():
    cfg = load_config(); require_allocation(cfg)
    if OUTPUT.exists():
        raise RuntimeError('refusing ranking confirmation overwrite')
    if subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip():
        raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git', 'merge-base', '--is-ancestor', cfg['starting_sha'], 'HEAD'], check=True)
    from nexus.tasks.spec import make_task_env
    torch.set_num_threads(1)
    started = time.perf_counter(); meter = rung1.Meter(cfg)
    key = holdout_from_rule()[0]
    spec = target_spec(key)
    priors = source_specs()
    payload = dict(complete=False, label='incomplete', cells=[], parents=cfg['parents'],
        implementation_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        config_sha256=sha(CONFIG), protocol_sha256=sha(PROTOCOL), allocation_sha256=sha(ALLOCATION),
        source_dirty=False, target_physics=list(key), holdout_rule=HOLD_RULE,
        source_physics=[list(k) for k in source_physics_keys()],
        new_environment_interactions=cfg['env_cap'], imagined_transitions=cfg['model_cap'],
        restore_method=cfg['restore_method'], full_episode_primary=False,
        primary_metric='scratch_minus_multitask_sequence_regret',
        closed_loop_is_primary=False, claims_learning_to_learn=False, is_agi=False)
    payload['code_hashes'] = {f: sha(f) for f in (
        'src/nexus/world/mcc_planning_ranking_confirm.py',
        'src/nexus/world/mcc_planning_ranking.py', 'src/nexus/world/mcc_multitask_128.py',
        'src/nexus/world/train.py', 'src/nexus/world/dynamics.py', 'src/nexus/world/data.py',
        'src/nexus/world/planning.py', 'src/nexus/world/xenv_transfer.py',
        'src/nexus/world/prediction_control_gap.py')}
    try:
        for seed in range(N_SEEDS):
            meter.check()
            models = h12.train_seed_models(cfg, spec, priors, seed, meter)
            env = make_task_env(spec)
            try:
                state_rows = []
                for state_index in range(N_STATES):
                    state_seed = int(cfg['state_reset_base']) + 10 * seed + state_index
                    sequences = candidate_sequences(
                        int(cfg['candidate_base']) + 10 * seed + state_index,
                        N_CAND, HORIZON, n_actions=N_ACTIONS)
                    state_rows.append(h12.evaluate_state(
                        env, models, state_seed, sequences, cfg, seed, state_index, meter))
                sequence, first_action, closed = h12.mean_seed_metrics(state_rows)
            finally:
                env.close()
            if any(not np.isfinite(v) for arm in ARMS for v in (sequence[arm], first_action[arm], closed[arm])):
                raise ValueError('nonfinite ranking confirmation metric')
            payload['cells'].append(dict(
                seed=seed, sequence_regret=sequence, first_action_regret=first_action,
                closed_loop_return=closed, states=state_rows))
            print(f'seed={seed} seconds={time.perf_counter()-started:.1f}', flush=True)
        payload.update(summarize(payload['cells'], cfg))
        if meter.env_steps != cfg['env_cap'] or meter.model_states != cfg['model_cap']:
            raise ValueError('confirmation totals inconsistent with the locked budget')
        if payload.get('closed_loop_is_primary') is not False:
            raise ValueError('closed-loop recede must stay secondary')
        if payload['groups']['primary']['metric'] != 'scratch_minus_multitask_sequence_regret':
            raise ValueError('primary metric drifted from sequence regret')
        meter.check(); payload['complete'] = True
    except Exception as exc:
        payload['label'] = 'incomplete'
        payload['complete'] = False
        payload['failure'] = dict(type=type(exc).__name__, message=str(exc))
        print('INCOMPLETE', payload['failure'], flush=True)
    payload['wall_clock_s'] = time.perf_counter() - started
    payload['counts'] = dict(env_steps=meter.env_steps, model_states=meter.model_states)
    save(OUTPUT, payload)
    return payload


def audit_results():
    cfg = load_config(); payload = json.loads(OUTPUT.read_text())
    if payload.get('complete') is not True:
        raise RuntimeError('incomplete/invalid ranking confirmation')
    rebuilt = summarize(payload['cells'], cfg)
    if payload['label'] != rebuilt['label']:
        raise ValueError('saved label differs')
    if payload.get('claims_learning_to_learn') is not False or payload.get('is_agi') is not False:
        raise ValueError('forbidden claim flags drifted')
    if payload.get('full_episode_primary') is not False or payload.get('closed_loop_is_primary') is not False:
        raise ValueError('closed-loop or full-episode primary drifted')
    if payload['groups']['primary']['metric'] != 'scratch_minus_multitask_sequence_regret':
        raise ValueError('primary metric drifted from sequence regret')
    if int(payload['counts']['env_steps']) != cfg['env_cap'] or int(payload['counts']['model_states']) != cfg['model_cap']:
        raise ValueError('confirmation execution totals drifted')
    return dict(audit_passed=True, label=payload['label'], raw_sha256=sha(OUTPUT),
        groups=payload['groups'],
        new_environment_steps=int(payload['counts']['env_steps']),
        new_imagined_transitions=int(payload['counts']['model_states']),
        target_physics=payload['target_physics'], is_agi=False,
        claims_learning_to_learn=False, closed_loop_is_primary=False)


def prep():
    cfg = load_config()
    record = load_allocation()
    if record.get('authorized') is True or int(record.get('runs', 0)) != 0:
        raise PermissionError('prep refuses an already authorized allocation')
    return dict(complete=True, authorized=False, runs=0, new_environment_steps=0,
        new_imagined_transitions=0, config_sha256=sha(CONFIG),
        protocol_sha256=sha(PROTOCOL), allocation_sha256=sha(ALLOCATION),
        target_physics=list(holdout_from_rule()[0]), holdout_rule=HOLD_RULE,
        source_physics=[list(k) for k in source_physics_keys()],
        n_states=N_STATES, n_candidates=N_CAND, horizon=HORIZON,
        restore_method=cfg['restore_method'],
        proposed_budget=budget(cfg), arms=list(ARMS),
        labels=('mcc_planning_ranking_confirm_multitask_better',
                'mcc_planning_ranking_confirm_scratch_better',
                'mcc_planning_ranking_confirm_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False, full_episode_primary=False,
        note='No collection. Same-design ranking confirmation. H12 holdout closed.')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=300, env_cap=28480, model_cap=348160).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('ranking confirmation allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before ranking confirmation collection')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')
