"""Run the registered investigation study once through the existing host."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_investigation_transfer.json','NEXUS_SEED_INVESTIGATION_TRANSFER_PROTOCOL.md',
                  'seed_investigation_transfer.json','seed_investigation_transfer_v1','seed-investigation-transfer-1')
