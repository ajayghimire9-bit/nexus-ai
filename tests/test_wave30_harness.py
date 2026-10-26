import dataclasses

from nexus.wave30_harness import FrozenPrior, TaskView, evaluate, run_stream, solve, summarise, verify_kernel_pin
from nexus.wave30_arms import stream
from nexus.wave25_factored import run


def test_kernel_pin_verified_from_git_object():
    assert len(verify_kernel_pin()) == 64


def test_solver_interface_exposes_no_hidden_fields():
    assert [f.name for f in dataclasses.fields(TaskView)] == ["public", "query", "oracle"]


def test_hidden_labels_do_not_change_solver_output():
    t = stream(751, n=2)[1]
    view = TaskView(tuple(t["public"]), t["query"], lambda x, c=t["teacher"]: run(c, x))
    a = solve("A1", view, seed=1, label="x")
    b = solve("A1", view, seed=1, label="x")
    keep = ("label", "answer", "work", "witnesses", "prover_status")
    assert {k: a[k] for k in keep} == {k: b[k] for k in keep}
    t2 = dict(t, family="A0" if t["family"] == "A1" else "A1")
    e1, e2 = evaluate(t, a), evaluate(t2, a)
    assert e1["correct"] == e2["correct"] and e1["category"] == e2["category"]


def test_matched_scope_and_categories():
    rows = run_stream(751, "A1b-full", prior=FrozenPrior(online=False), n=3)
    s = summarise(rows)
    assert s["agreement_among_proposals"] == 0            # full scope never yields proposal-relative labels
    assert all(r["scope"] == "full" for r in rows)
