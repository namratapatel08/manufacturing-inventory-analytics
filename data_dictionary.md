# Data Dictionary & ETL Business Rules

## Sources

| Source file | Origin | License | Rows | Notes |
|---|---|---|---|---|
| `data/raw/ai4i2020.csv` | [AI4I 2020 Predictive Maintenance Dataset, UCI ML Repository](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset) (mirrored on GitHub, identical to the UCI/Kaggle copy) | CC BY 4.0 | 10,000 | Real sensor readings from a milling process simulation: temperatures, rotational speed, torque, tool wear, and 5 independent failure-mode flags (TWF/HDF/PWF/OSF/RNF) plus an overall `Machine failure` flag. |
| `data/raw/grocery_inventory.csv` | [Inventory-Management-Forecasting-using-Machine-Learning, GitHub](https://github.com/piumalnipun9/Inventory-Management-Forecasting-using-Machine-Learning) | MIT | 990 | SKU-level grocery inventory snapshot: stock on hand, reorder points, supplier, category, sales volume, unit price. |

Both files are committed unmodified under `data/raw/`.

## Why derived fields were needed

Neither source ships fields a production OEE / inventory-turnover dashboard needs out of the box:

* AI4I2020 has no shift, machine, or calendar date — it's a flat list of readings — and no "planned production time" or "ideal cycle time" (the two other inputs OEE needs beyond the failure flags).
* The grocery dataset has a **unique street address per row** (990 addresses / 990 rows), so it has no real multi-warehouse structure to drill into, and its `Inventory_Turnover_Rate` column turns out to be statistically indistinguishable from random noise (see below).

Every derived field is listed here so nothing is hidden. No *measured* value (temperature, torque, tool wear, stock quantity, sales volume, price, ...) was invented — only the operational context (which machine, which shift, which date, which distribution center) and one OEE input (a machine "speed factor", see below) were assigned.

## Manufacturing domain — derived fields

| Field | Rule |
|---|---|
| `machine_id` (1-6), `shift_id` (1-2), `date_key` | Assigned via an independent stable hash of each unit's `UDI` per dimension (not a plain `UDI % N`, which was tried first and produced a hidden 1:1 correlation between machine and shift — caught during validation, see commit history / `etl/transform.py` comments). Spread across a 12-week production window (2026-01-05 to 2026-03-29). |
| `ideal_cycle_time_sec` | By product tier: Economy(L)=18s, Standard(M)=25s, Premium(H)=35s — slower tiers assumed to be higher-precision product lines. |
| `downtime_min` per unit | Each triggered failure flag (TWF/HDF/PWF/OSF/RNF) contributes a fixed per-event downtime: TWF=8, HDF=12, PWF=15, OSF=10, RNF=5 minutes (a tool change / reset time for that failure type, scaled to this dataset's ~10-40 unit batch sizes — real 8-hour-shift downtime minutes would be too large relative to these batch sizes). |
| `run_time_min` (per machine/shift/date bucket) | `ideal_run_time = ideal_cycle_time_sec × total_units`. A per-bucket **speed factor** ~ Normal(0.83, 0.06), clipped to [0.65, 0.97], is applied (`run_time = ideal_run_time / speed_factor`) to represent minor stoppages and speed loss *not* captured by the explicit failure flags — this is standard OEE practice (Performance always includes unlogged micro-stops) and is the one fully-synthetic input in the manufacturing model. |
| `planned_min` | `run_time_min + downtime_min` (derived, not fixed — batch sizes vary by bucket). |
| `is_defective` | Directly `Machine failure` from the source (unmodified). |

**Resulting OEE** (validated on the full dataset, see `docs/kpi_validation_output.txt`): Availability 79.2%, Performance 82.9%, Quality 96.6% → **OEE 65.0%** — a realistic "solid but improvable" plant figure, with Availability as the clearest improvement lever (Heat Dissipation and Power failures alone are ~70% of all downtime).

## Inventory domain — derived fields

| Field | Rule |
|---|---|
| `dc_id` (distribution center) | Source `Warehouse_Location` is a unique street address per row with no real facility grouping. Each SKU-lot is deterministically bucketed into one of 5 named distribution centers (DC-East/West/Central/North/South) via a stable MD5 hash of `Product_ID`. The original address is preserved as `source_address` on the fact row for traceability. |
| `supplier_id` | Source `Supplier_ID` is a unique per-row lot identifier, not a supplier master key (350 distinct `Supplier_Name` values recur across many `Supplier_ID`s). Rebuilt as a proper dimension keyed on `supplier_name`; the original per-row ID is kept as `supplier_lot_id`. |
| `recomputed_turnover_rate` | **Data-quality finding:** the source `Inventory_Turnover_Rate` column has mean ≈50.15, std ≈28.8 — statistically indistinguishable from `Uniform(1,100)` noise (correlation with a properly-derived turnover metric measured at **0.000**, see Q10 in `sql/*/04_kpi_queries.sql` / `03_kpi_queries.sql`) — i.e. it does not actually track stock or sales. It is kept as `vendor_reported_turnover` for traceability, and a real metric is computed instead: `turnover_rate = Sales_Volume / Average_Inventory`, where `Average_Inventory ≈ (Stock_Quantity + Reorder_Level) / 2` (documented approximation — the source is a point-in-time snapshot with no opening-balance history, so reorder level is used as a proxy for typical replenished stock level). |
| `days_of_inventory` | `365 / recomputed_turnover_rate`. |
| `is_below_reorder_point` | `Stock_Quantity <= Reorder_Level`. |
| `revenue_est` | `Unit_Price × Sales_Volume`. |

## Star schema

**Manufacturing:** `fact_production_unit` (grain: 1 manufactured unit, 10,000 rows) and a pre-aggregated `fact_production_shift` (grain: machine × shift × date, 1,008 rows, used by the OEE view for fast dashboard queries) — both link to `dim_date`, `dim_machine`, `dim_shift`, `dim_product_type`, `dim_failure_mode`.

**Inventory:** `fact_inventory` (grain: 1 SKU-lot record, 990 rows) links to `dim_sku`, `dim_category`, `dim_supplier`, `dim_dc`, and shares `dim_date` via `date_received` / `last_order_date` (role-playing dimension in the Power BI model).

Full column-level definitions are in the CSV headers under `data/processed/` and the DDL in `sql/sqlserver/01_create_schema.sql`.
