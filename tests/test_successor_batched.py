"""Batched successor adapter tests: toy parity, reuse, provenance guards."""
import json
from pathlib import Path

import numpy as np
import pytest

from nexus.world import bellman_backup_control, successor_batched
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences


class Toy:
    batch_independent = True

    def __init__(self, dim=3):
        self.dim = dim
        self.calls = []

    def step(self, obs, actions):
        obs = np.asarray(obs, dtype=np.float32).reshape(-1, self.dim)
        actions = np.asarray(actions)
        self.calls.append((obs.copy(), actions.copy()))
        nxt = obs.copy()
        nxt[:, -1] += (actions.astype(np.float32) - 1) * np.float32(.025)
        nxt[:, 0] += nxt[:, -1] * np.float32(.01)
        return nxt, .03 + .04 * actions


@pytest.mark.parametrize("seed", [0, 27, 91])
def test_batched_twin_matches_the_serial_lookahead_bitwise_on_toy(seed):
    seq = candidate_sequences(seed, 16, 16, 3)
    obs = np.linspace(-.2, .3, 3, dtype=np.float32)
    serial, batched = Toy(), Toy()
    expected = bellman_backup_control.lookahead_first_action(serial, obs, seq)
    action, q, pred = successor_batched.lookahead_first_action(batched, obs, seq)
    assert action == expected[0] == int(np.argmax(expected[1]))
    assert q == [float(v) for v in expected[1]]
    assert np.array_equal(pred, expected[2])
    assert len(serial.calls) == 51 and len(batched.calls) == 17
    assert sum(len(a) for _, a in serial.calls) == \
        sum(len(a) for _, a in batched.calls) == 771


def test_prepared_candidate_table_is_reusable_and_not_mutated():
    seq = candidate_sequences(5, 16, 16, 3)
    prepared = successor_batched.prepare(seq)
    first = successor_batched.lookahead_first_action(Toy(), np.zeros(3, np.float32), prepared)
    second = successor_batched.lookahead_first_action(Toy(), np.ones(3, np.float32) * .2, prepared)
    assert np.array_equal(prepared.sequences, seq)
    assert first[0] in (0, 1, 2) and second[0] in (0, 1, 2)


def test_unsupported_and_malformed_inputs_fail_closed():
    seq = candidate_sequences(0, 16, 16, 3)
    obs = np.zeros(3, np.float32)

    class Stateful:
        def step(self, obs, actions):
            raise AssertionError("must not be called")

    with pytest.raises(TypeError):
        successor_batched.lookahead_first_action(Stateful(), obs, seq)
    with pytest.raises(ValueError):
        successor_batched.lookahead_first_action(Toy(), obs, np.zeros((8, 16), dtype=np.int64))
    with pytest.raises(ValueError):
        successor_batched.lookahead_first_action(Toy(), np.zeros(4, np.float32), seq)


@pytest.mark.parametrize("artifact", ["artifacts/successor_archived_parity.json",
                                      "artifacts/cline_successor_episode_parity.json"])
def test_recorded_parity_provenance_still_binds_the_historical_hot_path(artifact):
    recorded = json.loads(Path(artifact).read_text())["code_hashes"]
    for file in ("src/nexus/world/bellman_backup_control.py",
                 "src/nexus/world/successor_search.py"):
        assert sha(file) == recorded[file], (artifact, file)
