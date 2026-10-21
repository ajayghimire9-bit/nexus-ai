"""Execute the single registered Meta-Rule Evolution v1 study."""
from run_seed_update_diagnosis import execute_study

if __name__ == "__main__":
    execute_study(
        "seed_meta_rule_evolution.json",
        "NEXUS_SEED_META_RULE_EVOLUTION_PROTOCOL.md",
        "seed_meta_rule_evolution.json",
        "seed_meta_rule_evolution_v1",
        "seed-meta-rule-evolution-1",
    )
