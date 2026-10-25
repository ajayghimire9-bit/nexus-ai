"""Wave 24 v3: device-agnostic Qwen engine and LLM-guided, twin-fuzzed QuixBugs repair."""
import pytest

from nexus.wave24_code_repair import Meter, Program, split_tests
from nexus.wave24_llm_repair import (extract_function, fuzz_inputs, method_nexus_qwen, method_qwen_standalone,
                                     repair_prompt, run_tests_capture, split_source)


class FakeEngine:
    """Scripted completions with real-shaped telemetry (used only by unit tests)."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete(self, system, user, *, temperature=0.0, seed=0, purpose=""):
        self.calls.append(purpose)
        text = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        return text, dict(input_tokens=len(user.split()), generated_tokens=len(text.split()), cache_hit=False)

    @staticmethod
    def work_units(row):
        return row["input_tokens"] + 4 * row["generated_tokens"]


GOOD_GCD = "```python\ndef gcd(a, b):\n    if b == 0:\n        return a\n    else:\n        return gcd(b, a % b)\n```"
BAD_GCD = "```python\ndef gcd(a, b):\n    return a\n```"


def test_extract_function_and_prompt_use_real_docstring_and_fault_localization():
    p = Program.load("gcd")
    code, doc = split_source(p.source)
    assert "Greatest Common Divisor" in doc and "def gcd" in code
    pub, _ = split_tests(p, 1)
    prompt = repair_prompt(p, pub, suspicious=[5])
    assert "Specification" in prompt and "line 5" in prompt and "Failing test" in prompt
    assert "def gcd" in extract_function(GOOD_GCD, "gcd")


def test_fuzz_inputs_are_deterministic_and_capture_raises():
    p = Program.load("gcd")
    pub, _ = split_tests(p, 1)
    assert fuzz_inputs(pub, 3) == fuzz_inputs(pub, 3)
    code = compile("def f(x):\n    raise ValueError()\n", "<candidate>", "exec")
    assert run_tests_capture(code, "f", [1], Meter(10**6)) == ("raise", "ValueError")


def test_nexus_qwen_verifies_candidates_and_charges_llm_work():
    p = Program.load("gcd")
    pub, hid = split_tests(p, 1)
    eng = FakeEngine([GOOD_GCD, GOOD_GCD, GOOD_GCD, GOOD_GCD])
    r = method_nexus_qwen(p, pub, hid, eng, seed=1, k=2)
    assert r["plausible"] and r["correct"] and r["stage"] == "qwen" and r["llm_work"] > 0
    assert r["work"] >= r["llm_work"] and any(c.startswith("twin:") for c in eng.calls)


def test_wrong_llm_candidates_fall_back_to_mutation_search():
    p = Program.load("gcd")
    pub, hid = split_tests(p, 1)
    r = method_nexus_qwen(p, pub, hid, FakeEngine([BAD_GCD]), seed=1, k=2)
    assert r["stage"] == "mutation_fallback" and r["correct"]


def test_standalone_llm_answer_is_not_verified_before_grading():
    p = Program.load("gcd")
    pub, hid = split_tests(p, 1)
    r = method_qwen_standalone(p, pub, hid, FakeEngine([BAD_GCD]))
    assert r["plausible"] and not r["correct"]


def test_live_qwen15_engine_runs_and_reports_backend_and_tokens():
    from nexus.wave24_qwen_engine import QwenEngine, locate_model, locate_server
    try:
        locate_model(), locate_server()
    except FileNotFoundError as exc:
        pytest.skip(f"local Qwen-1.5B weights or llama-server absent: {exc}")
    e = QwenEngine(max_tokens=24)
    try:
        meta = e.start()
        text, row = e.complete("Reply with one word.", "Say ok.", purpose="live-test")
        assert meta["model_file"] == "qwen2.5-1.5b-instruct-q4_k_m.gguf" and meta["quantization"] == "Q4_K_M"
        assert row["backend"] in ("metal", "cpu") and row["generated_tokens"] > 0 and text.strip()
        assert e.telemetry()["backend"] == ("metal" if meta["n_gpu_layers"] == -1 else "cpu")
    finally:
        e.close()
