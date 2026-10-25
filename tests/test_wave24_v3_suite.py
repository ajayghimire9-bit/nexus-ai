"""Wave 24 v3: MBPP sandbox and arms, AST helper library, wake-sleep, strategy allocation,
procedural transfer / meta experiments, and the locked-suite runner + independent verifier."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexus.wave24_helpers import HelperLibrary, canonical
from nexus.wave24_mbpp import (Meter, MbppTask, StrategyAllocator, extract_code, grade, load_tasks, method_nexus_evolved,
                               method_nexus_frozen, method_standalone, method_verified_sampling, ordered, passes,
                               screen, signature)


class ScriptedEngine:
    """Deterministic stand-in for QwenEngine: replies are functions of (purpose, user prompt)."""

    def __init__(self, reply):
        self.reply, self.calls, self.rows, self.max_tokens = reply, [], [], 320

    def start(self):
        return dict(backend="scripted", model_file="none")

    def complete(self, system, user, *, temperature=0.0, seed=0, purpose="", prefix="", stop=()):
        self.calls.append((purpose, user))
        text = self.reply(purpose, user)
        row = dict(purpose=purpose, input_tokens=len(user.split()), generated_tokens=len(text.split()),
                   cache_hit=False)
        self.rows.append(row)
        return prefix + text, row

    @staticmethod
    def work_units(row):
        return row["input_tokens"] + 4 * row["generated_tokens"]

    def telemetry(self):
        return dict(backend="scripted", model="none", calls=len(self.rows), fresh_calls=len(self.rows),
                    charged_cache_hits=0, generated_tokens=sum(r["generated_tokens"] for r in self.rows),
                    input_tokens=sum(r["input_tokens"] for r in self.rows), wall_s=0.0)

    def close(self):
        pass


def _task(text, tests):
    return MbppTask(9000 + len(text), text, tests, [], "")


ADD = _task("Write a function to add two numbers.", ["assert add(1, 2) == 3", "assert add(5, 5) == 10",
                                                       "assert add(-1, 1) == 0"])


# --------------------------------------------------------------------------- sandbox
def test_mbpp_split_is_deterministic_hash_split_and_public_is_first_assert():
    dev, ev = load_tasks("dev"), load_tasks("eval")
    assert len(dev) == 515 and len(ev) == 459 and not ({t.task_id for t in dev} & {t.task_id for t in ev})
    t = dev[0]
    assert t.public[0].source == t.tests[0] and len(t.hidden) == len(t.tests) - 1 + len(t.challenge)
    assert [x.task_id for x in ordered(ev, "s")] == [x.task_id for x in ordered(ev, "s")]


def test_sandbox_blocks_escapes_imports_forged_eq_and_cuts_loops():
    m = Meter()
    assert screen("def f(x):\n    return ().__class__.__bases__") is None
    assert screen("class A:\n    def __eq__(self, o):\n        return True\n") is None
    assert screen("def f():\n    return eval('1')") is None
    ok, res = passes("import os\ndef add(a, b):\n    return a + b", ADD.public, m)
    assert not ok and res[0][0] == "error"
    ok, res = passes("def add(a, b):\n    while True:\n        a += 1", ADD.public, m)
    assert not ok and res[0][0] == "budget" and m.total > 1000
    ok, _ = passes("import sys\ndef add(a, b):\n    return min(a + b, sys.maxsize)", ADD.public, Meter())
    assert ok


def test_extraction_salvages_a_trailing_line_cut_by_the_token_limit():
    text = "```python\ndef add(a, b):\n    return a + b\n\nassert add(1, 2) == [3, 4, 5"
    assert extract_code(text, "add") == "def add(a, b):\n    return a + b"
    assert extract_code("```python\nprint('no function')\n```", "add") is None


# --------------------------------------------------------------------------- arms
GOOD = "def add(a, b):\n    return a + b\n```"
OVERFIT = "def add(a, b):\n    return 3\n```"
BROKEN = "def add(a, b):\n    return a - b\n```"


def test_standalone_is_unverified_and_graded_on_all_tests():
    r = method_standalone(ADD, ScriptedEngine(lambda p, u: OVERFIT))
    assert r["plausible"] and not r["correct"] and r["llm_calls"] == 1 and r["work"] == r["llm_work"]


def test_verified_sampling_returns_first_public_passing_sample_and_charges_every_call():
    eng = ScriptedEngine(lambda p, u: BROKEN if p.endswith("greedy") else GOOD)
    r = method_verified_sampling(ADD, eng, k=3)
    assert r["correct"] and r["llm_calls"] == 2 and r["stage"] == "sample1" and r["work"] > r["llm_work"]


def test_frozen_cegis_prompt_carries_the_observed_counterexample():
    eng = ScriptedEngine(lambda p, u: GOOD if "returned -1" in u else BROKEN)
    r = method_nexus_frozen(ADD, eng, k=2)
    assert r["correct"] and r["trace"] == ["greedy", "cegis"]
    assert "returned -1, but the expected value is 3" in eng.calls[1][1]


def test_allocator_learns_from_charged_outcomes_and_explore_runs_both_strategies():
    a = StrategyAllocator()
    for _ in range(4):
        a.record("fail", "resample", True, 300)
        a.record("fail", "cegis", False, 300)
    assert a.choose("fail") == "resample" and a.choose("error:TypeError") == "resample"
    eng = ScriptedEngine(lambda p, u: BROKEN)
    lib, alloc = HelperLibrary(), StrategyAllocator()
    r = method_nexus_evolved(ADD, eng, lib, allocator=alloc, k=2, online=False, explore=True)
    assert r["trace"] == ["greedy", "resample", "cegis"] and alloc.stats["fail"]["cegis"][1] == 1
    assert signature(("error", "TypeError: bad")) == "error:TypeError" and signature(None) == "no_code"


def test_engine_cache_hit_recharges_original_tokens(monkeypatch):
    from nexus import wave24_qwen_engine as qe
    monkeypatch.setattr(qe, "locate_model", lambda: Path("qwen2.5-1.5b-instruct-q4_k_m.gguf"))
    monkeypatch.setattr(qe, "locate_server", lambda: "llama-server")
    e = qe.QwenEngine()
    e.rt = object()
    e.meta = {}
    monkeypatch.setattr(e, "_post", lambda *a, **k: dict(content="x = 1", tokens_evaluated=10, tokens_predicted=5))
    _, r1 = e.complete("s", "u", prefix="```python\n", stop=("```",))
    _, r2 = e.complete("s", "u", prefix="```python\n", stop=("```",))
    assert not r1["cache_hit"] and r2["cache_hit"] and e.work_units(r1) == e.work_units(r2) == 30
    monkeypatch.setattr(e, "_post", lambda *a, **k: dict(content="y", tokens_evaluated=None, tokens_predicted=None))
    with pytest.raises(RuntimeError):
        e.complete("s", "different")


# --------------------------------------------------------------------------- helper library
def _digit_tasks():
    t1 = _task("Write a function to find the sum of digits of a number.", ["assert digit_sum(123) == 6",
                                                                            "assert digit_sum(45) == 9"])
    t2 = _task("Write a function to check if the sum of digits of a number is even.",
               ["assert even_digit_sum(123) == True", "assert even_digit_sum(45) == False"])
    return t1, t2


def test_anti_unification_promotes_verified_helper_and_raises_layers():
    t1, t2 = _digit_tasks()
    lib = HelperLibrary()
    lib.add_solution(t1, "def digit_sum(n):\n    return sum(int(d) for d in str(abs(n)))", verified_on="all",
                     tests=t1.all_tests)
    lib.add_solution(t2, "def even_digit_sum(x):\n    return sum(int(c) for c in str(abs(x))) % 2 == 0",
                     verified_on="all", tests=t2.all_tests)
    m = Meter()
    promoted = lib.sleep(m)
    assert [p["helper"] for p in promoted] == ["helper_1"] and m.total > 0       # re-verification charged
    assert lib.helpers["digit_sum"].layer == 2 and "helper_1(" in lib.helpers["even_digit_sum"].src
    for sol in lib.solutions:                                                      # still verified after refactor
        assert passes(lib.source_of([sol["name"]]), sol["tests"], Meter())[0]
    again = HelperLibrary.from_json(json.loads(json.dumps(lib.to_json())))
    assert again.summary()["by_layer"] == lib.summary()["by_layer"]


def test_alpha_equivalence_and_bound_variables():
    import ast
    a = canonical(ast.parse("sum(int(d) for d in str(n))", mode="eval").body, {"sum", "int", "str"})
    b = canonical(ast.parse("sum(int(q) for q in str(value))", mode="eval").body, {"sum", "int", "str"})
    assert a[0] == b[0] and a[1] == ["n"] and b[1] == ["value"]


def test_refactor_that_breaks_a_solution_is_rejected():
    t1, t2 = _digit_tasks()
    lib = HelperLibrary()
    lib.add_solution(t1, "def digit_sum(n):\n    return sum(int(d) for d in str(abs(n)))", verified_on="all",
                     tests=t1.all_tests)
    lib.add_solution(t2, "def even_digit_sum(x):\n    return sum(int(c) for c in str(abs(x))) % 2 == 0",
                     verified_on="all", tests=t2.all_tests)
    lib.solutions[1]["tests"] = [t2.all_tests[0].__class__(t2.all_tests[0].source, "even_digit_sum",
                                                           "even_digit_sum(123)", "False", (123,))]
    assert lib.sleep(Meter()) == [] and lib.rejections and "helper_1" not in lib.helpers
    assert "helper_1" not in lib.helpers["digit_sum"].src


def test_execution_only_composition_reuses_a_verified_helper_without_llm():
    t1, _ = _digit_tasks()
    lib = HelperLibrary()
    lib.add_solution(t1, "def digit_sum(n):\n    return sum(int(d) for d in str(abs(n)))", verified_on="all",
                     tests=t1.all_tests)
    t4 = _task("Write a function to find the sum of digits of the given number",
               ["assert sum_digits_of(4567) == 22", "assert sum_digits_of(10) == 1"])
    eng = ScriptedEngine(lambda p, u: BROKEN)
    r = method_nexus_evolved(t4, eng, lib, k=2)
    assert r["stage"] == "helper_composition" and r["llm_calls"] == 0 and r["correct"] and not eng.calls
    assert r["answer_layer"] == 2 and "sum_digits_of" in lib.helpers


def test_dev_library_artifact_is_dev_only_and_loads():
    data = json.loads((Path(__file__).resolve().parents[1] / "artifacts" / "wave24_mbpp_dev_library.json").read_text())
    dev = {t.task_id for t in load_tasks("dev")}
    assert data["split"] == "dev" and set(data["task_ids"]) <= dev
    assert all(set(h["task_ids"]) <= dev for h in data["library"]["helpers"])
    lib = HelperLibrary.from_json(data["library"])
    assert lib.summary()["helpers"] == len(data["library"]["helpers"])


# --------------------------------------------------------------------------- procedural
def test_procedural_v3_has_no_skeletons_no_suppression_and_valid_certificates():
    from nexus.wave24_domains import target_domains
    from nexus.wave24_quotient_core import WorkMeter
    from nexus.wave24_v3_procedural import V3Learner, run_seed, stream_bank
    out = run_seed(1, transfer_per_depth=2, meta_orders=1, meta_per_depth=2)
    rows = out["transfer"]["rows"]
    assert rows and not any(r["status"].startswith("UNIQUE") and r["certificate_valid"] is False for r in rows)
    assert all(not any(w.startswith(("MAP(", "FILTER(", "FOLD(", "ITERATE(", "WINDOW(", "GUARD("))
                       for w in r["witness"]) for r in rows)
    assert all(r["false_certificates"] == 0 for r in out["meta"]["runs"])
    d = target_domains()[0]
    L = V3Learner(seed=1)
    L.enter(d, WorkMeter(limit=10**12))
    for t in stream_bank(d, 5, 1):
        L.solve_task(t)
        assert {t.name for t in d.tools} <= {x.name for x in L.toolset()}      # nothing is ever hidden


# --------------------------------------------------------------------------- runner + verifier
def _fake_reply(purpose, user):
    m = re.search(r"assert (\w+)\(", user)
    if purpose.startswith("qb:") or m is None:
        return "def nothing():\n    return None\n```"
    return f"def {m.group(1)}(*args):\n    return None\n```"


def test_v3_runner_and_verifier_end_to_end_with_tamper_detection(tmp_path):
    from nexus.wave24_v3_suite import run_v3
    from scripts.verify_wave24_agi_gap_suite import verify_v3
    out = run_v3(seeds=(1,), mbpp_n=2, engine=ScriptedEngine(_fake_reply), log=lambda m: None)
    out["schema"] = "wave24_suite_v3"
    assert out["execution_status"] == "COMPLETE" and len(out["mbpp"]["rows"]) == 8
    assert len(out["quixbugs"]["rows"]) == 33
    res = verify_v3(json.loads(json.dumps(out, default=str)))
    assert res["gates"]["v3_zero_false_certificates"] is True and res["gates"]["v3_independent_regrade_matches"]
    tampered = json.loads(json.dumps(out, default=str))
    row = next(r for r in tampered["mbpp"]["rows"] if r["method"] == "verified_sampling")
    row.update(plausible=True, correct=True, answer="def broken(:\n")
    bad = verify_v3(tampered)
    assert bad["gates"]["v3_zero_false_certificates"] is False and bad["gates"]["v3_independent_regrade_matches"] is False
