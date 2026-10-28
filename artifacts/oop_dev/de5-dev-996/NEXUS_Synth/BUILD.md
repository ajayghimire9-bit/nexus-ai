# de5-dev-996 (NEXUS_Synth)

Outcome: COMPLETED_VERIFIED

Decisions: {"commit_protocol": "transactional", "dedup": "by_msg_id", "gap_handling": "skip", "gold_maintenance": "full_recompute", "lateness": "processing_time", "partition_discovery": "dynamic", "snapshots": "per_tick", "syn_decode": "p5ba354e8", "syn_net": "p9977eb3b", "syn_silver": "pe2b9fdd0", "syn_status": "p2f20b2da", "ts_format": "registry_typed", "ts_parse": "text", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True), ('accounting_and_lag', True), ('gold_equals_recompute', True), ('silver_rederivation', True), ('lateness_conformance', True), ('duplicate_delivery_invariance', True), ('arrival_permutation_invariance', True), ('backfill_timing_invariance', True), ('utc_offset_invariance', True), ('crash_sweep', True), ('rollback_drill', True), ('replay_conformance', True), ('ack_durability', True), ('chunk_invariance', True)]
