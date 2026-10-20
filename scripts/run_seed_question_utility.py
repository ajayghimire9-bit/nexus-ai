"""One task-blocked source question-learning study through the existing host."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_question_utility.json','NEXUS_SEED_QUESTION_UTILITY_PROTOCOL.md',
        'seed_question_utility.json','seed_question_utility_v1','seed-question-utility-1')
