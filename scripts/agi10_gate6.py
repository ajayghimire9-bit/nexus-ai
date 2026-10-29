"""Phase 10 retest of the Phase 9B gate control 6 (skill / utility removal) with the wake-sleep library (NOT LOCKED;
development seeds 81850-81949, disjoint from every earlier screen and from the unopened agi9de/confirm range).
Controls 1-5 passed in Phase 9B (artifacts/agi9b_dev/gate.json) and are NOT rerun: only the library can change.
L* = the Phase 10 main-lineage N120 library  U  every admitted method of the Phase 7 / 8 checkpoints (canonical union).
SAME RULE as Phase 9B (predeclared, completion-based): on fresh REPLICATION seeds of every screen spec where L* verified and
the base did not, the with-L* arm verifies strictly more than the without-L* arm, with 0 wrong in both. Screen specs: the
budget-binding regime found by the Stage 1A audit (P1 window + dup_id, P5 replay + thresholds, whose first repair step is
score-neutral) plus the Phase 9B specs (all-fault P2 / P6 / P4 / X1); two seeds each. Appends one line per search."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agi9b_gate as G9  # noqa: E402
from nexus.de_phase6 import world6 as W6  # noqa: E402
from nexus.de_phase8 import lineage8 as L8  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/agi10_dev/gate6.jsonl"


def library():
    lib = {s["canonical"]: s for s in G9.library().values()}
    ck = json.loads((ROOT / "artifacts/agi10_train/main.N120.json").read_text())
    for s in ck["memory"]["de"]["skills"].values():
        lib.setdefault(s["canonical"], dict(s, uses=0))
    return {f"L{i}": s for i, s in enumerate(lib.values())}


def app(row):
    with open(OUT, "a") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
        fh.flush()


def main():
    L = library()
    with_m = dict(L8.empty_memory(), de=dict(w={}, skills=L))
    without = L8.empty_memory()
    done = [json.loads(l) for l in OUT.read_text().splitlines()] if OUT.exists() else []
    if not done:
        app(dict(library=[s["canonical"] for s in L.values()], n=len(L)))
    seen = {(r.get("phase"), r.get("seed")) for r in done}
    specs = [dict(paradigm="P1", engine="sqlite", fault_p=1.0), dict(paradigm="P1", engine="duckdb", fault_p=1.0), dict(paradigm="P5", engine="sqlite", fault_p=1.0),
             dict(paradigm="P5", engine="duckdb", fault_p=1.0), dict(paradigm="P2", engine="duckdb", fault_p=1.0), dict(paradigm="P6", engine="sqlite", fault_p=1.0),
             dict(paradigm="P4", engine="duckdb", fault_p=1.0), dict(paradigm="X1", fault_p=1.0)]
    s = 81850
    for rep in range(2):
        for spec in specs:
            seed, s = s, s + 1
            if ("screen", seed) in seen:
                continue
            try:
                p = W6.make_project6(spec, seed, ROOT / "var/agi10_ws/dev/gate6")
            except RuntimeError:
                continue
            a, b = G9._search(p, with_m), G9._search(p, without)
            app(dict(phase="screen", seed=seed, spec=spec, with_L=a, without_L=b))
            print("screen", spec, a["verified"], b["verified"], a["work"], b["work"], flush=True)
    rows = [json.loads(l) for l in OUT.read_text().splitlines()]
    winners = []
    for r in rows:
        if r.get("phase") == "screen" and r["with_L"]["verified"] and not r["without_L"]["verified"] and r["spec"] not in winners:
            winners.append(r["spec"])
    s = 81920
    for spec in winners:
        for k in range(3):
            seed, s = s, s + 1
            if ("replicate", seed) in seen:
                continue
            try:
                p = W6.make_project6(spec, seed, ROOT / "var/agi10_ws/dev/gate6_rep")
            except RuntimeError:
                continue
            a, b = G9._search(p, with_m), G9._search(p, without)
            app(dict(phase="replicate", seed=seed, spec=spec, with_L=a, without_L=b))
            print("replicate", spec, a["verified"], b["verified"], flush=True)
    rows = [json.loads(l) for l in OUT.read_text().splitlines()]
    rep = [r for r in rows if r.get("phase") == "replicate"]
    passed = bool(rep) and sum(r["with_L"]["verified"] for r in rep) > sum(r["without_L"]["verified"] for r in rep) and \
        not any(r["with_L"]["wrong"] or r["without_L"]["wrong"] for r in rep)
    res = dict(passed=passed, library_size=len(L), screen=[(r["spec"]["paradigm"], r["with_L"]["verified"], r["without_L"]["verified"], r["with_L"]["work"], r["without_L"]["work"])
                                                          for r in rows if r.get("phase") == "screen"],
               replicate=[(r["spec"]["paradigm"], r["with_L"]["verified"], r["without_L"]["verified"]) for r in rep], winners=winners)
    (ROOT / "artifacts/agi10_dev/gate6.json").write_text(json.dumps(res, indent=1))
    print("GATE6", passed, res["replicate"])


if __name__ == "__main__":
    main()
