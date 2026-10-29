"""Phase 10B Stage 1 development checks (NOT LOCKED; development seeds / previously scored development projects only):
  1 ROUND primitive: P7 77303 (Phase 10 audit: no witness without it) - does the witness / fresh search now reach a repair?
  2 idempotent coverage: the Phase 10 wrong-repair configuration (84005 is now DEVELOPMENT data) re-run under C1@N60 with the
    fix -> must not submit a wrong repair (abstain or verify)
  3 bridge search: the two neutral-first-step audit tasks (77300, 77302) with the Phase 10 main N120 ranker + bridge flag vs
    without, standard budget 3,000
Appends one JSON line per check to artifacts/agi10b_dev/checks.jsonl."""
import copy, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agi7_diag as D  # noqa: E402
from nexus.de_phase6 import pipeline6 as P6  # noqa: E402
from nexus.de_phase7 import search7 as S7, world7 as W7  # noqa: E402
from nexus.de_phase9 import blocks9 as B  # noqa: E402
from nexus.de_phase10 import lineage10 as LN, manifest10 as MF, procedure10 as PR10  # noqa: E402
from nexus.de_phase10b import fixes10b, search10b  # noqa: E402,F401
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/agi10b_dev/checks.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)


def app(r):
    with open(OUT, "a") as fh:
        fh.write(json.dumps(r, default=str) + "\n")
    print(json.dumps(r, default=str)[:400], flush=True)


st = B.STRATA
p = W7.make_project7(st["legacy_disagreement"][0], 77303, ROOT / "var/agi10b_ws/dev/check")
truths = json.loads((Path(p["hidden_dir"]) / "stakeholder.json").read_text())["truths"]
wit = D.witness(P6.Inv6(p), p, truths)
r = S7.search(P6.Inv6(p), {}, work_budget=3000, wall_cap=10.0, mode="whole", use_skills=False)
app(dict(check="round_primitive", pid=p["pid"], witness=wit["found"], steps=[(s["op"], s["kind"]) for s in wit["steps"]], search=r["outcome"],
         verified=D.judge(p, r) if r["outcome"] == "submitted" else None))
sys.path.insert(0, str(ROOT / "scripts"))
import agi10_eval as EV  # noqa: E402
t = next(x for x in MF.eval_manifest() if x["seed"] == 84005)
p = LN.build(t, 84005, ROOT / "var/agi10b_ws/dev/check84005", require=False)
a = EV.arms()["C1@N60"]
s_ = PR10.investigate(p, PR10.Live(LN.W_SRC, LN.WALL), copy.deepcopy(a["mem"]), a["prog"], {})
o = PR10.outcome(p, s_)
app(dict(check="idempotent_coverage", pid=p["pid"], decision=s_.decision["kind"], verified=o["verified"], wrong=o["wrong"]))
ck = json.loads((ROOT / "artifacts/agi10_train/main.N120.json").read_text())
for spec, seed in ((st["conflict"][0], 77300), (st["conflict"][2], 77302)):
    p = W7.make_project7(spec, seed, ROOT / "var/agi10b_ws/dev/check")
    row = dict(check="bridge_search", pid=p["pid"])
    for tag, guide in (("ranker_no_bridge", dict(ck["memory"]["guide"], ratio=0.7)), ("ranker_bridge", dict(ck["memory"]["guide"], bridge=True, ratio=4 / 7)),
                       ("fixed", dict(kind="fixed"))):
        mem = dict(de=dict(w={}, skills={}), guide=guide)
        t0 = time.time()
        r = S7.search(P6.Inv6(p), mem, work_budget=3000, wall_cap=10.0, mode="whole", use_skills=False)
        row[tag] = dict(outcome=r["outcome"], work=r["work"], wall=round(time.time() - t0, 2), bridges=r["events"].get("bridges_marked", 0),
                        bridge_expansions=r["events"].get("bridge_expansions", 0), verified=D.judge(p, r) if r["outcome"] == "submitted" else None)
    app(row)
