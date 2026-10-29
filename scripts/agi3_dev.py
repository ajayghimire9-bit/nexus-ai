"""Phase 3 Stage 1 development checks (NOT LOCKED; development project seeds 51000-51499 and agi3/dev only).
  python scripts/agi3_dev.py de RUNTIME N [BUDGET]   memory-free DE learner on N dev projects per source family x level
  (more modes are added below)"""
import json, sys, time
from pathlib import Path
from nexus.campaign3 import de_world as W, de_learner as DL
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/agi3_dev"
WS = ROOT / "var/agi3_ws/dev"


def de(runtime, n, budget="2.0"):
    rt = W.RUNTIMES[runtime]()
    if runtime == "spark":
        W.SparkRuntime.warm()
    rows = []
    k = 0
    for fam in ("G1", "G2", "G3", "G4"):
        for lv in (1, 2):
            for j in range(int(n)):
                s = 51000 + k
                k += 1
                p = W.make_project(fam, lv, s, runtime, WS)
                rec = DL.solve(p, DL.empty_de(), rt, budget_s=float(budget))
                ev = W.evaluate(p, rec["spec"], rt) if rec["solved_visible"] else None
                rows.append(dict(pid=p["pid"], legacy_failed=rec["start"]["failed"], legacy_error=rec["start"].get("error"),
                                 solved_visible=rec["solved_visible"], hidden_ok=bool(ev and ev["ok"]), edits=rec["edits"],
                                 runs=rec["runs"], wall=rec["wall"], fails=ev and ev["fails"]))
                print(p["pid"], "legacy", rec["start"]["failed"], rec["start"].get("error"), "| solved", rec["solved_visible"],
                      "hidden", bool(ev and ev["ok"]), rec["edits"], "runs", rec["runs"], "wall", rec["wall"], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"de_{runtime}.json").write_text(json.dumps(rows, indent=1, default=str))
    print("solved", sum(r["hidden_ok"] for r in rows), "/", len(rows), "silent", sum(r["solved_visible"] and not r["hidden_ok"] for r in rows))




def untouched():
    """Generator self-check of C7, C8, E7, E8 only (determinism, reference passes, constants fail) - NO learner."""
    from nexus.campaign3.worlds3 import make_task3, UNTOUCHED3
    from nexus.campaign3 import seeds as SD
    from nexus.campaign.worlds import verify
    bad, n = [], 0
    for i, (w, f) in enumerate(UNTOUCHED3):
        for lv in (1, 2, 3):
            s = SD.RANGES[("agi3", "dev")].start + 800 + 10 * i + lv
            a = make_task3(w, f, lv, s, "untouched3", SD.partners_for(w, f, "untouched3"))
            b = make_task3(w, f, lv, s, "untouched3", SD.partners_for(w, f, "untouched3"))
            ok = [a.ref(x) for x in a.hidden_x] == [b.ref(x) for x in b.hidden_x] and verify(a, a.ref)["ok"] and \
                not verify(a, lambda x: 0)["ok"] and not verify(a, lambda x: ())["ok"]
            n += 1
            bad += [] if ok else [a.tid]
    (OUT / "untouched3_check.json").write_text(json.dumps(dict(n=n, bad=bad, note="generator self-check only")))
    print("untouched3 generator checks", n, "bad", bad)


if __name__ == "__main__":
    {"de": de, "untouched": untouched}[sys.argv[1]](*sys.argv[2:])
