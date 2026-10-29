"""Phase 9B rebuilt sensitivity gate (NOT LOCKED; development data only, agi9de/dev seeds 78000+; disjoint from the
unopened agi9de/confirm range). Evaluator calibration: nothing here is a NEXUS invention or transfer result.
Every step appends one JSON line per project to artifacts/agi9b_dev/<step>.jsonl and flushes (a timeout loses nothing;
a rerun resumes after the last written line).

  screen     select the 12-project gate set by STRUCTURE judged with a FRESH memory and F0 (never by which memory wins):
             reachable = the fresh search returns a repair candidate; multi-conflict (MC, >= 6) = after reading the
             documents >= 2 decision points / obligations are simultaneously open (conflicting or unclaimed) and >= 1 of
             them is a documented conflict; plus 6 other reachable projects (legacy disagreement x2, single conflict,
             undecided, benign, multi-fault composite)
  controls   memories U (FixedLearner_r1, Phase 8), A trust removed, B trust labels flipped, C reordered / renamed, E
             irrelevant extra memory, each under F0 on the gate set. U / A / B share one digest-keyed search cache (the
             candidate search runs once per project and is charged once; each control's investigation / verification pass
             is charged); C and E run uncached searches
  redundant  two 9-project balanced trajectories from U (sqlite / duckdb only) on the SAME stream: normal vs a controlled
             redundant extra live search per project; then both frozen memories on the gate set (uncached)
  skills     library L* = every admitted method of the Phase 7 / 8 checkpoints (canonical union). Screen seeds: search8 with
             L* vs without at the same total budget on all-fault P2 / P6 / P4 / X1 projects; every spec where L* verified
             and the base did not is REPLICATED on fresh disjoint seeds - only the replication counts
  judge      the six predeclared rules (below) -> artifacts/agi9b_dev/gate.json
RULES (fixed before running): 1 C: identical verified set, 0 wrong. 2 E: no completion gain over U, 0 wrong. 3 A: U verifies
strictly more MC projects than A. 4 B: U verifies strictly more MC projects than B, and B accepts 0 wrong. 5 redundant: the
two memories are identical, their gate-set verified sets are identical, and the selection rule prefers the normal learner
(>= 10 % lower acquisition+future cost) and never the redundant one. 6 skills: on the replication seeds the with-L* arm
verifies strictly more than the without-L* arm, with 0 wrong in both."""
import copy, json, sys, time
from pathlib import Path
from nexus.de_phase4 import world as W
from nexus.de_phase6 import pipeline6 as P6, trust6 as T6, world6 as W6
from nexus.de_phase7 import world7 as W7
from nexus.de_phase8 import lineage8 as L8, procedure8 as PR8, search8 as S8
from nexus.de_phase9 import blocks9 as B, compare9 as C
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "artifacts/agi9b_dev"
WS = ROOT / "var/agi9b_ws/dev"
DEV = 78000
LF = B.LF
MC_SPECS = [dict(paradigm="P5", engine=e, modes=m, fault_p=0.4) for e in ("sqlite", "duckdb")
            for m in (dict(watermark="conflict_approved", checkpoint="conflict_approved"), dict(watermark="conflict_approved", checkpoint="missing"),
                      dict(watermark="missing", checkpoint="conflict_approved"))]
OTHER = [("legacy_disagreement", dict(paradigm="P7", engine="duckdb", **LF)), ("legacy_disagreement", dict(paradigm="P1", engine="sqlite", **LF)),
         ("single_conflict", dict(paradigm="P7", engine="duckdb", dp_mode="conflict_approved")), ("undecided", dict(paradigm="P1", engine="duckdb", dp_mode="undecided")),
         ("benign", dict(paradigm="P2", engine="duckdb")), ("multi", dict(paradigm="X1"))]


def jl(name):
    return D / f"{name}.jsonl"


def read(name):
    p = jl(name)
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def append(name, row):
    D.mkdir(parents=True, exist_ok=True)
    with open(jl(name), "a") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
        fh.flush()


def load(n):
    m = json.loads((ROOT / f"artifacts/agi8_src/{n}.json").read_text())["memory"]
    m.setdefault("policy_w", None)
    m["M"]["batch"] = 9
    return m


def fresh_structure(p):
    st = PR8.investigate(p, PR8.Live(L8.W_SRC, L8.WALL_SRC), L8.empty_memory(), PR8.F0)
    pts = [d for d in st.dps if d.get("kind") != "absent"]
    conflicts = sum(1 for d in pts if len({c["effect_at_boundary"] for c in d.get("claims") or []}) > 1)
    unclaimed = sum(1 for d in pts if not d.get("claims"))
    return dict(reachable=bool(st.has_candidate), K=conflicts + unclaimed, conflicts=conflicts, unclaimed=unclaimed, fresh_decision=st.decision["kind"],
                fresh_reason=st.decision.get("reason"))


def screen():
    done = read("screen")
    seen = {r["seed"] for r in done}
    sel = [r for r in done if r.get("selected")]
    n_mc = sum(r["group"] == "MC" for r in sel)
    other_done = {r["stratum"] for r in sel if r["group"] == "other"}
    s = max([DEV - 1] + list(seen)) + 1
    plan = []
    for i in range(36):
        plan.append(("MC", "multi_conflict", MC_SPECS[i % len(MC_SPECS)]))
    for k in range(3):
        for st_, sp in OTHER:
            plan.append(("other", st_, sp))
    used_other = {}
    for group, stratum, spec in plan[len(done):]:
        if group == "MC" and n_mc >= 6:
            continue
        key = (stratum, json.dumps(spec, sort_keys=True))
        if group == "other" and (key in used_other or sum(1 for r in sel if r["group"] == "other") >= 6 or
                                 (stratum in other_done and stratum != "legacy_disagreement") or
                                 (stratum == "legacy_disagreement" and sum(1 for r in sel if r["stratum"] == stratum) >= 2)):
            continue
        seed = s
        s += 1
        t = time.time()
        try:
            p = W7.make_project7(spec, seed, WS / "gate")
        except RuntimeError as e:
            append("screen", dict(seed=seed, group=group, stratum=stratum, spec=spec, selected=False, why=f"build: {str(e)[:60]}"))
            continue
        f = fresh_structure(p)
        ok = f["reachable"] and (f["K"] >= 2 and f["conflicts"] >= 1 if group == "MC" else True)
        if group == "other" and stratum == "single_conflict":
            ok = ok and f["conflicts"] == 1 and f["K"] == 1
        row = dict(seed=seed, group=group, stratum=stratum, spec=spec, selected=ok, structure=f, wall=round(time.time() - t, 2))
        if ok:
            p["stratum"] = stratum
            row["project"] = p
            sel.append(row)
            if group == "MC":
                n_mc += 1
            else:
                other_done.add(stratum)
                used_other[key] = True
        append("screen", row)
        print(group, stratum, seed, ok, f, flush=True)
        if n_mc >= 6 and sum(1 for r in sel if r["group"] == "other") >= 6:
            break
    print("selected", len(sel), "MC", n_mc)


def gate_set():
    return [r for r in read("screen") if r.get("selected")]


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


def controls():
    gs = gate_set()
    done = {(r["memory"], r["seed"]) for r in read("controls")}
    U = load("FixedLearner_r1")
    mems = dict(U=U, **variants(U))
    shared = PR8.Live(L8.W_SRC, L8.WALL_SRC)
    for k in ("U", "A", "B", "C", "E"):
        live = shared if k in ("U", "A", "B") else PR8.Live(L8.W_SRC, L8.WALL_SRC)
        for r in gs:
            if (k, r["seed"]) in done:
                continue
            p = r["project"]
            row = C.eval_memory(mems[k], [p], live)[p["pid"]]
            append("controls", dict(row, memory=k, seed=r["seed"], group=r["group"], pid=p["pid"]))
        print(k, "done", flush=True)


class Redundant(L8.Lineage):
    def learn_project(self, spec, seed, root=None):
        row = super().learn_project(spec, seed, root)
        if not spec.get("legacy_flip"):
            p = W6.make_project6(spec, seed, self.root / "redundant")
            r = PR8.Live(L8.W_SRC, L8.WALL_SRC).search(p, dict(self.mem, de=dict(self.mem["de"], skills={})), "decompose", "off")
            row["work"] += r["cost"].get("work", 0)
            row["redundant_work"] = r["cost"].get("work", 0)
        return row


def redundant():
    U = load("FixedLearner_r1")
    stream = [(c, dict(sp, engine="duckdb") if sp.get("engine") == "spark" else sp, s)
              for c, sp, s in B.balanced_stream(list(range(DEV + 600, DEV + 609)), 1, "9b-redundant")]
    out = {}
    for tag, cls in (("normal", L8.Lineage), ("redundant", Redundant)):
        if any(r["tag"] == tag and r.get("final") for r in read("redundant")):
            continue
        lin = cls(f"R_{tag}", "FixedLearner", dict(admit=range(DEV + 700, DEV + 800)), WS / f"R_{tag}", time.time() + 200, f"R|{tag}", mem=copy.deepcopy(U),
                  frozen_procedure=True)
        for i, (c, spec, s) in enumerate(stream):
            row = lin.learn_project(spec, s)
            append("redundant", dict(tag=tag, i=i, seed=s, verified=row["verified"], wrong=row["wrong_first"], cost=dict(work=row["work"], probe_runs=row["probe_runs"],
                                     questions=row["questions"], reads=row["reads"]), redundant_work=row.get("redundant_work", 0), wall=row["wall"]))
            if (i + 1) % 9 == 0:
                lin.cycle(len(lin.cycles))
        rows = C.eval_memory(lin.mem, [r["project"] for r in gate_set()], PR8.Live(L8.W_SRC, L8.WALL_SRC))
        append("redundant", dict(tag=tag, final=True, mem_digest=C.mem_digest(lin.mem), summary=C.summary(rows), consolidation_s=round(lin.cost["consolidation_s"], 1)))
        print(tag, C.summary(rows)["verified"], flush=True)


def library():
    lib = {}
    for f in sorted((ROOT / "artifacts").glob("agi7_src/*.json")) + sorted((ROOT / "artifacts").glob("agi8_src/*.json")):
        for s in json.loads(f.read_text())["memory"]["de"]["skills"].values():
            lib.setdefault(s["canonical"], dict(s, uses=0))
    return {f"L{i}": s for i, s in enumerate(lib.values())}


def _search(p, mem):
    r = PR8.Live(L8.W_SRC, L8.WALL_SRC).search(p, mem, "whole", "on")
    ok = False
    if r["outcome"] == "submitted":
        ok = W6.evaluate6(p, [P6.ir6.lower(s, st["target_lang"]) for s, st in zip(r["specs"], p["stages"])])["ok"]
    return dict(verified=ok, wrong=r["outcome"] == "submitted" and not ok, work=r["cost"].get("work", 0), outcome=r["outcome"],
                method=bool((r.get("method_queue") or {}).get("accepted")))


def skills():
    L = library()
    with_m = dict(L8.empty_memory(), de=dict(w={}, skills=L))
    without = L8.empty_memory()
    specs = [dict(paradigm="P2", engine="sqlite", fault_p=1.0), dict(paradigm="P2", engine="duckdb", fault_p=1.0), dict(paradigm="P6", engine="sqlite", fault_p=1.0),
             dict(paradigm="P6", engine="duckdb", fault_p=1.0), dict(paradigm="P4", engine="duckdb", fault_p=1.0), dict(paradigm="X1", fault_p=1.0)]
    done = read("skills")
    if not done:
        append("skills", dict(library=[s["canonical"] for s in L.values()], n=len(L)))
    seen = {(r.get("phase"), r.get("seed")) for r in done}
    s = DEV + 900
    winners = []
    for rep in range(2):
        for spec in specs:
            seed = s
            s += 1
            if ("screen", seed) not in seen:
                try:
                    p = W6.make_project6(spec, seed, WS / "skills")
                except RuntimeError:
                    continue
                a, b = _search(p, with_m), _search(p, without)
                append("skills", dict(phase="screen", seed=seed, spec=spec, with_L=a, without_L=b))
                print("screen", spec, a["verified"], b["verified"], flush=True)
    winners = [r["spec"] for r in read("skills") if r.get("phase") == "screen" and r["with_L"]["verified"] and not r["without_L"]["verified"]]
    s = DEV + 950
    for spec in winners:
        for k in range(2):
            seed = s
            s += 1
            if ("replicate", seed) in seen:
                continue
            try:
                p = W6.make_project6(spec, seed, WS / "skills_rep")
            except RuntimeError:
                continue
            a, b = _search(p, with_m), _search(p, without)
            append("skills", dict(phase="replicate", seed=seed, spec=spec, with_L=a, without_L=b))
            print("replicate", spec, a["verified"], b["verified"], flush=True)


def skills_ext():
    """DISCLOSED EXTENSION after the first skill screen found no separating case: 12 more screen projects in the only regime
    where a method could enable a completion - all-fault composites (X1 P3->P2, X2 P7->P6), where base search exhausts its
    budget - under the SAME rule 6; any separating spec must replicate on fresh disjoint seeds (only the replication counts)."""
    L = library()
    with_m = dict(L8.empty_memory(), de=dict(w={}, skills=L))
    without = L8.empty_memory()
    seen = {(r.get("phase"), r.get("seed")) for r in read("skills")}
    specs = [dict(paradigm="X1", fault_p=1.0), dict(paradigm="X2", fault_p=1.0), dict(paradigm="X1", fault_p=1.0, names="heldout"),
             dict(paradigm="X2", fault_p=1.0, names="heldout")]
    s = DEV + 920
    for rep in range(3):
        for spec in specs:
            seed = s
            s += 1
            if ("screen", seed) in seen:
                continue
            try:
                p = W6.make_project6(spec, seed, WS / "skills")
            except RuntimeError:
                continue
            a, b = _search(p, with_m), _search(p, without)
            append("skills", dict(phase="screen", extension=True, seed=seed, spec=spec, with_L=a, without_L=b))
            print("screen-ext", spec, a["verified"], b["verified"], a["work"], b["work"], flush=True)
    winners = [r["spec"] for r in read("skills") if r.get("phase") == "screen" and r.get("extension") and r["with_L"]["verified"] and not r["without_L"]["verified"]]
    s = DEV + 980
    for spec in winners:
        for k in range(2):
            seed = s
            s += 1
            if ("replicate", seed) in seen:
                continue
            try:
                p = W6.make_project6(spec, seed, WS / "skills_rep")
            except RuntimeError:
                continue
            a, b = _search(p, with_m), _search(p, without)
            append("skills", dict(phase="replicate", seed=seed, spec=spec, with_L=a, without_L=b))
            print("replicate", spec, a["verified"], b["verified"], flush=True)


def judge():
    ctl = read("controls")
    by = {}
    for r in ctl:
        by.setdefault(r["memory"], {})[r["seed"]] = r
    gs = gate_set()
    mc = [r["seed"] for r in gs if r["group"] == "MC"]
    V = lambda k, seeds=None: sorted(s for s, r in by.get(k, {}).items() if r["verified"] and (seeds is None or s in seeds))  # noqa: E731
    Wr = lambda k: sum(r["wrong"] for r in by.get(k, {}).values())                                                              # noqa: E731
    g = {}
    g["1_reordered_renamed"] = dict(passed=V("C") == V("U") and Wr("C") == 0, U=V("U"), C=V("C"), wrong=Wr("C"))
    g["2_extra_irrelevant"] = dict(passed=set(V("E")) <= set(V("U")) and Wr("E") == 0, gain=sorted(set(V("E")) - set(V("U"))), wrong=Wr("E"))
    g["3_trust_removed"] = dict(passed=len(V("U", mc)) > len(V("A", mc)), U_mc=len(V("U", mc)), A_mc=len(V("A", mc)), n_mc=len(mc),
                                questions=dict(U=sum(r["questions"] for r in by["U"].values()), A=sum(r["questions"] for r in by["A"].values())))
    g["4_trust_corrupted"] = dict(passed=len(V("U", mc)) > len(V("B", mc)) and Wr("B") == 0, U_mc=len(V("U", mc)), B_mc=len(V("B", mc)), B_wrong=Wr("B"))
    red = read("redundant")
    fin = {r["tag"]: r for r in red if r.get("final")}
    if len(fin) == 2:
        acq = {t: sum(C.det_cost(r["cost"]) for r in red if r["tag"] == t and not r.get("final")) for t in fin}
        sn, sr = fin["normal"]["summary"], fin["redundant"]["summary"]
        pn = C.select(sr, sn, inc_acq_cost=acq["redundant"], cand_acq_cost=acq["normal"])
        pr = C.select(sn, sr, inc_acq_cost=acq["normal"], cand_acq_cost=acq["redundant"])
        g["5_redundant_computation"] = dict(passed=fin["normal"]["mem_digest"] == fin["redundant"]["mem_digest"] and sn["solved"] == sr["solved"] and pn[0] and not pr[0],
                                            same_memory=fin["normal"]["mem_digest"] == fin["redundant"]["mem_digest"], acquire=acq, prefer_normal=pn, prefer_redundant=pr,
                                            verified=[sn["verified"], sr["verified"]])
    else:
        g["5_redundant_computation"] = dict(passed=False, note="not complete")
    rep = [r for r in read("skills") if r.get("phase") == "replicate"]
    scr = [r for r in read("skills") if r.get("phase") == "screen"]
    g["6_skill_removal"] = dict(passed=bool(rep) and sum(r["with_L"]["verified"] for r in rep) > sum(r["without_L"]["verified"] for r in rep) and
                                not any(r["with_L"]["wrong"] or r["without_L"]["wrong"] for r in rep),
                                screen=[(r["spec"]["paradigm"], r["with_L"]["verified"], r["without_L"]["verified"], r["with_L"]["method"]) for r in scr],
                                replicate=[(r["spec"]["paradigm"], r["with_L"]["verified"], r["without_L"]["verified"]) for r in rep],
                                note=None if rep else "no screen spec where L* verified and the base did not: no separating case to replicate")
    res = dict(gate=g, passed=all(v["passed"] for v in g.values()), gate_set=[dict(seed=r["seed"], group=r["group"], stratum=r["stratum"], structure=r["structure"],
                                                                                 pid=r["project"]["pid"]) for r in gs],
               per_memory={k: dict(verified=len(V(k)), mc_verified=len(V(k, mc)), wrong=Wr(k), questions=sum(r["questions"] for r in v.values()),
                                   trust_used=sum(r["trust_used"] for r in v.values())) for k, v in by.items()})
    (D / "gate.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: {x: y for x, y in v.items() if x not in ("screen",)} for k, v in g.items()}, default=str))
    print("per memory", res["per_memory"], "PASSED", res["passed"])


if __name__ == "__main__":
    {"screen": screen, "controls": controls, "redundant": redundant, "skills": skills, "skills_ext": skills_ext, "judge": judge}[sys.argv[1]]()
