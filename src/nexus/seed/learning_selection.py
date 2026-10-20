"""Costed teaching/edit choices through SAME OuterSeedMeta and AdaptiveState."""
import random
import torch
from .adaptive_state import AdaptiveState
from .structural_edits import propose,commit,value
from nexus.evolution1.catalogue import digest


def episode(lesson,controller,meta,mode,*,training=False):
    if mode not in ('adaptive','random','fixed'):raise ValueError('selector_baseline')
    s=AdaptiveState(controller);rng=random.Random(lesson['seed']+877);trace=[];word=lesson['word'];labels=0
    # All methods see same unlabelled pool. Scale uses no query observations.
    scale=lesson['sx'].square().mean(0).sqrt().clamp(min=.01)*53**.5
    sx=lesson['sx']/scale;query=lesson['qx']/scale
    hidden_x=query[8:];hidden_y=torch.tensor(lesson['qy'][8:]).float()-.5
    probes=query[:8];py=torch.tensor(lesson['qy'][:8]).float()-.5
    before=float((s.predict('meaning',hidden_x,word)-hidden_y).square().mean())
    for i in range(8):
        eligible=['ask','test_concept','keep']
        support=[r for r in s.anchors['meaning'] if r['key']==word];development=s.development['meaning']
        if len(support)>=3 and len(development)>=2:
            eligible.append('repair')
            if not s.skills:eligible.append('add_skill')
        action='ask' if mode=='fixed' else rng.choice(eligible) if mode=='random' else meta.choose_learning(eligible,rng,explore=training)
        probe_before=float((s.predict('meaning',probes[i],word)-py[i]).square())
        compute_before=s.work['structural_fits']+s.work['actual_updates'];used=0
        if action in ('ask','test_concept'):
            s.update('meaning',sx[i],float(lesson['sy'][i]),digest((lesson['seed'],i)),key=word,assessment_only=action=='test_concept');used+=1
        elif action in ('repair','add_skill'):
            p=propose(s,'meaning',word,action)
            qx,qy=s.tensors('meaning',development)
            current=float((s.predict('meaning',qx,word)-qy).square().mean())
            proposed=float((value(p['parameters'],'meaning',qx,word)-qy).square().mean())
            if p['allowed'] and proposed<current-.01:commit(s,p)
        probe_after=float((s.predict('meaning',probes[i],word)-py[i]).square())
        used+=1;labels+=used # probe is actually revealed/costed,never fitted
        compute=s.work['structural_fits']+s.work['actual_updates']-compute_before
        receipt=dict(id=digest((lesson['seed'],mode,i)),probe_error_before=probe_before,probe_error_after=probe_after,labels=used,compute=compute)
        if training and mode=='adaptive':meta.reveal_learning(action,receipt,phase='source_training')
        trace.append(dict(action=action,eligible=eligible,receipt=receipt))
        if action=='keep':break
    final=float((s.predict('meaning',hidden_x,word)-hidden_y).square().mean())
    cost=labels+.1*(s.work['structural_fits']+s.work['actual_updates'])
    return dict(seed=lesson['seed'],mode=mode,trace=trace,labels=labels,compute=dict(s.work),
        hidden_query_rows=len(hidden_y),initial_query_mse=before,final_query_mse=final,
        improvement_per_cost=(before-final)/cost,cost=cost,
        hidden_query_used_for_learning=False,teaching_label_cap=16,decision_cap=8)
