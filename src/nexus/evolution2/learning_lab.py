"""Read-only, hash-verified replay adapter. No evaluator/learning imports."""
import hashlib
import html
import json
from pathlib import Path


def load_replay(root):
    folder=Path(root)/'artifacts'
    path=folder/'e3_8_compact_interactions.json';raw=path.read_bytes();result=json.loads(raw)
    validation=json.loads((folder/'e3_8_compact_interactions_validation.json').read_text())
    frozen_raw=(folder/'e3_8_frozen_fold_predictions.json').read_bytes()
    if validation.get('valid') is not True or validation['capture_sha256']!=hashlib.sha256(raw).hexdigest() or result.get('declared_complete') is not True:
        raise ValueError('verified_complete_replay_required')
    if result['config']['version']!='e3_8_compact_interactions_v1' or hashlib.sha256(frozen_raw).hexdigest()!=result['frozen_fold_sha256']:raise ValueError('replay_provenance')
    predictions={}
    for fold in json.loads(frozen_raw)['folds']:
        for row in fold['predictions']:
            p=row['public'];predictions[(p['family'],p['model_bundle'],p['episode'])]=row
    rows=[]
    for row in result['analysis']['raw']:
        p=row['public'];key=(p['family'],p['model_bundle'],p['episode']);pred=predictions[key]
        for method in ('model_mean','additive','interaction'):
            rows.append(dict(family=p['family'],model=p['model_bundle'],episode=p['episode'],method=method,
                predicted_advantage=pred['estimates'][method],observed_advantage=row['truth'],
                selected_return=row['returns'][method],regret=row['regret'][method],choice=pred['choices'][method]))
    if len(rows)!=108:raise ValueError('complete_replay_grid')
    return dict(kind='historical_training_replay',live=False,source=str(path),execution_sha=result['execution_sha'],
                decision=result['analysis']['label'],rows=rows)


def render(data,*,engineering_events=()):
    if data.get('kind')!='historical_training_replay' or data.get('live') is not False or not data.get('rows'):raise ValueError('historical_data_required')
    encoded=json.dumps(data,allow_nan=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    events=html.escape(json.dumps(list(engineering_events),indent=2,allow_nan=False))
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXUS Learning Lab — historical replay</title><style>
body{font:15px system-ui;margin:32px auto;max-width:1100px;padding:0 20px;color:#202124;background:#fafafa}h1{font-size:24px}h2{font-size:18px}p{max-width:85ch;line-height:1.5}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:9px;border-bottom:1px solid #ddd}th{position:sticky;top:0;background:#eee}label{margin-right:20px}select{padding:6px}pre{white-space:pre-wrap}small{color:#555}</style>
<h1>NEXUS Learning Lab</h1><p><strong>Historical training-feedback replay. No live execution.</strong>
Cached returns are observations; predicted advantages are forecasts. This page does not train, select experiments, or call an environment.</p>
<p>Advantage means rank-blend return minus successor-controller return. A positive prediction selects rank blend. Each reset was withheld while fitting its prediction. Family return scales differ.</p>
<p id="decision"></p><small id="source"></small><p><label>Family <select id="family"><option value="">All</option><option>pendulum</option><option>acrobot</option></select></label>
<label>Method <select id="method"><option value="">All</option><option>model_mean</option><option>additive</option><option>interaction</option></select></label></p>
<table><thead><tr><th>Family/model/reset</th><th>Method</th><th>Predicted advantage (return)</th><th>Observed advantage (return)</th><th>Chosen controller</th><th>Cached chosen return</th><th>In-set regret (return)</th></tr></thead><tbody id="rows"></tbody></table>
<h2>Engineering-only lineage and memory illustrations</h2><p>These contract events are synthetic, not environment-learning evidence. Their absence does not imply learning occurred.</p><pre>'''+events+'''</pre>
<script>const data='''+encoded+''';document.getElementById('decision').textContent='Recorded outcome: '+data.decision;
document.getElementById('source').textContent='Source: '+data.source+' | Execution '+data.execution_sha+' | fixed source training resets 0–8';
function draw(){const body=document.getElementById('rows');body.replaceChildren();for(const r of data.rows){if(document.getElementById('family').value&&r.family!==document.getElementById('family').value)continue;if(document.getElementById('method').value&&r.method!==document.getElementById('method').value)continue;const tr=document.createElement('tr');for(const v of [r.family+'/'+r.model+'/'+r.episode,r.method,r.predicted_advantage.toFixed(3),r.observed_advantage.toFixed(3),r.choice,r.selected_return.toFixed(3),r.regret.toFixed(3)]){const td=document.createElement('td');td.textContent=v;tr.appendChild(td)}body.appendChild(tr)}}
document.getElementById('family').onchange=draw;document.getElementById('method').onchange=draw;draw();</script></html>'''
