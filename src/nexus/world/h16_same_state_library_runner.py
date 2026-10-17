"""Guarded H16 same-state library runner. Collection remains unauthorized.

Implements the locked reset-plus-prefix ranking contrast. Does not
change locked H16 science files or H14/H15 artifacts. execute()
refuses until a later one-run allocation exists.
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
from nexus.world.xenv_transfer import make_planner
from nexus.world import h16_same_state_library as lock
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h16_same_state_library_feasibility as feas
from nexus.world.h14_candidate_reuse_runner import (
    GuardedMeter, guarded_collect, train_seed_models as h14_train_seed_models,
)

OUTPUT = Path('artifacts/h16_same_state_library.json')
REWARD_ATOL = 1e-5
EVENTS: list[str] = []
PRIMARY_METRIC = 'same_state_fixed_minus_redraw_relative_multitask_advantage'


def as_obs(obs):
    return np.asarray(obs, dtype=np.float32).reshape(-1)


def raw_state(env):
    inner = getattr(env, 'unwrapped', env)
    if not hasattr(inner, 'state'):
        raise RuntimeError('raw simulator state missing')
    return np.asarray(inner.state, dtype=np.float32).reshape(-1).copy()


def elapsed_steps(env):
    cur = env
    seen = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if getattr(cur, '_elapsed_steps', None) is not None:
            return int(cur._elapsed_steps)
        nxt = getattr(cur, 'env', None)
        cur = None if nxt is cur else nxt
    raise RuntimeError('TimeLimit elapsed_steps missing')


def wrapper_names(env):
    listed = getattr(env, 'wrapper_names', None)
    if listed is not None and not callable(listed):
        return list(listed)
    names = []
    cur = env
    seen = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        names.append(type(cur).__name__)
        nxt = getattr(cur, 'env', None)
        cur = None if nxt is cur else nxt
    return names


def assert_wrapper_stack(env):
    names = wrapper_names(env)
    if not lock.wrapper_stack_ok(names):
        raise RuntimeError(f'unexpected MCC wrapper stack: {names}')
    return names


def assert_exact(a, b, label):
    left = np.asarray(a, dtype=np.float32).reshape(-1)
    right = np.asarray(b, dtype=np.float32).reshape(-1)
    if left.shape != right.shape or not np.array_equal(left, right):
        raise RuntimeError(f'{label} identity failed')
    return left


def guarded_env_step(env, action, meter):
    meter.reserve_env(1)
    try:
        return env.step(int(action))
    except Exception:
        if hasattr(meter, 'env_interrupted'):
            meter.env_interrupted += 1
        raise


def published_reward(obs, action, nxt):
    from nexus.world.rewards import mountaincar_step_reward
    return float(np.asarray(mountaincar_step_reward(obs, int(action), nxt),
                            dtype=np.float64).reshape(-1)[0])


def score_library_guarded(model, obs, sequences, meter):
    """Imagined H=16 scores. Realized returns are not arguments."""
    if 'realized' in inspect.signature(score_library_guarded).parameters:
        raise RuntimeError('planner scoring must not accept realized returns')
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.shape != (lock.N_CAND, lock.HORIZON):
        raise ValueError('candidate shape drifted')
    original = model.step
    meter.instrument(model)
    try:
        planner = make_planner(model)
        scores = np.asarray(planner._score_batch(as_obs(obs), sequences), dtype=np.float64)
    finally:
        model.step = original
    if scores.shape != (lock.N_CAND,) or not np.isfinite(scores).all():
        raise RuntimeError('planner dropped a candidate or produced nonfinite scores')
    return scores


def train_seed_models(cfg, spec, priors, seed, meter, **kwargs):
    EVENTS.append(f'train:{seed}')
    return h14_train_seed_models(cfg, spec, priors, seed, meter, **kwargs)


def record_reference(env, cfg, seed, state_index, meter, *, check_reward=True, check_wrappers=True):
    """One 12-step model-independent prefix. Stores t=8 and t=12 snapshots."""
    if check_wrappers:
        assert_wrapper_stack(env)
    state_seed = int(cfg['state_reset_base']) + 10 * int(seed) + int(state_index)
    prefix_seed = int(cfg['prefix_base']) + 10 * int(seed) + int(state_index)
    prefix = lock.prefix_actions(cfg['prefix_base'], seed, state_index, max(lock.LATER_TIMES))
    if prefix.shape != (max(lock.LATER_TIMES),):
        raise ValueError('reference prefix length drifted')
    obs, _info = env.reset(seed=state_seed)
    reset_obs = as_obs(obs)
    reset_raw = raw_state(env)
    current = reset_obs
    if int(elapsed_steps(env)) != 0:
        raise RuntimeError('elapsed_steps is not zero after reset')
    rewards = []
    snapshots = {}
    for step, action in enumerate(prefix, start=1):
        nxt, reward, terminated, truncated, info = guarded_env_step(env, action, meter)
        nxt = as_obs(nxt)
        if terminated or truncated:
            raise RuntimeError('reference prefix ended before t=12')
        if check_reward and abs(float(reward) - published_reward(current, action, nxt)) > REWARD_ATOL:
            raise RuntimeError('environment reward does not match published mountaincar height')
        rewards.append(float(reward))
        current = nxt
        obs = nxt
        if step in lock.LATER_TIMES:
            snapshots[int(step)] = dict(
                later_t=int(step),
                later_obs=as_obs(obs).copy(),
                later_state=raw_state(env),
                elapsed_steps=int(elapsed_steps(env)),
                prefix_actions=[int(a) for a in prefix[:step]],
                prefix_rewards=list(rewards),
                terminated=False, truncated=False,
                gym_terminated=bool((info or {}).get('gym_terminated', False)),
            )
            if snapshots[int(step)]['elapsed_steps'] != int(step):
                raise RuntimeError('elapsed_steps does not equal prefix length')
    if set(snapshots) != set(lock.LATER_TIMES):
        raise RuntimeError('reference snapshots missing t=8 or t=12')
    return dict(seed=int(seed), state_index=int(state_index), state_seed=int(state_seed),
                prefix_seed=int(prefix_seed), prefix_actions=[int(a) for a in prefix],
                prefix_rewards=rewards, reset_obs=reset_obs, reset_state=reset_raw,
                snapshots=snapshots)


def replay_to_later(env, reference, later_t, meter, *, check_reward=True):
    """Reset plus the stored first t actions. Never assigns .state."""
    later_t = int(later_t)
    snap = reference['snapshots'][later_t]
    obs, _info = env.reset(seed=int(reference['state_seed']))
    reset_obs = as_obs(obs)
    assert_exact(reset_obs, reference['reset_obs'], 'reset_obs')
    assert_exact(raw_state(env), reference['reset_state'], 'reset_state')
    replayed_actions = []
    replayed_rewards = []
    current = reset_obs
    for expected_action, expected_reward in zip(snap['prefix_actions'], snap['prefix_rewards']):
        nxt, reward, terminated, truncated, _info = guarded_env_step(env, int(expected_action), meter)
        if terminated or truncated:
            raise RuntimeError('replay prefix ended early')
        if float(reward) != float(expected_reward):
            raise RuntimeError('prefix reward identity failed')
        if check_reward and abs(float(reward) - published_reward(current, expected_action, as_obs(nxt))) > REWARD_ATOL:
            raise RuntimeError('environment reward does not match published mountaincar height')
        replayed_actions.append(int(expected_action))
        replayed_rewards.append(float(reward))
        current = as_obs(nxt)
        obs = current
    replayed = dict(
        prefix_actions=replayed_actions, prefix_rewards=replayed_rewards,
        reset_obs=reference['reset_obs'], reset_state=reference['reset_state'],
        later_obs=as_obs(obs), later_state=raw_state(env),
        terminated=False, truncated=False,
        elapsed_steps=int(elapsed_steps(env)), later_t=later_t)
    lock.assert_replay_identity({
        'prefix_actions': snap['prefix_actions'], 'prefix_rewards': snap['prefix_rewards'],
        'reset_obs': reference['reset_obs'], 'reset_state': reference['reset_state'],
        'later_obs': snap['later_obs'], 'later_state': snap['later_state'],
        'terminated': False, 'truncated': False,
        'elapsed_steps': snap['elapsed_steps'], 'later_t': later_t,
    }, replayed)
    return replayed


def realize_candidates(env, reference, later_t, sequences, meter, *, check_reward=True):
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.shape != (lock.N_CAND, lock.HORIZON):
        raise ValueError('candidate shape drifted')
    values = np.zeros(lock.N_CAND, dtype=np.float64)
    traces = []
    for actions in sequences:
        replayed = replay_to_later(env, reference, later_t, meter, check_reward=check_reward)
        rewards = []
        current = as_obs(replayed['later_obs'])
        for action in actions:
            nxt, reward, terminated, truncated, _info = guarded_env_step(env, int(action), meter)
            nxt = as_obs(nxt)
            if terminated or truncated:
                raise RuntimeError('candidate ended before the horizon')
            if check_reward and abs(float(reward) - published_reward(current, action, nxt)) > REWARD_ATOL:
                raise RuntimeError('environment reward does not match published mountaincar height')
            rewards.append(float(reward))
            current = nxt
        if len(rewards) != lock.HORIZON:
            raise RuntimeError('incomplete candidate realization')
        values[len(traces)] = float(math.fsum(rewards))
        traces.append(rewards)
    if not np.isfinite(values).all():
        raise ValueError('nonfinite candidate return')
    return values, traces


def evaluate_reset_group(env, models, cfg, seed, state_index, meter, *,
                         check_reward=True, check_wrappers=True, score_fn=None):
    reference = record_reference(env, cfg, seed, state_index, meter,
                                 check_reward=check_reward, check_wrappers=check_wrappers)
    scorer = score_fn or score_library_guarded
    later_states = []
    for later_t in lock.LATER_TIMES:
        snap = reference['snapshots'][later_t]
        obs = snap['later_obs']
        libraries = {}
        selected = {}
        for kind in lock.LIBS:
            sid, sequences = lock.library_for(
                kind, cfg['library_base'], cfg['redraw_base'], seed, state_index, later_t)
            scores = {}
            chosen = {}
            for arm in lock.ARMS:
                pred = np.asarray(scorer(models[arm], obs, sequences, meter), dtype=np.float64)
                if pred.shape != (lock.N_CAND,) or not np.isfinite(pred).all():
                    raise RuntimeError('nonfinite or misaligned scores')
                idx = lock.selected_index(pred)
                scores[arm] = pred
                chosen[arm] = dict(index=idx, action=int(sequences[idx, 0]))
            realized, traces = realize_candidates(
                env, reference, later_t, sequences, meter, check_reward=check_reward)
            oracle = lock.oracle_return(realized)
            libraries[kind] = dict(
                candidate_seed=int(sid),
                library_fingerprint=lock.library_fingerprint(sequences),
                sequences=np.asarray(sequences, dtype=np.int64).tolist(),
                predicted_scores={arm: scores[arm].tolist() for arm in lock.ARMS},
                selected=chosen,
                realized=realized.tolist(),
                reward_traces=traces,
                oracle=oracle,
                selected_return={arm: lock.selected_return(realized, scores[arm]) for arm in lock.ARMS},
                regret={arm: lock.within_library_regret(realized, scores[arm]) for arm in lock.ARMS},
            )
            lock.oracle_cancels_in_arm_gap(realized, scores['multitask'], scores['scratch'])
            selected[kind] = libraries[kind]['selected_return']
        later_states.append(dict(
            seed=int(seed), state_index=int(state_index), later_t=int(later_t),
            state_seed=int(reference['state_seed']), prefix_seed=int(reference['prefix_seed']),
            prefix_actions=list(snap['prefix_actions']), prefix_rewards=list(snap['prefix_rewards']),
            reset_obs=as_obs(reference['reset_obs']).tolist(),
            reset_state=as_obs(reference['reset_state']).tolist(),
            later_obs=as_obs(snap['later_obs']).tolist(),
            later_state=as_obs(snap['later_state']).tolist(),
            elapsed_steps=int(snap['elapsed_steps']),
            s_mt_l0=float(selected['l0']['multitask']),
            s_sc_l0=float(selected['l0']['scratch']),
            s_mt_redraw=float(selected['redraw']['multitask']),
            s_sc_redraw=float(selected['redraw']['scratch']),
            libraries=libraries,
        ))
    return dict(reference=dict(
        state_seed=reference['state_seed'], prefix_seed=reference['prefix_seed'],
        prefix_actions=reference['prefix_actions'], prefix_rewards=reference['prefix_rewards'],
        reset_obs=as_obs(reference['reset_obs']).tolist(),
        reset_state=as_obs(reference['reset_state']).tolist(),
    ), later_states=later_states)


def spearman(pred, realized):
    xa = np.asarray(pred, dtype=np.float64).reshape(-1)
    xb = np.asarray(realized, dtype=np.float64).reshape(-1)
    if xa.size != xb.size or xa.size < 2:
        raise ValueError('spearman needs aligned finite vectors')
    ra = np.argsort(np.argsort(xa))
    rb = np.argsort(np.argsort(xb))
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    den = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    return 0.0 if den == 0 else float((ra * rb).sum() / den)


def first_action_regret(sequences, realized, scores):
    return float(feas.first_action_regret(sequences, realized, scores))


def secondary_metrics(cells):
    """Diagnostics only. Must not be passed into classify_primary."""
    opportunity = []
    regret_mt_l0 = []
    spearman_mt = []
    first_reg = []
    diversity = []
    for cell in cells:
        seed_opp = []
        seed_reg = []
        seed_sp = []
        seed_fa = []
        seed_div = []
        for row in cell['later_states']:
            l0 = row['libraries']['l0']
            redraw = row['libraries']['redraw']
            seed_opp.append(float(l0['oracle'] - redraw['oracle']))
            seed_reg.append(float(l0['regret']['multitask']))
            seed_sp.append(spearman(l0['predicted_scores']['multitask'], l0['realized']))
            seed_fa.append(first_action_regret(l0['sequences'], l0['realized'],
                                               l0['predicted_scores']['multitask']))
            seed_div.append(len({tuple(seq) for seq in l0['sequences']}))
        opportunity.append(float(np.mean(seed_opp)))
        regret_mt_l0.append(float(np.mean(seed_reg)))
        spearman_mt.append(float(np.mean(seed_sp)))
        first_reg.append(float(np.mean(seed_fa)))
        diversity.append(float(np.mean(seed_div)))
    return dict(oracle_opportunity_l0_minus_redraw=seed_level_ci(opportunity),
                multitask_l0_regret=seed_level_ci(regret_mt_l0),
                multitask_l0_spearman=seed_level_ci(spearman_mt),
                multitask_l0_first_action_regret=seed_level_ci(first_reg),
                l0_sequence_diversity=seed_level_ci(diversity))


def summarize_experiment(cells):
    primary = lock.mean_seed_cells(cells)
    return dict(label=primary['label'],
                groups=dict(primary=dict(per_seed=primary['per_seed'],
                                         interval=primary['interval'],
                                         metric=PRIMARY_METRIC,
                                         budget=lock.PRIMARY_BUDGET),
                            secondaries=secondary_metrics(cells)))


def run_grid(cfg, meter, spec, priors, *, check_reward=True, check_wrappers=True, hooks=None):
    hooks = hooks or {}
    cells = []
    for seed in range(lock.N_SEEDS):
        meter.check()
        models = (hooks.get('train_seed_models') or train_seed_models)(
            cfg, spec, priors, seed, meter)
        env = (hooks.get('make_env') or _make_env)(spec)
        EVENTS.append(f'env:{seed}')
        try:
            later = []
            for state_index in range(lock.N_STATES):
                group = evaluate_reset_group(
                    env, models, cfg, seed, state_index, meter,
                    check_reward=check_reward,
                    check_wrappers=check_wrappers and not bool(hooks.get('skip_wrapper_check')),
                    score_fn=hooks.get('score_fn'))
                later.extend(group['later_states'])
        finally:
            env.close()
        cells.append(dict(seed=seed, later_states=later))
    return cells


def _make_env(spec):
    from nexus.tasks.spec import make_task_env
    EVENTS.append('make_task_env')
    return make_task_env(spec)


def target_spec(key):
    from nexus.tasks.mountaincar_continuous_family import _mcc
    return _mcc('mcc_h16_same_state_t0', 'mcc_same_state_library',
                f'H16 same-state library target {key}.',
                gravity=key[0], power=key[1], max_speed=key[2])


def empty_payload(cfg, started):
    key = lock.holdout_from_rule()[0]
    return dict(complete=False, label='incomplete', cells=[], parents=cfg['parents'],
                implementation_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                config_sha256=sha(lock.CONFIG), protocol_sha256=sha(lock.PROTOCOL),
                allocation_sha256=sha(lock.ALLOCATION), source_dirty=False,
                target_physics=list(key), holdout_rule=lock.HOLD_RULE,
                source_physics=[list(item) for item in lock.source_physics_keys()],
                later_times=list(lock.LATER_TIMES),
                new_environment_interactions=cfg['env_cap'], imagined_transitions=cfg['model_cap'],
                restore_method=cfg['restore_method'], full_episode_primary=False,
                primary_metric=PRIMARY_METRIC, closed_loop_is_primary=False,
                same_state_is_primary=True, share_step0_scores=False,
                claims_learning_to_learn=False, is_agi=False, started_s=started,
                code_hashes={path: sha(path) for path in (
                    'src/nexus/world/h16_same_state_library_runner.py',
                    'src/nexus/world/h16_same_state_library.py',
                    'src/nexus/world/h14_candidate_reuse_runner.py',
                    'src/nexus/world/h14_candidate_reuse.py',
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
        raise RuntimeError('refusing H16 overwrite')
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
            raise ValueError('H16 physics drifted')
        spec = (hooks or {}).get('spec') or target_spec(key)
        priors = (hooks or {}).get('priors') or h14.h13.source_specs()
        payload['cells'] = run_grid(cfg, meter, spec, priors,
                                    check_reward=not bool((hooks or {}).get('skip_reward_check')),
                                    check_wrappers=not bool((hooks or {}).get('skip_wrapper_check')),
                                    hooks=hooks)
        payload.update(summarize_experiment(payload['cells']))
        if meter.env_steps != cfg['env_cap'] or meter.model_states != cfg['model_cap']:
            raise ValueError('H16 totals inconsistent with the locked budget')
        if payload['groups']['primary']['metric'] != PRIMARY_METRIC:
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
    report.update(runner_implemented=True, runner='src/nexus/world/h16_same_state_library_runner.py',
                  output=str(OUTPUT), note='Guarded H16 runner. Collection unauthorized.')
    return report
