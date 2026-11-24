/* =====================================================================
   Headline KPI queries — SQL Server / T-SQL
   Logically identical to sql/validation_postgres/04_kpi_queries.sql.
   Validated output (run against the real data on PostgreSQL, since this
   project's build sandbox has no route to a SQL Server instance):
   docs/kpi_validation_output.txt
   ===================================================================== */
USE MfgInventoryDW;
GO

-- Q1. Overall plant OEE + component breakdown
SELECT
    AVG(availability) AS avg_availability,
    AVG(performance)  AS avg_performance,
    AVG(quality)      AS avg_quality,
    AVG(oee)          AS avg_oee,
    SUM(total_units)     AS total_units_produced,
    SUM(defective_units) AS total_defective_units
FROM dbo.vw_oee_shift;
GO

-- Q2. OEE by machine (drill-down level 1)
SELECT machine_name, production_line,
       AVG(oee) AS oee, AVG(availability) AS availability,
       AVG(performance) AS performance, AVG(quality) AS quality,
       SUM(total_units) AS units
FROM dbo.vw_oee_shift
GROUP BY machine_name, production_line
ORDER BY oee DESC;
GO

-- Q3. OEE trend by week (line chart / time drill-down)
SELECT [year], week_of_year, AVG(oee) AS oee
FROM dbo.vw_oee_shift
GROUP BY [year], week_of_year
ORDER BY [year], week_of_year;
GO

-- Q4. Defect rate by machine / shift
SELECT machine_name, shift_name,
       COUNT(*) AS units,
       SUM(CASE WHEN is_defective = 1 THEN 1 ELSE 0 END) AS defects,
       100.0 * SUM(CASE WHEN is_defective = 1 THEN 1 ELSE 0 END) / COUNT(*) AS defect_rate_pct
FROM dbo.vw_defect_detail
GROUP BY machine_name, shift_name
ORDER BY defect_rate_pct DESC;
GO

-- Q5. Downtime Pareto by failure mode
SELECT failure_mode_name,
       SUM(CASE WHEN is_defective = 1 THEN 1 ELSE 0 END) AS occurrences,
       SUM(downtime_min) AS total_downtime_min,
       100.0 * SUM(downtime_min) / SUM(SUM(downtime_min)) OVER () AS pct_of_total_downtime
FROM dbo.vw_defect_detail
WHERE failure_mode_code <> 'NONE'
GROUP BY failure_mode_name
ORDER BY total_downtime_min DESC;
GO

-- Q6. Inventory turnover & days-of-inventory by category
SELECT category,
       AVG(recomputed_turnover_rate) AS avg_turnover_rate,
       AVG(days_of_inventory)        AS avg_days_of_inventory,
       SUM(stock_quantity)           AS total_units_on_hand,
       SUM(revenue_est)              AS total_revenue
FROM dbo.vw_inventory_detail
GROUP BY category
ORDER BY total_revenue DESC;
GO

-- Q7. Reorder risk list (stock at/under reorder point)
SELECT TOP 20 sku_id, product_name, category, dc_name, stock_quantity,
       reorder_level, reorder_quantity, status
FROM dbo.vw_inventory_detail
WHERE is_below_reorder_point = 1
ORDER BY (reorder_level - stock_quantity) DESC;
GO

-- Q8. Stock turnover / days-of-inventory by distribution center
SELECT dc_name, region,
       AVG(recomputed_turnover_rate) AS avg_turnover_rate,
       AVG(days_of_inventory)        AS avg_days_of_inventory,
       SUM(CASE WHEN is_below_reorder_point = 1 THEN 1 ELSE 0 END) AS skus_below_reorder,
       COUNT(*) AS total_skus
FROM dbo.vw_inventory_detail
GROUP BY dc_name, region
ORDER BY avg_turnover_rate DESC;
GO

-- Q9. ABC classification summary
SELECT abc_class,
       COUNT(*) AS sku_count,
       SUM(revenue_est) AS revenue,
       100.0 * SUM(revenue_est) / SUM(SUM(revenue_est)) OVER () AS pct_of_revenue
FROM dbo.vw_inventory_abc
GROUP BY abc_class
ORDER BY abc_class;
GO

-- Q10. Data-quality check: vendor-reported vs recomputed turnover
-- (T-SQL has no built-in CORR(); computed via the standard covariance/stdev formula)
SELECT
    (AVG(vendor_reported_turnover * recomputed_turnover_rate)
     - AVG(vendor_reported_turnover) * AVG(recomputed_turnover_rate))
    / NULLIF(STDEV(vendor_reported_turnover) * STDEV(recomputed_turnover_rate), 0) AS correlation,
    STDEV(vendor_reported_turnover) AS vendor_stddev,
    STDEV(recomputed_turnover_rate) AS recomputed_stddev
FROM dbo.vw_inventory_detail;
GO
