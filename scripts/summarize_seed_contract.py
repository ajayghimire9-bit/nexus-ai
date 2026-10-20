"""Saved-data summaries; no world/model execution and no posthoc selection."""
import json
import math
from pathlib import Path
import statistics as st
ROOT=Path(__file__).resolve().parents[1]


def interval(values):
    mean=st.mean(values);half=4.302652729*st.stdev(values)/math.sqrt(3)
    return dict(mean=mean,lo=mean-half,hi=mean+half,paired_values=values,unit='training_seed_within_recipe',df=2)


def summarize(r):
    c=r['config'];result=dict(recipes={},language=r['language'],references={k:dict(mean_return=st.mean(e['return_sum'] for e in rows),successes=sum(e['success'] for e in rows)) for k,rows in r['references'].items()})
    for recipe in c['recipes']:
        cell={};ids=lambda cond:[f'{recipe}_{s}_{cond}' for s in c['model_seeds']]
        ranking=lambda identity:st.mean(s['models'][identity]['reward']['regret'] for s in r['ranking'])
        returns=lambda identity,p:st.mean(e['return_sum'] for e in r['control'][identity][p])
        for condition in c['conditions']:
            names=ids(condition)
            cell[condition]=dict(regret=st.mean(ranking(i) for i in names),optimal_rate=st.mean(s['models'][i]['reward']['optimal'] for s in r['ranking'] for i in names),pixels_mae=st.mean(s['models'][i]['pixels_non_goal_mae'] for s in r['ranking'] for i in names),structured_mae=st.mean(s['models'][i]['structured_non_goal_mae'] for s in r['ranking'] for i in names),
                control={p:dict(mean_return=st.mean(returns(i,p) for i in names),successes=sum(e['success'] for i in names for e in r['control'][i][p]),episodes=len(names)*c['control_episodes']) for p in ('pruned','unpruned')},
                pruning_effect=interval([returns(i,'pruned')-returns(i,'unpruned') for i in names]))
            relevant=[m for m in r['models'] if m['identity'] in names]
            cell[condition]['concepts']={k:dict(query_accuracy=st.mean(t['conditions'][k]['query_correct']/6 for m in relevant for t in m['concepts']),abstentions=sum(t['conditions'][k]['abstained'] for m in relevant for t in m['concepts']),predicate_checks=sum(t['conditions'][k]['predicate_checks'] for m in relevant for t in m['concepts'])) for k in ('neural','symbolic_equal_cap','symbolic_full_reference')}
        cell['regret_reduction']=interval([ranking(a)-ranking(b) for a,b in zip(ids('legacy'),ids('aligned_v1'))])
        cell['control_gain']={p:interval([returns(a,p)-returns(b,p) for a,b in zip(ids('aligned_v1'),ids('legacy'))]) for p in ('pruned','unpruned')}
        cell['ranking_screen']=cell['aligned_v1']['regret']<=.75*cell['legacy']['regret']
        cell['control_screen']=all(v['mean']>=.1 for v in cell['control_gain'].values())
        result['recipes'][recipe]=cell
    result['practical_screen']=all(v['ranking_screen'] and v['control_screen'] for v in result['recipes'].values())
    return result


if __name__=='__main__':print(json.dumps(summarize(json.loads((ROOT/'artifacts/seed_contract_study.json').read_text())),indent=2))
