"""E3.12F profile over the SAME panel validator, selector and metered runner.

No environment/model construction here. Runtime registration remains absent.
"""
from copy import deepcopy
import itertools

from nexus.evolution1.catalogue import digest
from nexus.evolution2 import reset_blocks as blocks
from nexus.evolution2 import operator_headroom as panel
from nexus.evolution2.mutation_control import seed_pair, check_real_step

METHODS = ()  # Raw selectors only; no learner may receive the union feedback.
KINDS = panel.KINDS
operators = panel.operators
CONDITIONS = ('random_balanced', 'public_blocked')


def validate_config(c, *, registered=False):
    fields = {'version', 'status', 'execution_authorized', 'families', 'model_bundles',
              'training_episodes', 'evaluation_episodes', 'env_seed_base', 'planner_seed_base',
              'schedule_seeds', 'practical_margin', 'time_cap_s', 'real_cap', 'imagined_cap',
              'model_call_cap', 'network_forward_cap', 'checkpoint_inventory', 'checkpoint_inventory_sha256'}
    if type(c) is not dict or set(c) != fields:
        raise ValueError('reset_blocked_config_schema')
    fixed = dict(version='e3_12f_reset_blocked_runtime_v1', families=['pendulum', 'acrobot'],
        model_bundles=[0, 1], training_episodes=list(range(8)), evaluation_episodes=list(range(8, 12)),
        practical_margin=1., time_cap_s=300, real_cap=28800, imagined_cap=44236800,
        model_call_cap=1440000, network_forward_cap=1440000,
        checkpoint_inventory='artifacts/e3_9_planner_evidence_readiness.json',
        checkpoint_inventory_sha256='58a9c11758e0a13d09f68c35697374ecbad1b19c9755780436fae897a931c0f9')
    if digest({k:c[k] for k in fixed}) != digest(fixed):
        raise ValueError('reset_blocked_fixed_recipe')
    if c['status'] == 'prepared_not_registered':
        if c['execution_authorized'] is not False or any(c[k] is not None for k in ('env_seed_base','planner_seed_base','schedule_seeds')):
            raise ValueError('unregistered_template_only')
        if registered:
            raise ValueError('fresh_registration_and_authorization_required')
        return False
    if c['status'] != 'registered' or c['execution_authorized'] is not True:
        raise ValueError('fresh_registration_and_authorization_required')
    for k in ('env_seed_base', 'planner_seed_base'):
        blocks._integer(c[k])
        if c[k] + 160000 >= 2**32:
            raise ValueError('registered_seed_overflow')
    keys = {f'{f}:{b}' for f,b in itertools.product(c['families'],c['model_bundles'])}
    if type(c['schedule_seeds']) is not dict or set(c['schedule_seeds']) != keys:
        raise ValueError('complete_schedule_seed_grid')
    values = list(c['schedule_seeds'].values())
    for value in values: blocks._integer(value)
    if len(set(values)) != len(values):
        raise ValueError('unique_schedule_seed_roles')
    return True


def requested_seeds(c):
    validate_config(c, registered=True)
    from nexus.evolution2.mutation_control import requested_seeds as base_seeds
    previous = base_seeds(c)
    schedules = set(c['schedule_seeds'].values())
    if previous & schedules: raise ValueError('schedule_seed_role_collision')
    return previous | schedules


def plan_for(p,c,f,b):
    key = f'{f}:{b}'
    plan = blocks.validate_plan(p['reset_plans'][key])
    if (plan['family'] != f or plan['seed'] != c['schedule_seeds'][key]
            or [r['reset_id'] for r in plan['public_observations']] != c['training_episodes']):
        raise ValueError('registered_reset_plan')
    return plan


def path_labels(row,p,c):
    plan = plan_for(p,c,row['family'],row['bundle'])
    if row['role'] == 'training':
        public = next(r['observation'] for r in plan['public_observations'] if r['reset_id'] == row['episode'])
        if row['initial_observation'] != public: raise ValueError('reset_observation_reproduction')
        return blocks.required_paths(plan)[str(row['episode'])]
    return {'parent',*KINDS}


def decide(rows,c,f,b,plan):
    # Filter on role BEFORE reading paths; query dictionaries can be opaque.
    training = [r for r in rows if (r['family'],r['bundle'],r['role']) == (f,b,'training')]
    projection = [dict(reset_id=r['episode'],paths={k:{'return':v['return'],'cpu_s':v['cpu_s']}
                   for k,v in r['paths'].items()}) for r in training]
    return {condition: blocks.select_parent_inclusive(plan,projection,condition,b) for condition in CONDITIONS}


def planned_real_steps(p,c):
    return sum(blocks.physical_work(plan_for(p,c,f,b)).real_steps
               for f,b in itertools.product(c['families'],c['model_bundles']))


def _check_seal(p,key,kind,value):
    manifest = p[kind+'_manifests'][key]
    if set(manifest) != {'path','sha256','content_hash'} or manifest['content_hash'] != digest(value):
        raise ValueError('immutable_'+kind+'_manifest')
    if (type(manifest['sha256']) is not str or len(manifest['sha256']) != 64
            or any(ch not in '0123456789abcdef' for ch in manifest['sha256'])):
        raise ValueError('manifest_file_sha256_required')


def validate(p,c):
    validate_config(c,registered=True)
    for row in p['rows']:
        if type(row['bundle']) is not int or type(row['episode']) is not int:
            raise ValueError('integer_registered_row_ids')
    for model in p['models']:
        if type(model['bundle']) is not int:raise ValueError('integer_registered_model_ids')
    counts={'real_steps','imagined_transitions','model_calls','network_forwards'}
    for field in ('completed','reserved','unknown_upper'):
        work=p['resources'][field]
        if set(work)!=counts or any(type(v) is not int or v<0 for v in work.values()):
            raise ValueError('integer_complete_resource_grid')
    keys = {f'{f}:{b}' for f,b in itertools.product(c['families'],c['model_bundles'])}
    for name in ('reset_plans','plan_manifests','sealed_decisions','decision_manifests'):
        if set(p[name]) != keys: raise ValueError('complete_'+name+'_grid')
    decisions = {}
    for f,b in itertools.product(c['families'],c['model_bundles']):
        key=f'{f}:{b}';plan=plan_for(p,c,f,b)
        decisions[key]=decide(p['rows'],c,f,b,plan)
        if p['sealed_decisions'][key] != decisions[key]: raise ValueError('pre_query_decision_seal')
        _check_seal(p,key,'plan',plan);_check_seal(p,key,'decision',decisions[key])
    def replay(rows,config):
        for row in rows:
            if row['before'] != {} or row['after'] != {}: raise ValueError('union_feedback_cannot_update_learner')
            if row['role']=='evaluation' and row['decision']!=decisions[f"{row['family']}:{row['bundle']}"]:
                raise ValueError('frozen_query_decision')
        return {key:{} for key in keys}
    return panel.validate(p,c,labels=lambda r,_:path_labels(r,p,c),replay=replay,
                          planned_real_steps=planned_real_steps(p,c))


def analyze(p,c):
    validate(p,c)
    families={}
    for f in c['families']:
        models=[]
        for b in c['model_bundles']:
            rows=[r for r in p['rows'] if (r['family'],r['bundle'],r['role'])==(f,b,'evaluation')]
            choices=p['sealed_decisions'][f'{f}:{b}'];cases=[]
            for r in rows:
                values={k:panel.number(v['return']) for k,v in r['paths'].items()}
                cases.append(dict(episode=r['episode'],returns={
                    **{k:values[choices[k]['choice']] for k in CONDITIONS},
                    'parent':values['parent'],'fixed_switch':values['switch'],'fixed_blend':values['rank_blend'],
                    'uniform_expected':(values['switch']+values['rank_blend'])/2}))
            means={k:sum(x['returns'][k] for x in cases)/4 for k in cases[0]['returns']}
            models.append(dict(bundle=b,mean_returns=means,choices=deepcopy(choices),query_cases=cases))
        contrasts={name:panel.paired_contrast(models,'public_blocked',name)
                   for name in ('random_balanced','parent','fixed_switch','fixed_blend','uniform_expected')}
        primary=contrasts['random_balanced']
        passed=primary['mean']>=c['practical_margin'] and primary['ci95'][0]>0 and all(v>0 for v in primary['per_model'])
        families[f]=dict(models=models,contrasts=contrasts,screen_passed=bool(passed))
    return dict(families=families,
        label='exploratory_reset_blocking_screen_passed' if all(x['screen_passed'] for x in families.values()) else 'reset_blocking_not_established',
        statistical_unit='two pretrained models per family; df1 paired t intervals; episodes are not model replications',
        physical_real_steps=planned_real_steps(p,c),revealed_training_returns_per_method_per_model=16,
        dependent_evidence='Shared query paths; identical choices imply identical returns. Uniform is analytic, not an extra rollout.')
