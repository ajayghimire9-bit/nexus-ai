"""Run the locked source-only scalar gate comparison through the existing host."""
from run_seed_update_diagnosis import execute_study


if __name__=='__main__':
    execute_study('seed_update_gate.json','NEXUS_SEED_UPDATE_GATE_PROTOCOL.md',
        'seed_update_gate.json','seed_update_gate_v1','seed-update-gate-1')
