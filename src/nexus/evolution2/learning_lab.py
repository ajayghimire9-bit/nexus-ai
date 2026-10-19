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


def load_integration(root):
    """A verified engineering status, never a newly observed control return."""
    folder=Path(root)/'artifacts';raw=(folder/'e3_10_metered_model.json').read_bytes()
    result=json.loads(raw);verified=json.loads((folder/'e3_10_metered_model_validation.json').read_text())
    if verified.get('valid') is not True or verified['capture_sha256']!=hashlib.sha256(raw).hexdigest() or result.get('declared_complete') is not True or result.get('outcome')!='metered_inference_equivalence_verified':raise ValueError('verified_integration_required')
    if verified['resources_verified']!=result['resources'] or result['resources']['real_steps']!=0:raise ValueError('engineering_resource_provenance')
    return dict(kind='verified_engineering_inference',execution_sha=result['execution_sha'],
        model_observation_cells=len(result['rows']),resources=result['resources'],wall_s=result['wall_s'],
        claim='Inference correctness only; no new environment returns or demonstrated learning improvement.')


def load_control_replay(root,study):
    """Small allowlist over verified, closed captures; never a live evaluator."""
    names={'forecast16':('e3_11b_forecast_calibration','e3_11b_forecast_calibration_validation','e3_11b_forecast_predecision'),
           'horizon64':('e3_11d_horizon_calibration','e3_11d_horizon_validation','e3_11d_horizon_predecision')}
    if study not in names:raise ValueError('supported_recorded_study_required')
    result_name,validation_name,prediction_name=names[study];folder=Path(root)/'artifacts'
    raw=(folder/(result_name+'.json')).read_bytes();p=json.loads(raw);v=json.loads((folder/(validation_name+'.json')).read_text())
    if p.get('declared_complete') is not True or v.get('valid') is not True or hashlib.sha256(raw).hexdigest()!=v['capture_sha256']:raise ValueError('verified_complete_capture_required')
    raw_predictions=(folder/(prediction_name+'.jsonl')).read_bytes()
    if hashlib.sha256(raw_predictions).hexdigest()!=p['predecision_sha256']:raise ValueError('verified_predecision_required')
    predictions={(r['family'],r['bundle'],r['episode']):r for r in map(json.loads,raw_predictions.splitlines())}
    paths={(r['family'],r['bundle'],r['episode']):r for r in p['records']};cases=[]
    if len(paths)!=16 or len(p['rows'])!=16 or len(predictions)!=16:raise ValueError('complete_recorded_grid')
    for row in p['rows']:
        key=row['family'],row['bundle'],row['episode'];r=paths[key];forecasts=dict(row['predictions'])
        if study=='horizon64':forecasts['policy_16']=predictions[key]['policy_16']
        cases.append(dict(family=key[0],bundle=key[1],episode=key[2],forecasts=forecasts,
            returns={label:sum(values) for label,values in row['rewards'].items()},paths=r['actual']))
    return dict(kind='verified_recorded_control_replay',live=False,study=study,execution_sha=p['execution_sha'],
        capture_sha256=v['capture_sha256'],label=p['analysis']['label'],cases=cases,analysis=p['analysis'])


def load_operator_replay(root,*,parent_retention=False):
    """E3.12B recorded choices, never retrospective fitting of a new selector."""
    root=Path(root);folder=root/'artifacts'
    capture='e3_12d_parent_retention' if parent_retention else 'e3_12b_operator_headroom'
    validation='e3_12d_parent_validation' if parent_retention else 'e3_12b_operator_validation'
    raw=(folder/(capture+'.json')).read_bytes();p=json.loads(raw)
    v=json.loads((folder/(validation+'.json')).read_text())
    config_raw=(root/('configs/'+capture+'.json')).read_bytes();c=json.loads(config_raw)
    if (v.get('valid') is not True or p.get('declared_complete') is not True
        or hashlib.sha256(raw).hexdigest()!=v['result_sha256']
        or hashlib.sha256(config_raw).hexdigest()!=p['provenance']['config_sha256']):raise ValueError('verified_operator_capture_required')
    expected={(f,b,e) for f in c['families'] for b in c['model_bundles'] for e in c['training_episodes']+c['evaluation_episodes']}
    keys=[(r['family'],r['bundle'],r['episode']) for r in p['rows']]
    if len(keys)!=len(expected) or set(keys)!=expected:raise ValueError('complete_operator_replay_grid')
    cases=[];training=[]
    for r in p['rows']:
        wanted={'parent','switch','rank_blend'}
        if parent_retention and r['role']=='training':
            kind=c['training_schedule'][f"{r['family']}:{r['bundle']}"][r['episode']]
            if r['training_operator']!=kind:raise ValueError('recorded_parent_schedule')
            wanted={'parent',kind}
        if set(r['paths'])!=wanted:raise ValueError('recorded_operator_paths')
        returns={}
        for kind,path in r['paths'].items():
            if len(path['steps'])!=200:raise ValueError('complete_operator_trajectory')
            total=sum(s['reward'] for s in path['steps'])
            if not abs(total-path['return'])<1e-8:raise ValueError('recorded_reward_accounting')
            returns[kind]=total
        base=dict(family=r['family'],bundle=r['bundle'],episode=r['episode'],returns=returns)
        if r['role']=='training':training.append({**base,'before':r['before'],'after':r['after']})
        else:
            choice=r['decision']['parent_inclusive']['choice'] if parent_retention else r['decision']['training_mean_kind']
            cases.append({**base,'decision':r['decision'],'paths':r['paths'],
                'selected_minus_parent':returns[choice]-returns['parent'],'harmful_change':returns[choice]<returns['parent']})
    return dict(kind='verified_operator_control_replay',study='E3.12D' if parent_retention else 'E3.12B',live=False,scientific=True,
        execution_sha=p['provenance']['source_commit'],capture_sha256=v['result_sha256'],label=p['analysis']['label'],
        training=training,cases=cases,analysis=p['analysis'],
        caveat=('Closed limited-feedback parent-retention screen FAILED; choices matched existing selectors; no new evaluation.' if parent_retention else
            'Closed full-information source diagnostic; no new parent-inclusive selector scored. Not generalization or proven self-improvement.'))


def load_preparation(root):
    """Unregistered F config status only; no results are invented for replay."""
    raw=(Path(root)/'configs/e3_12f_reset_blocked_runtime_v2.json').read_bytes();c=json.loads(raw)
    return dict(kind='unexecuted_preparation',scientific=False,live=False,study='E3.12F',
        config_sha256=hashlib.sha256(raw).hexdigest(),status=c['status'],
        execution_authorized=c['execution_authorized'],
        caps={k:c[k] for k in ('time_cap_s','real_cap','imagined_cap','model_call_cap','network_forward_cap')},
        caveat='Preparation and source-only bounds; no F collection or measured result. This viewer cannot authorize or execute it.')


def load_training_audit(root):
    """Already recorded training-only evidence, not policy-return validation."""
    folder=Path(root)/'artifacts';raw=(folder/'e3_12e_training_stability.json').read_bytes();p=json.loads(raw)
    v=json.loads((folder/'e3_12e_training_validation.json').read_text())
    if p.get('declared_complete') is not True or v.get('valid') is not True or hashlib.sha256(raw).hexdigest()!=v['capture_sha256']:raise ValueError('verified_training_audit_required')
    return dict(kind='recorded_training_estimate_diagnostic',live=False,query_outcomes_used=0,
        execution_sha=p['execution_sha'],capture_sha256=v['capture_sha256'],
        models=[{k:m[k] for k in ('family','bundle','full','choice_flip_counts','raw_paired_sign_disagreements')} for m in p['analysis']['models']],
        caveat='Training sensitivity only; no new policy-value, continual-learning or transfer evidence.')


def render(data,*,engineering_events=(),integration=None):
    if data.get('kind')!='historical_training_replay' or data.get('live') is not False or not data.get('rows'):raise ValueError('historical_data_required')
    encoded=json.dumps(data,allow_nan=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    events=html.escape(json.dumps(list(engineering_events),indent=2,allow_nan=False))
    panel=''
    if integration is not None:
        if integration.get('kind')!='verified_engineering_inference':raise ValueError('verified_engineering_status_only')
        panel='<h2>Frozen-model integration check</h2><p>Separate from the historical return replay: this checks inference and metering, not control improvement.</p><pre>'+html.escape(json.dumps(integration,indent=2,allow_nan=False))+'</pre>'
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXUS Learning Lab — historical replay</title><style>
body{font:15px system-ui;margin:32px auto;max-width:1100px;padding:0 20px;color:#202124;background:#fafafa}h1{font-size:24px}h2{font-size:18px}p{max-width:85ch;line-height:1.5}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:9px;border-bottom:1px solid #ddd}th{position:sticky;top:0;background:#eee}label{margin-right:20px}select{padding:6px}pre{white-space:pre-wrap}small{color:#555}</style>
<h1>NEXUS Learning Lab</h1><p><strong>Historical training-feedback replay. No live execution.</strong>
Cached returns are observations; predicted advantages are forecasts. This page does not train, select experiments, or call an environment.</p>
<p>Advantage means rank-blend return minus successor-controller return. A positive prediction selects rank blend. Each reset was withheld while fitting its prediction. Family return scales differ.</p>
<p id="decision"></p><small id="source"></small><p><label>Family <select id="family"><option value="">All</option><option>pendulum</option><option>acrobot</option></select></label>
<label>Method <select id="method"><option value="">All</option><option>model_mean</option><option>additive</option><option>interaction</option></select></label></p>
<table><thead><tr><th>Family/model/reset</th><th>Method</th><th>Predicted advantage (return)</th><th>Observed advantage (return)</th><th>Chosen controller</th><th>Cached chosen return</th><th>In-set regret (return)</th></tr></thead><tbody id="rows"></tbody></table>
'''+panel+'''<h2>Engineering-only lineage and memory illustrations</h2><p>These contract events are synthetic, not environment-learning evidence. Their absence does not imply learning occurred.</p><pre>'''+events+'''</pre>
<script>const data='''+encoded+''';document.getElementById('decision').textContent='Recorded outcome: '+data.decision;
document.getElementById('source').textContent='Source: '+data.source+' | Execution '+data.execution_sha+' | fixed source training resets 0–8';
function draw(){const body=document.getElementById('rows');body.replaceChildren();for(const r of data.rows){if(document.getElementById('family').value&&r.family!==document.getElementById('family').value)continue;if(document.getElementById('method').value&&r.method!==document.getElementById('method').value)continue;const tr=document.createElement('tr');for(const v of [r.family+'/'+r.model+'/'+r.episode,r.method,r.predicted_advantage.toFixed(3),r.observed_advantage.toFixed(3),r.choice,r.selected_return.toFixed(3),r.regret.toFixed(3)]){const td=document.createElement('td');td.textContent=v;tr.appendChild(td)}body.appendChild(tr)}}
document.getElementById('family').onchange=draw;document.getElementById('method').onchange=draw;draw();</script></html>'''
