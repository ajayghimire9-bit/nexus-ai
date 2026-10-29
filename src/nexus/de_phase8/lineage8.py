"""Phase 8 source lineages (NOT LOCKED): procedure selection by FUTURE LEARNING.

Both cohorts start from F0 (shared prior) and an empty task-derived memory; the archive rule (FIXED_W) and the improver M0
are FROZEN in both (no Phase 7 archive-weight updates). Both run the same memory / method learner:
  per project  investigate with the current procedure; submit (+ one retry flipping a trust-resolved point); hidden
               verification is the source feedback; update evidence weights (verified edits +, regressions -), calibrated
               trust, and skill sources (verified repairs and the best retained partial program of unsolved projects)
  per cycle    (every `batch` projects) method consolidation: invent7 compatible clusters -> at most one new candidate ->
               admit8 on applicable admission projects OUTSIDE its support plus one retention project, base vs trial with
               the bounded method queue (search8, same total work): admitted iff it enables a completion or cuts
               deterministic work by >= 20 % on the same non-empty correct set, never adds a wrong submission and never
               loses a completion; the trace separates bound / executed / on a successful path / caused
Full additionally runs FUTURE-LEARNING ROUNDS (FixedLearner keeps F0):
  screen       procedure proposals (procedure7.proposals: typed insertions, pairs, sampled edits) replayed on a cached
               screen pool; shortlist ONE proposal whose BEHAVIOUR SIGNATURE (decision + choices, documents read, questions,
               how each point was resolved, search configuration) differs from the incumbent's on >= 1 pool task, that
               adds no wrong submission and loses at most one correct outcome there (a bounded exploration allowance -
               immediate completion is not the criterion); ranked by pool correct, then number of tasks whose behaviour
               differs (a screening prior that keeps the longitudinal test informative, not a reward), then cost; if no
               supported proposal qualifies, the best UNSUPPORTED one (replay cannot judge it) is taken for live exploration.
               (Stage 1 rehearsal: an action-log difference alone selected no-op edits - a redundant resolve deleted, two
               independent actions swapped - and both rollouts were identical; fixed before any source outcome.)
  rollout      two clones of the exact parent checkpoint (independent memory / caches): incumbent vs candidate procedure,
               each FIXED within its trajectory, on the SAME exogenous stream of ROLL_BATCHES x batch projects with normal
               evidence learning and method consolidation (no nested procedure auditions); the edit must be EXERCISED early
               enough to be followed by >= 2 complete cycles, else the comparison is UNINFORMATIVE (not a tie)
  downstream   both frozen memories are evaluated with the SAME procedure F0 and archive rule on disjoint future projects
  select       the candidate wins iff it adds no wrong submission (trajectory or downstream) and verifies more downstream
               projects - or the same non-empty set at >= 10 % lower deterministic cost
  confirm      a second disjoint downstream set: the winner must not be worse (verified >=, wrong <=)
  adopt        only the PROCEDURE change; clone memories are discarded and the main lineage learns on.
Every round records the causal chain: edit -> evidence collected -> memory -> downstream decisions -> verified outcome."""
from __future__ import annotations

import copy
import hashlib
import json
import random
import time
from pathlib import Path

from nexus.de_phase6 import pipeline6 as P6, skills6 as SK, trust6 as T6, world6 as W6
from nexus.de_phase7 import lineage7 as L7, procedure7 as PR7, seeds7 as S7, skills7 as SK7, world7 as W7
from nexus.de_phase8 import procedure8 as PR8, seeds8 as S

WS = Path(__file__).resolve().parents[3] / "var" / "agi8_ws"
M0 = dict(skill_min_support=2, skill_max_len=3, trust_margin=1.0, trust_support=2, batch=4)
W_SRC, WALL_SRC = 3000, 6.0
ROLL_BATCHES, DOWN_N, CONF_N, POOL_N = 3, 6, 6, 6
SOURCE_SPECS = L7.SOURCE_SPECS


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=list).encode()).hexdigest()[:16]


def empty_memory():
    return dict(de=dict(w={}, skills={}), trust=T6.empty(), skill_src=[], M=copy.deepcopy(M0))


def build(spec, seed, root):
    return W7.make_project7(spec, seed, root)


def evaluate_memory(mem, projects, root_tag=None):
    """Frozen memory, procedure F0, fixed archive rule: -> {pid: row}."""
    live = PR8.Live(W_SRC, WALL_SRC)
    rows = {}
    for p in projects:
        st = PR8.investigate(p, live, copy.deepcopy(mem), PR8.F0, {})
        o = PR8.outcome(p, st)
        rows[p["pid"]] = dict(verified=o["verified"], wrong=o["wrong"], decision=o["decision"], reason=st.decision.get("reason"),
                              cost_s=round(PR8.cost_s(st.cost), 4), questions=st.cost["questions"],
                              resolutions=[d["via"] for d in st.dps], via_skill=bool((st.cand or {}).get("via_skill")))
    return rows


class Lineage:
    def __init__(self, name, cohort, blk, root, deadline, rng_key, out_path=None, mem=None, prog=None, lib=None, frozen_procedure=False):
        self.name, self.cohort = name, cohort
        self.mem = mem or empty_memory()
        self.prog, self.lib = copy.deepcopy(prog or PR8.F0), copy.deepcopy(lib or {})
        if prog is not None:
            self.prog = prog                                   # clones keep statement identities (exercise tracking)
        self.blk, self.root, self.deadline, self.out_path = blk, Path(root), deadline, out_path
        self.frozen_procedure = frozen_procedure
        self.rng = random.Random(f"agi8|{rng_key}")
        self.live = PR8.Live(W_SRC, WALL_SRC)
        self.rows, self.log, self.cycles, self.rounds = [], [], [], []
        self.admit_seeds = list(blk["admit"])
        self.cursor = dict(pool=0, roll=0, down=0, conf=0)
        self.t0 = time.time()
        self.cost = dict(main_s=0.0, round_s=0.0, consolidation_s=0.0)

    def left(self):
        return self.deadline - time.time()

    # ---- one source project
    def learn_project(self, spec, seed, root=None):
        t0 = time.time()
        p = build(spec, seed, root or (self.root / "src"))
        st = PR8.investigate(p, self.live, self.mem, self.prog, self.lib)
        cand = st.cand or {}
        subs, verified, wrong = [], False, False
        if st.decision["kind"] == "submit":
            o = PR8.outcome(p, st)
            subs.append(o["verified"])
            verified, wrong = o["verified"], o["wrong"]
            if not verified:
                tr = [d for d in st.dps if (d["via"] or "").startswith("trust") and len(d["options"]) == 2]
                if len(tr) == 1:
                    k = f"{tr[0]['stage']}:{tr[0]['pos']}"
                    st.decision["choices"][k] = [o_ for o_ in tr[0]["options"] if o_ != tr[0]["resolved"]][0]
                    o2 = PR8.outcome(p, st)
                    subs.append(o2["verified"])
                    if o2["verified"]:
                        verified = True
                        tr[0]["resolved"] = st.decision["choices"][k]
        n_trust0 = len(self.mem["trust"]["records"])
        for d in st.dps:
            if not d.get("claims"):
                continue
            if d["undecided"]:
                T6.record(self.mem["trust"], p["pid"], d["claims"], None, "stakeholder undetermined (negative evidence)")
                continue
            eff = how = None
            if verified and d["resolved"] is not None and d.get("effects"):
                eff = d["effects"][d["options"].index(d["resolved"])]
                how = "verified submission" if len(subs) == 1 else "refuted then verified submission"
            elif d["via"] == "clarification" and d.get("effects"):
                eff = d["effects"][d["options"].index(d["resolved"])]
                how = "stakeholder answer"
            if eff is not None:
                T6.record(self.mem["trust"], p["pid"], d["claims"], eff, how)
        feats = set(cand.get("start_features") or [])
        path = cand.get("path") or []
        w = self.mem["de"]["w"]
        if verified and path:
            for k, op, prm in path:
                for f in feats:
                    w.setdefault(f, {})[op] = w.get(f, {}).get(op, 0.0) + 1.0
        for r in (cand.get("regressions") or [])[:30]:
            for f in r["pre"]:
                w.setdefault(f, {})[r["op"]] = w.get(f, {}).get(r["op"], 0.0) - 0.5
        inv = self.live.invs.get(p["pid"])
        partial = cand.get("partial")
        n_src0 = len(self.mem["skill_src"])
        try:
            if verified and path and inv is not None:
                SK.record(self.mem["skill_src"], p["pid"], inv, [tuple(e) for e in path], feats, True)
            elif partial and inv is not None and (partial["stage_fixed"] > 0 or partial["gain"] > 0):
                SK.record(self.mem["skill_src"], p["pid"] + "#partial", inv, [tuple(e) for e in partial["path"]], feats, True)
        except Exception as e:                                   # noqa: BLE001
            self.log.append(dict(step="record_failed", project=p["pid"], err=str(e)[:80]))
        self.live.invs.pop(p["pid"], None)
        row = dict(project=p["pid"], paradigm=p["paradigm"], seed=seed, decision=st.decision["kind"], reason=st.decision.get("reason"), submissions=subs,
                   verified=verified, wrong_first=wrong, questions=st.cost["questions"], reads=st.cost["reads"], work=st.cost["work"],
                   probe_runs=st.cost["probe_runs"], cost_s=round(PR8.cost_s(st.cost), 4), trust_added=len(self.mem["trust"]["records"]) - n_trust0,
                   src_added=len(self.mem["skill_src"]) - n_src0, partial=bool(partial), via_skill=bool(cand.get("via_skill")),
                   obligations=st.obligation_status, executed=sorted(st.executed), wall=round(time.time() - t0, 3), procedure_digest=digest([self.prog, self.lib]))
        self.rows.append(row)
        return row

    # ---- method consolidation
    def cycle(self, idx):
        t0 = time.time()
        c = dict(cycle=idx, t=round(time.time() - self.t0, 1), projects=len(self.rows), skills=self.consolidate())
        self.cycles.append(c)
        self.cost["consolidation_s"] += time.time() - t0
        self.save()
        return c

    def consolidate(self):
        if not self.mem["skill_src"] or self.left() < 15:
            return dict(candidates=0)
        cands = SK7.invent7(self.mem["skill_src"], self.mem["M"]["skill_min_support"], self.mem["M"]["skill_max_len"])
        known = {s["canonical"] for s in self.mem["de"]["skills"].values()} | {e["canonical"] for e in self.log if e.get("step") == "skill_admission"}
        cands = [x for x in cands if x["canonical"] not in known][:1]
        out = dict(candidates=len(cands), admitted=[])
        for cand in cands:
            projs, retention = self._admission_projects(cand)
            if len(projs) < 2:
                self.log.append(dict(step="skill_admission", canonical=cand["canonical"], edits=cand["edits"], admitted=False,
                                     why=dict(reason="fewer than 2 applicable admission projects outside the support")))
                continue
            ok, why = admit8(self.mem, cand, projs, retention)
            if ok:
                sid = f"S{len(self.mem['de']['skills'])}"
                self.mem["de"]["skills"][sid] = dict(cand, admission={k: v for k, v in why.items() if k != "rows"}, validated_on=[p["pid"] for p in projs + retention])
                out["admitted"].append(sid)
            self.log.append(dict(step="skill_admission", canonical=cand["canonical"], edits=cand["edits"], support=cand["support"], novelty=cand["novelty"],
                                 from_partial=cand["from_partial"], admitted=ok, why=why))
        return out

    def _admission_projects(self, cand):
        pre, projs, retention = set(cand["pre"]), [], []
        support = {s.split("#")[0] for s in cand["support"]}
        for _ in range(10):
            if (len(projs) == 2 and retention) or not self.admit_seeds:
                break
            s = self.admit_seeds.pop(0)
            try:
                p = build(SOURCE_SPECS[s % len(SOURCE_SPECS)], s, self.root / "adm")
                if p["pid"] in support:
                    continue
                inv = P6.Inv6(p)
                ev0 = inv.run(inv.legacy)
            except Exception:                                  # noqa: BLE001
                continue
            if (not pre or len(pre & ev0["features"]) / len(pre) >= 0.5) and len(projs) < 2:
                projs.append(p)
            elif not retention:
                retention.append(p)
        return projs, retention

    # ---- future-learning round (Full)
    def _take(self, kind, n, specs_fn):
        out = []
        seeds = list(self.blk[kind])
        while len(out) < n and self.cursor[kind] < len(seeds):
            s = seeds[self.cursor[kind]]
            self.cursor[kind] += 1
            try:
                out.append((specs_fn(s), s))
            except RuntimeError:
                continue
        return out

    def screen(self, idx, rec):
        # screen (replay on a cached pool, charged real execution)
        pool = []
        for spec, s in self._take("pool", POOL_N, lambda s: S7.pool_specs()[s % len(S7.pool_specs())]):
            try:
                pool.append(build(spec, s, self.root / "pool"))
            except RuntimeError:
                continue
        live = PR8.Live(W_SRC, WALL_SRC)
        caches = {p["pid"]: PR8.build_entry(p, live, self.mem) for p in pool}
        base = PR8.score(self.prog, self.lib, pool, caches, self.mem)
        props = PR7.proposals(self.prog, self.lib, random.Random(f"agi8-prop|{self.name}|{idx}"), typed_pairs=True)
        scored = []
        for et, new, block, desc in props:
            rows = PR8.score(new, self.lib, pool, caches, self.mem)
            n_diff = sum(rows[p]["signature"] != base[p]["signature"] for p in rows)
            if not n_diff:                                       # same evidence and decisions everywhere: uninformative
                continue
            unsup = sum(r["unsupported"] for r in rows.values())
            c = sum(r["correct"] for r in rows.values())
            wr = sum(r["wrong"] for r in rows.values())
            scored.append(dict(desc=desc, type=et, new=new, block=block, correct=c, wrong=wr, unsupported=unsup, behaviour_diff_tasks=n_diff,
                               cost=round(sum(r["cost"]["wall_s"] for r in rows.values()), 3)))
        bc, bw = sum(r["correct"] for r in base.values()), sum(r["wrong"] for r in base.values())
        ok = [x for x in scored if x["unsupported"] == 0 and x["wrong"] <= bw and x["correct"] >= bc - 1]
        ok.sort(key=lambda x: (-x["correct"], -x["behaviour_diff_tasks"], x["cost"], len(json.dumps(x["new"]))))
        uns = sorted([x for x in scored if x["unsupported"] > 0 and x["wrong"] <= bw], key=lambda x: (-x["correct"], -x["behaviour_diff_tasks"], x["cost"]))
        pick = ok[0] if ok else (uns[0] if uns else None)
        rec.update(screen=dict(pool=[p["pid"] for p in pool], proposals=len(props), behaviourally_different=len(scored), admissible=len(ok),
                               unsupported_only=len(uns), incumbent=dict(correct=bc, wrong=bw), pick=None if pick is None else
                               {k: v for k, v in pick.items() if k not in ("new", "block")}, pick_kind="supported" if ok else "unsupported" if uns else None))
        return pick

    def future_round(self, idx):
        t_start = time.time()
        rec = dict(round=idx, t=round(t_start - self.t0, 1), parent_projects=len(self.rows), parent_digest=digest(self.mem))
        pick = self.screen(idx, rec)
        if pick is None:
            rec["result"] = "no candidate"
            return self._close_round(rec, t_start)
        # 2 rollout on a common exogenous stream
        n_roll = ROLL_BATCHES * self.mem["M"]["batch"]
        stream = self._take("roll", n_roll, lambda s: SOURCE_SPECS[s % len(SOURCE_SPECS)])
        block_ids = {id(b) for b in pick["block"]}
        clones = {}
        for tag, prog in (("incumbent", copy.deepcopy(self.prog)), ("candidate", pick["new"])):
            c = Lineage(f"{self.name}|r{idx}|{tag}", self.cohort, self.blk, self.root / f"roll{idx}_{tag}", self.deadline, f"{self.name}|{idx}|{tag}",
                        mem=copy.deepcopy(self.mem), prog=prog, lib=copy.deepcopy(self.lib), frozen_procedure=True)
            c.admit_seeds = list(self.admit_seeds)                 # identical (independent) admission opportunities
            first = None
            for i, (spec, s) in enumerate(stream):
                if c.left() < 8:
                    break
                try:
                    row = c.learn_project(spec, s, root=self.root / f"roll{idx}_{tag}" / "src")
                except RuntimeError:
                    continue
                if first is None and (not block_ids or block_ids & set(row["executed"])):
                    first = i
                if (i + 1) % self.mem["M"]["batch"] == 0:
                    c.cycle(len(c.cycles))
            clones[tag] = dict(lin=c, exercised_at=first)
        cand_c = clones["candidate"]
        ex = cand_c["exercised_at"]
        cycles_after = sum(1 for cy in cand_c["lin"].cycles if ex is not None and cy["projects"] > ex)
        traj = {tag: dict(projects=len(v["lin"].rows), verified=sum(r["verified"] for r in v["lin"].rows), wrong=sum(r["wrong_first"] for r in v["lin"].rows),
                          reads=sum(r["reads"] for r in v["lin"].rows), questions=sum(r["questions"] for r in v["lin"].rows),
                          trust_records=len(v["lin"].mem["trust"]["records"]), skill_src=len(v["lin"].mem["skill_src"]),
                          skills=sorted(s["canonical"] for s in v["lin"].mem["de"]["skills"].values()), cost_s=round(sum(r["cost_s"] for r in v["lin"].rows), 3),
                          cycles=len(v["lin"].cycles)) for tag, v in clones.items()}
        rec.update(rollout=dict(stream=[s for _, s in stream], exercised_at=ex, cycles_after_exercise=cycles_after, trajectories=traj))
        if ex is None or cycles_after < 2:
            rec["result"] = "uninformative (edit not exercised early enough for 2 complete cycles)"
            return self._close_round(rec, t_start)
        # 3 downstream: same procedure F0 for both frozen memories
        down = [build(spec, s, self.root / "down") for spec, s in self._take("down", DOWN_N, lambda s: SOURCE_SPECS[(s * 7) % len(SOURCE_SPECS)])]
        dr = {tag: evaluate_memory(v["lin"].mem, down) for tag, v in clones.items()}
        summ = lambda rows: dict(verified=sum(r["verified"] for r in rows.values()), wrong=sum(r["wrong"] for r in rows.values()),  # noqa: E731
                                 solved=sorted(p for p, r in rows.items() if r["verified"]), cost_s=round(sum(r["cost_s"] for r in rows.values()), 3))
        di, dc = summ(dr["incumbent"]), summ(dr["candidate"])
        rec["downstream"] = dict(incumbent=di, candidate=dc, per_project={p: [dr["incumbent"][p]["decision"] + ":" + str(dr["incumbent"][p]["verified"]),
                                                                            dr["candidate"][p]["decision"] + ":" + str(dr["candidate"][p]["verified"]),
                                                                            dr["incumbent"][p]["resolutions"], dr["candidate"][p]["resolutions"]] for p in dr["incumbent"]})
        win = (traj["candidate"]["wrong"] <= traj["incumbent"]["wrong"] and dc["wrong"] <= di["wrong"] and
               (dc["verified"] > di["verified"] or (dc["verified"] == di["verified"] > 0 and dc["solved"] == di["solved"] and dc["cost_s"] <= 0.9 * di["cost_s"])))
        if not win:
            rec["result"] = "rejected (no downstream advantage)"
            return self._close_round(rec, t_start)
        conf = [build(spec, s, self.root / "conf") for spec, s in self._take("conf", CONF_N, lambda s: SOURCE_SPECS[(s * 11) % len(SOURCE_SPECS)])]
        cr = {tag: summ(evaluate_memory(v["lin"].mem, conf)) for tag, v in clones.items()}
        rec["confirmation"] = cr
        if cr["candidate"]["verified"] < cr["incumbent"]["verified"] or cr["candidate"]["wrong"] > cr["incumbent"]["wrong"]:
            rec["result"] = "rejected at confirmation"
            return self._close_round(rec, t_start)
        self.prog = copy.deepcopy(pick["new"])
        rec["result"] = "adopted"
        rec["adopted_program"] = self.prog
        return self._close_round(rec, t_start)

    def _close_round(self, rec, t_start):
        rec["round_s"] = round(time.time() - t_start, 1)
        self.cost["round_s"] += time.time() - t_start
        self.rounds.append(rec)
        self.save()
        return rec

    def checkpoint(self):
        return dict(name=self.name, cohort=self.cohort, memory=self.mem, procedure=self.prog, library=self.lib, rows=self.rows, cycles=self.cycles,
                    rounds=self.rounds, log=self.log, n_projects=len(self.rows), cost=self.cost, wall=round(time.time() - self.t0, 1))

    def save(self):
        if self.out_path is None:
            return
        tmp = Path(str(self.out_path) + ".tmp")
        tmp.write_text(json.dumps(self.checkpoint(), default=list))
        tmp.replace(self.out_path)


def admit8(mem, cand, projs, retention, min_saving=0.2):
    live_b, live_t = PR8.Live(W_SRC, WALL_SRC), PR8.Live(W_SRC, WALL_SRC)
    trial = copy.deepcopy(mem)
    trial["de"]["skills"]["candidate"] = cand
    rows, trace = {}, []
    for p in projs + retention:
        out = {}
        for tag, m, live in (("base", mem, live_b), ("trial", trial, live_t)):
            r = live.search(p, m, "whole", "on")
            ok = False
            if r["outcome"] == "submitted":
                files = [P6.ir6.lower(s, st["target_lang"]) for s, st in zip(r["specs"], p["stages"])]
                ok = W6.evaluate6(p, files)["ok"]
            out[tag] = dict(verified=ok, wrong=r["outcome"] == "submitted" and not ok, work=r["cost"].get("work", 0), via_skill=r.get("via_skill", False),
                            mq=r.get("method_queue"))
        rows[p["pid"]] = out
        trace.append(dict(project=p["pid"], retention=p in retention, bound=bool((out["trial"]["mq"] or {}).get("tried")),
                          executed=bool((out["trial"]["mq"] or {}).get("passed_checks")), on_path=out["trial"]["via_skill"] and out["trial"]["verified"],
                          caused=(out["trial"]["verified"] and not out["base"]["verified"]) or
                                 (out["trial"]["via_skill"] and out["trial"]["verified"] and out["base"]["verified"] and out["trial"]["work"] < out["base"]["work"])))
    wb = sum(v["base"]["wrong"] for v in rows.values())
    wt = sum(v["trial"]["wrong"] for v in rows.values())
    lost = [p for p, v in rows.items() if v["base"]["verified"] and not v["trial"]["verified"]]
    gained = [p for p, v in rows.items() if v["trial"]["verified"] and not v["base"]["verified"]]
    same = sorted(p for p, v in rows.items() if v["base"]["verified"]) == sorted(p for p, v in rows.items() if v["trial"]["verified"])
    xb = sum(v["base"]["work"] for v in rows.values() if v["base"]["verified"])
    xt = sum(v["trial"]["work"] for v in rows.values() if v["trial"]["verified"])
    why = dict(rows=rows, trace=trace, wrong=[wb, wt], lost=lost, gained=gained, work_on_correct=[xb, xt])
    if wt > wb:
        return False, dict(why, reason="adds a wrong submission")
    if lost:
        return False, dict(why, reason="loses a completion")
    if gained and any(t["caused"] for t in trace):
        return True, dict(why, reason="enables a completion")
    if same and xb > 0 and xt <= (1 - min_saving) * xb and any(t["caused"] for t in trace):
        return True, dict(why, reason=f"cuts deterministic work by >= {min_saving:.0%} on the same non-empty correct set")
    return False, dict(why, reason="no attributable benefit")
