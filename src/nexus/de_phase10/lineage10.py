"""Phase 10 wake-sleep learner (NOT LOCKED). One lineage = one exogenous Repos_Train stream; checkpoints at N = 25 / 60 / 120.

WAKE (per task)   investigate with the current procedure (F0 or pi*) and memory (trust, evidence weights w = G_count, library
                  L*, ranker = G_learned once trained); hidden verification is the feedback. Updates: calibrated trust;
                  w (verified edits +, regressions -); skill sources (verified repairs; + partial stage repairs iff P* is on);
                  P* (partial / failed hypotheses, boundary witnesses x_diff, unresolved claims; support / refute counts);
                  ranker pairs along every VERIFIED path.
SLEEP (every M.batch tasks)
  abstraction     invent7 compatible clusters over the skill sources -> at most 2 new candidates -> Delta MDL (memory10) >
                  M.mdl_threshold across >= 2 tasks AND leave-one-paradigm-out validation (2 applicable + 1 retention admission
                  projects from paradigms ABSENT from the candidate's support; base vs trial with the bounded method queue;
                  no added wrong, no lost completion) -> L*
  dreaming        M.dream_ratio x batch Repos_Train tasks whose TRUTH passes the v7 invariants and the hidden evaluator
                  (contract guard) -> witness path -> ranker pairs (dreams use the generator's known specification as
                  training supervision; never an evaluation target)
  ranker          guide10.train on all pairs; accuracy on a project-grouped held-out 20 %
PI* ROUND (N1, N2)    counterfactual replay: typed procedure proposals scored on an 8-project cached pool (4 multi-conflict
                  K >= 2), unsupported counterfactuals skipped as unknown; admit7 per cycle; adopted only if not worse with 0
                  wrong on a separate 6-project confirmation pool (4 multi-conflict).
M* ROUND (N1)     clones from the N1 checkpoint run 20 wake tasks (2 sleeps) under M0, M' (one seeded single-field edit) and
                  M_rand (a seeded random M) on a COMMON stream; frozen memories are validated on 10 tasks (F0); M' is adopted
                  only if it verifies STRICTLY more validation tasks than M0 (>= 1; no win at zero solves)."""
from __future__ import annotations

import copy
import json
import random
import sys
import time
from pathlib import Path

from nexus.de_phase6 import pipeline6 as P6, skills6 as SK, trust6 as T6, world6 as W6
from nexus.de_phase7 import procedure7 as PR7, skills7 as SK7, world7 as W7
from nexus.de_phase8 import lineage8 as L8, procedure8 as PR8
from nexus.de_phase10 import guide10 as G, manifest10 as MF, memory10 as MEM, procedure10 as PR10

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import agi7_diag as WIT  # noqa: E402  (witness: development / dream supervision only)

M0 = dict(batch=10, mdl_threshold=0.0, guided_ratio=0.7, dream_ratio=0.3, skill_min_support=2, skill_max_len=3, trust_margin=1.0, trust_support=2)
SPACE = dict(mdl_threshold=[0.0, 5.0, 10.0], guided_ratio=[0.5, 0.7, 0.9], dream_ratio=[0.2, 0.3, 0.6])
W_SRC, WALL = 3000, 6.0


def empty_memory(M=None, pstar=True):
    return dict(de=dict(w={}, skills={}), trust=T6.empty(), skill_src=[], P=MEM.empty_p(), pstar=pstar, guide=None, pairs=[], M=copy.deepcopy(M or M0))


def build(spec, seed, root, require=None):
    """Projects with the held-out mutation family excluded (training) or required (eval 'require_fault' targets)."""
    sp = {k: v for k, v in spec.items() if k not in ("group", "mc", "require_fault", "tier", "seed")}
    for bump in range(16):
        p = W7.make_project7(dict(sp, _v=bump) if bump else sp, seed, root)
        has = bool(set(p["faults"]) & MF.HELD_OUT_FAULTS)
        if require is None or has == require:
            return p
    raise RuntimeError("no project with the required fault family")


def paradigm_of(pid):
    return pid.split(".")[1]


class Learner:
    def __init__(self, name, mem, prog, root, deadline, out_dir, evolve_pi=True, evolve_m=False, seeds=None):
        self.name, self.mem, self.prog, self.lib = name, mem, copy.deepcopy(prog), {}
        self.root, self.deadline, self.out = Path(root), deadline, Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.evolve_pi, self.evolve_m = evolve_pi, evolve_m
        self.seeds = seeds or MF.TRAIN
        self.live = PR10.Live(W_SRC, WALL)
        self.cursor = dict(dream=0, admit=0, pool=0, mroll=0, mval=0)
        self.n, self.cycles, self.events = 0, 0, []
        self.cost = dict(wake=0.0, abstraction=0.0, dreams=0.0, ranker=0.0, pi_round=0.0, m_round=0.0)
        self.t0 = time.time()

    def left(self):
        return self.deadline - time.time()

    def log(self, kind, row):
        with open(self.out / f"{self.name}.{kind}.jsonl", "a") as fh:
            fh.write(json.dumps(dict(row, n=self.n, t=round(time.time() - self.t0, 1)), default=list) + "\n")
            fh.flush()

    def _take(self, kind):
        seeds = list(self.seeds[kind])
        s = seeds[self.cursor[kind] % len(seeds)]
        self.cursor[kind] += 1
        return s

    # ---------------- wake
    def wake(self, spec, seed):
        t0 = time.time()
        p = build(spec, seed, self.root / "wake", require=False)
        mem = self.mem
        st = PR10.investigate(p, self.live, mem, self.prog, self.lib)
        cand = st.cand or {}
        verified, wrong = False, False
        if st.decision["kind"] == "submit":
            o = PR10.outcome(p, st)
            verified, wrong = o["verified"], o["wrong"]
        for d in st.dps:
            if d.get("claims"):
                if d["undecided"]:
                    T6.record(mem["trust"], p["pid"], d["claims"], None, "stakeholder undetermined (negative evidence)")
                elif verified and d["resolved"] is not None and d.get("effects"):
                    T6.record(mem["trust"], p["pid"], d["claims"], d["effects"][d["options"].index(d["resolved"])], "verified submission")
                elif d["via"] == "clarification" and d.get("effects"):
                    T6.record(mem["trust"], p["pid"], d["claims"], d["effects"][d["options"].index(d["resolved"])], "stakeholder answer")
                elif mem["pstar"] and d["resolved"] is None:
                    mem["P"]["claims"].append(dict(project=p["pid"], claims=[c.get("provenance") for c in d["claims"]], why="unresolved"))
            if mem["pstar"] and d.get("probe") is not None:
                mem["P"]["witnesses"].append(dict(project=p["pid"], stage=d["stage"], via=d["via"]))
        feats = set(cand.get("start_features") or [])
        path = cand.get("path") or []
        w = mem["de"]["w"]
        if verified and path:
            for k, op, prm in path:
                for f in feats:
                    w.setdefault(f, {})[op] = w.get(f, {}).get(op, 0.0) + 1.0
        for r in (cand.get("regressions") or [])[:30]:
            for f in r["pre"]:
                w.setdefault(f, {})[r["op"]] = w.get(f, {}).get(r["op"], 0.0) - 0.5
            if mem["pstar"]:
                MEM.refute(mem["P"], r["op"], r["pre"])
        inv = self.live.invs.get(p["pid"])
        partial = cand.get("partial")
        npairs = 0
        try:
            if verified and path and inv is not None:
                before = len(mem["skill_src"])
                SK.record(mem["skill_src"], p["pid"], inv, [tuple(e) for e in path], feats, True)
                if mem["pstar"]:
                    for rec in mem["skill_src"][before:]:
                        MEM.confirm(mem["P"], rec["edits"], p["pid"])
                pr = G.path_pairs(inv, [tuple(e) for e in path], random.Random(f"{self.name}|{p['pid']}"))
                mem["pairs"] += [dict(project=p["pid"], src="wake", pos=a, neg=b) for a, b in pr]
                npairs = len(pr)
            elif mem["pstar"] and partial and inv is not None and (partial["stage_fixed"] > 0 or partial["gain"] > 0):
                before = len(mem["skill_src"])
                SK.record(mem["skill_src"], p["pid"] + "#partial", inv, [tuple(e) for e in partial["path"]], feats, True)
                for rec in mem["skill_src"][before:]:
                    MEM.add_hypothesis(mem["P"], rec["edits"], p["pid"], "partial")
        except Exception as e:                                    # noqa: BLE001
            self.log("events", dict(kind="record_failed", project=p["pid"], err=str(e)[:80]))
        mem["pairs"] = mem["pairs"][-4000:]
        self.live.invs.pop(p["pid"], None)
        self.n += 1
        dt = time.time() - t0
        self.cost["wake"] += dt
        self.log("wake", dict(project=p["pid"], paradigm=p["paradigm"], decision=st.decision["kind"], reason=st.decision.get("reason"), verified=verified, wrong=wrong,
                              questions=st.cost["questions"], work=st.cost["work"], via_skill=bool(cand.get("via_skill")), method_queue=cand.get("method_queue"),
                              guide=(mem.get("guide") or {}).get("kind"), pairs=npairs, wall=round(dt, 2), cost_s=round(PR10.cost_s(st.cost), 4)))
        return verified

    # ---------------- sleep
    def sleep(self):
        self.cycles += 1
        t = time.time()
        self.abstraction()
        self.cost["abstraction"] += time.time() - t
        t = time.time()
        self.dreams()
        self.cost["dreams"] += time.time() - t
        t = time.time()
        self.train_ranker()
        self.cost["ranker"] += time.time() - t

    def abstraction(self):
        mem = self.mem
        if not mem["skill_src"] or self.left() < 30:
            return
        cands = SK7.invent7(mem["skill_src"], mem["M"]["skill_min_support"], mem["M"]["skill_max_len"])
        known = {s["canonical"] for s in mem["de"]["skills"].values()} | set(mem.get("_tried", []))
        for cand in [c for c in cands if c["canonical"] not in known][:2]:
            mem.setdefault("_tried", []).append(cand["canonical"])
            tasks = {s.split("#")[0] for s in cand["support"]}
            dm = MEM.delta_mdl(len(cand["edits"]), len(tasks), len(mem["de"]["skills"]))
            row = dict(canonical=cand["canonical"], edits=cand["edits"], novelty=cand["novelty"], support=cand["support"], from_partial=cand["from_partial"], delta_mdl=dm)
            if dm <= mem["M"]["mdl_threshold"]:
                self.log("abstraction", dict(row, admitted=False, why=f"Delta MDL {dm} <= threshold {mem['M']['mdl_threshold']}"))
                continue
            sup_par = {paradigm_of(s) for s in tasks}
            projs, retention = [], []
            for _ in range(10):
                if len(projs) == 2 and retention:
                    break
                s = self._take("admit")
                spec = MF.train_spec(s % 90, s)
                if spec["paradigm"] in sup_par:
                    continue                                  # leave-one-paradigm-out: never a support paradigm
                try:
                    p = build(spec, s, self.root / "adm", require=False)
                    ev0 = P6.Inv6(p).run(P6.Inv6(p).legacy)
                except Exception:                              # noqa: BLE001
                    continue
                pre = set(cand["pre"])
                if (not pre or len(pre & ev0["features"]) / len(pre) >= 0.5) and len(projs) < 2:
                    projs.append(p)
                elif not retention:
                    retention.append(p)
            if not projs and not retention:
                self.log("abstraction", dict(row, admitted=False, why="no leave-one-paradigm-out validation project"))
                continue
            ok, why = L8.admit8(mem, cand, projs, retention)
            lopo_ok = not why["lost"] and why["wrong"][1] <= why["wrong"][0]
            if lopo_ok:
                sid = f"L{len(mem['de']['skills'])}"
                mem["de"]["skills"][sid] = dict(cand, admission=dict(delta_mdl=dm, lopo=dict(paradigms=sorted({p['paradigm'] for p in projs + retention}),
                                                                                               wrong=why["wrong"], lost=why["lost"], gained=why["gained"], trace=why["trace"])))
            self.log("abstraction", dict(row, admitted=lopo_ok, lopo_projects=[p["pid"] for p in projs + retention], why={k: v for k, v in why.items() if k != "rows"}))

    def dreams(self):
        n = max(0, round(self.mem["M"]["dream_ratio"] * self.mem["M"]["batch"]))
        for _ in range(n):
            if self.left() < 30:
                return
            s = self._take("dream")
            spec = MF.train_spec(s % 90, s)
            try:
                p = build(spec, s, self.root / "dream", require=False)
                inv = P6.Inv6(p)
            except Exception:                                  # noqa: BLE001
                continue
            truths = json.loads((Path(p["hidden_dir"]) / "stakeholder.json").read_text())["truths"]
            guard = not P6.invariants(inv, truths) and WIT.ok_hidden(p, truths)
            if not guard:
                self.log("dreams", dict(project=p["pid"], contract_guard=False))
                continue
            wit = WIT.witness(P6.Inv6(p), p, truths)
            pairs = []
            if wit["found"] and wit["steps"]:
                path = []
                specs = list(inv.legacy)
                # reconstruct the witness edits as (stage, op, param) by re-running the greedy choice deterministically
                for stp in wit["steps"]:
                    best = None
                    for s2, prm in P6.E.candidates(stp["op"], specs[stp["stage"]], inv.dom(stp["stage"], specs)):
                        g = WIT.agree(s2, truths[stp["stage"]]) - WIT.agree(specs[stp["stage"]], truths[stp["stage"]])
                        if best is None or g > best[0]:
                            best = (g, prm, s2)
                    if best is None:
                        break
                    path.append((stp["stage"], stp["op"], best[1]))
                    specs = list(specs)
                    specs[stp["stage"]] = best[2]
                pairs = G.path_pairs(inv, path, random.Random(f"dream|{p['pid']}"))
                self.mem["pairs"] += [dict(project=p["pid"], src="dream", pos=a, neg=b) for a, b in pairs]
            self.log("dreams", dict(project=p["pid"], contract_guard=True, witness=wit["found"], depth=wit["depth"], pairs=len(pairs)))
        self.mem["pairs"] = self.mem["pairs"][-4000:]

    def train_ranker(self):
        data = self.mem["pairs"]
        if len(data) < 20:
            return
        projects = sorted({d["project"] for d in data})
        rng = random.Random(f"split|{self.name}|{self.cycles}")
        held = set(rng.sample(projects, max(1, len(projects) // 5)))
        tr = [(d["pos"], d["neg"]) for d in data if d["project"] not in held]
        te = [(d["pos"], d["neg"]) for d in data if d["project"] in held]
        w = G.train(tr, seed=self.cycles)
        self.mem["guide"] = dict(kind="learned", w=w, ratio=self.mem["M"]["guided_ratio"])
        self.log("ranker", dict(pairs=len(data), train=len(tr), heldout=len(te), heldout_pair_accuracy=G.pair_accuracy(w, te), weights=len(w),
                                dream_share=round(sum(d["src"] == "dream" for d in data) / len(data), 3)))

    # ---------------- pi* (counterfactual replay)
    def pi_round(self, idx):
        if not self.evolve_pi or self.left() < 80:
            return
        t = time.time()
        pool_specs, conf_specs = MF.pool_specs()
        pool, conf = [], []
        for specs, out in ((pool_specs, pool), (conf_specs, conf)):
            for sp in specs:
                s = self._take("pool")
                try:
                    out.append(build(sp, s, self.root / "pi", require=False))
                except RuntimeError:
                    continue
        live = PR10.Live(W_SRC, WALL)
        caches = {p["pid"]: PR10.build_entry(p, live, self.mem) for p in pool + conf}
        prog, lib = copy.deepcopy(self.prog), copy.deepcopy(self.lib)
        base = PR10.score(prog, lib, pool, caches, self.mem)
        start = copy.deepcopy(prog)
        log = []
        for cyc in range(2):
            best = None
            for et, new, block, desc in PR7.proposals(prog, lib, random.Random(f"pi|{self.name}|{idx}|{cyc}"), typed_pairs=True):
                rows = PR10.score(new, lib, pool, caches, self.mem)
                if any(r["unsupported"] for r in rows.values()):
                    continue                                   # unknown counterfactual: never a success or a failure
                ok, why = PR7.admit7(base, rows)
                if ok:
                    key = (sum(r["correct"] for r in rows.values()), -sum(r["cost"]["wall_s"] for r in rows.values()))
                    if best is None or key > best[0]:
                        best = (key, new, desc, rows, why)
            if best is None:
                break
            prog, base = best[1], best[3]
            log.append(dict(cycle=cyc, adopted=best[2], why={k: v for k, v in best[4].items() if k != "lost"}))
        adopted = False
        if prog != start:
            b0 = PR10.score(start, lib, conf, caches, self.mem)
            b1 = PR10.score(prog, lib, conf, caches, self.mem)
            mc = [p["pid"] for p in conf if p["pid"].startswith("P6.P5")]
            ok = (sum(r["wrong"] for r in b1.values()) == 0 and sum(r["correct"] for r in b1.values()) >= sum(r["correct"] for r in b0.values())
                  and all(b1[p]["correct"] >= b0[p]["correct"] for p in mc if p in b1))
            log.append(dict(confirmation=ok, before=sum(r["correct"] for r in b0.values()), after=sum(r["correct"] for r in b1.values()),
                            wrong_after=sum(r["wrong"] for r in b1.values()), multi_conflict=mc))
            if ok:
                self.prog, adopted = prog, True
        self.cost["pi_round"] += time.time() - t
        self.log("pi", dict(round=idx, adopted=adopted, program=self.prog, log=log, pool=[p["pid"] for p in pool], conf=[p["pid"] for p in conf],
                            wall=round(time.time() - t, 1)))

    # ---------------- checkpoint
    def checkpoint(self, N):
        ck = dict(name=self.name, N=N, memory=self.mem, procedure=self.prog, cost=self.cost, n=self.n, cycles=self.cycles, wall=round(time.time() - self.t0, 1))
        p = self.out / f"{self.name}.N{N}.json"
        tmp = Path(str(p) + ".tmp")
        tmp.write_text(json.dumps(ck, default=list))
        tmp.replace(p)
        self.log("checkpoints", dict(N=N, skills=sorted(s["canonical"] for s in self.mem["de"]["skills"].values()), trust=len(self.mem["trust"]["records"]),
                                     P=len(self.mem["P"]["hypotheses"]), pairs=len(self.mem["pairs"]), guide=(self.mem.get("guide") or {}).get("kind"),
                                     procedure=self.prog, M=self.mem["M"], cost={k: round(v, 1) for k, v in self.cost.items()}))
        return p


def validate(mem, prog, projects):
    live = PR10.Live(W_SRC, WALL)
    v = w = 0
    for p in projects:
        st = PR10.investigate(p, live, copy.deepcopy(mem), prog, {})
        o = PR10.outcome(p, st)
        v += o["verified"]
        w += o["wrong"]
    return v, w


def m_round(learner, root):
    """M* vs M0 vs M_rand from the current checkpoint (common stream, independent memories)."""
    t = time.time()
    rng = random.Random(f"M|{learner.name}")
    k = rng.choice(sorted(SPACE))
    alt = [v for v in SPACE[k] if v != learner.mem["M"][k]]
    Medit = dict(learner.mem["M"], **{k: rng.choice(alt)})
    Mrand = dict(learner.mem["M"], **{f: rng.choice(v) for f, v in SPACE.items()})
    stream = [learner._take("mroll") for _ in range(20)]
    val = []
    for _ in range(10):
        s = learner._take("mval")
        try:
            val.append(build(MF.train_spec(s % 90, s), s, Path(root) / "mval", require=False))
        except RuntimeError:
            continue
    res = {}
    for tag, M in (("M0", learner.mem["M"]), ("M_edit", Medit), ("M_rand", Mrand)):
        mem = copy.deepcopy(learner.mem)
        mem["M"] = copy.deepcopy(M)
        if mem.get("guide"):
            mem["guide"]["ratio"] = M["guided_ratio"]
        c = Learner(f"{learner.name}.mround.{tag}", mem, learner.prog, Path(root) / tag, learner.deadline, learner.out, evolve_pi=False)
        c.cursor = dict(learner.cursor)
        for i, s in enumerate(stream):
            if c.left() < 40:
                break
            try:
                c.wake(MF.train_spec(s % 90, s), s)
            except RuntimeError:
                continue
            if (i + 1) % 10 == 0:
                c.sleep()
        v, w = validate(c.mem, PR10.F0, val)
        res[tag] = dict(M=M, verified=v, wrong=w, tasks=c.n, cycles=c.cycles, skills=len(c.mem["de"]["skills"]))
    complete = all(r["tasks"] == len(stream) for r in res.values())       # a truncated clone makes the comparison uninformative
    adopt = complete and res["M_edit"]["verified"] > res["M0"]["verified"] and res["M_edit"]["verified"] >= 1 and res["M_edit"]["wrong"] <= res["M0"]["wrong"]
    if adopt:
        learner.mem["M"] = copy.deepcopy(Medit)
        if learner.mem.get("guide"):
            learner.mem["guide"]["ratio"] = Medit["guided_ratio"]
    learner.cost["m_round"] += time.time() - t
    learner.log("m", dict(edit=[k, Medit[k]], results=res, adopted=adopt, complete=complete, wall=round(time.time() - t, 1)))
    return adopt
