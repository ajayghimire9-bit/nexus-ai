"""Export verified recorded E3.11D data; stdlib only, no simulation/inference."""
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'artifacts';raw=(folder/'e3_11d_horizon_calibration.json').read_bytes();p=json.loads(raw)
    verification=json.loads((folder/'e3_11d_horizon_validation.json').read_text())
    if not p['declared_complete'] or verification.get('valid') is not True or hashlib.sha256(raw).hexdigest()!=verification['capture_sha256']:raise ValueError('verified_complete_capture_required')
    raw_receipts=(folder/'e3_11d_horizon_predecision.jsonl').read_bytes()
    if hashlib.sha256(raw_receipts).hexdigest()!=p['predecision_sha256']:raise ValueError('forecast_file_hash')
    receipts={(r['family'],r['bundle'],r['episode']):r for r in map(json.loads,raw_receipts.splitlines())}
    rows=[]
    for r in p['rows']:
        guesses={**r['predictions'],'policy_16':receipts[r['family'],r['bundle'],r['episode']]['policy_16']}
        values={n:sum(r['rewards']['rank_blend'][:n])-sum(r['rewards']['successor_anchor'][:n]) for n in (16,64,192)}
        returns={label:sum(rewards) for label,rewards in r['rewards'].items()}
        for method,guess in guesses.items():
            choice='rank_blend' if guess>1e-6 else 'successor_anchor'
            rows.append(dict(family=r['family'],bundle=r['bundle'],episode=r['episode'],method=method,
                predicted_advantage=guess,actual_advantage_16=values[16],actual_advantage_64=values[64],actual_advantage_192=values[192],
                chosen_controller=choice,selected_return=returns[choice],in_set_regret=max(returns.values())-returns[choice],forecast_receipt_sha256=r['forecast_sha256']))
    means={f:{method:{metric:mean(model['methods'][method][metric] for model in entry['models'])
        for metric in entry['models'][0]['methods'][method]} for method in entry['models'][0]['methods']}
        for f,entry in p['analysis']['families'].items()}
    result=dict(capture_sha256=verification['capture_sha256'],analysis=p['analysis'],family_means=means,
        physical_continuations=32,logical_method_returns=64,additional_real_steps=0,additional_imagined_transitions=0,
        caution='Prefix16 is cached, not another executed forecast. Regret reduction and return gain are mathematically dependent; two existing models per family.')
    with (folder/'e3_11d_horizon_summary.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    with (folder/'e3_11d_horizon_returns.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(label=p['analysis']['label'],family_means=means)))


if __name__=='__main__':main()
