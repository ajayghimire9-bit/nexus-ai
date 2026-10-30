"""Phase 10C wrong-submission diagnostic (NOT LOCKED; development data only).  python scripts/agi10c_diag.py CASE OUT.json
CASE x2_10b  : Phase 10B rep1 training task 22 (P6.X2 seed 88021, manifest10.train_spec(21, 88021)) with the rep1 N25.preM memory
               (the nearest saved memory; the exact N21 memory was not checkpointed) under the Phase 10B configuration
--fix        : with the Phase 10C shared verifier fix (fixes10c)
CASE h5_dev  : Phase 10C dev target 91940 (H5) with the dev A4_rep0 arm memory
Rebuilds the project, re-runs the investigation, and on a submission reports the hidden verdict per batch, the submitted vs
true stage specifications, the visible checks, the decision points / coverage obligations and how each was resolved."""
import copy, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase6 import pipeline6 as P6  # noqa: E402
from nexus.de_phase8 import procedure8 as PR8  # noqa: E402
from nexus.de_phase10 import lineage10 as LN, manifest10 as MF, procedure10 as PR10  # noqa: E402


def report(p, st, live):
    o = PR10.outcome(p, st)
    truths = json.loads((Path(p["hidden_dir"]) / "stakeholder.json").read_text())["truths"]
    specs = PR8.chosen_specs(st) if st.decision["kind"] == "submit" else None
    cand = st.cand or {}
    inv = P6.Inv6(p)
    ev = inv.run(specs, True) if specs else None
    stages = []
    for k in range(len(p["stages"])):
        s = specs[k] if specs else None
        stages.append(dict(paradigm=p["stages"][k]["paradigm"], mechs=p["stages"][k]["mechs"], faults=p["stages"][k]["faults"], engine=p["stages"][k]["engine"],
                           equal_truth=s == truths[k], submitted=s, truth=truths[k], legacy=inv.legacy[k]))
    return dict(pid=p["pid"], faults=p["faults"], decision=st.decision, outcome={k: v for k, v in o.items() if k != "files"}, path=cand.get("path"),
                search_path_specs_equal_chosen=cand.get("specs") == specs, visible=dict(ok=ev["ok"], failed=ev["failed"], held_ok=ev["held_ok"]) if ev else None,
                dps=[{k: d.get(k) for k in ("stage", "pos", "kind", "options", "effects", "resolved", "via", "conflict", "legacy_effect", "undecided")} for d in st.dps],
                choices=st.decision.get("choices"), obligation_status=st.obligation_status, stages=stages, dp_modes=p.get("dp_modes"),
                state_hidden=p.get("hidden_state"))


def main(case, out, *flags):
    if "--fix" in flags:
        from nexus.de_phase10c import fixes10c  # noqa: F401
    if case != "x2_10b":
        W.SparkCode.warm()
    if case == "x2_10b":
        from nexus.de_phase10b import fixes10b, search10b  # noqa: F401
        mem = json.loads((ROOT / "artifacts/agi10b_train/rep1.N25.preM.json").read_text())["memory"]
        p = LN.build(MF.train_spec(21, 88021), 88021, ROOT / "var/agi10c_ws/diag", require=False)
        live = PR10.Live(LN.W_SRC, LN.WALL)
    else:
        from nexus.de_phase10c import lineage10c as LC, manifest10c as MC
        import agi10c_train as TRN
        m = json.loads((ROOT / "artifacts/agi10c_dev/train/rep0.final.json").read_text())["memory"]
        mem = LC.arm_memory(TRN.fixed_trust()[0], skills=m["de"]["skills"], guide_w=m["guides"]["Lstar"])
        t = next(x for x in MC.dev_manifest() if x["seed"] == 91940)
        p = LC.build(t, t["seed"], ROOT / "var/agi10c_ws/diag")
        live = LC.Live(LN.W_SRC, LN.WALL)
    st = PR10.investigate(p, live, copy.deepcopy(mem), PR10.F0, {})
    r = report(p, st, live)
    Path(out).write_text(json.dumps(r, indent=1, default=str))
    print(json.dumps({k: r[k] for k in ("pid", "faults", "outcome", "path", "visible", "search_path_specs_equal_chosen")}, default=str))
    for s in r["stages"]:
        print(s["paradigm"], s["faults"], "equal_truth", s["equal_truth"])
        if not s["equal_truth"]:
            print("  SUB ", json.dumps(s["submitted"])[:700])
            print("  TRUE", json.dumps(s["truth"])[:700])
    for d in r["dps"]:
        print("dp", d)


if __name__ == "__main__":
    main(*sys.argv[1:])
