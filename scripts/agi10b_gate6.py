"""Phase 10B gate control 6, redefined by the owner as the SKILL / BRIDGE-MACRO / RANKER UTILITY control (NOT LOCKED;
development seeds 90600-90799; agi9de/confirm stays unopened unless this passes).
  learned   L* = the Phase 10 main-lineage N120 library  +  its learned ranker with BRIDGE expansion (search10b)
  plain     no library, the fixed (unguided) order
Both: the same total work budget (3,000), search8 method queue, fixes10b (ROUND primitive, idempotent coverage) for both.
PREDECLARED RULE (completion-based, as in 9B): screen 12 development projects with zero-gain first steps (all-fault P1
window + dup_id, P5 replay + thresholds, P4, X1; P7 pit + ratio), two seeds each; every spec where 'learned' verified and
'plain' did not is REPLICATED on 3 fresh seeds; pass iff on the replication seeds 'learned' verifies strictly more than
'plain', with 0 wrong in both. One JSON line per search is appended."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agi9b_gate as G9  # noqa: E402
from nexus.de_phase6 import world6 as W6  # noqa: E402
from nexus.de_phase8 import lineage8 as L8  # noqa: E402
from nexus.de_phase10b import fixes10b, search10b  # noqa: E402,F401
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/agi10b_dev/gate6.jsonl"


def app(row):
    with open(OUT, "a") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
        fh.flush()


def main():
    ck = json.loads((ROOT / "artifacts/agi10_train/main.N120.json").read_text())
    learned = dict(L8.empty_memory(), de=dict(w={}, skills=ck["memory"]["de"]["skills"]), guide=dict(ck["memory"]["guide"], bridge=True, ratio=4 / 7))
    plain = dict(L8.empty_memory(), guide=dict(kind="fixed"))
    done = [json.loads(l) for l in OUT.read_text().splitlines()] if OUT.exists() else []
    seen = {(r.get("phase"), r.get("seed")) for r in done}
    specs = [dict(paradigm="P1", engine="sqlite", fault_p=1.0), dict(paradigm="P1", engine="duckdb", fault_p=1.0), dict(paradigm="P5", engine="sqlite", fault_p=1.0),
             dict(paradigm="P5", engine="duckdb", fault_p=1.0), dict(paradigm="P4", engine="duckdb", fault_p=1.0), dict(paradigm="X1", fault_p=1.0),
             dict(paradigm="P7", engine="duckdb", fault_p=1.0)]
    s = 90600
    for rep in range(2):
        for spec in specs:
            seed, s = s, s + 1
            if ("screen", seed) in seen:
                continue
            try:
                p = W6.make_project6(spec, seed, ROOT / "var/agi10b_ws/dev/gate6")
            except RuntimeError:
                continue
            a, b = G9._search(p, learned), G9._search(p, plain)
            app(dict(phase="screen", seed=seed, spec=spec, learned=a, plain=b))
            print("screen", spec, a["verified"], b["verified"], a["work"], b["work"], flush=True)
    rows = [json.loads(l) for l in OUT.read_text().splitlines()]
    winners = []
    for r in rows:
        if r.get("phase") == "screen" and r["learned"]["verified"] and not r["plain"]["verified"] and r["spec"] not in winners:
            winners.append(r["spec"])
    s = 90700
    for spec in winners:
        for k in range(3):
            seed, s = s, s + 1
            if ("replicate", seed) in seen:
                continue
            try:
                p = W6.make_project6(spec, seed, ROOT / "var/agi10b_ws/dev/gate6_rep")
            except RuntimeError:
                continue
            a, b = G9._search(p, learned), G9._search(p, plain)
            app(dict(phase="replicate", seed=seed, spec=spec, learned=a, plain=b))
            print("replicate", spec, a["verified"], b["verified"], flush=True)
    rows = [json.loads(l) for l in OUT.read_text().splitlines()]
    rep = [r for r in rows if r.get("phase") == "replicate"]
    passed = bool(rep) and sum(r["learned"]["verified"] for r in rep) > sum(r["plain"]["verified"] for r in rep) and \
        not any(r["learned"]["wrong"] or r["plain"]["wrong"] for r in rep + [r for r in rows if r.get("phase") == "screen"])
    res = dict(passed=passed, winners=winners, screen=[(r["spec"]["paradigm"], r["learned"]["verified"], r["plain"]["verified"], r["learned"]["work"], r["plain"]["work"])
                                                       for r in rows if r.get("phase") == "screen"], replicate=[(r["spec"]["paradigm"], r["learned"]["verified"], r["plain"]["verified"]) for r in rep])
    (ROOT / "artifacts/agi10b_dev/gate6.json").write_text(json.dumps(res, indent=1))
    print("GATE6", passed, res["replicate"])


if __name__ == "__main__":
    main()
