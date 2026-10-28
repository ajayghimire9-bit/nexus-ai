# de5-dev-993 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "soft_and_hard", "discount_unit": "registry_unit", "fx": "table", "fx_unknown": "quarantine", "gap_handling": "skip", "gold_maintenance": "recompute_affected", "lateness": "processing_time", "malformed": "drop_silent", "partition_discovery": "dynamic", "schema_handling": "registry_int_cast", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
