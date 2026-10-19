"""Bridge trusted measured host paths into existing structural mutation credit.

No environment construction or outcome prediction. A reviewed host must own
the paths/receipts; Python dictionaries are not cryptographic attestation.
"""
import math
from nexus.evolution1.resources import ExecutionReport
from nexus.evolution1.catalogue import digest


def observe_measured_pair(generator,parent,child,paths,receipts,protocol,*,return_scale):
    if set(paths)!= {'parent','child'} or set(receipts)!=set(paths):raise ValueError('complete_measured_pair')
    required={'phase','pair_id','context_hash','reset_seed','planner_seed','horizon','planning_cap','checkpoint_sha256','reward_sha256'}
    if set(protocol)!=required or protocol['phase']!='training':raise ValueError('registered_training_pair_only')
    for key in ('context_hash','checkpoint_sha256','reward_sha256'):
        if type(protocol[key]) is not str or len(protocol[key])!=64 or any(c not in '0123456789abcdef' for c in protocol[key]):raise ValueError('measured_pair_provenance')
    outcomes=[]
    for name,strategy in [('parent',parent),('child',child)]:
        path=paths[name];receipt=receipts[name]
        if type(receipt) is not ExecutionReport or receipt.status!='complete_execution' or any(receipt.physical_unknown_upper_bound.values()):raise ValueError('trusted_completed_pair_receipt')
        rewards=path['rewards'];horizon=protocol['horizon']
        if type(horizon) is not int or horizon<1 or len(rewards)!=horizon or receipt.physical_completed_reported.real_steps!=horizon:raise ValueError('complete_charged_real_path')
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in rewards):raise ValueError('finite_actual_rewards')
        if type(path['cpu_s']) not in (int,float) or not math.isfinite(path['cpu_s']) or path['cpu_s']<=0:raise ValueError('measured_cpu_time')
        if path['strategy']!=strategy.fingerprint or any(path[k]!=protocol[k] for k in required):raise ValueError('matched_path_protocol')
        outcomes.append(dict(kind='observed_full_policy_return',phase='training',strategy=strategy.fingerprint,
            pair_id=protocol['pair_id'],context_hash=protocol['context_hash'],reset_seed=protocol['reset_seed'],planner_seed=protocol['planner_seed'],
            horizon=horizon,planning_cap=protocol['planning_cap'],cpu_s=path['cpu_s'],return_value=sum(rewards),event=digest([name,path])))
    for row in outcomes:row['return']=row.pop('return_value')
    return generator.observe_mutation(parent,child,*outcomes,return_scale=return_scale)
