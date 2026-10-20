"""Data-only validation; saved evidence never grants neural execution."""
import math
CHANNELS={'reward':62,'meaning':53}

def validate_state(p):
    def numeric(v,n):return type(v) is list and len(v)==n and all(type(x) in (int,float) and math.isfinite(x) and abs(x)<1000 for x in v)
    if type(p) is not dict or set(p)!={'schema','blocks','anchors','development','skills','seen','steps','work'} or p['schema']!='seed_adaptive_state_v1':raise ValueError('adaptive_state_schema')
    if any(type(p[k]) is not dict or set(p[k])!=set(CHANNELS) for k in ('blocks','anchors','development')):raise ValueError('adaptive_channels')
    if type(p['steps']) is not int or not 0<=p['steps']<=24 or type(p['seen']) is not list or len(p['seen'])!=p['steps'] or len(set(p['seen']))!=len(p['seen']) or any(type(r) is not str or len(r)!=64 for r in p['seen']):raise ValueError('adaptive_steps')
    for c,n in CHANNELS.items():
        if not numeric(p['blocks'][c],n):raise ValueError('adaptive_parameters')
        for field,cap in (('anchors',8),('development',4)):
            rows=p[field][c]
            if type(rows) is not list or len(rows)>cap:raise ValueError('adaptive_memory_cap')
            for r in rows:
                if type(r) is not dict or set(r)!={'x','y','ref','key'} or not numeric(r['x'],n) or type(r['y']) not in (float,int) or not math.isfinite(r['y']) or abs(r['y'])>100 or r['ref'] not in p['seen'] or type(r['key']) is not str or len(r['key'])>64:raise ValueError('adaptive_anchor')
    refs=[r['ref'] for c in CHANNELS for f in ('anchors','development') for r in p[f][c]]
    if len(refs)!=len(set(refs)):raise ValueError('assessment_training_overlap')
    if type(p['skills']) is not list or len(p['skills'])>2:raise ValueError('adaptive_skill_cap')
    keys=[]
    for s in p['skills']:
        if type(s) is not dict or set(s)!={'channel','key','theta'} or s['channel'] not in CHANNELS or type(s['key']) is not str or len(s['key'])>64 or not numeric(s['theta'],CHANNELS[s['channel']]):raise ValueError('typed_skill')
        keys.append((s['channel'],s['key']))
    if len(keys)!=len(set(keys)):raise ValueError('duplicate_skills')
    if type(p['work']) is not dict or set(p['work'])!={'actual_updates','question_hypotheses','structural_fits','linear_solves'} or any(type(v) is not int or not 0<=v<=100000 for v in p['work'].values()):raise ValueError('adaptive_work')
