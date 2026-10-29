"""Phase 10B learner (NOT LOCKED): de_phase10.lineage10.Learner (protected, unchanged) with
  VALLEY DETECTION   every verified repair path is replayed step by step; a consecutive pair (a1, a2) with
                     delta-score(a1) <= 0 and delta-score(a1 o a2) > 0 is a VALLEY CROSSING: it is recorded as a skill source
                     and its canonical role-form edit pair is remembered as a bridge
  BRIDGE PRIORITY    sleep abstraction considers bridge candidates first (the MDL + LOPO admission rule is unchanged)
  BRIDGE GUIDE       the learned ranker carries bridge=True (search10b: 40 % guided / 30 % bridge lookahead / 30 % fallback;
                     child mixing ratio 4/7)
  M* GATE FIX        m_round10b compares clones over the validation tasks that were BUILT for every clone, requires the
                     edited M to introduce 0 new build / truncation failures relative to M0, and counts a clone as
                     truncated only when it stopped early on the deadline (an identical generation failure in every clone
                     no longer vetoes)
  pi* rounds are DISABLED (no adoption in Phases 8-10; their cost is spent on the two training repetitions instead).
  Budget settings (pre-registered before any outcome): at most ONE abstraction candidate per sleep (bridge candidates first),
  the M* round compares M0 with M' only (no M_rand clone), and dreams use SQLite / DuckDB repositories only."""
from __future__ import annotations

import copy
import json
import random
import time
from pathlib import Path

from nexus.de_phase6 import pipeline6 as P6, skills6 as SK, trust6 as T6
from nexus.de_phase7 import skills7 as SK7
from nexus.de_phase8 import lineage8 as L8
from nexus.de_phase10 import guide10 as G, lineage10 as LN, manifest10 as MF, memory10 as MEM, procedure10 as PR10
from nexus.de_phase10b import fixes10b, search10b  # noqa: F401  (ROUND primitive, idempotent coverage, bridge search)

build = LN.build
paradigm_of = LN.paradigm_of


def bridge_sig(edits):
    """Operator sequence of a (role-form) edit sequence: the bridge identity used for abstraction priority."""
    return json.dumps([e[0] for e in edits])


class Learner(LN.Learner):
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
                self.valleys(inv, p["pid"], [tuple(e) for e in path])
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

    def valleys(self, inv, pid, path):
        specs = list(inv.legacy)
        scores = [inv.run(specs, True)["score"]]
        stages = []
        for k, op, prm in path:
            specs = P6.replay(inv, [(k, op, prm)], specs)
            scores.append(inv.run(specs, True)["score"])
            stages.append(list(specs))
        found = []
        for i in range(len(path) - 1):
            if scores[i + 1] - scores[i] <= 1e-9 and scores[i + 2] - scores[i] > 1e-9:
                before = len(self.mem["skill_src"])
                SK.record(self.mem["skill_src"], pid + "#bridge", inv, [tuple(path[i]), tuple(path[i + 1])], set(), True)
                for rec in self.mem["skill_src"][before:]:
                    if len(rec["edits"]) >= 2:
                        sig = bridge_sig(rec["edits"])
                        if sig not in self.mem.setdefault("bridges", []):
                            self.mem["bridges"].append(sig)
                found.append(dict(i=i, edits=[path[i][1], path[i + 1][1]], gains=[round(scores[i + 1] - scores[i], 3), round(scores[i + 2] - scores[i], 3)]))
        if found:
            self.log("valleys", dict(project=pid, valleys=found))

    def dreams(self):
        """Dreams on SQLite / DuckDB repositories only (witness steps run the hidden evaluator; Spark start-up dominated the
        dream cost in rehearsal). Otherwise lineage10.Learner.dreams."""
        orig = MF.train_spec

        def no_spark(i, seed):
            sp = orig(i, seed)
            if sp.get("engine") == "spark":
                sp = dict(sp, engine="duckdb")
            return sp
        MF.train_spec = no_spark
        try:
            super().dreams()
        finally:
            MF.train_spec = orig

    def train_ranker(self):
        super().train_ranker()
        if self.mem.get("guide"):
            self.mem["guide"]["bridge"] = True
            self.mem["guide"]["ratio"] = 4 / 7

    def abstraction(self):
        mem = self.mem
        if not mem["skill_src"] or self.left() < 30:
            return
        cands = SK7.invent7(mem["skill_src"], mem["M"]["skill_min_support"], mem["M"]["skill_max_len"])
        known = {s["canonical"] for s in mem["de"]["skills"].values()} | set(mem.get("_tried", []))
        bridges = set(mem.get("bridges", []))
        fresh = [c for c in cands if c["canonical"] not in known]
        fresh.sort(key=lambda c: bridge_sig(c["edits"]) not in bridges)   # valley-crossing bridge macros first (stable otherwise)
        for cand in fresh[:1]:                                         # 1 candidate per sleep (Phase 10B budget; bridge-first)
            mem.setdefault("_tried", []).append(cand["canonical"])
            tasks = {s.split("#")[0] for s in cand["support"]}
            dm = MEM.delta_mdl(len(cand["edits"]), len(tasks), len(mem["de"]["skills"]))
            row = dict(canonical=cand["canonical"], edits=cand["edits"], novelty=cand["novelty"], support=cand["support"], from_partial=cand["from_partial"], delta_mdl=dm,
                       valley_crossing=bridge_sig(cand["edits"]) in bridges)
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
                mem["de"]["skills"][sid] = dict(cand, valley_crossing=bridge_sig(cand["edits"]) in bridges, admission=dict(delta_mdl=dm, lopo=dict(paradigms=sorted({p['paradigm'] for p in projs + retention}),
                                                                                               wrong=why["wrong"], lost=why["lost"], gained=why["gained"], trace=why["trace"])))
            self.log("abstraction", dict(row, admitted=lopo_ok, lopo_projects=[p["pid"] for p in projs + retention], why={k: v for k, v in why.items() if k != "rows"}))



def m_round(learner, root):
    """M* vs M0 vs M_rand (common stream, independent memories), compared over the validation tasks BUILT for every clone."""
    t = time.time()
    rng = random.Random(f"M|{learner.name}")
    k = rng.choice(sorted(LN.SPACE))
    alt = [v for v in LN.SPACE[k] if v != learner.mem["M"][k]]
    Medit = dict(learner.mem["M"], **{k: rng.choice(alt)})
    Mrand = dict(learner.mem["M"], **{f: rng.choice(v) for f, v in LN.SPACE.items()})
    stream = [learner._take("mroll") for _ in range(20)]
    val, val_fail = [], []
    for _ in range(10):
        s = learner._take("mval")
        try:
            val.append(build(MF.train_spec(s % 90, s), s, Path(root) / "mval", require=False))
        except RuntimeError:
            val_fail.append(s)
    res = {}
    for tag, M in (("M0", learner.mem["M"]), ("M_edit", Medit)):          # M_rand dropped in Phase 10B (budget; pre-registered)
        mem = copy.deepcopy(learner.mem)
        mem["M"] = copy.deepcopy(M)
        if mem.get("guide"):
            mem["guide"]["ratio"] = 4 / 7
        c = Learner(f"{learner.name}.mround.{tag}", mem, learner.prog, Path(root) / tag, learner.deadline, learner.out, evolve_pi=False, seeds=learner.seeds)
        c.cursor = dict(learner.cursor)
        built_fail, truncated = [], False
        for i, s in enumerate(stream):
            if c.left() < 40:
                truncated = True
                break
            try:
                c.wake(MF.train_spec(s % 90, s), s)
            except RuntimeError:
                built_fail.append(s)
                continue
            if (i + 1) % 10 == 0:
                c.sleep()
        per = {}
        live = PR10.Live(LN.W_SRC, LN.WALL)
        for p in val:
            st = PR10.investigate(p, live, copy.deepcopy(c.mem), PR10.F0, {})
            o = PR10.outcome(p, st)
            per[p["pid"]] = (o["verified"], o["wrong"])
        res[tag] = dict(M=M, per=per, verified=sum(v for v, _ in per.values()), wrong=sum(w for _, w in per.values()), tasks=c.n, build_failures=built_fail,
                        truncated=truncated, skills=len(c.mem["de"]["skills"]))
    base_fail = set(res["M0"]["build_failures"])
    new_fail = set(res["M_edit"]["build_failures"]) - base_fail
    informative = not any(r["truncated"] for r in res.values()) and not new_fail
    adopt = informative and res["M_edit"]["verified"] > res["M0"]["verified"] and res["M_edit"]["verified"] >= 1 and res["M_edit"]["wrong"] <= res["M0"]["wrong"]
    if adopt:
        learner.mem["M"] = copy.deepcopy(Medit)
    learner.cost["m_round"] += time.time() - t
    learner.log("m", dict(edit=[k, Medit[k]], results={t_: {x: y for x, y in r.items() if x != "per"} for t_, r in res.items()}, validation_build_failures=val_fail,
                          new_build_failures=sorted(new_fail), informative=informative, adopted=adopt, wall=round(time.time() - t, 1)))
    return adopt
