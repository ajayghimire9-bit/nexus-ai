# de4-test-7973 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "insert_if_absent", "commit_protocol": "offsets_first", "dedup": "none", "deletes": "hard_only", "discount_unit": "registry_unit", "fx": "none", "fx_unknown": "quarantine", "gap_handling": "skip", "gold_maintenance": "recompute_affected", "lateness": "processing_time", "malformed": "drop_silent", "partition_discovery": "dynamic", "schema_handling": "v1_lenient", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "text", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
