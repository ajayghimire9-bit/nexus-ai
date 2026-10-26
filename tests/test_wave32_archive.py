"""Wave 32 genome scope: mutations stay inside the editable scope; frozen keys cannot be set."""
import random

import pytest

from nexus import wave32_archive as A


def test_gen0_valid_and_mutations_stay_in_scope():
    rng = random.Random(0)
    g = A.validate(dict(A.GEN0))
    for _ in range(200):
        g = A.mutate(g, rng)
        assert set(g) == set(A.GENES) and all(g[k] in A.GENES[k] for k in g)


@pytest.mark.parametrize("bad", [{"matched_depth": 2}, {"lemmas": "unsound"}, {"checker": "v1"}])
def test_frozen_or_unknown_genes_rejected(bad):
    with pytest.raises(ValueError):
        A.validate(dict(A.GEN0, **bad))


def test_v3b_genome_scope_and_gen0_is_always_on():
    rng = random.Random(1)
    g = A.validate(dict(A.GEN0_V3B))
    assert g["online"] and g["gate_repeat"] == 0.0 and g["warmup"] == 1 and g["rebuild_on"] == "every"
    for _ in range(200):
        g = A.mutate(g, rng)
        assert set(g) == set(A.GENES_V3B)
    with pytest.raises(ValueError):
        A.validate(dict(A.GEN0_V3B, checker=2))


def test_online_gates_are_solver_side():
    from nexus import wave31_solver as S
    from nexus import wave31_tasks as T
    progs = [T.teacher("records", c) for c in T.S3_CORES[:3]]
    gate = dict(A.GEN0_V3B, gate_repeat=0.3, warmup=1)
    S.online_reset()
    outs = [S.online_update(p, gate) for p in progs]           # three distinct cores: repeat rate 0 -> no rebuild
    assert not any(o["rebuilt"] for o in outs) and S.ONLINE["library"] == []
    S.online_reset()
    outs = [S.online_update(p, dict(A.GEN0_V3B)) for p in progs + progs[:1]]
    assert all(o["rebuilt"] for o in outs)
    S.online_reset()
    assert not S.online_update(progs[0], dict(A.GEN0_V3B, online=False))["rebuilt"]
