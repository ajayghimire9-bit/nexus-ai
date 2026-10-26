"""Wave 30 increment 2 (NOT LOCKED): reporting semantics, matched-strength A0 / A1 / A1b comparison, history
controls, and an evaluator / solver separation, built around the frozen Checker Kernel (unchanged).

Solver interface. A solver sees only `TaskView(public, query, oracle)`. Generator metadata, teacher identity,
hidden answers and family labels ("A0" / "A1-only") live in the evaluator. A test checks this.

Report categories, per task (evaluator):
  * correct: a UNIQUE-labelled answer that equals the hidden answer;
  * exhaustive_certified: kernel `exhaustive_UNIQUE` - a unique query answer within the explicitly declared
    grammar (tool specs), depth bound, representation set and the kernel's execution semantics;
  * AGREEMENT_AMONG_PROPOSALS: kernel `proposal_relative_UNIQUE` - agreement only within the examined proposal
    set. It is never counted as exhaustive certification;
  * wrong_teacher_outside_scope: a UNIQUE label whose answer differs from the teacher, where the teacher is not
    expressible in the declared scope. The certificate is still valid relative to its scope;
  * wrong_teacher_inside_scope: the same with the teacher inside the scope. For an exhaustive label this would
    mean a kernel or scope defect;
  * invalid_claim: the prover claimed UNIQUE but the kernel did not confirm it;
  * ambiguous: kernel AMBIGUOUS, with concrete witnesses - two observation-consistent programs with distinct
    query answers, each checked by the kernel (`candidate_fails` excluded). The kernel's k is exact for an
    exhaustive scope and "at least k" for a proposal scope;
  * abstain: incomplete, unsupported or budget-exhausted evidence, with a reason.

Matched strength. A1b-full uses exactly A1's declared scope and the kernel's exhaustive label; its learned prior
may only reorder enumeration (and so which ambiguity witnesses, and hence probes, appear first: both arms stop
a level early once two disagreeing witnesses exist, then probe). A1b-proposal (scope truncated by the prior,
escalating to full if nothing fits) is reported separately as a performance / coverage trade-off.

Costs (one meter, categories): source_learning, proposal_generation, scope_construction, prover, probe_design +
oracle, lemma_construction, failed_proposal (all work of a proposal search that had to escalate), checker
(kernel chains checked), plus wall-clock seconds per task.
"""
from __future__ import annotations

import hashlib
import random
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from nexus import checker_kernel as K
from nexus.wave24_domains import vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import AMBIGUOUS, NONE_FOUND, UNIQUE, Searcher, meter
from nexus.wave25_factored import run
from nexus.wave26_phase4 import C_ORACLE, PROBE_BUDGET
from nexus.wave29_core import choose_verify, violated
from nexus.wave30_arms import (DEPTH, FAMILIES, PROVER_BUDGET, WakeSleepPrior, a0_tools, a1_tools, family,
                               post_spec, spec_of, stream)

ROOT = Path(__file__).resolve().parents[2]
KERNEL_PIN_COMMIT = "e234898"


# --------------------------------------------------------------------------- kernel integrity (runner-side)
def verify_kernel_pin():
    """Compare the kernel file on disk with the pin stored in the git object of commit KERNEL_PIN_COMMIT (not the
    working tree). Raises if they differ or git is unavailable. AGENTS.md alone is not an enforcement boundary."""
    pinned = subprocess.run(["git", "-C", str(ROOT), "show", f"{KERNEL_PIN_COMMIT}:src/nexus/checker_kernel.sha256"],
                            capture_output=True, text=True, check=True).stdout.split()[0]
    committed = subprocess.run(["git", "-C", str(ROOT), "show", f"{KERNEL_PIN_COMMIT}:src/nexus/checker_kernel.py"],
                               capture_output=True, check=True).stdout
    disk = (ROOT / "src" / "nexus" / "checker_kernel.py").read_bytes()
    if hashlib.sha256(committed).hexdigest() != pinned or hashlib.sha256(disk).hexdigest() != pinned:
        raise RuntimeError("checker kernel does not match its pinned hash; refusing to run")
    loaded = Path(K.__file__).resolve()
    if loaded != (ROOT / "src" / "nexus" / "checker_kernel.py").resolve():
        raise RuntimeError(f"checker kernel loaded from an unexpected path: {loaded}")
    return pinned


# --------------------------------------------------------------------------- solver-side
@dataclass(frozen=True)
class TaskView:
    public: tuple
    query: object
    oracle: object


def _searcher_round(public, query, tools, m, *, early):
    s = Searcher(tuple(public), query, tools, popper=True, m=meter(PROVER_BUDGET), partial_depth=0, max_depth=DEPTH,
                 early_ambiguity=early)
    r = s.run_to(DEPTH)
    hyps = list(r.hypotheses) if r.status in (UNIQUE, AMBIGUOUS) else []
    status = r.status
    if hyps and status == UNIQUE and r.size < DEPTH:
        try:
            found = s.level()                      # Occam-margin shell (k_min + 1)
            for p, q in found.values():
                hyps.append((tuple(t.name for t in p), q, p))
        except WorkExhausted:
            status = "EXHAUSTED"
    m.charge("prover", s.m.total)
    seen, merged = set(), []
    for h in hyps:
        if vkey(h[1]) not in seen:
            seen.add(vkey(h[1]))
            merged.append(h)
    if status not in (UNIQUE, AMBIGUOUS, NONE_FOUND):
        return "EXHAUSTED", merged
    if not merged:
        return NONE_FOUND, []
    return (UNIQUE if len(seen) == 1 else AMBIGUOUS), merged


PROBE_DESIGN = {"mode": "early"}     # "early" (Wave 30 inc 2) | "complete" (order-invariant, inc 3)


def _canon(hyps):
    return sorted(hyps, key=lambda h: (K.key([spec_of(t.fn) for t in h[2]]), K.key(h[1])))


def prove2(view, tools, kind, m, rng):
    """Probe while ambiguous (early-stopped levels expose two disagreeing witnesses). A round that ends UNIQUE is
    complete (early stopping only triggers on a disagreement). Returns (evidence or None, prover status,
    witness evidences, public used, probes)."""
    public = list(view.public)
    probes = 0
    complete = PROBE_DESIGN["mode"] == "complete"
    if complete:
        # order-invariant prover: canonical enumeration order, so class representatives, probe design and hence the
        # final observations depend only on (observations, declared scope), never on a proposer's candidate order
        tools = sorted(tools, key=lambda t: K.key(spec_of(t.fn)))
    while True:
        status, hyps = _searcher_round(public, view.query, tools, m, early=not complete)
        if complete:
            hyps = _canon(hyps)          # order-invariant: every class representative, canonical order
        if status != AMBIGUOUS or probes >= PROBE_BUDGET or view.oracle is None:
            break
        chains = [tuple(t.fn for t in h[2]) for h in hyps]
        v = choose_verify(chains, [], [x for x, _ in public] + [view.query], rng, _Sub(m, "probe_design"))
        if v is None:
            break
        m.charge("oracle", C_ORACLE)
        probes += 1
        try:
            public.append((v, view.oracle(v)))
        except Exception:
            break
    # an early-ambiguity round that ends UNIQUE is complete; an AMBIGUOUS one already holds two witnesses
    if status in (NONE_FOUND, "EXHAUSTED"):
        return None, status, [], public, probes
    specs = [spec_of(t.fn) for t in tools]
    lemmas = []
    ys = [y for _, y in public]
    lm = _Sub(m, "lemma_construction")
    for i, t in enumerate(tools):
        for post in violated(t.fn, public, lm):
            ps = post_spec(post)
            j = next((j for j, y in enumerate(ys) if K.violates(ps, y)), None)
            if j is not None:
                lemmas.append({"tool": i, "post": ps, "public_index": j})

    def ev_for(h):
        return {"version": 1, "public": [[x, y] for x, y in public], "query": view.query, "claimed_answer": h[1],
                "candidate": [spec_of(t.fn) for t in h[2]],
                "scope": {"kind": kind, "tools": specs, "max_depth": DEPTH}, "lemmas": lemmas,
                "trace": {"prover_status": status, "probes": probes, "lemmas": len(lemmas)}}
    return ev_for(hyps[0]), status, [ev_for(h) for h in hyps[1:3]], public, probes


class _Sub:
    """Meter view charging everything to one category of the parent meter."""

    def __init__(self, m, cat):
        self.m, self.cat = m, cat

    def charge(self, _cat, n=1):
        self.m.charge(self.cat, n)


def solve(arm, view, *, prior=None, seed=0, label=""):
    """arm in A0, A1, A1b-full, A1b-proposal. Sees only `view`."""
    m = meter(10**12)
    # probe-design randomness is seeded by the TASK only (not the arm), so arms at matched scope see identical
    # candidate probe inputs (increment 2 seeded by arm: a fairness defect found during reconciliation)
    rng = random.Random(f"w30h:{seed}:{label.split(':')[-1]}" if PROBE_DESIGN["mode"] == "complete"
                        else f"w30h:{arm}:{seed}:{label}")
    t0 = time.perf_counter()
    inputs = [x for x, _ in view.public] + [view.query]
    tools = a0_tools(inputs) if arm == "A0" else a1_tools(inputs)
    m.charge("scope_construction", len(tools))
    scope = "full"
    try:
        if arm == "A1b-full":
            m.charge("proposal_generation", len(FAMILIES))
            rank = {f: -v for f, v in prior.c.items()}
            tools = sorted(tools, key=lambda t: (rank.get(family(t.fn), 0), t.name))
            ev, st, wit, pub, probes = prove2(view, tools, "exhaustive", m, rng)
        elif arm == "A1b-proposal":
            m.charge("proposal_generation", len(FAMILIES))
            fams = prior.proposal()
            sub = [t for t in tools if family(t.fn) in fams]
            pm = meter(10**12)
            ev, st, wit, pub, probes = prove2(view, sub, "proposal", pm, rng)
            scope = "proposal"
            if ev is None:
                m.charge("failed_proposal", pm.total)
                ev, st, wit, pub, probes2 = prove2(view, tools, "exhaustive", m, rng)
                probes += probes2
                scope = "escalated"
            else:
                for k, v in pm.counts.items():
                    m.charge(k, v)
        else:
            ev, st, wit, pub, probes = prove2(view, tools, "exhaustive", m, rng)
    except WorkExhausted:
        ev, st, wit, probes = None, "EXHAUSTED", [], 0
    kt0 = time.perf_counter()
    verdict = K.check(ev) if ev is not None else dict(label="ABSTAIN", reason=f"prover_{st}", chains_checked=0)
    m.charge("checker", verdict.get("chains_checked", 0))
    witnesses = []
    if verdict["label"] == "AMBIGUOUS":
        for w in [ev] + wit:
            wv = K.check(w)
            if wv["label"] == "AMBIGUOUS":                  # the candidate itself fits (else candidate_fails)
                witnesses.append(K.key(w["claimed_answer"]))
                m.charge("checker", wv.get("chains_checked", 0))
    kernel_s = time.perf_counter() - kt0
    uniq = verdict["label"] in ("exhaustive_UNIQUE", "proposal_relative_UNIQUE")
    if prior is not None and arm in ("A1b-full", "A1b-proposal") and prior.online and uniq:
        prior.sleep({family(t.fn) for t in tools if K.key(spec_of(t.fn)) in {K.key(s) for s in ev["candidate"]}})
        m.charge("source_learning", 1)
    if KEEP_EVIDENCE["on"] and ev is not None:
        KEEP_EVIDENCE["items"].append(ev)
    return dict(arm=arm, label=verdict["label"], kernel_k=verdict.get("k"), reason=verdict.get("reason"),
                answer=ev["claimed_answer"] if uniq else None, prover_status=st, witnesses=sorted(set(witnesses)),
                scope=scope, scope_kind=(ev or {}).get("scope", {}).get("kind"), probes=probes, work=m.total,
                work_by=dict(m.counts), wall_s=time.perf_counter() - t0, kernel_s=kernel_s,
                scope_specs=[K.key(s) for s in (ev or {}).get("scope", {}).get("tools", [])] if ev else None,
                n_tools=len(tools))


KEEP_EVIDENCE = {"on": False, "items": []}


class FrozenPrior(WakeSleepPrior):
    def __init__(self, counts=None, online=False):
        super().__init__(FAMILIES)
        if counts:
            self.c = Counter(counts)
        self.online = online


# --------------------------------------------------------------------------- evaluator
def evaluate(task, res):
    """Evaluator-only: compares with the hidden answer and the teacher's specs."""
    teacher = [K.key(s) for s in task["teacher_spec"]]
    in_scope = res["scope_specs"] is not None and len(teacher) <= DEPTH and set(teacher) <= set(res["scope_specs"])
    uniq = res["label"] in ("exhaustive_UNIQUE", "proposal_relative_UNIQUE")
    correct = uniq and K.key(res["answer"]) == K.key(task["answer"])
    cat = ("exhaustive_certified" if res["label"] == "exhaustive_UNIQUE" else
           "AGREEMENT_AMONG_PROPOSALS" if res["label"] == "proposal_relative_UNIQUE" else
           "ambiguous" if res["label"] == "AMBIGUOUS" else "abstain")
    wrong = None
    if uniq and not correct:
        wrong = "wrong_teacher_inside_scope" if in_scope else "wrong_teacher_outside_scope"
    invalid = res["prover_status"] == UNIQUE and not uniq
    out = {k: v for k, v in res.items() if k != "scope_specs"}
    out.update(category=cat, correct=correct, wrong=wrong, invalid_claim=invalid, teacher_in_scope=in_scope,
               family=task["family"], domain=task["domain"],
               ambiguity_reported=(f"exactly {res['kernel_k']}" if res["label"] == "AMBIGUOUS" and
                                   res["scope_kind"] == "exhaustive" else
                                   f"at least {res['kernel_k']}" if res["label"] == "AMBIGUOUS" else None))
    return out


def run_stream(split_seed, arm, prior=None, n=16):
    rows = []
    for i, t in enumerate(stream(split_seed, n=n)):
        view = TaskView(public=tuple(t["public"]), query=t["query"], oracle=lambda x, c=t["teacher"]: run(c, x))
        rows.append(evaluate(t, solve(arm, view, prior=prior, seed=split_seed, label=f"{arm}:{i}")))
    return rows


def summarise(rows):
    cats = Counter(r["category"] for r in rows)
    wb = Counter()
    for r in rows:
        wb.update(r["work_by"])
    return dict(n=len(rows), correct=sum(r["correct"] for r in rows),
                exhaustive_certified=cats.get("exhaustive_certified", 0),
                agreement_among_proposals=cats.get("AGREEMENT_AMONG_PROPOSALS", 0),
                correct_exhaustive=sum(r["correct"] and r["category"] == "exhaustive_certified" for r in rows),
                wrong_outside_scope=sum(r["wrong"] == "wrong_teacher_outside_scope" for r in rows),
                wrong_inside_scope=sum(r["wrong"] == "wrong_teacher_inside_scope" for r in rows),
                invalid_claims=sum(r["invalid_claim"] for r in rows),
                ambiguous=cats.get("ambiguous", 0),
                ambiguous_with_2_verified_witnesses=sum(r["category"] == "ambiguous" and len(r["witnesses"]) >= 2
                                                        for r in rows),
                abstain=cats.get("abstain", 0),
                abstain_reasons=dict(Counter(r["reason"] for r in rows if r["category"] == "abstain")),
                work=sum(r["work"] for r in rows), work_by=dict(wb),
                wall_s=round(sum(r["wall_s"] for r in rows), 1), kernel_s=round(sum(r["kernel_s"] for r in rows), 1),
                scope=dict(Counter(r["scope"] for r in rows)),
                by_family={f: dict(n=sum(r["family"] == f for r in rows),
                                   correct=sum(r["correct"] for r in rows if r["family"] == f))
                           for f in ("A0", "A1")})
