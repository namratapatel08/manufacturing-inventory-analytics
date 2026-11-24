# Power BI Report Build Guide

The PBIP project under `powerbi/` ships a complete semantic model (12 tables,
14 relationships, 26 DAX measures — see `powerbi/ManufacturingInventoryDashboard.SemanticModel/`)
and a generated report scaffold (`powerbi/ManufacturingInventoryDashboard.Report/`)
with 3 pages and ~30 visuals already wired to the right fields.

This project was built in a Linux sandbox with no access to Power BI Desktop,
so the report's JSON was hand-generated against the documented PBIR schema
rather than exported from the tool itself. **Open `ManufacturingInventoryDashboard.pbip`
in Power BI Desktop first** — if everything renders, you're done. If a visual
looks off or Desktop flags something, this guide gives you the exact
field list to rebuild any visual in under a minute.

## First-time setup

1. Install [Power BI Desktop](https://www.microsoft.com/en-us/power-platform/products/power-bi/desktop) (Windows).
2. Open `powerbi/ManufacturingInventoryDashboard.pbip`.
3. Power BI will ask you to update the `ProcessedDataFolder` parameter (Transform data → Manage Parameters) — point it at the absolute path of this repo's `data/processed/` folder on your machine, e.g. `C:\repos\ManufacturingInventoryAnalytics\data\processed\`.
4. Refresh (Home → Refresh). All 12 tables should load (10,000 + 990 + small dimension rows).
5. **Optional — point at SQL Server instead of CSV:** run `sql/sqlserver/01_create_schema.sql`, `00_bulk_load.sql`, and `02_kpi_views.sql` against your instance, then in Power Query change each table's source step from `Csv.Document(...)` to `Sql.Database("<server>", "MfgInventoryDW")` and pick the matching table/view. The DAX measures and relationships don't need to change either way.

## Page 1 — Executive Summary

| Visual | Type | Fields |
|---|---|---|
| KPI tiles | Card ×6 | `OEE`, `Defect Rate`, `Avg Stock Turnover`, `% SKUs Below Reorder`, `Total Inventory Revenue`, `Total Units Produced` |
| OEE by Machine | Clustered bar, sorted descending | Axis: `dim_machine[machine_name]` · Values: `OEE`. Add a constant line at 0.85 (Format → Analytics → Constant line) labeled "World-class benchmark". |
| OEE Trend by Week | Line chart | Axis: `dim_date[week_of_year]` (filtered to production window) · Values: `OEE` |
| Inventory Revenue by ABC Class | Clustered bar | Axis: `fact_inventory[abc_class]` · Values: `Total Inventory Revenue` |
| Revenue by Category | Bar chart, sorted descending | Axis: `dim_category[category]` · Values: `Total Inventory Revenue` |

## Page 2 — Manufacturing OEE

| Visual | Type | Fields |
|---|---|---|
| KPI tiles | Card ×5 | `Availability`, `Performance (capped)`, `Quality`, `OEE`, `OEE vs Target` |
| Production Line slicer | Slicer | `dim_machine[production_line]` |
| Defect Rate by Machine & Shift | Bar chart | Axis: `dim_machine[machine_name]` · Legend: `dim_shift[shift_name]` · Values: `Defect Rate` |
| Downtime by Failure Mode | Bar chart, sorted descending (Pareto) | Axis: `dim_failure_mode[failure_mode_name]` · Values: `Total Downtime (min)` |
| Machine-Level OEE Detail | Table | `dim_machine[machine_name]`, `production_line`, `OEE`, `Availability`, `Performance (capped)`, `Quality`, `Total Units Produced`, `Defect Rate` |

**Drill-down path:** `dim_machine[plant] → production_line → machine_name`, cross-filtered by `dim_shift[shift_name]`. Right-click any bar → Drill down, or add the hierarchy to the axis and use the drill icons in the visual header.

## Page 3 — Inventory Health

| Visual | Type | Fields |
|---|---|---|
| KPI tiles | Card ×4 | `Total Stock On Hand`, `Total SKUs`, `Avg Days of Inventory`, `Revenue at Risk (Below Reorder)` |
| Distribution Center slicer | Slicer | `dim_dc[dc_name]` |
| Avg Stock Turnover by Category | Bar chart | Axis: `dim_category[category]` · Values: `Avg Stock Turnover` |
| Days of Inventory by DC | Bar chart | Axis: `dim_dc[dc_name]` · Values: `Avg Days of Inventory` |
| Reorder Risk table | Table, filtered to `is_below_reorder_point = TRUE` | `sku_id`, `dim_sku[product_name]`, `dim_category[category]`, `dim_dc[dc_name]`, `stock_quantity`, `reorder_level`, `status` |

**Drill-down path:** `dim_dc[region] → dc_name`, cross-filtered by `dim_category[category] → dim_sku[product_name]`.

## Suggested polish (not in the generated scaffold)

- Conditional formatting on the Machine-Level OEE table: red/yellow/green background on the `OEE` column (thresholds 50% / 65% / 85%).
- A bookmark-driven toggle between "Vendor-reported" and "Recomputed" turnover on the Inventory page, to visually make the data-quality finding in `docs/data_dictionary.md` (put both `[Avg Stock Turnover]` and a second measure on `fact_inventory[vendor_reported_turnover]` side by side).
- Tooltip page showing sensor detail (`air_temp_k`, `process_temp_k`, `torque_nm`, `tool_wear_min`) on hover over a machine bar, using `fact_production_unit`.
- A report-level theme matching `dashboard/index.html`'s palette (see that file's `<style>` block for exact hex values) for visual consistency between the HTML preview and the live Power BI report.
