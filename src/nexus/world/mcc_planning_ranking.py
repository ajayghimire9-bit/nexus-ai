"""Same-state MCC planning-ranking diagnostic.

Tests whether H10-recipe multitask ranks shared H=16 candidates better
than scratch on matched reset states. Collection stays unauthorized until
a later one-run allocation. The locked yaml/protocol hashes must not change.
"""
from __future__ import annotations
import hashlib
import importlib
import json
import math
import re
import subprocess
import time
from pathlib import Path
import numpy as np
import torch
import yaml
from nexus.cl.metrics import seed_level_ci
from nexus.world.data import collect_transitions, concat_datasets
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.rewards import mountaincar_step_reward
from nexus.world.terminal_value_execution import save
from nexus.world.train import train_world_model
from nexus.world import mcc_multitask_128 as h10
from nexus.world import mcc_multitask_128_confirm as h11
from nexus.world import xenv_transfer as rung1

CONFIG = Path('configs/mcc_planning_ranking.yaml')
PROTOCOL = Path('docs/NEXUS_MCC_PLANNING_RANKING_PROTOCOL.md')
ALLOCATION = Path('configs/mcc_planning_ranking_allocation.json')
OUTPUT = Path('artifacts/mcc_planning_ranking.json')
HOLD_RULE = 'mcc_planning_ranking_v1'
CLOSED_H11 = (0.0022, 0.0016, 0.07)
N_SEEDS = 10
N_STATES = 4
HORIZON = 16
N_CAND = 16
N_ACTIONS = 3
N_ARMS = 2
PRIMARY_BUDGET = 128
LOCKED_CONFIG = '17a48088591e8c9316f5b6bffd7cefac48ea2daf158cac98555204b47546feb6'
LOCKED_PROTOCOL = '6acea6f51bdc8ec0ce0f72ce08996f38a333e2e68f854b8fb6c77e218a57148b'
REGISTRIES = h11.REGISTRIES
OTHER_BRANCH_BLOCKS = h11.OTHER_BRANCH_BLOCKS + (73_000_000,)
SEED_MARGIN = h11.SEED_MARGIN
ARMS = ('multitask', 'scratch')
RESET_ATOL = 1e-6
REWARD_ATOL = 1e-5
FROZEN_TRAIN_FIELDS = (
    'n_model_seeds', 'source_family', 'target_family', 'target_budget',
    'n_source_physics', 'source_train', 'target_train', 'target_val',
    'pretrain_epochs', 'train_epochs', 'train_lr', 'term_weight', 'batch_size',
    'hidden', 'horizon', 'n_candidates', 'n_actions',
    'cross_family_weights', 'new_architecture_family', 'retune_from_closed_splits',
    'claims_learning_to_learn', 'is_agi',
)


def source_specs():
    return h10.source_specs()


def source_physics_keys():
    return h10.source_physics_keys()


def occupied_physics():
    occupied = set(h11.occupied_physics())
    occupied.add(h11.CLOSED_H10)
    occupied.add(CLOSED_H11)
    occupied.update(source_physics_keys())
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
    return _mcc('mcc_planning_rank_t0', 'mcc_planning_ranking',
        f'Same-state ranking diagnostic target {key}.',
        gravity=key[0], power=key[1], max_speed=key[2])


def sequence_regret(predicted, actual):
    """Nonnegative: best realized candidate return minus selected realized return."""
    pred = np.asarray(predicted, dtype=np.float64).reshape(-1)
    real = np.asarray(actual, dtype=np.float64).reshape(-1)
    if pred.shape != real.shape or pred.size == 0:
        raise ValueError('predicted and realized candidate returns must align')
    if not np.isfinite(pred).all() or not np.isfinite(real).all():
        raise ValueError('nonfinite candidate returns')
    selected = int(np.argmax(pred))
    regret = float(np.max(real) - real[selected])
    if regret < -1e-12:
        raise ValueError('sequence regret became negative')
    return float(max(regret, 0.0))


def first_action_values(scores, sequences):
    seq = np.asarray(sequences, dtype=np.int64)
    val = np.asarray(scores, dtype=np.float64).reshape(-1)
    if seq.ndim != 2 or seq.shape[0] != val.size:
        raise ValueError('first-action values need paired sequences')
    out = {}
    for action in range(N_ACTIONS):
        mask = seq[:, 0] == action
        if np.any(mask):
            out[int(action)] = float(np.max(val[mask]))
    if not out:
        raise ValueError('no first actions in the candidate set')
    return out


def first_action_regret(predicted, actual, sequences):
    """Nonnegative: best realized first-action value minus selected first-action value."""
    pred_v = first_action_values(predicted, sequences)
    real_v = first_action_values(actual, sequences)
    chosen = max(pred_v, key=pred_v.get)
    if chosen not in real_v:
        raise ValueError('selected first action missing from realized set')
    best = max(real_v.values())
    regret = float(best - real_v[chosen])
    if regret < -1e-12:
        raise ValueError('first-action regret became negative')
    return float(max(regret, 0.0))


def restore_is_reset_seed(method):
    """Ground-truth candidates are restored only by env.reset(seed=state_seed)."""
    return method == 'reset_same_seed'


def budget(cfg):
    source = int(cfg['n_source_physics']) * int(cfg['source_train']) * N_SEEDS
    target = (int(cfg['target_train']) + int(cfg['target_val'])) * N_SEEDS
    gt = N_SEEDS * int(cfg['n_states']) * N_CAND * HORIZON
    closed = N_SEEDS * N_ARMS * int(cfg['n_states']) * HORIZON
    imagined_score = N_SEEDS * N_ARMS * int(cfg['n_states']) * N_CAND * HORIZON
    imagined_recede = N_SEEDS * N_ARMS * int(cfg['n_states']) * HORIZON * N_CAND * HORIZON
    if source + target + gt + closed != cfg['env_cap']:
        raise ValueError('ranking env-step allocation mismatch')
    if imagined_score + imagined_recede != cfg['model_cap']:
        raise ValueError('ranking imagined allocation mismatch')
    if int(cfg['target_train']) != PRIMARY_BUDGET:
        raise ValueError('ranking target budget drifted')
    if int(cfg['n_states']) != N_STATES:
        raise ValueError('ranking state grid drifted')
    return dict(source_collection=source, target_pool=target, ground_truth_open_loop=gt,
                closed_loop_recede=closed, imagined_score=imagined_score,
                imagined_recede=imagined_recede, time_cap_s=cfg['time_cap_s'])


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'mcc_planning_ranking_multitask_better'
    if mean < 0 and hi < 0:
        return 'mcc_planning_ranking_scratch_better'
    return 'mcc_planning_ranking_not_established'


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    h10_cfg = yaml.safe_load(h10.CONFIG.read_text())
    locked = dict(starting_sha='95dbebc962e53c12f271fe8ed02fe61c2ac55fc5',
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
        reset_base=74000000, state_reset_base=74100000, candidate_base=74200000,
        collect_source_base=74300000, collect_target_base=74400000,
        closed_loop_step_base=74500000,
        cross_family_weights=False, new_architecture_family=False,
        retune_from_closed_splits=False, claims_learning_to_learn=False, is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError('locked ranking design/budget changed')
    for key in FROZEN_TRAIN_FIELDS:
        if cfg[key] != h10_cfg[key]:
            raise ValueError(f'ranking training recipe drifted from H10: {key}')
    if cfg['source_physics'] != h10_cfg['source_physics']:
        raise ValueError('ranking source physics drifted from H10')
    if cfg['h10_negative_seeds_used'] is not False:
        raise ValueError('H11 seeds 4/5 must not select physics or candidates')
    if not restore_is_reset_seed(cfg['restore_method']):
        raise ValueError('restore method drifted')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('ranking rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('ranking target collides with occupied physics')
    if tuple(cfg['target_physics'][0]) in {h11.CLOSED_H10, CLOSED_H11}:
        raise ValueError('ranking must not reuse H10 or H11 holdouts')
    spec = target_spec(tuple(cfg['target_physics'][0]))
    if spec.family != 'mountaincar_continuous' or spec.n_actions != N_ACTIONS:
        raise ValueError('ranking target is not MountainCarContinuous')
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
        raise ValueError('ranking seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base_id in OTHER_BRANCH_BLOCKS:
        if any(base_id <= u < base_id + 300000 for u in used):
            raise ValueError('ranking seeds collide with another live branch block')


def summarize(cells, cfg):
    rows = {int(c['seed']): c for c in cells}
    if set(rows) != set(range(N_SEEDS)):
        raise ValueError('incomplete ranking seed grid')
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
        raise RuntimeError('refusing ranking overwrite')
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
        'src/nexus/world/mcc_planning_ranking.py', 'src/nexus/world/mcc_multitask_128.py',
        'src/nexus/world/train.py', 'src/nexus/world/dynamics.py', 'src/nexus/world/data.py',
        'src/nexus/world/planning.py', 'src/nexus/world/xenv_transfer.py',
        'src/nexus/world/prediction_control_gap.py')}
    try:
        for seed in range(N_SEEDS):
            meter.check()
            models = train_seed_models(cfg, spec, priors, seed, meter)
            env = make_task_env(spec)
            try:
                state_rows = []
                for state_index in range(N_STATES):
                    state_seed = int(cfg['state_reset_base']) + 10 * seed + state_index
                    sequences = candidate_sequences(
                        int(cfg['candidate_base']) + 10 * seed + state_index,
                        N_CAND, HORIZON, n_actions=N_ACTIONS)
                    state_rows.append(evaluate_state(
                        env, models, state_seed, sequences, cfg, seed, state_index, meter))
                sequence, first_action, closed = mean_seed_metrics(state_rows)
            finally:
                env.close()
            if any(not np.isfinite(v) for arm in ARMS for v in (sequence[arm], first_action[arm], closed[arm])):
                raise ValueError('nonfinite ranking metric')
            payload['cells'].append(dict(
                seed=seed, sequence_regret=sequence, first_action_regret=first_action,
                closed_loop_return=closed, states=state_rows))
            print(f'seed={seed} seconds={time.perf_counter()-started:.1f}', flush=True)
        payload.update(summarize(payload['cells'], cfg))
        if meter.env_steps != cfg['env_cap'] or meter.model_states != cfg['model_cap']:
            raise ValueError('ranking totals inconsistent with the locked budget')
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
        raise RuntimeError('incomplete/invalid ranking evaluation')
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
        raise ValueError('ranking execution totals drifted')
    if int(payload['counts']['env_steps']) > cfg['env_cap'] or int(payload['counts']['model_states']) > cfg['model_cap']:
        raise ValueError('ranking meters exceeded locked caps')
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
        labels=('mcc_planning_ranking_multitask_better',
                'mcc_planning_ranking_scratch_better',
                'mcc_planning_ranking_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False, full_episode_primary=False,
        note='No collection. Small same-state grid. H10/H11 holdouts closed.')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=300, env_cap=28480, model_cap=348160).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('ranking allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before ranking collection')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def as_obs(obs):
    return np.asarray(obs, dtype=np.float32).reshape(-1)


def record_reset(env, seed):
    """First reset of a ranking state. Later restores must match this observation."""
    obs, _info = env.reset(seed=int(seed))
    return as_obs(obs).copy()


def assert_same_reset(env, seed, obs0, atol=RESET_ATOL):
    """Restore only by reset(seed=state_seed). A mismatch invalidates the cell."""
    obs, _info = env.reset(seed=int(seed))
    obs = as_obs(obs)
    expected = as_obs(obs0)
    if obs.shape != expected.shape or not np.allclose(obs, expected, atol=atol, rtol=0.0):
        raise RuntimeError('reset identity failed')
    return obs


def score_candidates(model, obs, sequences, meter):
    """Imagined H=16 scores. Realized counterfactual returns are not an argument."""
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.shape != (N_CAND, HORIZON):
        raise ValueError('candidate shape drifted')
    original = model.step
    meter.instrument(model)
    try:
        planner = rung1.make_planner(model)
        scores = np.asarray(planner._score_batch(as_obs(obs), sequences), dtype=np.float64)
    finally:
        model.step = original
    if scores.shape != (N_CAND,) or not np.isfinite(scores).all():
        raise RuntimeError('planner dropped a candidate or produced nonfinite scores')
    return scores


def realize_open_loop(env, state_seed, obs0, sequences, meter, *, check_reward=True):
    """Shared simulator returns. The model is not called and does not see these values."""
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.shape != (N_CAND, HORIZON):
        raise ValueError('candidate shape drifted')
    actual = np.zeros(N_CAND, dtype=np.float64)
    traces = []
    for actions in sequences:
        obs = assert_same_reset(env, state_seed, obs0)
        rewards = []
        for action in actions:
            nxt, reward, terminated, truncated, _info = env.step(int(action))
            meter.env_step()
            nxt = as_obs(nxt)
            if check_reward:
                published = float(np.asarray(
                    mountaincar_step_reward(obs, int(action), nxt), dtype=np.float64).reshape(-1)[0])
                if abs(float(reward) - published) > REWARD_ATOL:
                    raise RuntimeError('environment reward does not match published mountaincar height')
            rewards.append(float(reward))
            obs = nxt
            if terminated or truncated:
                break
        if len(rewards) != HORIZON:
            raise RuntimeError('open-loop ended before the candidate horizon')
        actual[len(traces)] = float(math.fsum(rewards))
        traces.append(rewards)
    return actual, traces


def recede_closed_loop(env, model, state_seed, obs0, cfg, seed, arm_index, meter):
    """Secondary 16-step receding control from the same obs0. Not the primary metric."""
    obs = assert_same_reset(env, state_seed, obs0)
    original = model.step
    meter.instrument(model)
    try:
        planner = rung1.make_planner(model)
        rewards = []
        for step in range(HORIZON):
            cand_seed = int(cfg['closed_loop_step_base']) + 1000 * int(seed) + 100 * int(arm_index) + step
            seq = candidate_sequences(cand_seed, N_CAND, HORIZON, n_actions=N_ACTIONS)
            scores = planner._score_batch(obs, seq)
            action = int(seq[int(np.argmax(scores)), 0])
            nxt, reward, terminated, truncated, _info = env.step(action)
            meter.env_step()
            rewards.append(float(reward))
            obs = as_obs(nxt)
            if terminated or truncated:
                break
        if len(rewards) != HORIZON:
            raise RuntimeError('closed-loop ended before the ranking horizon')
        return float(math.fsum(rewards))
    finally:
        model.step = original


def rank_shared_state(predictions, actual, sequences):
    """Regrets from already-computed predicted scores and shared realized returns."""
    actual = np.asarray(actual, dtype=np.float64).reshape(-1)
    sequences = np.asarray(sequences, dtype=np.int64)
    ranked = {}
    for arm, pred in predictions.items():
        pred = np.asarray(pred, dtype=np.float64).reshape(-1)
        selected = int(np.argmax(pred))
        ranked[arm] = dict(
            selected=selected,
            first_action=int(sequences[selected, 0]),
            sequence_regret=sequence_regret(pred, actual),
            first_action_regret=first_action_regret(pred, actual, sequences),
            predicted=pred.tolist(),
        )
    return ranked


def evaluate_state(env, models, state_seed, sequences, cfg, seed, state_index, meter,
                   *, check_reward=True):
    """Score both arms from obs0, then realize the shared open loop, then recede."""
    obs0 = record_reset(env, state_seed)
    predictions = {arm: score_candidates(models[arm], obs0, sequences, meter) for arm in ARMS}
    actual, traces = realize_open_loop(
        env, state_seed, obs0, sequences, meter, check_reward=check_reward)
    ranked = rank_shared_state(predictions, actual, sequences)
    for arm_index, arm in enumerate(ARMS):
        ranked[arm]['closed_loop_return'] = recede_closed_loop(
            env, models[arm], state_seed, obs0, cfg, seed, arm_index, meter)
    return dict(state_index=int(state_index), state_seed=int(state_seed),
                obs0=obs0.tolist(), actual=actual.tolist(), traces=traces, ranked=ranked)


def mean_seed_metrics(state_rows):
    if len(state_rows) != N_STATES:
        raise ValueError('seed is missing a ranking state')
    sequence = {arm: float(np.mean([row['ranked'][arm]['sequence_regret'] for row in state_rows]))
                for arm in ARMS}
    first_action = {arm: float(np.mean([row['ranked'][arm]['first_action_regret'] for row in state_rows]))
                    for arm in ARMS}
    closed = {arm: float(np.mean([row['ranked'][arm]['closed_loop_return'] for row in state_rows]))
              for arm in ARMS}
    return sequence, first_action, closed


def train_seed_models(cfg, spec, priors, seed, meter):
    """Frozen H10 recipe. Source RMS pretrain, then target RMS on both arms."""
    parts = []
    for i, prior in enumerate(priors):
        base = cfg['collect_source_base'] + 120 * seed + 40 * i
        ds = collect_transitions(prior, n_transitions=int(cfg['source_train']),
            env_seeds=tuple(range(base, base + 6)), base_seed=base + 6,
            mix=('random', 'exploratory'))
        meter.collect(int(cfg['source_train']))
        parts.append(ds)
    source = concat_datasets(*parts, task_id='mcc_planning_rank_source')
    source_train = source.slice(np.arange(len(source) - 32, dtype=np.int64))
    source_val = source.slice(np.arange(len(source) - 32, len(source), dtype=np.int64))
    if len(source_train) != 1504 or len(source_val) != 32:
        raise ValueError('ranking source split drifted')
    source_rms = rung1.fit_rms(source_train.obs)
    target_base = cfg['collect_target_base'] + 40 * seed
    train = collect_transitions(spec, n_transitions=int(cfg['target_train']),
        env_seeds=tuple(range(target_base, target_base + 6)), base_seed=target_base + 6,
        mix=('random', 'exploratory'))
    val = collect_transitions(spec, n_transitions=int(cfg['target_val']),
        env_seeds=(target_base + 8, target_base + 9), base_seed=target_base + 10,
        mix=('random', 'exploratory'))
    meter.collect(int(cfg['target_train']) + int(cfg['target_val']))
    if len(train) != int(cfg['target_train']) or len(val) != int(cfg['target_val']):
        raise ValueError('ranking target prefix length drifted')
    target_rms = rung1.fit_rms(train.obs)
    multi, _pre = train_world_model(source_train, source_val, kind='residual',
        epochs=int(cfg['pretrain_epochs']), lr=cfg['train_lr'],
        seed=5 + 19 * seed, n_actions=spec.n_actions, hidden=(64, 64),
        obs_rms=source_rms, freeze_rms=True)
    multi.copy_rms(target_rms)
    h10.continue_train(multi, train, val, epochs=int(cfg['train_epochs']),
        lr=cfg['train_lr'], seed=7 + 19 * seed)
    scratch, _log = train_world_model(train, val, kind='residual',
        epochs=int(cfg['train_epochs']), lr=cfg['train_lr'],
        seed=5 + 19 * seed, n_actions=spec.n_actions, hidden=(64, 64),
        obs_rms=target_rms, freeze_rms=True)
    return {'multitask': multi, 'scratch': scratch}
