"""Wave 26 Phase 2: oracle realism inside the Phase 1 crossover cell (depth 2, 8 fields, large grammar,
c_oracle = 20) - noisy oracles, noise-tolerant certificates, opaque stdlib mechanisms.

* Opaque mechanisms: every bounded selection S[k, o] and Sort[o] of the grammar is replaced by an opaque
  stdlib callable (itertools.islice / heapq.nsmallest / heapq.nlargest / sorted with operator.itemgetter).
  NEXUS sees only a callable with an anonymous role; it cannot inspect its code. Its structural class is
  observed on every concrete transition the certifier executes (EMPIRICAL_CONTRACT: checks, violations).
  EMPIRICAL contracts never prune (vault firewall); a property prunes only if it is PROVED_SOUND for every
  role that can appear, so with opaque roles present no contract prunes. (pandas is not installed; stdlib
  only.)
* Noise: each oracle response is corrupted independently with probability eps (one random output item
  dropped). Public training pairs are noiseless.
* Noise-tolerant certificate: the exact certifier runs on the noiseless public pairs only and yields the
  complete minimal-size version space H. Probes update each h's disagreement count d(h). With a uniform
  prior over programs, an answer group's evidence is max over its members of eps^d (1-eps)^(n-d); the
  certificate UNIQUE_WITHIN_NOISE(eps, delta) is issued iff the leading group's evidence exceeds every other
  group's by a likelihood ratio >= (1 - delta) / delta, i.e. (d_second - d_lead) * ln((1-eps)/eps)
  >= ln((1-delta)/delta). Probes may repeat an input (fresh noise). Budget 6 probes.
* Arms: exact_eig_noisy (unlearned: flat likelihood-weighted EIG, standard perturbations),
  full_noisy (vault + answer-directed likelihood-weighted I(Y_q;Y_x) over standard + factored candidates),
  naive_exact_elim (full_noisy's probes but eliminating on ANY disagreement - the brittle control).
"""
from __future__ import annotations

import heapq
import itertools
import math
import operator
import random
from collections import Counter, defaultdict

from nexus.wave24_domains import Tool, vkey
from nexus.wave24_v4_core import AMBIGUOUS, Searcher, candidate_probes, meter
from nexus.wave25_contracts import _class_holds, learn_contracts, make_contract_pruner, item_map
from nexus.wave25_factored import TASK_BUDGET, Order, binding_grammar, run
from nexus.wave25_s3 import enumerate_H, factored_candidates, outputs
from nexus.wave25_vault import ContractVault
from nexus.wave26_phase1 import GRAMMARS, records_world_f

C_ORACLE = 20
EPSILONS = (0.01, 0.05, 0.10)
DELTA = 0.01
PROBE_BUDGET_NOISY = 6
CELL = ("d2", 2, 8, "large")
HORIZON = 100
ARMS = ("exact_eig_noisy", "full_noisy", "naive_exact_elim")
N_CAND = 200


class Opaque:
    """Black-box stdlib callable with an anonymous role; Mech-compatible (role, slots, name, __call__)."""

    def __init__(self, idx, fn):
        self._fn, self.idx = fn, idx
        self.role = "Opaque"
        self.slots = ()
        self.observed = Counter()            # EMPIRICAL_CONTRACT evidence: checks / violations per class

    def __call__(self, xs):
        if not isinstance(xs, list):
            raise TypeError("list callable on a scalar")
        out = self._fn(xs)
        self.observed["checks"] += 1
        if not _class_holds("submultiset", xs, out):
            self.observed["submultiset_violations"] += 1
        return out

    def name(self):
        return f"opaque{self.idx}"


def _opaque_for(mech, idx):
    if mech.role == "S":
        k, o = mech.slots
        if o.path == "#":
            fn = lambda xs, k=k: list(itertools.islice(xs, k))
        elif o.desc:
            fn = lambda xs, k=k, g=operator.itemgetter(o.path): heapq.nlargest(k, xs, key=g)
        else:
            fn = lambda xs, k=k, g=operator.itemgetter(o.path): heapq.nsmallest(k, xs, key=g)
    else:
        (o,) = mech.slots
        fn = lambda xs, g=operator.itemgetter(o.path), r=o.desc: sorted(xs, key=g, reverse=r)
    return Opaque(idx, fn)


def grammar2(inputs):
    """Phase 1 large grammar with every S and Sort swapped for an opaque stdlib callable."""
    tools, j = [], 0
    for t in binding_grammar(inputs, maps=False, **GRAMMARS[CELL[3]]):
        m = t.fn
        if m.role == "Agg":
            continue
        if m.role in ("S", "Sort"):
            op = _opaque_for(m, j)
            j += 1
            tools.append(Tool(op.name(), op, op.name(), kind="primitive", parts=("Opaque",)))
        else:
            tools.append(t)
    return tools


def make_episodes2(world, seed, n):
    rng = random.Random(f"w26-p2:{world['name']}:{seed}")
    out, tries = [], 0
    while len(out) < n and tries < n * 400:
        tries += 1
        xs = [world["sample"](rng) for _ in range(4)]
        tools = grammar2(xs)
        chain = tuple(rng.choice([t.fn for t in tools]) for _ in range(CELL[1]))
        try:
            ys = [run(chain, x) for x in xs]
        except Exception:
            continue
        if len({vkey(y) for y in ys[:3]}) < 2 or any(vkey(x) == vkey(y) for x, y in zip(xs, ys)):
            continue
        public = tuple(zip(xs[:3], ys[:3]))
        res = Searcher(public, xs[3], tools, popper=True, m=meter(TASK_BUDGET), partial_depth=0,
                       max_depth=CELL[1]).run_to(CELL[1])
        if res.size != CELL[1] or res.status != AMBIGUOUS or vkey(ys[3]) not in {vkey(h[1]) for h in res.hypotheses}:
            continue
        out.append(dict(public=public, query=xs[3], answer=ys[3], teacher=chain, inputs=xs))
    return out


def corrupt(y, rng):
    if isinstance(y, list) and y:
        z = list(y)
        del z[rng.randrange(len(z))]
        return z
    return ["__noise__"]


# --------------------------------------------------------------------------- likelihood-weighted objectives
def _wH(weights, keys):
    tot = defaultdict(float)
    for w, k in zip(weights, keys):
        tot[k] += w
    z = sum(tot.values())
    return -sum(v / z * math.log2(v / z) for v in tot.values() if v > 0) if z > 0 else 0.0


def _wcond(weights, target, ys):
    by = defaultdict(lambda: ([], []))
    for w, t, y in zip(weights, target, ys):
        by[y][0].append(w)
        by[y][1].append(t)
    z = sum(weights)
    return _wH(weights, target) - sum(sum(ws) / z * _wH(ws, ts) for ws, ts in by.values()) if z > 0 else 0.0


def group_status(yq, d, n, eps):
    lead = defaultdict(lambda: math.inf)
    for y, di in zip(yq, d):
        lead[y] = min(lead[y], di)
    ranked = sorted(lead.items(), key=lambda kv: kv[1])
    if len(ranked) == 1:
        return ranked[0][0], math.inf
    gap = ranked[1][1] - ranked[0][1]
    return ranked[0][0], gap * math.log((1 - eps) / eps)


# --------------------------------------------------------------------------- episode
def prepare(ep, vault):
    """Exact certification on the noiseless public pairs + complete version space (shared by every arm;
    each arm's meter is charged this work in full). Contracts prune only if PROVED_SOUND for every role."""
    tools = grammar2(ep["inputs"])
    roles = {t.fn.role for t in tools}
    u = vault.sound_props(roles)
    props_ok = u["numeric"] or u["provenance"]
    m = meter(10**12)
    pr = None
    if props_ok:
        pr = make_contract_pruner(vault.pruner_props(roles, list(u["numeric"]) + ["provenance", "kind"]),
                                  maps=[item_map(t.fn) for t in tools if item_map(t.fn) is not None])
    res = Searcher(ep["public"], ep["query"], tools, popper=True, m=meter(TASK_BUDGET), partial_depth=0,
                   max_depth=CELL[1], abstract=pr).run_to(CELL[1])
    m.charge("certify_work_units", res.work)
    H = enumerate_H(list(ep["public"]), [t.fn for t in tools], res.size, m)
    yq = outputs(H, ep["query"], m)
    return dict(tools=tools, H=H, yq=yq, base_work=m.total, base_by=dict(m.counts), pruning=bool(props_ok),
                status=res.status)


def run_arm(ep, prep, arm, eps, *, seed, c_oracle=C_ORACLE):
    m = meter(10**12)
    for k, v in prep["base_by"].items():
        m.charge(k, v)
    H, yq = prep["H"], prep["yq"]
    rng_probe = random.Random(f"w26-p2-design:{seed}:{arm}:{eps}:{vkey(ep['query'])}")
    rng_noise = random.Random(f"w26-p2-noise:{seed}:{eps}:{vkey(ep['query'])}")   # same noise stream per arm
    d = [0] * len(H)
    n = 0
    probed, cache = [], {}
    thresh = math.log((1 - DELTA) / DELTA)
    status, answer = AMBIGUOUS, None
    while True:
        if arm == "naive_exact_elim":
            alive = [i for i, di in enumerate(d) if di == 0]
            ys_alive = {yq[i] for i in alive}
            if len(ys_alive) == 1:
                status, answer = "UNIQUE_WITHIN_NOISE", next(iter(ys_alive))
                break
            if not alive:
                status = "EMPTY_VERSION_SPACE"
                break
            weights = [1.0 if di == 0 else 0.0 for di in d]
        else:
            lead, score = group_status(yq, d, n, eps)
            if score >= thresh:
                status, answer = "UNIQUE_WITHIN_NOISE", lead
                break
            weights = [eps ** di * (1 - eps) ** (n - di) for di in d]
        if n >= PROBE_BUDGET_NOISY:
            break
        bases = [x for x, _ in ep["public"]] + [ep["query"]]
        seen = {vkey(ep["query"])}
        best, best_key = None, None

        def scan(cands):
            nonlocal best, best_key
            for x in cands:
                k = vkey(x)
                if k in seen:
                    continue
                seen.add(k)
                if k not in cache:
                    cache[k] = outputs(H, x, m)
                ys = cache[k]
                key = (_wH(weights, ys), 0.0) if arm == "exact_eig_noisy" else \
                    (_wcond(weights, yq, ys), _wH(weights, ys))
                if best_key is None or key > best_key:
                    best, best_key = x, key

        tier1 = [x for _, x, _ in candidate_probes(bases, [], ep["query"], two_step=False)] + probed
        scan(tier1[:N_CAND])
        if arm != "exact_eig_noisy":
            # two-tier, cost-aware (as in the vault ReasoningProcedure): factored disagreement edits are
            # generated and scored only when no cheap candidate splits the weighted answer groups completely
            if best_key is None or best_key[0] < _wH(weights, yq) - 1e-9:
                scan(factored_candidates(H, yq, list(ep["public"]), ep["query"], rng_probe, m)[:N_CAND])
        if best is None or best_key[0] <= 1e-12:
            break
        n += 1
        m.charge("oracle_work_units", c_oracle)
        y = run(ep["teacher"], best)
        if rng_noise.random() < eps:
            y = corrupt(y, rng_noise)
        yk = vkey(y)
        ys = cache[vkey(best)]
        d = [di + (yi != yk) for di, yi in zip(d, ys)]
        if vkey(best) not in {vkey(p) for p in probed}:
            probed.append(best)
    truth = vkey(ep["answer"])
    return dict(arm=arm, eps=eps, status=status, probes=n,
                solved=status == "UNIQUE_WITHIN_NOISE" and answer == truth,
                false_certificate=status == "UNIQUE_WITHIN_NOISE" and answer != truth,
                truth_alive=any(y == truth for y, di in zip(yq, d) if di == 0), work=m.total, work_by=dict(m.counts),
                H=len(H), pruning=prep["pruning"])


def run_seed(seed, n_eps, *, epsilons=EPSILONS, c_oracle=C_ORACLE):
    world = records_world_f(seed, CELL[2])
    eps_list = make_episodes2(world, seed, n_eps)
    lib = learn_contracts()
    vault = ContractVault(lib)
    learn_cost = sum(lib.work.values())
    rows, empirical = [], Counter()
    for i, ep in enumerate(eps_list):
        prep = prepare(ep, vault)
        for t in prep["tools"]:
            if isinstance(t.fn, Opaque):
                empirical.update(t.fn.observed)
        for eps in epsilons:
            for arm in ARMS:
                r = run_arm(ep, prep, arm, eps, seed=seed, c_oracle=c_oracle)
                r.update(seed=seed, episode=i)
                rows.append(r)
    return dict(seed=seed, rows=rows, n=len(eps_list), contract_learning=learn_cost, c_oracle=c_oracle,
                empirical_contract=dict(empirical))


def binom_upper(n, p, q=0.99):
    """Smallest k with P(Binom(n, p) <= k) >= q."""
    c, k = 0.0, 0
    while k <= n:
        c += math.comb(n, k) * p ** k * (1 - p) ** (n - k)
        if c >= q:
            return k
        k += 1
    return n


def score(outs):
    agg = defaultdict(Counter)
    for o in outs:
        for r in o["rows"]:
            for key in ((r["arm"], r["eps"]), (r["arm"], "ALL")):
                a = agg[key]
                a["episodes"] += 1; a["solved"] += r["solved"]; a["false"] += r["false_certificate"]
                a["certs"] += r["status"] == "UNIQUE_WITHIN_NOISE"; a["probes"] += r["probes"]; a["work"] += r["work"]
                a["empty"] += r["status"] == "EMPTY_VERSION_SPACE"
    n_eps = sum(o["n"] for o in outs)
    learn = sum(o["contract_learning"] for o in outs) * n_eps * len(EPSILONS) / HORIZON / max(1, len(outs))
    tab = {f"{a}|{e}": dict(v) for (a, e), v in agg.items()}
    for k, v in tab.items():
        v["fully_loaded"] = v["work"] + (learn * (1 if k.endswith("ALL") else 1 / len(EPSILONS))
                                         if k.startswith(("full_noisy", "naive")) else 0)
        v["false_bound_99"] = binom_upper(v["certs"], DELTA)
    calibrated = all(tab[f"{a}|{e}"]["false"] <= tab[f"{a}|{e}"]["false_bound_99"]
                     for a in ("exact_eig_noisy", "full_noisy") for e in EPSILONS)
    F, E = tab["full_noisy|ALL"], tab["exact_eig_noisy|ALL"]
    return dict(table=tab, calibrated_soundness=calibrated,
                full_beats_exact=F["fully_loaded"] < E["fully_loaded"] and F["solved"] >= E["solved"],
                empirical_contracts={o["seed"]: o["empirical_contract"] for o in outs})
