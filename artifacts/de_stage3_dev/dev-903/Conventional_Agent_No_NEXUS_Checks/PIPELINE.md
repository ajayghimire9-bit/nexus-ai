# Pipeline for project dev-903 (Conventional_Agent_No_NEXUS_Checks)

Outcome: **COMPLETED_UNVERIFIED**

Run: `python pipeline.py --landing <batch dir> --state <state dir> --config config.json` once per batch, in order.
Outputs (state/lake.db): gold_carrier_volume, gold_inventory, gold_sla, gold_status_counts, gold_warehouse_revenue, late_events, quarantine, silver_manifest, silver_orders

## Implementation decisions
* `ts_parse` = `text`
* `cdc_apply` = `event_time`
* `cdc_incremental` = `watermark`
* `deletes` = `hard_only`
* `fx` = `none`
* `weight_parse` = `quarantine`
* `units` = `table`
* `drift` = `alias`
* `bronze_dedup` = `dedup`
* `dims_load` = `append`
* `revenue_join` = `semi_join`
* `sla_window` = `ignore`
* `carrier_uncovered` = `exclude`
* `bucket_uncovered` = `other`

## Clarifications
* none asked

## Verification
* none: the conventional stop rule submits the first configuration that runs without an exception

## Limits
* Checks cover the visible batches only; batch semantics are taken from docs/spec.json.
