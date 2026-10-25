"""Wake-sleep self-evolution on the natural MBPP task stream (v3 Piece B).

Wake: each task is attacked by nexus_evolved (execution-based helper composition, then Qwen
proposals whose follow-up strategy - resample vs counterexample-guided repair - comes from the
learned StrategyAllocator; on the dev stream both strategies are explored on every failure state
and their charged outcomes train the allocator); a verified answer is admitted to the library. On the DEV stream admission re-checks the answer on all of that dev task's tests (dev
labels are training data, charged to training work); on the held-out EVAL stream admission uses
only the public test that already verified the answer - hidden tests are never consulted.
Sleep (every `sleep_every` wake tasks) runs on a governed metabolic allowance
(`metabolic_share` x wake work since the previous sleep, carried over):
  1. anti-unification rounds (wave24_helpers.HelperLibrary.sleep): recurring alpha-normalised
     subtrees across distinct verified solutions become `def helper_k`, promoted only if every
     refactored solution re-passes its verifying tests and description length drops; a second
     round abstracts over code that already calls helper_k (layer 2+);
  2. targeted residual bridges: the most recent unsolved wake task is re-attacked once with the
     grown library when the allowance covers a full attempt; a verified bridge enters the library
     but is never counted as a first-attempt solve.
All sleep work (re-verification line events + bridge LLM tokens) is charged.
"""
from __future__ import annotations

from nexus.wave24_helpers import HelperLibrary
from nexus.wave24_mbpp import Meter, StrategyAllocator, method_nexus_evolved, passes, propose


class MbppWakeSleep:
    def __init__(self, engine, library=None, *, allocator=None, sleep_every=10, metabolic_share=0.15, k=3,
                 admit="public", abstraction_rounds=2, explore=False):
        self.engine = engine
        self.library = library if library is not None else HelperLibrary()
        self.allocator = allocator if allocator is not None else StrategyAllocator()
        self.explore = explore
        self.sleep_every, self.share, self.k = sleep_every, metabolic_share, k
        self.admit, self.rounds = admit, abstraction_rounds
        self.rows, self.sleeps, self.bridges = [], [], []
        self.wake_work = self.sleep_work = self.admission_work = 0
        self.since_sleep, self.allowance = 0, 0.0
        self.llm_call_work = []

    def wake(self, task):
        row = method_nexus_evolved(task, self.engine, self.library, allocator=self.allocator, k=self.k,
                                   online=False, explore=self.explore)
        self.wake_work += row["work"]
        self.since_sleep += row["work"]
        if row["llm_calls"]:
            self.llm_call_work.append(row["llm_work"] / row["llm_calls"])
        admitted = False
        if row["answer"] is not None:
            if self.admit == "all":
                m = Meter()
                admitted, _ = passes(row["answer"], task.all_tests, m, setup=task.setup)
                self.admission_work += m.total
                tests = task.all_tests
            else:
                admitted, tests = True, task.public
            if admitted:
                self.library.add_solution(task, row["answer"], verified_on=self.admit, tests=tests)
        row["admitted"] = admitted
        self.rows.append(row)
        if len(self.rows) % self.sleep_every == 0:
            self.sleep()
        return row

    def sleep(self):
        self.allowance += self.share * self.since_sleep
        self.since_sleep = 0
        meter = Meter()
        promoted = []
        for _ in range(self.rounds):
            if self.allowance - meter.total <= 0:
                break
            got = self.library.sleep(meter, budget=max(1, int(self.allowance - meter.total)))
            promoted += got
            if not got:
                break
        bridge = self._bridge(meter)
        self.allowance -= meter.total
        self.sleep_work += meter.total
        self.sleeps.append(dict(after=len(self.rows), work=meter.total, promoted=[p["helper"] for p in promoted],
                                bridge=bridge, library=len(self.library.helpers)))

    def _bridge(self, meter):
        todo = [r for r in self.rows[-2 * self.sleep_every:] if r["answer"] is None and not r.get("bridged")]
        if not todo or not self.llm_call_work:
            return None
        est = self.k * sum(self.llm_call_work) / len(self.llm_call_work)
        if self.allowance - meter.total < est:
            return None
        r = todo[-1]
        r["bridged"] = True
        task = self._task(r["task_id"])
        answer, info = propose(task, self.engine, k=self.k, meter=meter, library=self.library,
                               allocator=self.allocator)
        meter.charge(info["llm_work"])
        ok = False
        if answer is not None:
            if self.admit == "all":
                ok, _ = passes(answer, task.all_tests, meter, setup=task.setup)
                tests = task.all_tests
            else:
                ok, tests = True, task.public
            if ok:
                self.library.add_solution(task, answer, verified_on=f"bridge-{self.admit}", tests=tests)
        rec = dict(task_id=task.task_id, verified=ok, work=info["work"])
        self.bridges.append(rec)
        return rec

    def _task(self, task_id):
        from nexus.wave24_mbpp import load_tasks
        if not hasattr(self, "_by_id"):
            self._by_id = {t.task_id: t for t in load_tasks()}
        return self._by_id[task_id]

    def report(self):
        solved = [r for r in self.rows if r["answer"] is not None]
        return dict(tasks=len(self.rows), plausible=len(solved), correct=sum(r["correct"] for r in self.rows),
                    wake_work=self.wake_work, sleep_work=self.sleep_work, admission_work=self.admission_work,
                    total_work=self.wake_work + self.sleep_work + self.admission_work,
                    stages={s: sum(r["stage"] == s for r in self.rows) for s in {r["stage"] for r in self.rows}},
                    sleeps=self.sleeps, bridges=self.bridges, library=self.library.summary(),
                    allocator=self.allocator.to_json())
