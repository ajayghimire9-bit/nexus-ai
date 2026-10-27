# de3-dev-954 (NEXUS_Fresh)

Outcome: COMPLETED_VERIFIED

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "sink_then_offsets", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "table", "gap_handling": "wait_contiguous", "gold_maintenance": "full_recompute", "lateness": "watermark", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True), ('accounting_and_lag', True), ('gold_equals_recompute', True), ('silver_rederivation', True), ('lateness_conformance', True), ('duplicate_delivery_invariance', True), ('arrival_permutation_invariance', True), ('backfill_timing_invariance', True), ('utc_offset_invariance', True), ('crash_sweep', True), ('rollback_drill', True), ('replay_conformance', True), ('ack_durability', True), ('chunk_invariance', True)]
