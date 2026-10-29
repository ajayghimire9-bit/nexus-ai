"""Phase 7 source lineages (NOT LOCKED): repeated LEARN -> ADMIT -> USE cycles.

Per source project (both cohorts, real execution, Tiers 1-2): investigate with the CURRENT admitted procedure; submit
(+ one retry flipping a trust-resolved decision point, as in Phase 6); hidden-batch verification is the source feedback.
Learning after each project:
  evidence memory  operator weights (feature -> operator): + for each edit of a verified repair, - only for REGRESSIONS
                   (a check the parent passed now fails), never for neutral / worse-but-retained attempts
  trust            calibrated provenance records (trust6) from verified submissions, refuted-then-verified ones,
                   clarifications and 'undetermined' answers (negative evidence)
  skill sources    verified repairs AND the best retained intermediate program of an unsolved project (#partial),
                   in role form (skills6.record); a partial is a hypothesis until an admitted skill built on it pays off
  archive policy   Full only: delayed-utility update of the expansion / retention weights from a verified solution's
                   archived ancestors vs the other expanded programs (search7.update_policy)
Every `batch` projects one CYCLE:
  1 method consolidation: invent7 candidates (compatible clusters) -> admit_skill on applicable admission projects
    (deterministic work cost; bound / executed / responsible trace)
  2 Full only: one procedure-learning ROUND (procedure7.learn_round) on the proposal-selection pool (cached under the
    CURRENT memory) with an untouched confirmation check; the adopted procedure is used on the NEXT batch
  3 Full only: retention check - the new procedure replayed on every earlier round's caches
The checkpoint is written atomically after every cycle (a timeout keeps the last complete cycle).
Cohorts: Full (learned archive policy + learned procedure, from SEED) | FixedLearner (FIXED_W + FIXED_STRATEGY). Both have
the same language, archive capacity, evidence memory, skill machinery, trust and engines, and the same exogenous stream.
The improver M is FIXED at M0 in Stage 2 for both (an M comparison needs several complete cycles per clone, which a
300 s job cannot contain): meta_compare implements the comparator with execution assertions; its campaign is deferred."""
from __future__ import annotations

import copy
import hashlib
import json
import random
import time
from pathlib import Path

from nexus.de_phase6 import lineage6 as L6, pipeline6 as P6, skills6 as SK, trust6 as T6, world6 as W6
from nexus.de_phase7 import procedure7 as PR7, search7 as S7, seeds7 as S, skills7 as SK7, world7 as W7

WS = Path(__file__).resolve().parents[3] / "var" / "agi7_ws"
M0 = dict(skill_min_support=2, skill_max_len=3, policy_lr=0.15, worse_delta=0.35, archive_cap=48, proc_cycles=3, typed_pairs=True, src_work=3000,
          trust_margin=1.0, trust_support=2, batch=6)
SPACE = dict(skill_min_support=[2, 3], skill_max_len=[2, 3], policy_lr=[0.05, 0.15, 0.4], worse_delta=[0.15, 0.35, 0.7], archive_cap=[24, 48, 96],
             proc_cycles=[2, 3, 5], typed_pairs=[True, False], src_work=[2000, 3000, 4500])
SOURCE_SPECS = L6.SOURCE_SPECS + [dict(paradigm=p, engine=e, dp_mode="explicit", legacy_flip=True, fault_p=0.4)
                                  for p, e in (("P1", "duckdb"), ("P5", "sqlite"), ("P7", "duckdb"), ("P7", "sqlite"))]
POOL_SIZE, CONFIRM_PER_ROUND, ADMIT_PROJECTS = 6, 3, 2


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=list).encode()).hexdigest()[:16]


def empty_memory(M=None):
    return dict(de=dict(w={}, skills={}), trust=T6.empty(), skill_src=[], M=copy.deepcopy(M or M0), policy_prov=[])


def build(spec, seed, root):
    return W7.make_project7(spec, seed, root)


class Lineage:
    def __init__(self, name, cohort, blk, root, deadline, rng_key, out_path=None, mem=None, prog=None, lib=None):
        self.name, self.cohort = name, cohort
        self.mem = mem or empty_memory()
        if cohort == "Full":
            self.prog, self.lib = copy.deepcopy(prog or PR7.SEED), copy.deepcopy(lib or {})
        else:
            self.prog, self.lib = copy.deepcopy(PR7.FIXED_STRATEGY), {}
        self.blk, self.root, self.deadline, self.out_path = blk, Path(root), deadline, out_path
        self.rng = random.Random(f"agi7|{rng_key}")
        self.touch = {}
        self.live = PR7.Live(lambda p, mem: mem["M"]["src_work"], wall_cap=8.0, touch=self.touch)
        self.rows, self.log, self.cycles = [], [], []
        self.admit_seeds = list(blk["admit"])[:100]
        self.confirm_seeds = list(blk["confirm"])
        self.pool, self.round_caches = None, []
        self.t0 = time.time()

    def left(self):
        return self.deadline - time.time()

    def mem_for_search(self):
        m = self.mem if self.cohort == "Full" else dict(self.mem, policy_w=None)
        return m

    # ---- one source project
    def learn_project(self, spec, seed):
        p = build(spec, seed, self.root / "src")
        mem = self.mem_for_search()
        st = PR7.investigate(p, self.live, mem, self.prog, self.lib)
        cand = st.cand or {}
        subs, verified, wrong = [], False, False
        if st.decision["kind"] == "submit":
            o = PR7.outcome(p, st)
            subs.append(o["verified"])
            verified, wrong = o["verified"], o["wrong"]
            if not verified:
                tr = [d for d in st.dps if (d["via"] or "").startswith("trust") and len(d["options"]) == 2]
                if len(tr) == 1:
                    k = f"{tr[0]['stage']}:{tr[0]['pos']}"
                    st.decision["choices"][k] = [o_ for o_ in tr[0]["options"] if o_ != tr[0]["resolved"]][0]
                    o2 = PR7.outcome(p, st)
                    subs.append(o2["verified"])
                    if o2["verified"]:
                        verified = True
                        tr[0]["resolved"] = st.decision["choices"][k]
        for d in st.dps:                                       # calibrated trust records
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
        try:
            if verified and path and inv is not None:
                SK.record(self.mem["skill_src"], p["pid"], inv, [tuple(e) for e in path], feats, True)
            elif partial and inv is not None and (partial["stage_fixed"] > 0 or partial["gain"] > 0):
                SK.record(self.mem["skill_src"], p["pid"] + "#partial", inv, [tuple(e) for e in partial["path"]], feats, True)
        except Exception as e:                                   # noqa: BLE001
            self.log.append(dict(step="record_failed", project=p["pid"], err=str(e)[:80]))
        if self.cohort == "Full" and verified and cand.get("solution_nodes") and cand.get("other_nodes"):
            self.touch["policy_lr"] = self.touch.get("policy_lr", 0) + 1
            self.mem["policy_w"] = S7.update_policy(self.mem.get("policy_w") or dict(S7.FIXED_W), cand["solution_nodes"], cand["other_nodes"],
                                                    lr=self.mem["M"]["policy_lr"], project=p["pid"], prov=self.mem["policy_prov"])
        self.live.invs.pop(p["pid"], None)
        row = dict(project=p["pid"], paradigm=p["paradigm"], spec=spec, seed=seed, decision=st.decision["kind"], reason=st.decision.get("reason"),
                   submissions=subs, verified=verified, wrong_first=wrong, questions=st.cost["questions"], work=st.cost["work"],
                   probe_runs=st.cost["probe_runs"], wall=st.cost["wall_s"], barrier=st.barrier, coverage_by_procedure=st.coverage_checked and not st.barrier["computed"],
                   events=cand.get("events"), solution_kinds=cand.get("solution_kinds"), via_skill=cand.get("via_skill"),
                   skill_bound=len(cand.get("skill_trace") or []), partial=bool(partial), procedure_digest=digest([self.prog, self.lib]))
        self.rows.append(row)
        return row

    # ---- one cycle
    def cycle(self, idx):
        c = dict(cycle=idx, t=round(time.time() - self.t0, 1), projects=len(self.rows))
        c["skills"] = self.consolidate()
        if self.cohort == "Full" and self.left() > 25:
            c["procedure"] = self.procedure_round(idx)
        self.cycles.append(c)
        self.save()
        return c

    def consolidate(self):
        if not self.mem["skill_src"]:
            return dict(candidates=0)
        self.touch["skill_min_support"] = self.touch.get("skill_min_support", 0) + 1
        self.touch["skill_max_len"] = self.touch.get("skill_max_len", 0) + 1
        cands = SK7.invent7(self.mem["skill_src"], self.mem["M"]["skill_min_support"], self.mem["M"]["skill_max_len"])
        known = {s["canonical"] for s in self.mem["de"]["skills"].values()} | {e["canonical"] for e in self.log if e.get("step") == "skill_admission"}
        cands = [x for x in cands if x["canonical"] not in known][:2]
        out = dict(candidates=len(cands), admitted=[])
        for cand in cands:
            if self.left() < 20:
                break
            projs = self._applicable(cand)
            if len(projs) < ADMIT_PROJECTS:
                self.log.append(dict(step="skill_admission", canonical=cand["canonical"], edits=cand["edits"], admitted=False,
                                     why=dict(reason="fewer than 2 applicable admission projects")))
                continue
            ok, why = SK7.admit_skill(self.mem, cand, projs, work_budget=self.mem["M"]["src_work"],
                                      policy_w=self.mem.get("policy_w") if self.cohort == "Full" else None)
            if ok:
                sid = f"S{len(self.mem['de']['skills'])}"
                self.mem["de"]["skills"][sid] = dict(cand, admission={k: v for k, v in why.items() if k not in ("base_trace",)}, validated_on=[p["pid"] for p in projs])
                out["admitted"].append(sid)
            self.log.append(dict(step="skill_admission", canonical=cand["canonical"], edits=cand["edits"], support=cand["support"], novelty=cand["novelty"],
                                 from_partial=cand["from_partial"], admitted=ok, why=why))
        return out

    def _applicable(self, cand):
        pre, projs = set(cand["pre"]), []
        for _ in range(8):
            if len(projs) == ADMIT_PROJECTS or not self.admit_seeds:
                break
            s = self.admit_seeds.pop(0)
            try:
                p = build(SOURCE_SPECS[s % len(SOURCE_SPECS)], s, self.root / "adm")
                inv = P6.Inv6(p)
                ev0 = inv.run(inv.legacy)
            except Exception:                                  # noqa: BLE001
                continue
            if not pre or len(pre & ev0["features"]) / len(pre) >= 0.5:
                projs.append(p)
        return projs

    def _pool(self):
        if self.pool is None:
            self.pool = []
            for i, spec in enumerate(S.pool_specs()[:POOL_SIZE + 2]):
                if len(self.pool) == POOL_SIZE:
                    break
                try:
                    self.pool.append(build(spec, self.blk["pool"][i], self.root / "pool"))
                except RuntimeError:
                    continue
        return self.pool

    def procedure_round(self, idx):
        mem = self.mem_for_search()
        live = PR7.Live(lambda p, m: m["M"]["src_work"], wall_cap=8.0, touch=self.touch)
        pool = self._pool()
        caches = {p["pid"]: PR7.build_entry(p, live, mem) for p in pool}
        confirm = []
        while len(confirm) < CONFIRM_PER_ROUND and self.confirm_seeds:
            s = self.confirm_seeds.pop(0)
            try:
                confirm.append(build(S.pool_specs()[s % len(S.pool_specs())], s, self.root / "confirm"))
            except RuntimeError:
                continue
        conf_caches = {p["pid"]: PR7.build_entry(p, live, mem) for p in confirm}
        before = (copy.deepcopy(self.prog), copy.deepcopy(self.lib))
        prog, lib, log = PR7.learn_round(self.prog, self.lib, pool, caches, confirm, conf_caches, mem,
                                         random.Random(f"agi7-pl|{self.name}|{idx}"), cycles=self.mem["M"]["proc_cycles"],
                                         typed_pairs=self.mem["M"]["typed_pairs"], round_id=idx, touch=self.touch)
        self.touch["typed_pairs"] = self.touch.get("typed_pairs", 0) + 1
        changed = [prog, lib] != list(before)
        self.prog, self.lib = prog, lib
        retention = []
        for j, (pj, cj) in enumerate(self.round_caches):            # retention of earlier useful behaviour
            old = PR7.score(before[0], before[1], pj, cj, mem)
            new = PR7.score(prog, lib, pj, cj, mem)
            retention.append(dict(round=j, before=sum(r["correct"] for r in old.values()), after=sum(r["correct"] for r in new.values()),
                                  wrong_after=sum(r["wrong"] for r in new.values())))
        self.round_caches.append((pool, caches))
        self.log += log
        return dict(changed=changed, program=prog, library=sorted(lib), retention=retention,
                    pool_correct=sum(r["correct"] for r in PR7.score(prog, lib, pool, caches, mem).values()), confirm_n=len(confirm))

    def checkpoint(self):
        return dict(name=self.name, cohort=self.cohort, memory=self.mem, procedure=self.prog, library=self.lib, touch=self.touch, rows=self.rows,
                    cycles=self.cycles, log=self.log, n_projects=len(self.rows), wall=round(time.time() - self.t0, 1))

    def save(self):
        if self.out_path is None:
            return
        tmp = Path(str(self.out_path) + ".tmp")
        tmp.write_text(json.dumps(self.checkpoint(), default=list))
        tmp.replace(self.out_path)


# ------------------------------------------------------------------ improver comparator (campaign deferred)
def judge_edit(key, touch_edited, rows_base, rows_edit, traj_base, traj_edit):
    """Adopt M' over M only if the edited field was EXERCISED in the edited clone (it reached its triggering event),
    the two trajectories actually DIFFER, and the downstream rows pass admit7. Otherwise the edit is untested."""
    if not touch_edited.get(key):
        return False, dict(reason=f"untested: {key} never reached its triggering event")
    if traj_base == traj_edit:
        return False, dict(reason="untested: behaviourally inactive (identical trajectories)")
    return PR7.admit7(rows_base, rows_edit)


def trajectory_digest(lin):
    return digest([[r["project"], r["decision"], r["verified"], r["work"]] for r in lin.rows] + [lin.prog, sorted(lin.mem["de"]["skills"])])


def meta_compare(ckpt, edit, stream, eval_projects, n_cycles, root, deadline):
    """Two clones of a source checkpoint (M vs M with one field edited) each run n_cycles complete cycles on the SAME
    exogenous stream, then the same disjoint evaluation projects under their own procedure."""
    key, val = edit
    outs = []
    for tag, M in (("base", ckpt["memory"]["M"]), ("edit", dict(ckpt["memory"]["M"], **{key: val}))):
        mem = copy.deepcopy(ckpt["memory"])
        mem["M"] = copy.deepcopy(M)
        lin = Lineage(f"{ckpt['name']}|{tag}", ckpt["cohort"], S.block(0), root / tag, deadline, f"meta|{tag}", mem=mem, prog=ckpt["procedure"],
                      lib=ckpt["library"])
        n = 0
        for spec, seed in stream:
            if len(lin.cycles) >= n_cycles or lin.left() < 5:
                break
            lin.learn_project(spec, seed)
            n += 1
            if n % mem["M"]["batch"] == 0:
                lin.cycle(len(lin.cycles))
        rows = {}
        for p in eval_projects:
            st = PR7.investigate(p, lin.live, lin.mem_for_search(), lin.prog, lin.lib)
            o = PR7.outcome(p, st)
            rows[p["pid"]] = dict(correct=o["verified"] or (o["decision"] == "abstain" and bool(p["undecided"])), completed=o["verified"],
                                  wrong=o["wrong"], cost=dict(wall_s=PR7.cost_s(st.cost), questions=0))
        outs.append((lin, rows))
    (la, ra), (lb, rb) = outs
    ok, why = judge_edit(key, lb.touch, ra, rb, trajectory_digest(la), trajectory_digest(lb))
    return dict(edit=[key, val], adopted=ok, why=why, cycles=[len(la.cycles), len(lb.cycles)], touch_edit=lb.touch.get(key, 0))
