/* =====================================================================
   KPI views — SQL Server / T-SQL.
   Logically identical to sql/validation_postgres/03_kpi_views.sql, which
   was executed end-to-end against the real loaded data to verify every
   number in this project (see docs/kpi_validation_output.txt).
   ===================================================================== */
USE MfgInventoryDW;
GO

------------------------------------------------------------------------
-- 1. OEE by machine / shift / date  (Availability x Performance x Quality)
------------------------------------------------------------------------
CREATE OR ALTER VIEW dbo.vw_oee_shift AS
SELECT
    f.date_key,
    d.[year], d.quarter, d.[month], d.month_name, d.week_of_year,
    m.machine_id, m.machine_name, m.production_line, m.plant,
    s.shift_id, s.shift_name,
    f.planned_min,
    f.run_time_min,
    f.downtime_min,
    f.total_units,
    f.good_units,
    f.defective_units,
    CAST(f.run_time_min AS DECIMAL(9,4)) / NULLIF(f.planned_min, 0)                              AS availability,
    (f.avg_ideal_cycle_time_sec * f.total_units) / NULLIF(f.run_time_min * 60.0, 0)              AS performance,
    CAST(f.good_units AS DECIMAL(9,4)) / NULLIF(f.total_units, 0)                                AS quality,
    (CAST(f.run_time_min AS DECIMAL(9,4)) / NULLIF(f.planned_min, 0))
      * IIF((f.avg_ideal_cycle_time_sec * f.total_units) / NULLIF(f.run_time_min * 60.0, 0) > 1.0,
            1.0, (f.avg_ideal_cycle_time_sec * f.total_units) / NULLIF(f.run_time_min * 60.0, 0))
      * (CAST(f.good_units AS DECIMAL(9,4)) / NULLIF(f.total_units, 0))                          AS oee
FROM dbo.fact_production_shift f
JOIN dbo.dim_date d    ON d.date_key = f.date_key
JOIN dbo.dim_machine m ON m.machine_id = f.machine_id
JOIN dbo.dim_shift s   ON s.shift_id = f.shift_id;
GO

------------------------------------------------------------------------
-- 2. Defect detail (unit grain, with failure-mode + sensor context)
------------------------------------------------------------------------
CREATE OR ALTER VIEW dbo.vw_defect_detail AS
SELECT
    u.unit_id, u.date_key, d.[year], d.[month], d.month_name, d.week_of_year,
    m.machine_id, m.machine_name, m.production_line,
    s.shift_id, s.shift_name,
    pt.product_type_code, pt.product_type_name,
    u.is_defective, u.failure_mode_code, fm.failure_mode_name,
    u.downtime_min, u.air_temp_k, u.process_temp_k, u.rotational_speed_rpm,
    u.torque_nm, u.tool_wear_min
FROM dbo.fact_production_unit u
JOIN dbo.dim_date d           ON d.date_key = u.date_key
JOIN dbo.dim_machine m        ON m.machine_id = u.machine_id
JOIN dbo.dim_shift s          ON s.shift_id = u.shift_id
JOIN dbo.dim_product_type pt  ON pt.product_type_code = u.product_type_code
JOIN dbo.dim_failure_mode fm  ON fm.failure_mode_code = u.failure_mode_code;
GO

------------------------------------------------------------------------
-- 3. Inventory KPI detail (turnover, days of inventory, reorder risk)
------------------------------------------------------------------------
CREATE OR ALTER VIEW dbo.vw_inventory_detail AS
SELECT
    fi.inventory_key, fi.sku_id, sk.product_name, c.category_id, c.category,
    fi.dc_id, dc.dc_name, dc.region,
    fi.supplier_id, sp.supplier_name,
    fi.status, fi.date_received, fi.last_order_date, fi.expiration_date,
    fi.stock_quantity, fi.reorder_level, fi.reorder_quantity,
    fi.sales_volume, sk.unit_price,
    fi.vendor_reported_turnover, fi.recomputed_turnover_rate, fi.days_of_inventory,
    fi.is_below_reorder_point, fi.revenue_est
FROM dbo.fact_inventory fi
JOIN dbo.dim_sku sk      ON sk.sku_id = fi.sku_id
JOIN dbo.dim_category c  ON c.category_id = sk.category_id
JOIN dbo.dim_dc dc       ON dc.dc_id = fi.dc_id
JOIN dbo.dim_supplier sp ON sp.supplier_id = fi.supplier_id;
GO

------------------------------------------------------------------------
-- 4. ABC classification (revenue-based Pareto)
------------------------------------------------------------------------
CREATE OR ALTER VIEW dbo.vw_inventory_abc AS
WITH ranked AS (
    SELECT
        sku_id, product_name, category, revenue_est,
        SUM(revenue_est) OVER (ORDER BY revenue_est DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            / NULLIF(SUM(revenue_est) OVER (), 0) AS cum_revenue_pct
    FROM dbo.vw_inventory_detail
)
SELECT *,
    CASE
        WHEN cum_revenue_pct <= 0.70 THEN 'A'
        WHEN cum_revenue_pct <= 0.90 THEN 'B'
        ELSE 'C'
    END AS abc_class
FROM ranked;
GO
