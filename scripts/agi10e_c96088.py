"""Phase 10E Stage 1A forensic: what actually made Phase 10C Draw C target 96088 wrong (NOT LOCKED; no new evaluation row, no
learner, no search: the already-consumed target is rebuilt only to execute FIXED specifications against its hidden batches).
  python scripts/agi10e_c96088.py OUT.json
Variants (the submitted specs come from the saved Phase 10C diagnostic artifacts/agi10c_dev/diag_96088.json):
  V0 submitted              window-end predicate merged into the CDC stage filter (P4 IR: a stage applies dedup THEN filter)
  V1 end moved downstream   the same predicate moved to the window stage (pure relocation across the stage boundary)
  V2 V0 + window start      the submitted specs plus the missing window-start predicate in the window stage
  V3 truth                  the generator's stages
For each variant: the hidden verdict per batch (world6.evaluate6, the stage engines) and the reference outputs; plus the
witness rows on which V0 and V1 differ, if any."""
import copy, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus.de_phase4 import ir as IR4, world as W  # noqa: E402
from nexus.de_phase6 import ir6, world6 as W6  # noqa: E402


def main(out):
    from nexus.de_phase10c import lineage10c as LC
    import agi10c_mstar as MS
    d = json.loads((ROOT / "artifacts/agi10c_dev/diag_96088.json").read_text())
    t = next(x for x in MS.DRAW_C if x["seed"] == 96088)
    p = LC.build(t, t["seed"], ROOT / "var/agi10e_ws/c96088")
    sub = [s["submitted"] for s in d["stages"]]
    truth = [s["truth"] for s in d["stages"]]
    end = sub[0]["filter"][2]
    start = truth[1]["filter"][1]
    v1 = copy.deepcopy(sub)
    v1[0]["filter"] = sub[0]["filter"][1]
    v1[1]["filter"] = end
    v2 = copy.deepcopy(sub)
    v2[1]["filter"] = start
    V = dict(V0_submitted=sub, V1_end_moved_downstream=v1, V2_submitted_plus_start=v2, V3_truth=truth)
    res = dict(pid=p["pid"], window_end=end, window_start=start, variants={})
    hid = Path(p["hidden_dir"])
    for name, specs in V.items():
        files = [ir6.lower(s, stg["target_lang"]) for s, stg in zip(specs, p["stages"])]
        ev = W6.evaluate6(p, files)
        outs = {}
        for b in ("visible", "hidden1.csv", "hidden2.csv"):
            if b == "visible":
                header, rows = W.read_csv(Path(p["ws"]) / "data" / "batch.csv") if (Path(p["ws"]) / "data" / "batch.csv").exists() else (None, None)
                continue
            header, rows = W.read_csv(hid / b)
            state = dict(W.state_of(p["ws"]), **p["hidden_state"][b])
            cur = rows
            for s in specs:
                cur = [{c: ("" if v is None else str(v)) for c, v in r.items() if c != "__rowid"} for r in IR4.interpret(s, cur, state)["clean"]]
            outs[b] = sorted(json.dumps(r, sort_keys=True) for r in cur)
        res["variants"][name] = dict(hidden=ev, ref_outputs=outs)
    a, b = res["variants"]["V0_submitted"]["ref_outputs"], res["variants"]["V1_end_moved_downstream"]["ref_outputs"]
    res["V0_equals_V1_on_hidden_reference"] = a == b
    res["verdicts"] = {k: v["hidden"]["ok"] for k, v in res["variants"].items()}
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(dict(verdicts=res["verdicts"], fails={k: v["hidden"]["fails"] for k, v in res["variants"].items()},
                          V0_equals_V1=res["V0_equals_V1_on_hidden_reference"], end=end, start=start), default=str))


if __name__ == "__main__":
    main(*sys.argv[1:])
