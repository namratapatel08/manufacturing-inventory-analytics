/* =====================================================================
   Bulk-load the processed star-schema CSVs (data/processed/*.csv) into
   SQL Server. Run 01_create_schema.sql first.

   Adjust the file path below to wherever this repo is checked out on the
   machine running SQL Server (BULK INSERT reads files visible to the SQL
   Server *service* account, not your client machine -- if SSMS/the engine
   run on a different host than your checkout, copy the CSVs to a path the
   engine can reach, or use the Import Flat File wizard / bcp.exe instead).
   ===================================================================== */
USE MfgInventoryDW;
GO

DECLARE @root NVARCHAR(260) = N'C:\ManufacturingInventoryAnalytics\data\processed\';

-- Load order respects FK dependencies (dimensions before facts)
DECLARE @tables TABLE (seq INT IDENTITY, tbl SYSNAME, file_name SYSNAME);
INSERT INTO @tables (tbl, file_name) VALUES
 ('dim_date', 'dim_date.csv'),
 ('dim_machine', 'dim_machine.csv'),
 ('dim_shift', 'dim_shift.csv'),
 ('dim_product_type', 'dim_product_type.csv'),
 ('dim_failure_mode', 'dim_failure_mode.csv'),
 ('fact_production_unit', 'fact_production_unit.csv'),
 ('fact_production_shift', 'fact_production_shift.csv'),
 ('dim_supplier', 'dim_supplier.csv'),
 ('dim_dc', 'dim_dc.csv'),
 ('dim_category', 'dim_category.csv'),
 ('dim_sku', 'dim_sku.csv'),
 ('fact_inventory', 'fact_inventory.csv');

DECLARE @sql NVARCHAR(MAX), @tbl SYSNAME, @file SYSNAME, @i INT = 1, @n INT;
SELECT @n = COUNT(*) FROM @tables;
WHILE @i <= @n
BEGIN
    SELECT @tbl = tbl, @file = file_name FROM @tables WHERE seq = @i;
    SET @sql = N'BULK INSERT dbo.' + QUOTENAME(@tbl) +
               N' FROM ''' + @root + @file + N'''' +
               N' WITH (FORMAT = ''CSV'', FIRSTROW = 2, CODEPAGE = ''65001'', TABLOCK);';
    PRINT @sql;
    EXEC sp_executesql @sql;
    SET @i += 1;
END
GO

-- Sanity check row counts
SELECT 'dim_date' t, COUNT(*) rows FROM dbo.dim_date
UNION ALL SELECT 'dim_machine', COUNT(*) FROM dbo.dim_machine
UNION ALL SELECT 'fact_production_unit', COUNT(*) FROM dbo.fact_production_unit
UNION ALL SELECT 'fact_production_shift', COUNT(*) FROM dbo.fact_production_shift
UNION ALL SELECT 'dim_sku', COUNT(*) FROM dbo.dim_sku
UNION ALL SELECT 'fact_inventory', COUNT(*) FROM dbo.fact_inventory;
GO
