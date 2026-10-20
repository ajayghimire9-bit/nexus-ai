"""Plot existing results only; no worlds or inference."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def render(r):
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="430" viewBox="0 0 960 430"><rect width="960" height="430" fill="#111b2b"/><g fill="#e6edf8" font-family="sans-serif"><text x="24" y="32" font-size="21">Frozen Seed action scorer: spatial-transfer development</text><text x="24" y="57" font-size="13">Goal completion · same one core · all models frozen · greedy 100% in every group</text>']
    for i,(g,a) in enumerate(r['analysis']['groups'].items()):
        y=85+75*i;heads=sum(a['control'][f'readout_{s}']['goal_rate'] for s in r['config']['head_seeds'])/3
        parts.append(f'<text x="24" y="{y+14}" font-size="14">{g}</text>')
        for j,(label,val,color) in enumerate([('readout',heads,'#75d4b1'),('frozen',a['control']['frozen']['goal_rate'],'#80a8d6'),('random',a['control']['random']['goal_rate'],'#efbd72')]):
            yy=y+j*16;parts.append(f'<rect x="210" y="{yy}" width="{val*350:.3f}" height="12" fill="{color}"/><text x="590" y="{yy+11}" font-size="12">{label}: {val:.1%}</text>')
    parts.append('<text x="24" y="415" font-size="13">Primary passed versus frozen ranking; cross-diagonal goals trail random. Not learning-to-learn.</text></g></svg>')
    return ''.join(parts)


if __name__=='__main__':(ROOT/'docs/assets/seed-spatial-transfer.svg').write_text(render(json.loads((ROOT/'artifacts/seed_spatial_transfer.json').read_text())))
