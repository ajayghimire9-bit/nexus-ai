#!/usr/bin/env python3
"""Posthoc baseline-strength audit, explicitly outside the primary test family."""
import argparse
import json
from pathlib import Path
import statistics
from nexus.world.value_candidate_discrimination import inputs,OUTPUT,validate_result
from nexus.world.planning_value import sha
from nexus.world.long_continuation import paired_interval


def supplement():
    cfg,parent,stage,capture=inputs();p=json.loads(OUTPUT.read_text())
    if not p.get('complete'):raise RuntimeError('incomplete analysis')
    validate_result(p,cfg,parent,stage,capture)
    prefixes={r['task']:r for r in capture['prefixes']};cal={(r['decoder'],r['task']):r for r in capture['cells']};rows={(r['decoder'],r['task']):r for r in p['cells']}
    groups={}
    for group,tasks in [('development',cfg['development_tasks']),('source',cfg['source_tasks'])]:
        deltas=[];means=[]
        for d in cfg['decoders']:
            differences=[];uniform=[]
            for t in tasks:
                u=statistics.mean(sum(x['rewards'])+tail for x,tail in zip(prefixes[t]['rollouts'],cal[d,t]['targets']))
                uniform.append(u)
                differences.extend(rows[d,t]['metrics'][str(s)]['value_return']-u for s in cfg['students'])
            deltas.append(statistics.mean(differences));means.append(statistics.mean(uniform))
        groups[group]=dict(uniform_expected_return=statistics.mean(means),value_minus_uniform=dict(per_decoder=deltas,interval=paired_interval(deltas)))
    return dict(kind='posthoc_unadjusted_baseline_audit_not_preregistered',source_sha256=sha(OUTPUT),groups=groups,new_environment_steps=0)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');args=p.parse_args();r=supplement()
    if args.write:
        output=Path('artifacts/value_candidate_discrimination_supplement.json')
        if output.exists():raise RuntimeError('refusing overwrite')
        output.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2))
