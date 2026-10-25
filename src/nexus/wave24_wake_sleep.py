"""Wake-sleep self-evolution with hierarchical compression and a shadow verification gate.

Wake: solve stream tasks; log certified derivations (tool objects) and unsolved residuals.
Sleep (every `sleep_every` wake tasks, charged on a metabolic meter):
  1. refactor logged derivations with already-promoted abstractions, then count
     adjacent sub-derivations recurring across DISTINCT tasks -> candidates
     (a candidate built from abstractions is one layer higher: macro-of-macro,
     skeleton-in-macro);
  2. shadow replay: each candidate re-solves the replay buffer (recent tasks
     that contain it + recent unsolved residuals); it is promoted only if total
     work strictly drops and no buffer task loses its solve. Residuals that the
     candidate solves are recorded as resolved bridges.
No blind idle rollouts are used. Every shadow solve's work is charged.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from nexus.wave24_agi_suite import UNIQUE, grade, macro_tool, solve
from nexus.wave24_domains import Task, vkey
from nexus.wave24_skeletons import ELEM_FUNCS, FOLDS, SkeletonSpec, TYPE_PREDS, instantiate


# --------------------------------------------------------------------------- idiom streams
def _param_free_specs(domain):
    specs = [SkeletonSpec("MAP", (f,), ()) for f in ELEM_FUNCS]
    specs += [SkeletonSpec("FOLD", (f,), ()) for f in FOLDS]
    specs += [SkeletonSpec("FILTER", (p,), ("drop",)) for p in TYPE_PREDS]
    specs += [SkeletonSpec("ITERATE", (t.name,), ()) for t in domain.tools]
    return specs


def _step_tools(domain, with_skeletons):
    by_name = {t.name: t for t in domain.tools}
    tools = list(domain.tools)
    if with_skeletons:
        tools += [instantiate(s, by_name) for s in _param_free_specs(domain)]
    return tools


def _defined(chain, xs):
    out = []
    for x in xs:
        v = x
        for t in chain:
            v = t(v)
        out.append(v)
    return out


def universal_idiom_pool(seed, *, n=8):
    """Cross-family regularities: generic skeleton compositions shared by every family (seeded).

    Declared world assumption: real data work reuses the same generic idioms
    (clean -> project -> aggregate) across very different data families.
    """
    rng = random.Random(f"universal-idioms:{seed}")
    specs = [SkeletonSpec("MAP", (f,), ()) for f in ELEM_FUNCS] + [SkeletonSpec("FOLD", (f,), ()) for f in FOLDS] \
        + [SkeletonSpec("FILTER", (p,), ("drop",)) for p in TYPE_PREDS]
    pool = []
    while len(pool) < n:
        k = rng.choice((2, 3))
        chain = [rng.choice([x for x in specs if x.type != "FOLD"]) for _ in range(k - 1)] + [rng.choice(specs)]
        if len({c.name for c in chain}) == k and chain not in pool:
            pool.append(chain)
    return pool


def generic_tool(tool):
    """True iff a tool mentions no domain primitive (only generic skeletons), so it can cross families."""
    if tool.kind == "skeleton":
        return not tool.name.startswith(("ITERATE", "GUARD"))
    if tool.kind == "macro":
        return all(generic_tool(c) for c in tool.children)
    return False


def idiom_library(domain, seed, *, n=4, with_skeletons=True, attempts=600, universal_share=0.5):
    """Per-seed latent idioms: half drawn from the cross-family pool (when valid here), half family-specific."""
    rng = random.Random(f"idioms:{domain.name}:{seed}")
    tools = _step_tools(domain, with_skeletons)
    probes = domain.inputs(rng, 8)
    idioms = []
    if with_skeletons and universal_share > 0:
        pool = universal_idiom_pool(seed)
        rng.shuffle(pool)
        for spec_chain in pool:
            if len(idioms) >= int(n * universal_share):
                break
            chain = [instantiate(sp) for sp in spec_chain]
            try:
                outs = _defined(chain, probes)
            except Exception:
                continue
            if len({vkey(o) for o in outs}) >= 3 and not any(vkey(o) == vkey(x) for o, x in zip(outs, probes)):
                idioms.append(chain)
    for _ in range(attempts):
        chain = [rng.choice(tools) for _ in range(rng.choice((2, 3)))]
        if any(a.name == b.name for a, b in zip(chain, chain[1:])):
            continue
        try:
            outs = _defined(chain, probes)
        except Exception:
            continue
        if len({vkey(o) for o in outs}) < 3 or any(vkey(o) == vkey(x) for o, x in zip(outs, probes)):
            continue
        if any([t.name for t in chain] == [t.name for t in i] for i in idioms):
            continue
        idioms.append(chain)
        if len(idioms) == n:
            break
    return idioms


def idiom_stream(domain, seed, n_tasks, idioms, *, n_public=3, attempts=60):
    """Tasks composed from the latent idioms (+ an occasional primitive): recurring structure."""
    rng = random.Random(f"stream:{domain.name}:{seed}")
    prims = list(domain.tools)
    tasks = []
    for _ in range(n_tasks * attempts):
        kind = rng.random()
        if kind < 0.25:
            chain = list(rng.choice(idioms))
        elif kind < 0.7:
            a, b = rng.sample(idioms, 2) if len(idioms) >= 2 else (idioms[0], idioms[0])
            chain = list(a) + list(b)
        else:
            chain = list(rng.choice(idioms)) + [rng.choice(prims)]
        xs = domain.inputs(rng, n_public + 1)
        try:
            ys = _defined(chain, xs)
        except Exception:
            continue
        if len({vkey(y) for y in ys[:-1]}) < 2 or all(vkey(x) == vkey(y) for x, y in zip(xs, ys)):
            continue
        tasks.append(Task(domain.name, tuple(zip(xs[:-1], ys[:-1])), xs[-1], ys[-1], tuple(t.name for t in chain)))
        if len(tasks) == n_tasks:
            break
    return tasks


# --------------------------------------------------------------------------- wake-sleep
@dataclass
class WakeEntry:
    task: Task
    solved: bool
    certified: bool
    work: int
    chain: tuple


class WakeSleep:
    def __init__(self, learner, *, sleep_every=6, buffer=8, max_candidates=4, layer_cap=None, budget=12000,
                 metabolic_share=0.15):
        self.L = learner
        self.sleep_every, self.buffer, self.max_candidates = sleep_every, buffer, max_candidates
        self.layer_cap, self.budget = layer_cap, budget
        self.log = []
        self.promotions, self.rejections, self.resolved, self.bridges = [], [], [], []
        self.sleep_work = 0
        self.metabolic_share = metabolic_share
        self.wake_work_since_sleep = 0
        self.allowance = 0

    def wake(self, task):
        r = self.L.solve(task, budget=self.budget)
        self.wake_work_since_sleep += r.work
        ok = r.status == UNIQUE and r.certificate_valid is True
        self.log.append(WakeEntry(task, grade(task, r), ok, r.work, tuple(getattr(r, "_chain", ())) if ok else ()))
        if len(self.log) % self.sleep_every == 0:
            self.sleep()
        return r

    def _refactor(self, chain):
        """Greedy rewrite of a derivation with promoted abstractions (longest first)."""
        macros = sorted(self.L.macros.values(), key=lambda m: -len(m.children))
        chain = list(chain)
        changed = True
        while changed:
            changed = False
            for m in macros:
                k = len(m.children)
                for i in range(len(chain) - k + 1):
                    if [t.name for t in chain[i:i + k]] == [c.name for c in m.children]:
                        chain[i:i + k] = [m]
                        changed = True
                        break
        return chain

    def _budget(self):
        return int(max(1, min(self.budget, self.allowance)))

    def _spend(self, work):
        self.sleep_work += work
        self.allowance -= work

    def shadow_solve(self, task, extra, budget=None):
        tools = self.L.toolset() + self.L.task_skeletons(task) + list(extra)
        forces = {**self.L.forces_all(), **{t.name: "F_COMPOSITE" for t in tools}}
        forces.update(self.L.forces)
        return solve(task, tools, budget=budget or self.budget, learned=True, model=self.L.model,
                     policy=self.L.policy if self.L.policy_prune else None, forces=forces, record=False,
                     laws=self.L.laws, predict=self.L.predict_on, fault_memory=dict(self.L.fault_memory))

    def bridge_residuals(self, recent, k=1):
        """Targeted residual bridges: re-attack recent unsolved wake tasks with a governed 2x budget.

        A found bridge adds a certified derivation to the compression pool and is
        recorded as resolved; it is NOT counted as a first-attempt stream solve.
        """
        todo = [e for e in recent if not e.certified and not getattr(e, "bridged", False)][-k:]
        for e in todo:
            if self.allowance < self.budget:   # a bridge needs a full per-task budget of headroom
                return
            e.bridged = True
            tools = self.L.toolset() + self.L.task_skeletons(e.task)
            forces = {**{t.name: "F_COMPOSITE" for t in tools}, **self.L.forces}
            r = solve(e.task, tools, budget=self._budget(), learned=True, model=self.L.model, forces=forces,
                      record=False, laws=self.L.laws, predict=self.L.predict_on, fault_memory=dict(self.L.fault_memory))
            self._spend(r.work)
            if r.status == UNIQUE and r.certificate_valid is True:
                e.certified, e.chain = True, tuple(r._chain)
                self.resolved.append(e.task)
                self.bridges.append(dict(witness=list(r.witness), work=r.work))

    def sleep(self):
        """Governed sleep: allowance = metabolic_share x wake work since the last sleep (carried over)."""
        self.allowance += self.metabolic_share * self.wake_work_since_sleep
        self.wake_work_since_sleep = 0
        recent = self.log[-max(self.buffer * 2, 12):]
        derivs = [(e, self._refactor(e.chain)) for e in recent if e.certified and len(e.chain) >= 2]
        counts, objects = Counter(), {}
        for e, chain in derivs:
            seen = set()
            for i in range(len(chain) - 1):
                key = (chain[i].name, chain[i + 1].name)
                if key not in seen:
                    counts[key] += 1
                    seen.add(key)
                    objects[key] = (chain[i], chain[i + 1])
        candidates = [k for k, n in counts.most_common() if n >= 2 and "macro[" + ">".join(k) + "]" not in self.L.macros]
        for key in candidates[:self.max_candidates]:
            a, b = objects[key]
            macro = macro_tool({a.name: a, b.name: b}, key)
            if self.layer_cap is not None and macro.layer > self.layer_cap:
                continue
            containing = [e for e, chain in derivs if any((chain[i].name, chain[i + 1].name) == key
                                                         for i in range(len(chain) - 1))][-self.buffer:]
            residuals = [e for e in recent if not e.certified][-max(1, self.buffer // 2):]
            replay = containing + residuals
            gains, lost, resolved = [], 0, []
            for e in replay:
                if e in residuals and self.allowance < self.budget:
                    continue          # residual replays only with full headroom
                if self.allowance <= 0:
                    break
                r = self.shadow_solve(e.task, [macro], budget=self._budget() if e in residuals else
                                      max(1, min(self._budget(), 2 * e.work)))
                self._spend(r.work)
                ok = r.status == UNIQUE and r.certificate_valid is True and grade(e.task, r)
                if e.solved and not ok:
                    lost += 1
                if ok and not e.solved:
                    resolved.append(e)
                gains.append((e.work if e.solved else self.budget) - r.work if ok else -r.work)
            if lost == 0 and sum(gains) > 0 and len(containing) >= 2:
                self.L.macros[macro.name] = macro
                self.promotions.append(dict(macro=macro.name, layer=macro.layer, gain=sum(gains),
                                            replay=len(replay), resolved=len(resolved)))
                self.resolved += [e.task for e in resolved]
            else:
                self.rejections.append(dict(macro=macro.name, layer=macro.layer, gain=sum(gains), lost=lost,
                                            containing=len(containing)))
        self.bridge_residuals(recent)
