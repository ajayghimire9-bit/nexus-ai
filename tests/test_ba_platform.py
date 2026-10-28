"""ba platform patches (fast; generator-only crash check of X6 on a NON-test seed; no NEXUS code runs on X6)."""
from nexus import ba_platform as BP
from nexus import ba_seeds  # noqa: F401
from nexus import seed_registry as R


def test_x6_schedule_and_reference_mapping():
    assert [BP.PL.fault_of(s, "ba_test") for s in (0, 4, 8, 12)] == ["X6", "X3", "X6", "X5"]
    P = BP.Project(3, "ba_test")                                     # seed 3 is outside every ba range
    assert P.fault == "X6" and 3 not in R.REGISTRY[("ba", "test")]
    vf = P.schema.val
    early = [e for t in range(1, 9) for e in P.ticks[t]["B"]]
    late = [e for t in range(9, 17) for e in P.ticks[t]["B"]]
    assert all(vf in e and vf + "_amount" not in e for e in early)
    assert all(vf + "_amount" in e and vf not in e for e in late)
    moved = [dict({a: b for a, b in e.items() if a != vf + "_amount"}, **{vf: e[vf + "_amount"]}) for e in late]
    assert P.ref_B(early + late) == P.ref_B(early + moved)


def test_bounded_arm_is_a_strong_arm():
    assert issubclass(BP.NexusArmBounded, BP.NexusArmStrong)
