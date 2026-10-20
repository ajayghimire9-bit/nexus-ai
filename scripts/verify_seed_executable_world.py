"""Independent stdlib-only arithmetic audit: never fits, probes or runs a world."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]


def audit(path):
    raw=Path(path).read_bytes();r=json.loads(raw);c=r['config'];rows=r['rows']
    if not r['declared_complete'] or [x['seed'] for x in rows]!=list(range(971000,971016)):raise ValueError('complete_task_grid')
    methods=['fixed','induced','all_history','replay','gru32'];checked=0;steps=0
    for row in rows:
        if set(row['metrics'])!=set(methods) or set(row['predictions'])!=set(methods):raise ValueError('complete_methods')
        for role,n in [('source',96),('validation',48),('final',96)]:
            data=row['data'][role]
            if [v['episode'] for v in data]!=[f'{role}-{row["seed"]}-{i}' for i in range(n)]:raise ValueError('complete_episodes')
            steps+=sum(len(v['codes'])+1 for v in data)
        for m in methods:
            p=row['predictions'][m];data=row['data']['final']
            if len(p)!=96 or any(type(v) not in (float,int) or not math.isfinite(v) for v in p):raise ValueError('finite_prediction')
            mse=sum((a-int(x['outcome']))**2 for a,x in zip(p,data))/96
            accuracy=sum((a>=.5)==x['outcome'] for a,x in zip(p,data))/96
            if abs(mse-row['metrics'][m]['brier'])>1e-12 or abs(accuracy-row['metrics'][m]['accuracy'])>1e-12:raise ValueError('metric_arithmetic')
            checked+=96
    primary=[row for row in rows if row['kind'] in ('earlier','order')]
    differences=[row['metrics']['fixed']['brier']-row['metrics']['induced']['brier'] for row in primary]
    mean=sum(differences)/8
    variance=sum((v-mean)**2 for v in differences)/7
    half=2.364624251*math.sqrt(variance/8)
    recorded=r['analysis']['fixed_minus_induced']
    if max(abs(mean-recorded['mean']),abs(mean-half-recorded['ci95'][0]),abs(mean+half-recorded['ci95'][1]))>1e-12:raise ValueError('paired_interval')
    retained=max(x['change'].get('forgetting',0.) for x in rows)
    expected='source_feature_screen_passed' if mean>=.03 and mean-half>0 and retained<=.01 else 'source_feature_screen_failed'
    if r['analysis']['label']!=expected or r['resources']['real_steps']!=steps or r['resources']['updates']!=3200:raise ValueError('screen_or_accounting')
    if r['execution_debit_s']!=math.ceil(r['host_receipt']['wall_s'])+1 or abs(r['session_used_s']-c['carried_used_s']-r['execution_debit_s'])>1e-9:raise ValueError('ledger')
    return dict(valid=True,predictions_checked=checked,authored_observations=steps,
        paired_mean=mean,paired_ci95=[mean-half,mean+half],decision=expected,
        artifact_sha256=hashlib.sha256(raw).hexdigest(),scientific_execution=False)


if __name__=='__main__':print(json.dumps(audit(sys.argv[1] if len(sys.argv)>1 else ROOT/'artifacts/seed_executable_world.json'),indent=2))
