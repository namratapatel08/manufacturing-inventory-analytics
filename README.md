# Manufacturing & Inventory Analytics

An end-to-end BI project: two real public datasets → a documented SQL ETL
pipeline → a validated star-schema data warehouse → OEE / defect / stock-turnover
KPI queries → a Power BI Project (semantic model + report) → this dashboard.

**[Open the dashboard preview](dashboard/index.html)** — a static HTML build of
the report (light/dark mode, hover tooltips) so the results are viewable
without installing anything.

## Headline numbers (validated — see `docs/kpi_validation_output.txt`)

| KPI | Value |
|---|---|
| Overall OEE | **65.0%** (Availability 79.2% × Performance 82.8% × Quality 96.6%) |
| Defect rate | 3.39% (339 / 10,000 units) |
| Biggest downtime driver | Heat Dissipation + Power failures = 70% of all downtime minutes |
| Avg stock turnover | 1.28× |
| SKUs below reorder point | 465 / 990 (47.0%) — $145,653 of revenue at risk |
| Inventory Pareto | Class A SKUs (35% of catalog) drive 69.9% of revenue |

## Why this project is structured the way it is

The brief was: pull a public manufacturing/inventory dataset, load it into
SQL, write real KPI queries, and build a Power BI report with drill-downs.
Two things drove every decision below — documented in full in
**[`docs/data_dictionary.md`](docs/data_dictionary.md)**:

1. **The public datasets don't ship OEE-ready fields.** [AI4I 2020](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)
   (UCI, CC BY 4.0, real sensor data from a milling process) has temperatures,
   torque, tool wear, and 5 failure-mode flags — but no machine/shift/date
   context, no planned production time, no ideal cycle time. A small, fully
   documented set of business rules derives those (see the data dictionary);
   nothing about the *measured* sensor values or failure flags was touched.
2. **The inventory dataset's own turnover metric turned out to be noise.**
   A [grocery inventory dataset](https://github.com/piumalnipun9/Inventory-Management-Forecasting-using-Machine-Learning)
   (MIT) ships an `Inventory_Turnover_Rate` column — checked it against a
   properly derived turnover metric and got **zero correlation** (see Q10 in
   `sql/*/04_kpi_queries.sql`). The vendor column is kept for traceability
   (`vendor_reported_turnover`) and a real metric is computed instead
   (`recomputed_turnover_rate = Sales Volume / Average Inventory`). That kind
   of check is the actual job in a BI project, so it's called out rather than
   buried.

## Architecture

```
Raw public CSVs  →  Python ETL (documented business rules)  →  Star schema CSVs
                                                                       │
                                          ┌────────────────────────────┴───────────────────────────┐
                                          ▼                                                          ▼
                              PostgreSQL 16 (validation)                                   SQL Server (deliverable)
                              schema + KPI views + queries                                 identical schema/views/queries
                              — actually executed, see                                     (sql/sqlserver/*.sql) — T-SQL,
                              docs/kpi_validation_output.txt                                ready to run against a real instance
                                          │
                                          ▼
                          Power BI Project (PBIP): TMDL semantic model
                          (12 tables, 14 relationships, 26 DAX measures)
                          + a 3-page report (Executive / Manufacturing / Inventory)
                                          │
                                          ▼
                          dashboard/index.html — static preview of the same
                          KPIs/visuals, viewable with no installs
```

**Why PostgreSQL *and* SQL Server T-SQL?** This project was built in a Linux
sandbox with no outbound access to Docker Hub / Microsoft Container Registry,
so a real SQL Server instance couldn't be provisioned to test against. Rather
than ship untested T-SQL, the identical schema/views/queries were run against
PostgreSQL 16 (installed locally) to validate every number in this README —
then translated to correct T-SQL syntax for the actual deliverable
(`sql/sqlserver/`). Every dialect difference (window functions, `LIMIT` vs
`TOP`, `STDDEV` vs `STDEV`, no `CORR()` in T-SQL, etc.) is handled explicitly —
see the comments in `sql/sqlserver/03_kpi_queries.sql`.

## Repo layout

```
data/
  raw/                    the two public datasets, unmodified
  processed/              star-schema CSVs produced by etl/transform.py
etl/
  transform.py            raw → star schema, with every derivation documented inline
sql/
  sqlserver/               the deliverable: T-SQL DDL, bulk load, KPI views & queries
  validation_postgres/     identical logic, actually executed to validate the numbers above
powerbi/
  ManufacturingInventoryDashboard.pbip         open this in Power BI Desktop
  ManufacturingInventoryDashboard.SemanticModel/   TMDL: tables, relationships, DAX measures
  ManufacturingInventoryDashboard.Report/          PBIR: 3 report pages, ~30 visuals
dashboard/
  index.html              standalone HTML preview of the dashboard (no installs needed)
docs/
  data_dictionary.md       every derived field & business rule, in full
  kpi_validation_output.txt   raw psql output for every KPI query, for spot-checking
  powerbi_report_guide.md  exact field list for every visual, page by page
scripts/
  generate_tmdl.py          builds the semantic model's table TMDL from the processed CSVs
  generate_report.py        builds the PBIR report pages/visuals
  export_dashboard_data.py  pulls validated KPI output into dashboard/data.json
```

## Reproducing it

```bash
pip install -r requirements.txt

# 1. Raw CSVs -> star schema
cd etl && python3 transform.py

# 2a. Validate against PostgreSQL (what was actually run to produce the numbers above)
psql -f sql/validation_postgres/01_create_schema.sql
psql -f sql/validation_postgres/02_load_data.sql
psql -f sql/validation_postgres/03_kpi_views.sql
psql -f sql/validation_postgres/04_kpi_queries.sql

# 2b. Or load the real deliverable into SQL Server
sqlcmd -i sql/sqlserver/01_create_schema.sql
sqlcmd -i sql/sqlserver/00_bulk_load.sql
sqlcmd -i sql/sqlserver/02_kpi_views.sql

# 3. Open powerbi/ManufacturingInventoryDashboard.pbip in Power BI Desktop
#    (set the ProcessedDataFolder parameter to your local data/processed/ path)
```

## Data sources & licenses

| Dataset | Source | License |
|---|---|---|
| AI4I 2020 Predictive Maintenance | [UCI ML Repository](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset) | CC BY 4.0 |
| Grocery Inventory | [GitHub](https://github.com/piumalnipun9/Inventory-Management-Forecasting-using-Machine-Learning) | MIT |

Full column-level provenance and every ETL business rule: [`docs/data_dictionary.md`](docs/data_dictionary.md).
