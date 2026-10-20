"""Training-bank diagnostic of future-learning credit,not transfer evidence.

Reuses AdaptiveState/vetted edits and OuterSeedMeta. Source labels only. Every
policy gets 32 proposal opportunities and eight unopened source-bank tasks.
"""
import random
import torch
from .adaptive_state import AdaptiveState
from .structural_edits import propose,commit,parameters,install,value
from .plasticity import correction
from .grounded_meta import OuterSeedMeta
from .surprise import AssessmentLedger


def trial(x,y,kind,index):
    s=AdaptiveState();x=torch.nn.functional.pad(x,(0,62-x.shape[1]))
    # Same public observable features and scaled old anchor for all methods.
    # This source-only diagnostic does not replace deployed reward features.
    s.anchors['reward']=[dict(x=x[i].tolist(),y=float(y[i]),ref=f'{index*100+i:064x}',key='new') for i in range(3)]
    if index%2:s.skills=[dict(channel='reward',key='new',theta=(x[0]*y[0]/x[0].square().sum().clamp(min=1e-6)).tolist())]
    original=parameters(s);p=None;accepted=False;reason=None;ledger=AssessmentLedger();token=ledger.reserve([f'{index}/3',f'{index}/4'],phase='fresh_development')
    try:
        p=propose(s,'reward','new',kind)
        keep=float((value(original,'reward',x[3:5],'new')-y[3:5]).square().mean())
        candidate=float((value(p['parameters'],'reward',x[3:5],'new')-y[3:5]).square().mean())
        decision=ledger.assess(token,keep_loss=keep,candidate_loss=candidate,forgetting=p['known_prediction_drift'],cost=1+p['training_updates'])
        if p['allowed'] and decision['accept']:commit(s,p);accepted=kind!='keep'
    except ValueError as e:reason=str(e)
    # Future lesson outcomes5:7 and probe7:9 never entered proposal/acceptance.
    def future(params):
        temp=AdaptiveState();install(temp,params);theta=temp.blocks['reward']
        scoped=sum((torch.tensor(v['theta']) for v in temp.skills if v['key']=='new'),torch.zeros(62))
        for i in (5,6):theta=correction(theta,x[i],y[i]-x[i]@scoped,x[:3],torch.ones(62))
        return float((x[7:]@(theta+scoped)-y[7:]).square().mean())
    before=future(original);after=future(parameters(s));forget=max(0.,float((value(parameters(s),'reward',x[:3],'old')-y[:3]).square().mean()-(value(original,'reward',x[:3],'old')-y[:3]).square().mean()))
    return dict(future_error_before=before,future_error_after=after,forgetting=forget,cost=float(1+(p['training_updates'] if p else 0)+4),accepted=accepted,reason=reason)


def evaluate(x,base,y,check):
    result={};actions=('keep','repair','add_skill','merge')
    for mode in ('adaptive','random','fixed','historical_best'):
        meta=OuterSeedMeta();rng=random.Random(6411);rows=[]
        for i in range(40):
            check();training=i<32
            if mode=='adaptive':action=meta.choose_edit(rng,explore=training)
            elif mode=='random':action=rng.choice(actions)
            elif mode=='fixed':action='repair'
            else:
                action=actions[i%4] if i<8 else max(actions,key=lambda a:meta.controller.predicted_kind_value((),'edit/'+a))
            sl=slice(i*9,(i+1)*9);row=trial(x[sl],y[sl]-base[sl],action,i)
            receipt={k:v for k,v in row.items() if k!='reason'};receipt['id']=f'{mode}/{i}'
            if training:reward=meta.reveal_edit(action,receipt,phase='source_training')
            else:reward=row['future_error_before']-row['future_error_after']-row['forgetting']-.0001*row['cost']
            rows.append(dict(task=i,phase='source_training' if training else 'heldout_source_bank',action=action,reward=reward,**row))
        result[mode]=dict(rows=rows,heldout_mean_reward=sum(r['reward'] for r in rows[32:])/8,source_journal_entries=len(meta.journal.snapshot()))
    return dict(protocol='32_source_proposals_then_8_heldout_source_tasks_same_one_decoder',policies=result,real_new_collection=0,heldout_feedback_updates=0)
