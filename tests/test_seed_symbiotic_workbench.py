"""Comprehensive unit and integration tests for Symbiotic Multi-Backend NEXUS Workbench (Sections A-J)."""
from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import uuid
from pathlib import Path

from nexus.seed.lab import SeedWorkspace
from nexus.seed.storage import load, save
from nexus.seed.symbiotic_workbench import (
    BoundedIngestionJob,
    HierarchicalPlanner,
    KnowledgeAndDocRetriever,
    Lean4ProofBackend,
    MultiFormatDataBackend,
    PolyglotCodingWorkbench,
    StatefulProgramEditor,
    StatefulZ3Coordinator,
    StigmergicCapsuleRegistry,
    SymPySymbolicBackend,
    TypedActionProposal,
)


def _write_csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _chat_send(ws: SeedWorkspace, sid: str, text: str) -> dict:
    return ws.dispatch(dict(
        session_id=sid,
        request=dict(op="chat_send", text=text, id=uuid.uuid4().hex),
    ))["response"]


def test_section_c_six_step_stateful_program_editor_sales_workflow(tmp_path: Path):
    """Demonstrates the exact 6-step sales workflow in chat + session restart:
    1. total sales by region
    2. exclude individual sales below 10 (row_filter rf_1)
    3. exclude regions with totals below 100 (group_filter gf_1)
    4. sort ascending (sort_1)
    5. undo only the group-total filter (selective_undo gf_1 keeping rf_1 and sort_1=asc)
    6. save actual executed AST + bindings, restart session, and apply to a compatible new schema.
    """
    sales_rows = [
        {"region": "East", "amount": "5"},     # excluded in step 2 (<10)
        {"region": "East", "amount": "60"},
        {"region": "East", "amount": "55"},    # East total after rf_1: 115
        {"region": "West", "amount": "4"},     # excluded in step 2 (<10)
        {"region": "West", "amount": "30"},
        {"region": "West", "amount": "25"},    # West total after rf_1: 55 (<100, excluded in step 3, restored in step 5!)
        {"region": "North", "amount": "120"},  # North total: 120
    ]
    new_schema_rows = [
        {"territory": "South", "revenue": "8"},    # <10 excluded by rf_1
        {"territory": "South", "revenue": "45"},   # South total: 45
        {"territory": "Central", "revenue": "90"},
        {"territory": "Central", "revenue": "30"}, # Central total: 120
    ]
    sales_csv = _write_csv(tmp_path / "sales_q1.csv", sales_rows)
    new_csv = _write_csv(tmp_path / "territory_rev.csv", new_schema_rows)

    ws = SeedWorkspace(tmp_path / "store", attach_local_runtime=False)
    sid = ws.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]

    # Step 1: Total sales by region
    r1 = _chat_send(ws, sid, f"program init sales {sales_csv}")
    card1 = r1["chat"]["messages"][-1]["cards"][-1]["data"]
    out1 = json.loads(Path(card1["output_path"]).read_text())
    assert {r["region"]: r["total"] for r in out1} == {"north": 120.0, "east": 120.0, "west": 59.0}

    # Step 2: Exclude individual sales below 10
    r2 = _chat_send(ws, sid, "program row_filter rf_1 >= 10")
    card2 = r2["chat"]["messages"][-1]["cards"][-1]["data"]
    out2 = json.loads(Path(card2["output_path"]).read_text())
    assert {r["region"]: r["total"] for r in out2} == {"north": 120.0, "east": 115.0, "west": 55.0}

    # Step 3: Exclude regions with totals below 100
    r3 = _chat_send(ws, sid, "program group_filter gf_1 >= 100")
    card3 = r3["chat"]["messages"][-1]["cards"][-1]["data"]
    out3 = json.loads(Path(card3["output_path"]).read_text())
    assert {r["region"]: r["total"] for r in out3} == {"north": 120.0, "east": 115.0}

    # Step 4: Sort ascending
    r4 = _chat_send(ws, sid, "program sort asc")
    card4 = r4["chat"]["messages"][-1]["cards"][-1]["data"]
    out4 = json.loads(Path(card4["output_path"]).read_text())
    assert [r["region"] for r in out4] == ["east", "north"]

    # Step 5: Undo ONLY the group-total filter (`gf_1`), keeping `rf_1 >= 10` and `sort_1 == asc`
    r5 = _chat_send(ws, sid, "program selective_undo gf_1")
    card5 = r5["chat"]["messages"][-1]["cards"][-1]["data"]
    out5 = json.loads(Path(card5["output_path"]).read_text())
    assert [(r["region"], r["total"]) for r in out5] == [
        ("west", 55.0),
        ("east", 115.0),
        ("north", 120.0),
    ]
    active_ids = [n["node_id"] for n in card5["active_nodes"]]
    assert "rf_1" in active_ids and "sort_1" in active_ids and "gf_1" not in active_ids

    # Step 6: Save capsule, save & restart session, apply to compatible new schema (`territory`, `revenue`)
    r_save = _chat_send(ws, sid, "program save capsule")
    assert r_save["chat"]["messages"][-1]["status"] == "success"
    saved_receipt = _chat_send(ws, sid, "Save this conversation.")["saved"]

    restored_session = load(ws.directory, sid, saved_receipt["hash"])
    fresh_ws = SeedWorkspace(ws.directory, attach_local_runtime=False)
    fresh_ws.sessions[sid] = restored_session

    r6 = _chat_send(fresh_ws, sid, f"program apply capsule {new_csv}")
    card6 = r6["chat"]["messages"][-1]["cards"][-1]["data"]
    out6 = json.loads(Path(card6["output_path"]).read_text())
    # Verify row_filter >= 10 (excluded 8) and ascending sort were preserved and rebound to territory/revenue!
    assert [(r["territory"], r["total"]) for r in out6] == [
        ("south", 45.0),
        ("central", 120.0),
    ]


def test_section_c_dependent_conflict_detection():
    """Verify selective_undo / remove_node blocks when a downstream node depends on the target."""
    editor = StatefulProgramEditor()
    editor.insert_node("grp_1", "group_by", {"key": "$KEY_COL"})
    editor.insert_node("agg_1", "aggregate", {"key": "$KEY_COL", "metric": "$METRIC_COL", "out_col": "$TOTAL_COL"})
    editor.insert_node("gf_1", "group_filter", {"field": "$TOTAL_COL", "cmp": "ge", "threshold": 50})
    try:
        editor.selective_undo("grp_1")
    except ValueError as exc:
        assert "dependent_nodes_conflict" in str(exc)
    else:
        raise AssertionError("Expected dependent_nodes_conflict when removing grp_1 while agg_1 and gf_1 depend on it")


def test_section_d_json_flattening_and_sqlite_join_where_having_and_cancel(tmp_path: Path):
    """Verify nested JSON flattening/reconstruction and SQLite multi-table JOIN + WHERE vs HAVING + post-commit cancel."""
    payload = {
        "dataset": "regional_orders",
        "version": 2,
        "orders": [
            {"id": "o1", "customer": {"region": "East", "tier": "gold"}, "metrics": {"amount": 25.0}},
            {"id": "o2", "customer": {"region": "West", "tier": "silver"}, "metrics": {"amount": 40.0}},
        ],
    }
    flat, meta = MultiFormatDataBackend.flatten_json_records(payload, record_path="orders")
    assert flat[0]["customer.region"] == "East"
    assert flat[0]["metrics.amount"] == 25.0
    rebuilt = MultiFormatDataBackend.reconstruct_json_records(flat, meta)
    assert rebuilt == payload

    # SQLite multi-table JOIN + WHERE vs HAVING
    db_path = tmp_path / "warehouse.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE orders (order_id TEXT, store_id TEXT, amount REAL)")
    conn.execute("CREATE TABLE stores (store_id TEXT, region TEXT)")
    conn.executemany("INSERT INTO stores VALUES (?, ?)", [("s1", "East"), ("s2", "West"), ("s3", "North")])
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?)", [
        ("1", "s1", 5.0),    # filtered out by WHERE amount >= 10
        ("2", "s1", 60.0),
        ("3", "s1", 50.0),   # East total = 110
        ("4", "s2", 40.0),   # West total = 40 (filtered out by HAVING >= 100)
        ("5", "s3", 130.0),  # North total = 130
    ])
    conn.commit()
    conn.close()

    out_db = tmp_path / "out_summary.sqlite"
    cancel_state = {"flag": False}

    def hook(stage: str):
        if stage == "after_commit":
            cancel_state["flag"] = True

    res = MultiFormatDataBackend.execute_sqlite_workflow(
        db_path=db_path,
        output_db_path=out_db,
        query_spec=dict(
            base_table="orders",
            join_table="stores",
            join_on=("orders.store_id", "stores.store_id"),
            key_expr="stores.region",
            key_alias="region",
            metric_expr="orders.amount",
            agg_fn="SUM",
            out_alias="total",
            where_min=10.0,
            having_min=100.0,
            order="asc",
        ),
        cancelled=lambda: cancel_state["flag"],
        checkpoint=hook,
    )
    assert res["committed"] is True
    assert res["cancelled_after_commit"] is True
    assert res["rows"] == [{"region": "east", "total": 110.0}, {"region": "north", "total": 130.0}]


def test_section_e_polyglot_python_and_typescript_coding_backend(tmp_path: Path):
    """Verify Python + TypeScript CST indexing, multi-file coordination repair, test execution, and selective undo."""
    wb = PolyglotCodingWorkbench(tmp_path / "repo")
    files = {
        "pricing.py": (
            "def compute_discount(subtotal: float, rate: float) -> float:\n"
            "    # Bug: returns rate instead of subtotal * rate\n"
            "    return round(rate, 2)\n"
        ),
        "checkout.py": (
            "from pricing import compute_discount\n\n"
            "def final_total(items: list[float], rate: float, tax_rate: float) -> float:\n"
            "    subtotal = sum(items)\n"
            "    discount = compute_discount(subtotal, rate)\n"
            "    # Bug: adds discount instead of subtracting before tax\n"
            "    taxed = (subtotal + discount) * (1.0 + tax_rate)\n"
            "    return round(taxed, 2)\n"
        ),
        "formatter.ts": (
            "export interface Receipt {\n"
            "  region: string;\n"
            "  total: number;\n"
            "}\n\n"
            "export function formatReceipt(r: Receipt): string {\n"
            "  return `${r.region.trim().toUpperCase()}: $${r.total.toFixed(2)}`;\n"
            "}\n"
        ),
    }
    idx = wb.load_repository(files)
    assert idx["tree_sitter_active"] is True
    assert "compute_discount" in idx["symbols"]["pricing.py"]
    assert "formatReceipt" in idx["symbols"]["formatter.ts"]

    # Multi-file Python repair across pricing.py and checkout.py
    wb.apply_patch(
        "pricing.py",
        "def compute_discount(subtotal: float, rate: float) -> float:\n"
        "    return round(subtotal * rate, 2)\n",
        edit_id="fix_pricing",
    )
    wb.apply_patch(
        "checkout.py",
        "from pricing import compute_discount\n\n"
        "def final_total(items: list[float], rate: float, tax_rate: float) -> float:\n"
        "    subtotal = sum(items)\n"
        "    discount = compute_discount(subtotal, rate)\n"
        "    taxed = (subtotal - discount) * (1.0 + tax_rate)\n"
        "    return round(taxed, 2)\n",
        edit_id="fix_checkout",
    )
    py_res = wb.run_python_tests(
        "from checkout import final_total\n"
        "assert final_total([100.0, 50.0], 0.10, 0.20) == 162.0\n"
    )
    assert py_res["passed"] is True

    # TypeScript validation with real tsc --noEmit and Node execution
    ts_res = wb.run_typescript_validation(
        "import { formatReceipt } from './formatter.ts';\n"
        "const out = formatReceipt({ region: ' east ', total: 42.5 });\n"
        "if (out !== 'EAST: $42.50') throw new Error(out);\n"
    )
    assert ts_res["passed"] is True
    assert ts_res["typecheck_passed"] is True
    assert ts_res["runtime_passed"] is True

    # Selective undo of pricing.py edit without reverting checkout.py edit
    undo_res = wb.selective_undo_edit("fix_pricing")
    assert undo_res["restored"] is True
    assert "subtotal - discount" in wb.files["checkout.py"]
    assert "round(rate, 2)" in wb.files["pricing.py"]


def test_section_f_reasoning_z3_sympy_and_lean4(tmp_path: Path):
    """Verify Z3 constraint graph + selective undo, SymPy symbolic math, and Lean 4 honest status & sorry rejection."""
    ws = SeedWorkspace(tmp_path / "store", attach_local_runtime=False)
    sid = ws.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]

    # Z3 via chat: c1 + c2 (sat) -> c3 makes unsat -> selective undo c3 restores sat
    _chat_send(ws, sid, "z3 add c1: x >= 10")
    r_sat = _chat_send(ws, sid, "z3 add c2: y == x + 5")
    z3_sat = r_sat["chat"]["messages"][-1]["cards"][-1]["data"]["z3"]
    assert z3_sat["status"] == "sat"
    assert z3_sat["translation_verified"] is True

    r_unsat = _chat_send(ws, sid, "z3 add c3: y < 12")
    z3_unsat = r_unsat["chat"]["messages"][-1]["cards"][-1]["data"]["z3"]
    assert z3_unsat["status"] == "unsat"

    r_undo = _chat_send(ws, sid, "z3 undo c3")
    z3_restored = r_undo["chat"]["messages"][-1]["cards"][-1]["data"]["z3"]
    assert z3_restored["status"] == "sat"
    assert z3_restored["model"]["x"] >= 10
    assert z3_restored["model"]["y"] == z3_restored["model"]["x"] + 5

    # SymPy via chat
    r_sym = _chat_send(ws, sid, "sympy solve x**2 - 9 = 0")
    sym_data = r_sym["chat"]["messages"][-1]["cards"][-1]["data"]["sympy"]
    assert sym_data["solutions"] == ["-3", "3"]
    assert sym_data["all_verified"] is True

    # Lean 4: reject `sorry` immediately
    sorry_res = Lean4ProofBackend.check_proof("theorem broken (p : Prop) : p := by sorry")
    assert sorry_res["status"] == "rejected_unverified_token"
    assert sorry_res["verified"] is False

    # Lean 4: honest blocked reporting when `lean` binary is absent on host
    clean_res = Lean4ProofBackend.check_proof("theorem rfl_nat (n : Nat) : n = n := rfl")
    assert clean_res["status"] in ("blocked_missing_runtime", "verified")
    if clean_res["status"] == "blocked_missing_runtime":
        assert clean_res["verified"] is False
        assert "not installed" in clean_res["reason"]


def test_section_g_hierarchical_planner_contract_propagation():
    """Verify 3-level planner (project_goal <-> module_contract <-> function_or_program) revalidates on contract change."""
    planner = HierarchicalPlanner()
    planner.add_node("fn_parse", "function_or_program", "parse_amount", {"min_allowed": 0})
    planner.add_node("mod_ingest", "module_contract", "IngestModule", {"min_allowed": 0}, depends_on=["fn_parse"])
    planner.add_node("goal_pipeline", "project_goal", "AuditPipeline", {"min_allowed": 0}, depends_on=["mod_ingest"])

    state = {"fn_min": 0}
    callbacks = {
        "fn_parse": lambda c: {"passed": state["fn_min"] == c["min_allowed"]},
        "mod_ingest": lambda c: {"passed": state["fn_min"] == c["min_allowed"]},
        "goal_pipeline": lambda c: {"passed": state["fn_min"] == c["min_allowed"]},
    }
    v1 = planner.validate_all(callbacks)
    assert v1["all_verified"] is True

    # Update low-level contract -> invalidates module_contract and project_goal
    prop = planner.update_contract("fn_parse", {"min_allowed": 10})
    assert set(prop["invalidated_nodes"]) == {"fn_parse", "mod_ingest", "goal_pipeline"}

    # Before updating implementation & parent contracts, validation fails
    v2 = planner.validate_all(callbacks)
    assert v2["all_verified"] is False

    # Coordinate implementation and contracts across levels -> revalidation passes
    state["fn_min"] = 10
    planner.update_contract("mod_ingest", {"min_allowed": 10})
    planner.update_contract("goal_pipeline", {"min_allowed": 10})
    v3 = planner.validate_all(callbacks)
    assert v3["all_verified"] is True


def test_section_h_knowledge_and_wikidata_snapshot_adapter():
    """Verify versioned doc retrieval, Wikidata snapshot contradiction detection, and lexical-vs-grounded separation."""
    kr = KnowledgeAndDocRetriever()
    kr.register_document(
        doc_id="spec_tax_v2",
        title="Regional Tax Rounding Spec",
        content="All regional tax calculations must round half-to-even at 2 decimal places.",
        version="2.1.0",
        timestamp="2026-10-23T08:00:00Z",
        grounded_bindings={"round_places": 2, "mode": "half_to_even"},
    )
    kr.load_wikidata_snapshot([
        {
            "qid": "Q9901",
            "label": "Mercury",
            "description": "innermost planet in the Solar System",
            "aliases": ["planet Mercury"],
            "executable_binding": None,
            "claims": [
                {"property": "P2067_mass_kg", "value": 3.3011e23, "source": "IAU_2015"},
            ],
        },
        {
            "qid": "Q9902",
            "label": "Mercury (element)",
            "description": "chemical element with atomic number 80",
            "aliases": ["quicksilver", "Hg"],
            "executable_binding": {"atomic_number": 80},
            "claims": [
                {"property": "P2054_density_g_cm3", "value": 13.534, "source": "CRC_Handbook_v102"},
                {"property": "P2054_density_g_cm3", "value": 13.600, "source": "Legacy_Table_1970"},
            ],
        },
    ])
    res = kr.retrieve("Mercury density and tax rounding spec")
    assert res["provenance_kind"] == "source_attributed"
    assert len(res["doc_hits"]) == 1
    assert res["grounded_executable_bindings"] == {"round_places": 2, "mode": "half_to_even"}
    assert len(res["lexical_candidate_meanings"]) == 2
    assert len(res["contradictions"]) == 1
    assert res["uncertainty"] == "high_contradiction_detected"


def test_section_i_cross_profile_capsule_exchange_and_consolidation(tmp_path: Path):
    """Verify Profile A capsule acquisition, counterexample rejection, export to Profile B, sandbox revalidation on import without auto-execution, and active/cold consolidation."""
    reg_a = StigmergicCapsuleRegistry("profile_a", tmp_path / "profile_a")
    reg_b = StigmergicCapsuleRegistry("profile_b", tmp_path / "profile_b")

    # 1. Faulty candidate rejected with counterexample retained
    bad = reg_a.acquire_from_code_and_docs(
        source_code="def normalize_Margin(row):\n    return round((row['rev'] + row['cost']) / row['rev'], 4)\n",
        doc_spec="Compute profit margin (rev - cost) / rev",
        function_name="normalize_Margin",
        behavioral_probes=[
            {"input": {"rev": 100.0, "cost": 25.0}, "expected": 0.75},
        ],
    )
    assert bad["accepted"] is False
    assert len(bad["counterexamples"]) == 1

    # 2. Valid candidate passes behavioral probes in Profile A
    good = reg_a.acquire_from_code_and_docs(
        source_code="def compute_margin(row):\n    return round((row['rev'] - row['cost']) / row['rev'], 4)\n",
        doc_spec="Compute profit margin (rev - cost) / rev",
        function_name="compute_margin",
        behavioral_probes=[
            {"input": {"rev": 100.0, "cost": 25.0}, "expected": 0.75},
            {"input": {"rev": 200.0, "cost": 50.0}, "expected": 0.75},
        ],
    )
    assert good["accepted"] is True
    cid = good["capsule_id"]

    # 3. Export from Profile A -> Import into isolated Profile B
    bundle = reg_a.export_capsule_bundle(cid)
    imp = reg_b.import_capsule_bundle(bundle)
    assert imp["imported"] is True
    assert imp["auto_executed_on_import"] is False
    assert imp["sandbox_revalidated"] is True

    # 4. Execute in Profile B
    exec_b = reg_b.execute_capsule(cid, {"rev": 80.0, "cost": 20.0})
    assert exec_b["output"] == 0.75
    assert exec_b["reuse_hits"] == 1

    # 5. Consolidate & prune: Profile A never reused `cid` (0 hits), so it moves to cold; Profile B reused `cid`, so it stays active!
    cons_a = reg_a.consolidate_and_prune()
    cons_b = reg_b.consolidate_and_prune()
    assert cid in cons_a["moved_to_cold"]
    assert cid in cons_b["kept_active"]

    # 6. Bounded ingestion job with cancellation support
    job = BoundedIngestionJob(reg_a, max_items=4, max_wall_s=5.0)
    jres = job.run([
        {
            "source_code": "def clamp_positive(x):\n    return max(0, x)\n",
            "doc_spec": "Clamp integer to >= 0",
            "function_name": "clamp_positive",
            "behavioral_probes": [{"input": -5, "expected": 0}, {"input": 7, "expected": 7}],
        }
    ])
    assert jres["job_status"] == "completed"
    assert len(jres["accepted_capsules"]) == 1
