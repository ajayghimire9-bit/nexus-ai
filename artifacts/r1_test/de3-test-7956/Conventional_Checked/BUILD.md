# de3-test-7956 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "arrival", "backfill_merge": "blind_overwrite", "commit_protocol": "sink_then_offsets", "dedup": "none", "deletes": "soft_and_hard", "fx": "none", "gap_handling": "wait_contiguous", "gold_maintenance": "full_recompute", "lateness": "processing_time", "malformed": "quarantine", "partition_discovery": "static_initial", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
