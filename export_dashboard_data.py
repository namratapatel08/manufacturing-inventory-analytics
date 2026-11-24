"""
Exports every KPI dataset the HTML dashboard preview needs, straight from
the validated PostgreSQL database (same views/queries as sql/*/04_kpi_queries.sql),
into a single JSON file consumed by dashboard/index.html.
"""
import json
import psycopg2
import psycopg2.extras

import os

# Local validation DB only (see sql/validation_postgres/). Override via env
# vars if your local Postgres uses different credentials.
conn = psycopg2.connect(
    host=os.environ.get("PGHOST", "localhost"),
    dbname=os.environ.get("PGDATABASE", "mfg_inventory"),
    user=os.environ.get("PGUSER", "postgres"),
    password=os.environ.get("PGPASSWORD", "postgres"),
)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def q(sql):
    cur.execute(sql)
    return cur.fetchall()

data = {}

data["headline"] = q("""
    SELECT ROUND(AVG(availability)::numeric,4) availability, ROUND(AVG(performance)::numeric,4) performance,
           ROUND(AVG(quality)::numeric,4) quality, ROUND(AVG(oee)::numeric,4) oee,
           SUM(total_units) total_units, SUM(defective_units) total_defects
    FROM vw_oee_shift
""")[0]

data["oee_by_machine"] = q("""
    SELECT machine_name, production_line, ROUND(AVG(oee)::numeric,4) oee,
           ROUND(AVG(availability)::numeric,4) availability, ROUND(AVG(performance)::numeric,4) performance,
           ROUND(AVG(quality)::numeric,4) quality, SUM(total_units) units, SUM(defective_units) defects
    FROM vw_oee_shift GROUP BY machine_name, production_line ORDER BY machine_name
""")

data["oee_by_week"] = q("""
    SELECT year, week_of_year, ROUND(AVG(oee)::numeric,4) oee
    FROM vw_oee_shift GROUP BY year, week_of_year ORDER BY year, week_of_year
""")

data["defect_by_machine_shift"] = q("""
    SELECT machine_name, shift_name, COUNT(*) units,
           SUM(CASE WHEN is_defective THEN 1 ELSE 0 END) defects,
           ROUND(100.0*SUM(CASE WHEN is_defective THEN 1 ELSE 0 END)/COUNT(*),2) defect_rate_pct
    FROM vw_defect_detail GROUP BY machine_name, shift_name ORDER BY defect_rate_pct DESC
""")

data["downtime_pareto"] = q("""
    SELECT failure_mode_name, COUNT(*) FILTER (WHERE is_defective) occurrences,
           SUM(downtime_min) total_downtime_min,
           ROUND(100.0*SUM(downtime_min)/SUM(SUM(downtime_min)) OVER (),2) pct_of_total
    FROM vw_defect_detail WHERE failure_mode_code <> 'NONE'
    GROUP BY failure_mode_name ORDER BY total_downtime_min DESC
""")

data["inventory_by_category"] = q("""
    SELECT category, ROUND(AVG(recomputed_turnover_rate)::numeric,2) avg_turnover,
           ROUND(AVG(days_of_inventory)::numeric,1) avg_days_of_inventory,
           SUM(stock_quantity) total_units, ROUND(SUM(revenue_est)::numeric,2) total_revenue
    FROM vw_inventory_detail GROUP BY category ORDER BY total_revenue DESC
""")

data["inventory_by_dc"] = q("""
    SELECT dc_name, region, ROUND(AVG(recomputed_turnover_rate)::numeric,2) avg_turnover,
           ROUND(AVG(days_of_inventory)::numeric,1) avg_days_of_inventory,
           COUNT(*) FILTER (WHERE is_below_reorder_point) skus_below_reorder, COUNT(*) total_skus
    FROM vw_inventory_detail GROUP BY dc_name, region ORDER BY dc_name
""")

data["abc_summary"] = q("""
    SELECT abc_class, COUNT(*) sku_count, ROUND(SUM(revenue_est)::numeric,2) revenue,
           ROUND(100.0*SUM(revenue_est)/SUM(SUM(revenue_est)) OVER (),2) pct_of_revenue
    FROM vw_inventory_abc GROUP BY abc_class ORDER BY abc_class
""")

data["reorder_risk_top"] = q("""
    SELECT sku_id, product_name, category, dc_name, stock_quantity, reorder_level, status
    FROM vw_inventory_detail WHERE is_below_reorder_point
    ORDER BY (reorder_level - stock_quantity) DESC LIMIT 12
""")

data["inventory_headline"] = q("""
    SELECT SUM(stock_quantity) total_stock, COUNT(*) total_skus,
           ROUND(AVG(days_of_inventory)::numeric,1) avg_days_of_inventory,
           ROUND(SUM(revenue_est) FILTER (WHERE is_below_reorder_point)::numeric,2) revenue_at_risk,
           ROUND(SUM(revenue_est)::numeric,2) total_revenue,
           COUNT(*) FILTER (WHERE is_below_reorder_point) skus_below_reorder
    FROM vw_inventory_detail
""")[0]

def default(o):
    from decimal import Decimal
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError

with open("../dashboard/data.json", "w") as f:
    json.dump(data, f, indent=2, default=default)

print("Wrote dashboard/data.json")
for k, v in data.items():
    print(f"  {k}: {len(v) if isinstance(v, list) else 1} rows")
