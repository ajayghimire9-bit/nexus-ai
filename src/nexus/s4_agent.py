"""Stage 4 build agents (NOT LOCKED). Every arm uses the same tools, generator (s4_template), proposer permutation, exception
attribution and caps; arms differ ONLY in the acceptance checks and in an optional procedure library (Stage 6).

  Conventional_NoCheck    stop at the first configuration whose every visible tick runs (descriptive ablation)
  Conventional_Checked    accept when the STANDARD engineering checks pass; retries; may ask clarifications
  NEXUS_*                 accept when every NEXUS check passes; a failing check advances the decision it implicates
Library (s6_library): admitted procedures re-order a decision's options (the procedure's option first) and may re-order
the checks. Acceptance criteria are never weakened: every arm runs its full suite on the configuration it submits.
Agents see docs/spec.json and the visible log only; never the evaluator, truth, held-out ticks or fault-class ids."""
from __future__ import annotations

import json
import random
import resource
import shutil
import time
from pathlib import Path

from nexus import s4_checks as C
from nexus import s4_template as T

MAX_PROPOSALS = 40
MAX_CPU_S = 900.0


def _cpu():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


class Proposer:
    def __init__(self, project, prior=None):
        self.perm, self.idx, self.rej, self.calls = {}, {}, {}, 0
        for d, opts in T.DECISIONS.items():
            o = list(opts)
            random.Random(f"de2-proposer:{project}:{d}").shuffle(o)
            if prior and d in prior and prior[d] in o:
                o.remove(prior[d]); o.insert(0, prior[d])
            self.perm[d], self.idx[d], self.rej[d] = o, 0, set()

    def choice(self):
        self.calls += 1
        return {d: self.perm[d][self.idx[d]] for d in T.DECISIONS}

    def advance(self, d):
        self.rej[d].add(self.perm[d][self.idx[d]])
        for j, o in enumerate(self.perm[d]):
            if o not in self.rej[d]:
                self.idx[d] = j
                return True
        return False


def attribute(stage):
    return [d for d in T.DECISIONS if T.STAGE_OF[d] == stage]


def localize(prop, choice, check, implicate, bundle, spec, full, work, runner, suite, base_score, passed=()):
    """Localized, compositional repair search for one failing check.
    1. single changes (implicated decisions first, then the others), each scored by re-running ONLY the failing check plus a
       regression guard (every check that passed before must still pass); the largest strict severity reduction wins;
    2. conflict-directed pairs: a single change that improved the check but broke guard check G is paired with changes to
       the decisions G implicates; then pairs among the implicated decisions.
    No option is rejected without evidence. Returns (decision(s) changed or None, trials)."""
    guard = [c for c in suite if c in STD_PRE or c in passed]
    trials = [0]

    def score(ch, tag):
        (bundle / "pipeline.py").write_text(T.emit(ch))
        r = C.verify(bundle, spec, full, work / tag, runner, suite=guard + ([check] if check not in guard else []), order=suite)
        shutil.rmtree(work / tag, ignore_errors=True)
        trials[0] += 1
        broke = next((x["check"] for x in r if x["check"] != check and not x["ok"]), None)
        sc = next((x["score"] for x in r if x["check"] == check), None)
        return sc, broke

    def alts(d):
        return [o for o in prop.perm[d] if o != choice[d] and o not in prop.rej[d]]

    conflicts = []
    for group in (list(implicate), [d for d in T.DECISIONS if d not in implicate]):
        best = None
        for d in group:
            for o in alts(d):
                sc, broke = score(dict(choice, **{d: o}), f"{d}_{o}")
                if broke is None and sc is not None and sc < base_score and (best is None or sc < best[0]):
                    best = (sc, ((d, o),))
                elif broke is not None and broke != "runs_all_ticks":
                    conflicts.append((d, o, broke))
            if best and best[0] == 0:
                break
        if best:
            break
    if not best:
        pairs = [((d, o), (d2, o2)) for d, o, g in conflicts for d2 in C.IMPLICATE.get(g, []) if d2 != d for o2 in alts(d2)]
        imp = [d for d in implicate if d in T.DECISIONS]
        pairs += [((d1, o1), (d2, o2)) for i, d1 in enumerate(imp) for d2 in imp[i + 1:] for o1 in alts(d1) for o2 in alts(d2)]
        seen = set()
        for (d1, o1), (d2, o2) in pairs:
            if trials[0] >= MAX_TRIALS or (d1, o1, d2, o2) in seen:
                continue
            seen.add((d1, o1, d2, o2))
            sc, broke = score(dict(choice, **{d1: o1, d2: o2}), f"{d1}_{o1}_{d2}_{o2}")
            if broke is None and sc is not None and sc < base_score and (best is None or sc < best[0]):
                best = (sc, ((d1, o1), (d2, o2)))
                if sc == 0:
                    break
    if not best:
        return None, trials[0]
    for d, o in best[1]:
        prop.rej[d].add(choice[d])
        prop.idx[d] = prop.perm[d].index(o)
    return "+".join(d for d, _ in best[1]), trials[0]


MAX_TRIALS = 60


STD_PRE = ("runs_all_ticks",)


def build(arm, ws, ask_fn=None, profile=None, library=None):
    """ws: docs/spec.json + visible/log (ticks 1-8). Returns the agent record; leaves ws/bundle as the deliverable."""
    t0, c0 = time.perf_counter(), _cpu()
    ws = Path(ws)
    spec = json.loads((ws / "docs/spec.json").read_text())
    full = ws / "visible" / "log"
    bundle, scratch = ws / "bundle", ws / "scratch"
    bundle.mkdir(exist_ok=True); scratch.mkdir(exist_ok=True)
    runner = C.Runner(profile)
    lib_cost = {"retrieval_cpu_s": 0.0, "applicability_cpu_s": 0.0}
    prior, order, used = {}, None, []
    if library is not None and arm.startswith("NEXUS"):
        a = _cpu()
        procs = library.retrieve("build")
        lib_cost["retrieval_cpu_s"] = _cpu() - a
        a = _cpu()
        feats = library.features(spec, C.records(full))
        for p in procs:
            if library.applicable(p, feats):
                prior[p["decision"]] = p["option"]
                used.append(p["id"])
        order = library.check_order()
        lib_cost["applicability_cpu_s"] = _cpu() - a
    prop = Proposer(spec["project"], prior)
    suite = None if arm == "Conventional_NoCheck" else (C.STANDARD if arm == "Conventional_Checked" else C.NEXUS)
    (bundle / "config.json").write_text(json.dumps(T.config_from_spec(spec), indent=1, sort_keys=True))
    outcome, history, accepted, checks = "HARD_FAIL", [], None, []
    final_cpu, final_runs, search_cpu, search_runs = 0.0, 0, 0.0, 0
    for k in range(MAX_PROPOSALS):
        if _cpu() - c0 + runner.cpu_s > MAX_CPU_S:
            break
        choice = prop.choice()
        (bundle / "pipeline.py").write_text(T.emit(choice))
        cpu0, runs0 = runner.cpu_s, runner.runs
        if suite is None:
            runs, _ = C.replay(runner, bundle, full, spec, scratch / f"r{k}", range(1, 9))
            res = [dict(check="runs_all_ticks", ok=all(r["exit"] == 0 for r in runs) and len(runs) == 8,
                        detail=runs[-1]["err"][-200:], implicate=[], stage=runs[-1]["stage"])]
        else:
            res = C.verify(bundle, spec, full, scratch / f"v{k}", runner, suite=suite, order=order)
        bad = next((r for r in res if not r["ok"]), None)
        step = dict(k=k, choice=choice, failed=bad["check"] if bad else None)
        if bad is None:
            final_cpu, final_runs = runner.cpu_s - cpu0, runner.runs - runs0
            outcome, accepted, checks = ("COMPLETED_VERIFIED" if suite == C.NEXUS else "COMPLETED_CHECKED" if suite else
                                         "COMPLETED_UNVERIFIED"), choice, res
            history.append(step)
            break
        imp = bad["implicate"]
        if bad["check"] == "runs_all_ticks":
            stage = bad.get("stage") or next((r.get("stage") for r in [bad] if r.get("stage")), None)
            if stage is None and "stage=" in bad["detail"]:
                stage = bad["detail"].split("stage=")[1].split()[0]
            imp = attribute(stage)
        if suite is not None:
            passed = [r["check"] for r in res if r["ok"]]
            step["fix"], step["trials"] = localize(prop, choice, bad["check"], imp, bundle, spec, full, scratch / f"loc{k}",
                                                   runner, suite, bad.get("score", 1), passed)
        else:
            step["fix"] = next((d for d in imp if prop.advance(d)), None)
        step["cpu_s"] = round(runner.cpu_s - cpu0, 4)
        if prior and step.get("fix"):
            step["failed_reuse"] = [d for d in str(step["fix"]).split("+") if d in prior and choice[d] == prior[d]]
        history.append(step)
        search_cpu += runner.cpu_s - cpu0
        search_runs += runner.runs - runs0
        if step["fix"] is None:
            outcome, checks = "ABSTAIN_UNSUPPORTED", res
            break
        shutil.rmtree(scratch / f"v{k}", ignore_errors=True)
    final = accepted or choice
    (bundle / "pipeline.py").write_text(T.emit(final))
    shutil.copy(Path(C.__file__), bundle / "checks.py")
    (bundle / "BUILD.md").write_text(f"# {spec['project']} ({arm})\n\nOutcome: {outcome}\n\nDecisions: {json.dumps(final, sort_keys=True)}\n"
                                     f"\nChecks: {[(r['check'], r['ok']) for r in checks]}\n")
    agent_cpu = _cpu() - c0
    from nexus import s6_library as SL
    feats = sorted(SL.features(spec, C.records(full)))
    failed = sum(len(h.get("failed_reuse", [])) for h in history)
    return dict(arm=arm, project=spec["project"], outcome=outcome, final_choice=final, history=history, library_used=used,
                features=feats, failed_reuse=failed,
                failed_reuse_cpu_s=round(sum(h["cpu_s"] for h in history if h.get("failed_reuse")), 4),
                submitted=outcome.startswith("COMPLETED"),
                cost=dict(proposals=prop.calls, pipeline_runs=runner.runs, check_runs=runner.runs,
                          final_check_runs=final_runs, final_check_cpu_s=round(final_cpu, 3),
                          rejected_and_search_runs=search_runs, rejected_cpu_s=round(search_cpu, 3), exec_cpu_s=round(runner.cpu_s, 3),
                          agent_cpu_s=round(agent_cpu, 3),
                          total_cpu_s=round(agent_cpu + runner.cpu_s, 3), wall_s=round(time.perf_counter() - t0, 3), **lib_cost),
                human=dict(clarifications=0, engineering_repairs=0, operational_interventions=0))
