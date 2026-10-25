"""Wave 24 v4 Track B: held-out MBPP with a Tycho-gated helper library and a docstring twin fuzzer.

Reused unchanged: `wave24_mbpp` (sandboxed assert runner, prompts, standalone / verified-sampling arms,
StrategyAllocator, propose), `wave24_helpers.HelperLibrary` (verified helpers, execution-only composition,
anti-unification sleep), `wave24_mbpp_evolve.MbppWakeSleep` (wake-sleep accounting) and the dev library
artifact trained in v3 on the dev split only.

Data (all outcome-blind hash orders over the committed split):
  * eval  - MBPP eval split MINUS the 32 tasks consumed by v3 ("mbpp-v3-eval" order), re-ordered by
            sha256("mbpp-v4-eval:<id>"), first N. No solver has run on these tasks.
  * val   - MBPP dev split MINUS the 58 v3 training tasks, ordered by "mbpp-v4-val", first N_VAL;
            used once, only for the Tycho admission of the library (never for training).
Arms: standalone (unverified 1-shot), verified_sampling (k=2), symbolic (execution-only helper
composition, no LLM), nexus_v4 (Tycho-gated library + learned follow-up allocator + online growth from
public tests + metabolic sleep + docstring twin fuzz check on sampled follow-up candidates).
"""
from __future__ import annotations

from nexus.wave24_helpers import HelperLibrary
from nexus.wave24_mbpp import (Meter, StrategyAllocator, _ask, extract_code, grade, load_namespace,
                               load_tasks, method_nexus_evolved, ordered, passes, _traced, CALL_LINE_BUDGET)
from nexus.wave24_mbpp_evolve import MbppWakeSleep

V3_EVAL_SALT, V3_EVAL_N = "mbpp-v3-eval", 32
V3_TRAIN_SALT, V3_TRAIN_N = "mbpp-v3-train", 58
V4_EVAL_SALT, V4_VAL_SALT = "mbpp-v4-eval", "mbpp-v4-val"
N_FUZZ = 6


def eval_tasks(n):
    used = {t.task_id for t in ordered(load_tasks("eval"), V3_EVAL_SALT)[:V3_EVAL_N]}
    return ordered([t for t in load_tasks("eval") if t.task_id not in used], V4_EVAL_SALT)[:n]


def val_tasks(n):
    used = {t.task_id for t in ordered(load_tasks("dev"), V3_TRAIN_SALT)[:V3_TRAIN_N]}
    return ordered([t for t in load_tasks("dev") if t.task_id not in used], V4_VAL_SALT)[:n]


# --------------------------------------------------------------------------- Tycho gate (no LLM)
def tycho_library(library, tasks, *, work_per_solve):
    """Net validation benefit of offering the library: correct execution-only compositions save an
    estimated `work_per_solve` (dev mean NEXUS work per correct solve) each; every unit of retrieval and
    composition work on the validation tasks is charged; one wrong composition blocks admission."""
    m = Meter()
    hits = correct = wrong = context_hits = context_chars = 0
    for t in tasks:
        hit = library.compose(t, m)
        if hit is not None:
            hits += 1
            if grade(hit, t):          # validation data: graded on all of its tests
                correct += 1
            else:
                wrong += 1
        extra, _, used = library.context(t, m)
        if used:
            context_hits += 1
            context_chars += len(extra)
    saving = correct * work_per_solve
    cost = m.total + context_chars // 4          # retrieval/composition work + extra prompt tokens (~4 chars)
    net = saving - cost
    return dict(tasks=len(tasks), composition_hits=hits, correct_hits=correct, wrong_hits=wrong,
                context_hits=context_hits, saving=saving, cost=cost, net_benefit=net,
                admitted=net > 0 and wrong == 0)


# --------------------------------------------------------------------------- docstring twin fuzzer
def _mutate(v):
    if isinstance(v, bool):
        return [not v]
    if isinstance(v, int):
        return [v + 1, v - 1, v * 2]
    if isinstance(v, float):
        return [v + 1.0, -v]
    if isinstance(v, str):
        return [v[::-1], v + v[:1]] if v else ["a"]
    if isinstance(v, list):
        return [list(reversed(v)), v[:-1], v + v[:1]] if v else [[0]]
    if isinstance(v, tuple):
        return [tuple(reversed(v)), v[:-1]] if v else [(0,)]
    return []


def fuzz_inputs(args, n=N_FUZZ):
    """Generic one-argument mutations of the public test's literal arguments."""
    out = []
    for i, a in enumerate(args):
        for b in _mutate(a):
            new = tuple(b if j == i else x for j, x in enumerate(args))
            if new != tuple(args) and new not in out:
                out.append(new)
    return out[:n]


def _call(ns, func, args, m):
    if ns is None or func not in ns:
        return ("error",)
    try:
        return ("ok", repr(_traced(lambda: ns[func](*args), m, CALL_LINE_BUDGET)))
    except BaseException as exc:   # noqa: BLE001 - candidate faults are data
        if isinstance(exc, KeyboardInterrupt):
            raise
        return ("raise", type(exc).__name__)


def twin_prompt(task):
    t = task.public[0]
    return (f"{task.text}\nWrite the function `{t.func}` taking {len(t.args)} argument(s). "
            f"Do not include tests.")


def twin_check(task, answer, engine, m):
    """Independent docstring-only twin; returns (verdict, llm_work, disagreement inputs).

    verdict: agree | disagree (twin passes the public test and differs on a fuzzed input) |
             no_twin (twin unusable) | no_fuzz (no literal arguments to fuzz).
    """
    t = task.public[0]
    fz = fuzz_inputs(t.args)
    if not fz:
        return "no_fuzz", 0, []
    text, w = _ask(engine, twin_prompt(task), temperature=0.0, seed=11, purpose=f"mbpp:{task.task_id}:twin")
    code = extract_code(text, t.func)
    if code is None or not passes(code, task.public, m, setup=task.setup)[0]:
        return "no_twin", w, []
    a_ns = load_namespace(answer, m, setup=task.setup)
    b_ns = load_namespace(code, m, setup=task.setup)
    diff = [x for x in fz if _call(a_ns, t.func, x, m) != _call(b_ns, t.func, x, m)]
    return ("disagree" if diff else "agree"), w, [repr(x) for x in diff[:3]]


class TwinWakeSleep(MbppWakeSleep):
    """MbppWakeSleep whose wake applies the docstring twin fuzz check to SAMPLED follow-up candidates.

    Greedy and helper-composition answers are kept as they are; a follow-up (resample / CEGIS) candidate
    is withheld (abstain) when a public-passing independent twin disagrees with it on a fuzzed input.
    Twin tokens are charged to the task. Online admission uses the public test only.
    """

    def __init__(self, *a, twin=True, **kw):
        super().__init__(*a, **kw)
        self.twin = twin

    def wake(self, task):
        row = method_nexus_evolved(task, self.engine, self.library, allocator=self.allocator, k=self.k,
                                   online=False, explore=self.explore)
        row["method"] = "nexus_v4"
        row["twin"] = "skipped"
        if self.twin and row["answer"] is not None and row["stage"] not in ("greedy", "greedy+lib",
                                                                           "helper_composition"):
            m = Meter()
            verdict, w, diff = twin_check(task, row["answer"], self.engine, m)
            row.update(twin=verdict, twin_disagreements=diff)
            row["work"] += w + m.total
            row["llm_work"] += w
            row["llm_calls"] += int(w > 0)
            if verdict == "disagree":
                row.update(answer=None, plausible=False, correct=False, stage="twin_abstain")
        self.wake_work += row["work"]
        self.since_sleep += row["work"]
        if row["llm_calls"]:
            self.llm_call_work.append(row["llm_work"] / row["llm_calls"])
        row["admitted"] = row["answer"] is not None
        if row["admitted"]:
            self.library.add_solution(task, row["answer"], verified_on="public", tests=task.public)
        self.rows.append(row)
        if len(self.rows) % self.sleep_every == 0:
            self.sleep()
        return row


def method_symbolic(task, library):
    """Pure symbolic arm: execution-only helper composition over the library, no LLM."""
    m = Meter()
    hit = library.compose(task, m)
    return dict(method="symbolic", task_id=task.task_id, plausible=hit is not None, correct=grade(hit, task),
                work=m.total, llm_work=0, llm_calls=0, stage="helper_composition" if hit else "none", answer=hit)


def load_library(blob):
    return HelperLibrary.from_json(blob["library"]), StrategyAllocator(blob["allocator"])
