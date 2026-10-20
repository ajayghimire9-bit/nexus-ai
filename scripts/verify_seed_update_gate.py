"""Read-only source-gate audit; explicit checkpoint audits fail on missing files."""
from verify_seed_cumulative_learning import main
from nexus.seed.update_gate import validate,source_pack


if __name__=='__main__':
    main(study_name='seed_update_gate',identifier='seed-update-gate-1',width=1,validator=validate,packer=source_pack)
