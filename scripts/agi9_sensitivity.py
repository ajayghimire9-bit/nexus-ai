"""Phase 9 Stage 1 comparator sensitivity audit (NOT LOCKED; development data only, agi9de/dev seeds). These controls test
the EVALUATOR, never NEXUS's invention; nothing here is counted as a learned improvement or transfer.
  python scripts/agi9_sensitivity.py OUT.json
Memories (from the Phase 8 trained FixedLearner checkpoints, development use):
  U  useful experienced memory (FixedLearner_r1: 39 calibrated trust records)
  A  relevant-memory ablation: U with the trust records removed
  B  corrupted evidence: U with every trust record's verified agreement label flipped
  C  equivalent memory: U with trust records reordered, skill keys renamed and skill sources reordered (same semantics)
  E  irrelevant extra experience: U + skill sources duplicated x3, evidence weights for features that never occur, and
     feature-less trust records (more memory, no new usable evidence)
  D  equal learning at lower cost: two 9-project balanced trajectories from U on the SAME stream - normal vs one with a
     controlled REDUNDANT computation (an extra discarded live search per project); same acquired memory, more C_acquire
  F  method channel: FixedLearner_r0's admitted method vs its removal on applicable development projects (search8 with
     identical total budget)
PREDECLARED GATE (fixed before running): A: U verifies more than A on the block. B: B verifies fewer than U or accepts
more wrong repairs. C: identical verified set and cost within 1 %. D: the selection rule prefers normal over redundant
(and never the reverse) and the two memories are identical. E: E is not selected over U. F: reported as sensitive if any
completion or >= 10 % work difference on comparable correct completions, else INSENSITIVE (method utility untested).
The gate passes iff A-E pass."""
import copy, json, random, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase6 import trust6 as T6, world6 as W6, pipeline6 as P6  # noqa: E402
from nexus.de_phase8 import lineage8 as L8, procedure8 as PR8  # noqa: E402
from nexus.de_phase9 import blocks9 as B, compare9 as C  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
DEV = B.RANGES[("agi9de", "dev")].start


def load(n):
    m = json.loads((ROOT / f"artifacts/agi8_src/{n}.json").read_text())["memory"]
    m.setdefault("policy_w", None)
    m["M"]["batch"] = 9
    return m


def variants(U):
    A = copy.deepcopy(U)
    A["trust"] = T6.empty()
    Bm = copy.deepcopy(U)
    for r in Bm["trust"]["records"]:
        r["agreed"] = not r["agreed"]
    T6.refit(Bm["trust"])
    Cm = copy.deepcopy(U)
    Cm["trust"]["records"] = list(reversed(Cm["trust"]["records"]))
    T6.refit(Cm["trust"])
    Cm["de"]["skills"] = {f"renamed_{k}": v for k, v in Cm["de"]["skills"].items()}
    Cm["skill_src"] = list(reversed(Cm["skill_src"]))
    E = copy.deepcopy(U)
    E["skill_src"] = E["skill_src"] * 3
    for i in range(40):
        E["de"]["w"].setdefault(f"irrelevant:feature_{i}", {})["round2"] = 1.0
    E["trust"]["records"] += [dict(project=f"irrelevant{i}", claim={}, features=[], agreed=bool(i % 2), how="irrelevant", scope="-") for i in range(40)]
    T6.refit(E["trust"])
    return dict(A=A, B=Bm, C=Cm, E=E)


class Redundant(L8.Lineage):
    """Control only: an extra discarded live search per project (same memory, more acquisition work)."""

    def learn_project(self, spec, seed, root=None):
        row = super().learn_project(spec, seed, root)
        p = W6.make_project6({k: v for k, v in spec.items() if k != "legacy_flip"}, seed, self.root / "redundant") if not spec.get("legacy_flip") else None
        if p is not None:
            r = PR8.Live(L8.W_SRC, L8.WALL_SRC).search(p, dict(self.mem, de=dict(self.mem["de"], skills={})), "decompose", "off")
            row["work"] += r["cost"].get("work", 0)
            row["redundant_work"] = r["cost"].get("work", 0)
        return row


def trajectory(cls, mem, stream, tag):
    lin = cls(f"D_{tag}", "FixedLearner", dict(admit=range(DEV + 1600, DEV + 1700)), L8.WS / "dev9" / f"D_{tag}", time.time() + 120, f"D|{tag}",
              mem=copy.deepcopy(mem), frozen_procedure=True)
    t = time.time()
    for i, (c, spec, s) in enumerate(stream):
        lin.learn_project(spec, s)
        if (i + 1) % 9 == 0:
            lin.cycle(len(lin.cycles))
    acq = [r["cost"] if "cost" in r else dict(work=r["work"], probe_runs=r["probe_runs"], questions=r["questions"], reads=r["reads"]) for r in lin.rows]
    return lin, acq, round(time.time() - t, 1)


def main(out):
    W.SparkCode.warm()
    res = {}
    U = load("FixedLearner_r1")
    block = C.build_block(B.block_specs(list(range(DEV, DEV + 18))), ROOT / "var/agi9_ws/dev/sens_block")
    res["block"] = [dict(stratum=p.get("stratum"), pid=p.get("pid"), error=p.get("error")) for p in block]
    live = PR8.Live(L8.W_SRC, L8.WALL_SRC)                      # one shared, digest-keyed cache: identical searches run once
    rows = {"U": C.eval_memory(U, block, live)}
    for k, m in variants(U).items():
        rows[k] = C.eval_memory(m, block, live)
    S = {k: C.summary(v) for k, v in rows.items()}
    res["summaries"] = S
    res["exposure"] = {k: [dict(pid=p[-24:], stratum=r["stratum"], verified=r["verified"], wrong=r["wrong"], trust_used=r["trust_used"], points=r["points"])
                           for p, r in v.items() if r["points"]] for k, v in rows.items() if k in ("U", "A", "B")}
    gate = {}
    gate["A_useful_vs_removed"] = dict(passed=S["U"]["verified"] > S["A"]["verified"], U=S["U"]["verified"], A=S["A"]["verified"])
    gate["B_useful_vs_corrupted"] = dict(passed=S["B"]["verified"] < S["U"]["verified"] or S["B"]["wrong"] > S["U"]["wrong"],
                                         U=[S["U"]["verified"], S["U"]["wrong"]], B=[S["B"]["verified"], S["B"]["wrong"]])
    gate["C_equivalent"] = dict(passed=S["C"]["solved"] == S["U"]["solved"] and abs(S["C"]["cost_s"] - S["U"]["cost_s"]) <= 0.01 * max(1e-9, S["U"]["cost_s"]),
                                U=S["U"]["cost_s"], C=S["C"]["cost_s"])
    ok_e, why_e = C.select(S["U"], S["E"])
    gate["E_irrelevant_not_rewarded"] = dict(passed=not ok_e, why=why_e)
    # D
    stream = B.balanced_stream(list(range(DEV + 100, DEV + 109)), 1, "sensD")
    ln, acq_n, wn = trajectory(L8.Lineage, U, stream, "normal")
    lr, acq_r, wr = trajectory(Redundant, U, stream, "redundant")
    same_mem = C.mem_digest(ln.mem) == C.mem_digest(lr.mem)
    rn, rr = C.eval_memory(ln.mem, block, live), C.eval_memory(lr.mem, block, live)
    sn, sr = C.summary(rn), C.summary(rr)
    an, ar = sum(C.det_cost(c) for c in acq_n), sum(C.det_cost(c) for c in acq_r)
    pick_normal, why1 = C.select(sr, sn, inc_acq_cost=ar, cand_acq_cost=an)
    pick_redundant, why2 = C.select(sn, sr, inc_acq_cost=an, cand_acq_cost=ar)
    gate["D_cheaper_equivalent"] = dict(passed=same_mem and pick_normal and not pick_redundant, same_memory=same_mem, acquire=[round(an, 3), round(ar, 3)],
                                        why_normal=why1, why_redundant=why2, proxies_normal=C.proxy_costs(rn, acq_n), trajectory_wall=[wn, wr])
    res["throughput"] = dict(trajectory_9_projects_wall_s=[wn, wr], mean_project_wall=round(sum(r["wall"] for r in ln.rows) / len(ln.rows), 2),
                             cycle_s=[c["t"] for c in ln.cycles], consolidation_s=round(ln.cost["consolidation_s"], 1))
    # F
    M0 = load("FixedLearner_r0")
    noM = copy.deepcopy(M0)
    noM["de"]["skills"] = {}
    fr = []
    for j in range(6):
        try:
            p = W6.make_project6(dict(paradigm="P2", engine=("sqlite", "duckdb")[j % 2], fault_p=1.0), DEV + 200 + j, ROOT / "var/agi9_ws/dev/sensF")
        except RuntimeError:
            continue
        row = {}
        for tag, m in (("with", M0), ("without", noM)):
            r = PR8.Live(L8.W_SRC, L8.WALL_SRC).search(p, m, "whole", "on")
            ok = False
            if r["outcome"] == "submitted":
                ok = W6.evaluate6(p, [P6.ir6.lower(s, st["target_lang"]) for s, st in zip(r["specs"], p["stages"])])["ok"]
            row[tag] = dict(verified=ok, work=r["cost"].get("work", 0), method=bool((r.get("method_queue") or {}).get("accepted")))
        fr.append(dict(pid=p["pid"], **row))
    comp = [x for x in fr if x["with"]["verified"] and x["without"]["verified"]]
    wsum = [sum(x["with"]["work"] for x in comp), sum(x["without"]["work"] for x in comp)]
    gained = sum(x["with"]["verified"] and not x["without"]["verified"] for x in fr) - sum(x["without"]["verified"] and not x["with"]["verified"] for x in fr)
    sens = gained != 0 or (wsum[1] > 0 and abs(wsum[0] - wsum[1]) >= 0.1 * wsum[1])
    gate["F_method_channel"] = dict(sensitive=sens, rows=fr, work_on_common_correct=wsum, completion_difference=gained,
                                    note=None if sens else "INSENSITIVE: no completion or >= 10 % work difference; method utility untested by this channel")
    res["gate"] = gate
    res["gate_passed"] = all(gate[k]["passed"] for k in gate if k[0] in "ABCDE")
    res["wall"] = round(time.time() - T0, 1)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: {x: y for x, y in v.items() if x not in ("rows", "proxies_normal")} for k, v in gate.items()}, default=str))
    print("summaries", {k: (v["verified"], v["wrong"], v["trust_used"], v["cost_s"], v["by_stratum"]) for k, v in S.items()})
    print("GATE", res["gate_passed"], "throughput", res["throughput"], "wall", res["wall"])


if __name__ == "__main__":
    main(sys.argv[1])
