# de5-dev-994 (Fixed_Policy)

Decisions: {"apply_order": "arrival", "backfill_merge": "blind_overwrite", "commit_protocol": "sink_then_offsets", "dedup": "none", "deletes": "soft_and_hard", "discount_unit": "registry_unit", "fx": "none", "fx_unknown": "quarantine", "gap_handling": "skip", "gold_maintenance": "full_recompute", "lateness": "processing_time", "malformed": "quarantine", "partition_discovery": "static_initial", "schema_handling": "v1_lenient", "snapshots": "per_tick", "ts_format": "iso_only", "ts_parse": "utc", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', False)]
