"""Six worlds with different state topology, execution semantics and interaction protocol (NOT LOCKED)."""
from . import world_a_data, world_b_temporal, world_c_spatial, world_d_planning, world_e_causal, world_f_programs
from .base import Task, TaskView, verify, build_task  # noqa: F401

WORLDS = {m.WORLD: m for m in (world_a_data, world_b_temporal, world_c_spatial, world_d_planning, world_e_causal,
                               world_f_programs)}
FAMILIES = {w: m.FAMILIES for w, m in WORLDS.items()}
SOURCE_WORLDS, HELDOUT_WORLDS = ("A", "B", "D", "F"), ("C", "E")


def make_task(world, family, level, seed, role, partners):
    return build_task(WORLDS, world, family, level, seed, role, partners, WORLDS[world].Q_BUDGET)
