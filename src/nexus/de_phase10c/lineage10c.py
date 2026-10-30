"""Phase 10C compositional wake-sleep learner (NOT LOCKED).

HELD FIXED (owner rule 2): calibrated trust (the frozen Phase 10B rep0 final trust state, never updated here), the F0
procedure, M0 learner hyperparameters, the bridge machinery (search10c) - no pi* or M* rounds. The whole budget buys experience.
WAKE   investigate (search10c with the learner's current Arm-4 configuration: library L* + ranker G_L*); hidden verification is
       the feedback. On a verified repair: (a) STAGE-LOCAL SKILL SOURCES - the path is replayed; each maximal same-stage segment
       is recorded in role form with the RESIDUAL SYMPTOMS of its stage when the segment started (its modular precondition);
       (b) valley crossings (flat a1, gaining a1 o a2) are remembered as bridges; (c) STEP RECORDS for the rankers: per step the
       residual-symptom context, the taken primitive's tokens, up to 8 sibling primitives' tokens, and its role-form edit.
       Unverified searches with a best partial that clears a stage give '#partial' segments (sources only).
SLEEP  (every M0.batch tasks and at checkpoints)
  abstraction  invent7 clusters over the segments -> multi-edit candidates (>= 2 edits, >= 2 source projects), bridge
               candidates first, one per sleep; Delta MDL > M0.mdl_threshold; MODULAR ADMISSION: on <= 2 leave-one-paradigm-out
               training projects where the macro binds at the root with its precondition matched, it must make SUB-PROBLEM
               PROGRESS on >= 1 (fewer failing stage tests / checks, no passing check lost), and a base-vs-trial search on them
               must lose no completion and add no wrong submission
  dreams       contract-guarded witness paths on training-family projects (truth passes the v7 invariants + hidden evaluator)
               -> step records + '#dream' segments
  rankers      G_L0  : pairwise logistic ranker on primitive step pairs (for the Learned + L0 arm)
               G_L*  : the same records REWRITTEN over L0 U L*: where a library macro matches consecutive same-stage steps
                       (role-form) with its precondition met, the step becomes the macro token (negatives: the siblings and the
                       macro's own first primitive) (for the Learned + L0 U L* arm and for the learner's own wake search)
All randomness: rng10c.rng(rep, step, task) - never the learner name. Costs (wake, abstraction, dreams, rankers) are charged."""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from nexus.de_phase6 import engines6 as E, pipeline6 as P6, skills6 as SK
from nexus.de_phase7 import skills7 as SK7
from nexus.de_phase8 import procedure8 as PR8
from nexus.de_phase10 import guide10 as G, lineage10 as LN, memory10 as MEM, procedure10 as PR10
from nexus.de_phase10c import manifest10c as MC, search10c as S10
from nexus.de_phase10c.rng10c import rng, seed_of

import agi7_diag as WIT  # noqa: E402  (lineage10 put scripts/ on sys.path; witness: dream supervision only)

M0 = dict(LN.M0)
SPACE = dict(mdl_threshold=[0.0, 5.0, 10.0], dream_ratio=[0.2, 0.3, 0.6])   # Stage 4 M* edit space (guided_ratio is held at 4/7: bridge machinery)
REC_CAP, N_NEG = 1500, 8
WORK, WALL, CANDS_PER_SLEEP = 1500, 4.0, 2               # revised Phase 10C budget: identical in training, admission and every arm


def build(spec, seed, root):
    return LN.build(spec, seed, root, require=None)


def paradigm_of(pid):
    return pid.split(".")[1]


def memory(trust):
    m = LN.empty_memory(M=M0, pstar=False)
    m["trust"] = copy.deepcopy(trust)
    m["guide"] = dict(kind="fixed", v10c=True, bridge=True)
    m.update(steps=[], bridges=[], guides={})
    return m


def arm_memory(trust, skills=None, guide_w=None):
    """An evaluation arm: fixed trust, F0, M0, search10c; library and guide as given (empty = L0 / G_fixed)."""
    m = memory(trust)
    m["de"]["skills"] = copy.deepcopy(skills or {})
    m["guide"] = dict(kind="learned", w=guide_w, v10c=True, bridge=True, ratio=S10.RATIO) if guide_w else dict(kind="fixed", v10c=True, bridge=True)
    m.pop("steps"); m.pop("guides"); m.pop("bridges")
    return m


class Live(PR10.Live):
    """procedure10.Live whose search result also carries the solution's macro steps and the search events."""

    def search(self, project, mem, mode, skills):
        key = (project["pid"], PR8.search_digest(mem), mode, skills, self.work_budget, "10c")
        if key in self.cache:
            r = copy.deepcopy(self.cache[key])
            r["shared"] = True
            return r
        t0 = time.time()
        try:
            inv = P6.Inv6(project)
        except Exception as e:                                  # noqa: BLE001
            out = dict(outcome="unsupported", has_candidate=False, path=None, specs=None, dps=[], cost=dict(work=0, wall_s=0.0), note=str(e)[:80])
            self.cache[key] = out
            return copy.deepcopy(out)
        r = PR8.S8.search(inv, mem, self.work_budget, self.wall_cap, mode=mode, use_skills=skills == "on", skills_mod=self.proposer)
        self.invs[project["pid"]] = inv
        out = dict(outcome=r["outcome"], has_candidate=r["outcome"] in ("submitted", "ambiguous"), path=r["path"], specs=r["specs"], dps=r["dps"],
                   cost=dict(work=r["work"], sqlite_runs=inv.runs["sqlite"], duckdb_runs=inv.runs["duckdb"], spark_runs=inv.runs["spark"], wall_s=round(time.time() - t0, 3)),
                   regressions=r.get("regressions", []), start_features=r.get("start_features", []), via_skill=r.get("via_skill", False), skill_trace=[],
                   method_queue=None, solution_kinds=r.get("solution_kinds", []), partial=r.get("best_partial") if r["outcome"] == "none" else None,
                   macro_steps=r.get("macro_steps", []), events=r.get("events", {}))
        self.cache[key] = out
        return copy.deepcopy(out)


def replay_evs(inv, path):
    specs = list(inv.legacy)
    evs = [inv.run(specs, True)]
    sp = [specs]
    for k, op, prm in path:
        specs = P6.replay(inv, [(k, op, prm)], specs)
        evs.append(inv.run(specs, True))
        sp.append(specs)
    return evs, sp


def segments(inv, path, evs, sp):
    """Maximal same-stage runs: (stage, start index, role-form edits, residual symptoms at the start)."""
    n = len(inv.stages)
    out, i = [], 0
    while i < len(path):
        k = path[i][0]
        j = i
        while j < len(path) and path[j][0] == k:
            j += 1
        edits = [SK.abstract_edit(path[t][1], path[t][2], inv.dom(k, sp[t]), True) for t in range(i, j)]
        out.append((k, i, edits, sorted(S10.symptoms(evs[i], k, n))))
        i = j
    return out


def step_records(inv, path, evs, sp, r):
    n = len(inv.stages)
    recs = []
    for t, (k, op, prm) in enumerate(path):
        specs, ev = sp[t], evs[t]
        sib, pos = [], None
        for o in E.OPS:
            for kk in range(n):
                dom = inv.dom(kk, specs)
                for _, p2 in E.candidates(o, specs[kk], dom):
                    if (kk, o, p2) == (k, op, prm):
                        pos = S10.tokens(f"op:{o}", S10.ctx(ev, kk, n), S10.prim_roles(o, p2, dom))
                    else:
                        sib.append((o, kk, p2, dom))
        if pos is None:
            break
        negs = [S10.tokens(f"op:{o}", S10.ctx(ev, kk, n), S10.prim_roles(o, p2, dom)) for o, kk, p2, dom in r.sample(sib, min(N_NEG, len(sib)))]
        recs.append(dict(stage=k, ctx=S10.ctx(ev, k, n), sym=sorted(S10.symptoms(ev, k, n)), pos=pos, negs=negs,
                         abs=json.loads(json.dumps(SK.abstract_edit(op, prm, inv.dom(k, specs), True), default=list))))
    return recs


def rewrite(steps_by_project, skills):
    """Ranker pairs over L0 U L*: library macros replace matching consecutive same-stage steps (role-form match + precondition)."""
    macs = [(S10.mac_id(sk), [SK._tup(e) for e in sk["edits"]], sk) for _, sk in sorted(skills.items()) if len(sk["edits"]) >= 2]
    pairs, n_mac = [], 0
    for pid, recs in steps_by_project:
        i = 0
        while i < len(recs):
            hit = None
            for mid, edits, sk in macs:
                L = len(edits)
                seg = recs[i:i + L]
                if len(seg) == L and all(s["stage"] == recs[i]["stage"] for s in seg) and S10.pre_ok(sk, set(recs[i]["sym"])) and \
                        all(SK._matches(e, SK._tup(s["abs"])) for e, s in zip(edits, seg)):
                    hit = (mid, L)
                    break
            if hit:
                pos = S10.tokens(hit[0], recs[i]["ctx"])
                pairs += [(pid, pos, ng) for ng in recs[i]["negs"] + [recs[i]["pos"]]]
                n_mac += 1
                i += hit[1]
            else:
                pairs += [(pid, recs[i]["pos"], ng) for ng in recs[i]["negs"]]
                i += 1
    return pairs, n_mac


class Learner:
    def __init__(self, rep, name, trust, root, deadline, out_dir, seeds, stream=None, M=None):
        self.rep, self.name = int(rep), name                  # the name only names files; it never reaches a seed
        self.mem = memory(trust)
        self.mem["M"] = copy.deepcopy(M or M0)
        self.M = self.mem["M"]
        self.prog = copy.deepcopy(PR10.F0)
        self.root, self.deadline, self.out = Path(root), deadline, Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.seeds = seeds
        self.stream = stream or (lambda i: MC.train_spec(self.rep, i))
        self.live = Live(WORK, WALL)
        self.cursor = dict(dream=0, admit=0)
        self.n, self.cycles = 0, 0
        self.cost = dict(wake=0.0, abstraction=0.0, dreams=0.0, ranker=0.0)
        self.t0 = time.time()

    def left(self):
        return self.deadline - time.time()

    def log(self, kind, row):
        with open(self.out / f"{self.name}.{kind}.jsonl", "a") as fh:
            fh.write(json.dumps(dict(row, n=self.n, t=round(time.time() - self.t0, 1)), default=list) + "\n")
            fh.flush()

    def _take(self, kind):
        i = self.cursor[kind]
        self.cursor[kind] += 1
        seeds = list(self.seeds[kind])
        return i, seeds[i % len(seeds)]

    def _sources(self, pid, inv, path, tag=""):
        evs, sp = replay_evs(inv, path)
        for k, i, edits, sym in segments(inv, path, evs, sp):
            self.mem["skill_src"].append(dict(project=pid + tag, stage_features=sym, edits=edits))
        return evs, sp

    def valleys(self, pid, inv, path, evs, sp):
        n = len(inv.stages)
        for i in range(len(path) - 1):
            if path[i][0] == path[i + 1][0] and evs[i + 1]["score"] - evs[i]["score"] <= 1e-9 and evs[i + 2]["score"] - evs[i]["score"] > 1e-9:
                k = path[i][0]
                edits = [SK.abstract_edit(path[t][1], path[t][2], inv.dom(k, sp[t]), True) for t in (i, i + 1)]
                self.mem["skill_src"].append(dict(project=pid + "#bridge", stage_features=sorted(S10.symptoms(evs[i], k, n)), edits=edits))
                sig = json.dumps([e[0] for e in edits])
                if sig not in self.mem["bridges"]:
                    self.mem["bridges"].append(sig)
                self.log("valleys", dict(project=pid, i=i, ops=[e[0] for e in edits]))

    # ---------------- wake
    def wake(self, i, seed):
        t0 = time.time()
        spec = self.stream(i)
        p = build(spec, seed, self.root / "wake")
        st = PR10.investigate(p, self.live, self.mem, self.prog, {})
        cand = st.cand or {}
        verified = wrong = False
        if st.decision["kind"] == "submit":
            o = PR10.outcome(p, st)
            verified, wrong = o["verified"], o["wrong"]
        path = [tuple(e) for e in (cand.get("path") or [])]
        inv = self.live.invs.get(p["pid"])
        nrec = 0
        try:
            if verified and path and inv is not None:
                evs, sp = self._sources(p["pid"], inv, path)
                self.valleys(p["pid"], inv, path, evs, sp)
                recs = step_records(inv, path, evs, sp, rng(self.rep, 1, seed))
                self.mem["steps"].append([p["pid"], recs])
                nrec = len(recs)
            elif (cand.get("partial") or {}).get("stage_fixed", 0) > 0 and inv is not None:
                self._sources(p["pid"], inv, [tuple(e) for e in cand["partial"]["path"]], "#partial")
        except Exception as e:                                    # noqa: BLE001
            self.log("events", dict(kind="record_failed", project=p["pid"], err=str(e)[:80]))
        self._trim()
        self.live.invs.pop(p["pid"], None)
        self.n += 1
        dt = time.time() - t0
        self.cost["wake"] += dt
        self.log("wake", dict(i=i, seed=seed, project=p["pid"], paradigm=p["paradigm"], family=spec["paradigm"], decision=st.decision["kind"], reason=st.decision.get("reason"),
                              verified=verified, wrong=wrong, work=st.cost["work"], via_skill=bool(cand.get("via_skill")), macro_steps=cand.get("macro_steps"),
                              guide=self.mem["guide"]["kind"], library=len(self.mem["de"]["skills"]), records=nrec, wall=round(dt, 2)))
        return verified

    def _trim(self):
        while sum(len(r) for _, r in self.mem["steps"]) > REC_CAP:
            self.mem["steps"].pop(0)
        self.mem["skill_src"] = self.mem["skill_src"][-800:]

    # ---------------- sleep
    def sleep(self):
        self.cycles += 1
        for part, fn in (("abstraction", self.abstraction), ("dreams", self.dreams), ("ranker", self.train_rankers)):
            t = time.time()
            fn()
            self.cost[part] += time.time() - t

    def abstraction(self):
        mem = self.mem
        if not mem["skill_src"] or self.left() < 30:
            return
        cands = [c for c in SK7.invent7(mem["skill_src"], self.M["skill_min_support"], self.M["skill_max_len"]) if len(c["edits"]) >= 2]
        known = {s["canonical"] for s in mem["de"]["skills"].values()} | set(mem.get("_tried", []))
        bridges = set(mem["bridges"])
        fresh = [c for c in cands if c["canonical"] not in known]
        fresh.sort(key=lambda c: json.dumps([e[0] for e in c["edits"]]) not in bridges)
        for cand in fresh[:CANDS_PER_SLEEP]:
            mem.setdefault("_tried", []).append(cand["canonical"])
            tasks = {s.split("#")[0] for s in cand["support"]}
            dm = MEM.delta_mdl(len(cand["edits"]), len(tasks), len(mem["de"]["skills"]))
            row = dict(canonical=cand["canonical"], edits=cand["edits"], pre=cand["pre"], support=cand["support"], from_partial=cand["from_partial"], delta_mdl=dm,
                       valley_crossing=json.dumps([e[0] for e in cand["edits"]]) in bridges)
            if dm <= self.M["mdl_threshold"]:
                self.log("abstraction", dict(row, admitted=False, why="Delta MDL"))
                continue
            sup_par = {paradigm_of(s) for s in tasks}
            vals, progress = [], []
            for _ in range(8):
                if len(vals) == 2 or self.left() < 30:
                    break
                i, s = self._take("admit")
                spec = self.stream(i)
                if spec["paradigm"] in sup_par:
                    continue                                  # leave-one-paradigm-out
                try:
                    p = build(spec, s, self.root / "adm")
                    inv = P6.Inv6(p)
                    ev0 = inv.run(inv.legacy, True)
                except Exception:                              # noqa: BLE001
                    continue
                node = dict(specs=list(inv.legacy), ev=ev0)
                bound = S10.macro_cands(inv, dict(de=dict(skills={"c": cand})), node)
                if not bound:
                    continue
                prog = False
                for k, _, s2, edits, _ in bound:
                    specs = list(inv.legacy)
                    specs[k] = s2
                    ev = inv.run(specs, True)
                    lost = set(ev0["passed"]) - set(ev["passed"])
                    f0 = len(ev0["failed"]) + sum(map(len, ev0["stage_fail"]))
                    f1 = len(ev["failed"]) + sum(map(len, ev["stage_fail"]))
                    prog = prog or (not lost and not ev.get("error") and f1 < f0)
                vals.append(p)
                progress.append(prog)
            if not any(progress):
                self.log("abstraction", dict(row, admitted=False, why="no modular sub-problem progress on a leave-one-paradigm-out project", validation=len(vals)))
                continue
            rows = {}
            trial = copy.deepcopy(mem)
            trial["de"]["skills"]["candidate"] = dict(cand)
            for p in vals:
                out = {}
                for tag, m in (("base", mem), ("trial", trial)):
                    st = PR10.investigate(p, Live(WORK, WALL), copy.deepcopy(m), self.prog, {})
                    o = PR10.outcome(p, st)
                    out[tag] = (o["verified"], o["wrong"])
                rows[p["pid"]] = out
            lost = [k for k, v in rows.items() if v["base"][0] and not v["trial"][0]]
            wrong = [sum(v[t][1] for v in rows.values()) for t in ("base", "trial")]
            ok = not lost and wrong[1] <= wrong[0]
            if ok:
                sid = f"L{len(mem['de']['skills'])}"
                mem["de"]["skills"][sid] = dict(cand, valley_crossing=row["valley_crossing"], admission=dict(delta_mdl=dm, progress=progress, rows=rows))
            self.log("abstraction", dict(row, admitted=ok, progress=progress, rows=rows, why="admitted" if ok else "loses a completion or adds a wrong submission"))

    def dreams(self):
        n = max(0, round(self.M["dream_ratio"] * self.M["batch"]))
        for _ in range(n):
            if self.left() < 30:
                return
            i, s = self._take("dream")
            try:
                p = build(self.stream(i), s, self.root / "dream")
                inv = P6.Inv6(p)
            except Exception:                                  # noqa: BLE001
                continue
            truths = json.loads((Path(p["hidden_dir"]) / "stakeholder.json").read_text())["truths"]
            if P6.invariants(inv, truths) or not WIT.ok_hidden(p, truths):
                self.log("dreams", dict(project=p["pid"], contract_guard=False))
                continue
            wit = WIT.witness(P6.Inv6(p), p, truths)
            path, specs = [], list(inv.legacy)
            for stp in wit["steps"] if wit["found"] else []:
                best = None
                for s2, prm in E.candidates(stp["op"], specs[stp["stage"]], inv.dom(stp["stage"], specs)):
                    g = WIT.agree(s2, truths[stp["stage"]]) - WIT.agree(specs[stp["stage"]], truths[stp["stage"]])
                    if best is None or g > best[0]:
                        best = (g, prm, s2)
                if best is None:
                    break
                path.append((stp["stage"], stp["op"], best[1]))
                specs = list(specs)
                specs[stp["stage"]] = best[2]
            nrec = 0
            if path:
                try:
                    evs, sp = self._sources(p["pid"], inv, path, "#dream")
                    recs = step_records(inv, path, evs, sp, rng(self.rep, 2, s))
                    self.mem["steps"].append([p["pid"] + "#dream", recs])
                    nrec = len(recs)
                except Exception as e:                        # noqa: BLE001
                    self.log("events", dict(kind="dream_record_failed", project=p["pid"], err=str(e)[:80]))
            self.log("dreams", dict(project=p["pid"], family=self.stream(i)["paradigm"], contract_guard=True, witness=wit["found"], depth=wit["depth"], records=nrec))
        self._trim()

    def train_rankers(self):
        steps = [(pid, recs) for pid, recs in self.mem["steps"]]
        prim = [(pid, a, b) for pid, recs in steps for r in recs for a, b in [(r["pos"], ng) for ng in r["negs"]]]
        if len(prim) < 20:
            return
        projects = sorted({pid.split("#")[0] for pid, _ in steps})
        held = set(rng(self.rep, self.cycles, 3).sample(projects, max(1, len(projects) // 5)))
        info = {}
        for tag, pairs, nmac in (("L0", prim, 0),) + ((("Lstar",) + rewrite(steps, self.mem["de"]["skills"])),):
            tr = [(a, b) for pid, a, b in pairs if pid.split("#")[0] not in held]
            te = [(a, b) for pid, a, b in pairs if pid.split("#")[0] in held]
            w = G.train(tr, seed=seed_of(self.rep, self.cycles, 4))
            self.mem["guides"][tag] = w
            info[tag] = dict(pairs=len(pairs), train=len(tr), heldout=len(te), heldout_pair_accuracy=G.pair_accuracy(w, te), weights=len(w), macro_steps=nmac)
        self.mem["guide"] = dict(kind="learned", w=self.mem["guides"]["Lstar"], v10c=True, bridge=True, ratio=S10.RATIO)
        self.log("ranker", dict(info, cycle=self.cycles, held_projects=sorted(held)))

    # ---------------- checkpoint
    def checkpoint(self, N):
        ck = dict(name=self.name, rep=self.rep, N=N, memory=self.mem, cost=self.cost, n=self.n, cycles=self.cycles, cursor=self.cursor,
                  wall=round(time.time() - self.t0, 1))
        p = self.out / f"{self.name}.N{N}.json"
        tmp = Path(str(p) + ".tmp")
        tmp.write_text(json.dumps(ck, default=list))
        tmp.replace(p)
        self.log("checkpoints", dict(N=N, skills=sorted(s["canonical"] for s in self.mem["de"]["skills"].values()), steps=sum(len(r) for _, r in self.mem["steps"]),
                                     guides=sorted(self.mem["guides"]), cost={k: round(v, 1) for k, v in self.cost.items()}))
        return p
