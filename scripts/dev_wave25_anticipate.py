"""Dev-only (seeds 1-99): regime-B tuning grid for (lam0, m_max) of the anticipatory controller; ledgered."""
import json, sys, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"


def main():
    from nexus.wave25_anticipate import run_seed
    t0 = time.perf_counter()
    res = {}
    try:
        for lam0, mm in ((0.25, 10), (0.5, 20), (1.0, 20), (1.0, 40), (2.0, 40)):
            tot = Counter()
            for s in (1, 2, 3):
                out = run_seed(s, n_per_world=20, regimes=("B",), arms=("fixed_lambda",), lam0=lam0, m_max=mm)
                for r in out["regimes"]["B"]["rows"]:
                    tot["probes"] += r["probes"]; tot["work"] += r["work"]; tot["solved"] += r["solved"]
                    tot["fc"] += r["false_certificates"]
            res[f"{lam0}/{mm}"] = dict(tot)
            print(lam0, mm, dict(tot), flush=True)
    finally:
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run="wave25-anticipate-dev:grid", seeds=[1, 2, 3], wall_s=time.perf_counter() - t0,
                                    status="COMPLETE")) + "\n")
    print(json.dumps(res))


if __name__ == "__main__":
    main()
