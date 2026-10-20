"""Run the single locked source comparison through the existing host entry."""
from run_seed_update_diagnosis import execute_study


if __name__=='__main__':
    execute_study('seed_bounded_correction.json','NEXUS_SEED_BOUNDED_CORRECTION_PROTOCOL.md',
        'seed_bounded_correction.json','seed_bounded_correction_v1','seed-bounded-correction-1')
