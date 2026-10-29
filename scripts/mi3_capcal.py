"""MI-3 per-episode cap calibration from DEVELOPMENT data only (NOT LOCKED): the CPU of every exact solve in the MI-2 discovery
records (artifacts/mi2_dev/disc_a_*.json; mi2/disc pool, development data, cap 3 s). Frozen rule: cap = the smallest of
{1.0, 1.5, 2.0, 3.0} s covering >= 90 % of those solves (censored at 3 s). Writes artifacts/mi3_dev/capcal.json."""
import glob, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
t = [r["cpu_s"] for f in sorted(glob.glob(str(ROOT / "artifacts/mi2_dev/disc_a_*.json"))) for c in json.load(open(f))["cands"]
     for r in c["per_episode"] if r["exact"]]
t.sort()
cov = {c: sum(x <= c for x in t) / len(t) for c in (1.0, 1.5, 2.0, 3.0)}
cap = next(c for c in (1.0, 1.5, 2.0, 3.0) if cov[c] >= 0.9)
q = {p: t[min(len(t) - 1, int(p * len(t)))] for p in (0.5, 0.75, 0.9, 0.95, 0.99)}
out = dict(n_solves=len(t), coverage=cov, quantiles=q, cap_s=cap, max=t[-1])
(ROOT / "artifacts/mi3_dev/capcal.json").write_text(json.dumps(out, indent=1))
print(out)
