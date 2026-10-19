"""Deterministic stdlib SVG from saved results; no inference or collection."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    r=json.loads((ROOT/'artifacts/seed_grounded_pilot.json').read_text())
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1020" height="420" viewBox="0 0 1020 420">',
        '<rect width="1020" height="420" fill="#fff"/><g font-family="sans-serif" fill="#182a38">',
        '<text x="35" y="30" font-size="19">Seed authored pilot: learning losses and actual returns</text>',
        '<text x="35" y="54" font-size="12">One model seed per recipe. Four paired control episodes; points are not independent model replicates.</text>',
        '<path d="M60 90 V330 H460 M560 90 V330 H980" stroke="#8a959e" fill="none"/>',
        '<text x="65" y="82">Training loss (total objective)</text><text x="565" y="82">Mean actual return / episode points</text>']
    colors=['#187e8b','#b05229'];method_names=['latent_mpc','random','greedy']
    for j,m in enumerate(r['models']):
        points=' '.join(f'{60+i/119*390:.2f},{330-min(3,l["total"])/3*230:.2f}' for i,l in enumerate(m['training']['losses']))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{colors[j]}" stroke-width="2"/>')
        parts.append(f'<text x="{65+j*200}" y="365" fill="{colors[j]}">{m["recipe"]}</text>')
        for k,method in enumerate(method_names):
            x=600+k*140+j*28;values=[e['return_sum'] for e in m['control'][method]]
            y=lambda v:330-(v+1)/3*230
            parts.append(f'<path d="M{x-10} {y(sum(values)/len(values)):.2f} H{x+10}" stroke="{colors[j]}" stroke-width="4"/>')
            for i,v in enumerate(values):parts.append(f'<circle cx="{x+(i-1.5)*3}" cy="{y(v):.2f}" r="3" fill="{colors[j]}"/>')
    for k,name in enumerate(['latent MPC','random','greedy']):parts.append(f'<text x="{570+k*140}" y="355" font-size="12">{name}</text>')
    for v in range(4):parts.append(f'<text x="35" y="{334-v/3*230:.1f}" font-size="11">{v}</text>')
    for v in [-1,0,1,2]:parts.append(f'<text x="535" y="{334-(v+1)/3*230:.1f}" font-size="11">{v}</text>')
    parts.extend(['<text x="190" y="388" font-size="12">Optimizer updates 1–120</text>',
        '<text x="35" y="410" font-size="11">Lower loss is not proof of useful planning. Neither model exceeded the greedy known-grid baseline.</text></g></svg>'])
    path=ROOT/'docs/assets/seed-grounded-pilot.svg';path.write_text('\n'.join(parts)+'\n')
    print(path)


if __name__=='__main__':main()
