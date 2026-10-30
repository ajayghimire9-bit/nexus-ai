"""Phase 10E Stage 2 diagnostic (NOT LOCKED; training-stream projects only): why rep0's replay-macro candidate lost the `ckey`
key role. For each of its source projects (wake or dream), rebuild it and report the schema.yml unique tests seen by Inv10e and
the Phase 10E roles of the truth dedup key / order column at the root.  python scripts/agi10e_diag_ckey.py"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase10d import world10d as W  # noqa: E402
from nexus.de_phase10e import dag10e as D, manifest10e as ME  # noqa: E402

for rep, seed in ((0, 101042), (0, 101028), (0, 101201), (1, 101711), (1, 101548)):
    b = ME.train(rep)
    kind = "wake" if seed in b["wake"] else "dream" if seed in b["dream"] else "admit"
    if kind == "wake":
        i = seed - b["wake"].start
    else:
        i = next(json.loads(l) for l in open(ROOT / f"artifacts/agi10e_train/rep{rep}.dreams.jsonl") if json.loads(l)["project"].endswith(str(seed)))
        i = None
    spec = ME.train_spec(rep, i) if i is not None else dict(family="S_replay", faults=["replay"], engine=None, legacy=None)
    if i is None:
        pid = next(json.loads(l)["project"] for l in open(ROOT / f"artifacts/agi10e_train/rep{rep}.dreams.jsonl") if json.loads(l)["project"].endswith(str(seed)))
        _, fam, eng, leg, _ = pid.split(".")
        spec = dict(family=fam, faults=list(ME.TRAIN_FAMILIES[fam]), engine=eng, legacy=leg, names="base")
    p = W.make_project10d(spec, seed, ROOT / "var/agi10e_ws/diagckey")
    inv = D.Inv10e(p)
    t = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())["stg"]["stg_order_items"]["dedup"]
    dom = inv.dom(0, inv.legacy)
    kc, oc = t["key"][1][1], t["order"][1][1]
    print(rep, seed, kind, p["pid"], "ukeys(stg_order_items)", sorted(c for r, c in inv.ukeys if r == "stg_order_items"),
          "key", kc, dom.roles("stg_order_items", kc), "order", oc, dom.roles("stg_order_items", oc))
