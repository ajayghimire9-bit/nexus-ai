"""One locked source-only update-utility audit through the existing host."""
from run_seed_update_diagnosis import execute_study


if __name__=='__main__':
    execute_study('seed_prefix_consistency.json','NEXUS_SEED_PREFIX_CONSISTENCY_PROTOCOL.md',
        'seed_prefix_consistency.json','seed_prefix_consistency_v1','seed-prefix-consistency-1')
