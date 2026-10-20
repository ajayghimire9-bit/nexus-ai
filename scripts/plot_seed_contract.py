"""Saved-data SVG; points are training-seed means, not episode replications."""
import json
from pathlib import Path
from summarize_seed_contract import summarize
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    r=json.loads((ROOT/'artifacts/seed_contract_study.json').read_text());s=summarize(r)
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="420"><rect width="1000" height="420" fill="white"/><g font-family="sans-serif" fill="#233442">','<text x="30" y="30" font-size="20">Corrected contracts did not establish better decisions</text>','<text x="30" y="54" font-size="12">Three scratch seeds per recipe. Dots are means over eight paired episodes.</text>']
    colors=['#a45d3d','#187e8b','#6d679c'];conditions=['legacy','aligned_v1','untrained'];y=lambda v:330-(v+1)*90
    for j,recipe in enumerate(r['config']['recipes']):
        x0=70+j*470;parts.append(f'<text x="{x0}" y="85" font-size="17">{recipe}: pruned MPC return</text><path d="M{x0} 95 V330 H{x0+360}" fill="none" stroke="#aabbc0"/>')
        for name,style in [('random','#999'),('greedy','#444')]:
            yy=y(s['references'][name]['mean_return']);parts.append(f'<path d="M{x0} {yy} H{x0+360}" stroke="{style}" stroke-dasharray="4 4"/><text x="{x0+365}" y="{yy+4}" font-size="11">{name}</text>')
        for k,condition in enumerate(conditions):
            x=x0+55+k*110;yy=y(s['recipes'][recipe][condition]['control']['pruned']['mean_return']);parts.append(f'<path d="M{x-22} {yy} H{x+22}" stroke="{colors[k]}" stroke-width="5"/>')
            for i,seed in enumerate(r['config']['model_seeds']):
                rows=r['control'][f'{recipe}_{seed}_{condition}']['pruned'];value=sum(e['return_sum'] for e in rows)/len(rows);parts.append(f'<circle cx="{x+(i-1)*8}" cy="{y(value)}" r="4" fill="{colors[k]}"/>')
            parts.append(f'<text x="{x-40}" y="353" font-size="12">{condition}</text>')
        for v in [-1,0,1,2]:parts.append(f'<text x="{x0-25}" y="{y(v)+4}" font-size="11">{v}</text>')
    parts.append('<text x="30" y="390" font-size="12">All paired control-gain and pruning-effect 95% intervals include zero. No general-learning claim.</text></g></svg>')
    (ROOT/'docs/assets/seed-contract-control.svg').write_text('\n'.join(parts)+'\n')
