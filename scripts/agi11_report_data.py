"""Phase 11 Stage 5: report data from the committed artifacts (NOT LOCKED; analysis only).  python scripts/agi11_report_data.py OUT.json"""
import json, sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus.de_phase11 import abstr11 as A, core11 as C  # noqa: E402


def main(out):
    res = {}
    for r in ("rep0", "rep1"):
        rows = [json.loads(l) for l in open(ROOT / f"artifacts/agi11_stageA/{r}.tasks.jsonl") if '"event"' not in l]
        fin = json.loads((ROOT / f"artifacts/agi11_stageA/{r}.final.json").read_text())
        lib = A.load_library(fin["library"])
        fams = Counter(x["family"] for x in rows)
        ver = Counter(x["family"] for x in rows if x["verified"])
        funcs = []
        for a in fin["acquisitions"]:
            f = lib[a["name"]]
            body = A._ground(f["body"], f["params"])
            funcs.append(dict(name=a["name"], cls=a["class"], kind=a["kind"], params=f["params"], body=f["body"], expanded_size=C.size(body), ops=a["ops"],
                              support_projects=a["support"], instances=a["instances"], compression=a["compression"], acquired_after_task=a["acquired_after_task"],
                              support_families=sorted({x["family"] for x in rows if x["task"] in a["support"]}),
                              stageA_uses_after=sum(a["name"] in x.get("uses", []) for x in rows if x["verified"] and x["i"] >= a["acquired_after_task"])))
        rb = [json.loads(l) for l in open(ROOT / f"artifacts/agi11_stageB/{r}.tasks.jsonl") if '"event"' not in l]
        res[r] = dict(stageA=dict(tasks=len(rows), verified=sum(x["verified"] for x in rows), wrong=sum(x["wrong"] for x in rows), submitted=sum(x["outcome"] == "submitted" for x in rows),
                                  per_family={k: f"{ver[k]}/{v}" for k, v in sorted(fams.items())}, functions=funcs, wall_bound=sum(x["wall_bound"] for x in rows)),
                      stageB=dict(tasks=len(rb), verified=sum(x["verified"] for x in rb), wrong=sum(x["wrong"] for x in rb), submitted=sum(x["outcome"] == "submitted" for x in rb),
                                  wall_bound=sum(x["wall_bound"] for x in rb), uses=Counter(u for x in rb if x["verified"] for u in x["uses"])))
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    for r, v in res.items():
        print(r, v["stageA"]["per_family"], [(f["name"], f["cls"], f["expanded_size"], f["support_families"], f["stageA_uses_after"]) for f in v["stageA"]["functions"]], v["stageB"])


if __name__ == "__main__":
    main(*sys.argv[1:])
