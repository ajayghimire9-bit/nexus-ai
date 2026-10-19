"""Export verified recorded results only; no fitting, model imports or collection."""
import csv
import argparse
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


def calibration():
    """Saved-result export only, no new scientific computation or fitting."""
    folder=ROOT/'artifacts';raw=(folder/'e3_11b_forecast_calibration.json').read_bytes();p=json.loads(raw)
    v=json.loads((folder/'e3_11b_forecast_calibration_validation.json').read_text())
    if not p['declared_complete'] or v.get('valid') is not True or hashlib.sha256(raw).hexdigest()!=v['capture_sha256']:raise ValueError('verified_capture_required')
    models=p['analysis']['families'];rows=[]
    for r in p['rows']:
        a,b=(sum(r['rewards'][label]) for label in ('successor_anchor','rank_blend'))
        a16,b16=(sum(r['rewards'][label][:16]) for label in ('successor_anchor','rank_blend'))
        for method,prediction in r['predictions'].items():
            rows.append(dict(family=r['family'],bundle=r['bundle'],episode=r['episode'],method=method,
                predicted_advantage=prediction,actual_advantage_16=b16-a16,actual_advantage_192=b-a,
                chosen_controller='rank_blend' if prediction>1e-6 else 'successor_anchor',selected_return=b if prediction>1e-6 else a,
                in_set_regret=max(a,b)-(b if prediction>1e-6 else a),successor_return=a,rank_blend_return=b,
                forecast_receipt_sha256=r['forecast_sha256']))
    means={f:{method:{metric:statistics.mean(m['methods'][method][metric] for m in entry['models'])
        for metric in entry['models'][0]['methods'][method]} for method in ('policy_forecast','common_tail','training_mean')}
        for f,entry in models.items()}
    summary=dict(kind='verified_saved_calibration_export',capture_sha256=v['capture_sha256'],primary_analysis=p['analysis'],
        family_means=means,physical_continuations=32,cached_method_returns=48,additional_environment_execution=0,
        caution='Selected-return gains and regret reductions are mathematically dependent. Two pretrained models per family; intervals are exploratory. Zero accuracy-difference interval can arise from equal discrete accuracy, not identical choices or proven equivalence.')
    with (folder/'e3_11b_forecast_summary.json').open('x') as handle:json.dump(summary,handle,indent=2);handle.write('\n')
    with (folder/'e3_11b_forecast_returns.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(label=p['analysis']['label'],family_means=means)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--calibration',action='store_true');args=parser.parse_args()
    calibration() if args.calibration else main()
