"""Distinct vetted edits over SAME AdaptiveState, no generated code or worlds."""
import copy
import json
import torch
from nexus.evolution1.catalogue import digest
from .plasticity import correction

TOLERANCE=1e-5


def parameters(state):
    return dict(blocks={k:v.tolist() for k,v in state.blocks.items()},skills=copy.deepcopy(state.skills))


def install(state,p):
    state.blocks={k:torch.tensor(v) for k,v in p['blocks'].items()}
    state.skills=copy.deepcopy(p['skills'])


def value(p,channel,x,key):
    y=x@torch.tensor(p['blocks'][channel])
    for s in p['skills']:
        if s['channel']==channel and s['key']==key:y=y+x@torch.tensor(s['theta'])
    return y


def propose(state,channel,key,kind):
    if kind not in ('keep','repair','add_skill','merge'):raise ValueError('vetted_edit_required')
    original=parameters(state);candidate=copy.deepcopy(original);theta=state.blocks[channel]
    matching=[s for s in state.skills if s['channel']==channel and s['key']==key]
    support=[r for r in state.anchors[channel] if r['key']==key]
    guard=[r for r in state.anchors[channel] if r['key']!=key]
    sx,sy=state.tensors(channel,support);gx,_=state.tensors(channel,guard)
    fits=0
    if kind=='add_skill':
        if matching:raise ValueError('scope_exists_no_replacement')
        if len(state.skills)>=2:raise ValueError('scoped_skill_cap')
        if not support:raise ValueError('support_required')
        residual=torch.zeros_like(theta)
        for x,y in zip(sx,sy):
            residual=correction(residual,x,y-x@theta,x.new_zeros(0,len(theta)),torch.ones_like(theta));fits+=1
        candidate['skills'].append(dict(channel=channel,key=key,theta=residual.tolist()))
    elif kind=='repair':
        if not support:raise ValueError('support_required')
        # Keep every scoped vector exactly,including the repaired context's.
        scoped=sum((torch.tensor(s['theta']) for s in matching),torch.zeros_like(theta))
        repaired=theta.clone()
        for x,y in zip(sx,sy):
            repaired=correction(repaired,x,y-x@scoped,gx,torch.ones_like(theta));fits+=1
        candidate['blocks'][channel]=repaired.tolist()
    elif kind=='merge':
        if len(matching)!=1:raise ValueError('one_existing_scope_required')
        # Algebraic absorption. No fitting,query labels or new skills.
        delta=torch.tensor(matching[0]['theta'])
        candidate['blocks'][channel]=(theta+delta).tolist()
        candidate['skills']=[s for s in candidate['skills'] if not(s['channel']==channel and s['key']==key)]
        for s in candidate['skills']:
            if s['channel']==channel:s['theta']=(torch.tensor(s['theta'])-delta).tolist()
    if not all(torch.isfinite(torch.tensor(v)).all() for v in candidate['blocks'].values()):raise ValueError('nonfinite_edit')
    drift=max((abs(float(value(candidate,channel,torch.tensor(r['x']),r['key'])-value(original,channel,torch.tensor(r['x']),r['key']))) for r in guard),default=0.)
    # Scoped addition has global algebraic isolation; repair/merge have a finite
    # anchor preservation guarantee only. Unknown-context behavior may change.
    allowed=drift<=TOLERANCE
    if kind=='merge':
        for r in support:
            x=torch.tensor(r['x'])
            allowed &= abs(float(value(candidate,channel,x,key)-value(original,channel,x,key)))<=TOLERANCE
    state.work['structural_fits']+=fits
    state.work['linear_solves']+=fits*bool(len(gx) and kind=='repair')
    return dict(kind=kind,channel=channel,key=key,parent=digest(original),parameters=candidate,
        allowed=bool(allowed),known_prediction_drift=drift,training_updates=fits,
        description_bytes=len(json.dumps(candidate,sort_keys=True,separators=(',',':')).encode()))


def commit(state,proposal):
    if not proposal['allowed'] or proposal['parent']!=digest(parameters(state)):raise ValueError('unsafe_or_stale_edit')
    if proposal['kind']=='keep':return None
    before=parameters(state);install(state,proposal['parameters'])
    record=dict(kind=proposal['kind'],channel=proposal['channel'],key=proposal['key'],before=before,
                after=digest(parameters(state)),id=digest(dict(parent=proposal['parent'],kind=proposal['kind'],steps=state.steps)))
    state.undo=(state.undo+[record])[-4:]
    return record['id']


def rollback(state):
    if not state.undo:return dict(status='nothing_to_rollback')
    record=state.undo[-1]
    if record['after']!=digest(parameters(state)):raise ValueError('rollback_would_overwrite_subsequent_learning')
    install(state,record['before']);state.undo.pop();state.reviews={}
    # Evidence,step counts and spent work are never rolled back.
    return dict(status='rolled_back',edit_id=record['id'],kind=record['kind'])


def review(state,channel,key):
    support=[r for r in state.anchors[channel] if r['key']==key]
    query=[r for r in state.development[channel] if r['key']==key]
    signature=lambda:digest(dict(channel=channel,key=key,support=support,query=query,parameters=parameters(state)))
    tag=signature()
    if tag in state.reviews:return dict(copy.deepcopy(state.reviews[tag]),cached_review=True)
    if len(support)<3 or len(query)<2:return dict(status='needs_separate_development',adopted='keep')
    qx,qy=state.tensors(channel,query);proposals={};rows=[]
    for kind in ('keep','repair','add_skill','merge'):
        try:p=propose(state,channel,key,kind)
        except ValueError as e:
            rows.append(dict(edit=kind,eligible=False,reason=str(e),bytes_added=0,training_updates=0));continue
        error=float((value(p['parameters'],channel,qx,key)-qy).square().mean())
        score=-error-.0001*p['training_updates']-.000001*p['description_bytes']
        rows.append(dict(edit=kind,eligible=p['allowed'],query_error=error,score=score,
            known_prediction_drift=p['known_prediction_drift'],training_updates=p['training_updates'],
            description_bytes=p['description_bytes'],bytes_added=p['description_bytes']-len(json.dumps(parameters(state),sort_keys=True,separators=(',',':')).encode())))
        proposals[kind]=p
    keep=rows[0];eligible=[r for r in rows if r['eligible'] and (r['edit']=='keep' or
        r['query_error']<=keep['query_error']-(0. if r['edit']=='merge' else .01))]
    winner=max(eligible,key=lambda r:r['score']);adopted=winner['edit']
    edit_id=commit(state,proposals[adopted])
    result=dict(status='development_only_edit_check',adopted=adopted,candidates=rows,edit_id=edit_id,cached_review=False)
    # Cache under post-promotion parameters: another identical review cannot
    # repeatedly refit,promote or manufacture additional development evidence.
    state.reviews[signature()]=copy.deepcopy(result)
    if len(state.reviews)>24:state.reviews.pop(next(iter(state.reviews)))
    return result
