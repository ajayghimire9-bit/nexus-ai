from nexus.wave30_alien import apply, draw, group_table, params


def test_reference_mechanisms_and_ambiguity_records():
    for s in range(12):
        t = draw(10_000 + s)
        assert t is not None
        assert all(apply(t["reference"], x) == y for x, y in t["train"])
        assert apply(t["reference"], t["test_input"]) == t["answer"]
        assert t["fitting_params"] >= 1 and t["distinct_test_outputs"] >= 1
        assert (t["ambiguity"] == "none") == (t["distinct_test_outputs"] == 1)


def test_group_tables_are_groups():
    for kind in ("Z4", "Z2xZ2"):
        t = group_table(kind, [2, 0, 3, 1])
        e = [c for c in range(4) if all(t[(c, x)] == x for x in range(4))]
        assert len(e) == 1
        assert all(any(t[(a, b)] == e[0] for b in range(4)) for a in range(4))
