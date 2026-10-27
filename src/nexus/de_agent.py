"""Stage 3 engineering agents (NOT LOCKED). Two matched arms over the SAME tools, code generator (de_template), proposer,
exception attribution and budgets; cross-project learning is disabled in both (no state survives a project).

  Conventional_Agent_No_NEXUS_Checks  generate -> run; on an exception, change the decision the failing stage names; stop at
                                      the first configuration that runs without an exception (COMPLETED_UNVERIFIED)
  NEXUS_Engineer_No_History           inspect + coverage check -> ask_clarification for every rule gap the data hits ->
                                      generate -> run -> verify_invariants (de_checks); a failing invariant changes the
                                      decision it implicates; submit only when every invariant holds (COMPLETED_VERIFIED),
                                      otherwise ABSTAIN / HARD_FAIL (never a silent submission)

The proposer is deliberately uninformed: each decision's options are ordered by a seeded random permutation of
(project id, decision), identical for both arms. Neither arm imports or sees the evaluator, the generator's truth or held-out
batch 3 (tests/test_de_stage3.py checks the imports). The workspace holds docs/ and the visible batches only.
Metering: kernel-reported CPU seconds (agent process via getrusage(SELF), pipeline runs via getrusage(CHILDREN)), wall
time, bytes written, number of proposals, executions, invariant checks and clarifications."""
from __future__ import annotations

import hashlib
import json
import platform
import random
import resource
import shutil
import sqlite3
import time
from pathlib import Path

from nexus import de_checks as C
from nexus import de_template as T
from nexus import outcome_contract as OC

ARMS = ("Conventional_Agent_No_NEXUS_Checks", "NEXUS_Engineer_No_History")
# descriptive sensitivity arm (predeclared, not a primary comparison): the conventional stop rule with a BEST-CASE proposer
# whose first option is always the generator's correct-shape option; it bounds what verification adds beyond code quality
SENSITIVITY = ("Conventional_BestCaseProposer_Sensitivity",)
MAX_PROPOSALS = 40          # identical cap for both arms
MAX_CPU_S = 300.0           # identical per-project CPU cap for both arms (agent + pipeline runs + checks)


def _cpu_self():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


class Tools:
    """The agent's only interface to the project. Every call is counted; costs are bucketed."""

    def __init__(self, ws, ask_fn, sandbox_profile=None):
        self.ws = Path(ws)
        self.bundle = self.ws / "bundle"
        self.scratch = self.ws / "scratch"
        self.bundle.mkdir(parents=True, exist_ok=True)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.batches = sorted(p for p in self.ws.iterdir() if p.is_dir() and p.name.startswith("batch"))
        self._ask = ask_fn
        self.runner = C.Runner(sandbox_profile)
        self.calls = {}
        self.clarifications = []
        self.io_bytes = 0
        self.exec_cpu = {"run": 0.0, "verify": 0.0}
        self.exec_runs = {"run": 0, "verify": 0}

    def _count(self, name):
        self.calls[name] = self.calls.get(name, 0) + 1

    def read_docs(self):
        self._count("read_docs")
        return json.loads((self.ws / "docs/spec.json").read_text())

    def inspect_schema(self):
        self._count("inspect_schema")
        out = {}
        for b in self.batches:
            con = sqlite3.connect(f"file:{b / 'source.db'}?mode=ro", uri=True)
            db = {}
            for (t, sql) in con.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"):
                cols = [(r[1], r[2], r[5]) for r in con.execute(f'PRAGMA table_info("{t}")')]
                fks = [(r[3], r[2], r[4]) for r in con.execute(f'PRAGMA foreign_key_list("{t}")')]
                db[t] = dict(columns=cols, foreign_keys=fks, rows=con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])
            con.close()
            files = {}
            for f in sorted(b.rglob("*")):
                if f.suffix == ".jsonl":
                    rows = C.jsonl(f)
                    files[str(f.relative_to(b))] = dict(rows=len(rows), keys=sorted(rows[0]) if rows else [], sample=rows[:2])
                elif f.suffix == ".csv":
                    lines = f.read_text().split("\n")
                    files[str(f.relative_to(b))] = dict(rows=len([x for x in lines[1:] if x]), header=lines[0], sample=lines[1:3])
            out[b.name] = dict(db=db, files=files)
        return out

    def ask_clarification(self, topic, value):
        self._count("ask_clarification")
        a = self._ask(topic, value)
        self.clarifications.append(dict(question=f"{topic}:{value}", answer=a))
        return a

    def edit_file(self, rel, text):
        self._count("edit_file")
        f = self.bundle / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
        self.io_bytes += len(text.encode())

    def run_sql_or_python(self, tag):
        """Run the bundle's pipeline over the visible batches on a fresh state. Returns (runs, state_dir)."""
        self._count("run_sql_or_python")
        c0, n0 = self.runner.cpu_s, self.runner.runs
        out = self.runner.run_seq(self.bundle, self.batches, self.scratch / f"run_{tag}")
        self.exec_cpu["run"] += self.runner.cpu_s - c0
        self.exec_runs["run"] += self.runner.runs - n0
        self.io_bytes += sum(f.stat().st_size for f in out[1].rglob("*") if f.is_file())
        return out

    def inspect_outputs(self, state, spec):
        self._count("inspect_outputs")
        tabs = C.tables(state, spec)
        rep = {}
        for t, rows in tabs.items():
            if isinstance(rows, list):
                cols, pk = spec["outputs"][t]["columns"], spec["outputs"][t]["pk"]
                ks = [tuple(r[cols.index(c)] for c in pk) for r in rows]
                rep[t] = dict(rows=len(rows), null_rate={c: round(sum(r[i] is None for r in rows) / max(1, len(rows)), 3)
                                                         for i, c in enumerate(cols)}, pk_unique=len(ks) == len(set(ks)))
            else:
                rep[t] = rows
        return rep

    def verify_invariants(self, spec, tag, base):
        self._count("verify_invariants")
        c0, n0 = self.runner.cpu_s, self.runner.runs
        res = C.verify(self.bundle, spec, self.batches, self.scratch / f"verify_{tag}", self.runner, base=base)
        self.exec_cpu["verify"] += self.runner.cpu_s - c0
        self.exec_runs["verify"] += self.runner.runs - n0
        return res


class Proposer:
    """Shared, uninformed code/rule generator front end: one seeded permutation of each decision's options."""

    def __init__(self, project_id, best_case=False):
        self.perm = {}
        for d, opts in T.DECISIONS.items():
            o = list(opts)
            random.Random(f"de1-proposer:{project_id}:{d}").shuffle(o)
            if best_case and d in T.CORRECT_SHAPE:
                o.remove(T.CORRECT_SHAPE[d]); o.insert(0, T.CORRECT_SHAPE[d])
            self.perm[d] = o
        self.idx = {d: 0 for d in T.DECISIONS}
        self.rejected = {d: set() for d in T.DECISIONS}
        self.calls = 0

    def choice(self):
        self.calls += 1
        return {d: self.perm[d][self.idx[d]] for d in T.DECISIONS}

    def advance(self, d):
        """Reject the current option of d and move to the next unrejected one. False if none is left."""
        self.rejected[d].add(self.perm[d][self.idx[d]])
        for j, o in enumerate(self.perm[d]):
            if o not in self.rejected[d]:
                self.idx[d] = j
                return True
        return False


def attribute(stage):
    """Decisions whose code runs in the failing stage (in DECISIONS order)."""
    return [d for d in T.DECISIONS if T.STAGE_OF[d] == stage]


def _bundle_docs(arm, spec, choice, clar, checks, outcome):
    lines = [f"# Pipeline for project {spec['project']} ({arm})", "", f"Outcome: **{outcome}**", "",
             "Run: `python pipeline.py --landing <batch dir> --state <state dir> --config config.json` once per batch, in order.",
             "Outputs (state/lake.db): " + ", ".join(spec["outputs"]), "", "## Implementation decisions"]
    lines += [f"* `{d}` = `{v}`" for d, v in choice.items()]
    lines += ["", "## Clarifications"] + ([f"* {c['question']} -> {c['answer']}" for c in clar] or ["* none asked"])
    lines += ["", "## Verification"]
    lines += ([f"* {'PASS' if c['ok'] else 'FAIL'} {c['check']}: {c['detail']}" for c in checks] or
              ["* none: the conventional stop rule submits the first configuration that runs without an exception"])
    lines += ["", "## Limits", "* Checks cover the visible batches only; batch semantics are taken from docs/spec.json.", ""]
    return "\n".join(lines)


def _manifest(bundle):
    files = {str(f.relative_to(bundle)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(bundle.rglob("*"))
             if f.is_file() and f.name != "MANIFEST.json"}
    return json.dumps(dict(python=platform.python_version(), sqlite=sqlite3.sqlite_version, dependencies="python standard "
                           "library only (argparse, csv, glob, hashlib, json, os, re, sqlite3, datetime)", files=files),
                      indent=1, sort_keys=True)


TEST_NEXUS = '''"""Invariant tests for this pipeline (generated by NEXUS). Set DE_SPEC=<docs/spec.json> and DE_BATCHES=<batch dirs, os.pathsep>."""
import json, os, pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import invariants as I

B = pathlib.Path(__file__).resolve().parents[1]


def test_all_invariants_hold():
    spec = json.loads(pathlib.Path(os.environ["DE_SPEC"]).read_text())
    res = I.verify(B, spec, os.environ["DE_BATCHES"].split(os.pathsep), pathlib.Path(tempfile.mkdtemp()) / "w", I.Runner(),
                   stop_at_first=False)
    assert all(r["ok"] for r in res), [r for r in res if not r["ok"]]
'''
TEST_CONV = '''"""Smoke test (conventional stop rule): the pipeline runs over the batches without an exception."""
import os, pathlib, subprocess, sys, tempfile

B = pathlib.Path(__file__).resolve().parents[1]


def test_runs_without_exception():
    st = pathlib.Path(tempfile.mkdtemp()) / "state"
    for b in os.environ["DE_BATCHES"].split(os.pathsep):
        subprocess.run([sys.executable, str(B / "pipeline.py"), "--landing", b, "--state", str(st), "--config",
                        str(B / "config.json")], check=True)
'''


def solve(arm, ws, ask_fn, sandbox_profile=None):
    """Run one arm on one project workspace. Returns the agent-side record (outcome, cost and dependence meters)."""
    t0, c0 = time.perf_counter(), _cpu_self()
    tools = Tools(ws, ask_fn, sandbox_profile)
    spec = tools.read_docs()
    tools.inspect_schema()
    prop = Proposer(spec["project"], best_case=arm in SENSITIVITY)
    clar = {}
    if arm == "NEXUS_Engineer_No_History":
        for topic, value in C.coverage(spec, tools.batches):
            a = tools.ask_clarification(topic, value)
            if a != "NOT_A_QUESTION":
                clar[f"{topic}:{value}"] = a
    tools.edit_file("config.json", json.dumps(T.config_from_spec(spec, clar), indent=1, sort_keys=True))
    outcome, checks, history, accepted = OC.HARD_FAIL, [], [], None
    cpu_rejected = 0.0
    for k in range(MAX_PROPOSALS):
        if _cpu_self() - c0 + tools.runner.cpu_s > MAX_CPU_S:
            outcome = OC.HARD_FAIL
            break
        choice = prop.choice()
        tools.edit_file("pipeline.py", T.emit(choice))
        cpu_before = tools.runner.cpu_s
        runs, st = tools.run_sql_or_python(k)
        last = runs[-1]
        step = dict(k=k, choice=dict(choice), exit=last["exit"], stage=last["stage"])
        if last["exit"] != 0:
            step["fix"] = None
            for d in attribute(last["stage"]):
                if prop.advance(d):
                    step["fix"] = d
                    break
            history.append(step)
            cpu_rejected += tools.runner.cpu_s - cpu_before
            if step["fix"] is None:
                outcome = OC.HARD_FAIL
                break
            continue
        if arm != "NEXUS_Engineer_No_History":
            tools.inspect_outputs(st, spec)
            outcome, accepted = OC.COMPLETED_UNVERIFIED, choice
            history.append(step)
            break
        res = tools.verify_invariants(spec, k, (runs, st))
        bad = next((r for r in res if not r["ok"]), None)
        step["checks"] = [(r["check"], r["ok"]) for r in res]
        if bad is None:
            tools.inspect_outputs(st, spec)
            outcome, accepted, checks = OC.COMPLETED_VERIFIED, choice, res
            history.append(step)
            break
        step["fix"] = None
        for d in bad["implicate"]:
            if prop.advance(d):
                step["fix"] = d
                break
        history.append(step)
        cpu_rejected += tools.runner.cpu_s - cpu_before
        if step["fix"] is None:
            outcome, checks = OC.ABSTAIN_UNSUPPORTED, res     # an invariant no available option satisfies: refuse to submit
            break
    # deliverable bundle
    final = accepted or choice
    tools.edit_file("pipeline.py", T.emit(final))
    if arm == "NEXUS_Engineer_No_History":
        tools.edit_file("tests/test_pipeline.py", TEST_NEXUS)
        shutil.copy(Path(C.__file__), tools.bundle / "tests/invariants.py")
    else:
        tools.edit_file("tests/test_pipeline.py", TEST_CONV)
    tools.edit_file("PIPELINE.md", _bundle_docs(arm, spec, final, tools.clarifications, checks, outcome))
    tools.edit_file("MANIFEST.json", _manifest(tools.bundle))
    agent_cpu = _cpu_self() - c0
    return dict(
        arm=arm, project=spec["project"], outcome=outcome, submitted=outcome in (OC.COMPLETED_VERIFIED, OC.COMPLETED_UNVERIFIED),
        final_choice=final, history=history, clarifications=tools.clarifications,
        cost=dict(proposer_calls=prop.calls, tool_calls=tools.calls, pipeline_runs=tools.exec_runs["run"],
                  check_runs=tools.exec_runs["verify"], exec_cpu_s=round(tools.exec_cpu["run"], 3),
                  check_cpu_s=round(tools.exec_cpu["verify"], 3), agent_cpu_s=round(agent_cpu, 3),
                  wasted_cpu_s=round(cpu_rejected, 3), io_bytes=tools.io_bytes, wall_s=round(time.perf_counter() - t0, 3),
                  total_cpu_s=round(agent_cpu + tools.runner.cpu_s, 3)),
        human=dict(clarifications=len(tools.clarifications), engineering_repairs=0, operational_interventions=0))
