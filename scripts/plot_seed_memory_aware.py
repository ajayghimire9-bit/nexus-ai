"""Deterministic SVG from saved source evidence, no inference or collection."""
from pathlib import Path
from summarize_seed_memory_aware import analyze
ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    a=analyze();svg=['<svg xmlns="http://www.w3.org/2000/svg" width="880" height="390" viewBox="0 0 880 390">',
        '<rect width="880" height="390" fill="#101c29"/><g font-family="sans-serif" fill="#e5edf5">',
        '<text x="28" y="32" font-size="20">Seed: learned plasticity versus fixed memory protection</text>',
        '<text x="28" y="58" font-size="14">Episode-held-out source assessment: 0.36% reduction; 10% screen FAILED</text>']
    colors={'learned':'#72cbbb','fixed_protected':'#f4ba77'}
    for i,(split,row) in enumerate(a['splits'].items()):
        y=105+i*74;svg.append(f'<text x="28" y="{y+15}" font-size="15">{split}</text>')
        for j,m in enumerate(colors):
            v=row['query_auc'][m]['mean'];width=v/.26*530;yy=y+j*25
            svg.append(f'<rect x="180" y="{yy}" width="{width:.2f}" height="18" fill="{colors[m]}"/><text x="{190+width:.2f}" y="{yy+14}" font-size="13">{v:.6f}</text>')
    svg+=['<text x="28" y="337" font-size="13">Teal: learned D; orange: fixed D=I. Lower query learning-curve MSE is better.</text>',
          '<text x="28" y="357" font-size="13">Replay SGD audit MSE=12.991580 (unstable; outside chart scale). One frozen decoder.</text>',
          '<text x="28" y="377" font-size="13">Three controller seeds share source data. No control or general learning claim.</text></g></svg>']
    (ROOT/'docs/assets/seed-memory-aware.svg').write_text('\n'.join(svg))
