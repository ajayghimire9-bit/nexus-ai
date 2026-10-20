"""Deterministic SVG from existing result only; no new evaluation."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def render(r):
    a=r['analysis'];rows=[]
    for name,v in a['control'].items():
        rows.append((name,v['success'],v['mean_return']))
    s=['<svg xmlns="http://www.w3.org/2000/svg" width="940" height="410" viewBox="0 0 940 410">','<rect width="940" height="410" fill="#111b2b"/>','<g font-family="sans-serif" fill="#e6edf8"><text x="25" y="34" font-size="21">Fresh Seed action-readout development study</text><text x="25" y="59" font-size="13">One frozen core · 32 paired episodes/method · no evaluation updates</text>']
    for i,(name,success,ret) in enumerate(rows):
        y=100+i*37;color='#75d4b1' if name.startswith('readout') else '#80a8d6'
        s.append(f'<text x="25" y="{y+15}" font-size="14">{name}</text><rect x="175" y="{y}" width="{success*250:.3f}" height="20" fill="{color}"/><text x="445" y="{y+15}" font-size="14">goals {success:.1%}</text><text x="615" y="{y+15}" font-size="14">return {ret:+.3f}</text>')
    s.append('<text x="25" y="390" font-size="13">Readout beats frozen/random/MPC here; known-grid greedy remains stronger. Not general control or learning-to-learn.</text></g></svg>')
    return ''.join(s)


if __name__=='__main__':(ROOT/'docs/assets/seed-readout.svg').write_text(render(json.loads((ROOT/'artifacts/seed_surprise_readout.json').read_text())))
