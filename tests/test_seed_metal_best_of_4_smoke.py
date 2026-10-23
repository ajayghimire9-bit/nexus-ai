"""Offline Metal Best-of-4 smoke gates. 0 live model calls."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexus.seed.best_of_n_verify import GPU_REFUSED
from nexus.seed.capability_evidence import digest
from nexus.seed.metal_best_of_4_smoke import (
    LOCAL_RUNTIME_SHA256, code_prompt, code_spec, grant_from_config, load_config,
    replay_code_cell, replay_sentence_cell, run_cells, sentence_prompt, summarize,
)
from nexus.seed.metal_model_runtime import (
    CPU_LEDGER_USED_S, ExplicitMetalGrant, MetalGrantEnforcer, load_metal_ledger,
    local_runtime_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / "configs/seed_metal_best_of_4_smoke.json")
SAFE = (
    '{"body": "return (item[\'yard\'] if \'yard\' in item else \'\').lower() + \'/\' + '
    '(item[\'slip\'] if \'slip\' in item else \'\').lower()"}'
)
FAIL = '{"body": "return item[\'yard\'].lower() + \'/\' + item[\'slip\'].lower()"}'
SENT_FAIL = "Metalvault."
SENT_PASS = "Metalvault keeps each verified sentence in the knowledge vault in 2026 [seed-metal-1]."


def test_locked_prompt_has_no_planted_get_and_disjoint_cases():
    rendered, _plan = code_prompt(CONFIG)
    assert ".get" not in rendered
    assert ".get" not in sentence_prompt(CONFIG)
    spec = code_spec(CONFIG)
    public = {json.dumps(row["input"], sort_keys=True) for row in spec["public"]}
    private = {json.dumps(row["input"], sort_keys=True) for row in spec["private"]}
    assert public.isdisjoint(private)
    assert local_runtime_sha256() == LOCAL_RUNTIME_SHA256
    assert CONFIG["cpu_ledger_used_s"] == CPU_LEDGER_USED_S
    assert CONFIG["cpu_ledger_debit_s"] == 0


def test_unauthorized_grant_still_refuses(tmp_path: Path):
    with pytest.raises(ValueError, match=GPU_REFUSED):
        MetalGrantEnforcer(ExplicitMetalGrant(authorized=False, ledger_path=str(tmp_path / "x.json")))


def test_offline_cells_promote_and_export(tmp_path: Path):
    grant = grant_from_config(CONFIG, ledger_path=str(tmp_path / "metal_ledger.json"))
    enforcer = MetalGrantEnforcer(
        grant, hardware_probe=lambda: True, rss_reader=lambda: 256.0,
    )
    code_bodies = [FAIL, SAFE, FAIL, FAIL]
    sentences = [SENT_FAIL, SENT_PASS, "Created 99 metalvault.", "Metalvault is unused."]

    def code_sampler(prompt, plan):
        del prompt
        return code_bodies[plan.index]

    def sentence_sampler(prompt, plan):
        del prompt
        return sentences[plan.index]

    records = run_cells(
        CONFIG, tmp_path, grant=grant,
        code_sampler=code_sampler, sentence_sampler=sentence_sampler, enforcer=enforcer,
    )
    ledger = load_metal_ledger(tmp_path / "metal_ledger.json", grant.max_session_metal_seconds)
    summary = summarize(records, CONFIG, ledger)
    assert summary["cell1_promoted_index"] == 1
    assert summary["cell1_private_3_of_3"] is True
    assert summary["cell2_promoted_index"] == 1
    assert summary["sleep_rows"] == 1
    assert summary["cpu_ledger_used_s"] == CPU_LEDGER_USED_S
    assert ledger["kind"] == "metal_session_ledger"
    assert abs(float(ledger["used_s"]) - CPU_LEDGER_USED_S) > 1
    replay = replay_code_cell(CONFIG, records[0]["candidates"])
    assert replay.selected is not None and replay.selected.index == 1
    replay_s = replay_sentence_cell(CONFIG, records[1]["candidates"], tmp_path / "replay")
    assert replay_s.selected is not None and replay_s.selected.index == 1


def test_config_hash_is_stable():
    again = load_config(ROOT / "configs/seed_metal_best_of_4_smoke.json")
    assert digest(CONFIG) == digest(again)
