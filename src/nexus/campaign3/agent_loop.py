"""Phase 3 lineage (NOT LOCKED): the Phase 2 lineage (campaign2.agent_loop.Lineage: provisional archive P, graded
admission, locked acceptance barrier, full-rollout meta-evaluation) extended - not rebuilt - with
  * the real-pipeline DE world in the same curriculum: cells = 8 learning world families x 4 levels + DE source families
    G1-G4 x 2 levels (SQLite during source learning; Spark is used in the Stage 1 cycle and Stage 4);
  * the DE learner's memory state["DE"] (pi_de weights, admitted skills L_de, provisional records P_de), updated on the
    same experience / admission / M interfaces: a candidate skill is admitted only if it lowers the search cost (runtime
    executions) on separate DE admission projects by >= M.admit.speedup without fewer solves or a new silent error;
    skills built only from P (partial evidence) are provisional and need that positive evidence;
  * the Phase 2 crowding-out fix: a world proposal is 'provisional' only when NO solved source program supports it;
  * source tasks get a 1.5 s CPU cap (deeper source search, the Phase 2 recommendation); admission, rollout evaluation and
    Stage 4 keep the 0.6 s cap.
Solved-Only cohort: the world archive P is off and the DE learner ignores failures (no refutations, no partial records)."""
from __future__ import annotations

import copy
import random
import time
from pathlib import Path

from nexus.campaign2 import agent_loop as A2, improver as I
from nexus.campaign2 import substrate as S
from nexus.campaign3 import seeds as SD, de_world as DW, de_learner as DL
from nexus.campaign3.worlds3 import make_task3

SRC_CAP_S, EVAL_CAP_S = 0.6, 0.6     # 1.5 s bought <= 1 cost level and no extra B/D discoverability (agi3_bd_audit)
DE_SRC_S, DE_ADMIT_S = 1.0, 0.6
WS_ROOT = Path(__file__).resolve().parents[3] / "var" / "agi3_ws"          # worktree-local, git-ignored


def task_of(world, family, level, seed):
    role = SD.role_of(world, family)
    return make_task3(world, family, level, seed, role, SD.partners_for(world, family, role))


class Curriculum3(A2.Curriculum):
    def __init__(self, rng):
        super().__init__(rng)
        self.cells = self.cells + [("DE", f, lv) for f in SD.DE_SOURCE for lv in (1, 2)]
        self.hist = {c: [] for c in self.cells}


M3 = copy.deepcopy(I.M0) + [["de_policy", dict(lr=1.0, neg_lr=0.5)]]
I.SPACE["de_policy"] = dict(lr=[0.5, 1.0, 2.0], neg_lr=[0.0, 0.25, 0.5, 1.0])


def m_random3(rng):
    M = I.m_random(rng)
    return M + [["de_policy", dict(lr=rng.choice(I.SPACE["de_policy"]["lr"]), neg_lr=rng.choice(I.SPACE["de_policy"]["neg_lr"]))]]


def de_cfg(M, use_failures):
    d = I.first(M, "de_policy", None) or dict(lr=1.0, neg_lr=0.5)
    return dict(lr=d.get("lr", 1.0), neg_lr=d.get("neg_lr", 0.5), use_failures=use_failures, max_P=60)


class Lineage3(A2.Lineage):
    def __init__(self, *a, de_seeds=None, de_adm_seeds=None, random_de=False, **k):
        super().__init__(*a, **k)
        self.cur = Curriculum3(random.Random(f"agi3-cur|{self.rng_key}"))
        self.st.setdefault("DE", DL.empty_de())
        self.de_seeds = de_seeds if de_seeds is None or isinstance(de_seeds, A2.SeedStream) else A2.SeedStream(de_seeds)
        self.de_adm = de_adm_seeds if de_adm_seeds is None or isinstance(de_adm_seeds, A2.SeedStream) else A2.SeedStream(de_adm_seeds)
        self.random_de = random_de
        self.de_pending, self._clones = [], []
        self.rt = DW.SQLiteRuntime()
        self.ws = WS_ROOT / "src" / self.name.replace("|", "_")

    # ---- tasks
    def _adm_task(self):
        s = next(self.adm_seeds)
        w, f = SD.ADMIT[s % len(SD.ADMIT)]
        return task_of(w, f, (s % len(SD.ADMIT) + s // len(SD.ADMIT)) % 2 + 1, s)

    def _next_task(self):
        if self.schedule is not None:
            if not self.schedule:
                return None, None
            w, f, lv, s = self.schedule.pop(0)
            return (w, f, lv), (("DE", f, lv, s) if w == "DE" else task_of(w, f, lv, s))
        cur = I.first(self.st["M"], "curriculum")
        cell = self.cur.pick(cur["rule"], cur["eps"])
        if cell[0] == "DE":
            return cell, ("DE", cell[1], cell[2], next(self.de_seeds))
        return cell, task_of(*cell, next(self.task_seeds))

    def _eval_set(self, st, tasks):
        old, self.cap = self.cap, EVAL_CAP_S
        try:
            return super()._eval_set(st, tasks)
        finally:
            self.cap = old

    # ---- the Phase 2 crowding-out fix
    def _proposals(self, M, st, rng):
        props = super()._proposals(M, st, rng)
        solved = {e["tid"] for e in self.archive}
        for c in props:
            if c.get("kind") in ("L", "R") and c.get("tier") == "provisional" and any(t in solved for t in c["support"]):
                c["tier"] = "validated"            # supported by >= 1 solved program: not provisional
        return props

    # ---- one step (world task or DE project)
    def step(self):
        if self.left() < self.cap + 1.0:
            self.stop_reason = self.stop_reason or "budget"
            return False
        cell, task = self._next_task()
        if task is None:
            self.stop_reason = "schedule exhausted"
            return False
        if isinstance(task, tuple) and task[0] == "DE":
            self._de_step(cell, task)
        else:
            self.sched_log.append([task.world, task.family, task.level, task.seed])
            r = A2.safe_episode(task, self.st, self.cap, want_partials=self.use_P)
            self.cur.update(cell, 1.0 if r["solved"] else 0.0)
            if r["solved"]:
                for n in r["used_items"]:
                    tab = self.st["L"] if n[0] == "L" else self.st["R"]
                    if n[2:] in tab:
                        tab[n[2:]]["uses"].append(task.tid)
                        tab[n[2:]]["util"] += 1
                self.archive.append(dict(tid=task.tid, sig=list(task.mech.sig), prog=r["_ast"], origin=r["origin"]))
                self.archive = self.archive[-A2.BUFFER:]
            else:
                self._archive_partials(task, r)
            self.rows.append({k: v for k, v in r.items() if k not in ("_ast", "_partials")} |
                             dict(t=round(self.elapsed(), 1), phase="source", n_partials=len(r["_partials"])))
        self.n_since += 1
        if self.n_since >= I.first(self.st["M"], "schedule")["period"]:
            if self.proposal_round():
                self.n_since = 0
            self.de_round()
        return True

    def _de_project(self, fam, lv, s, runtime="sqlite"):
        return DW.make_project(fam, lv, s, runtime, self.ws)

    def _de_step(self, cell, task):
        _, fam, lv, s = task
        self.sched_log.append(["DE", fam, lv, s])
        p = self._de_project(fam, lv, s)
        rec = DL.solve(p, self.st["DE"], self.rt, budget_s=min(DE_SRC_S, max(0.05, self.left() - 1)))
        ev = DW.evaluate(p, rec["spec"], self.rt) if rec["solved_visible"] else None
        ok = bool(ev and ev["ok"])
        DL.learn(self.st["DE"], rec, p, de_cfg(self.st["M"], self.use_P), ok)
        if ok and rec["edits"]:
            self.de_pending.append(DL.skill_from(rec, p))
        self.cur.update(cell, 1.0 if ok else 0.0)
        self.rows.append(dict(tid=p["pid"], world="DE", family=fam, level=lv, seed=s, role="learn", outcome="submitted" if
                              rec["solved_visible"] else "abstain", solved=ok, silent=rec["solved_visible"] and not ok,
                              runs=rec["runs"], cpu_s=rec["wall"], edits=rec["edits"], graded=rec["start"]["score"],
                              t=round(self.elapsed(), 1), phase="source", queries=0, used_items=[]))

    def de_round(self):
        """DE skill admission: pending verified skills (+ provisional ones from P_de in failure-using cohorts, or random
        skills in the Random-Proposal cohort) are judged on 2 separate DE admission projects by search cost."""
        de = self.st["DE"]
        cands = list(self.de_pending)
        self.de_pending = []
        if self.use_P and not self.random_de:
            cands += DL.provisional_skills(de)
        if self.random_de:
            cands = [DL.random_skill(self.rng) for _ in range(max(1, len(cands)))]
        cands = cands[:3]
        if not cands or self.de_adm is None or self.left() < 2 * (1 + len(cands)) * DE_ADMIT_S + 1:
            return
        adm = I.first(self.st["M"], "admit")
        projs = []
        for _ in range(2):
            s = next(self.de_adm)
            projs.append(self._de_project(SD.DE_SOURCE[s % 4], s // 4 % 2 + 1, s))

        def judge(state_de):
            out = []
            for p in projs:
                rec = DL.solve(p, state_de, self.rt, budget_s=DE_ADMIT_S)
                ev = DW.evaluate(p, rec["spec"], self.rt) if rec["solved_visible"] else None
                out.append(dict(solved=bool(ev and ev["ok"]), silent=rec["solved_visible"] and not (ev and ev["ok"]), runs=rec["runs"]))
            return out
        base = judge(de)
        log = []
        for sk in cands:
            key = (tuple(sk["ops"]), tuple(sk["pre"]))
            if any((tuple(v["ops"]), tuple(v["pre"])) == key for v in de["skills"].values()):
                continue
            trial = copy.deepcopy(de)
            trial["skills"]["tmp"] = sk
            res = judge(trial)
            sb, sr = sum(r["solved"] for r in base), sum(r["solved"] for r in res)
            rb, rr = sum(r["runs"] for r in base), sum(r["runs"] for r in res)
            ok = (sum(r["silent"] for r in res) <= sum(r["silent"] for r in base) and sr >= sb and
                  (sr > sb or rr <= (1 - adm["speedup"]) * rb))
            if ok:
                sid = f"S{de['next_id']}"
                de["next_id"] += 1
                de["skills"][sid] = dict(sk, validated_on=[p["pid"] for p in projs], admission=dict(d_solved=sr - sb, runs=[rb, rr]),
                                         birth_round=self.n_round, birth_lineage=self.name)
            log.append(dict(ops=sk["ops"], pre=sk["pre"], tier=sk.get("tier", "validated"), ok=ok, runs=[rb, rr],
                            solved=[sb, sr], provenance=sk.get("provenance")))
        if len(de["skills"]) > 12:                             # bounded memory: keep the newest 12
            for k in list(de["skills"])[:-12]:
                del de["skills"][k]
        self.rounds.append(dict(round=self.n_round, kind="de_admission", lineage=self.name, projects=[p["pid"] for p in projs],
                                proposals=log, n_skills=len(de["skills"]), n_P_de=len(de["P"])))

    def _clone(self, name, M, k):
        c = Lineage3(name, copy.deepcopy(self.st), 1e9, self.out, self.task_seeds.clone(), self.adm_seeds.clone(),
                     rng_key=f"{self.rng_key}|roll{k}", use_P=self.use_P, cap_s=self.cap,
                     de_seeds=self.de_seeds.clone() if self.de_seeds else None,
                     de_adm_seeds=self.de_adm.clone() if self.de_adm else None, random_de=self.random_de)
        c.st["M"] = copy.deepcopy(M)
        c.archive = copy.deepcopy(self.archive)
        c.cur = copy.deepcopy(self.cur)
        c.n_round, c.n_since = self.n_round, self.n_since
        self._clones.append(c)
        return c

    def meta_rollout(self):
        self._clones = []
        ok = super().meta_rollout()
        win = next((c for c in self._clones if c.st is self.st), None)
        if win is not None:                                   # the winner's DE streams / pending skills continue the lineage
            self.de_seeds, self.de_adm, self.de_pending = win.de_seeds, win.de_adm, win.de_pending
        self._clones = []
        return ok


# the rollout evaluation tasks of the Phase 2 harness use campaign2's task_of; point it at Phase 3 tasks
A2.task_of = task_of
