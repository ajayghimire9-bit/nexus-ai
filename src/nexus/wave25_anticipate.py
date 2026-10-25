"""Wave 25: cost-aware anticipatory investigation controller with a revisable query-expectation model.

Keeps the validated stack of ab0dcd5 (factored hypotheses, persistent version space V_t, dual-ledger vault,
exact certifier). Only the probe choice inside ReasoningProcedure changes:

  score(x) = I(Y_q ; Y_x | V_t) + lam_t * E_future(x),
  E_future(x) = sum_pool w_pool * mean_{q~ in pool} I(Y_q~ ; Y_x | V_t)

* Proxy pools are built ONLY from q_curr, the observed public inputs and V_t (never from a held-out query):
  related = profile-preserving perturbations of q_curr; boundary = selection-boundary / threshold /
  field-decorrelation edits of q_curr. Their hypothesis outputs are computed once per decision and cached.
* QueryExpectationModel: continuation belief p_cont ~ decaying Beta-Bernoulli over completed episodes
  (did a follow-up query arrive?); pool weights ~ decaying Dirichlet, updated when a follow-up arrives by
  which pool's mean input profile it is closer to. No regime label is ever given.
* Stop rule unchanged: no probe once the current query is certified UNIQUE.
* Cost-aware expansion: Tier 1 (cheap perturbations) is scanned up to the first candidate that splits the
  current answer groups completely, then for at most round(M_MAX * p_cont) more candidates (the lookahead
  budget; zero when follow-ups are believed absent); Tier 2 (factored edits) only if Tier 1 has no complete
  split. Every hypothesis execution is charged.
* The fixed-lambda control is identical code with p_cont frozen at 1 and uniform frozen pool weights.
"""
from __future__ import annotations

import random
from collections import Counter

from nexus.wave24_domains import vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import AMBIGUOUS, UNIQUE, candidate_probes, meter
from nexus.wave25_contracts import default_props, learn_contracts, tycho_admit_contracts
from nexus.wave25_factored import ORACLE_COST, PROBE_BUDGET, ints_world, make_tasks, records_world, run
from nexus.wave25_s3 import _H, _reps, choose_probe, cond_info, enumerate_H, factored_candidates, outputs
from nexus.wave25_vault import (PROVED_SOUND, ContractVault, Episode, ReasoningProcedure, _T, certify_full,
                                certify_static, episode_grammar, task_context)

LAM0 = 0.5          # tuned on dev regime B (grid declared in the protocol)
M_MAX = 20
DECAY = 0.9
N_PROXY = 6


def profile(x):
    """Observable input profile: (length, concordance of numeric fields across items or sortedness)."""
    if not isinstance(x, list) or not x:
        return (0.0, 0.0)
    if isinstance(x[0], dict):
        nums = [k for k, v in x[0].items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        agree = tot = 0
        for i in range(len(x)):
            for j in range(i + 1, len(x)):
                for a in range(len(nums)):
                    for b in range(a + 1, len(nums)):
                        da = x[i][nums[a]] - x[j][nums[a]]
                        db = x[i][nums[b]] - x[j][nums[b]]
                        tot += 1
                        agree += (da * db) >= 0
        return (float(len(x)), agree / tot if tot else 1.0)
    return (float(len(x)), sum(a <= b for a, b in zip(x, x[1:])) / max(1, len(x) - 1))


class QueryExpectationModel:
    def __init__(self, *, revisable=True):
        self.revisable = revisable
        self.a, self.b = 1.0, 1.0                       # Beta(continuation)
        self.w = {"related": 1.0, "boundary": 1.0}       # Dirichlet over proxy pools
        self.trajectory = []

    @property
    def p_cont(self):
        return self.a / (self.a + self.b) if self.revisable else 1.0

    def weights(self):
        if not self.revisable:
            return {"related": 0.5, "boundary": 0.5}
        t = sum(self.w.values())
        return {k: v / t for k, v in self.w.items()}

    def end_episode(self, n_followups):
        if not self.revisable:
            return
        self.a, self.b = DECAY * self.a + (n_followups > 0), DECAY * self.b + (n_followups == 0)
        self.trajectory.append(dict(event="episode", p_cont=self.p_cont, w=self.weights()))

    def observe_followup(self, q_next_ambiguous, pool_ambiguity):
        """A follow-up arrived and the certifier showed whether V_t disagrees on it. Credit the proxy pool
        whose ambiguity rate under V_t (measured when the pools were built) best matches that outcome."""
        if not self.revisable or not pool_ambiguity:
            return
        target = 1.0 if q_next_ambiguous else 0.0
        near = min(pool_ambiguity, key=lambda k: (abs(pool_ambiguity[k] - target), k))
        for k in self.w:
            self.w[k] = DECAY * self.w[k] + (k == near)
        self.trajectory.append(dict(event="followup", ambiguous=bool(q_next_ambiguous), nearest=near,
                                    pool_ambiguity=dict(pool_ambiguity), w=self.weights()))


def proxy_pools(H, yq, public, q_curr, rng, m):
    """Zero-oracle proxy queries built from q_curr only (plus V_t's thresholds for the boundary pool)."""
    seen = {vkey(q_curr)} | {vkey(x) for x, _ in public}
    rel, bnd = [], []
    for fam, x, _ in candidate_probes([q_curr], [], q_curr, two_step=False):
        if vkey(x) not in seen:
            seen.add(vkey(x))
            rel.append(x)
    for _, x in factored_candidates(H, yq, [], q_curr, rng, m, labels=True):
        if vkey(x) not in seen:
            seen.add(vkey(x))
            bnd.append(x)
    rng.shuffle(rel)
    rng.shuffle(bnd)
    return {"related": rel[:N_PROXY], "boundary": bnd[:N_PROXY]}


class AnticipatoryProcedure(ReasoningProcedure):
    def __init__(self, vault, *, seed=0, revisable=True, lam0=LAM0, m_max=M_MAX):
        super().__init__(vault, seed=seed)
        self.qm = QueryExpectationModel(revisable=revisable)
        self.lam0, self.m_max = lam0, m_max
        self.last_pool_ambiguity = None
        self.lookahead_log = Counter()
        self.cert_work, self.cert_n = 0.0, 0          # observed certification work per probe (running)

    def schedule_probe(self, H, yq, public, query, world, rng, m):
        seen = {vkey(x) for x, _ in public} | {vkey(query)}
        dom = world["name"]
        cap = _H(Counter(yq))
        bases = [x for x, _ in public] + [query]
        weights = self.qm.weights()
        budget_after_clean = round(self.m_max * self.qm.p_cont)
        lam = self.lam0 * self.qm.p_cont if budget_after_clean > 0 else 0.0
        prox = []                                            # cached proxy outputs on V_t
        if lam > 0:                                          # cost-aware: no proxies when no lookahead pays
            pools = proxy_pools(H, yq, public, query, rng, m)
            amb = {}
            for k, qs in pools.items():
                n_amb = 0
                for q in qs:
                    ys = outputs(H, q, m)
                    if len(set(ys)) > 1:                     # only proxies V_t still disagrees on matter
                        prox.append((weights[k] / max(1, len(qs)), ys))
                        n_amb += 1
                if qs:
                    amb[k] = n_amb / len(qs)
            self.last_pool_ambiguity = amb
            self.lookahead_log["proxy_builds"] += 1

        def future(ys_x):
            return sum(w * cond_info(yq_p, ys_x) for w, yq_p in prox)

        state = dict(best=None, key=None, gen=None, clean_seen=False, extra=0)

        def scan(cands):
            for gen, x in cands:
                k = vkey(x)
                if k in seen:
                    continue
                seen.add(k)
                self.gen_tries[dom][gen] += 1
                ys = outputs(H, x, m)
                cur = cond_info(yq, ys)
                fut = future(ys) if (lam > 0 and prox) else 0.0
                key = (cur + lam * fut, cur, _H(Counter(ys)))
                if state["key"] is None or key > state["key"]:
                    state.update(best=x, key=key, gen=gen)
                if cur >= cap - 1e-12:
                    if not state["clean_seen"]:
                        state["clean_seen"] = True
                    else:
                        state["extra"] += 1
                if state["clean_seen"] and state["extra"] >= budget_after_clean:
                    return True
            return state["clean_seen"]

        def by_rate(cands):
            rate = {g: (self.gen_hits[dom][g] + 1) / (self.gen_tries[dom][g] + 2) for g, _ in cands}
            return sorted(cands, key=lambda gx: -rate[gx[0]])

        reps = H[:50]
        tier1 = [(fam, x) for fam, x, _ in candidate_probes(bases, [(None, None, tuple(_T(mm) for mm in h))
                                                                    for h in reps], query)]
        done = scan(by_rate(tier1)[:300])
        tier = 1
        expand = not done
        if done and lam > 0 and prox and state["best"] is not None:
            # cost-aware lookahead expansion: residual follow-up entropy left by the best Tier-1 probe, valued
            # at the observed cost of one probe (oracle + re-certification), against the Tier-2 scan cost
            ys_b = outputs(H, state["best"], m)
            resid = sum(w * (_H(Counter(yp)) - cond_info(yp, ys_b)) for w, yp in prox)
            per_probe = getattr(self, "oracle_cost", ORACLE_COST) + (self.cert_work / max(1, self.cert_n))
            t2 = factored_candidates(H, yq, public, query, rng, m, labels=True)
            est_cost = min(len(t2), budget_after_clean) * len(H)
            if self.qm.p_cont * resid * per_probe > est_cost:
                self.lookahead_log["tier2_lookahead"] += 1
                state["extra"] = 0
                tier = 2
                scan(by_rate(t2)[:budget_after_clean])
        if expand:
            tier = 2
            scan(by_rate(factored_candidates(H, yq, public, query, rng, m, labels=True))[:300])
        self.lookahead_log["extra_candidates"] += state["extra"]
        self.lookahead_log["decisions"] += 1
        if state["best"] is None or state["key"][1] <= 0:
            return None, "none"
        self.gen_hits[dom][state["gen"]] += 1
        return state["best"], f"tier{tier}:{state['gen']}"


# --------------------------------------------------------------------------- regimes and episodes
def _shift(world, x, rng):
    """Shifted follow-up input: longer, with correlated numeric fields decorrelated (records) or mixed
    signs / unsorted (int lists)."""
    x = [dict(r) if isinstance(r, dict) else r for r in x]
    while len(x) < 5:
        x.append(world["sample"](rng, 1)[0])
    if isinstance(x[0], dict):
        nums = [k for k, v in x[0].items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(nums) >= 2:
            vals = [r[nums[-1]] for r in x]
            vals = vals[::-1]
            for r, v in zip(x, vals):
                r[nums[-1]] = v
    else:
        x = [(-v if i % 2 else v) for i, v in enumerate(x)]
    return x


def make_regime_episodes(world, seed, n, regime):
    """A: q1 only. B: q2 from the world's sampler. C: q2 shifted (boundary / decorrelated profile) and
    selected so that the public-only version space disagrees on it (a structural follow-up)."""
    rng = random.Random(f"w25-reg:{regime}:{world['name']}:{seed}")
    out = []
    for t in make_tasks(world, seed, n, active=True):
        if regime == "A":
            out.append(Episode(world["name"], t.public, (t.query,), (t.answer,), t.teacher))
            continue
        tools = episode_grammar(Episode(world["name"], t.public, (t.query,), (t.answer,), t.teacher), world)
        mechs = [tl.fn for tl in tools]
        H0 = None
        for _ in range(40):
            q2 = world["sample"](rng)
            if regime == "C":
                q2 = _shift(world, q2, rng)
            if vkey(q2) in {vkey(x) for x, _ in t.public} | {vkey(t.query)}:
                continue
            try:
                a2 = run(t.teacher, q2)
            except Exception:
                continue
            if regime == "C":
                if H0 is None:
                    from nexus.wave24_v4_core import Searcher
                    from nexus.wave25_factored import MAX_DEPTH, TASK_BUDGET
                    res = Searcher(tuple(t.public), t.query, tools, popper=True, m=meter(TASK_BUDGET),
                                   partial_depth=0, max_depth=MAX_DEPTH).run_to(MAX_DEPTH)
                    H0 = enumerate_H(list(t.public), mechs, res.size, meter(10**12)) if res.size in (1, 2) else []
                if len(set(outputs(H0, q2, meter(10**12)))) < 2:
                    continue
            out.append(Episode(world["name"], t.public, (t.query, q2), (t.answer, a2), t.teacher))
            break
    return out


ARMS = ("revisable", "myopic", "fixed_lambda", "s3_batch", "b_first", "flat_eig")


def run_regime_episode(ep, world, arm, *, rp=None, static_props=None, seed=0):
    m = meter(10**12)
    tools = episode_grammar(ep, world)
    mechs = [t.fn for t in tools]
    obs = list(ep.public)
    rng = random.Random(f"w25-ant:{seed}:{arm}:{vkey(ep.queries[0])}")
    per_q = []
    nexus_arm = arm in ("revisable", "myopic", "fixed_lambda")
    for qi, (q, ans) in enumerate(zip(ep.queries, ep.answers)):
        probes, labels = 0, []
        q_start = m.total
        try:
            ctx = task_context(world, obs, tools)
            res = certify_full(obs, q, tools, world, rp, ctx, m)[0] if nexus_arm else \
                certify_static(obs, q, tools, world, static_props, m)
            initial = res.status
            if qi > 0 and isinstance(rp, AnticipatoryProcedure):
                # the follow-up has been asked and certified once: update the proxy mixture from what V_t did
                rp.qm.observe_followup(res.status == AMBIGUOUS, rp.last_pool_ambiguity)
            while res.status == AMBIGUOUS and probes < PROBE_BUDGET:
                H = enumerate_H(obs, mechs, res.size, m) if res.size in (1, 2) else \
                    [tuple(t.fn for t in p) for p in _reps(res)]
                yq = outputs(H, q, m)
                if nexus_arm:
                    x, label = rp.schedule_probe(H, yq, obs, q, world, rng, m)
                else:
                    x, label = choose_probe({"s3_batch": "s3", "b_first": "b_first", "flat_eig": "flat_eig"}[arm],
                                            H, obs, q, world, rng, m, _reps(res))
                labels.append(label)
                if x is None:
                    break
                probes += 1
                m.charge("oracle_work_units", ORACLE_COST)
                try:
                    y = run(ep.teacher, x)
                except Exception:
                    continue
                obs.append((x, y))
                ctx = task_context(world, obs, tools)
                w0 = m.total
                res = certify_full(obs, q, tools, world, rp, ctx, m)[0] if nexus_arm else \
                    certify_static(obs, q, tools, world, static_props, m)
                if isinstance(rp, AnticipatoryProcedure):
                    rp.cert_work += m.total - w0
                    rp.cert_n += 1
        except WorkExhausted:
            per_q.append(dict(q=qi, status="EXHAUSTED", solved=False, false_certificate=False, probes=probes,
                              work=m.total - q_start))
            continue
        if nexus_arm and res.status == UNIQUE and res.size in (1, 2):
            rp.record_witnesses(world, enumerate_H(obs, mechs, res.size, meter(10**12)))
        per_q.append(dict(q=qi, initial_status=initial, status=res.status,
                          solved=res.status == UNIQUE and vkey(res.answer) == vkey(ans),
                          false_certificate=res.status == UNIQUE and vkey(res.answer) != vkey(ans),
                          probes=probes, work=m.total - q_start, labels=labels))
    if isinstance(rp, AnticipatoryProcedure):
        rp.qm.end_episode(len(ep.queries) - 1)
    return dict(arm=arm, world=ep.world, queries=per_q, work=m.total, probes=sum(q["probes"] for q in per_q),
                solved=sum(q["solved"] for q in per_q), false_certificates=sum(q["false_certificate"] for q in per_q))


def run_seed(seed, *, n_per_world=20, n_val=15, regimes=("A", "B", "C"), arms=ARMS, lam0=LAM0, m_max=M_MAX):
    worlds = {"INT_LIST": ints_world(seed), "RECORDS": records_world(seed)}
    blib = learn_contracts()
    val = make_tasks(worlds["INT_LIST"], seed + 700, n_val, active=False, max_depth=3) + \
        make_tasks(worlds["RECORDS"], seed + 700, n_val, active=False, max_depth=3)
    tycho = tycho_admit_contracts(blib, val, worlds)
    static = {n: default_props(blib, {"F", "S", "Sort", "Agg"} | ({"Map"} if w["maps"] else set()))
              for n, w in worlds.items()}
    learn_cost = sum(learn_contracts().work.values())
    out = dict(seed=seed, regimes={}, tycho_batch=dict(admitted=tycho["admitted"], overhead=tycho["validation_overhead"]),
               learning_cost=learn_cost)
    for reg in regimes:
        eps = [(n, e) for n, w in worlds.items() for e in make_regime_episodes(w, seed + 1100, n_per_world, reg)]
        random.Random(f"w25-reg-order:{seed}:{reg}").shuffle(eps)
        procs = {}
        for arm in arms:
            if arm in ("revisable", "fixed_lambda"):
                procs[arm] = AnticipatoryProcedure(ContractVault(learn_contracts()), seed=seed,
                                                   revisable=arm == "revisable", lam0=lam0, m_max=m_max)
            elif arm == "myopic":
                procs[arm] = ReasoningProcedure(ContractVault(learn_contracts()), seed=seed)
        rows = []
        for i, (n, ep) in enumerate(eps):
            for arm in arms:
                r = run_regime_episode(ep, worlds[n], arm, rp=procs.get(arm), static_props=static[n], seed=seed)
                r.update(seed=seed, regime=reg, episode=i)
                rows.append(r)
        info = {}
        for arm, p in procs.items():
            info[arm] = dict(vault_proved=sum(v.status == PROVED_SOUND for v in p.vault.validity),
                             utility_net=sum(u.observed_work_saved - u.check_cost_total for u in p.vault.utility.values()))
            if isinstance(p, AnticipatoryProcedure):
                info[arm].update(p_cont_final=p.qm.p_cont, weights_final=p.qm.weights(),
                                 trajectory=p.qm.trajectory, lookahead=dict(p.lookahead_log))
        out["regimes"][reg] = dict(rows=rows, procedures=info, episodes=len(eps))
    return out
