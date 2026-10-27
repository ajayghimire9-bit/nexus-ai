# de4-test-7974 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "arrival", "backfill_merge": "blind_overwrite", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "hard_only", "discount_unit": "registry_unit", "fx": "none", "fx_unknown": "error", "gap_handling": "skip", "gold_maintenance": "delta_no_retract", "lateness": "processing_time", "malformed": "drop_silent", "partition_discovery": "static_initial", "schema_handling": "registry_typed", "snapshots": "none", "ts_format": "registry_typed", "ts_parse": "text", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
