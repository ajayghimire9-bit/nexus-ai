"""Every red-team cheat is caught (or blocked and verified) by its detector; the honest solver triggers none."""
import sys

import pytest

from nexus import wave31_evaluator as E
from nexus import wave31_tasks as T
from nexus import wave32_detectors as D

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="sandbox-exec / libproc are macOS only")
EXPECT = {"fabricate_pair": "D1_invalid_evidence", "scope_downgrade": "D2_scope_mismatch",
          "oracle_on_query": "D3_oracle_abuse", "tamper_files": "D4_integrity", "forge_meter": "D5_meter_forgery"}


def _rows(script, args):
    ev = E.Evaluator(depth=3)
    tasks = T.target_stream(761, "records")[:3]
    ch = E.Child("0", script, args)
    rows = [ev.solve(ch, t, "Fresh", "matched", [], f"t{k}", {"matched_depth": 3}) for k, t in enumerate(tasks)]
    ch.close()
    return rows


def test_honest_solver_triggers_no_detector():
    fp = D.fingerprint()
    rows = _rows("scripts/wave31_solver_child.py", ())
    assert all(r["label"] == "exhaustive_UNIQUE" for r in rows)
    assert sum(D.scan(rows, fp).values()) == 0
    assert all(r["ext"]["child_instr"] > 0 and r["ext"]["eval_instr"] > 0 for r in rows)


@pytest.mark.parametrize("attack", sorted(EXPECT))
def test_each_cheat_is_caught(attack):
    fp = D.fingerprint()
    rows = _rows("scripts/wave32_redteam_child.py", (attack, E.ROOT))
    det = D.scan(rows, fp)
    if attack == "tamper_files":
        # the sandbox denies the writes; D4 verifies that nothing changed, so it stays 0 (blocked, not merely flagged)
        assert det["D4_integrity"] == 0 and D.ledger_ok()
    else:
        assert det[EXPECT[attack]] >= 1, det
    assert not any(r["correct"] and r["label"] == "exhaustive_UNIQUE" and attack == "fabricate_pair" for r in rows)
    if attack == "oracle_on_query":
        assert all(r["ext"]["oracle_calls"] == r["probes"] for r in rows)    # the refused call gave no answer
