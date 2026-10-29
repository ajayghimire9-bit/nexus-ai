"""Phase 9 Stage 1 sensitivity audit, reduced after the first run hit its 150 s cap with nothing saved (NOT LOCKED;
development data only). Controls A, B, C, E of scripts/agi9_sensitivity.py with the same predeclared pass rules, on a
9-project development block (conflict x3, legacy disagreement x2, missing, undecided, benign, multi), no Spark engine;
results are written after EVERY memory evaluation. D (cheaper-equivalent learning) and F (method channel) are not run.
  python scripts/agi9_sensitivity_lite.py OUT.json"""
import json, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agi9_sensitivity as S  # noqa: E402
from nexus.de_phase8 import lineage8 as L8, procedure8 as PR8  # noqa: E402
from nexus.de_phase9 import blocks9 as B, compare9 as C  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
DEV = B.RANGES[("agi9de", "dev")].start + 300
out = Path(sys.argv[1])
st = B.STRATA
items = [("conflict", st["conflict"][0], DEV), ("conflict", st["conflict"][1], DEV + 1), ("conflict", st["conflict"][2], DEV + 2),
         ("legacy_disagreement", st["legacy_disagreement"][0], DEV + 3), ("legacy_disagreement", st["legacy_disagreement"][1], DEV + 4),
         ("missing", st["missing"][0], DEV + 5), ("undecided", st["undecided"][1], DEV + 6), ("benign", st["benign"][0], DEV + 7), ("multi", st["multi"][0], DEV + 8)]
res = dict(note="reduced audit (A, B, C, E); D and F not run", summaries={}, exposure={})


def save():
    res["wall"] = round(time.time() - T0, 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, default=str))


block = C.build_block(items, ROOT / "var/agi9_ws/dev/sens_lite")
res["block"] = [dict(stratum=p.get("stratum"), pid=p.get("pid"), error=p.get("error")) for p in block]
res["t_block"] = round(time.time() - T0, 1)
save()
U = S.load("FixedLearner_r1")
mems = dict(U=U, **S.variants(U))
live = PR8.Live(L8.W_SRC, L8.WALL_SRC)
rows = {}
for k in ("U", "A", "B", "C", "E"):
    rows[k] = C.eval_memory(mems[k], block, live)
    res["summaries"][k] = C.summary(rows[k])
    res["exposure"][k] = [dict(pid=p[-22:], stratum=r["stratum"], verified=r["verified"], wrong=r["wrong"], trust_used=r["trust_used"], questions=r["questions"],
                               points=[(x["kind"], x["via"], x["conflict"]) for x in r["points"]]) for p, r in rows[k].items()]
    res[f"t_{k}"] = round(time.time() - T0, 1)
    save()
    print(k, res["summaries"][k]["verified"], res["summaries"][k]["wrong"], res["summaries"][k]["trust_used"], res[f"t_{k}"], flush=True)
Sm = res["summaries"]
gate = dict(A_useful_vs_removed=dict(passed=Sm["U"]["verified"] > Sm["A"]["verified"], U=Sm["U"]["verified"], A=Sm["A"]["verified"]),
            B_useful_vs_corrupted=dict(passed=Sm["B"]["verified"] < Sm["U"]["verified"] or Sm["B"]["wrong"] > Sm["U"]["wrong"],
                                       U=[Sm["U"]["verified"], Sm["U"]["wrong"]], B=[Sm["B"]["verified"], Sm["B"]["wrong"]]),
            C_equivalent=dict(passed=Sm["C"]["solved"] == Sm["U"]["solved"] and abs(Sm["C"]["cost_s"] - Sm["U"]["cost_s"]) <= 0.01 * max(1e-9, Sm["U"]["cost_s"]),
                              U=Sm["U"]["cost_s"], C=Sm["C"]["cost_s"]),
            E_irrelevant_not_rewarded=dict(zip(("selected", "why"), C.select(Sm["U"], Sm["E"]))),
            D_cheaper_equivalent=dict(passed=None, note="not run (Stage 1 budget exhausted by the first, timed-out audit)"),
            F_method_channel=dict(sensitive=None, note="not run; method utility untested by this channel"))
gate["E_irrelevant_not_rewarded"]["passed"] = not gate["E_irrelevant_not_rewarded"]["selected"]
res["gate"] = gate
res["gate_passed"] = False if gate["D_cheaper_equivalent"]["passed"] is None else all(g["passed"] for k, g in gate.items() if k[0] in "ABCDE")
save()
print(json.dumps(gate, default=str))
print("GATE", res["gate_passed"], "wall", res["wall"])
