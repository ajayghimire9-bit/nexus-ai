"""Phase 2 agent loop (NOT LOCKED): Phase 1's 11-step loop plus
  * a LOCKED acceptance barrier (ACCEPT: competitor margin 1, 4 confirmation queries on the most novel probes, chance-fit
    bound 0.1) that neither pi nor M can change, so partial credit can guide search and memory while accepted silent
    errors stay governed by the same rule for every arm;
  * graded partial credit: per labelled example 1 for an exact match, else the fraction of the output's leading positions
    (time steps / rows) that agree, 0 for a wrong scalar; mean over labelled examples;
  * Tier 1, the bounded PROVISIONAL EXPERIENCE ARCHIVE P: from every UNSOLVED episode, the best partially-correct
    executable candidates (score >= M.archive.min_score) with their evidence - which labelled examples they match exactly,
    their graded score and the first counterexample; bounded by M.archive.max_P and per input/output-signature diversity
    (per_key); never used by the solver, never ground truth;
  * Tier 2, VALIDATED knowledge R, L: a proposal supported by any P entry (tier 'provisional') is admitted only on
    positive evidence on separate admission tasks (more exact solves, or graded admission credit up by >= M.admit.eps with
    no new silent error and no slowdown); the neutral (no-evidence) rule applies only to solved-only proposals;
  * draft attribution: a solution containing a subtree inserted from the task's draft program is origin 'draft_subtree',
    otherwise 'pure_synthesis'; every archive entry and every learned item carries its origins;
  * FULL-ROLLOUT meta-evaluation (Full cohort): a candidate M' and the current M each control their own complete
    multi-round mini-learning rollout (own curriculum, admission, pruning, archive and schedule) from a clone of
    (R, L, P, pi), with paired environment randomness (identical task-seed stream, admission seeds and RNG seeds, but
    free actions); both post-rollout learners are scored on the same held-out rollout-evaluation tasks (graded); the
    winner's post-rollout learner and M continue the lineage (M' adopted iff strictly better)."""
from __future__ import annotations

import copy
import json
import math
import os
import random
import time
from pathlib import Path

from nexus.campaign2 import improver as I, state as ST, substrate as S
from nexus.campaign2 import seeds as SD
from nexus.campaign2.worlds2 import make_task2
from nexus.campaign.worlds import verify

CAP_S = 0.6
MAX_COST = 18
BUFFER = 40
ACCEPT = dict(margin=1, confirm_q=4, fit_alpha=0.1)      # locked system constants
ROLL_S, ROLL_EVAL = 24.0, 3     # a rollout must afford >= 1 proposal round (~11 s at M0 settings)


def _atoms(v, out):
    if isinstance(v, tuple):
        for z in v:
            _atoms(z, out)
    else:
        out.add(v)
    return out


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


def ex_score(y, label):
    """Graded agreement of one output with one label."""
    if y == label:
        return 1.0
    if isinstance(y, tuple) and isinstance(label, tuple) and (y or label):
        k = 0
        for a, b in zip(y, label):
            if a != b:
                break
            k += 1
        return k / max(len(y), len(label))
    return 0.0


def solve(view, st, cap_s=CAP_S, rng=None, costs=None, want_partials=False):
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
    novelty = [len(_atoms(x, set()) - seen_vals) for x in xs]

    def consistent(vals):
        for i, y in labels.items():
            if not view.ok(xs[i], y, vals[i]):
                return False
        return True

    def partial(vals):
        if view.protocol != "io":
            return sum(view.ok(xs[i], y, vals[i]) for i, y in labels.items()) / len(labels)
        return sum(ex_score(vals[i], y) for i, y in labels.items()) / len(labels)

    extra = _draft_extra(view.draft)
    extra_ids = {id(a) for a, _ in extra}
    macros, feats = ST.macros_of(st), ST.feats_of(st, pi["feat_k"])
    srch = S.Search(xs, view.sig, view.out, costs or ST.costs_of(st), consistent, macros=macros, feats=feats, extra=extra,
                    consts=_mined_consts(view), deadline=t0 + cap_s, lam_max=pi["lam_max"],
                    partial=partial if want_partials else None)
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
                unl = sorted((j for j in range(len(xs)) if j not in labels), key=lambda j: (-novelty[j], j))
                if rec["confirmed"] < ACCEPT["confirm_q"] and unl and view.queries < view.q_budget:
                    labels[unl[0]] = view.query(xs[unl[0]])
                    rec["confirmed"] += 1
                    continue
                lv = [repr(y) for y in labels.values()]
                chance = srch.n_cands * math.prod(lv.count(v) / len(lv) for v in lv)
                rec["chance_fit"] = chance
                if chance > ACCEPT["fit_alpha"]:
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
            if rec["first_hit"] is not None and c >= rec["first_hit"] + ACCEPT["margin"]:
                if decide():
                    break
                rec["first_hit"] = None
    except S.Deadline:
        pass
    if rec["outcome"] is None:
        n_h = len([h for h in srch.hyps if consistent(h[2])])
        rec.update(outcome="abstain_timeout" if time.process_time() >= t0 + cap_s else "abstain_nohyp", n_hyps=n_h)
    rec["origin"] = None
    if rec["prog"] is not None:
        rec["origin"] = "draft_subtree" if any(id(n) in extra_ids for n in S.nodes(rec["prog"])) else "pure_synthesis"
    # graded credit and incomplete-experience material (re-scored on every label gathered, including queried ones)
    best = 1.0 if rec["prog"] is not None else 0.0
    rec["partials"] = []
    if want_partials and rec["prog"] is None:
        ranked = sorted(srch.partials, key=lambda z: (z[0], z[1]), reverse=True)
        seen_src = set()
        for sc, negc, ast, vals in ranked:
            sc = partial(vals)
            src = S.to_src(ast)
            # partial behaviour must come from reading the input: candidates with no input / representation leaf are skipped
            if src in seen_src or not any(n[0] in ("x", "r") for n in S.nodes(ast)):
                continue
            seen_src.add(src)
            matched = [i for i, y in labels.items() if view.ok(xs[i], y, vals[i])]
            cex = next((i for i in sorted(labels) if i not in matched), None)
            rec["partials"].append(dict(prog=ast, score=round(sc, 4), matched=matched, n_labels=len(labels), cex=cex,
                                        origin="draft_subtree" if any(id(n) in extra_ids for n in S.nodes(ast)) else
                                        "pure_synthesis", cost=-negc))
            if len(rec["partials"]) >= 3:
                break
        best = max([p["score"] for p in rec["partials"]], default=0.0)
    rec["graded"] = best
    rec.update(queries=view.queries, cpu_s=round(time.process_time() - t0, 4), n_cands=srch.n_cands)
    return rec


def episode(task, st, cap_s=CAP_S, costs=None, want_partials=False):
    view = task.view()
    rec = solve(view, st, cap_s, random.Random(f"probe|{task.tid}"), costs=costs, want_partials=want_partials)
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
                origin=rec["origin"], pure_task=bool(task.meta.get("pure_synthesis")), graded=rec["graded"],
                sig_key=f"{','.join(task.mech.sig)}->{task.mech.out}", _ast=rec["prog"], _partials=rec["partials"])


def safe_episode(task, st, cap_s=CAP_S, want_partials=False):
    try:
        return episode(task, st, cap_s, want_partials=want_partials)
    except Exception as e:                                       # noqa: BLE001
        return dict(tid=task.tid, world=task.world, family=task.family, level=task.level, seed=task.seed, role=task.role,
                    outcome="error:" + repr(e)[:120], solved=False, silent=False, verify=None, queries=0,
                    q_budget=task.q_budget, cpu_s=0.0, n_cands=0, level_reached=0, prog=None, prog_size=None, used_items=[],
                    origin=None, pure_task=False, graded=0.0, sig_key="", _ast=None, _partials=[])


def task_of(world, family, level, seed):
    role = SD.role_of(world, family)
    return make_task2(world, family, level, seed, role, SD.partners_for(world, family, role))


class Curriculum:
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

    def update(self, cell, score):
        self.hist[cell].append(score)


class SeedStream:
    """A copyable deterministic stream of seeds (paired environment randomness across rollouts)."""

    def __init__(self, seeds):
        self.seeds, self.i = list(seeds), 0

    def __next__(self):
        s = self.seeds[self.i]
        self.i += 1
        return s

    def clone(self):
        c = SeedStream(())
        c.seeds, c.i = self.seeds, self.i
        return c


class Lineage:
    """use_P False = the Full-SolvedOnly ablation (no provisional archive: only verified solutions feed proposals)."""

    def __init__(self, name, st, budget_s, out_dir, task_seeds, adm_seeds, rng_key, schedule=None, meta_edits=False,
                 cap_s=CAP_S, use_P=True, roll_seeds=None):
        self.name, self.st, self.budget, self.out = name, st, budget_s, Path(out_dir)
        self.task_seeds = task_seeds if isinstance(task_seeds, SeedStream) else SeedStream(task_seeds)
        self.adm_seeds = adm_seeds if isinstance(adm_seeds, SeedStream) else SeedStream(adm_seeds)
        self.roll_seeds = roll_seeds if roll_seeds is None or isinstance(roll_seeds, SeedStream) else SeedStream(roll_seeds)
        self.rng_key = rng_key
        self.rng = random.Random(f"agi2-lineage|{rng_key}")
        self.schedule, self.meta_edits, self.cap, self.use_P = schedule, meta_edits, cap_s, use_P
        self.T0, self.C0 = time.time(), time.process_time()
        self.archive, self.rows, self.rounds, self.meta_log, self.sched_log = [], [], [], [], []
        self.cur = Curriculum(random.Random(f"agi2-cur|{rng_key}"))
        self.n_round, self.n_since, self.stop_reason, self.deadline = 0, 0, None, None

    def elapsed(self):
        return max(time.time() - self.T0, time.process_time() - self.C0)

    def left(self):
        own = self.budget - self.elapsed()
        return own if self.deadline is None else min(own, self.deadline - time.process_time())

    # ---------------- proposals (steps 8-9)
    def _material(self):
        solved = [dict(e, tier="validated") for e in self.archive]
        use = self.use_P and I.first(self.st["M"], "archive", {}).get("use", True)
        prov = [dict(tid=f"P:{e['tid']}:{k}", sig=e["sig"], prog=e["prog"], origin=e["origin"], tier="provisional")
                for k, e in enumerate(self.st["P"])] if use else []
        return solved + prov

    def _proposals(self, M, st, rng):
        mat = self._material()
        tier = {e["tid"]: e["tier"] for e in mat}
        origin = {e["tid"]: e.get("origin") for e in mat}
        ex_L = {S.to_src(m["body"]) for m in st["L"].values()}
        ex_R = {S.to_src(r["body"]) for r in st["R"].values()}
        props = []
        for stmts, fn, ex in ((I.stmt(M, "propose_L"), I.propose_L, ex_L), (I.stmt(M, "propose_R"), I.propose_R, ex_R)):
            for p in stmts:
                for c in fn(mat, st, p, rng, ex):
                    if S.to_src(c["body"]) in ex:
                        continue
                    ex.add(S.to_src(c["body"]))
                    sup = c["support"]
                    c["tier"] = "provisional" if any(tier.get(t) == "provisional" for t in sup) else "validated"
                    os_ = {origin.get(t) for t in sup} - {None}
                    c["origin"] = ("pure_synthesis" if os_ == {"pure_synthesis"} else "draft_subtree" if os_ == {"draft_subtree"}
                                   else "mixed" if os_ else "random")
                    c["n_provisional_support"] = sum(tier.get(t) == "provisional" for t in sup)
                    props.append(c)
        rw = I.first(M, "reweight")
        if rw:
            pi, why = I.reweight(self.archive, st, rw, rng)
            if pi is not None:
                props.append(dict(kind="pi_costs", pi=pi, why=why))
        tn = I.first(M, "tune")
        if tn:
            pi, why = I.tune(st, tn, rng, self.n_round)
            props.append(dict(kind="pi_params", pi=pi, why=why))
        return props

    def _apply(self, st, prop):
        st = copy.deepcopy(st)
        if prop["kind"] in ("L", "R"):
            iid = f"{prop['kind']}{st['next_id']}"
            st["next_id"] += 1
            item = dict(body=prop["body"], method=prop["method"], mdl=prop["mdl"], support=prop["support"],
                        birth_task=(prop["support"] or [None])[0], birth_round=self.n_round, birth_lineage=self.name,
                        size=S.size(prop["body"]), src=S.to_src(prop["body"]), uses=[], util=0,
                        tier=prop.get("tier", "validated"), origin=prop.get("origin"),
                        n_provisional_support=prop.get("n_provisional_support", 0))
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
            r = safe_episode(t, st, self.cap, want_partials=True)
            res.append(dict(tid=t.tid, solved=r["solved"], silent=r["silent"], cpu=r["cpu_s"],
                            graded=1.0 if r["solved"] else min(r["graded"], 0.999)))
        return res

    def _admit(self, base, res, rule, prop):
        kind = prop["kind"]
        sb, sr = sum(r["solved"] for r in base), sum(r["solved"] for r in res)
        gb, gr = sum(r["graded"] for r in base) / len(base), sum(r["graded"] for r in res) / len(res)
        info = dict(d_solved=sr - sb, d_graded=round(gr - gb, 4))
        if sum(r["silent"] for r in res) > sum(r["silent"] for r in base):
            info["why"] = "new silent error"
            return False, info
        both = [(a["cpu"], b["cpu"]) for a, b in zip(base, res) if a["solved"] and b["solved"]]
        ratio = (sum(b for _, b in both) / max(1e-9, sum(a for a, _ in both))) if both else None
        info["cpu_ratio"] = None if ratio is None else round(ratio, 3)
        if sr < sb:
            info["why"] = "fewer solves"
            return False, info
        slow = ratio is not None and ratio > 1 + rule["speedup"]
        if sr > sb or (gr - gb >= rule.get("eps", 0.05) and not slow):
            info["why"] = "positive evidence"
            return True, info
        validated_item = kind in ("L", "R") and prop.get("tier") != "provisional"
        if validated_item and ratio is not None and not slow and (rule["neutral"] or ratio <= 1 - rule["speedup"]):
            info["why"] = "no harm on commonly solved tasks (validated-only item)"
            return True, info
        if validated_item and ratio is None and rule["neutral"] and gr >= gb:
            info["why"] = "uninformative: validated-only additive item admitted (neutral)"
            return True, info
        info["why"] = "insufficient evidence" + (" (provisional item)" if prop.get("tier") == "provisional" else "")
        return False, info

    def _round_cost(self, n_props, n_tasks):
        return (1 + n_props) * n_tasks * (self.cap + 0.15)

    def proposal_round(self):
        st, M = self.st, self.st["M"]
        adm = I.first(M, "admit")
        tasks = [self._adm_task() for _ in range(adm["n_tasks"])]
        props = self._proposals(M, st, self.rng)
        if self.left() < self._round_cost(len(props), len(tasks)) + 1:
            return False
        base = self._eval_set(st, tasks)
        admitted = []
        for p in props:
            st2, _ = self._apply(st, p)
            res = self._eval_set(st2, tasks)
            ok, info = self._admit(base, res, adm, p)
            entry = dict(kind=p["kind"], ok=ok, info=info, src=S.to_src(p["body"]) if "body" in p else p.get("why"),
                         method=p.get("method"), mdl=p.get("mdl"), support=p.get("support"), tier=p.get("tier"),
                         origin=p.get("origin"), n_provisional_support=p.get("n_provisional_support"))
            if ok:
                self.st, iid = self._apply(self.st, p)
                entry["id"] = iid
                if p["kind"] in ("L", "R"):
                    tab = self.st[p["kind"]]
                    tab[iid]["admission"] = dict(info, tasks=[t.tid for t in tasks])
                    tab[iid]["util"] += 1 if info["d_solved"] > 0 else 0
            admitted.append(entry)
        self._prune()
        self.rounds.append(dict(round=self.n_round, t=round(self.elapsed(), 1), lineage=self.name,
                                adm_tasks=[t.tid for t in tasks], base_solved=sum(r["solved"] for r in base),
                                base_graded=round(sum(r["graded"] for r in base), 3), proposals=admitted,
                                n_L=len(self.st["L"]), n_R=len(self.st["R"]), n_P=len(self.st["P"]), M=copy.deepcopy(self.st["M"])))
        self.n_round += 1
        return True

    def _prune(self):
        pr = I.first(self.st["M"], "prune")
        for tab, cap in ((self.st["L"], pr["max_L"]), (self.st["R"], pr["max_R"])):
            while len(tab) > cap:
                refs = set()
                for it in list(self.st["L"].values()) + list(self.st["R"].values()):
                    refs |= {n for n in S.prod_names(it["body"]) if n[:2] in ("L:", "R:")}
                cands = [k for k in tab if f"L:{k}" not in refs and f"R:{k}" not in refs]
                if not cands:
                    break
                k = min(cands, key=lambda k: (tab[k]["util"], tab[k]["birth_round"]))
                self.st.setdefault("pruned", []).append(dict(id=k, src=tab[k]["src"], util=tab[k]["util"], round=self.n_round))
                del tab[k]
                self.st["pi"]["costs"].pop(f"L:{k}", None)
                self.st["pi"]["costs"].pop(f"R:{k}", None)

    def _archive_partials(self, task, r):
        """Tier 1: retain incomplete attempts (bounded, diversity-managed by input/output signature)."""
        if not self.use_P:
            return
        ar = I.first(self.st["M"], "archive", dict(max_P=40, per_key=8, min_score=0.3))
        P = self.st["P"]
        have = {S.to_src(e["prog"]) for e in P}
        for p in r["_partials"]:
            if p["score"] < ar["min_score"] or S.to_src(p["prog"]) in have:
                continue
            P.append(dict(tid=task.tid, sig=list(task.mech.sig), key=r["sig_key"], prog=p["prog"], src=S.to_src(p["prog"]),
                          score=p["score"], matched=p["matched"], n_labels=p["n_labels"], cex=p["cex"], origin=p["origin"],
                          added_round=self.n_round))
            have.add(S.to_src(p["prog"]))
        P.sort(key=lambda e: (-e["score"], -e["added_round"]))
        cnt, keep = {}, []
        for e in P:
            cnt[e["key"]] = cnt.get(e["key"], 0) + 1
            if cnt[e["key"]] <= ar["per_key"]:
                keep.append(e)
        self.st["P"] = keep[:ar["max_P"]]

    def _adm_task(self):
        s = next(self.adm_seeds)
        w, f = SD.ADMIT[s % len(SD.ADMIT)]
        return task_of(w, f, (s % len(SD.ADMIT) + s // len(SD.ADMIT)) % 2 + 1, s)

    def _next_task(self):
        if self.schedule is not None:
            if not self.schedule:
                return None, None
            w, f, lv, s = self.schedule.pop(0)
            return (w, f, lv), task_of(w, f, lv, s)
        cur = I.first(self.st["M"], "curriculum")
        cell = self.cur.pick(cur["rule"], cur["eps"])
        return cell, task_of(*cell, next(self.task_seeds))

    def step(self):
        """One source task (+ a proposal round when M's schedule says so). False when out of budget / schedule."""
        if self.left() < self.cap + 1.0:
            self.stop_reason = self.stop_reason or "budget"
            return False
        cell, task = self._next_task()
        if task is None:
            self.stop_reason = "schedule exhausted"
            return False
        self.sched_log.append([task.world, task.family, task.level, task.seed])
        r = safe_episode(task, self.st, self.cap, want_partials=self.use_P)
        self.cur.update(cell, 1.0 if r["solved"] else 0.0)
        if r["solved"]:
            for n in r["used_items"]:
                tab = self.st["L"] if n[0] == "L" else self.st["R"]
                if n[2:] in tab:
                    tab[n[2:]]["uses"].append(task.tid)
                    tab[n[2:]]["util"] += 1
            self.archive.append(dict(tid=task.tid, sig=list(task.mech.sig), prog=r["_ast"], origin=r["origin"]))
            self.archive = self.archive[-BUFFER:]
        else:
            self._archive_partials(task, r)
        self.rows.append({k: v for k, v in r.items() if k not in ("_ast", "_partials")} |
                         dict(t=round(self.elapsed(), 1), phase="source", n_partials=len(r["_partials"])))
        self.n_since += 1
        if self.n_since >= I.first(self.st["M"], "schedule")["period"]:
            if self.proposal_round():
                self.n_since = 0
        return True

    # ---------------- full-rollout meta evaluation (Full cohort)
    def _clone(self, name, M, k):
        c = Lineage(name, copy.deepcopy(self.st), 1e9, self.out, self.task_seeds.clone(), self.adm_seeds.clone(),
                    rng_key=f"{self.rng_key}|roll{k}", use_P=self.use_P, cap_s=self.cap)
        c.st["M"] = copy.deepcopy(M)
        c.archive = copy.deepcopy(self.archive)
        c.cur = copy.deepcopy(self.cur)
        c.n_round, c.n_since = self.n_round, self.n_since
        return c

    def meta_rollout(self):
        need = 2 * ROLL_S + 2 * ROLL_EVAL * (self.cap + 0.15) + 3
        if self.roll_seeds is None or self.left() < need:
            return False
        M = self.st["M"]
        M2, edit = I.m_mutate(M, self.rng)
        ev = []
        for _ in range(ROLL_EVAL):
            s = next(self.roll_seeds)
            w, f = SD.ADMIT[s % len(SD.ADMIT)]
            ev.append(task_of(w, f, s % 2 + 1, s))
        k = len(self.meta_log)
        outs = []
        for tag, MM in (("current", M), ("edited", M2)):
            c = self._clone(f"{self.name}|{tag}", MM, k)          # identical environment streams and RNG; free actions
            c.deadline = time.process_time() + ROLL_S
            while c.step():
                pass
            res = c._eval_set(c.st, ev)
            outs.append((c, dict(tasks=len(c.rows), rounds=c.n_round - self.n_round, solved=sum(r["solved"] for r in res),
                                 graded=round(sum(r["graded"] for r in res), 4), n_L=len(c.st["L"]), n_R=len(c.st["R"]),
                                 n_P=len(c.st["P"]), curriculum=[x[:3] for x in c.sched_log])))
        (ca, ra), (cb, rb) = outs
        adopted = (rb["solved"], rb["graded"]) > (ra["solved"], ra["graded"])
        win = cb if adopted else ca
        self.meta_log.append(dict(round=self.n_round, edit=edit, current=ra, edited=rb, adopted=adopted,
                                  eval_tasks=[t.tid for t in ev], diverged=ra["curriculum"] != rb["curriculum"]))
        # the lineage continues from the winning post-rollout learner (its learning is real source learning)
        self.st, self.archive, self.cur = win.st, win.archive, win.cur
        self.n_round, self.n_since = win.n_round, win.n_since
        self.task_seeds, self.adm_seeds = win.task_seeds, win.adm_seeds
        self.rows += [dict(r, phase=f"rollout:{'edited' if adopted else 'current'}") for r in win.rows]
        self.rounds += win.rounds
        self.sched_log += [["rollout"] + x for x in win.sched_log]
        return True

    def run(self):
        done_meta = 0
        while True:
            mp = I.first(self.st["M"], "schedule")["meta_period"]
            if self.meta_edits and self.n_round >= (done_meta + 1) * mp:
                done_meta = self.n_round // mp
                self.meta_rollout()
            if not self.step():
                break
            if len(self.rows) % 5 == 0:
                self.save()
        self.save(final=True)
        return self

    def save(self, final=False):
        self.out.mkdir(parents=True, exist_ok=True)
        doc = dict(name=self.name, final=final, stop_reason=self.stop_reason, elapsed=round(self.elapsed(), 2),
                   cpu=round(time.process_time() - self.C0, 2), digest=ST.digest(self.st), state=ST.to_json(self.st),
                   # the learned-task sequence (main loop + the WINNING rollouts' tasks, in order): what controls replay
                   schedule=[x[1:] if x[0] == "rollout" else x for x in self.sched_log], all_tasks=self.sched_log, rows=self.rows,
                   rounds=ST.to_json(self.rounds), meta_log=self.meta_log, use_P=self.use_P)
        p = self.out / f"{self.name}.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=0, default=list))
        os.replace(tmp, p)
