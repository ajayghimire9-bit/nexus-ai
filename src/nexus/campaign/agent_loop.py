"""The single autonomous agent loop shared by every world, cohort and arm (NOT LOCKED).

Per task (solve + learn):
  1 observe the labelled training pairs;               2 keep every consistent hypothesis (no predicted internal state
  3 pi picks the representation (R features by          is ever used as supervision; hypotheses are only filtered by
    utility) and search settings (costs, lambda cap)     oracle labels / simulator feedback on labelled inputs);
  4 epistemic decision: after the margin, measure disagreement among consistent hypotheses on the learner's own
    unlabelled probe inputs (prior-weighted entropy = expected information of a query); query the most informative
    probe while disagreement remains and budget allows, otherwise keep searching / abstain;
  5 construct the candidate = lowest-cost consistent hypothesis with no remaining disagreement;
  6 verify (independent world verifier; on SOURCE tasks only, its pass / fail is the training signal);
  7 revise: queried labels filter hypotheses; if none survives, search continues;
  8 propose Delta L / Delta R (improver.py) from verified solutions;   9 update pi; Full cohort proposes Delta M;
 10 admit proposals only by their measured effect on separate source-admission tasks; prune to bounded memory;
 11 reset: every per-task cache, hypothesis and concrete solution is discarded (the improver's bounded buffer of
    verified source solutions is a learning working set, never consulted by the solver and never saved in an endpoint).
At evaluation time only steps 1-7 run, from the frozen state restored before every episode."""
from __future__ import annotations

import copy
import json
import math
import os
import random
import time
from pathlib import Path

from nexus.campaign import improver as I, state as ST, substrate as S
from nexus.campaign import seeds as SD
from nexus.campaign.worlds import make_task, verify, FAMILIES

CAP_S = 0.6          # per-task CPU cap (source, admission, meta and evaluation alike)
MAX_COST = 18
BUFFER = 40


# ------------------------------------------------------------------ one task
def _mined_consts(view):
    cnt = {}

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, int):
            if v not in S.BASE_CONSTS and abs(v) <= 20:
                cnt[v] = cnt.get(v, 0) + 1
        elif isinstance(v, tuple):
            for z in v:
                walk(z)
    for _, y in view.train:
        walk(y)
    mined = [v for v, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
    if view.draft is not None:
        mined += [m[1] for m in S.nodes(view.draft) if m[0] == "c" and m[1] not in S.BASE_CONSTS and m[1] not in mined]
    return tuple(S.BASE_CONSTS) + tuple(mined)


def _atoms(v, out):
    if isinstance(v, tuple):
        for z in v:
            _atoms(z, out)
    else:
        out.add(v)
    return out


def _draft_extra(draft):
    if draft is None:
        return []
    out, seen = [], set()
    for sub, c in I._subtrees(draft, "top"):
        if I._free_inputs(sub) and any(m[0] == "a" for m in I._free_inputs(sub)):
            continue
        if (S.to_src(sub), c) not in seen:
            seen.add((S.to_src(sub), c))
            out.append((sub, c))
    return out


def solve(view, st, cap_s=CAP_S, rng=None, costs=None):
    """Steps 1-7 on one task. Returns the record (the program, if submitted, is an AST over st's L / R)."""
    pi = st["pi"]
    t0 = time.process_time()
    rng = rng or random.Random(0)
    probes, seen = [], {repr(x) for x, _ in view.train}
    for _ in range(pi["n_probes"] * 4):
        if len(probes) >= pi["n_probes"]:
            break
        x = view.sample(rng)
        if repr(x) not in seen:
            seen.add(repr(x))
            probes.append(x)
    xs = [x for x, _ in view.train] + probes
    labels = {i: y for i, (_, y) in enumerate(view.train)}
    seen_vals = set()
    for x, _ in view.train:
        _atoms(x, seen_vals)
    novelty = [len(_atoms(x, set()) - seen_vals) for x in xs]     # input values never seen in training

    def consistent(vals):
        for i, y in labels.items():
            if not view.ok(xs[i], y, vals[i]):
                return False
        return True

    macros, feats = ST.macros_of(st), ST.feats_of(st, pi["feat_k"])
    srch = S.Search(xs, view.sig, view.out, costs or ST.costs_of(st), consistent, macros=macros, feats=feats,
                    extra=_draft_extra(view.draft), consts=_mined_consts(view), deadline=t0 + cap_s, lam_max=pi["lam_max"])
    rec = dict(outcome=None, prog=None, cost=None, level=0, first_hit=None, probes=len(probes), confirmed=0)

    def decide():
        while True:
            H = [h for h in srch.hyps if consistent(h[2])]
            srch.hyps = H
            if not H:
                return None
            best_j, best_e = None, 0.0
            for j in range(len(xs)):
                if j in labels:
                    continue
                dist = {}
                for c, _, vals in H:
                    k = repr(vals[j])
                    dist[k] = dist.get(k, 0.0) + 2.0 ** -c
                if len(dist) < 2:
                    continue
                z = sum(dist.values())
                e = -sum(p / z * math.log2(p / z) for p in dist.values())
                if e > best_e + 1e-12:
                    best_j, best_e = j, e
                    if pi.get("qsel") == "first":
                        break
            if best_j is None:
                # confirmation experiment: before committing, spend up to pi.confirm_q queries on the unlabelled probes
                # with the most input values unseen in training, and check the prediction (a miss refutes -> re-search)
                unl = sorted((j for j in range(len(xs)) if j not in labels), key=lambda j: (-novelty[j], j))
                if rec["confirmed"] < pi.get("confirm_q", 0) and unl and view.queries < view.q_budget:
                    j = unl[0]
                    labels[j] = view.query(xs[j])
                    rec["confirmed"] += 1
                    continue
                # chance-fit (Occam / multiple-comparisons) bound: expected number of enumerated programs that would fit
                # every label by chance = candidates searched x prod_i (empirical frequency of label i's value)
                lv = [repr(y) for y in labels.values()]
                chance = srch.n_cands * math.prod(lv.count(v) / len(lv) for v in lv)
                rec["chance_fit"] = chance
                if chance > pi.get("fit_alpha", 0.1):
                    if unl and view.queries < view.q_budget:
                        labels[unl[0]] = view.query(xs[unl[0]])
                        continue
                    rec.update(outcome="abstain_evidence", n_hyps=len(H))
                    return rec
                rec.update(outcome="submitted", prog=H[0][1], cost=H[0][0], n_hyps=len(H))
                return rec
            if view.queries < view.q_budget:
                labels[best_j] = view.query(xs[best_j])
                continue
            rec.update(outcome="abstain_ambiguous", n_hyps=len(H))
            return rec

    try:
        for c in srch.levels(MAX_COST):
            rec["level"] = c
            srch.hyps = [h for h in srch.hyps if consistent(h[2])]
            if srch.hyps and rec["first_hit"] is None:
                rec["first_hit"] = c
            if rec["first_hit"] is not None and c >= rec["first_hit"] + pi["margin"]:
                if decide():
                    break
                rec["first_hit"] = None
    except S.Deadline:
        pass
    if rec["outcome"] is None:
        # commitment requires the competitor search (pi margin) to have completed; a deadline first means abstain
        n_h = len([h for h in srch.hyps if consistent(h[2])])
        rec.update(outcome="abstain_timeout" if time.process_time() >= t0 + cap_s else "abstain_nohyp", n_hyps=n_h)
    rec.update(queries=view.queries, cpu_s=round(time.process_time() - t0, 4), n_cands=srch.n_cands)
    return rec


def episode(task, st, cap_s=CAP_S, costs=None):
    """Solve one task from state st and verify the result independently (no state change)."""
    view = task.view()
    rec = solve(view, st, cap_s, random.Random(f"probe|{task.tid}"), costs=costs)
    if rec["prog"] is not None:
        g = S.compile_ast(rec["prog"], ST.macros_of(st), ST.feats_of(st))
        v = verify(task, lambda x: g(tuple(x), (), ()))
    else:
        v = None
    ok = bool(v and v["ok"])
    used = [n for n in S.prod_names(rec["prog"]) if n[:2] in ("L:", "R:")] if rec["prog"] is not None else []
    return dict(tid=task.tid, world=task.world, family=task.family, level=task.level, seed=task.seed, role=task.role,
                outcome=rec["outcome"], solved=ok, silent=rec["outcome"] == "submitted" and not ok, verify=v,
                queries=rec["queries"], q_budget=task.q_budget, cpu_s=rec["cpu_s"], n_cands=rec["n_cands"],
                level_reached=rec["level"], prog=S.to_src(rec["prog"]) if rec["prog"] is not None else None,
                prog_size=S.size(rec["prog"]) if rec["prog"] is not None else None, used_items=used,
                _ast=rec["prog"])


def safe_episode(task, st, cap_s=CAP_S):
    """episode(), with an unexpected exception recorded as an 'error' outcome (unsolved, not silent) instead of a crash."""
    try:
        return episode(task, st, cap_s)
    except Exception as e:                                       # noqa: BLE001
        return dict(tid=task.tid, world=task.world, family=task.family, level=task.level, seed=task.seed, role=task.role,
                    outcome="error:" + repr(e)[:120], solved=False, silent=False, verify=None, queries=0,
                    q_budget=task.q_budget, cpu_s=0.0, n_cands=0, level_reached=0, prog=None, prog_size=None, used_items=[],
                    _ast=None)


# ------------------------------------------------------------------ tasks for learning
def task_of(world, family, level, seed):
    return make_task(world, family, level, seed, SD.role_of(world, family), SD.partners_for(world, family,
                                                                                            SD.role_of(world, family)))


class Curriculum:
    """Task choice over the learning cells (8 learning families x 4 levels) by M's curriculum rule."""

    def __init__(self, rng):
        self.cells = [(w, f, lv) for (w, f) in SD.LEARN for lv in (1, 2, 3, 4)]
        self.hist = {c: [] for c in self.cells}
        self.rng, self.k = rng, 0

    def pick(self, rule, eps):
        self.k += 1
        if rule == "round_robin":
            return self.cells[(self.k - 1) % len(self.cells)]
        if self.rng.random() < eps:
            return self.rng.choice(self.cells)
        if rule == "frontier":
            fams = sorted({(w, f) for w, f, _ in self.cells})
            w, f = fams[(self.k - 1) % len(fams)]
            for lv in (1, 2, 3, 4):
                h = self.hist[(w, f, lv)]
                if len(h) < 2 or sum(h[-3:]) / len(h[-3:]) < 0.6:
                    return (w, f, lv)
            return (w, f, 4)

        def value(c):
            h = self.hist[c]
            n = len(h)
            lp = abs(sum(h[-2:]) / max(1, len(h[-2:])) - sum(h[-4:-2]) / max(1, len(h[-4:-2]))) if n >= 3 else 0.0
            rate = sum(h) / n if n else 0.5
            gate = 0.0 if c[2] == 1 or any(self.hist[(c[0], c[1], c[2] - 1)]) else -0.4
            return 0.6 / math.sqrt(1 + n) + lp + (0.3 if 0 < rate < 1 else 0.0) + gate + self.rng.random() * 1e-3
        return max(self.cells, key=value)

    def update(self, cell, solved):
        self.hist[cell].append(1 if solved else 0)


# ------------------------------------------------------------------ the lineage (source learning / meta clones)
class Lineage:
    """A learning run: cohort in {Full, Fixed-M0, Random-Proposal, Meta-*}; budget in charged (wall) seconds."""

    def __init__(self, name, st, budget_s, out_dir, task_seeds, adm_seeds, rng_key, schedule=None, meta_edits=False,
                 cap_s=CAP_S, log=print):
        self.name, self.st, self.budget, self.out = name, st, budget_s, Path(out_dir)
        self.task_seeds, self.adm_seeds = iter(task_seeds), iter(adm_seeds)
        self.rng = random.Random(f"agi-lineage|{rng_key}")
        self.schedule, self.meta_edits, self.cap = schedule, meta_edits, cap_s
        self.T0, self.C0 = time.time(), time.process_time()
        self.archive, self.rows, self.rounds, self.meta_log, self.sched_log = [], [], [], [], []
        self.cur = Curriculum(random.Random(f"agi-cur|{rng_key}"))
        self.log = log
        self.n_round = 0
        self.stop_reason = None

    def elapsed(self):
        return max(time.time() - self.T0, time.process_time() - self.C0)

    def left(self):
        return self.budget - self.elapsed()

    # ---- steps 8-10
    def _proposals(self, M, archive, st, rng):
        ex_L = {S.to_src(m["body"]) for m in st["L"].values()}
        ex_R = {S.to_src(r["body"]) for r in st["R"].values()}
        props = []
        for p in I.stmt(M, "propose_L"):
            for c in I.propose_L(archive, st, p, rng, ex_L):
                if S.to_src(c["body"]) not in ex_L:
                    ex_L.add(S.to_src(c["body"]))
                    props.append(c)
        for p in I.stmt(M, "propose_R"):
            for c in I.propose_R(archive, st, p, rng, ex_R):
                if S.to_src(c["body"]) not in ex_R:
                    ex_R.add(S.to_src(c["body"]))
                    props.append(c)
        rw = I.first(M, "reweight")
        if rw:
            pi, why = I.reweight(archive, st, rw, rng)
            if pi is not None:
                props.append(dict(kind="pi_costs", pi=pi, why=why))
        tn = I.first(M, "tune")
        if tn:
            pi, why = I.tune(st, tn, rng, self.n_round)
            props.append(dict(kind="pi_params", pi=pi, why=why))
        return props

    def _apply(self, st, prop, birth=None):
        st = copy.deepcopy(st)
        if prop["kind"] in ("L", "R"):
            iid = f"{'L' if prop['kind'] == 'L' else 'R'}{st['next_id']}"
            st["next_id"] += 1
            item = dict(body=prop["body"], method=prop["method"], mdl=prop["mdl"], support=prop["support"],
                        birth_task=(prop["support"] or [None])[0], birth_round=self.n_round, birth_lineage=self.name,
                        size=S.size(prop["body"]), src=S.to_src(prop["body"]), uses=[], util=0)
            if prop["kind"] == "L":
                item.update(holes=tuple(prop["holes"]), out=prop["out"])
                st["L"][iid] = item
            else:
                item.update(tin=prop["tin"], tout=prop["tout"])
                st["R"][iid] = item
            return st, iid
        if prop["kind"] == "pi_costs":
            st["pi"]["costs"] = copy.deepcopy(prop["pi"]["costs"])
        else:
            for k in I.TUNE:
                st["pi"][k] = prop["pi"][k]
        return st, prop["kind"]

    def _eval_set(self, st, tasks):
        res = []
        for t in tasks:
            r = safe_episode(t, st, self.cap)
            res.append(dict(tid=t.tid, solved=r["solved"], silent=r["silent"], cpu=r["cpu_s"]))
        return res

    def _admit(self, base, res, rule, kind="pi_costs"):
        sb, sr = sum(r["solved"] for r in base), sum(r["solved"] for r in res)
        if sum(r["silent"] for r in res) > sum(r["silent"] for r in base):
            return False, dict(d_solved=sr - sb, why="new silent error")
        both = [(a["cpu"], b["cpu"]) for a, b in zip(base, res) if a["solved"] and b["solved"]]
        ratio = (sum(b for _, b in both) / max(1e-9, sum(a for a, _ in both))) if both else None
        info = dict(d_solved=sr - sb, cpu_ratio=None if ratio is None else round(ratio, 3))
        if sr > sb:
            return True, info
        if sr < sb:
            info["why"] = "fewer solves"
            return False, info
        if ratio is None:
            # no commonly solved admission task = no evidence either way. A global pi change is then not admitted; an
            # additive L / R item (MDL-supported, bounded memory, pruned by utility) is, if M's admit.neutral allows it
            ok = kind in ("L", "R") and rule["neutral"]
            info["why"] = "uninformative" + (": additive item admitted (neutral)" if ok else ": not admitted")
            return ok, info
        if rule["neutral"]:
            return ratio <= 1 + rule["speedup"], info
        return ratio <= 1 - rule["speedup"], info

    def _round_cost(self, n_props, n_tasks):
        return (1 + n_props) * n_tasks * (self.cap + 0.15)

    def proposal_round(self):
        st, M = self.st, self.st["M"]
        adm = I.first(M, "admit")
        tasks = [self._adm_task() for _ in range(adm["n_tasks"])]
        alt = None
        if self.meta_edits and self.n_round % I.first(M, "schedule")["meta_period"] == 0:
            M2, edit = I.m_mutate(M, self.rng)
            r2 = random.Random()
            r2.setstate(self.rng.getstate())         # the edited M sees the identical random stream: differences = M only
            props2 = self._proposals(M2, self.archive, st, r2)
            alt = (M2, edit, props2)
        props = self._proposals(M, self.archive, st, self.rng)
        n_all = len(props) + (len(alt[2]) if alt else 0)
        if self.left() < self._round_cost(n_all, len(tasks)) + 2:
            return False
        base = self._eval_set(st, tasks)
        cache = {}

        def judge(plist):
            out = []
            for p in plist:
                key = json.dumps(ST.to_json({k: v for k, v in p.items() if k not in ("support", "mdl")}), sort_keys=True)
                if key not in cache:
                    st2, _ = self._apply(st, p)
                    res = self._eval_set(st2, tasks)
                    cache[key] = (res,) + self._admit(base, res, adm, p["kind"])
                res, ok, info = cache[key]
                out.append((p, ok, info, res))
            return out

        def gain(judged):
            g = 0.0
            for p, ok, info, res in judged:
                if ok:
                    g += 10 * info["d_solved"] + (1 - info["cpu_ratio"] if info.get("cpu_ratio") else 0.0)
            return g

        J = judge(props)
        chosen, meta = J, None
        if alt:
            J2 = judge(alt[2])
            g1, g2 = gain(J), gain(J2)
            adopted = g2 > g1
            meta = dict(round=self.n_round, edit=alt[1], gain_current=round(g1, 3), gain_edited=round(g2, 3), adopted=adopted)
            if adopted:
                chosen = J2
                self.st["M"] = alt[0]
            self.meta_log.append(meta)
        admitted = []
        for p, ok, info, res in chosen:
            entry = dict(kind=p["kind"], ok=ok, info=info, src=S.to_src(p["body"]) if "body" in p else p.get("why"),
                         method=p.get("method"), mdl=p.get("mdl"), support=p.get("support"))
            if ok:
                self.st, iid = self._apply(self.st, p)
                entry["id"] = iid
                if iid[:1] in ("L", "R") and iid not in ("pi_costs", "pi_params"):
                    tab = self.st["L"] if p["kind"] == "L" else self.st["R"]
                    tab[iid]["admission"] = dict(info, tasks=[t.tid for t in tasks])
                    tab[iid]["util"] += 1 if info["d_solved"] > 0 else 0
            admitted.append(entry)
        self._prune()
        self.rounds.append(dict(round=self.n_round, t=round(self.elapsed(), 1), adm_tasks=[t.tid for t in tasks],
                                base_solved=sum(r["solved"] for r in base), proposals=admitted, meta=meta,
                                n_L=len(self.st["L"]), n_R=len(self.st["R"]), M=copy.deepcopy(self.st["M"])))
        self.n_round += 1
        return True

    def _prune(self):
        pr = I.first(self.st["M"], "prune")
        for tab, cap in ((self.st["L"], pr["max_L"]), (self.st["R"], pr["max_R"])):
            while len(tab) > cap:
                refs = set()
                for it in list(self.st["L"].values()) + list(self.st["R"].values()):
                    refs |= {n for n in S.prod_names(it["body"]) if n[:2] in ("L:", "R:")}
                cands = [k for k in tab if f"{k[0]}:{k}" not in refs and f"L:{k}" not in refs and f"R:{k}" not in refs]
                if not cands:
                    break
                k = min(cands, key=lambda k: (tab[k]["util"], tab[k]["birth_round"]))
                self.st.setdefault("pruned", []).append(dict(id=k, src=tab[k]["src"], util=tab[k]["util"],
                                                            round=self.n_round))
                del tab[k]
                self.st["pi"]["costs"].pop(f"L:{k}", None)
                self.st["pi"]["costs"].pop(f"R:{k}", None)

    def _adm_task(self):
        s = next(self.adm_seeds)
        w, f = SD.ADMIT[s % len(SD.ADMIT)]
        return task_of(w, f, (s % len(SD.ADMIT) + s // len(SD.ADMIT)) % 2 + 1, s)   # admission: L1 / L2 interleaved

    def _next_task(self):
        if self.schedule is not None:
            if not self.schedule:
                return None, None
            w, f, lv, s = self.schedule.pop(0)
            return (w, f, lv), task_of(w, f, lv, s)
        cur = I.first(self.st["M"], "curriculum")
        cell = self.cur.pick(cur["rule"], cur["eps"])
        s = next(self.task_seeds)
        return cell, task_of(*cell, s)

    def run(self):
        n_since = 0
        while True:
            if self.left() < self.cap + 1.0:
                self.stop_reason = "budget"
                break
            cell, task = self._next_task()
            if task is None:
                self.stop_reason = "schedule exhausted"
                break
            self.sched_log.append([task.world, task.family, task.level, task.seed])
            r = safe_episode(task, self.st, self.cap)
            self.cur.update(cell, r["solved"])
            if r["solved"]:
                for n in r["used_items"]:
                    k = n[2:]
                    tab = self.st["L"] if n[0] == "L" else self.st["R"]
                    if k in tab:
                        tab[k]["uses"].append(task.tid)
                        tab[k]["util"] += 1
                self.archive.append(dict(tid=task.tid, sig=list(task.mech.sig), prog=r["_ast"]))
                self.archive = self.archive[-BUFFER:]
            self.rows.append({k: v for k, v in r.items() if k != "_ast"} | dict(t=round(self.elapsed(), 1), phase="source"))
            n_since += 1
            if n_since >= I.first(self.st["M"], "schedule")["period"]:
                if self.proposal_round():
                    n_since = 0
            if len(self.rows) % 5 == 0:
                self.save()
        self.save(final=True)
        return self

    def save(self, final=False):
        self.out.mkdir(parents=True, exist_ok=True)
        endpoint = {k: v for k, v in self.st.items()}
        doc = dict(name=self.name, final=final, stop_reason=self.stop_reason, elapsed=round(self.elapsed(), 2),
                   cpu=round(time.process_time() - self.C0, 2), digest=ST.digest(self.st), state=ST.to_json(endpoint),
                   schedule=self.sched_log, rows=self.rows, rounds=ST.to_json(self.rounds), meta_log=self.meta_log)
        p = self.out / f"{self.name}.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=0, default=list))
        os.replace(tmp, p)
