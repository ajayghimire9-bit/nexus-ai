"""Fresh full-return feedback for the existing AdvantagePredictor.

No controller, collector, dynamics model, memory or proposer implementation.
"""
import itertools
import json
import math
import time

import numpy as np

from nexus.evolution1.catalogue import digest
from nexus.evolution2.generated_strategies import AdvantagePredictor, advantage_features
from nexus.evolution2.observation_memory import FamilyNormalizer, load_source_train_obs
from nexus.core.strategy_memory_decide_bench import family_context, support_from_source
from nexus.evolution2 import full_policy_source as h

MANIFEST=h.ROOT/'artifacts/e3_2_frozen_predictor.json'
PREDICTIONS=h.ROOT/'artifacts/e3_2_predecision_predictions.jsonl'
METHODS=('quality_predictor','shuffled_pair_labels','model_mean','family_mean','global_mean',
         'always_successor','always_rank_blend','uniform')
ESTIMATES=METHODS[:5]


def paired_training(rows,c):
    expected=set(itertools.product(c['families'],c['model_bundles'],range(3),c['controllers']))
    ids=[(r['family'],r['model_bundle'],r['episode'],r['controller']) for r in rows]
    if len(ids)!=24 or set(ids)!=expected:raise ValueError('training_grid_only')
    for r in rows:
        if type(r['model_bundle']) is not int or type(r['episode']) is not int:raise ValueError('training_identity_type')
        if r.get('split')!='training':raise ValueError('evaluation_feedback_forbidden')
        if type(r['return']) not in (int,float) or not math.isfinite(r['return']):raise ValueError('finite_feedback')
        if len(r['steps'])!=200 or not math.isclose(sum(s['reward'] for s in r['steps']),r['return'],abs_tol=1e-9):raise ValueError('complete_training_return')
        if [s['tick'] for s in r['steps']]!=list(range(200)) or any(not math.isfinite(s['reward']) for s in r['steps']):raise ValueError('training_steps')
        seed,base=h.seeds(c,r['family'],r['model_bundle'],r['episode'])
        if r['reset_seed']!=seed or r['planner_base']!=base:raise ValueError('closed_or_wrong_seed_feedback')
    paired=[]
    for f,b,e in itertools.product(c['families'],c['model_bundles'],range(3)):
        group={r['controller']:r for r in rows if (r['family'],r['model_bundle'],r['episode'])==(f,b,e)}
        if len({r['initial_obs_hash'] for r in group.values()})!=1:raise ValueError('unpaired_training_reset')
        public=dict(family=f,model_bundle=b,episode=e,initial_obs=group['successor_anchor']['steps'][0]['obs'])
        values={k:v['return'] for k,v in group.items()}
        paired.append(dict(public=public,returns=values,advantage=values['rank_blend']-values['successor_anchor'],
                           event=digest(dict(public=public,returns=values,reset_seed=group['successor_anchor']['reset_seed']))))
    return paired


def choose(advantage):return 'rank_blend' if advantage>0 else 'successor_anchor'


class FrozenReturnSelector:
    """Trusted host hooks. Updates accept newly collected training rows only."""
    def __init__(self,c,persist=True):
        self.c=c;self.persist=persist;self.ready=False;self.records=[];self.predictors={}

    def features(self,public):
        if set(public)-{'family','model_bundle','episode','initial_obs','completed_real_steps'}:raise ValueError('nonpublic_features')
        f,b=public['family'],public['model_bundle'];obs=np.asarray(public['initial_obs'])
        key=f'{f}:{b}';anchors=tuple(self.anchor_means[key][k]/100. for k in ('successor_anchor','rank_blend'))
        args=(obs,self.supports[key],family_context(f),self.norms[f],anchors)
        return advantage_features(h.controllers()['rank_blend'],*args)-advantage_features(h.controllers()['successor_anchor'],*args)

    def learned_hash(self):
        return digest({k:[m.model[0].tolist(),m.model[1].tolist(),len(m.events),m.fit_calls] for k,m in self.predictors.items()})

    def fit(self,rows):
        if self.ready:raise RuntimeError('frozen_predictor_no_updates')
        start=time.perf_counter();bank=paired_training(rows,self.c)
        self.norms={f:FamilyNormalizer.fit(f,load_source_train_obs(f,(0,1))) for f in self.c['families']}
        self.supports={f'{f}:{b}':support_from_source(f,b,start=0,n=32) for f,b in itertools.product(self.c['families'],self.c['model_bundles'])}
        self.anchor_means={f'{f}:{b}':{k:float(np.mean([x['returns'][k] for x in bank if (x['public']['family'],x['public']['model_bundle'])==(f,b)]))
            for k in self.c['controllers']} for f,b in itertools.product(self.c['families'],self.c['model_bundles'])}
        self.family_means={f:float(np.mean([x['advantage'] for x in bank if x['public']['family']==f])) for f in self.c['families']}
        self.global_mean=float(np.mean([x['advantage'] for x in bank]))
        x=[self.features(r['public']) for r in bank];y=[r['advantage'] for r in bank]
        permutation=np.random.default_rng(31).permutation(12).tolist()
        for mode in ('quality_predictor','shuffled_pair_labels'):
            predictor=AdvantagePredictor()
            for i,r in enumerate(bank):
                predictor.observe(x[i],y[i] if mode=='quality_predictor' else y[permutation[i]],event=r['event'],provenance='revealed_source')
            predictor.predict(x[0]);self.predictors[mode]=predictor
        self.frozen_hash=self.learned_hash();self.ready=True
        self.manifest=dict(training_pairs=bank,feature_rows=[v.tolist() for v in x],feature_dimension=len(x[0]),
            models={k:dict(scale=m.model[0].tolist(),beta=m.model[1].tolist(),fit_calls=m.fit_calls) for k,m in self.predictors.items()},
            anchor_means=self.anchor_means,family_means=self.family_means,global_mean=self.global_mean,shuffle_permutation=permutation,
            learned_hash=self.frozen_hash,training_real_steps=4800,fit_wall_s=time.perf_counter()-start,
            normalizers={f:dict(mean=n.mean.tolist(),std=n.std.tolist(),source_n=n.n) for f,n in self.norms.items()},
            support_sha256={k:digest(dict(obs=s.obs.tolist(),action=s.action.tolist(),next_obs=s.next_obs.tolist())) for k,s in self.supports.items()})
        if self.persist:
            with MANIFEST.open('x') as out:json.dump(self.manifest,out,allow_nan=False);out.write('\n');out.flush()
            with PREDICTIONS.open('x'):pass

    @classmethod
    def restore(cls,c,manifest):
        """Verification only: restore frozen coefficients, no feedback updates/fits."""
        obj=cls(c,persist=False);obj.manifest=manifest
        obj.norms={f:FamilyNormalizer(f,np.asarray(n['mean']),np.asarray(n['std']),len(n['mean']),n['source_n']) for f,n in manifest['normalizers'].items()}
        obj.supports={f'{f}:{b}':support_from_source(f,b,start=0,n=32) for f,b in itertools.product(c['families'],c['model_bundles'])}
        obj.anchor_means=manifest['anchor_means'];obj.family_means=manifest['family_means'];obj.global_mean=manifest['global_mean']
        for name,weights in manifest['models'].items():
            m=AdvantagePredictor();m.model=(np.asarray(weights['scale']),np.asarray(weights['beta']))
            m.x=[np.asarray(row) for row in manifest['feature_rows']]
            m.fit_calls=weights['fit_calls'];m.events={r['event'] for r in manifest['training_pairs']};obj.predictors[name]=m
        obj.frozen_hash=manifest['learned_hash'];obj.ready=True
        if obj.learned_hash()!=obj.frozen_hash:raise ValueError('restored_weight_hash')
        return obj

    def decide(self,public):
        if not self.ready:raise RuntimeError('training_manifest_required')
        if public['episode'] not in (3,4,5,6):raise ValueError('evaluation_reset_required')
        key=(public['family'],public['model_bundle'],public['episode'])
        if any((r['family'],r['model_bundle'],r['episode'])==key for r in self.records):raise ValueError('duplicate_decision')
        if self.persist and h.sha(MANIFEST)!=self.manifest_sha:raise ValueError('manifest_changed')
        x=self.features(public);f,b=key[:2]
        estimates={k:m.predict(x) for k,m in self.predictors.items()}
        estimates.update(model_mean=self.anchor_means[f'{f}:{b}']['rank_blend']-self.anchor_means[f'{f}:{b}']['successor_anchor'],
                         family_mean=self.family_means[f],global_mean=self.global_mean)
        choices={k:choose(v) for k,v in estimates.items()}
        choices.update(always_successor='successor_anchor',always_rank_blend='rank_blend',
                       uniform='rank_blend' if int(digest(('E3.2_uniform',*key))[:8],16)%2 else 'successor_anchor')
        if self.learned_hash()!=self.frozen_hash:raise ValueError('evaluation_updated_predictor')
        record={**public,'estimates':estimates,'choices':choices,'feature_sha256':digest(x.tolist()),'learned_hash':self.frozen_hash}
        if self.persist:
            with PREDICTIONS.open('a') as out:out.write(json.dumps(record,allow_nan=False)+'\n');out.flush()
        self.records.append(record);return record

    @property
    def manifest_sha(self):
        # Hash the immutable expected bytes rather than trusting a changed file.
        import hashlib
        return hashlib.sha256((json.dumps(self.manifest,allow_nan=False)+'\n').encode()).hexdigest()


def analyze_selection(p,c):
    h.validate_result(p,c)
    if any(r.get('split')!=('training' if r['episode']<3 else 'evaluation') for r in p['episodes']):raise ValueError('phase_identity')
    records=p['selection_decisions'];expected=set(itertools.product(c['families'],c['model_bundles'],range(3,7)))
    ids=[(r['family'],r['model_bundle'],r['episode']) for r in records]
    if len(ids)!=16 or set(ids)!=expected:raise ValueError('prediction_grid')
    outcomes=[]
    for i,r in enumerate(records):
        if r['completed_real_steps']!=4800+i*400 or set(r['choices'])!=set(METHODS):raise ValueError('predecision_or_method_grid')
        if set(r['estimates'])!=set(ESTIMATES) or any(type(v) not in (int,float) or not math.isfinite(v) for v in r['estimates'].values()):raise ValueError('invalid_estimate')
        f,b,e=ids[i]
        episodes={x['controller']:x for x in p['episodes'] if (x['family'],x['model_bundle'],x['episode'])==(f,b,e)}
        if episodes['successor_anchor']['steps'][0]['obs']!=r['initial_obs']:raise ValueError('public_observation')
        values={k:x['return'] for k,x in episodes.items()};best=max(values.values());truth=values['rank_blend']-values['successor_anchor']
        if any(v not in c['controllers'] for v in r['choices'].values()):raise ValueError('invalid_selected_controller')
        outcomes.append(dict(family=f,model_bundle=b,episode=e,actual_advantage=truth,
            returns={m:values[r['choices'][m]] for m in METHODS},regret={m:best-values[r['choices'][m]] for m in METHODS},
            advantage_error={m:abs(pred-truth) for m,pred in r['estimates'].items()},
            sign_correct={m:(pred>0)==(truth>0) for m,pred in r['estimates'].items()}))
    by_family={};screen={}
    for f in c['families']:
        models={str(b):{m:float(np.mean([r['returns'][m] for r in outcomes if (r['family'],r['model_bundle'])==(f,b)])) for m in METHODS} for b in c['model_bundles']}
        means={m:float(np.mean([v[m] for v in models.values()])) for m in METHODS}
        gains={m:means['quality_predictor']-means[m] for m in METHODS if m!='quality_predictor'}
        screen[f]=all(v>=1. for v in gains.values()) and all(v['quality_predictor']>v['model_mean'] for v in models.values())
        by_family[f]=dict(per_model_returns=models,mean_returns=means,predictor_minus_baselines=gains,
            mean_regret={m:float(np.mean([r['regret'][m] for r in outcomes if r['family']==f])) for m in METHODS},
            advantage_mae={m:float(np.mean([r['advantage_error'][m] for r in outcomes if r['family']==f])) for m in records[0]['estimates']},
            sign_accuracy={m:float(np.mean([r['sign_correct'][m] for r in outcomes if r['family']==f])) for m in records[0]['estimates']})
    return dict(outcomes=outcomes,by_family=by_family,point_screen_by_family=screen,point_screen=all(screen.values()),
                independent_model_count_per_family=2,sign_and_two_arm_ranking_are_dependent=True,
                regret_reduction_equals_return_gain=True,general_control_or_learning_to_learn_established=False)
