"""Phase 4 DE-only lineage, curriculum and improver (NOT LOCKED). Reuses the Phase 2 / 3 design (campaign2.agent_loop:
copyable seed streams, a curriculum over cells, periodic admission rounds, full-rollout meta-evaluation in which the
lineage continues from the WINNING post-rollout learner; campaign2.improver: M as a list of [statement, params] with
`first`) on the data-engineering world only.

M (the learning procedure; every statement is read by the code that runs it):
  search      localize (policy | stage_asc | stage_desc: fault-localisation order), decompose (whole | stagewise),
              max_depth, stall_frac (give-up rule), cross_engine (sqlite_first: SQLite-to-Spark screening | off)
  memory      p_priority (failure-archive retrieval weight in operator ordering), skill_match (skill retrieval
              threshold), max_skills / prune_unused (memory pruning)
  learn       lr, neg_lr (refutations), partial_lr (verified partial repairs from P)
  ambiguity   mode (pref: resolve de_accept_v2 ambiguities with learned preferences | abstain), margin
  admit       speedup (a skill must cut search runs by this fraction on 2 separate admission projects)
  curriculum  rule (frontier | uniform | easy_first | hard_first), eps
  schedule    period (projects between admission rounds)
Meta-rollouts (Full / Solved-Only only): a not-yet-tried single-parameter edit M' (the first four target localisation,
decomposition, failure-archive priority and cross-engine adaptation; then the rest of the space in a seeded order) is
compared with M by two clones that each learn 2 projects and are then evaluated on 4 rollout projects (2 Spark projects for
a cross-engine edit) from the identical seed stream; M' is adopted iff it verifies more, or as many with <= 90 % of the runs.
Cohorts: Full (failure memory on, meta on), SolvedOnly (failure memory off from t = 0, own curriculum and meta checks),
Fixed-M0 (M fixed, replays Full's learned-project sequence), Random-Proposal (matched random M and random skill proposals,
replays Full's sequence)."""
from __future__ import annotations

import copy
import json
import os
import random
import time
from pathlib import Path

from nexus.campaign2 import agent_loop as A2, improver as I
from nexus.de_phase4 import learner as L, seeds as SD, world as W

SRC_BUDGET = {"sqlite": 0.5, "spark": 2.5}
ADMIT_BUDGET, ROLL_BUDGET = 0.5, {"sqlite": 0.5, "spark": 2.0}
WS_ROOT = Path(__file__).resolve().parents[3] / "var" / "agi4_ws"

M0 = [["search", dict(L.M0_SEARCH)], ["memory", dict(L.M0_MEMORY)], ["learn", dict(L.M0_LEARN)], ["ambiguity", dict(L.M0_AMBIG)],
      ["admit", dict(speedup=0.2)], ["curriculum", dict(rule="frontier", eps=0.2)], ["schedule", dict(period=6)]]
SPACE = {"search": dict(localize=["policy", "stage_asc", "stage_desc"], decompose=["whole", "stagewise"], max_depth=[4, 6, 8],
                        stall_frac=[0.1, 0.2, 0.4], cross_engine=["sqlite_first", "off"]),
         "memory": dict(p_priority=[0.0, 0.5, 1.0, 2.0], skill_match=[0.3, 0.5, 0.7], max_skills=[6, 12, 20], prune_unused=[0, 3]),
         "learn": dict(lr=[0.5, 1.0, 2.0], neg_lr=[0.0, 0.25, 0.5, 1.0], partial_lr=[0.0, 0.5, 1.0]),
         "ambiguity": dict(mode=["pref", "abstain"], margin=[0.5, 1.0, 2.0]),
         "admit": dict(speedup=[0.1, 0.2, 0.3]),
         "curriculum": dict(rule=["frontier", "uniform", "easy_first", "hard_first"], eps=[0.1, 0.2, 0.4]),
         "schedule": dict(period=[4, 6, 8])}
PRIORITY = [("search", "localize"), ("search", "decompose"), ("memory", "p_priority"), ("search", "cross_engine")]


def m_random(rng):
    """The matched random improver: M0's statements with every parameter drawn uniformly from SPACE."""
    return [[n, {k: rng.choice(SPACE[n][k]) for k in p}] for n, p in M0]


def edits_of(M, rng, tried):
    """All single-parameter edits of M not tried yet; the 4 priority knobs first, the rest in a seeded order."""
    out = []
    for n, p in M:
        for k, vals in SPACE[n].items():
            for v in vals:
                if v != p.get(k) and (n, k, v) not in tried:
                    out.append((n, k, v))
    pri = [e for e in out if (e[0], e[1]) in PRIORITY]
    rest = [e for e in out if (e[0], e[1]) not in PRIORITY]
    rng.shuffle(pri)
    rng.shuffle(rest)
    pri.sort(key=lambda e: PRIORITY.index((e[0], e[1])))
    first = []
    for kn in PRIORITY:                                   # one edit per priority knob, then everything else
        e = next((x for x in pri if (x[0], x[1]) == kn), None)
        if e:
            first.append(e)
    return first + [e for e in pri if e not in first] + rest


def apply_edit(M, e):
    M = copy.deepcopy(M)
    for s in M:
        if s[0] == e[0]:
            s[1][e[1]] = e[2]
    return M


def _left(stream):
    return len(stream.seeds) - stream.i


def learn_cfg(M, use_failures):
    lp = I.first(M, "learn")
    return dict(lr=lp["lr"], neg_lr=lp["neg_lr"], partial_lr=lp["partial_lr"], use_failures=use_failures, max_P=80)


class Curriculum:
    def __init__(self, rng):
        self.cells = list(SD.CELLS)
        self.hist = {c: [] for c in self.cells}
        self.rng, self.k = rng, 0

    def pick(self, rule, eps):
        self.k += 1
        fams = sorted({c[0] for c in self.cells})
        rt = "spark" if self.k % 3 == 0 else "sqlite"          # one project in three on Spark
        if rule == "uniform" or self.rng.random() < eps:
            return self.rng.choice([c for c in self.cells if c[2] == rt])
        f = fams[(self.k - 1) % len(fams)]
        ks = (1, 2, 3, 4)
        rate = lambda k: (sum(self.hist[(f, k, rt)][-3:]) / len(self.hist[(f, k, rt)][-3:])) if self.hist[(f, k, rt)] else None  # noqa: E731
        if rule == "hard_first":
            return (f, max(ks), rt) if self.k % 2 else (f, self.rng.choice(ks), rt)
        if rule == "easy_first":
            for k in ks:
                r = rate(k)
                if r is None or r < 0.7:
                    return (f, k, rt)
            return (f, 4, rt)
        for k in ks:                                           # frontier: the lowest level not yet reliably solved
            r = rate(k)
            if r is None or len(self.hist[(f, k, rt)]) < 2 or r < 0.6:
                return (f, k, rt)
        return (f, 4, rt)

    def update(self, cell, score):
        self.hist.setdefault(cell, []).append(score)


class Lineage:
    def __init__(self, name, st, budget_s, out, seeds, adm_seeds, roll_seeds=None, schedule=None, meta_edits=False, use_P=True,
                 random_de=False, rng_key="", min_edits=10):
        self.name, self.st, self.budget, self.out = name, st, budget_s, Path(out)
        self.seeds = seeds if isinstance(seeds, A2.SeedStream) else A2.SeedStream(seeds)
        self.adm = adm_seeds if isinstance(adm_seeds, A2.SeedStream) else A2.SeedStream(adm_seeds)
        self.roll = roll_seeds if roll_seeds is None or isinstance(roll_seeds, A2.SeedStream) else A2.SeedStream(roll_seeds)
        self.schedule, self.meta_edits, self.use_P, self.random_de = schedule, meta_edits, use_P, random_de
        self.rng_key, self.min_edits = rng_key, min_edits
        self.rng = random.Random(f"agi4|{rng_key}")
        self.cur = Curriculum(random.Random(f"agi4-cur|{rng_key}"))
        self.rows, self.rounds, self.meta_log, self.sched_log, self.pending = [], [], [], [], []
        self.tried, self.n_since, self.n_round, self.stop_reason = set(), 0, 0, None
        self.rts = {"sqlite": W.SQLiteCode(), "spark": W.SparkCode()}
        self.ws = WS_ROOT / "src" / name.replace("|", "_")
        self.T0 = time.time()
        self.deadline = None

    def elapsed(self):
        return time.time() - self.T0

    def left(self):
        end = self.T0 + self.budget if self.deadline is None else self.deadline
        return end - time.time()

    # ---- one learning project
    def _project(self, fam, k, s, rt, sub="p"):
        return W.make_project(fam, k, s, rt, self.ws / sub)

    def episode(self, p, budget, learn=True, explore=True):
        rt = self.rts[p["runtime"]]
        rec = L.solve(p, self.st["DE"], rt, budget_s=budget, M=self.st["M"], explore=explore)
        ev = W.evaluate(p, rec["code"], rt) if rec["outcome"] == "submitted" else None
        ok = bool(ev and ev["ok"])
        if learn:
            L.learn(self.st["DE"], rec, p, learn_cfg(self.st["M"], self.use_P), ok)
            if ok and rec["edits"]:
                self.pending.append(L.skill_from(rec, p))
        return rec, ev, ok

    def step(self):
        if self.left() < SRC_BUDGET["spark"] + 1.0:
            self.stop_reason = self.stop_reason or "budget"
            return False
        if self.schedule is not None:
            if not self.schedule:
                self.stop_reason = "schedule exhausted"
                return False
            fam, k, rt, s = self.schedule.pop(0)
            cell = (fam, k, rt)
        else:
            cu = I.first(self.st["M"], "curriculum")
            cell = self.cur.pick(cu["rule"], cu["eps"])
            fam, k, rt = cell
            if _left(self.seeds) < 1:
                self.stop_reason = "seed stream exhausted"
                return False
            s = next(self.seeds)
        self.sched_log.append([fam, k, rt, s])
        p = self._project(fam, k, s, rt)
        rec, ev, ok = self.episode(p, min(SRC_BUDGET[rt], max(0.05, self.left() - 1)))
        self.cur.update(cell, 1.0 if ok else 0.0)
        self.rows.append(dict(tid=p["pid"], family=fam, k=k, runtime=rt, seed=s, outcome=rec["outcome"], status=rec.get("status"),
                              solved=ok, silent=rec["outcome"] == "submitted" and not ok, runs=rec["runs"], wall=rec["wall"],
                              edits=rec["edits"], t=round(self.elapsed(), 2), phase="source", n_P=len(self.st["DE"]["P"]),
                              n_skills=len(self.st["DE"]["skills"]), reused=[x["skill"] for x in rec["trace"] if x.get("step") == "reuse"]))
        self.n_since += 1
        if self.n_since >= I.first(self.st["M"], "schedule")["period"]:
            self.n_since = 0
            self.n_round += 1
            self.admission_round()
        return True

    # ---- skill admission and pruning
    def admission_round(self):
        de = self.st["DE"]
        cands = list(self.pending)
        self.pending = []
        if self.use_P and not self.random_de:
            cands += L.provisional_skills(de)
        if self.random_de:
            cands = [L.random_skill(self.rng) for _ in range(max(1, len(cands)))]
        known = {(tuple(v["ops"]), tuple(v["pre"])) for v in de["skills"].values()}
        cands = [c for c in cands if (tuple(c["ops"]), tuple(c["pre"])) not in known][:3]
        log = []
        if cands and _left(self.adm) >= 2 and self.left() > (1 + len(cands)) * 2 * ADMIT_BUDGET + 2:
            projs = []
            for _ in range(2):
                s = next(self.adm)
                projs.append(self._project(SD.SOURCE_FAMS[s % 6], s // 6 % 3 + 1, s, "sqlite", "adm"))

            def judge(state_de):
                out = []
                for p in projs:
                    rec = L.solve(p, state_de, self.rts["sqlite"], budget_s=ADMIT_BUDGET, M=self.st["M"], explore=False)
                    ev = W.evaluate(p, rec["code"], self.rts["sqlite"]) if rec["outcome"] == "submitted" else None
                    out.append(dict(solved=bool(ev and ev["ok"]), silent=rec["outcome"] == "submitted" and not (ev and ev["ok"]),
                                    runs=rec["runs"]))
                return out
            base = judge(copy.deepcopy(de))
            sp = I.first(self.st["M"], "admit")["speedup"]
            for sk in cands:
                trial = copy.deepcopy(de)
                trial["skills"]["tmp"] = dict(sk, match=None)
                res = judge(trial)
                sb, sr = sum(r["solved"] for r in base), sum(r["solved"] for r in res)
                rb, rr = sum(r["runs"] for r in base), sum(r["runs"] for r in res)
                ok = (sum(r["silent"] for r in res) <= sum(r["silent"] for r in base) and sr >= sb and (sr > sb or rr <= (1 - sp) * rb))
                if ok:
                    sid = f"S{de['next_id']}"
                    de["next_id"] += 1
                    de["skills"][sid] = dict(sk, validated_on=[p["pid"] for p in projs], admission=dict(runs=[rb, rr], solved=[sb, sr]),
                                             birth_round=self.n_round, uses=0)
                log.append(dict(ops=sk["ops"], pre=sk["pre"], kind=sk.get("kind"), tier=sk.get("tier", "validated"), ok=ok,
                                runs=[rb, rr], solved=[sb, sr], provenance=sk.get("provenance")))
        mem = I.first(self.st["M"], "memory")
        if mem["prune_unused"]:
            for k in [k for k, v in de["skills"].items() if v.get("uses", 0) == 0 and self.n_round - v.get("birth_round", 0) >= mem["prune_unused"]]:
                del de["skills"][k]
        for k in list(de["skills"])[:-mem["max_skills"]] if len(de["skills"]) > mem["max_skills"] else []:
            del de["skills"][k]
        self.rounds.append(dict(round=self.n_round, kind="admission", proposals=log, n_skills=len(de["skills"]), n_P=len(de["P"])))

    # ---- improver: full-rollout comparison of M and one edited M'
    def _clone(self, M, tag):
        c = Lineage(f"{self.name}|{tag}", copy.deepcopy(self.st), 1e9, self.out, self.seeds.clone(), self.adm.clone(),
                    use_P=self.use_P, random_de=self.random_de, rng_key=f"{self.rng_key}|roll{len(self.meta_log)}")
        c.st["M"] = copy.deepcopy(M)
        c.cur = copy.deepcopy(self.cur)
        c.n_round, c.n_since, c.rts = self.n_round, self.n_since, self.rts
        return c

    def meta_rollout(self):
        if self.roll is None:
            return False
        e = next((x for x in edits_of(self.st["M"], random.Random(f"{self.rng_key}|edits|{len(self.meta_log)}"), self.tried)), None)
        if e is None:
            return False
        spark = e[1] == "cross_engine"
        need = 2 * (2 * SRC_BUDGET["sqlite"] + (2 * ROLL_BUDGET["spark"] if spark else 4 * ROLL_BUDGET["sqlite"])) + 2
        if self.left() < need or _left(self.roll) < 6:
            return False
        self.tried.add(e)
        M2 = apply_edit(self.st["M"], e)
        roll_learn = [next(self.roll) for _ in range(2)]
        ev_projects = []
        for _ in range(2 if spark else 4):
            s = next(self.roll)
            ev_projects.append(self._project(SD.SOURCE_FAMS[s % 6], s // 6 % 3 + 1, s, "spark" if spark else "sqlite", "roll"))
        outs = []
        for tag, MM in (("current", self.st["M"]), ("edited", M2)):
            c = self._clone(MM, tag)
            c.schedule = [(SD.SOURCE_FAMS[s % 6], s // 6 % 4 + 1, "sqlite", s) for s in roll_learn]
            while c.step():
                pass
            res = []
            for p in ev_projects:
                rec, ev, ok = c.episode(p, ROLL_BUDGET[p["runtime"]], learn=False, explore=False)
                res.append(dict(solved=ok, silent=rec["outcome"] == "submitted" and not ok, runs=rec["runs"]))
            outs.append((c, dict(solved=sum(r["solved"] for r in res), silent=sum(r["silent"] for r in res), runs=sum(r["runs"] for r in res))))
        (ca, ra), (cb, rb) = outs
        adopted = rb["silent"] <= ra["silent"] and (rb["solved"] > ra["solved"] or (rb["solved"] == ra["solved"] and rb["runs"] <= 0.9 * ra["runs"]))
        win = cb if adopted else ca
        self.meta_log.append(dict(round=self.n_round, edit=list(e), current=ra, edited=rb, adopted=adopted, eval_projects=[p["pid"] for p in ev_projects],
                                  spark_eval=spark))
        self.st, self.cur, self.pending = win.st, win.cur, win.pending + self.pending
        self.rows += [dict(r, phase=f"rollout:{'edited' if adopted else 'current'}") for r in win.rows]
        self.rounds += win.rounds
        self.sched_log += [["rollout"] + x for x in win.sched_log]
        return True

    def run(self):
        done = 0
        while True:
            if self.meta_edits and self.n_round > done and len(self.meta_log) < 40:
                done = self.n_round
                # front-load: at least min_edits distinct edits are evaluated (two rollouts per round until reached)
                for _ in range(2 if len(self.meta_log) < self.min_edits else 1):
                    if not self.meta_rollout():
                        break
            if not self.step():
                break
            if len(self.rows) % 5 == 0:
                self.save()
        self.save(final=True)
        return self

    def save(self, final=False):
        self.out.mkdir(parents=True, exist_ok=True)
        doc = dict(name=self.name, final=final, stop_reason=self.stop_reason, elapsed=round(self.elapsed(), 2), state=self.st,
                   schedule=[x[1:] if x[0] == "rollout" else x for x in self.sched_log], all_projects=self.sched_log, rows=self.rows,
                   rounds=self.rounds, meta_log=self.meta_log, use_P=self.use_P, M_final=self.st["M"])
        p = self.out / f"{self.name}.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=0, default=list))
        os.replace(tmp, p)
