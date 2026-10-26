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
