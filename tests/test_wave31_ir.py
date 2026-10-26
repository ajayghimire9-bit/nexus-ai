import inspect
import random

from nexus import checker_kernel_v2 as V
from nexus import wave31_ir as W


def test_solver_sees_no_evaluator_labels():
    assert list(inspect.signature(W.solve).parameters) == ["arm", "public", "query", "library"]


def test_teachers_execute_and_are_in_primitive_grammar():
    for t in W.stream(761, W.SOURCE_DOMAINS + W.TARGET_DOMAINS, n_per=1):
        assert V.key(V.run(t["teacher"], t["query"])[0]) == V.key(t["answer"])
        prims = {V.key(s) for s in W.primitives(t["public"], t["query"])}
        assert all(V.key(s) in prims for s in t["teacher"]) and len(t["teacher"]) <= 4


def test_library_is_learned_from_source_only_and_placebo_is_size_matched():
    progs = [W.teacher("lists", "topk", 2, 3, None), W.teacher("strings", "topk", 1, 3, None)]
    lib, sks = W.library_from(progs)
    assert sks and all(m["op"] == "seq" and V.known(m) for m in lib)
    assert all(not W.is_adapter(s) for m in lib for s in m["body"])          # adapters stripped from cores
    plc = W.placebo_library(len(lib), [len(m["body"]) for m in lib], random.Random(0))
    assert len(plc) == len(lib)
    assert sorted(len(m["body"]) for m in plc) == sorted(len(m["body"]) for m in lib)


def test_adapter_work_is_charged_separately():
    t = W.stream(761, ("grids",), n_per=1)[0]
    v, ev, meter, g = W.solve("Fresh", t["public"], t["query"], [])
    assert meter.get("adapter", 0) > 0 and meter.get("checker", 0) > 0
