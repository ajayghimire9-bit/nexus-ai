"""Comparable forecast inputs alongside planner_adapter, never reward labels."""
import numpy as np
from nexus.evolution1.resources import Operation,Work
from nexus.evolution2.planner_adapter import score_open_loop


def validate_plans(plans,n_actions):
    if len(plans)!=2 or any(type(k) is not str or not k.isidentifier() for k in plans):raise ValueError('paired_evidence_only')
    shape=None
    for value in plans.values():
        x=np.asarray(value)
        if x.ndim!=2 or x.dtype.kind not in 'iu' or not 1<=x.shape[0]<=16 or not 1<=x.shape[1]<=16 or np.any(x<0) or np.any(x>=n_actions):raise ValueError('common_horizon_actions')
        if shape is not None and x.shape!=shape:raise ValueError('matched_candidate_budgets')
        shape=x.shape
    return shape


def evidence_operations(plans,n_actions,*,forwards_per_call=1):
    n,h=validate_plans(plans,n_actions)
    if type(forwards_per_call) is not int or forwards_per_call<1:raise ValueError('declared_forward_count')
    return tuple(Operation(f'evidence_{name}_{t}','model',Work(imagined_transitions=n,model_calls=1,network_forwards=forwards_per_call))
                 for name in plans for t in range(h))


def planner_evidence(plans,observation,model,reward_fn,*,n_actions,ledger,clock,fingerprint):
    """Caller supplies pre-reserved-plan ledger and trusted frozen fingerprint.

    Proposed sequences must already share a scoring horizon. Generating those
    proposals costs extra and must be charged separately by the study host.
    """
    n,h=validate_plans(plans,n_actions)
    if np.asarray(observation).ndim!=1 or not np.isfinite(np.asarray(observation,dtype=float)).all():raise ValueError('finite_decision_observation')
    if getattr(model,'uses_simulator',False):raise ValueError('frozen_model_only')
    original=fingerprint();out={}
    for name,sequences in plans.items():
        history=[];terminations=[]
        class Recorded:
            def step(self,obs,action):
                ticket=ledger.reserve(f'evidence_{name}_{len(history)}',clock())
                try:
                    nxt,p=model.step(obs,action);nxt=np.asarray(nxt);p=np.asarray(p).reshape(-1)
                    if nxt.shape!=np.asarray(obs).shape or p.shape!=(n,) or not np.isfinite(nxt).all() or not np.isfinite(p).all() or np.any(p<0) or np.any(p>1):raise ValueError('finite_forecast')
                    history.append(nxt.copy().tolist());terminations.append(p.copy().tolist())
                except BaseException:
                    ledger.settle(ticket,'failed',clock());raise
                ledger.settle(ticket,'success',clock());return nxt,p
        try:scores=score_open_loop(Recorded(),observation,np.asarray(sequences),reward_fn)
        finally:
            if fingerprint()!=original:raise ValueError('model_or_context_changed')
        if not np.isfinite(scores).all() or len(history)!=h:raise ValueError('complete_forecast')
        out[name]=dict(kind='forecast_not_observed_return',common_horizon=h,actions=np.asarray(sequences).tolist(),
            scores=scores.tolist(),states=history,termination_estimates=terminations,
            selected_candidate=int(np.argmax(scores)),imagined_transitions=n*h,
            model_disagreement_calibrated=False)
    return out


def evidence_disagreement(first,second):
    """Pure same-action forecast sensitivity, never a failure probability."""
    if set(first)!=set(second):raise ValueError('paired_forecast_conditions')
    out={}
    for name in first:
        a,b=first[name],second[name]
        if a['actions']!=b['actions'] or a['common_horizon']!=b['common_horizon']:raise ValueError('same_action_horizon_required')
        error=np.asarray(a['scores'])-np.asarray(b['scores'])
        if not np.isfinite(error).all():raise ValueError('finite_disagreement')
        out[name]=dict(mean_absolute_reward_forecast_difference=float(np.mean(np.abs(error))),
                       calibrated_probability=False)
    return out
