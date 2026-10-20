"""Deterministic saved-data SVG; no inference or environment imports."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    r=json.loads((ROOT/'artifacts/seed_nonlinear_learning.json').read_text())
    if r['declared_complete'] is not True:raise ValueError('complete_study_required')
    a=r['analysis'];colors={'learned':'#007c66','static':'#b05b00','fixed':'#4565ad','replay':'#a53e86','none':'#687584'}
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="590" viewBox="0 0 1000 590">',
        '<rect width="1000" height="590" fill="#ffffff"/>',
        '<g font-family="sans-serif" fill="#17283c">',
        '<text x="65" y="35" font-size="22">Frozen nonlinear features: learning after 1, 2, 4 and 8 examples</text>',
        '<text x="65" y="60" font-size="14">Means and exploratory 95% paired-task intervals; eight tasks, one frozen core</text>']
    ymax=max(v['mse']['ci95'][1] for methods in a['per_budget'].values() for v in methods.values())*1.08
    x=lambda b:75+(b-1)*95
    y=lambda v:450-350*v/ymax
    for j in range(6):
        value=ymax*j/5;yy=y(value)
        svg.extend([f'<line x1="75" x2="740" y1="{yy}" y2="{yy}" stroke="#e0e5eb"/>',f'<text x="5" y="{yy+4}" font-size="12">{value:.4f}</text>'])
    for b in (1,2,4,8):svg.append(f'<text x="{x(b)-4}" y="475">{b}</text>')
    svg.extend(['<text x="320" y="505">Observed teaching examples</text>','<text x="75" y="90">Held-out query MSE (raw reward²)</text>'])
    for i,(m,color) in enumerate(colors.items()):
        points=[]
        for b in (1,2,4,8):
            v=a['per_budget'][str(b)][m]['mse'];xx=x(b);lo,hi=v['ci95'];points.append(f'{xx},{y(v["mean"])}')
            svg.extend([f'<line x1="{xx}" x2="{xx}" y1="{y(max(0,lo))}" y2="{y(hi)}" stroke="{color}" opacity=".5"/>',f'<circle cx="{xx}" cy="{y(v["mean"])}" r="4" fill="{color}"/>'])
        svg.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/>')
        svg.append(f'<text x="790" y="{125+30*i}" fill="{color}">{m}</text>')
    svg.extend([f'<text x="65" y="545">Registered combined screen: {"PASS" if a["screen_passed"] else "FAIL"}. Historical weights unchanged.</text>',
        '<text x="65" y="570">Source-only outer fitting; independent development assessment. No general learning-to-learn claim.</text>','</g></svg>'])
    path=ROOT/'artifacts/seed_nonlinear_learning_curve.svg'
    with path.open('x') as f:f.write('\n'.join(svg))
    print(path)


if __name__=='__main__':main()
