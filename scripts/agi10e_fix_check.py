"""Phase 10E Stage 1A check of de_phase10e.fixes10e (NOT LOCKED; Phase 10C DEV / TRAINING projects + the consumed target 96088's
fixed specifications; no search, no learner, no new evaluation row).  python scripts/agi10e_fix_check.py OUT.json
  dev        for every Phase 10C development and training-stream workspace ALREADY BUILT under var/agi10c_ws/{dev,train} (no
             evaluation / M* target; nothing is rebuilt), fixes10e.check on the generator's TRUTH stages: any non-None verdict
             is a FALSE ABSTAIN the fix would cause on a correct submission (the first attempt rebuilt dev projects and hit its
             90 s cap, disclosed)
  c96088     fixes10e.check on the 4 forensic variants (artifacts/agi10e_c96088.json): the wrong submission V0 and the pure
             relocation V1 must be blocked; V2 (+ window start) and V3 (truth) must pass"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus.de_phase10e import fixes10e as FX  # noqa: E402


def main(out):
    res = dict(dev=[], c96088={})
    for hid in sorted(list((ROOT / "var/agi10c_ws/dev").rglob("stakeholder.json")) + list((ROOT / "var/agi10c_ws/train").rglob("stakeholder.json"))):
        ws = hid.parent.parent / "workspace"
        if not (ws / "data").exists():
            continue
        p = dict(ws=str(ws), hidden_dir=str(hid.parent), pid=hid.parent.parent.name)
        truths = json.loads(hid.read_text())["truths"]
        res["dev"].append(dict(pid=p["pid"], state=sorted(FX.W4.state_of(ws)), verdict=FX.check(p, truths)))
    v = json.loads((ROOT / "artifacts/agi10e_c96088.json").read_text())
    d = json.loads((ROOT / "artifacts/agi10c_dev/diag_96088.json").read_text())
    sub = [s["submitted"] for s in d["stages"]]
    truth = [s["truth"] for s in d["stages"]]
    import copy
    v1 = copy.deepcopy(sub)
    v1[0]["filter"], v1[1]["filter"] = sub[0]["filter"][1], v["window_end"]
    v2 = copy.deepcopy(sub)
    v2[1]["filter"] = v["window_start"]
    p = dict(ws=str(next((ROOT / "var/agi10e_ws/c96088").glob("*/workspace"))))      # rebuilt once by scripts/agi10e_c96088.py
    for name, specs in dict(V0_submitted=sub, V1_end_moved_downstream=v1, V2_submitted_plus_start=v2, V3_truth=truth).items():
        res["c96088"][name] = dict(verdict=FX.check(p, specs), hidden_ok=v["verdicts"][name])
    built = res["dev"]
    res["summary"] = dict(dev_built=len(built), dev_false_abstain=sum(r["verdict"] is not None for r in built),
                          dev_with_multikey_state=sum(any(f == "batch.json" for f in r["state"]) for r in built),
                          c96088_false_accepts=sum(x["verdict"] is None and not x["hidden_ok"] for x in res["c96088"].values()),
                          c96088_blocked_correct=sum(x["verdict"] is not None and x["hidden_ok"] for x in res["c96088"].values()))
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res["summary"]), json.dumps({k: (x["verdict"] or "pass")[:90] for k, x in res["c96088"].items()}))


if __name__ == "__main__":
    main(*sys.argv[1:])
