"""Execute the one registered authored-history study through the existing host."""
from run_seed_update_diagnosis import execute_study

if __name__ == '__main__':
    execute_study('seed_executable_world.json','NEXUS_SEED_EXECUTABLE_WORLD_PROTOCOL.md',
                  'seed_executable_world.json','seed_executable_world_v1','seed-executable-world-1')
