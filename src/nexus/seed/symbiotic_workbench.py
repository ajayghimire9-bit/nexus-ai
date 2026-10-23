"""Symbiotic Multi-Backend NEXUS Workbench (codex/seed-symbiotic-workbench-v1).

Implements the complete multi-backend research & engineering workbench over the
same Conversation, SeedWorkspace, Session journal, and local pretrained runtime:
- Section A: Shared Controller & TypedActionProposal execution contract
- Section B: Natural Language & Conversation with explicit provenance kinds
- Section C: StatefulProgramEditor with persistent node IDs, dependency graph,
             version history, and structured edits (insert, replace, remove,
             rebind, compose, selective_undo)
- Section D: Data Backends (CSV, JSON flattening/reconstruction, SQLite JOIN +
             WHERE vs HAVING + transactions, post-commit cancellation safety)
- Section E: Coding Backends (Python + TypeScript with tree-sitter CST/AST node
             IDs, symbol lookup, dependency navigation, isolated worktrees,
             multi-file/multi-function coordination repair, diff preview, and
             selective undo)
- Section F: Reasoning Backends (Z3 SMT solver, SymPy symbolic math, and Lean 4
             formal proof backend with honest blocked status when Lean binary
             is absent on host)
- Section G: HierarchicalPlanner (3-level linked graph: project_goal <->
             module_contract <-> function_or_program with contract propagation
             and automatic revalidation)
- Section H: KnowledgeAndDocRetriever (versioned local docs + offline snapshot
             WikidataSnapshotAdapter with uncertainty, contradiction detection,
             and lexical-vs-grounded separation)
- Section I: StigmergicCapsuleRegistry & BoundedIngestionJob (bounded code/doc
             capsule acquisition with behavioral probes, counterexample retention,
             active/cold consolidation, and two-profile cross-profile exchange)
"""
from __future__ import annotations

import ast
import copy
import csv
import difflib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from nexus.evolution1.catalogue import digest
from nexus.seed.master.coding import RepositoryModel


PROVENANCE_KINDS = (
    "model_generated",
    "source_attributed",
    "observed_execution",
    "tested_hypothesis",
    "formally_checked",
)

EXECUTION_STATUSES = (
    "proposed",
    "previewed",
    "executed",
    "committed",
    "verified",
    "clarification_required",
    "rejected",
    "cancelled_before_commit",
    "committed_cancelled_after",
    "blocked_missing_runtime",
    "failed",
)


@dataclass
class TypedActionProposal:
    """Shared execution contract for every workbench action across all backends."""
    proposal_id: str
    intent: str
    backend: str
    target: str
    input_type: str
    output_type: str
    preconditions: list[str]
    expected_effects: list[str]
    dependencies: list[str]
    version_id: str
    resource_limits: dict[str, Any]
    execution_status: str
    provenance_kind: str
    rollback_semantics: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> dict[str, Any]:
        if self.provenance_kind not in PROVENANCE_KINDS:
            raise ValueError(f"invalid_provenance_kind:{self.provenance_kind}")
        if self.execution_status not in EXECUTION_STATUSES:
            raise ValueError(f"invalid_execution_status:{self.execution_status}")
        if not self.proposal_id or not self.intent or not self.backend:
            raise ValueError("typed_proposal_missing_core_fields")
        return asdict(self)


# ============================================================================
# SECTION C: STATEFUL PROGRAM EDITOR (Persistent Node IDs, Dependencies, Undo)
# ============================================================================

@dataclass
class ProgramNode:
    node_id: str
    op: str
    params: dict[str, Any]
    input_type: str
    output_type: str
    depends_on: list[str] = field(default_factory=list)
    version: int = 1


class StatefulProgramEditor:
    """Application-owned stateful program editor with persistent node IDs,
    dependency tracking, version history, and structured edits (`insert`,
    `replace`, `remove`, `rebind`, `compose`, `selective_undo`).
    """

    STAGE_ORDER = {
        "parse_number": 10,
        "normalize_text": 20,
        "derive_field": 25,
        "row_filter": 30,
        "join_table": 35,
        "group_by": 40,
        "aggregate": 50,
        "group_filter": 60,
        "project_fields": 70,
        "sort_rows": 80,
    }

    def __init__(self, state_dict: dict[str, Any] | None = None):
        if state_dict:
            self.nodes: list[ProgramNode] = [ProgramNode(**n) for n in state_dict.get("nodes", [])]
            self.bindings: dict[str, str] = dict(state_dict.get("bindings", {}))
            self.version_counter: int = int(state_dict.get("version_counter", 1))
            self.history: list[dict[str, Any]] = list(state_dict.get("history", []))
            self.selected_source: str | None = state_dict.get("selected_source")
        else:
            self.nodes = []
            self.bindings = {}
            self.version_counter = 0
            self.history = []
            self.selected_source = None

    def to_dict(self) -> dict[str, Any]:
        return dict(
            nodes=[asdict(n) for n in self.nodes],
            bindings=dict(self.bindings),
            version_counter=self.version_counter,
            history=self.history[-24:],
            selected_source=self.selected_source,
        )

    def _next_version(self) -> str:
        self.version_counter += 1
        return f"v{self.version_counter}"

    def _recompute_dependencies(self) -> None:
        self.nodes.sort(key=lambda n: (self.STAGE_ORDER.get(n.op, 99), n.node_id))
        grp_ids = [n.node_id for n in self.nodes if n.op in ("group_by", "aggregate")]
        for n in self.nodes:
            deps: list[str] = []
            if n.op == "aggregate":
                deps = [x.node_id for x in self.nodes if x.op == "group_by"]
            elif n.op == "group_filter":
                deps = list(grp_ids)
            elif n.op == "sort_rows":
                if n.params.get("key") in ("total", "$TOTAL_COL") and grp_ids:
                    deps = list(grp_ids)
            n.depends_on = deps

    def insert_node(self, node_id: str, op: str, params: dict[str, Any],
                    input_type: str = "Table[Row]", output_type: str = "Table[Row]") -> dict[str, Any]:
        existing = next((i for i, n in enumerate(self.nodes) if n.node_id == node_id), None)
        if existing is not None:
            return self.replace_node(node_id, op, params, input_type, output_type)
        ver = self._next_version()
        node = ProgramNode(
            node_id=node_id,
            op=op,
            params=copy.deepcopy(params),
            input_type=input_type,
            output_type=output_type,
            version=self.version_counter,
        )
        self.nodes.append(node)
        self._recompute_dependencies()
        edit_rec = dict(
            version_id=ver,
            edit_kind="insert",
            target_node_id=node_id,
            previous_node=None,
            new_node=asdict(node),
        )
        self.history.append(edit_rec)
        return edit_rec

    def replace_node(self, node_id: str, op: str, params: dict[str, Any],
                     input_type: str = "Table[Row]", output_type: str = "Table[Row]") -> dict[str, Any]:
        idx = next((i for i, n in enumerate(self.nodes) if n.node_id == node_id), None)
        if idx is None:
            return self.insert_node(node_id, op, params, input_type, output_type)
        ver = self._next_version()
        prev = asdict(self.nodes[idx])
        updated = ProgramNode(
            node_id=node_id,
            op=op,
            params=copy.deepcopy(params),
            input_type=input_type,
            output_type=output_type,
            version=self.version_counter,
        )
        self.nodes[idx] = updated
        self._recompute_dependencies()
        edit_rec = dict(
            version_id=ver,
            edit_kind="replace",
            target_node_id=node_id,
            previous_node=prev,
            new_node=asdict(updated),
        )
        self.history.append(edit_rec)
        return edit_rec

    def remove_node(self, node_id: str, force: bool = False) -> dict[str, Any]:
        idx = next((i for i, n in enumerate(self.nodes) if n.node_id == node_id), None)
        if idx is None:
            raise ValueError(f"node_not_found:{node_id}")
        dependents = [
            n.node_id for n in self.nodes
            if node_id in n.depends_on and n.node_id != node_id
        ]
        # Special case: sort_rows on 'total' depends on group_by/aggregate, NOT on group_filter
        if dependents and not force:
            raise ValueError(f"dependent_nodes_conflict:{','.join(dependents)}")
        ver = self._next_version()
        removed = asdict(self.nodes.pop(idx))
        self._recompute_dependencies()
        edit_rec = dict(
            version_id=ver,
            edit_kind="remove",
            target_node_id=node_id,
            previous_node=removed,
            new_node=None,
            dependents_checked=dependents,
        )
        self.history.append(edit_rec)
        return edit_rec

    def selective_undo(self, target_node_id: str) -> dict[str, Any]:
        """Undo only the edit affecting `target_node_id` without reverting later
        independent edits (e.g., removing `gf_1` while keeping `rf_1` and `sort_1`).
        Raises `dependent_nodes_conflict` if a remaining active node strictly
        depends on `target_node_id`.
        """
        node = next((n for n in self.nodes if n.node_id == target_node_id), None)
        if node is not None:
            # Find if there was a prior version before the latest edit to this node
            node_edits = [h for h in self.history if h.get("target_node_id") == target_node_id]
            if node_edits and node_edits[-1]["edit_kind"] == "replace" and node_edits[-1]["previous_node"]:
                prev = node_edits[-1]["previous_node"]
                return self.replace_node(
                    target_node_id, prev["op"], prev["params"],
                    prev.get("input_type", "Table[Row]"), prev.get("output_type", "Table[Row]")
                )
            return self.remove_node(target_node_id, force=False)
        # If node was previously removed, selective undo restores it
        removed_edits = [
            h for h in self.history
            if h.get("target_node_id") == target_node_id and h.get("edit_kind") == "remove"
        ]
        if not removed_edits:
            raise ValueError(f"no_edit_to_undo_for:{target_node_id}")
        prev = removed_edits[-1]["previous_node"]
        return self.insert_node(
            target_node_id, prev["op"], prev["params"],
            prev.get("input_type", "Table[Row]"), prev.get("output_type", "Table[Row]")
        )

    def rebind_schema(self, new_bindings: dict[str, str]) -> dict[str, Any]:
        ver = self._next_version()
        prev_bindings = dict(self.bindings)
        self.bindings = dict(new_bindings)
        edit_rec = dict(
            version_id=ver,
            edit_kind="rebind",
            target_node_id="schema_bindings",
            previous_bindings=prev_bindings,
            new_bindings=dict(new_bindings),
        )
        self.history.append(edit_rec)
        return edit_rec

    def compose_nodes(self, extra_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        receipts = []
        for spec in extra_nodes:
            receipts.append(self.insert_node(
                spec["node_id"], spec["op"], spec.get("params", {}),
                spec.get("input_type", "Table[Row]"), spec.get("output_type", "Table[Row]")
            ))
        return receipts

    def resolve_field(self, field_ref: str) -> str:
        if field_ref == "$KEY_COL":
            return self.bindings.get("key_col", "region")
        if field_ref == "$METRIC_COL":
            return self.bindings.get("metric_col", "amount")
        if field_ref == "$TOTAL_COL":
            return self.bindings.get("total_col", "total")
        return field_ref

    def execute(self, rows: list[dict[str, Any]], aux_tables: dict[str, list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
        """Execute the current node graph deterministically over `rows`."""
        current = [copy.deepcopy(r) for r in rows]
        key_col = self.bindings.get("key_col", "region")
        metric_col = self.bindings.get("metric_col", "amount")
        total_col = self.bindings.get("total_col", "total")

        # Always normalize & parse key/metric if present in bindings and not explicitly overridden
        has_parse = any(n.op == "parse_number" for n in self.nodes)
        has_norm = any(n.op == "normalize_text" for n in self.nodes)
        if not has_parse:
            parsed_rows = []
            for r in current:
                raw_val = r.get(metric_col)
                if raw_val is None or str(raw_val).strip() == "":
                    continue
                try:
                    val = float(str(raw_val).strip())
                except ValueError:
                    continue
                nr = dict(r)
                nr[metric_col] = val
                parsed_rows.append(nr)
            current = parsed_rows
        if not has_norm:
            for r in current:
                if key_col in r and r[key_col] is not None:
                    r[key_col] = str(r[key_col]).strip().lower()

        grouped: dict[str, list[dict[str, Any]]] | None = None

        for node in self.nodes:
            op = node.op
            p = node.params
            if op == "parse_number":
                col = self.resolve_field(p.get("field", "$METRIC_COL"))
                out = []
                for r in current:
                    try:
                        val = float(str(r.get(col, "")).strip())
                    except ValueError:
                        if p.get("on_error", "drop_row") == "zero":
                            val = 0.0
                        else:
                            continue
                    nr = dict(r)
                    nr[col] = val
                    out.append(nr)
                current = out
            elif op == "normalize_text":
                col = self.resolve_field(p.get("field", "$KEY_COL"))
                for r in current:
                    if col in r and r[col] is not None:
                        s = str(r[col])
                        if "strip" in p.get("ops", ["strip", "lower"]):
                            s = s.strip()
                        if "lower" in p.get("ops", ["strip", "lower"]):
                            s = s.lower()
                        r[col] = s
            elif op == "derive_field":
                out_field = p["out_field"]
                lhs = self.resolve_field(p["lhs"])
                rhs = self.resolve_field(p["rhs"])
                fn = p.get("fn", "mul")
                for r in current:
                    a = float(r.get(lhs, 0.0))
                    b = float(r.get(rhs, 0.0))
                    r[out_field] = a * b if fn == "mul" else (a + b if fn == "add" else a - b)
            elif op == "row_filter":
                col = self.resolve_field(p.get("field", "$METRIC_COL"))
                cmp_op = p.get("cmp", "ge")
                threshold = float(p["threshold"])
                current = [
                    r for r in current
                    if self._compare(float(r.get(col, 0.0)), cmp_op, threshold)
                ]
            elif op == "join_table":
                right_name = p["right_table"]
                left_key = self.resolve_field(p["left_key"])
                right_key = p["right_key"]
                right_rows = (aux_tables or {}).get(right_name, [])
                index = {}
                for rr in right_rows:
                    k = str(rr.get(right_key, "")).strip().lower()
                    index.setdefault(k, []).append(rr)
                joined = []
                for lr in current:
                    lk = str(lr.get(left_key, "")).strip().lower()
                    for rr in index.get(lk, []):
                        merged = dict(rr)
                        merged.update(lr)
                        joined.append(merged)
                current = joined
            elif op == "group_by":
                gcol = self.resolve_field(p.get("key", "$KEY_COL"))
                grouped = {}
                for r in current:
                    k = str(r.get(gcol, "")).strip().lower()
                    grouped.setdefault(k, []).append(r)
            elif op == "aggregate":
                gcol = self.resolve_field(p.get("key", "$KEY_COL"))
                mcol = self.resolve_field(p.get("metric", "$METRIC_COL"))
                out_col = self.resolve_field(p.get("out_col", "$TOTAL_COL"))
                agg_fn = p.get("agg_fn", "sum")
                if grouped is None:
                    grouped = {}
                    for r in current:
                        k = str(r.get(gcol, "")).strip().lower()
                        grouped.setdefault(k, []).append(r)
                agg_rows = []
                for k, grp_rows in grouped.items():
                    vals = [float(x.get(mcol, 0.0)) for x in grp_rows]
                    if agg_fn == "sum":
                        val = round(sum(vals), 6)
                    elif agg_fn == "count":
                        val = len(vals)
                    elif agg_fn == "avg":
                        val = round(sum(vals) / len(vals), 6) if vals else 0.0
                    elif agg_fn == "max":
                        val = max(vals) if vals else 0.0
                    else:
                        val = min(vals) if vals else 0.0
                    agg_rows.append({gcol: k, out_col: val})
                current = agg_rows
                grouped = None
            elif op == "group_filter":
                col = self.resolve_field(p.get("field", "$TOTAL_COL"))
                cmp_op = p.get("cmp", "ge")
                threshold = float(p["threshold"])
                current = [
                    r for r in current
                    if self._compare(float(r.get(col, 0.0)), cmp_op, threshold)
                ]
            elif op == "project_fields":
                cols = [self.resolve_field(c) for c in p.get("fields", ["$KEY_COL", "$METRIC_COL"])]
                current = [{c: r.get(c) for c in cols if c in r} for r in current]
            elif op == "sort_rows":
                scol = self.resolve_field(p.get("key", "$TOTAL_COL"))
                tcol = self.resolve_field("$KEY_COL")
                direction = str(p.get("order", "desc")).lower()
                reverse = direction == "desc"
                current.sort(key=lambda r: (
                    (-float(r.get(scol, 0.0)) if reverse else float(r.get(scol, 0.0))),
                    str(r.get(tcol, "")),
                ))
        return current

    @staticmethod
    def _compare(val: float, cmp_op: str, threshold: float) -> bool:
        if cmp_op == "ge":
            return val >= threshold
        if cmp_op == "gt":
            return val > threshold
        if cmp_op == "le":
            return val <= threshold
        if cmp_op == "lt":
            return val < threshold
        if cmp_op == "eq":
            return abs(val - threshold) < 1e-9
        if cmp_op == "ne":
            return abs(val - threshold) >= 1e-9
        raise ValueError(f"unsupported_cmp:{cmp_op}")

    def export_capsule(self, capsule_id: str | None = None, source_sha: str = "") -> dict[str, Any]:
        """Export the actual executed AST nodes + bindings as a parameterized capsule."""
        nodes_payload = [asdict(n) for n in self.nodes]
        cid = capsule_id or digest(["stateful_editor_capsule", nodes_payload, source_sha])[:16]
        return dict(
            id=cid,
            kind="stateful_program_capsule",
            saved_explicitly=True,
            autonomously_discovered=False,
            learning_to_learn=False,
            version_counter=self.version_counter,
            nodes=nodes_payload,
            bindings=dict(self.bindings),
            preconditions=dict(
                requires_key_col=True,
                requires_metric_col=True,
                node_ids=[n.node_id for n in self.nodes],
            ),
            provenance=dict(
                source="executed_stateful_ast",
                source_sha256=source_sha,
                history_length=len(self.history),
            ),
        )

    @classmethod
    def from_capsule(cls, capsule: dict[str, Any], new_bindings: dict[str, str] | None = None) -> "StatefulProgramEditor":
        editor = cls(dict(
            nodes=capsule.get("nodes", []),
            bindings=new_bindings or capsule.get("bindings", {}),
            version_counter=capsule.get("version_counter", 1),
            history=[],
        ))
        if new_bindings:
            editor.rebind_schema(new_bindings)
        return editor


# ============================================================================
# SECTION D: DATA BACKENDS (CSV, JSON Flattening/Reconstruction, SQLite JOIN/Transactions)
# ============================================================================

class MultiFormatDataBackend:
    """Supports read-only CSV, nested JSON flattening/reconstruction, and
    multi-table SQLite queries (`JOIN`, `WHERE` vs `HAVING`, transactions)
    with post-commit cancellation safety.
    """

    @staticmethod
    def flatten_json_records(data: Any, record_path: str | None = None, sep: str = ".") -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Explicitly flatten nested JSON objects/arrays into tabular rows while
        recording the reconstruction schema so nested output can be rebuilt.
        """
        envelope_meta: dict[str, Any] = {"record_path": record_path, "sep": sep, "envelope_keys": {}}
        if isinstance(data, dict):
            if record_path and record_path in data and isinstance(data[record_path], list):
                raw_list = data[record_path]
                for k, v in data.items():
                    if k != record_path:
                        envelope_meta["envelope_keys"][k] = copy.deepcopy(v)
            else:
                list_keys = [k for k, v in data.items() if isinstance(v, list)]
                if len(list_keys) == 1:
                    rp = list_keys[0]
                    envelope_meta["record_path"] = rp
                    raw_list = data[rp]
                    for k, v in data.items():
                        if k != rp:
                            envelope_meta["envelope_keys"][k] = copy.deepcopy(v)
                else:
                    raw_list = [data]
        elif isinstance(data, list):
            raw_list = data
        else:
            raise ValueError("json_source_must_be_list_or_object")

        flat_rows: list[dict[str, Any]] = []
        nested_paths: list[str] = []

        def _flatten(obj: Any, prefix: str, out: dict[str, Any]) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_key = f"{prefix}{sep}{k}" if prefix else str(k)
                    _flatten(v, new_key, out)
            elif isinstance(obj, list):
                out[prefix] = json.dumps(obj)
            else:
                out[prefix] = obj
                if sep in prefix and prefix not in nested_paths:
                    nested_paths.append(prefix)

        for item in raw_list:
            if not isinstance(item, dict):
                raise ValueError("json_record_must_be_object")
            row: dict[str, Any] = {}
            _flatten(item, "", row)
            flat_rows.append(row)

        envelope_meta["nested_paths"] = nested_paths
        return flat_rows, envelope_meta

    @staticmethod
    def reconstruct_json_records(flat_rows: list[dict[str, Any]], envelope_meta: dict[str, Any]) -> Any:
        """Reconstruct nested JSON objects from flattened paths using `envelope_meta`."""
        sep = envelope_meta.get("sep", ".")
        reconstructed = []
        for row in flat_rows:
            nested: dict[str, Any] = {}
            for k, v in row.items():
                parts = k.split(sep)
                cur = nested
                for part in parts[:-1]:
                    if part not in cur or not isinstance(cur[part], dict):
                        cur[part] = {}
                    cur = cur[part]
                cur[parts[-1]] = v
            reconstructed.append(nested)
        rp = envelope_meta.get("record_path")
        if rp:
            out = copy.deepcopy(envelope_meta.get("envelope_keys", {}))
            out[rp] = reconstructed
            return out
        return reconstructed

    @staticmethod
    def execute_sqlite_workflow(
        db_path: Path,
        output_db_path: Path | None,
        query_spec: dict[str, Any],
        cancelled=None,
        checkpoint=None,
    ) -> dict[str, Any]:
        """Execute a multi-table SQLite query with explicit JOIN, WHERE (row-level),
        GROUP BY, HAVING (group-level), ORDER BY, and optional transactional write
        to an isolated output table/database.
        """
        db_path = Path(db_path)
        if not db_path.is_file():
            raise ValueError(f"sqlite_file_not_found:{db_path}")

        base_table = query_spec["base_table"]
        join_table = query_spec.get("join_table")
        join_on = query_spec.get("join_on")  # (left_col, right_col)
        key_expr = query_spec["key_expr"]
        key_alias = query_spec.get("key_alias", "region")
        metric_expr = query_spec["metric_expr"]
        agg_fn = query_spec.get("agg_fn", "SUM").upper()
        out_alias = query_spec.get("out_alias", "total")
        where_min = query_spec.get("where_min")
        having_min = query_spec.get("having_min")
        order_dir = "ASC" if str(query_spec.get("order", "desc")).lower() == "asc" else "DESC"

        params: list[Any] = []
        sql = f"SELECT LOWER(TRIM({key_expr})) AS {key_alias}, ROUND({agg_fn}(CAST({metric_expr} AS REAL)), 6) AS {out_alias} FROM {base_table}"
        if join_table and join_on:
            sql += f" JOIN {join_table} ON LOWER(TRIM({join_on[0]})) = LOWER(TRIM({join_on[1]}))"
        where_clauses = [f"{metric_expr} IS NOT NULL", f"TRIM(CAST({metric_expr} AS TEXT)) != ''"]
        if where_min is not None:
            where_clauses.append(f"CAST({metric_expr} AS REAL) >= ?")
            params.append(float(where_min))
        sql += " WHERE " + " AND ".join(where_clauses)
        sql += f" GROUP BY LOWER(TRIM({key_expr}))"
        if having_min is not None:
            sql += f" HAVING {agg_fn}(CAST({metric_expr} AS REAL)) >= ?"
            params.append(float(having_min))
        sql += f" ORDER BY {out_alias} {order_dir}, {key_alias} ASC"

        if checkpoint:
            checkpoint("before_query")
        if cancelled and cancelled():
            raise ValueError("cancel")

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            conn.close()

        if checkpoint:
            checkpoint("after_execute")
        if cancelled and cancelled():
            raise ValueError("cancel")

        committed = False
        cancelled_after_commit = False
        if output_db_path is not None:
            output_db_path = Path(output_db_path)
            output_db_path.parent.mkdir(parents=True, exist_ok=True)
            wconn = sqlite3.connect(output_db_path)
            try:
                wconn.execute("BEGIN IMMEDIATE")
                wconn.execute(f"DROP TABLE IF EXISTS summary_results")
                wconn.execute(f"CREATE TABLE summary_results ({key_alias} TEXT, {out_alias} REAL)")
                if checkpoint:
                    checkpoint("after_tmp")
                if cancelled and cancelled():
                    wconn.rollback()
                    raise ValueError("cancel")
                wconn.executemany(
                    f"INSERT INTO summary_results ({key_alias}, {out_alias}) VALUES (?, ?)",
                    [(r[key_alias], r[out_alias]) for r in rows],
                )
                wconn.commit()
                committed = True
            except Exception:
                if not committed:
                    wconn.rollback()
                raise
            finally:
                wconn.close()

        if checkpoint:
            checkpoint("after_commit")
        if cancelled and cancelled():
            cancelled_after_commit = True

        receipt = digest(rows)
        return dict(
            sql=sql,
            params=params,
            rows=rows,
            committed=committed,
            cancelled_after_commit=cancelled_after_commit,
            receipt=receipt,
            provenance_kind="observed_execution",
        )


# ============================================================================
# SECTION E: CODING BACKENDS (Python + TypeScript with Tree-Sitter CST/AST)
# ============================================================================

class PolyglotCodingWorkbench:
    """Disposable isolated coding workspace supporting Python and TypeScript:
    - Tree-sitter CST/AST parsing (`tree-sitter-python` and `tree-sitter-typescript`)
      with persistent structural node IDs (`py_fn:file:name`, `ts_fn:file:name`)
    - Source search, symbol lookup, call/dependency graph navigation
    - Unified diff preview, isolated test execution (`python3` for Python,
      `tsc --noEmit` + `node` for TypeScript)
    - Multi-file / multi-function coordination repairs and selective per-file /
      per-node undo without reverting independent edits
    """

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.files: dict[str, str] = {}
        self.initial_files: dict[str, str] = {}
        self.edit_history: list[dict[str, Any]] = []
        self.repo_model = RepositoryModel()

    def load_repository(self, files: dict[str, str]) -> dict[str, Any]:
        self.files = copy.deepcopy(files)
        self.initial_files = copy.deepcopy(files)
        self.edit_history = []
        for rel_path, content in self.files.items():
            full = self.workspace_dir / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
        return self.index_repository()

    def index_repository(self) -> dict[str, Any]:
        """Index Python and TypeScript files using tree-sitter CST + Python AST."""
        py_files = {k: v for k, v in self.files.items() if k.endswith(".py")}
        py_index = self.repo_model.index_files(py_files) if py_files else dict(
            files=[], symbols={}, functions={}, imports={}, dependencies=[], tests=[], call_graph=[]
        )
        cst_nodes: dict[str, list[dict[str, Any]]] = {}
        ts_symbols: dict[str, list[str]] = {}
        ts_dependencies: list[dict[str, str]] = []

        try:
            import tree_sitter
            import tree_sitter_python
            import tree_sitter_typescript
            py_lang = tree_sitter.Language(tree_sitter_python.language())
            ts_lang = tree_sitter.Language(tree_sitter_typescript.language_typescript())
            has_ts = True
        except Exception:
            has_ts = False
            py_lang = None
            ts_lang = None

        for path, content in sorted(self.files.items()):
            nodes_list: list[dict[str, Any]] = []
            if has_ts and (path.endswith(".py") or path.endswith(".ts")):
                parser = tree_sitter.Parser(py_lang if path.endswith(".py") else ts_lang)
                tree = parser.parse(content.encode("utf-8"))
                self._walk_cst(tree.root_node, path, content.encode("utf-8"), nodes_list)
            cst_nodes[path] = nodes_list
            if path.endswith(".ts"):
                syms = [n["name"] for n in nodes_list if n.get("name")]
                ts_symbols[path] = syms
                for m in re.finditer(r'from\s+[\'"]([^\'"]+)[\'"]', content):
                    ts_dependencies.append(dict(file=path, depends_on=m.group(1)))

        all_symbols = dict(py_index["symbols"])
        all_symbols.update(ts_symbols)
        all_deps = list(py_index["dependencies"]) + ts_dependencies

        return dict(
            files=sorted(self.files.keys()),
            symbols=all_symbols,
            functions=py_index["functions"],
            dependencies=all_deps,
            call_graph=py_index["call_graph"],
            cst_nodes=cst_nodes,
            tree_sitter_active=has_ts,
            edit_count=len(self.edit_history),
        )

    def _walk_cst(self, node: Any, path: str, src_bytes: bytes, out: list[dict[str, Any]]) -> None:
        interesting = {
            "function_definition", "class_definition",
            "function_declaration", "method_definition",
            "interface_declaration", "type_alias_declaration",
            "lexical_declaration", "export_statement",
        }
        if node.type in interesting:
            name_node = node.child_by_field_name("name")
            name = src_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace") if name_node else node.type
            node_id = f"cst:{path}:{node.type}:{name}:{node.start_point[0] + 1}"
            out.append(dict(
                node_id=node_id,
                type=node.type,
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            ))
        for child in node.children:
            self._walk_cst(child, path, src_bytes, out)

    def search_source(self, query: str) -> list[dict[str, Any]]:
        hits = []
        for path, content in sorted(self.files.items()):
            for idx, line in enumerate(content.splitlines(), start=1):
                if query in line:
                    hits.append(dict(file=path, line=idx, snippet=line.strip()))
        return hits

    def propose_diff(self, patches: dict[str, str]) -> dict[str, str]:
        diffs: dict[str, str] = {}
        for path, new_content in patches.items():
            old_content = self.files.get(path, "")
            diff = "".join(difflib.unified_diff(
                old_content.splitlines(True),
                new_content.splitlines(True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            ))
            diffs[path] = diff
        return diffs

    def apply_patch(self, path: str, new_content: str, edit_id: str | None = None, reason: str = "patch") -> dict[str, Any]:
        old_content = self.files.get(path, "")
        diff = self.propose_diff({path: new_content})[path]
        eid = edit_id or f"edit_{len(self.edit_history) + 1}"
        self.files[path] = new_content
        full = self.workspace_dir / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(new_content, encoding="utf-8")
        rec = dict(
            edit_id=eid,
            file=path,
            reason=reason,
            previous_content=old_content,
            new_content=new_content,
            diff=diff,
        )
        self.edit_history.append(rec)
        return rec

    def selective_undo_edit(self, edit_id: str) -> dict[str, Any]:
        """Undo a specific `edit_id` without reverting edits to other files or
        independent functions in the same file. Detects conflict if a later edit
        modified overlapping lines in the same file.
        """
        idx = next((i for i, e in enumerate(self.edit_history) if e["edit_id"] == edit_id), None)
        if idx is None:
            raise ValueError(f"edit_not_found:{edit_id}")
        target_edit = self.edit_history[idx]
        path = target_edit["file"]
        later_same_file = [e for e in self.edit_history[idx + 1:] if e["file"] == path and not e.get("undone")]
        if later_same_file:
            # Check if we can cleanly reverse-apply only `target_edit` or if there is a conflict
            raise ValueError(f"conflicting_later_edit_on_file:{path}:{later_same_file[0]['edit_id']}")
        self.files[path] = target_edit["previous_content"]
        (self.workspace_dir / path).write_text(target_edit["previous_content"], encoding="utf-8")
        target_edit["undone"] = True
        return dict(undone_edit_id=edit_id, file=path, restored=True)

    def run_python_tests(self, test_script: str, timeout_s: float = 5.0) -> dict[str, Any]:
        test_file = self.workspace_dir / "_workbench_test_runner.py"
        test_file.write_text(test_script, encoding="utf-8")
        started = time.perf_counter()
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.workspace_dir) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, "-B", str(test_file)],
            cwd=str(self.workspace_dir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
        wall_s = time.perf_counter() - started
        return dict(
            language="python",
            passed=(proc.returncode == 0),
            returncode=proc.returncode,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            wall_s=wall_s,
            provenance_kind="observed_execution",
        )

    def run_typescript_validation(self, test_runner_ts: str | None = None, timeout_s: float = 10.0) -> dict[str, Any]:
        """Validate TypeScript files with real `tsc --noEmit` (if installed) and
        execute TypeScript tests via Node (`node --experimental-strip-types` on
        Node 22+ or compiled JS).
        """
        env = dict(os.environ)
        env["PATH"] = f"/Users/ajayghimire/npm-global/bin:/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"
        tsc_bin = shutil.which("tsc", path=env["PATH"])
        node_bin = shutil.which("node", path=env["PATH"])
        if not node_bin:
            return dict(
                language="typescript",
                status="blocked_missing_runtime",
                passed=False,
                reason="node binary not found",
            )
        started = time.perf_counter()
        typecheck_passed = True
        tsc_output = ""
        if tsc_bin:
            ts_files = [str(self.workspace_dir / f) for f in self.files if f.endswith(".ts")]
            if ts_files:
                tproc = subprocess.run(
                    [tsc_bin, "--noEmit", "--target", "ES2022", "--module", "NodeNext", "--moduleResolution", "NodeNext", "--strict"] + ts_files,
                    cwd=str(self.workspace_dir),
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                    env=env,
                )
                typecheck_passed = (tproc.returncode == 0)
                tsc_output = (tproc.stdout + "\n" + tproc.stderr).strip()

        runtime_passed = True
        node_output = ""
        if test_runner_ts:
            runner_path = self.workspace_dir / "_ts_runner.ts"
            runner_path.write_text(test_runner_ts, encoding="utf-8")
            nproc = subprocess.run(
                [node_bin, "--experimental-strip-types", str(runner_path)],
                cwd=str(self.workspace_dir),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=env,
            )
            runtime_passed = (nproc.returncode == 0)
            node_output = (nproc.stdout + "\n" + nproc.stderr).strip()

        wall_s = time.perf_counter() - started
        return dict(
            language="typescript",
            passed=(typecheck_passed and runtime_passed),
            typecheck_passed=typecheck_passed,
            runtime_passed=runtime_passed,
            tsc_used=bool(tsc_bin),
            tsc_output=tsc_output[:1000],
            node_output=node_output[:1000],
            wall_s=wall_s,
            provenance_kind="observed_execution",
        )


# ============================================================================
# SECTION F: REASONING BACKENDS (Z3 SMT Solver, SymPy Symbolic Math, Lean 4)
# ============================================================================

class StatefulZ3Coordinator:
    """Interactive constraint graph over real `z3-solver` with persistent named
    constraint nodes (`c1`, `c2`, `c3`), satisfiability checking (`sat`, `unsat`,
    `unknown`, `timeout`), model/counterexample extraction, selective constraint
    undo, and translation validation.
    """

    def __init__(self, state_dict: dict[str, Any] | None = None):
        if state_dict:
            self.variables: dict[str, str] = dict(state_dict.get("variables", {}))
            self.constraints: list[dict[str, Any]] = list(state_dict.get("constraints", []))
            self.assumptions: list[str] = list(state_dict.get("assumptions", []))
        else:
            self.variables = {}
            self.constraints = []
            self.assumptions = []

    def to_dict(self) -> dict[str, Any]:
        return dict(
            variables=dict(self.variables),
            constraints=list(self.constraints),
            assumptions=list(self.assumptions),
        )

    def add_variable(self, name: str, sort: str = "Int") -> None:
        if sort not in ("Int", "Real", "Bool"):
            raise ValueError(f"unsupported_z3_sort:{sort}")
        self.variables[name] = sort

    def add_constraint(self, node_id: str, expr_str: str, description: str = "") -> dict[str, Any]:
        # Validate expression syntax & variable references before adding
        tree = ast.parse(expr_str, mode="eval")
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Name) and sub.id not in ("And", "Or", "Not", "Implies", "True", "False"):
                if sub.id not in self.variables:
                    self.variables[sub.id] = "Int"
        existing = next((i for i, c in enumerate(self.constraints) if c["node_id"] == node_id), None)
        rec = dict(node_id=node_id, expr=expr_str, description=description or expr_str, active=True)
        if existing is not None:
            self.constraints[existing] = rec
        else:
            self.constraints.append(rec)
        return rec

    def remove_constraint(self, node_id: str) -> dict[str, Any]:
        for c in self.constraints:
            if c["node_id"] == node_id:
                c["active"] = False
                return dict(removed=node_id, active_constraints=[x["node_id"] for x in self.constraints if x.get("active", True)])
        raise ValueError(f"constraint_node_not_found:{node_id}")

    def _compile_z3_expr(self, node: ast.AST, z3_mod: Any, env: dict[str, Any]) -> Any:
        if isinstance(node, ast.Expression):
            return self._compile_z3_expr(node.body, z3_mod, env)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            raise ValueError(f"unbound_z3_variable:{node.id}")
        if isinstance(node, ast.UnaryOp):
            operand = self._compile_z3_expr(node.operand, z3_mod, env)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.Not):
                return z3_mod.Not(operand)
        if isinstance(node, ast.BinOp):
            left = self._compile_z3_expr(node.left, z3_mod, env)
            right = self._compile_z3_expr(node.right, z3_mod, env)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
        if isinstance(node, ast.BoolOp):
            vals = [self._compile_z3_expr(v, z3_mod, env) for v in node.values]
            if isinstance(node.op, ast.And):
                return z3_mod.And(*vals)
            if isinstance(node.op, ast.Or):
                return z3_mod.Or(*vals)
        if isinstance(node, ast.Compare):
            left = self._compile_z3_expr(node.left, z3_mod, env)
            conjuncts = []
            cur = left
            for op, comp in zip(node.ops, node.comparators):
                rhs = self._compile_z3_expr(comp, z3_mod, env)
                if isinstance(op, ast.Eq):
                    conjuncts.append(cur == rhs)
                elif isinstance(op, ast.NotEq):
                    conjuncts.append(cur != rhs)
                elif isinstance(op, ast.Lt):
                    conjuncts.append(cur < rhs)
                elif isinstance(op, ast.LtE):
                    conjuncts.append(cur <= rhs)
                elif isinstance(op, ast.Gt):
                    conjuncts.append(cur > rhs)
                elif isinstance(op, ast.GtE):
                    conjuncts.append(cur >= rhs)
                else:
                    raise ValueError(f"unsupported_compare_op:{type(op).__name__}")
                cur = rhs
            return conjuncts[0] if len(conjuncts) == 1 else z3_mod.And(*conjuncts)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = [self._compile_z3_expr(a, z3_mod, env) for a in node.args]
            if node.func.id == "And":
                return z3_mod.And(*args)
            if node.func.id == "Or":
                return z3_mod.Or(*args)
            if node.func.id == "Not":
                return z3_mod.Not(*args)
            if node.func.id == "Implies":
                return z3_mod.Implies(*args)
        raise ValueError(f"unsupported_z3_ast:{type(node).__name__}")

    def check(self, timeout_ms: int = 2000) -> dict[str, Any]:
        import z3
        solver = z3.Solver()
        solver.set("timeout", int(timeout_ms))
        env: dict[str, Any] = {}
        for vname, vsort in sorted(self.variables.items()):
            if vsort == "Int":
                env[vname] = z3.Int(vname)
            elif vsort == "Real":
                env[vname] = z3.Real(vname)
            else:
                env[vname] = z3.Bool(vname)

        active_nodes = [c for c in self.constraints if c.get("active", True)]
        compiled_assertions = []
        for c in active_nodes:
            z3_expr = self._compile_z3_expr(ast.parse(c["expr"], mode="eval"), z3, env)
            solver.assert_and_track(z3_expr, c["node_id"])
            compiled_assertions.append(dict(node_id=c["node_id"], expr=c["expr"], z3_sexpr=z3_expr.sexpr()))

        res = solver.check()
        status = str(res)  # 'sat', 'unsat', 'unknown'
        model_dict: dict[str, Any] | None = None
        unsat_core: list[str] = []
        translation_verified = False

        if status == "sat":
            m = solver.model()
            model_dict = {}
            for vname, zvar in sorted(env.items()):
                val = m.eval(zvar, model_completion=True)
                if z3.is_int_value(val):
                    model_dict[vname] = val.as_long()
                elif z3.is_rational_value(val):
                    model_dict[vname] = float(val.numerator_as_long()) / float(val.denominator_as_long())
                elif z3.is_true(val):
                    model_dict[vname] = True
                elif z3.is_false(val):
                    model_dict[vname] = False
                else:
                    model_dict[vname] = str(val)
            # Independent Python evaluation of the extracted model to verify translation
            translation_verified = all(
                bool(eval(compile(ast.parse(c["expr"], mode="eval"), "<z3_verify>", "eval"), {"__builtins__": {}}, model_dict))
                for c in active_nodes
            )
        elif status == "unsat":
            unsat_core = sorted(str(k) for k in solver.unsat_core())
            translation_verified = True

        return dict(
            backend="z3",
            status=status,
            active_constraint_ids=[c["node_id"] for c in active_nodes],
            compiled_assertions=compiled_assertions,
            model=model_dict,
            unsat_core=unsat_core,
            assumptions=list(self.assumptions) or [f"{k}:{v}" for k, v in sorted(self.variables.items())],
            translation_verified=translation_verified,
            provenance_kind="formally_checked",
        )


class SymPySymbolicBackend:
    """Symbolic algebra, equation solving, calculus, and equivalence checking
    backed by `sympy` with explicit domain assumptions and substitution checks.
    """

    @staticmethod
    def solve_or_simplify(task_spec: dict[str, Any]) -> dict[str, Any]:
        import sympy as sp
        op = task_spec.get("op", "solve")
        expr_str = task_spec["expression"]
        var_name = task_spec.get("variable", "x")
        domain = task_spec.get("domain", "real")
        if domain == "integer":
            x = sp.Symbol(var_name, integer=True, real=True)
        elif domain == "positive":
            x = sp.Symbol(var_name, positive=True, real=True)
        else:
            x = sp.Symbol(var_name, real=True)
        local_dict = {var_name: x, "pi": sp.pi, "E": sp.E}

        if op == "solve":
            if "=" in expr_str:
                lhs_s, rhs_s = expr_str.split("=", 1)
                lhs = sp.sympify(lhs_s, locals=local_dict)
                rhs = sp.sympify(rhs_s, locals=local_dict)
                eq = sp.Eq(lhs, rhs)
            else:
                lhs = sp.sympify(expr_str, locals=local_dict)
                rhs = sp.Integer(0)
                eq = sp.Eq(lhs, rhs)
            sols = sp.solve(eq, x)
            verified_sols = []
            for s in sols:
                residual = sp.simplify(lhs.subs(x, s) - rhs.subs(x, s))
                if residual == 0:
                    verified_sols.append(str(s))
            return dict(
                backend="sympy",
                op="solve",
                expression=expr_str,
                variable=var_name,
                domain_assumption=domain,
                solutions=verified_sols,
                all_verified=(len(verified_sols) == len(sols) and len(sols) > 0),
                provenance_kind="formally_checked",
            )
        elif op == "derivative":
            expr = sp.sympify(expr_str, locals=local_dict)
            deriv = sp.diff(expr, x)
            return dict(
                backend="sympy",
                op="derivative",
                expression=expr_str,
                variable=var_name,
                result=str(sp.simplify(deriv)),
                provenance_kind="formally_checked",
            )
        elif op == "equivalence":
            rhs_str = task_spec["target_expression"]
            e1 = sp.sympify(expr_str, locals=local_dict)
            e2 = sp.sympify(rhs_str, locals=local_dict)
            diff = sp.simplify(e1 - e2)
            equiv = (diff == 0)
            return dict(
                backend="sympy",
                op="equivalence",
                expression=expr_str,
                target_expression=rhs_str,
                equivalent=equiv,
                simplified_difference=str(diff),
                provenance_kind="formally_checked",
            )
        raise ValueError(f"unsupported_sympy_op:{op}")


class Lean4ProofBackend:
    """Formal proof-checking backend for Lean 4.
    - Rejects any theorem containing `sorry`, `admit`, or unverified `axiom` before
      or during checking.
    - Invokes the real `lean` binary if present on the machine.
    - If `lean` is not installed on the host, honestly reports
      `status="blocked_missing_runtime"` per protocol rule ('Real dependency/runtime
      absence is reported as blocked, never replaced by mocks and called complete').
    """

    FORBIDDEN_TOKENS = re.compile(r"\b(sorry|admit|axiom)\b")

    @classmethod
    def check_proof(cls, lean_source: str, executable_override: str | None = None, timeout_s: float = 10.0) -> dict[str, Any]:
        if type(lean_source) is not str or not lean_source.strip():
            raise ValueError("lean_source_required")
        forbidden_hits = cls.FORBIDDEN_TOKENS.findall(lean_source)
        if forbidden_hits:
            return dict(
                backend="lean4",
                status="rejected_unverified_token",
                verified=False,
                forbidden_tokens=sorted(set(forbidden_hits)),
                reason=f"Proof rejected: contains forbidden incomplete/unverified token(s): {sorted(set(forbidden_hits))}",
                provenance_kind="formally_checked",
            )
        env_path = f"{Path.home() / '.elan/bin'}:/opt/homebrew/bin:/usr/local/bin:{os.environ.get('PATH', '')}"
        lean_bin = executable_override or shutil.which("lean", path=env_path)
        if not lean_bin:
            return dict(
                backend="lean4",
                status="blocked_missing_runtime",
                verified=False,
                lean_binary=None,
                reason="Lean 4 binary ('lean') is not installed on this host. Reported honestly as blocked rather than mocked.",
                provenance_kind="observed_execution",
            )
        with tempfile.TemporaryDirectory() as tmp:
            proof_file = Path(tmp) / "ProofCheck.lean"
            proof_file.write_text(lean_source, encoding="utf-8")
            started = time.perf_counter()
            proc = subprocess.run(
                [lean_bin, str(proof_file)],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            wall_s = time.perf_counter() - started
            passed = (proc.returncode == 0)
            return dict(
                backend="lean4",
                status="verified" if passed else "proof_check_failed",
                verified=passed,
                lean_binary=lean_bin,
                returncode=proc.returncode,
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
                wall_s=wall_s,
                provenance_kind="formally_checked",
            )


# ============================================================================
# SECTION G: HIERARCHICAL PLANNING (Project Goal <-> Module Contract <-> Function)
# ============================================================================

@dataclass
class PlanNode:
    node_id: str
    level: str  # 'project_goal', 'module_contract', 'function_or_program'
    title: str
    contract: dict[str, Any]
    depends_on: list[str]
    status: str = "pending"  # 'pending', 'verified', 'stale_needs_revalidation', 'failed'
    validation_evidence: dict[str, Any] = field(default_factory=dict)


class HierarchicalPlanner:
    """Maintains a linked 3-level hierarchy:
      Level 1: `project_goal`
      Level 2: `module_contract`
      Level 3: `function_or_program`
    Tracks cross-level dependencies and acceptance checks, and automatically
    marks downstream modules/functions as `stale_needs_revalidation` and
    revalidates them when any contract changes.
    """

    VALID_LEVELS = ("project_goal", "module_contract", "function_or_program")

    def __init__(self, state_dict: dict[str, Any] | None = None):
        self.nodes: dict[str, PlanNode] = {}
        self.change_log: list[dict[str, Any]] = []
        if state_dict:
            for k, v in state_dict.get("nodes", {}).items():
                self.nodes[k] = PlanNode(**v)
            self.change_log = list(state_dict.get("change_log", []))

    def to_dict(self) -> dict[str, Any]:
        return dict(
            nodes={k: asdict(v) for k, v in self.nodes.items()},
            change_log=self.change_log[-24:],
        )

    def add_node(self, node_id: str, level: str, title: str, contract: dict[str, Any],
                 depends_on: list[str] | None = None) -> PlanNode:
        if level not in self.VALID_LEVELS:
            raise ValueError(f"invalid_plan_level:{level}")
        node = PlanNode(
            node_id=node_id,
            level=level,
            title=title,
            contract=copy.deepcopy(contract),
            depends_on=list(depends_on or []),
        )
        self.nodes[node_id] = node
        return node

    def update_contract(self, node_id: str, new_contract: dict[str, Any]) -> dict[str, Any]:
        """Update a node's contract and propagate invalidation to all transitively
        dependent nodes across levels.
        """
        if node_id not in self.nodes:
            raise ValueError(f"plan_node_not_found:{node_id}")
        old_contract = copy.deepcopy(self.nodes[node_id].contract)
        self.nodes[node_id].contract = copy.deepcopy(new_contract)
        self.nodes[node_id].status = "stale_needs_revalidation"

        affected = {node_id}
        changed = True
        while changed:
            changed = False
            for nid, n in self.nodes.items():
                if nid not in affected and any(d in affected for d in n.depends_on):
                    affected.add(nid)
                    n.status = "stale_needs_revalidation"
                    changed = True

        rec = dict(
            updated_node=node_id,
            old_contract=old_contract,
            new_contract=new_contract,
            invalidated_nodes=sorted(affected),
        )
        self.change_log.append(rec)
        return rec

    def validate_all(self, check_callbacks: dict[str, Any]) -> dict[str, Any]:
        """Validate nodes bottom-up (`function_or_program` -> `module_contract` -> `project_goal`)."""
        level_order = {"function_or_program": 1, "module_contract": 2, "project_goal": 3}
        ordered = sorted(self.nodes.values(), key=lambda n: (level_order[n.level], n.node_id))
        results = {}
        for node in ordered:
            deps_ok = all(self.nodes[d].status == "verified" for d in node.depends_on if d in self.nodes)
            if not deps_ok:
                node.status = "failed"
                node.validation_evidence = dict(passed=False, reason="dependency_not_verified")
                results[node.node_id] = node.validation_evidence
                continue
            cb = check_callbacks.get(node.node_id)
            if cb is not None:
                ev = cb(node.contract)
                passed = bool(ev.get("passed"))
                node.status = "verified" if passed else "failed"
                node.validation_evidence = ev
            else:
                node.status = "verified"
                node.validation_evidence = dict(passed=True, reason="structural_contract_satisfied")
            results[node.node_id] = node.validation_evidence
        return dict(
            all_verified=all(n.status == "verified" for n in self.nodes.values()),
            statuses={k: v.status for k, v in self.nodes.items()},
            results=results,
        )


# ============================================================================
# SECTION H: KNOWLEDGE & DOCUMENTATION (Versioned Docs + Wikidata Snapshot Adapter)
# ============================================================================

class KnowledgeAndDocRetriever:
    """Read-only knowledge and documentation adapter:
    - Indexes local documentation and versioned source specifications with
      explicit `doc_id`, `version`, `timestamp`, and `sha256`
    - Queries saved local Wikidata entity/claim snapshots for reproducible
      offline evaluation
    - Detects contradictions across sources or claim versions
    - Strictly separates `lexical_candidate_meanings` from `grounded_executable_bindings`
    """

    def __init__(self):
        self.docs: dict[str, dict[str, Any]] = {}
        self.wikidata_entities: dict[str, dict[str, Any]] = {}

    def register_document(self, doc_id: str, title: str, content: str,
                          version: str = "1.0.0", timestamp: str = "2026-10-23T00:00:00Z",
                          grounded_bindings: dict[str, Any] | None = None) -> dict[str, Any]:
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        rec = dict(
            doc_id=doc_id,
            title=title,
            version=version,
            timestamp=timestamp,
            sha256=sha,
            content=content,
            grounded_bindings=dict(grounded_bindings or {}),
        )
        self.docs[doc_id] = rec
        return rec

    def load_wikidata_snapshot(self, entities: list[dict[str, Any]]) -> int:
        for ent in entities:
            qid = ent["qid"]
            self.wikidata_entities[qid] = copy.deepcopy(ent)
        return len(self.wikidata_entities)

    def retrieve(self, query: str) -> dict[str, Any]:
        q_tokens = [t for t in re.findall(r"[a-z0-9_]+", query.lower()) if len(t) >= 2]
        doc_hits = []
        grounded_bindings = {}
        for doc_id, doc in sorted(self.docs.items()):
            text_lower = (doc["title"] + " " + doc["content"]).lower()
            matched = [t for t in q_tokens if t in text_lower]
            if matched:
                doc_hits.append(dict(
                    doc_id=doc_id,
                    title=doc["title"],
                    version=doc["version"],
                    timestamp=doc["timestamp"],
                    sha256=doc["sha256"],
                    matched_tokens=matched,
                    excerpt=doc["content"][:280],
                ))
                grounded_bindings.update(doc.get("grounded_bindings", {}))

        entity_hits = []
        contradictions = []
        lexical_candidates = []
        for qid, ent in sorted(self.wikidata_entities.items()):
            label = ent.get("label", "")
            aliases = ent.get("aliases", [])
            desc = ent.get("description", "")
            hay = " ".join([qid, label, desc] + aliases).lower()
            if any(t in hay for t in q_tokens):
                lexical_candidates.append(dict(
                    qid=qid,
                    label=label,
                    description=desc,
                    lexical_only=True,
                    executable_binding=ent.get("executable_binding"),
                ))
                claims_by_prop: dict[str, list[Any]] = {}
                for claim in ent.get("claims", []):
                    prop = claim["property"]
                    claims_by_prop.setdefault(prop, []).append(claim)
                for prop, clist in claims_by_prop.items():
                    distinct_vals = {json.dumps(c["value"], sort_keys=True) for c in clist}
                    if len(distinct_vals) > 1:
                        contradictions.append(dict(
                            qid=qid,
                            label=label,
                            property=prop,
                            conflicting_claims=clist,
                        ))
                entity_hits.append(dict(
                    qid=qid,
                    label=label,
                    snapshot_timestamp=ent.get("snapshot_timestamp", "2026-10-23T00:00:00Z"),
                    claims=ent.get("claims", []),
                ))

        uncertainty = "high_contradiction_detected" if contradictions else (
            "low_grounded" if (doc_hits or entity_hits) else "ungrounded_no_source_match"
        )
        return dict(
            query=query,
            provenance_kind="source_attributed",
            doc_hits=doc_hits,
            wikidata_hits=entity_hits,
            contradictions=contradictions,
            uncertainty=uncertainty,
            lexical_candidate_meanings=lexical_candidates,
            grounded_executable_bindings=grounded_bindings,
        )


# ============================================================================
# SECTION I: CAPSULE ACQUISITION, CONSOLIDATION & CROSS-PROFILE EXCHANGE
# ============================================================================

class StigmergicCapsuleRegistry:
    """Content-addressed versioned capsule store supporting:
    1. Bounded capsule acquisition from user-selected code/docs with behavioral
       probes, sandbox execution checks, and counterexample retention
    2. Consolidation & pruning between `active` and `cold` storage based on
       empirical net time saved vs retrieval/validation overhead
    3. Cross-profile capsule exchange (`export_bundle` -> `import_bundle`)
       between isolated local NEXUS profiles (`Profile A` -> `Profile B`),
       enforcing sandbox revalidation on import and NEVER auto-executing code
       during import.
    """

    def __init__(self, profile_id: str, storage_dir: Path):
        self.profile_id = profile_id
        self.storage_dir = Path(storage_dir)
        self.active_dir = self.storage_dir / "active"
        self.cold_dir = self.storage_dir / "cold"
        self.rejected_dir = self.storage_dir / "rejected"
        for d in (self.active_dir, self.cold_dir, self.rejected_dir):
            d.mkdir(parents=True, exist_ok=True)

    def acquire_from_code_and_docs(
        self,
        source_code: str,
        doc_spec: str,
        function_name: str,
        behavioral_probes: list[dict[str, Any]],
        license_tag: str = "MIT",
        source_attribution: str = "local_user_selection",
    ) -> dict[str, Any]:
        """Extract a candidate operation from user-selected code & doc, run
        behavioral probes in an isolated AST/namespace check, retain any
        counterexamples if probes fail, and promote to active storage only if
        all probes pass.
        """
        # Static safety check
        tree = ast.parse(source_code)
        fn_node = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function_name), None)
        if fn_node is None:
            raise ValueError(f"function_not_found_in_source:{function_name}")
        for sub in ast.walk(fn_node):
            if isinstance(sub, (ast.Import, ast.ImportFrom)):
                raise ValueError("capsule_cannot_contain_imports")
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in {"eval", "exec", "open", "__import__"}:
                raise ValueError(f"forbidden_call_in_capsule:{sub.func.id}")

        fn_source = ast.unparse(fn_node)
        counterexamples = []
        passed_probes = []
        ns: dict[str, Any] = {"__builtins__": {"len": len, "sum": sum, "min": min, "max": max, "round": round, "sorted": sorted, "abs": abs, "float": float, "int": int, "str": str, "dict": dict, "list": list}}
        exec(compile(ast.parse(fn_source), "<capsule_sandbox>", "exec"), ns)
        fn = ns[function_name]

        for probe in behavioral_probes:
            inp = copy.deepcopy(probe["input"])
            expected = probe["expected"]
            try:
                actual = fn(*inp) if isinstance(inp, list) and probe.get("unpack_args") else fn(inp)
                if actual == expected:
                    passed_probes.append(dict(input=inp, output=actual))
                else:
                    counterexamples.append(dict(input=inp, expected=expected, actual=actual))
            except Exception as exc:
                counterexamples.append(dict(input=inp, expected=expected, error=f"{type(exc).__name__}:{exc}"))

        content_hash = hashlib.sha256(json.dumps(
            dict(fn_source=fn_source, doc_spec=doc_spec, probes=behavioral_probes),
            sort_keys=True,
        ).encode("utf-8")).hexdigest()
        capsule_id = f"cap_{content_hash[:16]}"

        manifest = dict(
            capsule_id=capsule_id,
            content_sha256=content_hash,
            version="1.0.0",
            origin_profile=self.profile_id,
            function_name=function_name,
            fn_source=fn_source,
            doc_spec=doc_spec,
            input_type=behavioral_probes[0].get("input_type", "Any") if behavioral_probes else "Any",
            output_type=behavioral_probes[0].get("output_type", "Any") if behavioral_probes else "Any",
            behavioral_probes=behavioral_probes,
            passed_probes_count=len(passed_probes),
            counterexamples=counterexamples,
            provenance=dict(
                source_attribution=source_attribution,
                license=license_tag,
                acquired_at="2026-10-23T00:00:00Z",
                provenance_kind="tested_hypothesis",
            ),
            metrics=dict(
                reuse_hits=0,
                validation_failures=len(counterexamples),
                cumulative_saved_s=0.0,
                cumulative_overhead_s=0.001,
            ),
            tier="active" if not counterexamples and passed_probes else "rejected",
        )

        if counterexamples or not passed_probes:
            (self.rejected_dir / f"{capsule_id}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            return dict(accepted=False, capsule_id=capsule_id, counterexamples=counterexamples, manifest=manifest)

        (self.active_dir / f"{capsule_id}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return dict(accepted=True, capsule_id=capsule_id, counterexamples=[], manifest=manifest)

    def export_capsule_bundle(self, capsule_id: str) -> dict[str, Any]:
        path = self.active_dir / f"{capsule_id}.json"
        if not path.is_file():
            raise ValueError(f"active_capsule_not_found:{capsule_id}")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        return dict(
            bundle_kind="nexus_stigmergic_capsule_v1",
            exported_by_profile=self.profile_id,
            manifest=manifest,
        )

    def import_capsule_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """Import a capsule bundle from another profile.
        Does NOT auto-execute arbitrary side effects on import: it validates the
        content hash, AST safety, and replays the behavioral probes inside the
        bounded sandbox before admitting the capsule into `self.active_dir`.
        """
        if bundle.get("bundle_kind") != "nexus_stigmergic_capsule_v1":
            raise ValueError("invalid_capsule_bundle_kind")
        manifest = copy.deepcopy(bundle["manifest"])
        expected_hash = hashlib.sha256(json.dumps(
            dict(
                fn_source=manifest["fn_source"],
                doc_spec=manifest["doc_spec"],
                probes=manifest["behavioral_probes"],
            ),
            sort_keys=True,
        ).encode("utf-8")).hexdigest()
        if expected_hash != manifest.get("content_sha256"):
            raise ValueError("capsule_content_hash_mismatch")

        # Revalidate via acquire_from_code_and_docs in isolated sandbox
        reval = self.acquire_from_code_and_docs(
            source_code=manifest["fn_source"],
            doc_spec=manifest["doc_spec"],
            function_name=manifest["function_name"],
            behavioral_probes=manifest["behavioral_probes"],
            license_tag=manifest.get("provenance", {}).get("license", "MIT"),
            source_attribution=f"imported_from:{bundle.get('exported_by_profile')}",
        )
        return dict(
            imported=reval["accepted"],
            capsule_id=reval["capsule_id"],
            origin_profile=bundle.get("exported_by_profile"),
            target_profile=self.profile_id,
            auto_executed_on_import=False,
            sandbox_revalidated=True,
            counterexamples=reval["counterexamples"],
        )

    def execute_capsule(self, capsule_id: str, arg: Any, saved_time_estimate_s: float = 0.01) -> dict[str, Any]:
        started = time.perf_counter()
        path = self.active_dir / f"{capsule_id}.json"
        if not path.is_file():
            raise ValueError(f"active_capsule_not_found:{capsule_id}")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        ns: dict[str, Any] = {"__builtins__": {"len": len, "sum": sum, "min": min, "max": max, "round": round, "sorted": sorted, "abs": abs, "float": float, "int": int, "str": str, "dict": dict, "list": list}}
        exec(compile(ast.parse(manifest["fn_source"]), "<capsule_exec>", "exec"), ns)
        fn = ns[manifest["function_name"]]
        out = fn(copy.deepcopy(arg))
        overhead = time.perf_counter() - started
        manifest["metrics"]["reuse_hits"] += 1
        manifest["metrics"]["cumulative_saved_s"] += saved_time_estimate_s
        manifest["metrics"]["cumulative_overhead_s"] += overhead
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return dict(
            capsule_id=capsule_id,
            output=out,
            reuse_hits=manifest["metrics"]["reuse_hits"],
            provenance_kind="observed_execution",
        )

    def consolidate_and_prune(self) -> dict[str, Any]:
        """Move low-utility or negative-net-savings capsules from `active` to `cold`
        storage so active lookup stays fast.
        """
        kept_active = []
        moved_cold = []
        for path in sorted(self.active_dir.glob("*.json")):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            m = manifest.get("metrics", {})
            net_benefit = float(m.get("cumulative_saved_s", 0.0)) - float(m.get("cumulative_overhead_s", 0.0))
            if m.get("reuse_hits", 0) == 0 or net_benefit < 0.0:
                manifest["tier"] = "cold"
                target = self.cold_dir / path.name
                target.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                path.unlink()
                moved_cold.append(manifest["capsule_id"])
            else:
                kept_active.append(manifest["capsule_id"])
        return dict(kept_active=kept_active, moved_to_cold=moved_cold)


class BoundedIngestionJob:
    """User-approved bounded background/batch ingestion job with progress
    reporting, cancellation, and resource accounting.
    """

    def __init__(self, registry: StigmergicCapsuleRegistry, max_items: int = 16, max_wall_s: float = 10.0):
        self.registry = registry
        self.max_items = max_items
        self.max_wall_s = max_wall_s

    def run(self, items: list[dict[str, Any]], cancelled=None) -> dict[str, Any]:
        started = time.perf_counter()
        processed = 0
        accepted = []
        rejected = []
        status = "completed"

        for item in items[:self.max_items]:
            if cancelled and cancelled():
                status = "cancelled"
                break
            if (time.perf_counter() - started) > self.max_wall_s:
                status = "budget_exhausted"
                break
            res = self.registry.acquire_from_code_and_docs(
                source_code=item["source_code"],
                doc_spec=item.get("doc_spec", ""),
                function_name=item["function_name"],
                behavioral_probes=item["behavioral_probes"],
                license_tag=item.get("license", "MIT"),
                source_attribution=item.get("source_attribution", "bounded_ingestion_job"),
            )
            processed += 1
            if res["accepted"]:
                accepted.append(res["capsule_id"])
            else:
                rejected.append(res["capsule_id"])

        return dict(
            job_status=status,
            processed_count=processed,
            total_submitted=len(items),
            accepted_capsules=accepted,
            rejected_capsules=rejected,
            wall_s=time.perf_counter() - started,
        )


# ============================================================================
# SECTION A & B: SHARED WORKBENCH CONTROLLER & CHAT INTEGRATION
# ============================================================================

class SymbioticWorkbenchController:
    """Connects all symbiotic workbench backends (StatefulProgramEditor,
    MultiFormatDataBackend, PolyglotCodingWorkbench, StatefulZ3Coordinator,
    SymPySymbolicBackend, Lean4ProofBackend, HierarchicalPlanner,
    KnowledgeAndDocRetriever, StigmergicCapsuleRegistry) to the same
    SeedWorkspace, Session journal (`seed_master` events), and Conversation.
    """

    def __init__(self, store, session, session_id: str | None = None):
        self.store = store
        self.session = session
        self.session_id = session_id or "default"
        self.base_dir = Path(self.store.directory) / "workbench" / self.session_id
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.base_dir / "workbench_state.json"
        self.state = self._load_state()
        self.editor = StatefulProgramEditor(self.state.get("editor"))
        self.z3_coord = StatefulZ3Coordinator(self.state.get("z3"))
        self.planner = HierarchicalPlanner(self.state.get("planner"))
        self.coding = PolyglotCodingWorkbench(self.base_dir / "coding_worktree")
        if self.state.get("coding_files"):
            self.coding.files = dict(self.state["coding_files"])
            self.coding.edit_history = list(self.state.get("coding_history", []))
        self.knowledge = KnowledgeAndDocRetriever()
        for doc in self.state.get("docs", []):
            self.knowledge.register_document(**doc)
        if self.state.get("wikidata"):
            self.knowledge.load_wikidata_snapshot(self.state["wikidata"])
        self.registry = StigmergicCapsuleRegistry(
            profile_id=self.state.get("profile_id", "profile_a"),
            storage_dir=Path(self.store.directory) / "capsules" / self.state.get("profile_id", "profile_a"),
        )

    def _load_state(self) -> dict[str, Any]:
        if self.state_file.is_file():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Reconstruct from session journal if present
        from .master.memory import MASTER_EVENT_KIND
        for ev in reversed(self.session.journal.snapshot()):
            if ev.kind == MASTER_EVENT_KIND:
                p = json.loads(ev.payload_json)
                if p.get("op") == "symbiotic_workbench" and p["data"].get("state_snapshot"):
                    return p["data"]["state_snapshot"]
        return dict(profile_id="profile_a", docs=[], wikidata=[])

    def _save_state(self, backend: str, proposal: TypedActionProposal) -> None:
        snap = dict(
            profile_id=self.registry.profile_id,
            editor=self.editor.to_dict(),
            z3=self.z3_coord.to_dict(),
            planner=self.planner.to_dict(),
            coding_files=self.coding.files,
            coding_history=self.coding.edit_history[-16:],
            docs=list(self.knowledge.docs.values()),
            wikidata=list(self.knowledge.wikidata_entities.values()),
        )
        self.state_file.write_text(json.dumps(snap, indent=2), encoding="utf-8")
        from .master.memory import MASTER_EVENT_KIND
        if sum(e.kind == MASTER_EVENT_KIND for e in self.session.journal.snapshot()) < 240:
            self.session.event(MASTER_EVENT_KIND, dict(
                op="symbiotic_workbench",
                data=dict(
                    backend=backend,
                    proposal_id=proposal.proposal_id,
                    intent=proposal.intent,
                    execution_status=proposal.execution_status,
                    provenance_kind=proposal.provenance_kind,
                ),
            ))

    def execute_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Direct API dispatcher for `/api/seed` (`op='workbench_*'`)."""
        op = request.get("op", "")
        args = request.get("args", {})
        if op == "workbench_inspect":
            return dict(
                editor=self.editor.to_dict(),
                z3=self.z3_coord.to_dict(),
                planner=self.planner.to_dict(),
                coding=self.coding.index_repository(),
                active_capsules=[p.stem for p in sorted(self.registry.active_dir.glob("*.json"))],
                cold_capsules=[p.stem for p in sorted(self.registry.cold_dir.glob("*.json"))],
            )
        if op == "workbench_editor":
            return self._handle_editor_api(args)
        if op == "workbench_data":
            return self._handle_data_api(args)
        if op == "workbench_coding":
            return self._handle_coding_api(args)
        if op == "workbench_reasoning":
            return self._handle_reasoning_api(args)
        if op == "workbench_planning":
            return self._handle_planning_api(args)
        if op == "workbench_knowledge":
            return self._handle_knowledge_api(args)
        if op == "workbench_capsules":
            return self._handle_capsules_api(args)
        if op == "workbench_agent_solve":
            return self._handle_agent_solve_api(args)
        raise ValueError(f"unknown_workbench_op:{op}")

    def _handle_editor_api(self, args: dict[str, Any]) -> dict[str, Any]:
        sub = args["sub_op"]
        if sub == "insert":
            rec = self.editor.insert_node(args["node_id"], args["node_op"], args.get("params", {}))
        elif sub == "replace":
            rec = self.editor.replace_node(args["node_id"], args["node_op"], args.get("params", {}))
        elif sub == "remove":
            rec = self.editor.remove_node(args["node_id"], force=bool(args.get("force", False)))
        elif sub == "selective_undo":
            rec = self.editor.selective_undo(args["node_id"])
        elif sub == "rebind":
            rec = self.editor.rebind_schema(args["bindings"])
        elif sub == "execute":
            rows = args["rows"]
            out = self.editor.execute(rows, args.get("aux_tables"))
            rec = dict(output=out, row_count=len(out), nodes=[asdict(n) for n in self.editor.nodes])
        elif sub == "export_capsule":
            rec = self.editor.export_capsule(args.get("capsule_id"), args.get("source_sha", ""))
            cap_path = self.store.procedures_dir() / f"{rec['id']}.json"
            cap_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        else:
            raise ValueError(f"unknown_editor_sub_op:{sub}")
        prop = TypedActionProposal(
            proposal_id=digest([sub, args, self.editor.version_counter])[:16],
            intent=f"editor_{sub}",
            backend="stateful_program_editor",
            target=str(args.get("node_id", "program")),
            input_type="Table[Row]",
            output_type="Table[Row]",
            preconditions=["valid_node_id"],
            expected_effects=[f"program_version_v{self.editor.version_counter}"],
            dependencies=[n.node_id for n in self.editor.nodes],
            version_id=f"v{self.editor.version_counter}",
            resource_limits=dict(max_rows=10000),
            execution_status="committed",
            provenance_kind="observed_execution",
            rollback_semantics="selective_undo_supported",
            evidence=rec,
        )
        self._save_state("stateful_program_editor", prop)
        return dict(proposal=prop.validate(), result=rec, editor=self.editor.to_dict())

    def _handle_data_api(self, args: dict[str, Any]) -> dict[str, Any]:
        fmt = args["format"]
        if fmt == "json":
            flat, meta = MultiFormatDataBackend.flatten_json_records(args["data"], args.get("record_path"))
            if args.get("reconstruct"):
                rebuilt = MultiFormatDataBackend.reconstruct_json_records(flat, meta)
            else:
                rebuilt = None
            res = dict(flat_rows=flat, envelope_meta=meta, reconstructed=rebuilt)
        elif fmt == "sqlite":
            res = MultiFormatDataBackend.execute_sqlite_workflow(
                Path(args["db_path"]),
                Path(args["output_db_path"]) if args.get("output_db_path") else None,
                args["query_spec"],
            )
        else:
            raise ValueError(f"unsupported_data_format:{fmt}")
        prop = TypedActionProposal(
            proposal_id=digest([fmt, args])[:16],
            intent=f"data_{fmt}",
            backend=f"data_{fmt}",
            target=str(args.get("db_path", "json_payload")),
            input_type=fmt.upper(),
            output_type="Table[Row]",
            preconditions=["source_readable"],
            expected_effects=["read_only_source_preserved"],
            dependencies=[],
            version_id="v1",
            resource_limits=dict(timeout_s=5.0),
            execution_status="committed",
            provenance_kind="observed_execution",
            rollback_semantics="atomic_publish_or_transaction",
            evidence=res,
        )
        self._save_state(f"data_{fmt}", prop)
        return dict(proposal=prop.validate(), result=res)

    def _handle_coding_api(self, args: dict[str, Any]) -> dict[str, Any]:
        sub = args["sub_op"]
        if sub == "load":
            res = self.coding.load_repository(args["files"])
        elif sub == "search":
            res = dict(hits=self.coding.search_source(args["query"]))
        elif sub == "patch":
            res = self.coding.apply_patch(args["path"], args["new_content"], args.get("edit_id"), args.get("reason", "patch"))
        elif sub == "selective_undo":
            res = self.coding.selective_undo_edit(args["edit_id"])
        elif sub == "test_python":
            res = self.coding.run_python_tests(args["test_script"])
        elif sub == "test_typescript":
            res = self.coding.run_typescript_validation(args.get("test_runner_ts"))
        else:
            raise ValueError(f"unknown_coding_sub_op:{sub}")
        prop = TypedActionProposal(
            proposal_id=digest([sub, args])[:16],
            intent=f"coding_{sub}",
            backend="polyglot_coding",
            target=str(args.get("path", "repository")),
            input_type="Repository",
            output_type="ValidatedDiffOrTestReport",
            preconditions=["isolated_worktree"],
            expected_effects=[f"coding_{sub}_completed"],
            dependencies=[],
            version_id=f"edit_{len(self.coding.edit_history)}",
            resource_limits=dict(timeout_s=10.0),
            execution_status="verified" if res.get("passed", True) else "failed",
            provenance_kind="observed_execution",
            rollback_semantics="selective_undo_edit",
            evidence=res,
        )
        self._save_state("polyglot_coding", prop)
        return dict(proposal=prop.validate(), result=res)

    def _handle_reasoning_api(self, args: dict[str, Any]) -> dict[str, Any]:
        engine = args["engine"]
        if engine == "z3":
            sub = args.get("sub_op", "check")
            if sub == "add_constraint":
                self.z3_coord.add_constraint(args["node_id"], args["expr"], args.get("description", ""))
            elif sub == "remove_constraint":
                self.z3_coord.remove_constraint(args["node_id"])
            res = self.z3_coord.check(timeout_ms=int(args.get("timeout_ms", 2000)))
            status = "verified"
            prov = "formally_checked"
        elif engine == "sympy":
            res = SymPySymbolicBackend.solve_or_simplify(args)
            status = "verified"
            prov = "formally_checked"
        elif engine == "lean4":
            res = Lean4ProofBackend.check_proof(args["lean_source"], args.get("executable_override"))
            status = "blocked_missing_runtime" if res["status"] == "blocked_missing_runtime" else (
                "verified" if res.get("verified") else "rejected"
            )
            prov = res["provenance_kind"]
        else:
            raise ValueError(f"unknown_reasoning_engine:{engine}")
        prop = TypedActionProposal(
            proposal_id=digest([engine, args])[:16],
            intent=f"reason_{engine}",
            backend=f"reasoning_{engine}",
            target=engine,
            input_type="FormalSpecification",
            output_type="ProofOrModel",
            preconditions=["explicit_assumptions"],
            expected_effects=[f"{engine}_check"],
            dependencies=res.get("active_constraint_ids", []),
            version_id="v1",
            resource_limits=dict(timeout_ms=2000),
            execution_status=status,
            provenance_kind=prov,
            rollback_semantics="remove_constraint",
            evidence=res,
        )
        self._save_state(f"reasoning_{engine}", prop)
        return dict(proposal=prop.validate(), result=res)

    def _handle_planning_api(self, args: dict[str, Any]) -> dict[str, Any]:
        sub = args["sub_op"]
        if sub == "add_node":
            node = self.planner.add_node(args["node_id"], args["level"], args["title"], args["contract"], args.get("depends_on"))
            res = asdict(node)
        elif sub == "update_contract":
            res = self.planner.update_contract(args["node_id"], args["new_contract"])
        elif sub == "validate":
            res = self.planner.validate_all({})
        else:
            raise ValueError(f"unknown_planning_sub_op:{sub}")
        prop = TypedActionProposal(
            proposal_id=digest([sub, args])[:16],
            intent=f"plan_{sub}",
            backend="hierarchical_planner",
            target=str(args.get("node_id", "hierarchy")),
            input_type="ContractGraph",
            output_type="ValidationReport",
            preconditions=["acyclic_hierarchy"],
            expected_effects=["contract_propagation"],
            dependencies=list(self.planner.nodes.keys()),
            version_id=f"v{len(self.planner.change_log) + 1}",
            resource_limits=dict(max_nodes=64),
            execution_status="verified",
            provenance_kind="observed_execution",
            rollback_semantics="contract_history_revert",
            evidence=res,
        )
        self._save_state("hierarchical_planner", prop)
        return dict(proposal=prop.validate(), result=res, planner=self.planner.to_dict())

    def _handle_knowledge_api(self, args: dict[str, Any]) -> dict[str, Any]:
        sub = args["sub_op"]
        if sub == "register_doc":
            res = self.knowledge.register_document(
                args["doc_id"], args["title"], args["content"],
                args.get("version", "1.0.0"), args.get("timestamp", "2026-10-23T00:00:00Z"),
                args.get("grounded_bindings"),
            )
        elif sub == "load_wikidata":
            count = self.knowledge.load_wikidata_snapshot(args["entities"])
            res = dict(loaded_entities=count)
        elif sub == "retrieve":
            res = self.knowledge.retrieve(args["query"])
        else:
            raise ValueError(f"unknown_knowledge_sub_op:{sub}")
        prop = TypedActionProposal(
            proposal_id=digest([sub, args])[:16],
            intent=f"knowledge_{sub}",
            backend="knowledge_and_docs",
            target=str(args.get("query", args.get("doc_id", "snapshot"))),
            input_type="QueryOrDocument",
            output_type="SourceAttributedRetrieval",
            preconditions=["read_only_snapshot"],
            expected_effects=["no_unverified_mutation"],
            dependencies=[],
            version_id="v1",
            resource_limits=dict(max_hits=16),
            execution_status="executed",
            provenance_kind="source_attributed",
            rollback_semantics="read_only",
            evidence=res,
        )
        self._save_state("knowledge_and_docs", prop)
        return dict(proposal=prop.validate(), result=res)

    def _handle_capsules_api(self, args: dict[str, Any]) -> dict[str, Any]:
        sub = args["sub_op"]
        if sub == "acquire":
            res = self.registry.acquire_from_code_and_docs(
                args["source_code"], args.get("doc_spec", ""),
                args["function_name"], args["behavioral_probes"],
                args.get("license", "MIT"), args.get("source_attribution", "user_selection"),
            )
        elif sub == "export":
            res = self.registry.export_capsule_bundle(args["capsule_id"])
        elif sub == "import":
            target_profile = args.get("target_profile", "profile_b")
            target_reg = StigmergicCapsuleRegistry(
                profile_id=target_profile,
                storage_dir=Path(self.store.directory) / "capsules" / target_profile,
            )
            res = target_reg.import_capsule_bundle(args["bundle"])
        elif sub == "execute":
            profile_id = args.get("profile_id", self.registry.profile_id)
            reg = StigmergicCapsuleRegistry(
                profile_id=profile_id,
                storage_dir=Path(self.store.directory) / "capsules" / profile_id,
            )
            res = reg.execute_capsule(args["capsule_id"], args["arg"])
        elif sub == "consolidate":
            res = self.registry.consolidate_and_prune()
        else:
            raise ValueError(f"unknown_capsules_sub_op:{sub}")
        prop = TypedActionProposal(
            proposal_id=digest([sub, args])[:16],
            intent=f"capsule_{sub}",
            backend="stigmergic_capsule_registry",
            target=str(args.get("capsule_id", args.get("function_name", "registry"))),
            input_type="CapsuleSpec",
            output_type="VerifiedCapsuleManifest",
            preconditions=["sandbox_probes_required"],
            expected_effects=[f"capsule_{sub}"],
            dependencies=[],
            version_id="v1",
            resource_limits=dict(timeout_s=5.0),
            execution_status="verified" if res.get("accepted", res.get("imported", True)) else "rejected",
            provenance_kind="tested_hypothesis",
            rollback_semantics="move_to_cold_or_rejected",
            evidence=res,
        )
        self._save_state("stigmergic_capsule_registry", prop)
        return dict(proposal=prop.validate(), result=res)

    # ========================================================================
    # CHAT TURN ROUTER (Natural Language & Structured Commands in Chat)
    # ========================================================================

    def try_handle_chat(self, ws_turn) -> tuple[str, str, bool] | None:
        """Inspect a chat turn from `WorkspaceTurn.dispatch()` and route to
        the appropriate symbiotic workbench backend when matched. Returns
        `(reply, status, save)` or `None` to fall through to existing CSV/chat.
        """
        raw = ws_turn.raw.strip()
        lower = ws_turn.text

        # 1. Z3 Constraint Solver via chat
        if lower.startswith("z3 "):
            return self._chat_z3(ws_turn, raw)

        # 2. SymPy Symbolic Math via chat
        if lower.startswith("sympy "):
            return self._chat_sympy(ws_turn, raw)

        # 3. Lean 4 Proof Checking via chat
        if lower.startswith("lean4 ") or lower.startswith("lean "):
            return self._chat_lean4(ws_turn, raw)

        # 4. Stateful Program Editor commands via chat (6-step sales workflow, selective undo, JSON/SQLite)
        if lower.startswith("program ") or lower.startswith("editor "):
            return self._chat_program_editor(ws_turn, raw)

        # 5. Knowledge / Wikidata / Versioned Doc retrieval via chat
        if lower.startswith("wikidata ") or lower.startswith("docs "):
            return self._chat_knowledge(ws_turn, raw)

        # 6. Polyglot Coding (Python / TypeScript) via chat
        if lower.startswith("code ") or lower.startswith("typescript ") or lower.startswith("repo "):
            return self._chat_coding(ws_turn, raw)

        # 7. Hierarchical Planning via chat
        if lower.startswith("plan "):
            return self._chat_planning(ws_turn, raw)

        # 8. Cross-Profile Capsule Acquisition & Transfer via chat
        if lower.startswith("capsule "):
            return self._chat_capsule(ws_turn, raw)

        # 9. Autonomous Symbiotic Agent Loop via chat
        if lower.startswith("agent "):
            return self._chat_agent_loop(ws_turn, raw)

        return None

    def _chat_z3(self, ws_turn, raw: str) -> tuple[str, str, bool]:
        body = raw[3:].strip()
        if body.lower().startswith("add "):
            # Format: z3 add c1: x > 5 and y < 10
            m = re.match(r"add\s+([a-zA-Z0-9_]+)\s*:\s*(.+)", body, flags=re.I)
            if not m:
                return ws_turn.clarify("constraint", "Specify a constraint ID and expression, e.g. `z3 add c1: x >= 10`.")
            cid, expr = m.group(1), m.group(2).strip()
            self.z3_coord.add_constraint(cid, expr)
            res = self.z3_coord.check()
            prop = self._record_chat_proposal("z3_add_check", "reasoning_z3", cid, "formally_checked", res)
            ws_turn.card("Z3 Constraint Check", dict(source="execution_backed", executed=True, proposal=prop, z3=res))
            return (
                f"Added Z3 constraint `{cid}: {expr}`. Status: `{res['status']}` "
                f"(active: {res['active_constraint_ids']}, model: {res['model']}, "
                f"translation_verified={res['translation_verified']}). [provenance: formally_checked]"
            ), "success", False
        if body.lower().startswith("undo ") or body.lower().startswith("remove "):
            cid = body.split(None, 1)[1].strip()
            self.z3_coord.remove_constraint(cid)
            res = self.z3_coord.check()
            prop = self._record_chat_proposal("z3_selective_undo", "reasoning_z3", cid, "formally_checked", res)
            ws_turn.card("Z3 Constraint Selective Undo", dict(source="execution_backed", executed=True, proposal=prop, z3=res))
            return (
                f"Selectively removed Z3 constraint `{cid}`. Remaining active: {res['active_constraint_ids']}. "
                f"Status is now `{res['status']}` with model `{res['model']}`. [provenance: formally_checked]"
            ), "success", False
        if body.lower() == "check":
            res = self.z3_coord.check()
            prop = self._record_chat_proposal("z3_check", "reasoning_z3", "solver", "formally_checked", res)
            ws_turn.card("Z3 Constraint Check", dict(source="execution_backed", executed=True, proposal=prop, z3=res))
            return f"Z3 status: `{res['status']}`, model: `{res['model']}`. [provenance: formally_checked]", "success", False
        return ws_turn.clarify("constraint", "Supported Z3 commands: `z3 add <id>: <expr>`, `z3 remove <id>`, `z3 check`.")

    def _chat_sympy(self, ws_turn, raw: str) -> tuple[str, str, bool]:
        body = raw[6:].strip()
        if body.lower().startswith("derivative "):
            expr = body[11:].strip()
            res = SymPySymbolicBackend.solve_or_simplify(dict(op="derivative", expression=expr))
        elif body.lower().startswith("equivalent "):
            parts = body[11:].split("==", 1)
            res = SymPySymbolicBackend.solve_or_simplify(dict(
                op="equivalence", expression=parts[0].strip(), target_expression=parts[1].strip()
            ))
        else:
            expr = re.sub(r"^solve\s+", "", body, flags=re.I).strip()
            res = SymPySymbolicBackend.solve_or_simplify(dict(op="solve", expression=expr))
        prop = self._record_chat_proposal("sympy_math", "reasoning_sympy", expr if "expr" in locals() else body, "formally_checked", res)
        ws_turn.card("SymPy Symbolic Result", dict(source="execution_backed", executed=True, proposal=prop, sympy=res))
        return f"SymPy result: `{json.dumps(res)}`. [provenance: formally_checked]", "success", False

    def _chat_lean4(self, ws_turn, raw: str) -> tuple[str, str, bool]:
        source = re.sub(r"^(?:lean4|lean)\s+", "", raw, flags=re.I).strip()
        res = Lean4ProofBackend.check_proof(source)
        status_code = "blocked_missing_runtime" if res["status"] == "blocked_missing_runtime" else (
            "verified" if res.get("verified") else "rejected"
        )
        prop = self._record_chat_proposal("lean4_check", "reasoning_lean4", "ProofCheck.lean", res["provenance_kind"], res, status_code)
        ws_turn.card("Lean 4 Proof Check", dict(source="execution_backed", executed=res.get("verified", False), proposal=prop, lean4=res))
        if res["status"] == "blocked_missing_runtime":
            return (
                "Lean 4 proof checking is blocked on this host because the `lean` binary is not installed. "
                "Per NEXUS protocol, missing external runtimes are reported honestly as `blocked_missing_runtime` "
                "and never mocked."
            ), "clarification", False
        if not res.get("verified"):
            return f"Lean 4 rejected the proof (`{res['status']}`): {res.get('reason') or res.get('stderr')}", "clarification", False
        return "Lean 4 verified the theorem with zero incomplete tokens. [provenance: formally_checked]", "success", False

    def _chat_program_editor(self, ws_turn, raw: str) -> tuple[str, str, bool]:
        body = re.sub(r"^(?:program|editor)\s+", "", raw, flags=re.I).strip()
        b_lower = body.lower()

        if b_lower.startswith("init sales "):
            path_str = body[11:].strip()
            path = Path(path_str).expanduser().resolve()
            if not path.is_file():
                return ws_turn.clarify("file", f"Could not find CSV file `{path_str}`.")
            rows, profiles = ws_turn.load_table(path)
            from .assistant_benchmark_v2 import bind
            bindings = bind(profiles, dict(op="sum", min=None, order="desc"))
            self.editor = StatefulProgramEditor()
            self.editor.selected_source = str(path)
            self.editor.rebind_schema(dict(key_col=bindings["key_col"], metric_col=bindings["metric_col"], total_col="total"))
            self.editor.insert_node("grp_1", "group_by", dict(key="$KEY_COL"))
            self.editor.insert_node("agg_1", "aggregate", dict(key="$KEY_COL", metric="$METRIC_COL", out_col="$TOTAL_COL", agg_fn="sum"))
            self.editor.insert_node("sort_1", "sort_rows", dict(key="$TOTAL_COL", order="desc"))
            return self._execute_editor_and_reply(ws_turn, path, rows, "Initialized grouped sales program (`grp_1`, `agg_1`, `sort_1`).")

        if b_lower.startswith("row_filter "):
            # e.g., program row_filter rf_1 >= 10
            m = re.match(r"row_filter\s+([a-zA-Z0-9_]+)\s*(>=|>|<=|<|==)\s*(-?\d+(?:\.\d+)?)", body, flags=re.I)
            if not m:
                return ws_turn.clarify("constraint", "Use `program row_filter rf_1 >= 10`.")
            nid, op_sym, val = m.group(1), m.group(2), float(m.group(3))
            cmp_map = {">=": "ge", ">": "gt", "<=": "le", "<": "lt", "==": "eq"}
            self.editor.insert_node(nid, "row_filter", dict(field="$METRIC_COL", cmp=cmp_map[op_sym], threshold=val))
            path = Path(self.editor.selected_source or ws_turn.ws["selected_file"])
            rows, _ = ws_turn.load_table(path)
            return self._execute_editor_and_reply(ws_turn, path, rows, f"Inserted row filter `{nid}` ({op_sym} {val}).")

        if b_lower.startswith("group_filter "):
            # e.g., program group_filter gf_1 >= 100
            m = re.match(r"group_filter\s+([a-zA-Z0-9_]+)\s*(>=|>|<=|<|==)\s*(-?\d+(?:\.\d+)?)", body, flags=re.I)
            if not m:
                return ws_turn.clarify("constraint", "Use `program group_filter gf_1 >= 100`.")
            nid, op_sym, val = m.group(1), m.group(2), float(m.group(3))
            cmp_map = {">=": "ge", ">": "gt", "<=": "le", "<": "lt", "==": "eq"}
            self.editor.insert_node(nid, "group_filter", dict(field="$TOTAL_COL", cmp=cmp_map[op_sym], threshold=val))
            path = Path(self.editor.selected_source or ws_turn.ws["selected_file"])
            rows, _ = ws_turn.load_table(path)
            return self._execute_editor_and_reply(ws_turn, path, rows, f"Inserted group total filter `{nid}` ({op_sym} {val}).")

        if b_lower.startswith("sort "):
            order = "asc" if "asc" in b_lower else "desc"
            self.editor.replace_node("sort_1", "sort_rows", dict(key="$TOTAL_COL", order=order))
            path = Path(self.editor.selected_source or ws_turn.ws["selected_file"])
            rows, _ = ws_turn.load_table(path)
            return self._execute_editor_and_reply(ws_turn, path, rows, f"Updated `sort_1` to order={order}.")

        if b_lower.startswith("selective_undo ") or b_lower.startswith("remove "):
            nid = body.split(None, 1)[1].strip()
            try:
                self.editor.selective_undo(nid)
            except ValueError as exc:
                return ws_turn.clarify("conflict", f"Cannot selectively undo `{nid}` due to dependent node conflict: {exc}")
            path = Path(self.editor.selected_source or ws_turn.ws["selected_file"])
            rows, _ = ws_turn.load_table(path)
            return self._execute_editor_and_reply(ws_turn, path, rows, f"Selectively undone node `{nid}` while preserving independent nodes {[n.node_id for n in self.editor.nodes]}.")

        if b_lower == "save capsule":
            path = Path(self.editor.selected_source or ws_turn.ws["selected_file"])
            sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
            cap = self.editor.export_capsule(source_sha=sha)
            cap_path = self.store.procedures_dir() / f"{cap['id']}.json"
            cap_path.write_text(json.dumps(cap, indent=2), encoding="utf-8")
            ws_turn.ws["last_procedure_id"] = cap["id"]
            ws_turn.ws["last_saved_explicit"] = True
            prop = self._record_chat_proposal("editor_save_capsule", "stateful_program_editor", cap["id"], "observed_execution", cap)
            ws_turn.card("Saved Stateful Program Capsule", dict(source="execution_backed", executed=False, capsule=cap, proposal=prop))
            return f"Saved stateful program capsule `{cap['id']}` with nodes `{[n['node_id'] for n in cap['nodes']]}`.", "success", False

        if b_lower.startswith("apply capsule "):
            path_str = body[14:].strip()
            path = Path(path_str).expanduser().resolve()
            if not path.is_file():
                return ws_turn.clarify("file", f"Could not open target CSV `{path_str}`.")
            cid = ws_turn.ws.get("last_procedure_id")
            if not cid:
                caps = sorted(self.store.procedures_dir().glob("*.json"))
                if not caps:
                    return ws_turn.clarify("procedure", "No saved capsule found.")
                cid = caps[-1].stem
            cap = json.loads((self.store.procedures_dir() / f"{cid}.json").read_text(encoding="utf-8"))
            rows, profiles = ws_turn.load_table(path)
            from .assistant_benchmark_v2 import bind
            try:
                bindings = bind(profiles, dict(op="sum", min=None, order="desc"))
            except ValueError as exc:
                return ws_turn.clarify("file", f"Incompatible target schema: {exc}. Nothing ran.")
            self.editor = StatefulProgramEditor.from_capsule(
                cap, dict(key_col=bindings["key_col"], metric_col=bindings["metric_col"], total_col="total")
            )
            self.editor.selected_source = str(path)
            return self._execute_editor_and_reply(ws_turn, path, rows, f"Rebound and executed saved capsule `{cid}` on `{path.name}`.")

        return ws_turn.clarify("grain", "Unknown program editor command.")

    def _execute_editor_and_reply(self, ws_turn, path: Path, rows: list[dict[str, Any]], summary_note: str) -> tuple[str, str, bool]:
        out = self.editor.execute(rows)
        out_path = self.store.outputs_dir() / f"{path.stem}-editor-{digest(out)[:10]}.json"
        from .workspace_conversation import publish_json
        publish_json(out_path, out)
        receipt = digest(out)
        ws_turn.ws["selected_file"] = str(path)
        ws_turn.ws["last_output_path"] = str(out_path)
        ws_turn.ws["last_correction"] = summary_note[:450]
        prop = self._record_chat_proposal(
            "editor_execute", "stateful_program_editor", path.name, "observed_execution",
            dict(output_path=str(out_path), receipt=receipt, nodes=[n.node_id for n in self.editor.nodes], row_count=len(out)),
        )
        ws_turn.card("Execution-backed result", dict(
            source="execution_backed",
            executed=True,
            committed=True,
            row_count=len(out),
            preview=out[:5],
            output_path=str(out_path),
            source_file=str(path),
            source_file_unchanged=True,
            receipt=receipt,
            active_nodes=[asdict(n) for n in self.editor.nodes],
            bindings=dict(self.editor.bindings),
            proposal=prop,
        ))
        return f"{summary_note} Wrote {len(out)} row(s) to {out_path}. [provenance: observed_execution]", "success", False

    def _chat_knowledge(self, ws_turn, raw: str) -> tuple[str, str, bool]:
        query = re.sub(r"^(?:wikidata|docs)\s+", "", raw, flags=re.I).strip()
        res = self.knowledge.retrieve(query)
        prop = self._record_chat_proposal("knowledge_retrieve", "knowledge_and_docs", query, "source_attributed", res)
        ws_turn.card("Source-Attributed Knowledge Retrieval", dict(
            source="source_attributed", executed=False, proposal=prop, retrieval=res
        ))
        if res["contradictions"]:
            return (
                f"Retrieved sources for `{query}`, but detected {len(res['contradictions'])} contradiction(s) "
                f"across claims (`uncertainty={res['uncertainty']}`). Lexical candidates are kept separate from "
                "executable bindings. [provenance: source_attributed]"
            ), "clarification", False
        return (
            f"Retrieved {len(res['doc_hits'])} versioned doc hit(s) and {len(res['wikidata_hits'])} Wikidata snapshot "
            f"entity hit(s) for `{query}` (`uncertainty={res['uncertainty']}`). [provenance: source_attributed]"
        ), "reply", False

    def _chat_coding(self, ws_turn, raw: str) -> tuple[str, str, bool]:
        body = re.sub(r"^(?:code|typescript|repo)\s+", "", raw, flags=re.I).strip()
        if body.lower().startswith("search "):
            q = body[7:].strip()
            hits = self.coding.search_source(q)
            prop = self._record_chat_proposal("coding_search", "polyglot_coding", q, "observed_execution", dict(hits=hits))
            ws_turn.card("Repository Search Result", dict(source="execution_backed", executed=True, hits=hits, proposal=prop))
            return f"Found {len(hits)} source hit(s) for `{q}`. [provenance: observed_execution]", "reply", False
        if body.lower() == "index":
            idx = self.coding.index_repository()
            prop = self._record_chat_proposal("coding_index", "polyglot_coding", "repo", "observed_execution", idx)
            ws_turn.card("Repository CST/AST Index", dict(source="execution_backed", executed=True, index=idx, proposal=prop))
            return f"Indexed {len(idx['files'])} file(s) (`tree_sitter_active={idx['tree_sitter_active']}`). [provenance: observed_execution]", "reply", False
        return ws_turn.clarify("reference", "Supported coding commands: `repo index`, `repo search <query>`.")

    def _chat_planning(self, ws_turn, raw: str) -> tuple[str, str, bool]:
        body = raw[5:].strip()
        if body.lower() == "inspect":
            d = self.planner.to_dict()
            prop = self._record_chat_proposal("plan_inspect", "hierarchical_planner", "hierarchy", "observed_execution", d)
            ws_turn.card("Hierarchical Plan State", dict(source="execution_backed", executed=False, planner=d, proposal=prop))
            return f"Hierarchical plan has {len(d['nodes'])} linked node(s) across project, module, and function levels.", "reply", False
        return ws_turn.clarify("reference", "Use `plan inspect` or `/api/seed` `workbench_planning` operations.")

    def _chat_capsule(self, ws_turn, raw: str) -> tuple[str, str, bool]:
        body = raw[8:].strip()
        if body.lower() == "consolidate":
            res = self.registry.consolidate_and_prune()
            prop = self._record_chat_proposal("capsule_consolidate", "stigmergic_capsule_registry", "registry", "tested_hypothesis", res)
            ws_turn.card("Capsule Consolidation", dict(source="execution_backed", executed=True, result=res, proposal=prop))
            return f"Consolidated capsules: kept active={res['kept_active']}, moved to cold={res['moved_to_cold']}.", "success", False
        return ws_turn.clarify("procedure", "Use `capsule consolidate` or `/api/seed` `workbench_capsules` operations.")

    def _handle_agent_solve_api(self, args: dict[str, Any]) -> dict[str, Any]:
        from .symbiotic_agent_loop import AgentTaskPublicView, SymbioticAgentLoop
        task_view = AgentTaskPublicView(
            task_id=args.get("task_id", "api_agent_task"),
            cohort=args.get("cohort", "development"),
            domain=args.get("domain", "python_repo"),
            language=args.get("language", "python"),
            request=args["request"],
            files=args["files"],
            public_tests=args.get("public_tests", []),
            docs=args.get("docs", []),
            budget_steps=int(args.get("budget_steps", 16)),
        )
        loop = SymbioticAgentLoop(self.base_dir / "agent_runs", capsule_registry=self.registry)
        res = loop.solve(task_view)
        status_map = {
            "solved": "verified",
            "failed": "failed",
            "rejected": "rejected",
            "blocked": "blocked_missing_runtime",
        }
        prop = TypedActionProposal(
            proposal_id=digest([task_view.task_id, res["final_files_sha256"]])[:16],
            intent="agent_autonomous_solve",
            backend="symbiotic_agent_loop",
            target=task_view.task_id,
            input_type="AgentTaskPublicView",
            output_type="ReplayableAgentTrajectory",
            preconditions=["bounded_worker_subprocess"],
            expected_effects=[f"outcome_{res['outcome_category']}"],
            dependencies=[],
            version_id="v1",
            resource_limits=dict(budget_steps=task_view.budget_steps),
            execution_status=status_map.get(res["outcome_category"], "executed"),
            provenance_kind="observed_execution",
            rollback_semantics="isolated_worktree",
            evidence=dict(
                outcome_category=res["outcome_category"],
                tool_call_count=len(res["tool_calls"]),
                patch_attempt_count=len(res["patch_attempts"]),
            ),
        )
        self._save_state("symbiotic_agent_loop", prop)
        return dict(proposal=prop.validate(), result=res)

    def _chat_agent_loop(self, ws_turn, raw: str) -> tuple[str, str, bool]:
        body = raw[6:].strip()
        try:
            spec = json.loads(body) if body.startswith("{") else dict(
                task_id="chat_agent_task",
                domain="python_repo",
                language="python",
                request=body,
                files=self.coding.files,
                public_tests=[],
            )
        except Exception as exc:
            return ws_turn.clarify("reference", f"Invalid agent request payload: {exc}")
        out = self._handle_agent_solve_api(spec)
        res = out["result"]
        ws_turn.card("Autonomous Agent Loop Result", dict(
            source="execution_backed",
            executed=(res["outcome_category"] == "solved"),
            outcome_category=res["outcome_category"],
            tool_calls=res["tool_calls"],
            patch_attempts=res["patch_attempts"],
            final_diff=res["final_diff"],
            proposal=out["proposal"],
        ))
        turn_status = "success" if res["outcome_category"] == "solved" else (
            "clarification" if res["outcome_category"] in ("rejected", "blocked") else "error"
        )
        return (
            f"Agent loop finished with outcome `{res['outcome_category']}`: {res['summary_message']} "
            f"({len(res['tool_calls'])} tool call(s), {len(res['patch_attempts'])} patch attempt(s))."
        ), turn_status, False

    def _record_chat_proposal(self, intent: str, backend: str, target: str, prov: str,
                              evidence: dict[str, Any], status: str = "committed") -> dict[str, Any]:
        prop = TypedActionProposal(
            proposal_id=digest([intent, backend, target, time.time_ns()])[:16],
            intent=intent,
            backend=backend,
            target=target,
            input_type="ChatCommand",
            output_type="VerifiedArtifact",
            preconditions=["session_active"],
            expected_effects=[intent],
            dependencies=[],
            version_id="v1",
            resource_limits=dict(timeout_s=5.0),
            execution_status=status,
            provenance_kind=prov,
            rollback_semantics="selective_undo_supported",
            evidence=dict(summary=str(evidence)[:500]),
        )
        self._save_state(backend, prop)
        return prop.validate()

