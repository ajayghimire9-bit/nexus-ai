"""One locked answer-free study, through the existing host and ledger."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_answer_free_utility.json','NEXUS_SEED_ANSWER_FREE_UTILITY_PROTOCOL.md',
        'seed_answer_free_utility.json','seed_answer_free_utility_v1','seed-answer-free-utility-1')
