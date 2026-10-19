"""Export verified recorded results only; no fitting, model imports or collection."""
import csv
import hashlib
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'artifacts';raw=(folder/'e3_11_post_probe.json').read_bytes();p=json.loads(raw)
    v=json.loads((folder/'e3_11_post_probe_validation.json').read_text())
    if not p['declared_complete'] or v.get('valid') is not True or hashlib.sha256(raw).hexdigest()!=v['capture_sha256']:raise ValueError('verified_capture_required')
    diagnostics=[];exports=[]
    for family in ('pendulum','acrobot'):
        for bundle in (0,1):
            train=[r for r in p['pairs'] if (r['family'],r['bundle'],r['role'])==(family,bundle,'training')]
            rows=[r for r in p['pairs'] if (r['family'],r['bundle'],r['role'])==(family,bundle,'evaluation')]
            mean=statistics.mean(r['returns']['rank_blend']-r['returns']['successor_anchor'] for r in train)
            diagnostics.append(dict(family=family,bundle=bundle,training_mean_advantage=mean,
                same_proposed_first_action=sum(r['proposed_actions']['rank_blend']==r['proposed_actions']['successor_anchor'] for r in rows),
                evaluation_contexts=len(rows),model_mean_advantage_mae=statistics.mean(abs(mean-(r['returns']['rank_blend']-r['returns']['successor_anchor'])) for r in rows),
                contextual_advantage_mae=statistics.mean(abs(r['decision']['estimated_advantage']-(r['returns']['rank_blend']-r['returns']['successor_anchor'])) for r in rows)))
            for row in rows:
                probe=sum(s['reward'] for s in row['prefix'])
                for method,choice in row['decision']['choices'].items():
                    value=row['returns'][choice]
                    exports.append(dict(family=family,bundle=bundle,episode=row['episode'],method=method,chosen_controller=choice,
                        return_192=value,shared_probe_return=probe,accounted_return_200=probe+value,
                        in_set_regret=max(row['returns'].values())-value,physical_path_reference=f'{family}:{bundle}:{row["episode"]}:{choice}'))
    result=dict(kind='verified_recorded_result_summary',capture_sha256=v['capture_sha256'],primary_analysis=p['analysis'],diagnostics=diagnostics,
        physical_evaluation_paths=32,logical_method_returns=64,additional_environment_execution=0,
        caution='Zero-width contrast intervals here arise from identical choices/cached paths, not proven population equivalence. Regret reduction and return gain are mathematically dependent.')
    with (folder/'e3_11_summary.json').open('x') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    with (folder/'e3_11_evaluation_returns.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(exports[0]));writer.writeheader();writer.writerows(exports)
    print(json.dumps(dict(label=p['analysis']['label'],model_diagnostics=diagnostics)))


if __name__=='__main__':main()
