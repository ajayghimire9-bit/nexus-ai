"""Execute the single registered disjoint compositional meta-learning study."""
from run_seed_update_diagnosis import execute_study

if __name__ == "__main__":
    execute_study(
        "seed_disjoint_meta.json",
        "NEXUS_SEED_DISJOINT_META_PROTOCOL.md",
        "seed_disjoint_meta.json",
        "seed_disjoint_meta_v1",
        "seed-disjoint-meta-1",
    )
