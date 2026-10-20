"""Repository-only verification,hash audit and reproducible summary. No torch."""
import hashlib
import json
from pathlib import Path
import statistics as st
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.learning_validation_audit import validate,interval,resource_bound


def verify(root=ROOT):
    root=Path(root);rawpath=root/'artifacts/seed_learning_validation.json';r=json.loads(rawpath.read_text());c=json.loads((root/'configs/seed_learning_validation.json').read_text())
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if r['declared_complete'] is not True or r['config_sha256']!=sha(root/'configs/seed_learning_validation.json'):raise ValueError('complete_locked_result_required')
    if sha(root/c['parent_model'])!=c['parent_sha256']:raise ValueError('parent_checkpoint_hash')
    for m in r['controllers']:
        if sha(root/m['checkpoint'])!=m['sha256']:raise ValueError('controller_checkpoint_hash')
    validate(r,c)
    verified_rank_cells=0;maximum_ranking_difference=0.
    for model in r['controllers']:
        for split,tasks in model['curves'].items():
            for i,task in enumerate(tasks):
                truths=r['tasks'][split][i]['records']['query']
                for rows in task['methods'].values():
                    for row in rows:
                        for t,rank in zip(truths,row['ranking']):
                            p=rank['predicted'];y=t['actual'];choice=max(range(9),key=lambda j:p[j]);m=rank['metrics']
                            if m['selected']!=choice or m['optimal']!=(max(y)-y[choice]<1e-8):raise ValueError('independent_choice_arithmetic')
                            pairs=[(a,b) for a in range(9) for b in range(a) if abs(y[a]-y[b])>1e-8]
                            accuracy=sum(1. if (p[a]-p[b])*(y[a]-y[b])>0 else .5 if p[a]==p[b] else 0 for a,b in pairs)/len(pairs) if pairs else 1.
                            expected=dict(regret=max(y)-y[choice],pairwise_accuracy=accuracy,score_range=max(p)-min(p),reward_mae=st.mean(abs(a-b) for a,b in zip(p,y)),uniform_expected_regret=max(y)-st.mean(y))
                            maximum_ranking_difference=max(maximum_ranking_difference,max(abs(expected[k]-m[k]) for k in expected));verified_rank_cells+=1
    if maximum_ranking_difference>1e-7:raise ValueError('independent_rank_arithmetic')
    result=dict(schema='seed_learning_validation_analysis_v1',raw_sha256=sha(rawpath),execution_sha=r['execution_sha'],
        screens=r['screens'],independent_ranking_arithmetic=dict(cells=verified_rank_cells,maximum_error=maximum_ranking_difference),resources=dict(costs=r['costs'],total_authored_interactions=sum(r['costs'].values()),model_work=r['model_work'],update_work=r['update_work'],body_wall_s=r['wall_s'],session_used_s=r['session_used_s'],session_remaining_s=r['session_remaining_s'],worst_case_bound=resource_bound(c)),budgets={},semantics={},selection={},control={})
    for k in c['budgets']:
        result['budgets'][str(k)]={method:st.mean(row['query_mse'] for m in r['controllers'] for t in m['curves']['audit'] for row in t['methods'][method] if row['budget']==k) for method in ('learned','fixed','replay','none','neutral')}
    for kind in ('unary','relation'):
        result['semantics'][kind]={}
        for k in c['budgets']:
            cell={}
            for method in ('learned','fixed','replay','none','symbolic'):
                metrics=[row['methods'][method] for m in r['meaning'] for t in m['tasks'] if t['kind']==kind for row in t['rows'] if row['budget']==k]
                cell[method]=dict(accuracy=st.mean(v['correct']/v['total'] for v in metrics),coverage=st.mean(1-v['abstentions']/v['total'] for v in metrics),evaluated_examples=sum(v['total'] for v in metrics))
            result['semantics'][kind][str(k)]=cell
    result['semantics']['instructions']={str(k):{name:st.mean(row[name] for m in r['meaning'] for row in m['instructions']['rows'] if row['budget']==k) for name in ('neural_exact','symbolic_exact')} for k in c['budgets']}
    for method in ('adaptive','random','fixed'):
        rows=[t for m in r['selection'] for t in m['policies'][method]]
        result['selection'][method]={k:st.mean(t[k] for t in rows) for k in ('final_query_mse','improvement_per_cost','labels','cost')}
        result['selection'][method]['operations']={op:sum(t['action']==op for row in rows for t in row['trace']) for op in ('ask','test_concept','repair','add_skill','keep')}
    a=result['selection']['adaptive']
    result['selection']['passed']=all(a['final_query_mse']<=result['selection'][b]['final_query_mse'] and a['improvement_per_cost']>=result['selection'][b]['improvement_per_cost']*1.1 and a['improvement_per_cost']>0 for b in ('random','fixed'))
    for method in ('learned','fixed','replay','none','frozen','grid'):
        episodes=[e for task in r['control'].values() for name,rows in task.items() if name==method or name.endswith('/'+method) for e in rows]
        result['control'][method]=dict(episodes=len(episodes),goal_rate=st.mean(e['success'] for e in episodes),mean_return=st.mean(e['return_sum'] for e in episodes))
    result['transfer']=r['transfer']
    result['decision']='learning_and_actions_not_established' if not all(r['screens'][k]['passed'] for k in ('learning','actions')) else 'object_development_screens_passed'
    return result


if __name__=='__main__':print(json.dumps(verify(),indent=2))
