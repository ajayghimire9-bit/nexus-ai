# de4-val-7964 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "insert_if_absent", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "soft_and_hard", "discount_unit": "registry_unit", "fx": "table", "fx_unknown": "error", "gap_handling": "wait_contiguous", "gold_maintenance": "recompute_affected", "lateness": "processing_time", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "registry_int_cast", "snapshots": "none", "ts_format": "registry_typed", "ts_parse": "text", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
