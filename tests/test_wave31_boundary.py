"""Wave 31 increment 2: evaluator / meter boundary, reporting rule, LODO skeleton support. No experiment runs."""
import json
import subprocess
import sys

import pytest

from nexus import checker_kernel_v2 as V
from nexus import wave31_evaluator as E
from nexus import wave31_grammar as G
from nexus import wave31_solver as S
from nexus import wave31_tasks as T

darwin = pytest.mark.skipif(sys.platform != "darwin", reason="sandbox-exec is macOS only")


@darwin
def test_sandbox_denies_repo_writes_and_vault_reads(tmp_path):
    code = ("import sys\n"
            f"try:\n open({str(E.LEDGER)!r}, 'a').write('x')\n print('WROTE')\nexcept OSError:\n print('DENIED')\n")
    out = subprocess.run(["/usr/bin/sandbox-exec", "-p", E.sandbox_profile(), sys.executable, "-B", "-c", code],
                         capture_output=True, text=True, timeout=30)
    assert out.stdout.strip() == "DENIED"
    code2 = ("import os\n"
             f"try:\n os.listdir({E.VAULT!r})\n print('READ')\nexcept OSError:\n print('DENIED')\n")
    out2 = subprocess.run(["/usr/bin/sandbox-exec", "-p", E.sandbox_profile(), sys.executable, "-B", "-c", code2],
                          capture_output=True, text=True, timeout=30)
    assert out2.stdout.strip() == "DENIED"


def test_report_label_rule():
    ok = {"label": "exhaustive_UNIQUE"}
    assert G.report_label(ok, G.matched_scope()) == "exhaustive_UNIQUE"
    macro = {"kind": "exhaustive", "tools": G.G_P + [{"op": "seq", "body": [G.SORT, G.RUNH]}], "max_depth": 2}
    assert G.report_label(ok, macro) == "MACRO_SCOPE_UNIQUE"
    shallow = dict(G.matched_scope(), max_depth=2)
    assert G.report_label(ok, shallow) == "SCOPE_RELATIVE_UNIQUE"
    assert G.report_label({"label": "AMBIGUOUS"}, G.matched_scope()) == "AMBIGUOUS"


def test_lodo_skeleton_support():
    """Compositional cores are instances of learned skeletons; held-out cores and placebo do not get them for
    free; familiar cores are exact macros."""
    progs = [T.teacher("records", c) for c in T.S_CORES for _ in range(2)]
    lib = S.build(progs, "t")
    keys = {V.key(m) for m in lib["useful"]}

    def has(core):
        return V.key({"op": "seq", "body": [G.CORE_OPS[c] for c in core]}) in keys
    assert all(has(c) for c in T.TARGET["familiar_exact"])
    assert all(has(c) for c in T.TARGET["compositional"])
    assert not any(has(c) for c in T.TARGET["held_out"])
    assert abs(len(lib["placebo"]) - len(lib["useful"])) <= len(lib["useful"]) // 4


def test_expand_and_lemmas_are_kernel_valid():
    t = T.target_stream(761, "records")[0]
    lem = S.lemmas_for(t["public"], G.G_P)
    cand = T.teacher("records", tuple(t["core"]))
    ev = {"checker_version": 2, "public": t["public"], "query": t["query"], "claimed_answer": t["answer"],
          "candidate": cand, "scope": G.matched_scope(), "lemmas": lem, "trace": {}}
    v = V.check(ev)
    assert v["label"] != "ABSTAIN" or v["reason"] != "bad_lemma"
    v0 = V.check(dict(ev, lemmas=[]))
    assert v["label"] == v0["label"] and v.get("k") == v0.get("k")      # lemmas never change the verdict


class _FakeChild:
    def __init__(self, reply):
        self.reply, self.sent = reply, []

    def send(self, m):
        self.sent.append(m)

    def recv(self):
        return self.reply


def test_fabricated_public_pair_is_invalid():
    t = dict(T.target_stream(761, "records")[0])
    cand = T.teacher("records", tuple(t["core"]))
    fake = [[[{"a": 1, "b": 1}], [9, 9, 9]]]
    ev = {"checker_version": 2, "public": t["public"] + fake, "query": t["query"], "claimed_answer": t["answer"],
          "candidate": cand, "scope": G.matched_scope(), "lemmas": [], "trace": {}}
    msg = {"done": True, "evidence": ev, "meter": {"prover": 0},
           "info": {"probes": 0, "fallback": False, "checks": 1, "status": "x"}}
    e = E.Evaluator.__new__(E.Evaluator)
    e.kernel_work = 0
    row = e.grade(t, msg, {})
    assert row["label"] == "INVALID_EVIDENCE" and not row["correct"]


def test_solver_does_not_import_task_generator():
    for f in (S.__file__, E.ROOT / "scripts/wave31_solver_child.py"):
        imports = [ln for ln in open(f).read().splitlines() if ln.lstrip().startswith(("import ", "from "))]
        assert not any("wave31_tasks" in ln or "wave31_evaluator" in ln for ln in imports)
