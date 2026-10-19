# NEXUS documentation

**Start with Seed.** This is the current development direction: a local agent
that learns finite meanings through teaching. The wider compact, adaptive
intelligence mission remains a research ambition.

## Use and understand Seed

- [Quickstart and teaching walkthrough](seed/QUICKSTART.md)
- [Architecture and code ownership](seed/ARCHITECTURE.md)
- [Charter and boundaries](NEXUS_SEED_CHARTER.md)
- [S0–S7 roadmap](NEXUS_SEED_ROADMAP.md)
- [Implementation and sessions](NEXUS_SEED_STATUS.md)
- [Locked development protocol](NEXUS_SEED_PROTOCOL.md)
- [Results and incomplete comparison](NEXUS_SEED_RESULTS.md)
- [Contributor workflow](../CONTRIBUTING.md)

## Research context

- [Canonical current state](NEXUS_CANONICAL_CURRENT_STATE.md): newest outcomes;
  older chronological entries are retained history.
- [Master context](MASTER_CONTEXT.md): mission and complete research context.
- [Reuse map](NEXUS_CODE_REUSE_MAP.md): modules to reuse.
- [Full registry](NEXUS_FULL_RESEARCH_REGISTRY.md): experiment navigation.
- [Progress](NEXUS_PROGRESS.md), [hypotheses](NEXUS_HYPOTHESIS_REGISTER.md),
  and [next experiment](NEXUS_NEXT_EXPERIMENT.md).
- [Historical research guide](history/README.md).

## Evidence and private files

Public results live in [artifacts/](../artifacts/); locked configurations in
[configs/](../configs/). Original paths are stable because provenance records
refer to them. Local user sessions and ignored binary checkpoints are not public
artifacts. A GitHub clone does not contain every historical model file.

The Seed comparison is incomplete. Audit its recorded prefix with
`python3 -I -S scripts/verify_seed_comparison.py --allow-partial`; default strict
verification correctly rejects completeness. Do not execute it again.
