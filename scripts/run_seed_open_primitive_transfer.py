"""Execute the single registered Meta-Rule Evolution v2 + Open Primitive Code Transfer v1 study."""
from run_seed_update_diagnosis import execute_study

if __name__ == "__main__":
    execute_study(
        "seed_open_primitive_transfer.json",
        "NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md",
        "seed_open_primitive_transfer.json",
        "seed_open_primitive_transfer_v1",
        "seed-open-primitive-transfer-1",
    )
