"""E3.11D: locked 64-versus-16 forecast adapter; no new planner or learner."""
from copy import deepcopy
import json
from statistics import mean
from nexus.evolution2 import forecast_calibration as base


def settings(api):
    c=json.loads(api.CONFIG.read_text())
    fixed=dict(version='e3_11d_horizon_v1',families=['pendulum','acrobot'],model_bundles=[0,1],
        training_episodes=[],evaluation_episodes=[0,1,2,3],controllers=['successor_anchor','rank_blend'],
        env_seed_base=2141000000,planner_seed_base=2142000000,probe_seed_base=2143000000,evidence_seed_base=2144000000,
        forecast_steps=64,time_cap_s=180,real_cap=6272,imagined_cap=12224512,model_call_cap=485888,network_forward_cap=485888,journal_chunk_decisions=1500)
    if any(k not in c or base.digest(c[k])!=base.digest(v) for k,v in fixed.items()):raise ValueError('locked_horizon_settings')
    if (16*(64*2984+512+192*2982),16*(64*120+32+192*118))!=(c['imagined_cap'],c['model_call_cap']):raise ValueError('horizon_budget_arithmetic')
    path=api.ROOT/c['analysis_config']
    if api.sha(path)!=c['analysis_config_sha256']:raise ValueError('analysis_settings_hash')
    a=json.loads(path.read_text());base.validate_config(a)
    return c,a


def prefix_score(path,n=16):
    if len(path['steps'])<n:raise ValueError('complete_forecast_prefix')
    return sum(base.number(s['predicted_reward'])*base.number(s['survival_before']) for s in path['steps'][:n])


def short_advantage(record):
    return prefix_score(record['paths']['rank_blend'])-prefix_score(record['paths']['successor_anchor'])


def analyze(p,c,a):
    """Production caller first validates the raw capture with existing host."""
    base.validate_rows(p['rows'],a)
    records={(r['family'],r['bundle'],r['episode']):r for r in p['records']}
    if len(p['records'])!=16 or set(records)!=base.expected_grid(a):raise ValueError('complete_horizon_records')
    rows=deepcopy(p['rows'])
    for r in rows:
        record=records[r['family'],r['bundle'],r['episode']]
        if any(len(path['steps'])!=64 for path in record['paths'].values()):raise ValueError('complete_64_step_paths')
        r['predictions']['policy_16']=short_advantage(record)
    config={**a,'predictors':['policy_forecast','policy_16','common_tail','training_mean'],
        'comparison_baselines':['policy_16','training_mean']}
    result=base.summarize(rows,config)
    for f,entry in result['families'].items():
        for model in entry['models']:
            selected=[r for r in rows if r['family']==f and r['bundle']==model['bundle']]
            for method,metrics in model['methods'].items():
                metrics['matched_64_advantage_mae']=mean(abs(r['predictions'][method]-(
                    sum(r['rewards']['rank_blend'][:64])-sum(r['rewards']['successor_anchor'][:64]))) for r in selected)
    result['label']='longer_horizon_point_screen_passed_not_confirmed' if result['point_screen'] else 'longer_horizon_utility_not_established'
    result['forecast_horizons']=[16,64];result['primary_actual_steps']=192
    return result
