"""Phase 10E wake-sleep learner (NOT LOCKED): a verbatim copy of de_phase10d.lineage10d bound to de_phase10e (dag10e operators,
roles and acceptance rules; search10e; manifest10e families, so replay reaches training only as S_replay). ONE behavioural change
(Stage 1 development rehearsal, before any Phase 10E training): mechanism-matched admission draws up to ADMIT_DRAWS = 30
admission projects (Phase 10D: 10) to find <= 2 where a candidate binds, and a candidate rejected ONLY because it bound nowhere is
retried at later sleeps (at most NOBIND_RETRIES = 3 attempts). A macro for a mechanism that is 1 of 18 training families
(S_replay) otherwise finds no binding project in ~56 % of attempts and is never retried. Phase 10D docstring:
Phase 10D compositional wake-sleep learner on multi-table DAGs: de_phase10c.lineage10c's design on dag10d.

HELD FIXED (all arms, training included): investigation procedure (search -> visible checks + node contracts -> declared-engine
re-run -> submit; Phase 10D projects have documented requirements, so no trust decision arises), M0, search10d bridge machinery.
WAKE   search10d with the learner's current Arm-4 configuration (L* + G_L*); hidden verification (declared engine, 2 batches) is the
       feedback. Verified repair -> stage-local SEGMENTS (role form + the node's residual symptoms when the segment started),
       valley crossings (flat a1, gaining a1 o a2) as bridges, STEP RECORDS (context, taken primitive tokens, 8 sampled siblings,
       role-form edit). A best partial that clears a node contract -> '#partial' segments.
SLEEP  abstraction: invent7 multi-edit candidates (>= 2 source projects), bridges first, <= 2 per sleep, Delta MDL > threshold,
         MECHANISM-MATCHED MODULAR ADMISSION (the Phase 10C fix): validation = up to 2 admission-stream training projects (never a
         support project, never a held-out composition) where the macro BINDS at the root with its precondition met; it must make
         modular progress (fewer failing node contracts / checks, no passing check lost) on >= 1, and a base-vs-trial search on
         them must lose no completion and add no wrong submission
       dreams: training-family projects, a greedy witness path toward the generator's truth (contract-guarded: the truth passes
         every contract and the hidden batches) -> step records + '#dream' segments (dreams use the generator's specification as
         supervision; never an evaluation target)
       rankers: G_L0 on primitive step pairs; G_L* on the same records rewritten over L0 U L*
All randomness: rng10c.rng(rep, step, task)."""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from nexus.de_phase7 import skills7 as SK7
from nexus.de_phase6 import skills6 as SK
from nexus.de_phase10 import guide10 as G, lineage10 as LN, memory10 as MEM
from nexus.de_phase10c import search10c as S10
from nexus.de_phase10c.lineage10c import rewrite
from nexus.de_phase10c.rng10c import rng, seed_of
from nexus.de_phase10d import world10d as W
from nexus.de_phase10e import dag10e as D, manifest10e as MD, search10e as SD

M0 = dict(LN.M0)
WORK, WALL, CANDS_PER_SLEEP, REC_CAP, N_NEG = 600, 4.0, 2, 1500, 8
ADMIT_DRAWS, NOBIND_RETRIES = 30, 3          # Phase 10E admission amendment (every arm): Phase 10D drew 10 and never retried


def memory():
    return dict(de=dict(w={}, skills={}), skill_src=[], steps=[], bridges=[], guides={}, guide=dict(kind="fixed"), M=copy.deepcopy(M0))


def arm_memory(skills=None, guide_w=None):
    return dict(de=dict(w={}, skills=copy.deepcopy(skills or {})), guide=dict(kind="learned", w=guide_w, ratio=SD.RATIO) if guide_w else dict(kind="fixed"))


def build(spec, seed, root):
    return W.make_project10d(spec, seed, root)


def investigate(p, mem, mode="whole"):
    inv = D.Inv10d(p)
    r = SD.search(inv, mem, WORK, WALL, mode=mode)
    verified = wrong = False
    if r["outcome"] == "submitted":
        h = D.verify_hidden(p, r["specs"])
        verified, wrong = h["ok"], not h["ok"]
    return inv, r, verified, wrong


def replay_evs(inv, path):
    specs = [copy.deepcopy(s) for s in inv.legacy]
    evs, sp = [inv.run(specs, True)], [specs]
    for e in path:
        specs = D.replay(inv, [tuple(e)], specs)
        evs.append(inv.run(specs, True))
        sp.append(specs)
    return evs, sp


def segments(inv, path, evs, sp):
    out, i = [], 0
    while i < len(path):
        k = path[i][0]
        j = i
        while j < len(path) and path[j][0] == k:
            j += 1
        edits = [D.abstract_edit(path[t][1], path[t][2], inv.dom(k, sp[t])) for t in range(i, j)]
        out.append((k, i, edits, sorted(S10.symptoms(evs[i], k, 3))))
        i = j
    return out


def step_records(inv, path, evs, sp, r):
    recs = []
    for t, (k, op, prm) in enumerate(path):
        specs, ev = sp[t], evs[t]
        sib, pos = [], None
        for o in D.OPS:
            kk = D.OP_NODE[o]
            dom = inv.dom(kk, specs)
            for _, p2 in D.candidates(o, specs[kk], dom):
                if (kk, o, p2) == (k, op, prm):
                    pos = S10.tokens(f"op:{o}", S10.ctx(ev, kk, 3), SD.prim_roles(o, p2, dom))
                else:
                    sib.append((o, kk, p2))
        if pos is None:
            break
        negs = []
        for o, kk, p2 in r.sample(sib, min(N_NEG, len(sib))):
            negs.append(S10.tokens(f"op:{o}", S10.ctx(ev, kk, 3), SD.prim_roles(o, p2, inv.dom(kk, specs))))
        recs.append(dict(stage=k, ctx=S10.ctx(ev, k, 3), sym=sorted(S10.symptoms(ev, k, 3)), pos=pos, negs=negs,
                         abs=json.loads(json.dumps(D.abstract_edit(op, prm, inv.dom(k, specs)), default=list))))
    return recs


def flat(x, pre=""):
    if isinstance(x, dict):
        return set().union(*[flat(v, f"{pre}/{k}") for k, v in x.items()]) if x else {pre + "={}"}
    if isinstance(x, list):
        return set().union(*[flat(v, f"{pre}[{i}]") for i, v in enumerate(x)]) if x else {pre + "=[]"}
    return {f"{pre}={json.dumps(x)}"}


def dist(a, b):
    return len(flat(a) ^ flat(b))


def witness(inv, truth, max_depth=5):
    """Greedy truth-guided path: at each step the candidate edit (any node) that most reduces the structural distance to the truth."""
    specs = [copy.deepcopy(s) for s in inv.legacy]
    tr = [truth[n] for n in D.NODES]
    path = []
    for _ in range(max_depth):
        cur = sum(dist(specs[k], tr[k]) for k in range(3))
        if cur == 0:
            return path, True
        best = None
        for o in D.OPS:
            k = D.OP_NODE[o]
            base = dist(specs[k], tr[k])
            for s2, prm in D.candidates(o, specs[k], inv.dom(k, specs)):
                g = base - dist(s2, tr[k])
                if g > 0 and (best is None or g > best[0]):
                    best = (g, k, o, prm, s2)
        if best is None:
            return path, False
        _, k, o, prm, s2 = best
        specs = list(specs)
        specs[k] = s2
        path.append((k, o, prm))
    return path, sum(dist(specs[k], tr[k]) for k in range(3)) == 0


class Learner:
    def __init__(self, rep, name, root, deadline, out_dir, seeds, stream=None, M=None):
        self.rep, self.name = int(rep), name                     # the name only names files; it never reaches a seed
        self.mem = memory()
        self.mem["M"] = copy.deepcopy(M or M0)
        self.M = self.mem["M"]
        self.root, self.deadline, self.out = Path(root), deadline, Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.seeds = seeds
        self.stream = stream or (lambda i: MD.train_spec(self.rep, i))
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
        for i in range(len(path) - 1):
            if path[i][0] == path[i + 1][0] and evs[i + 1]["score"] - evs[i]["score"] <= 1e-9 and evs[i + 2]["score"] - evs[i]["score"] > 1e-9:
                k = path[i][0]
                edits = [D.abstract_edit(path[t][1], path[t][2], inv.dom(k, sp[t])) for t in (i, i + 1)]
                self.mem["skill_src"].append(dict(project=pid + "#bridge", stage_features=sorted(S10.symptoms(evs[i], k, 3)), edits=edits))
                sg = json.dumps([e[0] for e in edits])
                if sg not in self.mem["bridges"]:
                    self.mem["bridges"].append(sg)
                self.log("valleys", dict(project=pid, i=i, ops=[e[0] for e in edits]))

    def wake(self, i, seed):
        t0 = time.time()
        spec = self.stream(i)
        p = build(spec, seed, self.root / "wake")
        inv, r, verified, wrong = investigate(p, self.mem)
        path = [tuple(e) for e in (r.get("path") or [])]
        nrec = 0
        try:
            if verified and path:
                evs, sp = self._sources(p["pid"], inv, path)
                self.valleys(p["pid"], inv, path, evs, sp)
                recs = step_records(inv, path, evs, sp, rng(self.rep, 1, seed))
                self.mem["steps"].append([p["pid"], recs])
                nrec = len(recs)
            elif (r.get("best_partial") or {}).get("stage_fixed", 0) > 0:
                self._sources(p["pid"], inv, [tuple(e) for e in r["best_partial"]["path"]], "#partial")
        except Exception as e:                                      # noqa: BLE001
            self.log("events", dict(kind="record_failed", project=p["pid"], err=f"{type(e).__name__}: {str(e)[:80]}"))
        self._trim()
        self.n += 1
        dt = time.time() - t0
        self.cost["wake"] += dt
        self.log("wake", dict(i=i, seed=seed, project=p["pid"], family=spec["family"], faults=spec["faults"], engine=spec["engine"], legacy=spec["legacy"],
                              outcome=r["outcome"], verified=verified, wrong=wrong, work=r["work"], path=[e[1] for e in path], macro_steps=r.get("macro_steps"),
                              guide=self.mem["guide"]["kind"], library=len(self.mem["de"]["skills"]), records=nrec, n_cols=p["n_cols"], wall=round(dt, 2)))
        return verified

    def _trim(self):
        while sum(len(r) for _, r in self.mem["steps"]) > REC_CAP:
            self.mem["steps"].pop(0)
        self.mem["skill_src"] = self.mem["skill_src"][-800:]

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
            mem.setdefault("_nobind", {})
            tasks = {s.split("#")[0] for s in cand["support"]}
            dm = MEM.delta_mdl(len(cand["edits"]), len(tasks), len(mem["de"]["skills"]))
            row = dict(canonical=cand["canonical"], ops=[e[0] for e in cand["edits"]], pre=cand["pre"], support=cand["support"], delta_mdl=dm,
                       valley_crossing=json.dumps([e[0] for e in cand["edits"]]) in bridges)
            if dm <= self.M["mdl_threshold"]:
                self.log("abstraction", dict(row, admitted=False, why="Delta MDL"))
                continue
            vals, progress, tried = [], [], 0
            for _ in range(ADMIT_DRAWS):
                if len(vals) == 2 or self.left() < 30:
                    break
                i, s = self._take("admit")
                tried += 1
                try:
                    p = build(self.stream(i), s, self.root / "adm")
                    if p["pid"] in tasks:
                        continue
                    inv = D.Inv10d(p)
                    ev0 = inv.run(inv.legacy, True)
                except Exception:                                   # noqa: BLE001
                    continue
                node = dict(specs=[copy.deepcopy(x) for x in inv.legacy], ev=ev0)
                bound = SD.macro_cands(inv, dict(de=dict(skills={"c": cand})), node, [0, 1, 2])
                if not bound:
                    continue
                prog = False
                for k, _, s2, _, _ in bound:
                    specs = list(node["specs"])
                    specs[k] = s2
                    ev = inv.run(specs, True)
                    lost = set(ev0["passed"]) - set(ev["passed"])
                    f0 = len(ev0["failed"]) + sum(map(len, ev0["stage_fail"]))
                    f1 = len(ev["failed"]) + sum(map(len, ev["stage_fail"]))
                    prog = prog or (not lost and not ev.get("error") and f1 < f0)
                vals.append(p)
                progress.append(prog)
            if not vals:
                self.log("abstraction", dict(row, admitted=False, why=f"binds on no admission project ({tried} drawn)"))
                mem["_nobind"][cand["canonical"]] = mem["_nobind"].get(cand["canonical"], 0) + 1
                if mem["_nobind"][cand["canonical"]] < NOBIND_RETRIES:      # Phase 10E: retried at a later sleep
                    mem["_tried"].remove(cand["canonical"])
                continue
            if not any(progress):
                self.log("abstraction", dict(row, admitted=False, why="no modular sub-problem progress", validation=len(vals)))
                continue
            trial = copy.deepcopy(mem)
            trial["de"]["skills"]["candidate"] = dict(cand)
            rows = {}
            for p in vals:
                out = {}
                for tag, m in (("base", mem), ("trial", trial)):
                    _, _, v, w = investigate(p, m)
                    out[tag] = (v, w)
                rows[p["pid"]] = out
            lost = [k for k, v in rows.items() if v["base"][0] and not v["trial"][0]]
            wrong = [sum(v[t][1] for v in rows.values()) for t in ("base", "trial")]
            ok = not lost and wrong[1] <= wrong[0]
            if ok:
                mem["de"]["skills"][f"L{len(mem['de']['skills'])}"] = dict(cand, valley_crossing=row["valley_crossing"], admission=dict(delta_mdl=dm, progress=progress, rows=rows))
            self.log("abstraction", dict(row, admitted=ok, progress=progress, rows=rows, why="admitted" if ok else "loses a completion or adds a wrong submission"))

    def dreams(self):
        n = max(0, round(self.M["dream_ratio"] * self.M["batch"]))
        for _ in range(n):
            if self.left() < 30:
                return
            i, s = self._take("dream")
            try:
                p = build(self.stream(i), s, self.root / "dream")
                inv = D.Inv10d(p)
            except Exception:                                       # noqa: BLE001
                continue
            truth = json.loads((Path(p["hidden_dir"]) / "truth.json").read_text())
            tev = inv.run([truth[nd] for nd in D.NODES], True)
            if not tev["ok"] or not D.verify_hidden(p, [truth[nd] for nd in D.NODES], engine="duckdb")["ok"]:
                self.log("dreams", dict(project=p["pid"], contract_guard=False))
                continue
            path, found = witness(inv, truth)
            nrec = 0
            if path:
                try:
                    evs, sp = self._sources(p["pid"], inv, path, "#dream")
                    recs = step_records(inv, path, evs, sp, rng(self.rep, 2, s))
                    self.mem["steps"].append([p["pid"] + "#dream", recs])
                    nrec = len(recs)
                except Exception as e:                              # noqa: BLE001
                    self.log("events", dict(kind="dream_record_failed", project=p["pid"], err=str(e)[:80]))
            self.log("dreams", dict(project=p["pid"], family=self.stream(i)["family"], contract_guard=True, witness=found, depth=len(path), records=nrec))
        self._trim()

    def train_rankers(self):
        steps = [(pid, recs) for pid, recs in self.mem["steps"]]
        prim = [(pid, r["pos"], ng) for pid, recs in steps for r in recs for ng in r["negs"]]
        if len(prim) < 20:
            return
        projects = sorted({pid.split("#")[0] for pid, _ in steps})
        held = set(rng(self.rep, self.cycles, 3).sample(projects, max(1, len(projects) // 5)))
        info = {}
        for tag, pairs, nmac in (("L0", prim, 0), ("Lstar",) + rewrite(steps, self.mem["de"]["skills"])):
            tr = [(a, b) for pid, a, b in pairs if pid.split("#")[0] not in held]
            te = [(a, b) for pid, a, b in pairs if pid.split("#")[0] in held]
            w = G.train(tr, seed=seed_of(self.rep, self.cycles, 4))
            self.mem["guides"][tag] = w
            info[tag] = dict(pairs=len(pairs), train=len(tr), heldout=len(te), heldout_pair_accuracy=G.pair_accuracy(w, te), weights=len(w), macro_steps=nmac)
        self.mem["guide"] = dict(kind="learned", w=self.mem["guides"]["Lstar"], ratio=SD.RATIO)
        self.log("ranker", dict(info, cycle=self.cycles, held_projects=sorted(held)))

    def checkpoint(self, N):
        ck = dict(name=self.name, rep=self.rep, N=N, memory=self.mem, cost=self.cost, n=self.n, cycles=self.cycles, cursor=self.cursor, wall=round(time.time() - self.t0, 1))
        p = self.out / f"{self.name}.N{N}.json"
        tmp = Path(str(p) + ".tmp")
        tmp.write_text(json.dumps(ck, default=list))
        tmp.replace(p)
        self.log("checkpoints", dict(N=N, skills=[s["canonical"] for s in self.mem["de"]["skills"].values()], steps=sum(len(r) for _, r in self.mem["steps"]),
                                     guides=sorted(self.mem["guides"]), cost={k: round(v, 1) for k, v in self.cost.items()}))
        return p
