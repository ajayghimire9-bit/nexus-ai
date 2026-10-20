"""Saved-data SVG with task-stream uncertainty; no world/model execution."""
from pathlib import Path
import json
import statistics as st
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_seed_learning_validation import verify,ROOT


if __name__=='__main__':
    a=verify();raw=json.loads((ROOT/'artifacts/seed_learning_validation.json').read_text());c=raw['config']
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="840" viewBox="0 0 1000 840">',
         '<rect width="1000" height="840" fill="white"/><g font-family="sans-serif" fill="#222">',
         '<text x="35" y="32" font-size="22">Fresh Seed learning and action validation: primary screens failed</text>',
         '<text x="35" y="58" font-size="14">One frozen GRU core; three controller seeds averaged within eight fresh task streams</text>',
         '<text x="35" y="92" font-size="18">Held-out reward-prediction MSE after teaching</text>']
    x=lambda k:160+{1:0,2:1,4:2,8:3}[k]*235
    y=lambda v:330-(v-.09)/.22*205
    for tick in (.10,.15,.20,.25,.30):
        yy=y(tick);svg.append(f'<path d="M150 {yy:.1f}H890" stroke="#ddd"/><text x="100" y="{yy+5:.1f}" font-size="13">{tick:.2f}</text>')
    colors={'learned':'#be503d','fixed':'#747b84','replay':'#237da6','none':'#202b32','neutral':'#b0b6bb'}
    for method,color in colors.items():
        points=[]
        for k in c['budgets']:
            values=[st.mean(next(row['query_mse'] for row in m['curves']['audit'][i]['methods'][method] if row['budget']==k) for m in raw['controllers']) for i in range(8)]
            mean=st.mean(values);half=2.364624251*st.stdev(values)/8**.5;xx=x(k);points.append(f'{xx},{y(mean):.2f}')
            if method in ('learned','replay'):
                svg.append(f'<path d="M{xx} {y(mean-half):.2f}V{y(mean+half):.2f}" stroke="{color}" stroke-width="1.2"/>')
        dash=' stroke-dasharray="5 4"' if method in ('none','neutral') else ''
        svg.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2.3"{dash}/>')
    for k in c['budgets']:svg.append(f'<text x="{x(k)-4}" y="355" font-size="14">{k}</text>')
    svg+=['<text x="385" y="379" font-size="14">Observed teaching examples (log2 spacing)</text>',
           '<text x="22" y="255" transform="rotate(-90 22 255)" font-size="14">Query residual-reward MSE</text>']
    for i,(method,color) in enumerate(colors.items()):
        xx=90+i*178;svg.append(f'<path d="M{xx} 407H{xx+22}" stroke="{color}" stroke-width="3"/><text x="{xx+28}" y="412" font-size="13">{method}</text>')
    svg.append('<text x="35" y="454" font-size="18">Actual 12-step authored control: mean return and task-stream 95% intervals</text>')
    px=lambda v:220+(v+1.6)/3.5*650
    for i,method in enumerate(('learned','fixed','replay','none','frozen','grid')):
        yy=490+i*39;values=[]
        for task in raw['control'].values():
            es=[e for name,rows in task.items() if name==method or name.endswith('/'+method) for e in rows]
            values.append(st.mean(e['return_sum'] for e in es))
        mean=st.mean(values);half=2.364624251*st.stdev(values)/8**.5;color=colors.get(method,'#747b84')
        start=min(px(0),px(mean));width=abs(px(mean)-px(0))
        svg.append(f'<text x="35" y="{yy+5}" font-size="14">{method}</text><rect x="{start:.2f}" y="{yy-10}" width="{width:.2f}" height="20" fill="{color}"/><path d="M{px(mean-half):.2f} {yy}H{px(mean+half):.2f}" stroke="#222"/><circle cx="{px(mean):.2f}" cy="{yy}" r="3" fill="#222"/><text x="900" y="{yy+5}" font-size="13">{a["control"][method]["goal_rate"]:.1%} goals</text>')
    for tick in (-1.5,-1.,-.5,0.,.5,1.,1.5):svg.append(f'<text x="{px(tick)-10:.1f}" y="739" font-size="12">{tick:g}</text>')
    svg+=['<text x="360" y="762" font-size="14">Episodic return (authored reward units)</text>',
           '<text x="35" y="794" font-size="13">Bars/intervals aggregate inside task streams; episodes and controller seeds are not world-model replications.</text>',
           '<text x="35" y="819" font-size="12">Source: seed_learning_validation.json; execution39dd835. Error bars exploratory; no control/transfer success.</text></g></svg>']
    (ROOT/'docs/assets/seed-learning-validation.svg').write_text('\n'.join(svg))
