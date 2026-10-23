"""Reconstruct the Metal Best-of-4 smoke and reject tampers."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.metal_best_of_4_smoke import (
    LOCAL_RUNTIME_SHA256, replay_code_cell, replay_sentence_cell,
)
from nexus.seed.metal_model_runtime import CPU_LEDGER_USED_S, local_runtime_sha256
def verify(payload: dict, config: dict, directory: Path | None = None, *, check_tampers: bool = True) -> dict:
    if payload.get("config_hash") != digest(config):
        raise ValueError("config_hash")
    if config.get("cpu_ledger_used_s") != CPU_LEDGER_USED_S:
        raise ValueError("cpu_ledger_constant")
    if payload["summary"]["cpu_ledger_used_s"] != CPU_LEDGER_USED_S:
        raise ValueError("cpu_ledger_touched")
    if payload["summary"]["cpu_ledger_debit_s"] != 0:
        raise ValueError("cpu_ledger_debit")
    if local_runtime_sha256() != LOCAL_RUNTIME_SHA256:
        raise ValueError("local_model_runtime_changed")
    if not payload["summary"].get("local_model_runtime_unchanged"):
        raise ValueError("local_model_runtime_flag")
    ledger = payload.get("metal_ledger") or {}
    if ledger.get("kind") != "metal_session_ledger":
        raise ValueError("metal_ledger_kind")
    if abs(float(ledger.get("used_s") or 0.0) - CPU_LEDGER_USED_S) < 1e-6:
        raise ValueError("metal_ledger_mixed_cpu")
    peak = ledger.get("peak_rss_mib")
    if peak is not None and float(peak) > config["metal_grant"]["max_rss_mib"]:
        raise ValueError("metal_rss_over_cap")
    records = list(payload.get("records") or [])
    if payload.get("blocked_step") in (None, "") and records:
        code = next(row for row in records if row["kind"] == "cell1_code")
        sentence = next(row for row in records if row["kind"] == "cell2_sentence")
        if ".get" in code["prompt"] or ".get" in sentence["prompt"]:
            raise ValueError("planted_get")
        if len(code["candidates"]) != 4 or len(sentence["candidates"]) != 4:
            raise ValueError("candidate_width")
        replay_code = replay_code_cell(config, code["candidates"])
        replay_sent = replay_sentence_cell(config, sentence["candidates"], directory or Path("."))
        code_idx = None if replay_code.selected is None else replay_code.selected.index
        sent_idx = None if replay_sent.selected is None else replay_sent.selected.index
        if code_idx != payload["summary"]["cell1_promoted_index"]:
            raise ValueError("cell1_replay_mismatch")
        if sent_idx != payload["summary"]["cell2_promoted_index"]:
            raise ValueError("cell2_replay_mismatch")
        if sentence.get("sleep_rows"):
            if replay_sent.selected is None:
                raise ValueError("sleep_without_winner")
    tampers = _tamper_self_tests(payload, config, directory or Path(".")) if check_tampers else {}
    return dict(
        valid=True,
        cpu_ledger_used_s=CPU_LEDGER_USED_S,
        cpu_ledger_debit_s=0,
        metal_used_s=ledger.get("used_s"),
        metal_peak_rss_mib=peak,
        cell1_promoted_index=payload["summary"].get("cell1_promoted_index"),
        cell2_promoted_index=payload["summary"].get("cell2_promoted_index"),
        tampers=tampers,
        learning_to_learn=False,
    )


def _tamper_self_tests(payload: dict, config: dict, directory: Path) -> dict:
    tampers = {}
    if not payload.get("records"):
        return {"no_records_to_tamper": True}
    mutated = deepcopy(payload)
    mutated["summary"]["cpu_ledger_used_s"] = 3564.568 + 1
    try:
        verify(mutated, config, directory, check_tampers=False)
        tampers["cpu_ledger_tamper_rejected"] = False
    except ValueError:
        tampers["cpu_ledger_tamper_rejected"] = True
    mutated = deepcopy(payload)
    mutated["summary"]["cell1_promoted_index"] = 99
    try:
        verify(mutated, config, directory, check_tampers=False)
        tampers["promotion_tamper_rejected"] = False
    except ValueError:
        tampers["promotion_tamper_rejected"] = True
    return tampers


def main(directory: Path) -> dict:
    config = json.loads((ROOT / "configs/seed_metal_best_of_4_smoke.json").read_text(encoding="utf-8"))
    payload = json.loads((directory / "seed_metal_best_of_4_smoke.json").read_text(encoding="utf-8"))
    report = verify(payload, config, directory)
    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts" / "seed_metal_best_of_4_smoke"
    main(target)
