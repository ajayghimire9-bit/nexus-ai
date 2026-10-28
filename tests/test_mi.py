"""mi unit tests (fast; no discovery, no evaluation data)."""
import random

from nexus import mi_learner as ML
from nexus import mi_lpl as LP
from nexus import mi_ocean as M
from nexus import t7_repair as TR


def test_seed_procedure_reproduces_the_existing_hypothesis_space():
    d, _ = LP.hypothesis_space(LP.SEED_BASELINE, {})
    assert [LP._sig(n) for n in d] == [LP._sig(n) for n in TR.GRAMMAR5]


def test_generated_programs_always_execute_within_caps():
    rnd = random.Random(3)
    for k in range(60):
        p = LP.random_program(rnd)
        for _ in range(rnd.randint(0, 20)):
            p, _ = rnd.choice([lambda: LP.mutate(p, rnd), lambda: LP.crossover(p, LP.SEED_BASELINE, rnd)])()
        d, st = LP.hypothesis_space(p, {"obs": [2.0, 4.0, 10.0], "n_trans": 7})
        assert d[0] == ("var", "acc") and st["steps"] <= LP.STEP_CAP and len(d) <= LP.POOL_CAP + 1
        assert LP.source(p)


def test_data_derived_constants_and_features():
    assert ("const", 2) in LP._derive("int_ratios", [4.0, 2.0, 7.0])
    assert LP.features({"obs": [1.0, 2.5]})["n_obs_int_frac"] == 0.5


def test_episodes_have_consequential_mechanisms_and_param_domains_stay_in_class():
    for fam in M.DEV_FAMILIES:
        ep = M.Episode(7, fam)
        assert ep.y_train and ep.family == fam
    d, _ = ML.params_domain(7)({})
    ops = {n[1] for n in d if n[0] == "b"}
    assert ops <= {"+", "-"}                                             # parameter-only control: no new operator
