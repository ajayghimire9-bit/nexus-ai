#!/usr/bin/env python3
"""Independent raw-label arithmetic, read-only by default. Zero new simulation."""
import argparse
import json
import math
from pathlib import Path
import statistics
from nexus.world.terminal_value_calibration import load_config,parent_evidence,validate,OUTPUT
from nexus.world.planning_value import sha


def audit():
    cfg=load_config();parent,stage=parent_evidence();p=json.loads(OUTPUT.read_text())
    rebuilt=validate(p,cfg,parent,stage)
    recovery=json.loads(Path('artifacts/terminal_value_calibration_validation.json').read_text())
    if recovery.get('complete') is not True or recovery['source_sha256']!=sha(OUTPUT) or any(recovery[k]!=rebuilt[k] for k in ('label','summaries')):raise RuntimeError('missing/stale offline completion proof')
    groups={}
    for role,tasks in [('source',range(8)),('development',range(8,11))]:
        means={kind:[] for kind in ('imagined','actual','constant')}
        for d in cfg['decoders']:
            rmse={kind:[] for kind in means}
            for t in tasks:
                row=next(r for r in p['cells'] if r['decoder']==d and r['task']==t)
                actual=[sum(tr['rewards']) for tr in row['traces']]
                for s in cfg['students']:
                    for kind in means:
                        residuals=[v-y for v,y in zip(row['predictions'][str(s)][kind],actual)]
                        rmse[kind].append(math.sqrt(sum(e*e for e in residuals)/4))
            for kind in means:means[kind].append(statistics.mean(rmse[kind]))
        def interval(a,b):
            vals=[x-y for x,y in zip(a,b)];m=statistics.mean(vals);se=statistics.stdev(vals)/math.sqrt(10)
            return dict(mean=m,lo=m-2.262*se,hi=m+2.262*se,per_decoder=vals)
        benefit=interval(means['constant'],means['imagined']);endpoint=interval(means['imagined'],means['actual'])
        saved=rebuilt['summaries'][role]
        for target,ref in [(benefit,saved['benefit']),(endpoint,saved['endpoint_difference'])]:
            for k in ('mean','lo','hi'):
                if not math.isclose(target[k],ref[k],abs_tol=1e-8):raise RuntimeError('primary/secondary arithmetic mismatch')
        groups[role]=dict(means={k:statistics.mean(v) for k,v in means.items()},benefit=benefit,endpoint_difference=endpoint)
    return dict(kind='independent_arithmetic_not_external_replication',audit_passed=True,source_sha256=sha(OUTPUT),groups=groups,new_environment_steps=0)


def figure(result):
    groups=result['groups'];maximum=max(v for r in groups.values() for v in r['means'].values())*1.2
    pieces=['<svg xmlns="http://www.w3.org/2000/svg" width="920" height="410"><rect width="920" height="410" fill="white"/><g font-family="Arial" fill="#172432">',
        '<text x="24" y="30" font-size="20">Frozen terminal-value calibration on new states</text>',
        '<text x="24" y="53" font-size="13">Student contexts; mean task-level RMSE averaged inside ten decoders. Lower is better.</text>']
    colors=['#376d9d','#68a3a5','#8d899b']
    for i,(group,r) in enumerate(groups.items()):
        y=95+i*140;pieces.append(f'<text x="24" y="{y}" font-size="15">{group}</text>')
        for j,(name,value) in enumerate(r['means'].items()):
            yy=y+12+j*29;width=value/maximum*570
            pieces.extend([f'<text x="24" y="{yy+15}" font-size="12">{name}</text>',f'<rect x="145" y="{yy}" width="{width:.2f}" height="20" fill="{colors[j]}"/>',f'<text x="{155+width:.2f}" y="{yy+15}" font-size="12">{value:.2f}</text>'])
    ci=groups['development']['benefit'];pieces.append(f'<text x="24" y="366" font-size="13">Primary baseline minus imagined RMSE: {ci["mean"]:+.2f} [{ci["lo"]:+.2f}, {ci["hi"]:+.2f}] (paired 95%, df9)</text>')
    pieces.append('<text x="24" y="390" font-size="12">Known physics; actual endpoint is a research diagnostic, not an oracle or deployed input.</text></g></svg>')
    return ''.join(pieces)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');args=p.parse_args();result=audit()
    if args.write:
        dest=Path('artifacts/terminal_value_calibration_audit.json');plot=Path('artifacts/terminal_value_calibration.svg')
        if dest.exists() or plot.exists():raise RuntimeError('refusing overwrite')
        dest.write_text(json.dumps(result,indent=2)+'\n');plot.write_text(figure(result))
    print(json.dumps(result,indent=2))
