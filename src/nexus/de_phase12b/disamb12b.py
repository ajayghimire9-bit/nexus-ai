"""Phase 12B active disambiguation (NOT LOCKED): a copy of de_phase12.disamb12 with ONE toggleable change (Change B, `challenge`;
default False = Phase 12 behaviour) and the Change A flag threaded through every (re)synthesis (`reopen`):
  CHALLENGE  when query budget remains and the surviving candidates are a SINGLETON or UNANIMOUS (no disagreement found by the
             constructor's probes), NEXUS no longer skips its query: it issues a SHARED-BELIEF CHALLENGE QUERY on an admissible input
             drawn by the SAME generic mutation generator (NULL / duplicate / copy / fresh / boundary / cross / drop on the columns the
             candidate programs read) - the draw with the most mutations on those columns among CHALLENGE_PROBES draws (no new detector,
             no error-specific rule). If any draw makes the candidates disagree, it becomes an ordinary candidate-splitting query.
  LOGGING    every query is labelled split / challenge / static / random; `all_falsified` marks a SHARED-BELIEF FALSIFICATION (every
             current candidate contradicted -> synthesis restarts with the new example, reopen as configured).
Phase 12 docstring follows.
Phase 12 active disambiguation (NOT LOCKED): when several consistent executable explanations remain, construct a small admissible
input on which they disagree, query the budgeted reference, falsify, and continue or abstain.

ADMISSIBLE INPUTS (generic; no mechanism-specific detector): every relation of the task's schema gets 1..ROWS_MAX rows sampled from the
rows observed so far, then MUT_MAX random mutations (the mutated column is, with probability FOCUS, one the candidate programs reference,
read from their own ASTs) from a fixed generic menu: duplicate a row; set a cell to NULL; copy a value from
another row of the same column (creates duplicate keys / order ties); give a cell a FRESH value (creates unmatched keys); a boundary
value (each constant appearing in any candidate program, -1 / 0 / +1, and the column's observed min / max); copy a value from a column
of another relation with the same type (creates matches across relations); drop a row. An input is ADMISSIBLE iff every declared
contract holds (declared unique columns unique, declared not-null columns non-NULL) and types match the schema. All randomness:
rng10c numeric tuples.
CONSTRUCT  draw PROBES admissible inputs; evaluate EVERY candidate on each (one charged full check per candidate execution); keep the
           input with the most distinct candidate outputs (then the smallest largest class, then the fewest rows). The score uses only
           the candidates' own executions: there is no rule for any particular error type.
QUERY      the reference interface (`generator-supervised interaction`: the task generator's executable specification) returns the
           expected output for the input; each query is charged one full check and counted against B_q. NEXUS never certifies an
           answer by agreement among its own candidates.
FALSIFY    candidates whose output differs from the reference are eliminated. If none survives, the queried example joins the
           observations and synthesis resumes inside the remaining work cap (synth12.collect with extra_obs).
SUBMIT / ABSTAIN (identical for Fixed, Random and NEXUS): after the queries, the constructor searches FINAL_PROBES admissible inputs over
           the survivors; any disagreement -> ABSTAIN_UNRESOLVED_DISAGREEMENT; otherwise the minimal-size survivor is submitted. Agreement
           of the found candidates under a bounded search is an empirical consistency check, not a proof of correctness.
ARMS       fixed: queries the task's predefined static evidence batches; random: queries random admissible inputs from the SAME generator
           (no scoring); nexus: queries constructed distinguishing inputs (stops querying when no distinguishing input is found);
           first_match (diagnostic): the first consistent candidate in search order that also reproduces the first static evidence batch
           (Phase 11 acceptance), without retention or abstention."""
from __future__ import annotations

from nexus.de_phase10c.rng10c import rng as rng10c
from nexus.de_phase11 import core11 as C
from nexus.de_phase12b import synth12b as S

ROWS_MAX, MUT_MAX, PROBES, FINAL_PROBES, FOCUS, CHALLENGE_PROBES = 4, 3, 40, 40, 0.7, 40
COLLECT_SHARE = 0.7


def out_key(R):
    if R is C.ERR or R is None:
        return "ERR"
    return (tuple(sorted(R.cols)), tuple(sorted(R.bag().items(), key=repr)))


def run_cand(c, env, lib, budget):
    budget.c["full_checks"] += 1
    budget.c["probe_evals"] += 1
    try:
        R = C.run(c["expanded"], env)
    except (C.RelErr, TypeError, KeyError, ValueError, C.TypeErr, C.Unsupported):
        return "ERR"
    return out_key(C.project_like(R, sorted(R.cols)))


def constants(cands):
    out = set()

    def walk(x):
        if isinstance(x, tuple) and x:
            if x[0] == "const" and len(x) == 3 and isinstance(x[2], str):
                out.add((x[2], x[1]))
                return
            for y in x:
                walk(y)
    for c in cands:
        walk(c["expanded"])
    return out


def referenced_columns(cands):
    """Column names referenced by any candidate program (generic: read from the candidates' own ASTs)."""
    out = set()

    def walk(x):
        if isinstance(x, tuple) and x:
            if x[0] == "col" and len(x) == 2 and isinstance(x[1], str):
                out.add(x[1])
            elif x[0] in ("fold", "rank") and len(x) > 2 and isinstance(x[2], tuple):
                out.update(k for k in x[2] if isinstance(k, str))
            elif x[0] == "join" and len(x) == 6:
                out.update(k for k in x[4] + x[5] if isinstance(k, str))
            for y in x:
                walk(y)
    for c in cands:
        walk(c["expanded"])
    return out


class Inputs:
    """Generic admissible-input generator over the task schema, contracts and observed rows."""

    def __init__(self, task, observed, cands, seed):
        self.schema = {k: v.schema() for k, v in task["inputs"]["vis_a"].items()}
        self.contracts = task.get("contracts", {})
        self.pool = {k: [] for k in self.schema}
        for env in observed:
            for k, R in env.items():
                if k in self.pool:
                    self.pool[k] += [r for r in R.rows]
        self.consts = constants(cands)
        self.seed = seed
        self.n = {}                                              # one draw counter per tag (independent random streams)
        self.focus = referenced_columns(cands)

    def admissible(self, env):
        for k, R in env.items():
            ct = self.contracts.get(k, {})
            for c in ct.get("unique", []):
                i = R.cols.index(c)
                vals = [r[i] for r in R.rows]
                if len(vals) != len(set(vals)):
                    return False
            for c in ct.get("not_null", []):
                i = R.cols.index(c)
                if any(r[i] is None for r in R.rows):
                    return False
        return True

    def _fresh(self, t, used):
        if t == C.INT:
            return max([v for v in used if isinstance(v, int)] + [0]) + 7
        if t == C.STR:
            return "zz" + str(len(used))
        if t == C.NUM:
            return 0.5 + max([float(v) for v in used if isinstance(v, (int, float))] + [0.0])
        return None

    def draw(self, tag):
        """One admissible input (or None after 20 failed attempts); `tag` separates the random streams of the arms."""
        for _ in range(20):
            self.n[tag] = self.n.get(tag, 0) + 1
            r = rng10c(self.seed, tag, self.n[tag])
            env = {}
            for k, sch in self.schema.items():
                src = self.pool[k] or [tuple(None for _ in sch)]
                env[k] = [list(r.choice(src)) for _ in range(r.randint(1, ROWS_MAX))]
            self.last_focus = 0
            for _ in range(r.randint(0, MUT_MAX)):
                k = r.choice(sorted(env))
                rows, sch = env[k], self.schema[k]
                if not rows:
                    continue
                foc = [jj for jj, (cn, _) in enumerate(sch) if cn in self.focus]
                j = r.choice(foc) if foc and r.random() < FOCUS else r.randrange(len(sch))   # columns the candidates read
                t = sch[j][1]
                op = r.choice(("dup", "null", "copy", "fresh", "boundary", "cross", "drop"))
                self.last_focus += sch[j][0] in self.focus
                i = r.randrange(len(rows))
                if op == "dup":
                    rows.append(list(rows[i]))
                elif op == "null":
                    rows[i][j] = None
                elif op == "copy":
                    rows[i][j] = r.choice(rows)[j]
                elif op == "fresh":
                    rows[i][j] = self._fresh(t, [row[j] for row in self.pool[k]] + [row[j] for row in rows])
                elif op == "boundary":
                    obs = [row[j] for row in self.pool[k] if row[j] is not None]
                    opts = [v + d for tt, v in self.consts if tt == t and t in (C.INT, C.NUM) and v is not None for d in (-1, 0, 1)]
                    opts += [v for tt, v in self.consts if tt == t and t in (C.STR, C.BOOL)]
                    if obs and t in (C.INT, C.NUM, C.STR):
                        opts += [min(obs), max(obs)]
                    if opts:
                        rows[i][j] = r.choice(opts)
                elif op == "cross":
                    others = [(k2, j2) for k2, s2 in self.schema.items() for j2, (_, t2) in enumerate(s2) if k2 != k and t2 == t and env.get(k2)]
                    if others:
                        k2, j2 = r.choice(others)
                        rows[i][j] = r.choice(env[k2])[j2]
                elif op == "drop" and len(rows) > 1:
                    rows.pop(i)
            rel = {k: C.Rel([n for n, _ in sch], [t for _, t in sch], [tuple(x) for x in env[k]]) for k, sch in self.schema.items()}
            if self.admissible(rel):
                self.last_rel_focus = self.last_focus
                return rel
        return None


def construct(cands, gen, lib, budget, probes, tag):
    """-> (best distinguishing input or None, its per-candidate outputs, n_classes)."""
    best = None
    for _ in range(probes):
        env = gen.draw(tag)
        if env is None:
            continue
        outs = [run_cand(c, env, lib, budget) for c in cands]
        classes = {}
        for o in outs:
            classes[o] = classes.get(o, 0) + 1
        if len(classes) < 2:
            continue
        score = (len(classes), -max(classes.values()), -sum(len(R.rows) for R in env.values()))
        if best is None or score > best[0]:
            best = (score, env, outs)
    if best is None:
        return None, None, 1
    return best[1], best[2], best[0][0]


def challenge_input(cands, gen, lib, budget):
    """Change B: an admissible input for a singleton / unanimous set (see the module docstring). -> (env, 'challenge' | 'split')."""
    best, split = None, None
    for _ in range(CHALLENGE_PROBES):
        env = gen.draw(6)
        if env is None:
            continue
        focus = getattr(gen, "last_rel_focus", 0)
        outs = {run_cand(c, env, lib, budget) for c in cands} if len(cands) > 1 else set()
        if len(outs) >= 2:
            split = env
            break
        score = (focus, -sum(len(R.rows) for R in env.values()))
        if focus > 0 and (best is None or score > best[0]):
            best = (score, env)
    if split is not None:
        return split, "split"
    return (best[1], "challenge") if best else (None, None)


def resolve(task, admin, lib, costs, collected, arm, b_q, budget, seed, challenge=False, reopen=False):
    """One arm on one task, continuing from the shared candidate collection. -> dict(outcome, submission, queries, ...)."""
    cands = list(collected["candidates"])
    observed = [task["inputs"][k] for k in ("vis_a", "vis_b")]
    queries, extra = [], list(task.get("extra_obs", []))
    gen = Inputs(task, observed, cands, seed)
    try:
        if arm == "first_match":
            if not cands:
                return dict(outcome="none", submission=None, queries=queries)
            env, exp = admin["static"][0]
            budget.c["oracle_queries"] += 1
            budget.c["full_checks"] += 1
            for c in cands:
                if run_cand(c, env, lib, budget) == out_key(C.project_like(exp, sorted(exp.cols))):
                    return dict(outcome="submitted", submission=c, queries=[dict(source="static", n_cands=len(cands))])
            return dict(outcome="abstain_no_consistent_candidate", submission=None, queries=queries)
        q = 0
        while q < b_q:
            if not cands:
                break
            qtype = arm
            if arm == "fixed":
                env, qtype = admin["static"][q][0], "static"
            elif arm == "random":
                env = gen.draw(2)
            else:
                env, qtype = None, "split"
                if len(cands) >= 2:
                    env, _, ncls = construct(cands, gen, lib, budget, PROBES, 3)
                    if env is None:                                # also search the final-probe stream before giving up a query
                        env, _, ncls = construct(cands, gen, lib, budget, FINAL_PROBES, 4)
                if env is None:
                    if not challenge:
                        break
                    env, qtype = challenge_input(cands, gen, lib, budget)   # Change B: challenge a singleton / unanimous set
                if env is None:
                    break
            if env is None:
                break
            budget.c["oracle_queries"] += 1
            budget.c["full_checks"] += 1
            Y = admin["oracle"](env)
            yk = out_key(C.project_like(Y, sorted(Y.cols))) if Y is not C.ERR else "ERR"
            outs = [run_cand(c, env, lib, budget) for c in cands]
            surv = [c for c, o in zip(cands, outs) if o == yk]
            queries.append(dict(source=arm, qtype=qtype, n_cands=len(cands), distinct_predictions=len(set(outs)), falsified=len(cands) - len(surv),
                                split=len(set(outs)) >= 2 and len(surv) < len(cands), all_falsified=not surv, unanimous=len(set(outs)) == 1,
                                rows=sum(len(R.rows) for R in env.values())))
            q += 1
            if Y is not C.ERR:
                extra.append((f"q{len(extra) + 1}", env, Y))
                observed.append(env)
            if surv:
                cands = surv
            else:                                                # every explanation falsified: resume synthesis with the new example
                t2 = dict(task, extra_obs=extra)
                res = S.collect(t2, lib, costs, budget, reopen=reopen)
                cands = res["candidates"]
                queries[-1]["resumed"] = len(cands)
                if budget.exhausted:
                    break
            gen = Inputs(task, observed, cands, seed)
        if not cands:
            return dict(outcome="abstain_no_consistent_candidate", submission=None, queries=queries)
        if len(cands) >= 2:                                      # the SAME final probe for every arm (its own stream, tag 5)
            env, _, ncls = construct(cands, gen, lib, budget, FINAL_PROBES, 5)
            if env is not None:
                return dict(outcome="abstain_unresolved_disagreement", submission=None, queries=queries, survivors=len(cands))
        best = min(cands, key=lambda c: (c["size"], repr(c["expanded"])))
        return dict(outcome="submitted", submission=best, queries=queries, survivors=len(cands))
    except S.WorkExhausted as e:
        return dict(outcome="abstain_work_exhausted", submission=None, queries=queries, exhausted=str(e))
