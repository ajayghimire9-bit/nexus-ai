"""Guarded H14 candidate-reuse runner. Collection remains unauthorized.

Implements the locked shared-library versus redraw recede grid with
pre-operation budget reservation. Does not change locked H14 science
files or frozen H10-H13 implementations. execute() refuses until a
later one-run allocation exists.
"""
from __future__ import annotations
import inspect
import math
import subprocess
import time
from pathlib import Path
import numpy as np
from nexus.cl.metrics import seed_level_ci
from nexus.world.planning_value import sha
from nexus.world.terminal_value_execution import save
from nexus.world.xenv_transfer import make_planner, fit_rms
from nexus.world import h14_candidate_reuse as lock
from nexus.world import mcc_planning_ranking as h12

OUTPUT = Path('artifacts/h14_candidate_reuse.json')
REWARD_ATOL = h12.REWARD_ATOL
RESET_ATOL = lock.RESET_ATOL
EVENTS: list[str] = []


class GuardedMeter(lock.PreflightMeter):
    """Pre-operation reservation plus attempted/interrupted counters."""

    def __init__(self, cfg):
        super().__init__(cfg)
        self.env_attempted = 0
        self.imagined_attempted = 0
        self.env_interrupted = 0
        self.imagined_interrupted = 0

    def reserve_env(self, n=1):
        n = int(n)
        self.env_attempted += n
        try:
            return super().reserve_env(n)
        except Exception:
            self.env_interrupted += n
            raise

    def reserve_imagined(self, n):
        n = int(n)
        self.imagined_attempted += n
        try:
            return super().reserve_imagined(n)
        except Exception:
            self.imagined_interrupted += n
            raise


def as_obs(obs):
    return np.asarray(obs, dtype=np.float32).reshape(-1)


def raw_state(env):
    inner = getattr(env, 'unwrapped', env)
    if not hasattr(inner, 'state'):
        return None
    return np.asarray(inner.state, dtype=np.float64).reshape(-1).copy()


def record_reset(env, seed):
    obs, _info = env.reset(seed=int(seed))
    return dict(obs=as_obs(obs).copy(), state=raw_state(env))


def assert_same_reset(env, seed, recorded):
    obs, _info = env.reset(seed=int(seed))
    obs = as_obs(obs)
    expected = as_obs(recorded['obs'] if isinstance(recorded, dict) else recorded)
    lock.check_reset_identity(obs, expected, atol=RESET_ATOL)
    recorded_state = recorded.get('state') if isinstance(recorded, dict) else None
    current_state = raw_state(env)
    if recorded_state is not None and current_state is not None:
        if current_state.shape != np.asarray(recorded_state).shape or not np.allclose(
                current_state, recorded_state, atol=RESET_ATOL, rtol=0.0):
            raise RuntimeError('reset hidden-state identity failed')
    return obs


def candidate_seed_for(cfg, seed, state_index, step, mode):
    if mode == 'fixed' or int(step) == 0:
        return lock.shared_library_seed(cfg['library_base'], seed, state_index)
    return lock.redraw_step_seed(cfg['redraw_base'], seed, state_index, step)


def guarded_env_step(env, action, meter):
    meter.reserve_env(1)
    try:
        return env.step(int(action))
    except Exception:
        if hasattr(meter, 'env_interrupted'):
            meter.env_interrupted += 1
        raise


def guarded_collect(collect_fn, spec, n, env_seeds, base_seed, meter):
    meter.preflight_collection(int(n))
    dataset = collect_fn(spec, n_transitions=int(n), env_seeds=env_seeds,
                         base_seed=base_seed, mix=('random', 'exploratory'))
    if len(dataset) != int(n):
        raise ValueError('collection length drifted from reserved allocation')
    return dataset


def score_library_guarded(model, obs, sequences, meter):
    """Imagined H=16 scores. Realized counterfactual returns are not arguments."""
    if 'realized' in inspect.signature(score_library_guarded).parameters:
        raise RuntimeError('planner scoring must not accept realized returns')
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.shape != (lock.N_CAND, lock.HORIZON):
        raise ValueError('candidate shape drifted')
    first_next = {}
    original = model.step
    meter.instrument(model)
    instrumented = model.step

    def capturing(states, actions):
        nxt, prob = instrumented(states, actions)
        if 'batch' not in first_next:
            first_next['batch'] = np.asarray(nxt).copy()
        return nxt, prob

    model.step = capturing
    try:
        planner = make_planner(model)
        scores = np.asarray(planner._score_batch(as_obs(obs), sequences), dtype=np.float64)
    finally:
        model.step = original
    if scores.shape != (lock.N_CAND,) or not np.isfinite(scores).all():
        raise RuntimeError('planner dropped a candidate or produced nonfinite scores')
    return scores, first_next.get('batch')


def realize_open_loop(env, state_seed, recorded, sequences, meter, *, check_reward=True):
    """Shared L0 simulator returns. Models never see these values."""
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.shape != (lock.N_CAND, lock.HORIZON):
        raise ValueError('candidate shape drifted')
    actual = np.zeros(lock.N_CAND, dtype=np.float64)
    traces = []
    for actions in sequences:
        obs = assert_same_reset(env, state_seed, recorded)
        rewards = []
        for action in actions:
            nxt, reward, terminated, truncated, _info = guarded_env_step(env, action, meter)
            nxt = as_obs(nxt)
            if check_reward:
                from nexus.world.rewards import mountaincar_step_reward
                published = float(np.asarray(
                    mountaincar_step_reward(obs, int(action), nxt), dtype=np.float64).reshape(-1)[0])
                if abs(float(reward) - published) > REWARD_ATOL:
                    raise RuntimeError('environment reward does not match published mountaincar height')
            rewards.append(float(reward))
            obs = nxt
            if terminated or truncated:
                break
        if len(rewards) != lock.HORIZON:
            raise RuntimeError('open-loop ended before the candidate horizon')
        actual[len(traces)] = float(math.fsum(rewards))
        traces.append(rewards)
    return actual, traces


def recede_controller(env, model, recorded, cfg, seed, state_index, mode, arm, meter,
                      *, check_reward=True, score_fn=None):
    """16-step recede. Fixed rescores L0; redraw uses the locked later matrices."""
    if mode not in lock.MODES or arm not in lock.ARMS:
        raise ValueError('unknown arm or mode')
    obs = assert_same_reset(env, state_seed := int(cfg['state_reset_base']) + 10 * seed + state_index, recorded)
    scorer = score_fn or score_library_guarded
    l0 = lock.assert_shared_first_library(cfg['library_base'], seed, state_index)
    rewards = []
    traces = []
    for step in range(lock.HORIZON):
        sequences = lock.recede_candidates(mode, cfg['library_base'], cfg['redraw_base'],
                                           seed, state_index, step)
        if int(step) == 0 and not np.array_equal(sequences, l0):
            raise ValueError('step-0 library is not the shared L0')
        if mode == 'fixed' and not np.array_equal(sequences, l0):
            raise ValueError('fixed library drifted from L0')
        cand_seed = candidate_seed_for(cfg, seed, state_index, step, mode)
        scores, first_next = scorer(model, obs, sequences, meter)
        idx, action = lock.selected_first_action(sequences, scores)
        nxt, reward, terminated, truncated, _info = guarded_env_step(env, action, meter)
        nxt = as_obs(nxt)
        residual = None
        if first_next is not None:
            chosen = np.asarray(first_next)
            if chosen.ndim > 1:
                chosen = chosen[idx]
            residual = lock.one_step_residual(chosen, nxt).tolist()
        traces.append(lock.controller_trace(
            seed=int(seed), state_index=int(state_index), mode=mode, arm=arm,
            state_seed=int(state_seed), reset_observation=as_obs(recorded['obs']).tolist(),
            step=int(step), candidate_seed=int(cand_seed),
            library_fingerprint=lock.library_fingerprint(sequences),
            observation=as_obs(obs).tolist(), predicted_scores=np.asarray(scores).tolist(),
            selected_index=int(idx), executed_action=int(action),
            next_observation=nxt.tolist(), realized_reward=float(reward),
            terminated=bool(terminated), truncated=bool(truncated),
            env_steps=int(meter.env_steps), imagined_transitions=int(meter.model_states)))
        if residual is not None:
            traces[-1]['executed_transition_one_step_residual'] = residual
        rewards.append(float(reward))
        obs = nxt
        if terminated or truncated:
            break
    if len(rewards) != lock.HORIZON:
        raise RuntimeError('closed-loop ended before the H14 horizon')
    return float(math.fsum(rewards)), traces


def evaluate_state(env, models, cfg, seed, state_index, meter, *, check_reward=True, score_fn=None):
    state_seed = int(cfg['state_reset_base']) + 10 * seed + state_index
    recorded = record_reset(env, state_seed)
    l0 = lock.assert_shared_first_library(cfg['library_base'], seed, state_index)
    actual, open_traces = realize_open_loop(
        env, state_seed, recorded, l0, meter, check_reward=check_reward)
    controllers = {}
    returns = {}
    for arm in lock.ARMS:
        controllers[arm] = {}
        returns[arm] = {}
        for mode in lock.MODES:
            value, traces = recede_controller(
                env, models[arm], recorded, cfg, seed, state_index, mode, arm, meter,
                check_reward=check_reward, score_fn=score_fn)
            controllers[arm][mode] = dict(return_value=value, traces=traces)
            returns[arm][mode] = value
    return dict(state_index=int(state_index), state_seed=int(state_seed),
                obs0=as_obs(recorded['obs']).tolist(),
                reset_state=None if recorded['state'] is None else recorded['state'].tolist(),
                library_fingerprint=lock.library_fingerprint(l0),
                open_loop=dict(actual=actual.tolist(), traces=open_traces,
                               candidate_seed=lock.shared_library_seed(cfg['library_base'], seed, state_index),
                               library_fingerprint=lock.library_fingerprint(l0)),
                controllers=controllers, returns=returns)


def secondary_metrics(cells):
    """Diagnostics only. Must not be passed into classify_primary."""
    rows = {int(cell['seed']): cell for cell in cells}
    fixed = []
    redraw = []
    open_selected = []
    open_regret = []
    disagreement = []
    for seed in range(lock.N_SEEDS):
        means = lock.mean_seed_returns(rows[seed]['states'])
        fixed.append(means[('multitask', 'fixed')] - means[('scratch', 'fixed')])
        redraw.append(means[('multitask', 'redraw')] - means[('scratch', 'redraw')])
        seed_dis = []
        seed_sel = []
        seed_reg = []
        for state in rows[seed]['states']:
            actual = np.asarray(state['open_loop']['actual'], dtype=np.float64)
            t0 = state['controllers']['multitask']['fixed']['traces'][0]
            pred = np.asarray(t0['predicted_scores'], dtype=np.float64)
            seed_sel.append(float(actual[int(t0['selected_index'])]))
            seed_reg.append(h12.sequence_regret(pred, actual))
            later = 0
            n_later = 0
            for step in range(1, lock.HORIZON):
                n_later += 1
                actions = {arm: {mode: int(state['controllers'][arm][mode]['traces'][step]['executed_action'])
                                 for mode in lock.MODES} for arm in lock.ARMS}
                if (actions['multitask']['fixed'] != actions['multitask']['redraw']
                        or actions['scratch']['fixed'] != actions['scratch']['redraw']
                        or actions['multitask']['fixed'] != actions['scratch']['fixed']):
                    later += 1
            seed_dis.append(later / n_later)
        open_selected.append(float(np.mean(seed_sel)))
        open_regret.append(float(np.mean(seed_reg)))
        disagreement.append(float(np.mean(seed_dis)))
    return dict(multitask_minus_scratch_fixed=seed_level_ci(fixed),
                multitask_minus_scratch_redraw=seed_level_ci(redraw),
                open_loop_selected_return=seed_level_ci(open_selected),
                open_loop_sequence_regret=seed_level_ci(open_regret),
                later_state_action_disagreement=seed_level_ci(disagreement))


def summarize_experiment(cells):
    primary = lock.summarize(cells)
    primary['groups']['secondaries'] = secondary_metrics(cells)
    if primary['groups']['primary']['metric'] != 'fixed_minus_redraw_relative_multitask_advantage':
        raise ValueError('primary metric drifted')
    return primary


def train_seed_models(cfg, spec, priors, seed, meter, *, collect_fn=None, train_fn=None,
                      continue_fn=None, rms_fn=None):
    """Frozen H10 residual recipe with preflight collection reservation."""
    EVENTS.append(f'train:{seed}')
    if collect_fn is None or train_fn is None or continue_fn is None:
        from nexus.world.data import collect_transitions, concat_datasets
        from nexus.world.train import train_world_model
        from nexus.world import mcc_multitask_128 as h10
        collect_fn = collect_fn or collect_transitions
        train_fn = train_fn or train_world_model
        continue_fn = continue_fn or h10.continue_train
        concat = concat_datasets
    else:
        from nexus.world.data import concat_datasets
        concat = concat_datasets
    rms_fn = rms_fn or fit_rms
    parts = []
    for i, prior in enumerate(priors):
        base = int(cfg['collect_source_base']) + 120 * seed + 40 * i
        parts.append(guarded_collect(collect_fn, prior, int(cfg['source_train']),
                                    tuple(range(base, base + 6)), base + 6, meter))
    source = concat(*parts, task_id='mcc_h14_reuse_source')
    source_train = source.slice(np.arange(len(source) - 32, dtype=np.int64))
    source_val = source.slice(np.arange(len(source) - 32, len(source), dtype=np.int64))
    if len(source_train) != 1504 or len(source_val) != 32:
        raise ValueError('H14 source split drifted')
    source_rms = rms_fn(source_train.obs)
    target_base = int(cfg['collect_target_base']) + 40 * seed
    train = guarded_collect(collect_fn, spec, int(cfg['target_train']),
                            tuple(range(target_base, target_base + 6)), target_base + 6, meter)
    val = guarded_collect(collect_fn, spec, int(cfg['target_val']),
                          (target_base + 8, target_base + 9), target_base + 10, meter)
    if len(train) != int(cfg['target_train']) or len(val) != int(cfg['target_val']):
        raise ValueError('H14 target prefix length drifted')
    target_rms = rms_fn(train.obs)
    multi, _pre = train_fn(source_train, source_val, kind='residual',
                           epochs=int(cfg['pretrain_epochs']), lr=cfg['train_lr'],
                           seed=5 + 19 * seed, n_actions=3, hidden=(64, 64),
                           obs_rms=source_rms, freeze_rms=True)
    multi.copy_rms(target_rms)
    continue_fn(multi, train, val, epochs=int(cfg['train_epochs']),
                lr=cfg['train_lr'], seed=7 + 19 * seed)
    scratch, _log = train_fn(train, val, kind='residual',
                             epochs=int(cfg['train_epochs']), lr=cfg['train_lr'],
                             seed=5 + 19 * seed, n_actions=3, hidden=(64, 64),
                             obs_rms=target_rms, freeze_rms=True)
    return {'multitask': multi, 'scratch': scratch}


def target_spec(key):
    from nexus.tasks.mountaincar_continuous_family import _mcc
    return _mcc('mcc_h14_reuse_t0', 'mcc_candidate_reuse',
                f'H14 candidate-reuse target {key}.',
                gravity=key[0], power=key[1], max_speed=key[2])


def run_grid(cfg, meter, spec, priors, *, check_reward=True, hooks=None):
    hooks = hooks or {}
    cells = []
    for seed in range(lock.N_SEEDS):
        meter.check()
        models = (hooks.get('train_seed_models') or train_seed_models)(
            cfg, spec, priors, seed, meter)
        env = (hooks.get('make_env') or _make_env)(spec)
        EVENTS.append(f'env:{seed}')
        try:
            state_rows = []
            for state_index in range(lock.N_STATES):
                state_rows.append(evaluate_state(
                    env, models, cfg, seed, state_index, meter,
                    check_reward=check_reward, score_fn=hooks.get('score_fn')))
        finally:
            env.close()
        cells.append(dict(seed=seed, states=state_rows))
    return cells


def _make_env(spec):
    from nexus.tasks.spec import make_task_env
    EVENTS.append('make_task_env')
    return make_task_env(spec)


def empty_payload(cfg, started):
    key = lock.holdout_from_rule()[0]
    return dict(complete=False, label='incomplete', cells=[], parents=cfg['parents'],
                implementation_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                config_sha256=sha(lock.CONFIG), protocol_sha256=sha(lock.PROTOCOL),
                allocation_sha256=sha(lock.ALLOCATION), source_dirty=False,
                target_physics=list(key), holdout_rule=lock.HOLD_RULE,
                source_physics=[list(item) for item in lock.source_physics_keys()],
                new_environment_interactions=cfg['env_cap'], imagined_transitions=cfg['model_cap'],
                restore_method=cfg['restore_method'], full_episode_primary=False,
                primary_metric='fixed_minus_redraw_relative_multitask_advantage',
                closed_loop_is_primary=False, share_step0_scores=False,
                claims_learning_to_learn=False, is_agi=False,
                started_s=started,
                code_hashes={path: sha(path) for path in (
                    'src/nexus/world/h14_candidate_reuse_runner.py',
                    'src/nexus/world/h14_candidate_reuse.py',
                    'src/nexus/world/mcc_planning_ranking.py',
                    'src/nexus/world/mcc_planning_ranking_confirm.py',
                    'src/nexus/world/mcc_multitask_128.py',
                    'src/nexus/world/train.py', 'src/nexus/world/data.py',
                    'src/nexus/world/planning.py', 'src/nexus/world/xenv_transfer.py')})


def execute(*, hooks=None):
    """Refuse until authorized. Never create an environment before that check."""
    EVENTS.clear()
    EVENTS.append('load_config')
    cfg = lock.load_config()
    EVENTS.append('require_allocation')
    require = (hooks or {}).get('require_allocation') or lock.require_allocation
    require(cfg)
    EVENTS.append('authorized')
    output = Path((hooks or {}).get('output') or OUTPUT)
    if output.exists():
        raise RuntimeError('refusing H14 overwrite')
    if not (hooks or {}).get('skip_git_guards'):
        if subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip():
            raise RuntimeError('commit clean protocol before collection')
        subprocess.run(['git', 'merge-base', '--is-ancestor', cfg['starting_sha'], 'HEAD'], check=True)
    started = time.perf_counter()
    meter = GuardedMeter(cfg)
    payload = empty_payload(cfg, started)
    try:
        import torch
        torch.set_num_threads(1)
        key = lock.holdout_from_rule()[0]
        if key != lock.LOCKED_TARGET:
            raise ValueError('H14 physics drifted')
        spec = (hooks or {}).get('spec') or target_spec(key)
        priors = (hooks or {}).get('priors') or lock.h13.source_specs()
        payload['cells'] = run_grid(cfg, meter, spec, priors,
                                    check_reward=not bool((hooks or {}).get('skip_reward_check')),
                                    hooks=hooks)
        payload.update(summarize_experiment(payload['cells']))
        if meter.env_steps != cfg['env_cap'] or meter.model_states != cfg['model_cap']:
            raise ValueError('H14 totals inconsistent with the locked budget')
        if payload['groups']['primary']['metric'] != 'fixed_minus_redraw_relative_multitask_advantage':
            raise ValueError('primary metric drifted')
        meter.check()
        payload['complete'] = True
    except Exception as exc:
        payload['label'] = 'incomplete'
        payload['complete'] = False
        payload['failure'] = dict(type=type(exc).__name__, message=str(exc))
    payload['wall_clock_s'] = time.perf_counter() - started
    payload['counts'] = dict(env_steps=meter.env_steps, model_states=meter.model_states,
                             env_attempted=getattr(meter, 'env_attempted', meter.env_steps),
                             imagined_attempted=getattr(meter, 'imagined_attempted', meter.model_states),
                             env_interrupted=getattr(meter, 'env_interrupted', 0),
                             imagined_interrupted=getattr(meter, 'imagined_interrupted', 0),
                             events=list(EVENTS))
    save(output, payload)
    return payload


def prep():
    report = lock.prep()
    report.update(runner_implemented=True, runner='src/nexus/world/h14_candidate_reuse_runner.py',
                  output=str(OUTPUT), note='Runner implemented. Collection unauthorized. H10-H13 stay closed.')
    return report
