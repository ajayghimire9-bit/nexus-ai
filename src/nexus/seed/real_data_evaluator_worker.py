"""Isolated black-box evaluator and reference teacher worker for
`seed_real_data_adapter_learning_v1`.

Runs in a separate OS subprocess (`python3 -m nexus.seed.real_data_evaluator_worker`)
so that:
  1. Ground-truth reference implementations and private held-out assessment
     datasets/tables (CSV, JSON, and SQLite) never enter the learner's process memory;
  2. Read-only source files are written to `read_only_source/` (`0o444` mode) and
     cryptographically hash-checked before and after learner execution, while learner
     outputs must be written to a separate `output/` directory;
  3. Entire datasets and schemas (`clinical_sensor_telemetry`, `financial_ledger_audit`,
     `supply_chain_shipments_db`, `hospital_lab_results_db`) are reserved exclusively
     for later independent confirmation assessment rather than merely withholding rows;
  4. Active disambiguating questions (`answer_disambiguating_query`) are answered by
     executing the reference implementation on the learner's synthesized query rows
     when `answer_source_available=True`, or rejected when testing ambiguity reporting.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
from typing import Any


MISSING_SENTINELS = {None, "", "N/A", "n/a", "null", "NULL", "NaN", "nan", "ERR", "err", "-"}


def _canon_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_obj(obj: Any) -> str:
    return _sha256_bytes(_canon_json(obj).encode("utf-8"))


def _is_missing(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip() in MISSING_SENTINELS:
        return True
    return False


def _parse_num(val: Any, num_type: str = "float") -> float | int | None:
    if _is_missing(val):
        return None
    try:
        s = str(val).strip().replace("$", "").replace(",", "")
        f = float(s)
        if num_type == "int":
            return int(round(f))
        return round(f, 4)
    except (ValueError, TypeError):
        return None


def _norm_text(val: Any, ops: list[str] | tuple[str, ...]) -> str:
    if _is_missing(val):
        return ""
    s = str(val)
    for op in ops:
        if op == "strip":
            s = s.strip()
        elif op == "lower":
            s = s.lower()
        elif op == "upper":
            s = s.upper()
        elif op == "strip_trailing_slash":
            s = s.rstrip("/")
        elif op == "collapse_spaces":
            s = " ".join(s.split())
    return s


# ==============================================================================
# GROUND-TRUTH REFERENCE IMPLEMENTATIONS (PRIVATE TO EVALUATOR SUBPROCESS)
# ==============================================================================

def _ref_s1_filter_and_normalize_error_logs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Task S1: Filter production server error logs (`env == 'prod'`, `status_code >= 500`,
    valid non-missing `latency_ms`), normalize `endpoint` (`strip`, `lower`,
    `strip_trailing_slash`), project (`endpoint`, `status_code`, `latency_ms`, `region`),
    and order by `latency_ms DESC, endpoint ASC`."""
    out: list[dict[str, Any]] = []
    for r in rows:
        env_v = _norm_text(r.get("env"), ("strip", "lower"))
        if env_v != "prod":
            continue
        sc = _parse_num(r.get("status_code"), "int")
        lat = _parse_num(r.get("latency_ms"), "float")
        ep = _norm_text(r.get("endpoint"), ("strip", "lower", "strip_trailing_slash"))
        reg = _norm_text(r.get("region"), ("strip", "lower"))
        if sc is None or lat is None or not ep or not reg:
            continue
        if int(sc) >= 500:
            out.append(
                dict(
                    endpoint=ep,
                    status_code=int(sc),
                    latency_ms=round(float(lat), 2),
                    region=reg,
                )
            )
    out.sort(key=lambda x: (-float(x["latency_ms"]), str(x["endpoint"])))
    return out


def _ref_s2_endpoint_latency_grouped_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Task S2: Filter valid production error logs (`env == 'prod'`, `status_code >= 500`),
    normalize `endpoint`, group by `endpoint`, aggregate (`event_count`, `total_latency_ms`,
    `mean_latency_ms`, `max_latency_ms`), and order by `total_latency_ms DESC, endpoint ASC`."""
    cleaned = _ref_s1_filter_and_normalize_error_logs(rows)
    groups: dict[str, list[float]] = {}
    for r in cleaned:
        ep = str(r["endpoint"])
        groups.setdefault(ep, []).append(float(r["latency_ms"]))
    summary: list[dict[str, Any]] = []
    for ep, vals in groups.items():
        cnt = len(vals)
        tot = round(sum(vals), 2)
        mean_v = round(tot / cnt, 2)
        max_v = round(max(vals), 2)
        summary.append(
            dict(
                endpoint=ep,
                event_count=cnt,
                total_latency_ms=tot,
                mean_latency_ms=mean_v,
                max_latency_ms=max_v,
            )
        )
    summary.sort(key=lambda x: (-float(x["total_latency_ms"]), str(x["endpoint"])))
    return summary


def _ref_s3_region_incident_rollup(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Task S3: Filter production error logs (`env == 'prod'`, `status_code >= 500`),
    normalize `region`, group by `region`, aggregate (`event_count`, `total_latency_ms`,
    `mean_latency_ms`, `max_latency_ms`), and order by `total_latency_ms DESC, region ASC`."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        env = _norm_text(r.get("env"), ("strip", "lower"))
        if env != "prod":
            continue
        sc = _parse_num(r.get("status_code"), "int")
        lat = _parse_num(r.get("latency_ms"), "float")
        reg = _norm_text(r.get("region"), ("strip", "lower", "strip_trailing_slash"))
        if sc is None or lat is None or not reg:
            continue
        if int(sc) >= 500:
            groups.setdefault(reg, []).append(round(float(lat), 2))
    summary: list[dict[str, Any]] = []
    for reg, vals in groups.items():
        cnt = len(vals)
        tot = round(sum(vals), 2)
        mean_v = round(tot / cnt, 2)
        max_v = round(max(vals), 2)
        summary.append(
            dict(
                region=reg,
                event_count=cnt,
                total_latency_ms=tot,
                mean_latency_ms=mean_v,
                max_latency_ms=max_v,
            )
        )
    summary.sort(key=lambda x: (-float(x["total_latency_ms"]), str(x["region"])))
    return summary


def _ref_d1_clean_completed_orders(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Task D1 (Development Schema: `ecommerce_orders_and_refunds`):
    Filter `order_status == 'completed'`, `amount_usd >= 50.0`, normalize `sku_code`
    (`strip`, `lower`, `strip_trailing_slash`) and `warehouse_zone` (`strip`, `lower`),
    project (`sku_code`, `amount_usd`, `warehouse_zone`), and order by `amount_usd DESC, sku_code ASC`."""
    out: list[dict[str, Any]] = []
    for r in rows:
        st = _norm_text(r.get("order_status"), ("strip", "lower"))
        if st != "completed":
            continue
        amt = _parse_num(r.get("amount_usd"), "float")
        sku = _norm_text(r.get("sku_code"), ("strip", "lower", "strip_trailing_slash"))
        wh = _norm_text(r.get("warehouse_zone"), ("strip", "lower"))
        if amt is None or not sku or not wh:
            continue
        if float(amt) >= 50.0:
            out.append(
                dict(
                    sku_code=sku,
                    amount_usd=round(float(amt), 2),
                    warehouse_zone=wh,
                )
            )
    out.sort(key=lambda x: (-float(x["amount_usd"]), str(x["sku_code"])))
    return out


def _ref_d2_sku_revenue_grouped_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Task D2 (Development Schema: `ecommerce_orders_and_refunds`):
    Filter `order_status == 'completed'`, `amount_usd >= 50.0`, normalize `sku_code`,
    group by `sku_code`, aggregate (`event_count`, `total_amount_usd`, `mean_amount_usd`,
    `max_amount_usd`), and order by `total_amount_usd DESC, sku_code ASC`."""
    cleaned = _ref_d1_clean_completed_orders(rows)
    groups: dict[str, list[float]] = {}
    for r in cleaned:
        sku = str(r["sku_code"])
        groups.setdefault(sku, []).append(float(r["amount_usd"]))
    summary: list[dict[str, Any]] = []
    for sku, vals in groups.items():
        cnt = len(vals)
        tot = round(sum(vals), 2)
        summary.append(
            dict(
                sku_code=sku,
                event_count=cnt,
                total_amount_usd=tot,
                mean_amount_usd=round(tot / cnt, 2),
                max_amount_usd=round(max(vals), 2),
            )
        )
    summary.sort(key=lambda x: (-float(x["total_amount_usd"]), str(x["sku_code"])))
    return summary


def _ref_a1_telemetry_alert_aggregation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Task A1 (Reserved Independent Confirmation Schema 1: `clinical_sensor_telemetry`):
    Filter `calibration_state == 'calibrated'`, `reading_mv >= 120.0`, normalize `ward_id`
    (`strip`, `lower`, `strip_trailing_slash`), group by `ward_id`, aggregate
    (`event_count`, `total_reading_mv`, `mean_reading_mv`, `max_reading_mv`), and order by
    `total_reading_mv DESC, ward_id ASC`."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        cal = _norm_text(r.get("calibration_state"), ("strip", "lower"))
        if cal != "calibrated":
            continue
        mv = _parse_num(r.get("reading_mv"), "float")
        ward = _norm_text(r.get("ward_id"), ("strip", "lower", "strip_trailing_slash"))
        if mv is None or not ward:
            continue
        if float(mv) >= 120.0:
            groups.setdefault(ward, []).append(round(float(mv), 2))
    summary: list[dict[str, Any]] = []
    for ward, vals in groups.items():
        cnt = len(vals)
        tot = round(sum(vals), 2)
        summary.append(
            dict(
                ward_id=ward,
                event_count=cnt,
                total_reading_mv=tot,
                mean_reading_mv=round(tot / cnt, 2),
                max_reading_mv=round(max(vals), 2),
            )
        )
    summary.sort(key=lambda x: (-float(x["total_reading_mv"]), str(x["ward_id"])))
    return summary


def _ref_a2_ledger_department_reconciliation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Task A2 (Reserved Independent Confirmation Schema 2: `financial_ledger_audit`):
    Filter `clearance_status == 'cleared'`, `posted_usd >= 200.0`, normalize `dept_code`
    (`strip`, `lower`, `strip_trailing_slash`), group by `dept_code`, aggregate
    (`event_count`, `total_posted_usd`, `mean_posted_usd`, `max_posted_usd`), and order by
    `total_posted_usd DESC, dept_code ASC`."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        cl = _norm_text(r.get("clearance_status"), ("strip", "lower"))
        if cl != "cleared":
            continue
        amt = _parse_num(r.get("posted_usd"), "float")
        dept = _norm_text(r.get("dept_code"), ("strip", "lower", "strip_trailing_slash"))
        if amt is None or not dept:
            continue
        if float(amt) >= 200.0:
            groups.setdefault(dept, []).append(round(float(amt), 2))
    summary: list[dict[str, Any]] = []
    for dept, vals in groups.items():
        cnt = len(vals)
        tot = round(sum(vals), 2)
        summary.append(
            dict(
                dept_code=dept,
                event_count=cnt,
                total_posted_usd=tot,
                mean_posted_usd=round(tot / cnt, 2),
                max_posted_usd=round(max(vals), 2),
            )
        )
    summary.sort(key=lambda x: (-float(x["total_posted_usd"]), str(x["dept_code"])))
    return summary


def _ref_sql1_service_telemetry_db(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SQLite Task SQL1 (Development SQLite Schema: `cluster_rpc_events`):
    Filter `tier_mode == 'active'`, `duration_ms >= 250.0`, normalize `service_route`
    (`strip`, `lower`, `strip_trailing_slash`), group by `service_route`, aggregate
    (`event_count`, `total_duration_ms`, `mean_duration_ms`, `max_duration_ms`), and order by
    `total_duration_ms DESC, service_route ASC`."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        tm = _norm_text(r.get("tier_mode"), ("strip", "lower"))
        if tm != "active":
            continue
        dur = _parse_num(r.get("duration_ms"), "float")
        rt = _norm_text(r.get("service_route"), ("strip", "lower", "strip_trailing_slash"))
        if dur is None or not rt:
            continue
        if float(dur) >= 250.0:
            groups.setdefault(rt, []).append(round(float(dur), 2))
    summary: list[dict[str, Any]] = []
    for rt, vals in groups.items():
        cnt = len(vals)
        tot = round(sum(vals), 2)
        summary.append(
            dict(
                service_route=rt,
                event_count=cnt,
                total_duration_ms=tot,
                mean_duration_ms=round(tot / cnt, 2),
                max_duration_ms=round(max(vals), 2),
            )
        )
    summary.sort(key=lambda x: (-float(x["total_duration_ms"]), str(x["service_route"])))
    return summary


def _ref_sql2_supply_chain_shipments_db(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SQLite Task SQL2 (Reserved Independent Confirmation SQLite Schema 1: `freight_manifests`):
    Filter `customs_state == 'released'`, `freight_kg >= 100.0`, normalize `corridor_lane`
    (`strip`, `lower`, `strip_trailing_slash`), group by `corridor_lane`, aggregate
    (`event_count`, `total_freight_kg`, `mean_freight_kg`, `max_freight_kg`), and order by
    `total_freight_kg DESC, corridor_lane ASC`."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        cs = _norm_text(r.get("customs_state"), ("strip", "lower"))
        if cs != "released":
            continue
        kg = _parse_num(r.get("freight_kg"), "float")
        lane = _norm_text(r.get("corridor_lane"), ("strip", "lower", "strip_trailing_slash"))
        if kg is None or not lane:
            continue
        if float(kg) >= 100.0:
            groups.setdefault(lane, []).append(round(float(kg), 2))
    summary: list[dict[str, Any]] = []
    for lane, vals in groups.items():
        cnt = len(vals)
        tot = round(sum(vals), 2)
        summary.append(
            dict(
                corridor_lane=lane,
                event_count=cnt,
                total_freight_kg=tot,
                mean_freight_kg=round(tot / cnt, 2),
                max_freight_kg=round(max(vals), 2),
            )
        )
    summary.sort(key=lambda x: (-float(x["total_freight_kg"]), str(x["corridor_lane"])))
    return summary


def _ref_sql3_hospital_lab_results_db(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SQLite Task SQL3 (Reserved Independent Confirmation SQLite Schema 2: `assay_batches`):
    Filter `qc_flag == 'verified'`, `concentration_ug >= 40.0`, normalize `panel_code`
    (`strip`, `lower`, `strip_trailing_slash`), group by `panel_code`, aggregate
    (`event_count`, `total_concentration_ug`, `mean_concentration_ug`, `max_concentration_ug`),
    and order by `total_concentration_ug DESC, panel_code ASC`."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        qc = _norm_text(r.get("qc_flag"), ("strip", "lower"))
        if qc != "verified":
            continue
        ug = _parse_num(r.get("concentration_ug"), "float")
        panel = _norm_text(r.get("panel_code"), ("strip", "lower", "strip_trailing_slash"))
        if ug is None or not panel:
            continue
        if float(ug) >= 40.0:
            groups.setdefault(panel, []).append(round(float(ug), 2))
    summary: list[dict[str, Any]] = []
    for panel, vals in groups.items():
        cnt = len(vals)
        tot = round(sum(vals), 2)
        summary.append(
            dict(
                panel_code=panel,
                event_count=cnt,
                total_concentration_ug=tot,
                mean_concentration_ug=round(tot / cnt, 2),
                max_concentration_ug=round(max(vals), 2),
            )
        )
    summary.sort(key=lambda x: (-float(x["total_concentration_ug"]), str(x["panel_code"])))
    return summary


def _ref_r1_repo_python_ast_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Naturally Occurring Repository Task R1 (`repo_python_ast_metrics`):
    Processes real AST metrics extracted from actual repository `.py` files on disk.
    Filter `module_tier == 'active'`, `ast_node_count >= 150.0`, normalize `package_group`
    (`strip`, `lower`, `strip_trailing_slash`), group by `package_group`, aggregate
    (`event_count`, `total_ast_node_count`, `mean_ast_node_count`, `max_ast_node_count`),
    and order by `total_ast_node_count DESC, package_group ASC`."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        mt = _norm_text(r.get("module_tier"), ("strip", "lower"))
        if mt != "active":
            continue
        nodes = _parse_num(r.get("ast_node_count"), "float")
        pkg = _norm_text(r.get("package_group"), ("strip", "lower", "strip_trailing_slash"))
        if nodes is None or not pkg:
            continue
        if float(nodes) >= 150.0:
            groups.setdefault(pkg, []).append(round(float(nodes), 2))
    summary: list[dict[str, Any]] = []
    for pkg, vals in groups.items():
        cnt = len(vals)
        tot = round(sum(vals), 2)
        summary.append(
            dict(
                package_group=pkg,
                event_count=cnt,
                total_ast_node_count=tot,
                mean_ast_node_count=round(tot / cnt, 2),
                max_ast_node_count=round(max(vals), 2),
            )
        )
    summary.sort(key=lambda x: (-float(x["total_ast_node_count"]), str(x["package_group"])))
    return summary


def _ref_amb1_revenue_eur_semantic_disambiguation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ambiguous-Header Task AMB1 (`european_merchant_settlements`):
    Header `revenue_eur` contains both positive gross charges (`>= 50.0`), small fees (`20.0`),
    and negative refunds (`-45.0`, `-80.0`). Requires positive settled gross revenue (`>= 50.0`)."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        st = _norm_text(r.get("settlement_state"), ("strip", "lower"))
        if st != "settled":
            continue
        rev = _parse_num(r.get("revenue_eur"), "float")
        mcat = _norm_text(r.get("merchant_Desk"), ("strip", "lower", "strip_trailing_slash"))
        if rev is None or not mcat:
            continue
        if float(rev) >= 50.0:
            groups.setdefault(mcat, []).append(round(float(rev), 2))
    summary: list[dict[str, Any]] = []
    for mcat, vals in groups.items():
        cnt = len(vals)
        tot = round(sum(vals), 2)
        summary.append(
            dict(
                merchant_Desk=mcat,
                event_count=cnt,
                total_revenue_eur=tot,
                mean_revenue_eur=round(tot / cnt, 2),
                max_revenue_eur=round(max(vals), 2),
            )
        )
    summary.sort(key=lambda x: (-float(x["total_revenue_eur"]), str(x["merchant_Desk"])))
    return summary


REFERENCE_TASK_FUNCTIONS = {
    "S1_filter_and_normalize_error_logs": _ref_s1_filter_and_normalize_error_logs,
    "S2_endpoint_latency_grouped_summary": _ref_s2_endpoint_latency_grouped_summary,
    "S3_region_incident_rollup": _ref_s3_region_incident_rollup,
    "D1_clean_completed_orders": _ref_d1_clean_completed_orders,
    "D2_sku_revenue_grouped_summary": _ref_d2_sku_revenue_grouped_summary,
    "A1_telemetry_alert_aggregation": _ref_a1_telemetry_alert_aggregation,
    "A2_ledger_department_reconciliation": _ref_a2_ledger_department_reconciliation,
    "SQL1_service_telemetry_db": _ref_sql1_service_telemetry_db,
    "SQL2_supply_chain_shipments_db": _ref_sql2_supply_chain_shipments_db,
    "SQL3_hospital_lab_results_db": _ref_sql3_hospital_lab_results_db,
    "R1_repo_python_ast_metrics": _ref_r1_repo_python_ast_metrics,
    "AMB1_revenue_eur_semantic_disambiguation": _ref_amb1_revenue_eur_semantic_disambiguation,
}


# ==============================================================================
# DATASET GENERATORS (PUBLIC DEMONSTRATION DATA VS PRIVATE HELDOUT ASSESSMENT)
# ==============================================================================

def _server_logs_public_rows() -> list[dict[str, Any]]:
    # Notice: public demonstration rows intentionally leave boundary 500 vs 502 open
    # so active disambiguating queries can probe status_code == 500!
    return [
        {"timestamp": "2026-10-01T10:00:01Z", "endpoint": " /API/v1/CheckOut/ ", "status_code": "503", "latency_ms": "420.5", "env": "PROD", "region": "us-east"},
        {"timestamp": "2026-10-01T10:00:02Z", "endpoint": "/api/v1/checkout", "status_code": "502", "latency_ms": "180.0", "env": "prod", "region": " US-EAST "},
        {"timestamp": "2026-10-01T10:00:03Z", "endpoint": "/api/v1/checkout/", "status_code": "200", "latency_ms": "45.0", "env": "prod", "region": "us-east"},
        {"timestamp": "2026-10-01T10:00:04Z", "endpoint": " /Api/V1/Auth/ ", "status_code": "504", "latency_ms": "310.0", "env": "prod", "region": "eu-west"},
        {"timestamp": "2026-10-01T10:00:05Z", "endpoint": "/api/v1/auth", "status_code": "503", "latency_ms": "N/A", "env": "prod", "region": "eu-west"},
        {"timestamp": "2026-10-01T10:00:06Z", "endpoint": "/api/v1/auth/", "status_code": "502", "latency_ms": "290.0", "env": "staging", "region": "eu-west"},
        {"timestamp": "2026-10-01T10:00:07Z", "endpoint": "/api/v1/search/", "status_code": "404", "latency_ms": "120.0", "env": "prod", "region": "ap-south"},
        {"timestamp": "2026-10-01T10:00:08Z", "endpoint": " /api/v1/Auth ", "status_code": "501", "latency_ms": "190.0", "env": "PROD", "region": "eu-west"},
    ]


def _server_logs_private_heldout_rows() -> list[dict[str, Any]]:
    return [
        {"timestamp": "2026-10-02T11:00:01Z", "endpoint": " /API/v2/PayMent/ ", "status_code": "500", "latency_ms": "510.25", "env": "prod", "region": "us-west"},
        {"timestamp": "2026-10-02T11:00:02Z", "endpoint": "/api/v2/payment", "status_code": "503", "latency_ms": "289.75", "env": "PROD", "region": " US-WEST "},
        {"timestamp": "2026-10-02T11:00:03Z", "endpoint": "/api/v2/payment/", "status_code": "499", "latency_ms": "910.0", "env": "prod", "region": "us-west"},
        {"timestamp": "2026-10-02T11:00:04Z", "endpoint": "/api/v2/payment", "status_code": "502", "latency_ms": "null", "env": "prod", "region": "us-west"},
        {"timestamp": "2026-10-02T11:00:05Z", "endpoint": " /Api/V2/Inventory/ ", "status_code": "504", "latency_ms": "640.0", "env": "prod", "region": "eu-central"},
        {"timestamp": "2026-10-02T11:00:06Z", "endpoint": "/api/v2/inventory", "status_code": "500", "latency_ms": "360.0", "env": "prod", "region": "eu-central"},
        {"timestamp": "2026-10-02T11:00:07Z", "endpoint": "/api/v2/inventory/", "status_code": "503", "latency_ms": "410.0", "env": "dev", "region": "eu-central"},
        {"timestamp": "2026-10-02T11:00:08Z", "endpoint": "/api/v2/profile/", "status_code": "502", "latency_ms": "215.5", "env": "prod", "region": "us-west"},
        {"timestamp": "2026-10-02T11:00:09Z", "endpoint": "", "status_code": "503", "latency_ms": "300.0", "env": "prod", "region": "us-west"},
    ]


def _ecommerce_orders_public_rows() -> list[dict[str, Any]]:
    # Boundary 50.0 vs 55.0 left open in public rows so active query can test amount_usd == 50.0
    return [
        {"order_id": "ORD-1", "sku_code": " SKU-ALPHA/ ", "amount_usd": "120.0", "order_status": "COMPLETED", "warehouse_zone": "Zone-North"},
        {"order_id": "ORD-2", "sku_code": "sku-alpha", "amount_usd": "80.0", "order_status": "completed", "warehouse_zone": " zone-north "},
        {"order_id": "ORD-3", "sku_code": "sku-alpha/", "amount_usd": "35.0", "order_status": "completed", "warehouse_zone": "zone-north"},
        {"order_id": "ORD-4", "sku_code": " SKU-BETA/ ", "amount_usd": "210.5", "order_status": "Completed", "warehouse_zone": "Zone-South"},
        {"order_id": "ORD-5", "sku_code": "sku-beta", "amount_usd": "ERR", "order_status": "completed", "warehouse_zone": "zone-south"},
        {"order_id": "ORD-6", "sku_code": "sku-beta/", "amount_usd": "150.0", "order_status": "REFUNDED", "warehouse_zone": "zone-south"},
        {"order_id": "ORD-7", "sku_code": "sku-beta", "amount_usd": "59.5", "order_status": "completed", "warehouse_zone": "zone-south"},
    ]


def _ecommerce_orders_private_heldout_rows() -> list[dict[str, Any]]:
    return [
        {"order_id": "ORD-101", "sku_code": " SKU-GAMMA/ ", "amount_usd": "50.0", "order_status": "completed", "warehouse_zone": "zone-east"},
        {"order_id": "ORD-102", "sku_code": "sku-gamma", "amount_usd": "150.0", "order_status": "COMPLETED", "warehouse_zone": " ZONE-EAST "},
        {"order_id": "ORD-103", "sku_code": "sku-gamma/", "amount_usd": "49.5", "order_status": "completed", "warehouse_zone": "zone-east"},
        {"order_id": "ORD-104", "sku_code": " SKU-DELTA/ ", "amount_usd": "320.0", "order_status": "completed", "warehouse_zone": "zone-west"},
        {"order_id": "ORD-105", "sku_code": "sku-delta", "amount_usd": "N/A", "order_status": "completed", "warehouse_zone": "zone-west"},
        {"order_id": "ORD-106", "sku_code": "sku-delta/", "amount_usd": "180.0", "order_status": "cancelled", "warehouse_zone": "zone-west"},
        {"order_id": "ORD-107", "sku_code": "sku-delta", "amount_usd": "80.0", "order_status": "Completed", "warehouse_zone": "zone-west"},
    ]


def _telemetry_public_rows() -> list[dict[str, Any]]:
    return [
        {"reading_id": "T-1", "ward_id": " ICU-East/ ", "reading_mv": "180.0", "calibration_state": "CALIBRATED", "sensor_model": "M1"},
        {"reading_id": "T-2", "ward_id": "icu-east", "reading_mv": "140.0", "calibration_state": "calibrated", "sensor_model": "M1"},
        {"reading_id": "T-3", "ward_id": "icu-east/", "reading_mv": "95.0", "calibration_state": "calibrated", "sensor_model": "M1"},
        {"reading_id": "T-4", "ward_id": " Ward-North/ ", "reading_mv": "210.0", "calibration_state": "Calibrated", "sensor_model": "M2"},
        {"reading_id": "T-5", "ward_id": "ward-north", "reading_mv": "NaN", "calibration_state": "calibrated", "sensor_model": "M2"},
        {"reading_id": "T-6", "ward_id": "ward-north/", "reading_mv": "250.0", "calibration_state": "uncalibrated", "sensor_model": "M2"},
        {"reading_id": "T-7", "ward_id": "ward-north", "reading_mv": "130.0", "calibration_state": "calibrated", "sensor_model": "M2"},
    ]


def _telemetry_private_heldout_rows() -> list[dict[str, Any]]:
    return [
        {"reading_id": "T-101", "ward_id": " ICU-West/ ", "reading_mv": "120.0", "calibration_state": "calibrated", "sensor_model": "M1"},
        {"reading_id": "T-102", "ward_id": "icu-west", "reading_mv": "240.0", "calibration_state": "CALIBRATED", "sensor_model": "M1"},
        {"reading_id": "T-103", "ward_id": "icu-west/", "reading_mv": "118.0", "calibration_state": "calibrated", "sensor_model": "M1"},
        {"reading_id": "T-104", "ward_id": " Ward-South/ ", "reading_mv": "310.0", "calibration_state": "calibrated", "sensor_model": "M2"},
        {"reading_id": "T-105", "ward_id": "ward-south", "reading_mv": "null", "calibration_state": "calibrated", "sensor_model": "M2"},
        {"reading_id": "T-106", "ward_id": "ward-south/", "reading_mv": "190.0", "calibration_state": "Calibrated", "sensor_model": "M2"},
        {"reading_id": "T-107", "ward_id": "ward-south", "reading_mv": "400.0", "calibration_state": "drift_error", "sensor_model": "M2"},
    ]


def _ledger_public_rows() -> list[dict[str, Any]]:
    return [
        {"tx_hash": "TX-1", "dept_code": " ENG-CORE/ ", "posted_usd": "450.0", "clearance_status": "CLEARED", "fiscal_qtr": "Q1"},
        {"tx_hash": "TX-2", "dept_code": "eng-core", "posted_usd": "250.0", "clearance_status": "cleared", "fiscal_qtr": "Q1"},
        {"tx_hash": "TX-3", "dept_code": "eng-core/", "posted_usd": "120.0", "clearance_status": "cleared", "fiscal_qtr": "Q1"},
        {"tx_hash": "TX-4", "dept_code": " OPS-INFRA/ ", "posted_usd": "600.0", "clearance_status": "Cleared", "fiscal_qtr": "Q1"},
        {"tx_hash": "TX-5", "dept_code": "ops-infra", "posted_usd": "N/A", "clearance_status": "cleared", "fiscal_qtr": "Q1"},
        {"tx_hash": "TX-6", "dept_code": "ops-infra/", "posted_usd": "500.0", "clearance_status": "pending", "fiscal_qtr": "Q1"},
        {"tx_hash": "TX-7", "dept_code": "ops-infra", "posted_usd": "220.0", "clearance_status": "cleared", "fiscal_qtr": "Q1"},
    ]


def _ledger_private_heldout_rows() -> list[dict[str, Any]]:
    return [
        {"tx_hash": "TX-101", "dept_code": " SEC-AUDIT/ ", "posted_usd": "200.0", "clearance_status": "cleared", "fiscal_qtr": "Q2"},
        {"tx_hash": "TX-102", "dept_code": "sec-audit", "posted_usd": "400.0", "clearance_status": "CLEARED", "fiscal_qtr": "Q2"},
        {"tx_hash": "TX-103", "dept_code": "sec-audit/", "posted_usd": "195.0", "clearance_status": "cleared", "fiscal_qtr": "Q2"},
        {"tx_hash": "TX-104", "dept_code": " ML-RESEARCH/ ", "posted_usd": "810.0", "clearance_status": "cleared", "fiscal_qtr": "Q2"},
        {"tx_hash": "TX-105", "dept_code": "ml-research", "posted_usd": "ERR", "clearance_status": "cleared", "fiscal_qtr": "Q2"},
        {"tx_hash": "TX-106", "dept_code": "ml-research/", "posted_usd": "290.0", "clearance_status": "Cleared", "fiscal_qtr": "Q2"},
        {"tx_hash": "TX-107", "dept_code": "ml-research", "posted_usd": "900.0", "clearance_status": "rejected", "fiscal_qtr": "Q2"},
    ]


def _sql1_public_rows() -> list[dict[str, Any]]:
    return [
        {"rpc_id": "R-1", "service_route": " /grpc/AuthSvc/ ", "duration_ms": "320.0", "tier_mode": "ACTIVE", "host": "h1"},
        {"rpc_id": "R-2", "service_route": "/grpc/authsvc", "duration_ms": "280.0", "tier_mode": "active", "host": "h2"},
        {"rpc_id": "R-3", "service_route": "/grpc/authsvc/", "duration_ms": "140.0", "tier_mode": "active", "host": "h1"},
        {"rpc_id": "R-4", "service_route": " /grpc/BillSvc/ ", "duration_ms": "510.0", "tier_mode": "Active", "host": "h3"},
        {"rpc_id": "R-5", "service_route": "/grpc/billsvc", "duration_ms": "N/A", "tier_mode": "active", "host": "h3"},
        {"rpc_id": "R-6", "service_route": "/grpc/billsvc/", "duration_ms": "400.0", "tier_mode": "draining", "host": "h3"},
        {"rpc_id": "R-7", "service_route": "/grpc/billsvc", "duration_ms": "270.0", "tier_mode": "active", "host": "h2"},
    ]


def _sql1_private_heldout_rows() -> list[dict[str, Any]]:
    return [
        {"rpc_id": "R-101", "service_route": " /grpc/SearchSvc/ ", "duration_ms": "250.0", "tier_mode": "active", "host": "h1"},
        {"rpc_id": "R-102", "service_route": "/grpc/searchsvc", "duration_ms": "450.0", "tier_mode": "ACTIVE", "host": "h2"},
        {"rpc_id": "R-103", "service_route": "/grpc/searchsvc/", "duration_ms": "245.0", "tier_mode": "active", "host": "h1"},
        {"rpc_id": "R-104", "service_route": " /grpc/IndexSvc/ ", "duration_ms": "620.0", "tier_mode": "active", "host": "h3"},
        {"rpc_id": "R-105", "service_route": "/grpc/indexsvc", "duration_ms": "null", "tier_mode": "active", "host": "h3"},
        {"rpc_id": "R-106", "service_route": "/grpc/indexsvc/", "duration_ms": "380.0", "tier_mode": "Active", "host": "h2"},
        {"rpc_id": "R-107", "service_route": "/grpc/indexsvc", "duration_ms": "700.0", "tier_mode": "standby", "host": "h3"},
    ]


def _sql2_public_rows() -> list[dict[str, Any]]:
    return [
        {"manifest_id": "M-1", "corridor_lane": " EU-ROTTERDAM/ ", "freight_kg": "240.0", "customs_state": "RELEASED", "carrier": "C1"},
        {"manifest_id": "M-2", "corridor_lane": "eu-rotterdam", "freight_kg": "160.0", "customs_state": "released", "carrier": "C1"},
        {"manifest_id": "M-3", "corridor_lane": "eu-rotterdam/", "freight_kg": "75.0", "customs_state": "released", "carrier": "C2"},
        {"manifest_id": "M-4", "corridor_lane": " US-SAVANNAH/ ", "freight_kg": "310.0", "customs_state": "Released", "carrier": "C2"},
        {"manifest_id": "M-5", "corridor_lane": "us-savannah", "freight_kg": "ERR", "customs_state": "released", "carrier": "C2"},
        {"manifest_id": "M-6", "corridor_lane": "us-savannah/", "freight_kg": "420.0", "customs_state": "held", "carrier": "C1"},
        {"manifest_id": "M-7", "corridor_lane": "us-savannah", "freight_kg": "130.0", "customs_state": "released", "carrier": "C1"},
    ]


def _sql2_private_heldout_rows() -> list[dict[str, Any]]:
    return [
        {"manifest_id": "M-101", "corridor_lane": " JP-YOKOHAMA/ ", "freight_kg": "100.0", "customs_state": "released", "carrier": "C1"},
        {"manifest_id": "M-102", "corridor_lane": "jp-yokohama", "freight_kg": "300.0", "customs_state": "RELEASED", "carrier": "C2"},
        {"manifest_id": "M-103", "corridor_lane": "jp-yokohama/", "freight_kg": "98.0", "customs_state": "released", "carrier": "C1"},
        {"manifest_id": "M-104", "corridor_lane": " SG-TUAS/ ", "freight_kg": "520.0", "customs_state": "released", "carrier": "C2"},
        {"manifest_id": "M-105", "corridor_lane": "sg-tuas", "freight_kg": "N/A", "customs_state": "released", "carrier": "C2"},
        {"manifest_id": "M-106", "corridor_lane": "sg-tuas/", "freight_kg": "280.0", "customs_state": "Released", "carrier": "C1"},
        {"manifest_id": "M-107", "corridor_lane": "sg-tuas", "freight_kg": "600.0", "customs_state": "quarantined", "carrier": "C1"},
    ]


def _sql3_public_rows() -> list[dict[str, Any]]:
    return [
        {"batch_id": "B-1", "panel_code": " PANEL-CRP/ ", "concentration_ug": "85.0", "qc_flag": "VERIFIED", "instrument": "I1"},
        {"batch_id": "B-2", "panel_code": "panel-crp", "concentration_ug": "55.0", "qc_flag": "verified", "instrument": "I1"},
        {"batch_id": "B-3", "panel_code": "panel-crp/", "concentration_ug": "25.0", "qc_flag": "verified", "instrument": "I2"},
        {"batch_id": "B-4", "panel_code": " PANEL-TROP/ ", "concentration_ug": "120.0", "qc_flag": "Verified", "instrument": "I2"},
        {"batch_id": "B-5", "panel_code": "panel-trop", "concentration_ug": "NaN", "qc_flag": "verified", "instrument": "I2"},
        {"batch_id": "B-6", "panel_code": "panel-trop/", "concentration_ug": "95.0", "qc_flag": "rejected", "instrument": "I1"},
        {"batch_id": "B-7", "panel_code": "panel-trop", "concentration_ug": "60.0", "qc_flag": "verified", "instrument": "I1"},
    ]


def _sql3_private_heldout_rows() -> list[dict[str, Any]]:
    return [
        {"batch_id": "B-101", "panel_code": " PANEL-FERR/ ", "concentration_ug": "40.0", "qc_flag": "verified", "instrument": "I1"},
        {"batch_id": "B-102", "panel_code": "panel-ferr", "concentration_ug": "110.0", "qc_flag": "VERIFIED", "instrument": "I2"},
        {"batch_id": "B-103", "panel_code": "panel-ferr/", "concentration_ug": "39.0", "qc_flag": "verified", "instrument": "I1"},
        {"batch_id": "B-104", "panel_code": " PANEL-DDIM/ ", "concentration_ug": "175.0", "qc_flag": "verified", "instrument": "I2"},
        {"batch_id": "B-105", "panel_code": "panel-ddim", "concentration_ug": "null", "qc_flag": "verified", "instrument": "I2"},
        {"batch_id": "B-106", "panel_code": "panel-ddim/", "concentration_ug": "65.0", "qc_flag": "Verified", "instrument": "I1"},
        {"batch_id": "B-107", "panel_code": "panel-ddim", "concentration_ug": "210.0", "qc_flag": "contaminated", "instrument": "I1"},
    ]


def _extract_real_stdlib_ast_row(mod_obj: Any, package_group: str, module_tier: str, mod_id: str) -> dict[str, Any]:
    """Parses a real Python standard-library `.py` file on disk and extracts its
    actual AST node count and function count."""
    src_file = Path(mod_obj.__file__)
    tree = ast.parse(src_file.read_text(encoding="utf-8", errors="replace"))
    node_count = sum(1 for _ in ast.walk(tree))
    return {
        "module_id": mod_id,
        "package_group": package_group,
        "ast_node_count": str(float(node_count)),
        "module_tier": module_tier,
        "source_file": src_file.name,
    }


def _repo_ast_public_rows() -> list[dict[str, Any]]:
    import csv as _m_csv
    import heapq as _m_heapq
    import pathlib as _m_pathlib
    import sqlite3.dbapi2 as _m_dbapi2
    import types as _m_types
    return [
        _extract_real_stdlib_ast_row(_m_csv, " STDLIB_DATA/ ", "ACTIVE", "MOD-1"),
        _extract_real_stdlib_ast_row(_m_dbapi2, "stdlib_data", "active", "MOD-2"),
        _extract_real_stdlib_ast_row(_m_pathlib, "stdlib_data/", "active", "MOD-3"),
        _extract_real_stdlib_ast_row(_m_heapq, " STDLIB_CORE/ ", "Active", "MOD-4"),
        _extract_real_stdlib_ast_row(_m_types, "stdlib_core", "active", "MOD-5"),
        {"module_id": "MOD-6", "package_group": "stdlib_core/", "ast_node_count": "N/A", "module_tier": "active", "source_file": "corrupt.py"},
        {"module_id": "MOD-7", "package_group": "stdlib_core", "ast_node_count": "900.0", "module_tier": "deprecated", "source_file": "legacy.py"},
    ]


def _repo_ast_private_heldout_rows() -> list[dict[str, Any]]:
    import difflib as _m_difflib
    import fractions as _m_fractions
    import functools as _m_functools
    import pathlib as _m_pathlib
    import re as _m_re
    import statistics as _m_statistics
    import urllib.parse as _m_uparse
    return [
        _extract_real_stdlib_ast_row(_m_fractions, " STDLIB_MATH/ ", "active", "MOD-101"),
        _extract_real_stdlib_ast_row(_m_statistics, "stdlib_math", "ACTIVE", "MOD-102"),
        _extract_real_stdlib_ast_row(_m_pathlib, "stdlib_math/", "active", "MOD-103"),
        _extract_real_stdlib_ast_row(_m_difflib, " STDLIB_TEXT/ ", "active", "MOD-104"),
        _extract_real_stdlib_ast_row(_m_re, "stdlib_text", "Active", "MOD-105"),
        _extract_real_stdlib_ast_row(_m_uparse, "stdlib_text/", "deprecated", "MOD-106"),
        _extract_real_stdlib_ast_row(_m_functools, " STDLIB_FUNC/ ", "active", "MOD-107"),
    ]


def _amb1_public_rows() -> list[dict[str, Any]]:
    # Contains positive gross revenue (>= 50.0), small fee (20.0), and negative refunds (-45.0, -80.0)
    return [
        {"settlement_id": "EU-1", "merchant_Desk": " RETAIL-BERLIN/ ", "revenue_eur": "140.0", "settlement_state": "SETTLED", "currency": "EUR"},
        {"settlement_id": "EU-2", "merchant_Desk": "retail-berlin", "revenue_eur": "60.0", "settlement_state": "settled", "currency": "EUR"},
        {"settlement_id": "EU-3", "merchant_Desk": "retail-berlin/", "revenue_eur": "-45.0", "settlement_state": "settled", "currency": "EUR"},
        {"settlement_id": "EU-4", "merchant_Desk": " SAAS-PARIS/ ", "revenue_eur": "250.0", "settlement_state": "Settled", "currency": "EUR"},
        {"settlement_id": "EU-5", "merchant_Desk": "saas-paris", "revenue_eur": "-80.0", "settlement_state": "settled", "currency": "EUR"},
        {"settlement_id": "EU-6", "merchant_Desk": "saas-paris/", "revenue_eur": "90.0", "settlement_state": "settled", "currency": "EUR"},
        {"settlement_id": "EU-7", "merchant_Desk": "saas-paris", "revenue_eur": "null", "settlement_state": "settled", "currency": "EUR"},
        {"settlement_id": "EU-8", "merchant_Desk": "saas-paris", "revenue_eur": "180.0", "settlement_state": "chargeback", "currency": "EUR"},
    ]


def _amb1_private_heldout_rows() -> list[dict[str, Any]]:
    return [
        {"settlement_id": "EU-101", "merchant_Desk": " FINTECH-MADRID/ ", "revenue_eur": "50.0", "settlement_state": "settled", "currency": "EUR"},
        {"settlement_id": "EU-102", "merchant_Desk": "fintech-madrid", "revenue_eur": "150.0", "settlement_state": "SETTLED", "currency": "EUR"},
        {"settlement_id": "EU-103", "merchant_Desk": "fintech-madrid/", "revenue_eur": "-65.0", "settlement_state": "settled", "currency": "EUR"},
        {"settlement_id": "EU-104", "merchant_Desk": " LOGISTICS-MILAN/ ", "revenue_eur": "310.0", "settlement_state": "settled", "currency": "EUR"},
        {"settlement_id": "EU-105", "merchant_Desk": "logistics-milan", "revenue_eur": "-120.0", "settlement_state": "settled", "currency": "EUR"},
        {"settlement_id": "EU-106", "merchant_Desk": "logistics-milan/", "revenue_eur": "90.0", "settlement_state": "Settled", "currency": "EUR"},
        {"settlement_id": "EU-107", "merchant_Desk": "logistics-milan", "revenue_eur": "220.0", "settlement_state": "disputed", "currency": "EUR"},
    ]


TASK_PUBLIC_ROWS = {
    "S1_filter_and_normalize_error_logs": _server_logs_public_rows,
    "S2_endpoint_latency_grouped_summary": _server_logs_public_rows,
    "S3_region_incident_rollup": _server_logs_public_rows,
    "D1_clean_completed_orders": _ecommerce_orders_public_rows,
    "D2_sku_revenue_grouped_summary": _ecommerce_orders_public_rows,
    "A1_telemetry_alert_aggregation": _telemetry_public_rows,
    "A2_ledger_department_reconciliation": _ledger_public_rows,
    "SQL1_service_telemetry_db": _sql1_public_rows,
    "SQL2_supply_chain_shipments_db": _sql2_public_rows,
    "SQL3_hospital_lab_results_db": _sql3_public_rows,
    "R1_repo_python_ast_metrics": _repo_ast_public_rows,
    "AMB1_revenue_eur_semantic_disambiguation": _amb1_public_rows,
}

TASK_PRIVATE_HELDOUT_ROWS = {
    "S1_filter_and_normalize_error_logs": _server_logs_private_heldout_rows,
    "S2_endpoint_latency_grouped_summary": _server_logs_private_heldout_rows,
    "S3_region_incident_rollup": _server_logs_private_heldout_rows,
    "D1_clean_completed_orders": _ecommerce_orders_private_heldout_rows,
    "D2_sku_revenue_grouped_summary": _ecommerce_orders_private_heldout_rows,
    "A1_telemetry_alert_aggregation": _telemetry_private_heldout_rows,
    "A2_ledger_department_reconciliation": _ledger_private_heldout_rows,
    "SQL1_service_telemetry_db": _sql1_private_heldout_rows,
    "SQL2_supply_chain_shipments_db": _sql2_private_heldout_rows,
    "SQL3_hospital_lab_results_db": _sql3_private_heldout_rows,
    "R1_repo_python_ast_metrics": _repo_ast_private_heldout_rows,
    "AMB1_revenue_eur_semantic_disambiguation": _amb1_private_heldout_rows,
}


TASK_METADATA = {
    "S1_filter_and_normalize_error_logs": dict(
        tier="source_csv_json",
        format="csv",
        source_filename="server_access_logs.csv",
        output_filename="s1_error_logs_cleaned.json",
        schema_family="server_access_logs",
        candidate_thresholds=[500.0, 501.0, 502.0],
        required_output_columns=["endpoint", "status_code", "latency_ms", "region"],
        task_kind="filter_normalize_order",
    ),
    "S2_endpoint_latency_grouped_summary": dict(
        tier="source_csv_json",
        format="csv",
        source_filename="server_access_logs.csv",
        output_filename="s2_endpoint_latency_summary.json",
        schema_family="server_access_logs",
        candidate_thresholds=[500.0, 501.0, 502.0],
        required_output_columns=["endpoint", "event_count", "total_latency_ms", "mean_latency_ms", "max_latency_ms"],
        task_kind="grouped_summary",
    ),
    "S3_region_incident_rollup": dict(
        tier="source_csv_json",
        format="json",
        source_filename="server_access_logs.json",
        output_filename="s3_region_incident_rollup.csv",
        schema_family="server_access_logs",
        candidate_thresholds=[500.0, 501.0, 502.0],
        required_output_columns=["region", "event_count", "total_latency_ms", "mean_latency_ms", "max_latency_ms"],
        task_kind="grouped_summary",
    ),
    "D1_clean_completed_orders": dict(
        tier="development_csv_json",
        format="json",
        source_filename="ecommerce_orders.json",
        output_filename="d1_completed_orders.json",
        schema_family="ecommerce_orders_and_refunds",
        candidate_thresholds=[50.0, 55.0, 60.0],
        required_output_columns=["sku_code", "amount_usd", "warehouse_zone"],
        task_kind="filter_normalize_order",
    ),
    "D2_sku_revenue_grouped_summary": dict(
        tier="development_csv_json",
        format="csv",
        source_filename="ecommerce_orders.csv",
        output_filename="d2_sku_revenue_summary.csv",
        schema_family="ecommerce_orders_and_refunds",
        candidate_thresholds=[50.0, 55.0, 60.0],
        required_output_columns=["sku_code", "event_count", "total_amount_usd", "mean_amount_usd", "max_amount_usd"],
        task_kind="grouped_summary",
    ),
    "A1_telemetry_alert_aggregation": dict(
        tier="independent_confirmation_csv_json",
        format="csv",
        source_filename="clinical_sensor_telemetry.csv",
        output_filename="a1_telemetry_ward_summary.json",
        schema_family="clinical_sensor_telemetry",
        candidate_thresholds=[120.0, 125.0, 130.0],
        required_output_columns=["ward_id", "event_count", "total_reading_mv", "mean_reading_mv", "max_reading_mv"],
        task_kind="grouped_summary",
    ),
    "A2_ledger_department_reconciliation": dict(
        tier="independent_confirmation_csv_json",
        format="json",
        source_filename="financial_ledger_audit.json",
        output_filename="a2_ledger_dept_summary.json",
        schema_family="financial_ledger_audit",
        candidate_thresholds=[200.0, 210.0, 220.0],
        required_output_columns=["dept_code", "event_count", "total_posted_usd", "mean_posted_usd", "max_posted_usd"],
        task_kind="grouped_summary",
    ),
    "SQL1_service_telemetry_db": dict(
        tier="development_sqlite",
        format="sqlite",
        source_filename="service_telemetry_db.sqlite",
        table_name="cluster_rpc_events",
        output_filename="sql1_service_telemetry_summary.json",
        schema_family="cluster_rpc_events",
        candidate_thresholds=[250.0, 260.0, 270.0],
        required_output_columns=["service_route", "event_count", "total_duration_ms", "mean_duration_ms", "max_duration_ms"],
        task_kind="grouped_summary",
    ),
    "SQL2_supply_chain_shipments_db": dict(
        tier="independent_confirmation_sqlite",
        format="sqlite",
        source_filename="supply_chain_shipments_db.sqlite",
        table_name="freight_manifests",
        output_filename="sql2_supply_chain_summary.json",
        schema_family="freight_manifests",
        candidate_thresholds=[100.0, 115.0, 130.0],
        required_output_columns=["corridor_lane", "event_count", "total_freight_kg", "mean_freight_kg", "max_freight_kg"],
        task_kind="grouped_summary",
    ),
    "SQL3_hospital_lab_results_db": dict(
        tier="independent_confirmation_sqlite",
        format="sqlite",
        source_filename="hospital_lab_results_db.sqlite",
        table_name="assay_batches",
        output_filename="sql3_hospital_lab_summary.json",
        schema_family="assay_batches",
        candidate_thresholds=[40.0, 50.0, 55.0],
        required_output_columns=["panel_code", "event_count", "total_concentration_ug", "mean_concentration_ug", "max_concentration_ug"],
        task_kind="grouped_summary",
    ),
    "R1_repo_python_ast_metrics": dict(
        tier="naturally_occurring_repo_data",
        format="json",
        source_filename="stdlib_python_ast_metrics.json",
        output_filename="r1_stdlib_ast_summary.json",
        schema_family="python_stdlib_ast",
        candidate_thresholds=[150.0, 300.0, 500.0],
        required_output_columns=["package_group", "event_count", "total_ast_node_count", "mean_ast_node_count", "max_ast_node_count"],
        task_kind="grouped_summary",
    ),
    "AMB1_revenue_eur_semantic_disambiguation": dict(
        tier="ambiguous_header_disambiguation",
        format="csv",
        source_filename="european_merchant_settlements.csv",
        output_filename="amb1_revenue_eur_summary.json",
        schema_family="european_merchant_settlements",
        candidate_thresholds=[-100.0, 0.0, 50.0],
        required_output_columns=["merchant_Desk", "event_count", "total_revenue_eur", "mean_revenue_eur", "max_revenue_eur"],
        task_kind="grouped_summary",
    ),
}


def _write_csv_file(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _write_normalized_relational_tables(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    """Writes a normalized 2-table foreign-key schema (`dim_entities` and `fact_events`)
    so relational SQL queries with `JOIN`, `WHERE`, `GROUP BY`, and `ORDER BY` can be
    executed directly inside SQLite."""
    cols = list(rows[0].keys())
    # cols order in SQL1/SQL2/SQL3: [id_col, key_col, metric_col, status_col, aux_col]
    id_col, key_col, metric_col, status_col, aux_col = cols[0], cols[1], cols[2], cols[3], cols[4]
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        f'CREATE TABLE "dim_entities" ('
        f'"entity_id" TEXT PRIMARY KEY, "{key_col}" TEXT, "{status_col}" TEXT)'
    )
    conn.execute(
        f'CREATE TABLE "fact_events" ('
        f'"event_id" TEXT PRIMARY KEY, "entity_fk" TEXT, "{metric_col}" TEXT, "{aux_col}" TEXT, '
        f'FOREIGN KEY("entity_fk") REFERENCES "dim_entities"("entity_id"))'
    )
    for idx, r in enumerate(rows):
        ent_id = f"ENT-{idx + 1}"
        conn.execute(
            f'INSERT INTO "dim_entities" VALUES (?, ?, ?)',
            (ent_id, str(r.get(key_col, "")), str(r.get(status_col, ""))),
        )
        conn.execute(
            f'INSERT INTO "fact_events" VALUES (?, ?, ?, ?)',
            (str(r.get(id_col, f"EV-{idx + 1}")), ent_id, str(r.get(metric_col, "")), str(r.get(aux_col, ""))),
        )


def _write_sqlite_table(db_path: Path, table_name: str, rows: list[dict[str, Any]]) -> None:
    if db_path.exists():
        os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    try:
        cols = list(rows[0].keys())
        col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
        conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')
        placeholders = ", ".join("?" for _ in cols)
        for r in rows:
            conn.execute(
                f'INSERT INTO "{table_name}" VALUES ({placeholders})',
                tuple(str(r.get(c, "")) for c in cols),
            )
        if len(cols) >= 5:
            _write_normalized_relational_tables(conn, rows)
        conn.commit()
    finally:
        conn.close()


def _execute_relational_sql_on_rows(sql_query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Executes `sql_query` inside an isolated in-memory SQLite database containing ONLY
    the normalized relational tables `dim_entities` and `fact_events` (no flat table),
    so only a genuine relational JOIN + GROUP BY query can succeed."""
    conn = sqlite3.connect(":memory:")
    try:
        _write_normalized_relational_tables(conn, rows)
        conn.commit()
        cur = conn.execute(sql_query)
        col_names = [desc[0] for desc in cur.description]
        out: list[dict[str, Any]] = []
        for row in cur.fetchall():
            rec: dict[str, Any] = {}
            for i, col in enumerate(col_names):
                val = row[i]
                if isinstance(val, float):
                    rec[col] = round(val, 2)
                else:
                    rec[col] = val
            out.append(rec)
        return out
    finally:
        conn.close()


def init_task_workspace(payload: dict[str, Any]) -> dict[str, Any]:
    """Creates the read-only source file(s) (`0o444`) in `workspace_dir/read_only_source/`
    and an empty writable `workspace_dir/output/` directory. Returns public demonstration
    input-output pairs and declarative schema requirements (never the winning program or
    private held-out rows)."""
    ws_dir = Path(payload["workspace_dir"])
    task_id = str(payload["task_id"])
    if task_id not in TASK_METADATA:
        raise ValueError(f"unknown_task_id:{task_id}")

    meta = TASK_METADATA[task_id]
    ro_dir = ws_dir / "read_only_source"
    out_dir = ws_dir / "output"
    ro_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    pub_rows = TASK_PUBLIC_ROWS[task_id]()
    ref_fn = REFERENCE_TASK_FUNCTIONS[task_id]
    expected_demo_out = ref_fn(pub_rows)

    src_path = ro_dir / str(meta["source_filename"])
    if src_path.exists():
        os.chmod(src_path, stat.S_IRUSR | stat.S_IWUSR)

    fmt = meta["format"]
    if fmt == "csv":
        _write_csv_file(src_path, pub_rows)
    elif fmt == "json":
        src_path.write_text(json.dumps(pub_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif fmt == "sqlite":
        _write_sqlite_table(src_path, str(meta["table_name"]), pub_rows)
    else:
        raise ValueError(f"unsupported_format:{fmt}")

    # Enforce read-only mode on source file
    os.chmod(src_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    src_sha256 = _sha256_bytes(src_path.read_bytes())

    return dict(
        task_id=task_id,
        tier=meta["tier"],
        format=fmt,
        schema_family=meta["schema_family"],
        read_only_source_path=str(src_path),
        read_only_source_sha256=src_sha256,
        output_dir=str(out_dir),
        output_filename=meta["output_filename"],
        table_name=meta.get("table_name"),
        input_columns=list(pub_rows[0].keys()),
        required_output_columns=list(meta["required_output_columns"]),
        candidate_thresholds=list(meta["candidate_thresholds"]),
        task_kind=meta["task_kind"],
        demonstration_input_rows=pub_rows,
        demonstration_expected_output=expected_demo_out,
        winning_program_supplied=False,
        private_heldout_exposed=False,
    )


def answer_disambiguating_query(payload: dict[str, Any]) -> dict[str, Any]:
    """Executes the ground-truth reference transformation on the learner's synthesized
    disambiguating query rows when `answer_source_available=True`."""
    task_id = str(payload["task_id"])
    if not payload.get("answer_source_available", True):
        return dict(
            task_id=task_id,
            answered=False,
            reason="answer_source_unavailable",
            oracle_output=None,
        )
    query_rows = payload.get("query_rows", [])
    if not isinstance(query_rows, list) or len(query_rows) == 0:
        raise ValueError("empty_or_invalid_query_rows")
    ref_fn = REFERENCE_TASK_FUNCTIONS[task_id]
    ans = ref_fn(query_rows)
    return dict(
        task_id=task_id,
        answered=True,
        oracle_output=ans,
        query_receipt_sha256=_sha256_obj(dict(task_id=task_id, query_rows=query_rows, oracle_output=ans)),
    )


def evaluate_serialized_adapter_program(
    program_ops: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Executes a serialized `TypedDataAdapterProgram` on `rows` inside the isolated
    evaluator process."""
    current_rows = [dict(r) for r in rows]
    grouped: dict[str, list[dict[str, Any]]] | None = None

    for step in program_ops:
        op = str(step["op"])
        if op == "DropMalformedRows":
            req_fields = list(step["required_fields"])
            current_rows = [
                r for r in current_rows
                if all(not _is_missing(r.get(f)) for f in req_fields)
            ]
        elif op == "ParseNumberField":
            f_name = str(step["field"])
            t_name = str(step.get("target_field", f_name))
            n_type = str(step.get("num_type", "float"))
            on_err = str(step.get("on_error", "drop_row"))
            def_val = step.get("default_val", 0.0)
            next_rows: list[dict[str, Any]] = []
            for r in current_rows:
                parsed = _parse_num(r.get(f_name), n_type)
                if parsed is None:
                    if on_err == "drop_row":
                        continue
                    elif on_err == "fill_default":
                        parsed = int(def_val) if n_type == "int" else float(def_val)
                    else:
                        raise ValueError(f"parse_number_error:{f_name}")
                nr = dict(r)
                nr[t_name] = parsed
                next_rows.append(nr)
            current_rows = next_rows
        elif op == "FillMissingField":
            f_name = str(step["field"])
            def_val = step["default_val"]
            for r in current_rows:
                if _is_missing(r.get(f_name)):
                    r[f_name] = def_val
        elif op == "NormalizeTextField":
            f_name = str(step["field"])
            t_name = str(step.get("target_field", f_name))
            norm_ops = list(step.get("ops", ["strip", "lower", "strip_trailing_slash"]))
            next_rows = []
            for r in current_rows:
                val = _norm_text(r.get(f_name), norm_ops)
                if not val and step.get("drop_if_empty", True):
                    continue
                nr = dict(r)
                nr[t_name] = val
                next_rows.append(nr)
            current_rows = next_rows
        elif op == "FilterEquals":
            f_name = str(step["field"])
            target_val = step["value"]
            norm_cmp = bool(step.get("case_insensitive", True))
            if norm_cmp and isinstance(target_val, str):
                t_cmp = target_val.strip().lower()
                current_rows = [
                    r for r in current_rows
                    if _norm_text(r.get(f_name), ("strip", "lower")) == t_cmp
                ]
            else:
                current_rows = [r for r in current_rows if r.get(f_name) == target_val]
        elif op == "FilterNumericThreshold":
            f_name = str(step["field"])
            cmp_op = str(step.get("cmp", "ge"))
            thresh = float(step["threshold"])
            filtered: list[dict[str, Any]] = []
            for r in current_rows:
                v = r.get(f_name)
                if isinstance(v, (int, float)):
                    fv = float(v)
                else:
                    p = _parse_num(v, "float")
                    if p is None:
                        continue
                    fv = float(p)
                if cmp_op == "ge" and fv >= thresh:
                    filtered.append(r)
                elif cmp_op == "gt" and fv > thresh:
                    filtered.append(r)
                elif cmp_op == "le" and fv <= thresh:
                    filtered.append(r)
                elif cmp_op == "lt" and fv < thresh:
                    filtered.append(r)
            current_rows = filtered
        elif op == "ComputeDerivedField":
            t_name = str(step["target_field"])
            lhs_f = str(step["lhs_field"])
            rhs_f = str(step["rhs_field"])
            arith = str(step.get("arith_op", "add"))
            for r in current_rows:
                lv = float(r.get(lhs_f, 0.0))
                rv = float(r.get(rhs_f, 0.0))
                if arith == "add":
                    r[t_name] = round(lv + rv, 2)
                elif arith == "sub":
                    r[t_name] = round(lv - rv, 2)
                elif arith == "mul":
                    r[t_name] = round(lv * rv, 2)
        elif op == "ProjectFields":
            cols = list(step["fields"])
            current_rows = [{c: r.get(c) for c in cols} for r in current_rows]
        elif op == "GroupByField":
            k_field = str(step["key_field"])
            grouped = {}
            for r in current_rows:
                k_val = str(r.get(k_field, ""))
                if not k_val:
                    continue
                grouped.setdefault(k_val, []).append(r)
        elif op == "AggregateGroups":
            if grouped is None:
                k_field = str(step["key_field"])
                grouped = {}
                for r in current_rows:
                    k_val = str(r.get(k_field, ""))
                    if k_val:
                        grouped.setdefault(k_val, []).append(r)
            k_field = str(step["key_field"])
            aggs = list(step["aggregations"])
            agg_rows: list[dict[str, Any]] = []
            for k_val, g_rows in grouped.items():
                out_r: dict[str, Any] = {k_field: k_val}
                for agg_spec in aggs:
                    out_col = str(agg_spec["out_col"])
                    agg_fn = str(agg_spec["agg_fn"])
                    src_col = str(agg_spec.get("src_col", ""))
                    if agg_fn == "count":
                        out_r[out_col] = len(g_rows)
                    else:
                        vals = [float(gr[src_col]) for gr in g_rows if isinstance(gr.get(src_col), (int, float))]
                        if not vals:
                            out_r[out_col] = 0.0
                        elif agg_fn == "sum":
                            out_r[out_col] = round(sum(vals), 2)
                        elif agg_fn == "mean_round2":
                            out_r[out_col] = round(sum(vals) / len(vals), 2)
                        elif agg_fn == "max":
                            out_r[out_col] = round(max(vals), 2)
                        elif agg_fn == "min":
                            out_r[out_col] = round(min(vals), 2)
                agg_rows.append(out_r)
            current_rows = agg_rows
            grouped = None
        elif op == "OrderByFields":
            sort_keys = list(step["keys"])
            for sk in reversed(sort_keys):
                f_name = str(sk["field"])
                direction = str(sk.get("direction", "ASC")).upper()
                current_rows.sort(
                    key=lambda r, fn=f_name: r.get(fn, 0 if direction == "DESC" else ""),
                    reverse=(direction == "DESC"),
                )
        else:
            raise ValueError(f"unknown_adapter_op:{op}")

    return current_rows


def evaluate_task_submission(payload: dict[str, Any]) -> dict[str, Any]:
    """Verifies read-only source integrity, output file creation in `output/`,
    and evaluates the submitted `program_ops` on the private held-out dataset."""
    task_id = str(payload["task_id"])
    ws_dir = Path(payload["workspace_dir"])
    expected_ro_sha = str(payload["expected_read_only_source_sha256"])
    program_ops = list(payload["program_ops"])

    meta = TASK_METADATA[task_id]
    ro_path = ws_dir / "read_only_source" / str(meta["source_filename"])
    out_path = ws_dir / "output" / str(meta["output_filename"])

    actual_ro_sha = _sha256_bytes(ro_path.read_bytes()) if ro_path.exists() else ""
    ro_unmodified = bool(actual_ro_sha == expected_ro_sha)

    output_file_written = out_path.exists() and out_path.stat().st_size > 0

    # Evaluate on public demonstration rows
    pub_rows = TASK_PUBLIC_ROWS[task_id]()
    ref_fn = REFERENCE_TASK_FUNCTIONS[task_id]
    expected_pub = ref_fn(pub_rows)
    pred_pub = evaluate_serialized_adapter_program(program_ops, pub_rows)
    demo_exact_match = bool(pred_pub == expected_pub)

    # Evaluate on PRIVATE held-out assessment dataset
    priv_rows = TASK_PRIVATE_HELDOUT_ROWS[task_id]()
    expected_priv = ref_fn(priv_rows)
    pred_priv = evaluate_serialized_adapter_program(program_ops, priv_rows)

    # Also compute exact uniform expectation across the surviving version space V if provided
    vs_ops_list = payload.get("surviving_version_space_ops")
    if isinstance(vs_ops_list, list) and len(vs_ops_list) > 0:
        vs_hits = sum(
            1 for cand_ops in vs_ops_list
            if evaluate_serialized_adapter_program(cand_ops, priv_rows) == expected_priv
        )
        version_space_expected_accuracy = round(vs_hits / len(vs_ops_list), 6)
    else:
        version_space_expected_accuracy = 1.0 if (pred_priv == expected_priv) else 0.0

    submitted_sql = payload.get("submitted_sql_query")
    relational_sql_exact_match: bool | None = None
    if submitted_sql:
        sql_priv_pred = _execute_relational_sql_on_rows(str(submitted_sql), priv_rows)
        relational_sql_exact_match = bool(sql_priv_pred == expected_priv)
        heldout_exact_match = bool(pred_priv == expected_priv and relational_sql_exact_match)
    else:
        heldout_exact_match = bool(pred_priv == expected_priv)

    if len(expected_priv) == 0:
        row_acc = 1.0 if len(pred_priv) == 0 else 0.0
    else:
        matches = sum(
            1 for idx, exp_r in enumerate(expected_priv)
            if idx < len(pred_priv) and pred_priv[idx] == exp_r
        )
        row_acc = round(matches / max(len(expected_priv), len(pred_priv)), 6)

    schema_ok = bool(
        len(pred_priv) > 0
        and list(pred_priv[0].keys()) == list(meta["required_output_columns"])
    )

    receipt_payload = dict(
        task_id=task_id,
        tier=meta["tier"],
        ro_unmodified=ro_unmodified,
        output_file_written=output_file_written,
        demo_exact_match=demo_exact_match,
        heldout_exact_match=heldout_exact_match,
        version_space_expected_accuracy=version_space_expected_accuracy,
        relational_sql_exact_match=relational_sql_exact_match,
        heldout_row_accuracy=row_acc,
        schema_exact_match=schema_ok,
        program_sha256=_sha256_obj(program_ops),
    )
    return dict(
        **receipt_payload,
        heldout_accuracy=1.0 if (heldout_exact_match and ro_unmodified and output_file_written) else 0.0,
        separate_evaluator_process=True,
        private_heldout_exposed_to_learner=False,
        evaluator_receipt_sha256=_sha256_obj(receipt_payload),
    )


def answer_pidgin_stream_query(payload: dict[str, Any]) -> dict[str, Any]:
    """Answers a teaching query from Pillar 4 for an unknown stream verb (`'debounce'`,
    `'throttle'`) by executing the ground-truth stream semantics inside the isolated
    teacher subprocess."""
    verb = str(payload.get("verb", "")).strip().lower()
    probe_stream = payload.get("probe_stream", [])
    if verb == "debounce":
        out = [
            str(ev[0])
            for idx, ev in enumerate(probe_stream)
            if idx == 0 or not (ev[0] == probe_stream[idx - 1][0] and (int(ev[1]) - int(probe_stream[idx - 1][1])) <= 10)
        ]
    else:
        raise ValueError(f"unknown_pidgin_verb:{verb}")
    return dict(
        verb=verb,
        probe_stream=probe_stream,
        teacher_output=out,
        teacher_subprocess_receipt=_sha256_obj(dict(verb=verb, probe_stream=probe_stream, out=out)),
    )


def main() -> None:
    raw = sys.stdin.read()
    req = json.loads(raw)
    mode = req.get("mode")
    if mode == "init_task_workspace":
        res = init_task_workspace(req)
    elif mode == "answer_disambiguating_query":
        res = answer_disambiguating_query(req)
    elif mode == "evaluate_task_submission":
        res = evaluate_task_submission(req)
    elif mode == "answer_pidgin_stream_query":
        res = answer_pidgin_stream_query(req)
    else:
        raise ValueError(f"unknown_worker_mode:{mode}")
    sys.stdout.write(json.dumps(res, sort_keys=True))


if __name__ == "__main__":
    main()
