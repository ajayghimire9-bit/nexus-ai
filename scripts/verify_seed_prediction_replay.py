"""Independent stdlib ranking arithmetic; no neural imports or new execution."""
import hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    raw=(ROOT/'artifacts/seed_contract_study.json').read_bytes();study=json.loads(raw)
    replay=json.loads((ROOT/'artifacts/seed_contract_prediction_replay.json').read_text())
    if replay['declared_complete'] is not True or replay['parent_result_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('replay_provenance')
    states={s['seed']:s for s in study['ranking']};expected=[(m['identity'],s['seed']) for m in study['models'] for s in study['ranking']]
    if [(r['identity'],r['seed']) for r in replay['rows']]!=expected:raise ValueError('replay_grid')
    maximum=0.
    for row in replay['rows']:
        p=row['scores'];s=states[row['seed']];y=[o['reward'] for o in s['outcomes']]
        if len(p)!=9 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p):raise ValueError('finite_scores')
        choice=max(range(9),key=lambda i:p[i]);pairs=[(i,j) for i in range(9) for j in range(i) if abs(y[i]-y[j])>1e-8]
        accuracy=sum(1 if (p[i]-p[j])*(y[i]-y[j])>0 else .5 if p[i]==p[j] else 0 for i,j in pairs)/len(pairs) if pairs else 1.
        metrics=dict(selected=choice,optimal=max(y)-y[choice]<1e-8,regret=max(y)-y[choice],pairwise_accuracy=accuracy,reward_mae=sum(abs(a-b) for a,b in zip(p,y))/9,score_range=max(p)-min(p),uniform_expected_regret=max(y)-sum(y)/9)
        old=s['models'][row['identity']]['reward'];maximum=max(maximum,max(abs(metrics[k]-old[k]) for k in metrics))
    if maximum>1e-7 or replay['real_steps']!=0 or replay['imagined_transitions']!=len(expected)*9:raise ValueError('arithmetic_or_accounting')
    print(json.dumps(dict(verified_rows=len(expected),maximum_metric_difference=maximum,new_model_calls=0,new_world_steps=0)))
