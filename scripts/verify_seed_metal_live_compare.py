"""Replay the frozen Metal comparison and reject tampers."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.constrained_edit import plan_constrained_edit
from nexus.seed.lexicon_vault import KnowledgeVault, LexicalCapsuleStore
from nexus.seed.metal_live_compare import code_spec, load_config
from nexus.seed.metal_model_runtime import CPU_LEDGER_USED_S, local_runtime_sha256
from nexus.seed.metal_best_of_4_smoke import LOCAL_RUNTIME_SHA256
from nexus.seed.best_of_n_verify import score_code_candidates, score_sentence_candidates


def verify(payload: dict, config: dict, directory: Path, *, check_tampers: bool = True) -> dict:
    if payload.get("config_hash") != digest(config):
        raise ValueError("config_hash")
    if payload["summary"]["cpu_ledger_used_s"] != CPU_LEDGER_USED_S:
        raise ValueError("cpu_ledger_touched")
    if payload["summary"]["cpu_ledger_debit_s"] != 0:
        raise ValueError("cpu_ledger_debit")
    if local_runtime_sha256() != LOCAL_RUNTIME_SHA256:
        raise ValueError("local_model_runtime_changed")
    if not payload["summary"].get("stubbed_call2_vs_call4_is_not_live_advantage"):
        raise ValueError("stub_claimed_as_live")
    if payload["summary"].get("live_advantage_claimed"):
        raise ValueError("live_advantage_claimed")
    cost = payload["summary"].get("assistant_cost") or {}
    if "user_total_s" not in cost or "grant_charged_s" not in cost:
        raise ValueError("assistant_cost_missing")
    ledger = payload.get("metal_ledger") or {}
    if ledger.get("kind") != "metal_session_ledger":
        raise ValueError("metal_ledger_kind")
    records = list(payload.get("records") or [])
    if payload.get("blocked_step") in (None, "") and records:
        spec = code_spec(config)
        plan = plan_constrained_edit(spec["request"], spec["files"], spec["public"])
        vault = KnowledgeVault(directory / "replay_vault.sqlite")
        store = LexicalCapsuleStore(directory / "replay_capsules.sqlite")
        cell = config["sentence"]
        vault.ingest_document(cell["doc_id"], cell["title"], cell["fact"])
        capsule = store.ingest_new_term(
            cell["term"], cell["definition"], cell["pos_or_frame"],
            required_tokens=cell["required_tokens"],
        )
        facts = vault.retrieve_grounded_facts(cell["retrieve_query"])
        for row in records:
            if row["n_calls"] > config["k"]:
                raise ValueError("budget_exceeded:" + row["kind"])
            if ".get" in row.get("prompt", ""):
                raise ValueError("planted_get")
            if row["kind"].startswith("code_"):
                replay = score_code_candidates(row["candidates"], spec, plan)
                idx = None if replay.selected is None else replay.selected.index
                if idx != row.get("selected_index"):
                    raise ValueError("code_replay_mismatch:" + row["kind"])
                if bool(replay.selected and replay.selected.public_passed) != bool(row.get("public_passed")):
                    raise ValueError("code_success_mismatch:" + row["kind"])
            else:
                replay = score_sentence_candidates(
                    row["candidates"], targeted_capsule=capsule, retrieved_facts=facts, vault=vault,
                )
                idx = None if replay.selected is None else replay.selected.index
                if idx != row.get("selected_index"):
                    raise ValueError("sentence_replay_mismatch:" + row["kind"])
        vault.close()
        store.close()
    tampers = _tampers(payload, config, directory) if records and check_tampers else {}
    return dict(
        valid=True,
        cpu_ledger_used_s=CPU_LEDGER_USED_S,
        grant_charged_s=cost.get("grant_charged_s"),
        user_total_s=cost.get("user_total_s"),
        stubbed_call2_vs_call4_is_not_live_advantage=True,
        tampers=tampers,
        learning_to_learn=False,
    )


def _tampers(payload, config, directory):
    out = {}
    mutated = deepcopy(payload)
    mutated["summary"]["live_advantage_claimed"] = True
    try:
        verify(mutated, config, directory, check_tampers=False)
        out["advantage_tamper_rejected"] = False
    except ValueError:
        out["advantage_tamper_rejected"] = True
    return out


def main(directory: Path) -> dict:
    config = load_config(ROOT / "configs/seed_metal_live_compare.json")
    payload = json.loads((directory / "seed_metal_live_compare.json").read_text(encoding="utf-8"))
    report = verify(payload, config, directory)
    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts" / "seed_metal_live_compare"
    main(target)
