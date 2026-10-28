"""sc contract layer, mapping candidates and platform helper (fast; dev seeds outside every one-use range; no experiment)."""
from nexus import sc_contract as SC
from nexus import sc_mapping as SM
from nexus import sc_platform as SCP
from nexus import u5_stateful as SF
from tests.test_ba_accept import _machine as _m0

ADDX = ("b", "+", ("var", "acc"), ("var", "x"))


def _machine(close_resets):
    m = _m0(close_resets)
    m["regs"][0]["upd"][(1, "READ")] = ADDX                                            # READ accumulates the value field
    return m


def _payload(m):
    from nexus import u5_statesplit as SP
    src, name = SP.class_source(m)
    m = dict(m)
    return dict(source=src, name=name, machine=m, contract=SC.infer(m, [{"k": "a", "kind": "READ", "v": 2.0}]), mappings=[])


def test_missing_required_field_is_a_mismatch_not_zero():
    p = _payload(_machine(True))
    assert p["contract"]["required"] == {"READ": ["v"]}
    r = SC.ContractRunner(p)
    assert r.ingest({"k": "a", "kind": "OPEN"}) == []                                  # OPEN does not need v
    assert r.ingest({"k": "a", "kind": "READ", "v_amount": 3.0}) == [SC.MISMATCH_ROW]
    inc = r.pop_incidents()
    assert inc[0]["expected_fields"] == ["v"] and "v_amount" in inc[0]["observed_fields"] and inc[0]["kind"] == "READ"


def test_mapping_versions_keep_old_and_new_records_interpretable():
    p = SM._payload_with(_payload(_machine(True)), "v", "v_amount")
    r = SC.ContractRunner(p)
    evs = [{"k": "a", "kind": "OPEN"}, {"k": "a", "kind": "READ", "v": 1.0}, {"k": "a", "kind": "READ", "v_amount": 5.0},
           {"k": "a", "kind": "CLOSE"}]
    assert [r.ingest(e) for e in evs][-1] == [("bill", 6.0, None)]                      # old 1.0 + mapped 5.0


def test_nullable_field_is_legitimately_missing():
    m = _machine(True)
    c = SC.infer(m, [{"k": "a", "kind": "READ", "v": None}, {"k": "b", "kind": "READ", "v": 1.0}])
    assert c["nullable"] == {"READ": ["v"]} and c["required"] == {}


def test_candidates_are_numeric_paths_on_every_incident():
    inc = [dict(raw={"k": "a", "kind": "READ", "v_info": {"amount": 1.0, "unit": "x"}, "shard": 3}),
           dict(raw={"k": "b", "kind": "READ", "v_info": {"amount": 2.0}, "shard": 1})]
    assert SM.candidates(inc) == ["shard", "v_info.amount"]


def test_human_helper_restores_renamed_and_mixed_records():
    for s in (13301, 13309, 13313):                                                      # sc_dev: X6, X6D, X6M (dev seeds)
        P = SCP.Project(s, "sc_dev")
        ev = [e for t in range(1, 17) for e in P.ticks[t]["B"]]
        h = SCP.HumanRefMachine(P)
        assert all(SF.rows_eq(list(map(tuple, h.ingest(e))), w) for e, w in zip(ev, P.ref_B(ev))), (s, P.fault)
