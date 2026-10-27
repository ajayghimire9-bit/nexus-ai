# de3-test-7955 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "blind_overwrite", "commit_protocol": "sink_then_offsets", "dedup": "by_msg_id", "deletes": "hard_only", "fx": "table", "gap_handling": "wait_contiguous", "gold_maintenance": "recompute_affected", "lateness": "none", "malformed": "drop_silent", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
