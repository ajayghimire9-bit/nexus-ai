"""Public-observation exploration schedules; no environment, model or executor.

Reuses partial_feedback's selector and E1 Work. A shared physical panel may
contain both children, but each selector receives exactly one child per reset.
This is preparation for a masked-feedback study, not an online bandit result.
"""
from copy import deepcopy
import math
import random

from nexus.evolution1.catalogue import digest
from nexus.evolution1.resources import Work

KINDS = ('switch', 'rank_blend')
SCALES = {'pendulum': (1., 1., 8.),
          'acrobot': (1., 1., 1., 1., 4 * math.pi, 9 * math.pi)}


def _integer(value):
    if type(value) is not int or not 0 <= value < 2**32:
        raise ValueError('public_nonnegative_integer_required')
    return value


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('finite_numeric_value_required')
    return float(value)


def _matchings(ids):
    if not ids:
        yield ()
    else:
        first = ids[0]
        for j in range(1, len(ids)):
            for rest in _matchings(ids[1:j] + ids[j+1:]):
                yield ((first, ids[j]),) + rest


def make_plan(family, observations, seed):
    """Minimum-total squared public-distance matching, then one child/pair.

    Exactly 105 matchings for eight resets. Lexicographic tie break; no fitted
    normalization, reward, model parameters or hidden simulator state. Scale
    bounds are fixed public observation-schema constants, not task physics.
    Input IDs are symbolic reset identifiers, NOT environment seeds.
    """
    _integer(seed)
    if family not in SCALES or type(observations) is not list or len(observations) != 8:
        raise ValueError('eight_public_resets_required')
    public = []
    for row in observations:
        if type(row) is not dict or set(row) != {'reset_id', 'observation'}:
            raise ValueError('public_observation_fields_only')
        rid = _integer(row['reset_id'])
        obs = row['observation']
        if type(obs) is not list or len(obs) != len(SCALES[family]):
            raise ValueError('observation_schema')
        public.append({'reset_id': rid, 'observation': [_number(x) for x in obs]})
    public.sort(key=lambda r: r['reset_id'])
    ids = tuple(r['reset_id'] for r in public)
    if len(set(ids)) != 8:
        raise ValueError('duplicate_reset_id')
    scaled = {r['reset_id']: tuple(x/s for x, s in zip(r['observation'], SCALES[family])) for r in public}
    def distance(a, b):
        value = sum((x-y)**2 for x, y in zip(scaled[a], scaled[b]))
        if not math.isfinite(value):
            raise ValueError('nonfinite_public_distance')
        return value
    pairs = min(_matchings(ids), key=lambda p: (sum(distance(a, b) for a, b in p), p))
    # Isolated local RNGs; matching must not consume baseline allocation draws.
    baseline = [*([KINDS[0]]*4), *([KINDS[1]]*4)]
    random.Random(seed).shuffle(baseline)
    blocked = {}
    rng = random.Random(seed ^ 0x52455345)
    for a, b in pairs:
        k = rng.randrange(2)
        blocked[a], blocked[b] = KINDS[k], KINDS[1-k]
    schedules = {'random_balanced': dict(zip(map(str, ids), baseline)),
                 'public_blocked': {str(i): blocked[i] for i in ids}}
    result = dict(version='public_reset_blocks_v1', family=family, seed=seed,
                  public_observations=public, pairs=[list(p) for p in pairs],
                  squared_distance=sum(distance(a, b) for a, b in pairs), schedules=schedules)
    result['sha256'] = digest(result)
    return result


def validate_plan(plan):
    if type(plan) is not dict:
        raise ValueError('invalid_schedule_plan')
    expected = make_plan(plan.get('family'), plan.get('public_observations'), plan.get('seed'))
    if plan != expected or digest(plan) != digest(expected):
        raise ValueError('schedule_plan_derivation_or_hash')
    return expected


def required_paths(plan):
    p = validate_plan(plan)
    return {i: {'parent', *(s[i] for s in p['schedules'].values())}
            for i in p['schedules']['random_balanced']}


def physical_work(plan, query_resets=4):
    """Historical v1 estimate ONLY; unsafe call cap, NOT an allocation bound.

    Reuses D's 1536 rows/decision and 50-call per-step reservation ratio.
    Retained for old preparation replay. Use verified_physical_work instead.
    """
    if query_resets != 4 or type(query_resets) is not int:
        raise ValueError('four_query_resets_fixed')
    paths = sum(map(len, required_paths(plan).values())) + query_resets*3
    return Work(real_steps=paths*200, imagined_transitions=paths*200*1536,
                model_calls=paths*200*50, network_forwards=paths*200*50)


def operation_envelopes():
    """Source-only bounds, not model inference or imagined execution.

    Only switch branches on abs(obs[0])>.25; endpoints and equality cover
    every possible active component. Sum the SAME actual reservation plan.
    """
    from nexus.evolution2.full_policy_source import controllers,operation_plan
    from nexus.evolution2.operator_headroom import operators
    strategies={'parent':controllers()['successor_anchor'],**operators()}
    envelopes={}
    for name,strategy in strategies.items():
        costs=[]
        for dim in (3,6):
            for first in (-1.,-.25,0.,.25,1.):
                obs=[first]+[0.]*(dim-1)
                work=Work()
                for op in operation_plan(strategy,obs,3):work=work.plus(op.cost)
                costs.append(work)
        envelopes[name]=Work(*(max(w.values()[i] for w in costs) for i in range(4)))
    return envelopes


def verified_physical_work(plan):
    """Exact union path count and conservative branch-wise operation bounds."""
    kinds=required_paths(plan);bounds=operation_envelopes();total=Work()
    for name,work in bounds.items():
        paths=sum(name in selected for selected in kinds.values())+4
        total=total.plus(Work(*(v*paths*200 for v in work.values())))
    return total


def maximum_experiment_work():
    """Four models; at most 12 paths/kind/model including shared queries."""
    total=Work()
    for work in operation_envelopes().values():
        total=total.plus(Work(*(v*12*200*4 for v in work.values())))
    return total


def select_paired_parent_gain(plan,panel,condition,bundle):
    """Prespecified secondary: parent=0, children=matched observed gains.

    Reuses the existing training_statistics; identical feedback as raw choice.
    Exact ties retain parent, then switch, then rank blend. No new learner.
    """
    from nexus.evolution2.partial_feedback import training_statistics
    p=validate_plan(plan);rows=revealed_rows(p,panel,condition,bundle)
    c={'training_episodes':[r['episode'] for r in rows]}
    _,_,gains,counts=training_statistics(rows,c,p['family'],bundle,schedule=p['schedules'][condition])
    values={'parent':0.,**gains}
    return dict(version='paired_parent_gain_v1',choice=max(values,key=values.get),
                matched_advantages=values,observed_counts={'parent':8,**counts},
                training_hash=digest(rows))


def revealed_rows(plan, panel, condition, bundle):
    """Validate whole training union then emit a strict reward-only projection.

    No query rows accepted. Unrevealed child feedback and arbitrary nested
    metadata cannot flow into the existing learner through this adapter.
    """
    p = validate_plan(plan)
    _integer(bundle)
    if condition not in p['schedules'] or type(panel) is not list or len(panel) != 8:
        raise ValueError('complete_training_panel_required')
    by_id = {}
    paths = required_paths(p)
    for row in panel:
        if type(row) is not dict or set(row) != {'reset_id', 'paths'}:
            raise ValueError('training_panel_fields_only')
        rid = str(_integer(row['reset_id']))
        if rid in by_id or rid not in paths or set(row['paths']) != paths[rid]:
            raise ValueError('complete_union_grid_required')
        clean = {}
        for k, v in row['paths'].items():
            if type(v) is not dict or set(v) != {'return', 'cpu_s'}:
                raise ValueError('reward_cost_fields_only')
            clean[k] = {'return': _number(v['return']), 'cpu_s': _number(v['cpu_s'])}
            if clean[k]['cpu_s'] < 0:
                raise ValueError('negative_cost')
        by_id[rid] = clean
    output = []
    for rid, kind in p['schedules'][condition].items():
        output.append(dict(family=p['family'], bundle=bundle, role='training', episode=int(rid),
                           training_operator=kind, paths=deepcopy({k: by_id[rid][k] for k in ('parent', kind)})))
    return output


def select_parent_inclusive(plan, panel, condition, bundle):
    """Use the existing three-way raw-mean selector; no new learning rule."""
    from nexus.evolution2.partial_feedback import parent_inclusive_decision
    p = validate_plan(plan)
    rows = revealed_rows(p, panel, condition, bundle)
    config = {'training_episodes': [r['episode'] for r in rows]}
    return parent_inclusive_decision(rows, config, p['family'], bundle,
                                     schedule=p['schedules'][condition])


def validate_proposal(c):
    """Accept only this unregistered proposal; never grant execution authority."""
    expected = dict(version='e3_12f_reset_blocked_proposal_v1',
        status='prepared_not_registered', execution_authorized=False,
        families=['pendulum', 'acrobot'], model_bundles=[0, 1],
        training_resets=8, query_resets=4, steps_per_path=200,
        conditions=['random_balanced', 'public_blocked'],
        primary_selector='parent_inclusive_raw_mean_v1',
        practical_return_margin=1., proposed_time_cap_s=300,
        proposed_real_cap=28800, proposed_imagined_cap=44236800,
        proposed_model_call_cap=1440000, proposed_forward_cap=1440000,
        numerical_environment_seeds=None, numerical_planner_seeds=None,
        numerical_schedule_seeds=None, allocation=None)
    # JSON booleans and numeric strings must not impersonate numeric settings.
    if type(c) is not dict or set(c) != set(expected):
        raise ValueError('exact_proposal_schema')
    if (any(type(c[k]) is not type(v) or c[k] != v for k, v in expected.items())
            or digest(c) != digest(expected)):
        raise ValueError('proposal_settings_or_execution_boundary')
    return {'status': 'superseded_unsafe_call_estimate', 'execution_allowed': False,
            'resource_estimate_safe_for_allocation':False,
            'logical_revealed_training_returns_per_method_per_model': 16,
            'physical_real_step_range': [22400, 28800],
            'new_environment_steps': 0, 'new_model_inference': 0}
