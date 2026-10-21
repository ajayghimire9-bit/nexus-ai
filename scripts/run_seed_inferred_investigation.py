"""Single registered authored development study via existing resource host."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_inferred_investigation.json','NEXUS_SEED_INFERRED_INVESTIGATION_PROTOCOL.md',
        'seed_inferred_investigation.json','seed_inferred_investigation_v1','seed-inferred-investigation-1')
