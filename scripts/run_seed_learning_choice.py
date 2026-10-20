"""One committed source-only roll-in/protected-choice study, existing host."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_learning_choice.json','NEXUS_SEED_LEARNING_CHOICE_PROTOCOL.md',
        'seed_learning_choice.json','seed_learning_choice_v1','seed-learning-choice-1')
