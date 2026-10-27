# de4-test-7971 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "offsets_first", "dedup": "by_msg_id", "deletes": "hard_only", "discount_unit": "registry_unit", "fx": "table", "fx_unknown": "quarantine", "gap_handling": "skip", "gold_maintenance": "recompute_affected", "lateness": "watermark", "malformed": "drop_silent", "partition_discovery": "static_initial", "schema_handling": "v1_lenient", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "text", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
