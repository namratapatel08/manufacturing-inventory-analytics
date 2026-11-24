-- =====================================================================
-- Headline KPI queries — validated against the loaded data.
-- T-SQL equivalents: sql/sqlserver/03_kpi_queries.sql
-- =====================================================================

-- Q1. Overall plant OEE + component breakdown
SELECT
    ROUND(AVG(availability), 4) AS avg_availability,
    ROUND(AVG(performance), 4) AS avg_performance,
    ROUND(AVG(quality), 4)     AS avg_quality,
    ROUND(AVG(oee), 4)         AS avg_oee,
    SUM(total_units)           AS total_units_produced,
    SUM(defective_units)       AS total_defective_units
FROM vw_oee_shift;

-- Q2. OEE by machine (drill-down level 1)
SELECT machine_name, production_line,
       ROUND(AVG(oee), 4) AS oee,
       ROUND(AVG(availability), 4) AS availability,
       ROUND(AVG(performance), 4) AS performance,
       ROUND(AVG(quality), 4) AS quality,
       SUM(total_units) AS units
FROM vw_oee_shift
GROUP BY machine_name, production_line
ORDER BY oee DESC;

-- Q3. OEE trend by week (for line chart / time-of-day drill-down)
SELECT year, week_of_year,
       ROUND(AVG(oee), 4) AS oee
FROM vw_oee_shift
GROUP BY year, week_of_year
ORDER BY year, week_of_year;

-- Q4. Defect rate overall and by machine / shift
SELECT machine_name, shift_name,
       COUNT(*) AS units,
       SUM(CASE WHEN is_defective THEN 1 ELSE 0 END) AS defects,
       ROUND(100.0 * SUM(CASE WHEN is_defective THEN 1 ELSE 0 END) / COUNT(*), 2) AS defect_rate_pct
FROM vw_defect_detail
GROUP BY machine_name, shift_name
ORDER BY defect_rate_pct DESC;

-- Q5. Downtime Pareto by failure mode
SELECT failure_mode_name,
       COUNT(*) FILTER (WHERE is_defective) AS occurrences,
       SUM(downtime_min) AS total_downtime_min,
       ROUND(100.0 * SUM(downtime_min) / SUM(SUM(downtime_min)) OVER (), 2) AS pct_of_total_downtime
FROM vw_defect_detail
WHERE failure_mode_code <> 'NONE'
GROUP BY failure_mode_name
ORDER BY total_downtime_min DESC;

-- Q6. Inventory turnover & days-of-inventory by category
SELECT category,
       ROUND(AVG(recomputed_turnover_rate), 2) AS avg_turnover_rate,
       ROUND(AVG(days_of_inventory), 1)        AS avg_days_of_inventory,
       SUM(stock_quantity)                     AS total_units_on_hand,
       ROUND(SUM(revenue_est), 2)              AS total_revenue
FROM vw_inventory_detail
GROUP BY category
ORDER BY total_revenue DESC;

-- Q7. Reorder risk list (stock at/under reorder point)
SELECT sku_id, product_name, category, dc_name, stock_quantity, reorder_level, reorder_quantity, status
FROM vw_inventory_detail
WHERE is_below_reorder_point
ORDER BY (reorder_level - stock_quantity) DESC
LIMIT 20;

-- Q8. Stock turnover / days-of-inventory by distribution center (drill-down)
SELECT dc_name, region,
       ROUND(AVG(recomputed_turnover_rate), 2) AS avg_turnover_rate,
       ROUND(AVG(days_of_inventory), 1)        AS avg_days_of_inventory,
       COUNT(*) FILTER (WHERE is_below_reorder_point) AS skus_below_reorder,
       COUNT(*) AS total_skus
FROM vw_inventory_detail
GROUP BY dc_name, region
ORDER BY avg_turnover_rate DESC;

-- Q9. ABC classification summary
SELECT abc_class,
       COUNT(*) AS sku_count,
       ROUND(SUM(revenue_est), 2) AS revenue,
       ROUND(100.0 * SUM(revenue_est) / SUM(SUM(revenue_est)) OVER (), 2) AS pct_of_revenue
FROM vw_inventory_abc
GROUP BY abc_class
ORDER BY abc_class;

-- Q10. Data-quality check: vendor-reported vs recomputed turnover correlation
SELECT
    ROUND(CORR(vendor_reported_turnover, recomputed_turnover_rate)::numeric, 3) AS correlation,
    ROUND(STDDEV(vendor_reported_turnover)::numeric, 2) AS vendor_stddev,
    ROUND(STDDEV(recomputed_turnover_rate)::numeric, 2) AS recomputed_stddev
FROM vw_inventory_detail;
