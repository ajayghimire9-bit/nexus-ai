"""Offline Best-of-N sandbox selection and sleep-export gates. 0 model calls."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexus.seed.best_of_n_verify import (
    GPU_REFUSED, metal_sampler_status, sample_metal_candidates,
    score_code_candidates, score_sentence_candidates,
)
from nexus.seed.constrained_edit import plan_constrained_edit
from nexus.seed.lexicon_vault import KnowledgeVault, LexicalCapsuleStore
from nexus.seed.metal_model_runtime import (
    ExplicitMetalGrant, MetalGrantEnforcer, metal_candidate_schedule,
    write_metal_ledger,
)
from nexus.seed.sleep_consolidation import (
    collect_sleep_triples, metal_lora_status, run_metal_lora, write_sleep_jsonl,
)


SPEC = {
    "id": "py_path_slash_mock",
    "language": "python",
    "request": "Create function tag(item) that returns lane and bay in lowercase joined by one slash.",
    "files": {"lane.py": "def echo(text):\n    return text\n"},
    "public": [
        {"entry": "lane.tag", "input": {"lane": "Lab", "bay": "East"}, "expected": "lab/east"},
        {"entry": "lane.tag", "input": {"bay": "East"}, "expected": "/east"},
        {"entry": "lane.tag", "input": {"lane": "Lab"}, "expected": "lab/"},
    ],
}
SAFE = (
    "return (item['lane'] if 'lane' in item else '').lower() + '/' + "
    "(item['bay'] if 'bay' in item else '').lower()"
)
FAIL_FSTR = "return f\"{item['lane'].lower()}/{item['bay'].lower()}\""
FAIL_SET = "return {item['zone'].lower()}/{item['path'].lower()}"
FAIL_LITERAL = "return '/lab/'"


def _plan():
    return plan_constrained_edit(SPEC["request"], SPEC["files"], SPEC["public"])


def test_best_of_4_picks_first_public_pass():
    result = score_code_candidates(
        [
            json.dumps({"body": FAIL_FSTR}),
            json.dumps({"body": FAIL_SET}),
            json.dumps({"body": FAIL_LITERAL}),
            json.dumps({"body": SAFE}),
        ],
        SPEC,
        _plan(),
    )
    assert result.backend == "cpu_sandbox"
    assert result.learning_to_learn is False
    assert result.first_turn_public_all_passed is True
    assert result.selected is not None
    assert result.selected.index == 3
    assert result.selected.public_pass_count == 3
    assert result.selected.public_n == 3
    assert [row.public_passed for row in result.scores] == [False, False, False, True]


def test_best_of_4_reports_no_pass_without_planting():
    result = score_code_candidates(
        [
            json.dumps({"body": FAIL_FSTR}),
            json.dumps({"body": FAIL_SET}),
            json.dumps({"body": FAIL_LITERAL}),
            json.dumps({"body": "return item['lane']"}),
        ],
        SPEC,
        _plan(),
    )
    assert result.selected is None
    assert result.first_turn_public_all_passed is False


def test_sentence_best_of_n_uses_lexicon_verifier(tmp_path: Path):
    vault = KnowledgeVault(tmp_path / "vault.sqlite")
    store = LexicalCapsuleStore(tmp_path / "capsules.sqlite")
    vault.ingest_document(
        "seed-photo-1",
        "Seed note",
        "In 2026 photophosphorylation yields ATP inside the Seed lab.",
    )
    capsule = store.ingest_new_term(
        "photophosphorylation",
        "the light-driven synthesis of ATP",
        "noun_phrase",
        required_tokens=("atp",),
    )
    facts = vault.retrieve_grounded_facts("photophosphorylation ATP")
    result = score_sentence_candidates(
        [
            "Photophosphorylation.",
            "Photophosphorylation created 99 ATP in 1899.",
            "Photophosphorylation yields ATP inside the Seed lab in 2026 [seed-photo-1].",
        ],
        targeted_capsule=capsule,
        retrieved_facts=facts,
    )
    assert result.selected is not None
    assert result.selected.index == 2
    assert result.selected.sentence_passed is True
    vault.close()
    store.close()


def test_metal_sampler_and_lora_are_refused():
    status = metal_sampler_status()
    assert status["available"] is False
    assert status["reason"] == GPU_REFUSED
    assert status["pinned_runtime_temperature"] == 0
    with pytest.raises(ValueError, match=GPU_REFUSED):
        sample_metal_candidates("unused")
    lora = metal_lora_status()
    assert lora["available"] is False
    assert lora["learning_to_learn"] is False
    with pytest.raises(ValueError, match=GPU_REFUSED):
        run_metal_lora("unused.jsonl", output_dir="unused")


def test_sleep_export_keeps_only_verified_episodes(tmp_path: Path):
    triples = collect_sleep_triples(
        coding_episodes=[
            {"public_passed": True, "prompt": "tag(item)", "body": SAFE, "public": SPEC["public"]},
            {"public_passed": False, "prompt": "bad", "body": FAIL_LITERAL},
        ],
        lexicon_episodes=[
            {
                "passed": True,
                "prompt": "Explain the term.",
                "grounded_context": "In 2026 photophosphorylation yields ATP.",
                "verified_response": "Photophosphorylation yields ATP in 2026 [seed-photo-1].",
            },
        ],
    )
    path = tmp_path / "sleep.jsonl"
    written = write_sleep_jsonl(path, triples)
    assert written == 2
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert all(set(row) == {"prompt", "grounded_context", "verified_response"} for row in rows)
    assert SAFE in rows[0]["verified_response"]


def _authorized_grant(tmp_path: Path, **overrides) -> ExplicitMetalGrant:
    values = dict(
        authorized=True,
        owner="standing-test",
        reason="offline metal enforcement",
        ledger_path=str(tmp_path / "metal_ledger.json"),
        seed=100,
    )
    values.update(overrides)
    return ExplicitMetalGrant(**values)


def _enforcer(tmp_path: Path, grant=None, rss=128.0, clock=None) -> MetalGrantEnforcer:
    grant = grant or _authorized_grant(tmp_path)
    ticks = iter((0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07))
    return MetalGrantEnforcer(
        grant,
        hardware_probe=lambda: True,
        rss_reader=lambda: rss,
        clock=clock or (lambda: next(ticks)),
    )


def test_metal_grant_refused_without_explicit_authorization():
    assert ExplicitMetalGrant().authorized is False
    assert ExplicitMetalGrant.from_config({}, env={}).authorized is False
    with pytest.raises(ValueError, match=GPU_REFUSED):
        MetalGrantEnforcer(ExplicitMetalGrant(), hardware_probe=lambda: True)
    with pytest.raises(ValueError, match=GPU_REFUSED):
        sample_metal_candidates("unused", grant=ExplicitMetalGrant(authorized=False))


def test_metal_candidate_schedule_is_diverse_and_deterministic():
    plans = metal_candidate_schedule(4, 100)
    assert [row.temperature for row in plans] == [0.0, 0.35, 0.35, 0.35]
    assert [row.seed for row in plans] == [100, 101, 102, 103]
    assert all(row.n_gpu_layers == -1 for row in plans)


def test_metal_enforcer_aborts_on_rss_wall_and_session_caps(tmp_path: Path):
    rss_grant = _authorized_grant(tmp_path / "rss")
    with pytest.raises(ValueError, match="metal_rss_exceeded"):
        MetalGrantEnforcer(
            rss_grant,
            hardware_probe=lambda: True,
            rss_reader=lambda: 4097.0,
            clock=lambda: 0.0,
        ).guarded_call(lambda: "unused")

    wall_ticks = iter((0.0, 31.0))
    wall_grant = _authorized_grant(tmp_path / "wall")
    with pytest.raises(ValueError, match="metal_call_wall_exceeded"):
        MetalGrantEnforcer(
            wall_grant,
            hardware_probe=lambda: True,
            rss_reader=lambda: 128.0,
            clock=lambda: next(wall_ticks),
        ).guarded_call(lambda: "slow")

    session_grant = _authorized_grant(tmp_path / "session")
    write_metal_ledger(
        tmp_path / "session" / "metal_ledger.json",
        {
            "kind": "metal_session_ledger",
            "used_s": 600.0,
            "max_session_metal_seconds": 600.0,
            "cpu_ledger_forbidden": True,
            "calls": [],
        },
    )
    with pytest.raises(ValueError, match="metal_session_budget_exceeded"):
        MetalGrantEnforcer(
            session_grant,
            hardware_probe=lambda: True,
            rss_reader=lambda: 128.0,
            clock=lambda: 0.0,
        ).guarded_call(lambda: "unused")


def test_metal_ledger_refuses_frozen_cpu_mix(tmp_path: Path):
    from nexus.seed.metal_model_runtime import load_metal_ledger

    with pytest.raises(ValueError, match="metal_ledger_must_not_mix_cpu"):
        write_metal_ledger(
            tmp_path / "metal_ledger.json",
            {"kind": "cpu_session_ledger", "used_s": 3564.568},
        )
    cpu_path = tmp_path / "cpu.json"
    cpu_path.write_text('{"kind": "cpu_session_ledger", "used_s": 10.0}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="metal_ledger_must_not_mix_cpu"):
        load_metal_ledger(cpu_path, 600.0)


def test_sample_metal_candidates_uses_per_candidate_seed_and_temperature(tmp_path: Path):
    seen = []

    def sampler(prompt, plan):
        seen.append((prompt, plan.temperature, plan.seed, plan.n_gpu_layers))
        return f"cand-{plan.index}"

    texts = sample_metal_candidates(
        "prompt-a",
        n=4,
        grant=_authorized_grant(tmp_path),
        sampler=sampler,
        enforcer=_enforcer(tmp_path),
    )
    assert texts == ["cand-0", "cand-1", "cand-2", "cand-3"]
    assert [row[1] for row in seen] == [0.0, 0.35, 0.35, 0.35]
    assert [row[2] for row in seen] == [100, 101, 102, 103]
    assert all(row[3] == -1 for row in seen)


def test_score_code_candidates_promotes_first_passer_after_keyerror(tmp_path: Path):
    bodies = [
        json.dumps({"body": FAIL_FSTR}),
        json.dumps({"body": SAFE}),
        json.dumps({"body": FAIL_SET}),
        json.dumps({"body": FAIL_LITERAL}),
    ]

    def sampler(prompt, plan):
        del prompt
        return bodies[plan.index]

    result = score_code_candidates(
        None,
        SPEC,
        _plan(),
        prompt="tag(item)",
        metal_grant=_authorized_grant(tmp_path),
        metal_sampler=sampler,
        metal_enforcer=_enforcer(tmp_path),
    )
    assert result.selected is not None
    assert result.selected.index == 1
    assert result.selected.public_passed is True
    assert result.scores[0].public_passed is False


def test_score_sentence_candidates_promotes_first_grounded_metal_draft(tmp_path: Path):
    vault = KnowledgeVault(tmp_path / "vault.sqlite")
    store = LexicalCapsuleStore(tmp_path / "capsules.sqlite")
    vault.ingest_document(
        "seed-photo-1",
        "Seed note",
        "In 2026 photophosphorylation yields ATP inside the Seed lab.",
    )
    capsule = store.ingest_new_term(
        "photophosphorylation",
        "the light-driven synthesis of ATP",
        "noun_phrase",
        required_tokens=("atp",),
    )
    facts = vault.retrieve_grounded_facts("photophosphorylation ATP")
    drafts = [
        "Photophosphorylation yields ATP in 2026.",
        "Photophosphorylation yields ATP inside the Seed lab in 2026 [seed-photo-1].",
        "Photophosphorylation created 99 ATP.",
        "Photophosphorylation.",
    ]

    def sampler(prompt, plan):
        del prompt
        return drafts[plan.index]

    result = score_sentence_candidates(
        prompt="Explain the term.",
        targeted_capsule=capsule,
        retrieved_facts=facts,
        metal_grant=_authorized_grant(tmp_path),
        metal_sampler=sampler,
        metal_enforcer=_enforcer(tmp_path),
    )
    assert result.selected is not None
    assert result.selected.index == 1
    assert result.selected.sentence_passed is True
    vault.close()
    store.close()


def test_authorized_metal_lora_stays_inside_enforcer(tmp_path: Path):
    recorded = {}

    def trainer(*, dataset_path, output_dir, steps):
        recorded["dataset_path"] = dataset_path
        recorded["output_dir"] = output_dir
        recorded["steps"] = steps
        return dict(ok=True, steps=steps, learning_to_learn=False)

    out = run_metal_lora(
        tmp_path / "sleep.jsonl",
        output_dir=tmp_path / "lora",
        steps=8,
        grant=_authorized_grant(tmp_path),
        trainer=trainer,
        enforcer=_enforcer(tmp_path),
    )
    assert out["ok"] is True
    assert recorded["steps"] == 8
    assert out["learning_to_learn"] is False
