/* =====================================================================
   Manufacturing & Inventory Analytics — SQL Server DDL
   Target: Azure SQL / SQL Server 2019+
   Star schema: 2 fact tables (production, inventory) + 9 dimensions
   sharing a common dim_date.
   ===================================================================== */

IF DB_ID('MfgInventoryDW') IS NULL
BEGIN
    CREATE DATABASE MfgInventoryDW;
END
GO
USE MfgInventoryDW;
GO

------------------------------------------------------------------------
-- Shared dimension
------------------------------------------------------------------------
IF OBJECT_ID('dbo.dim_date', 'U') IS NOT NULL DROP TABLE dbo.dim_date;
CREATE TABLE dbo.dim_date (
    date_key      DATE         NOT NULL PRIMARY KEY,
    [year]        SMALLINT     NOT NULL,
    quarter       TINYINT      NOT NULL,
    [month]       TINYINT      NOT NULL,
    month_name    VARCHAR(3)   NOT NULL,
    [day]         TINYINT      NOT NULL,
    day_name      VARCHAR(3)   NOT NULL,
    week_of_year  TINYINT      NOT NULL,
    is_weekend    BIT          NOT NULL
);
GO

------------------------------------------------------------------------
-- MANUFACTURING dimensions & facts
------------------------------------------------------------------------
IF OBJECT_ID('dbo.dim_machine', 'U') IS NOT NULL DROP TABLE dbo.dim_machine;
CREATE TABLE dbo.dim_machine (
    machine_id        TINYINT      NOT NULL PRIMARY KEY,
    machine_name      VARCHAR(10)  NOT NULL,
    production_line   VARCHAR(20)  NOT NULL,
    plant             VARCHAR(50)  NOT NULL
);
GO

IF OBJECT_ID('dbo.dim_shift', 'U') IS NOT NULL DROP TABLE dbo.dim_shift;
CREATE TABLE dbo.dim_shift (
    shift_id         TINYINT      NOT NULL PRIMARY KEY,
    shift_name       VARCHAR(10)  NOT NULL,
    start_time       VARCHAR(5)   NOT NULL,
    end_time         VARCHAR(5)   NOT NULL
);
GO

IF OBJECT_ID('dbo.dim_product_type', 'U') IS NOT NULL DROP TABLE dbo.dim_product_type;
CREATE TABLE dbo.dim_product_type (
    product_type_code   CHAR(1)      NOT NULL PRIMARY KEY,
    product_type_name   VARCHAR(20)  NOT NULL,
    ideal_cycle_time_sec SMALLINT    NOT NULL
);
GO

IF OBJECT_ID('dbo.dim_failure_mode', 'U') IS NOT NULL DROP TABLE dbo.dim_failure_mode;
CREATE TABLE dbo.dim_failure_mode (
    failure_mode_code   VARCHAR(4)   NOT NULL PRIMARY KEY,
    failure_mode_name   VARCHAR(40)  NOT NULL,
    avg_downtime_min    SMALLINT     NOT NULL
);
GO

IF OBJECT_ID('dbo.fact_production_unit', 'U') IS NOT NULL DROP TABLE dbo.fact_production_unit;
CREATE TABLE dbo.fact_production_unit (
    unit_id                INT          NOT NULL PRIMARY KEY,
    date_key               DATE         NOT NULL REFERENCES dbo.dim_date(date_key),
    machine_id             TINYINT      NOT NULL REFERENCES dbo.dim_machine(machine_id),
    shift_id               TINYINT      NOT NULL REFERENCES dbo.dim_shift(shift_id),
    product_type_code      CHAR(1)      NOT NULL REFERENCES dbo.dim_product_type(product_type_code),
    product_code            VARCHAR(10),
    air_temp_k              DECIMAL(6,2),
    process_temp_k          DECIMAL(6,2),
    rotational_speed_rpm    INT,
    torque_nm                DECIMAL(6,2),
    tool_wear_min            SMALLINT,
    is_defective              BIT NOT NULL,
    failure_mode_code        VARCHAR(4) NOT NULL REFERENCES dbo.dim_failure_mode(failure_mode_code),
    downtime_min              SMALLINT NOT NULL,
    ideal_cycle_time_sec      SMALLINT NOT NULL
);
CREATE INDEX ix_fpu_date_machine_shift ON dbo.fact_production_unit(date_key, machine_id, shift_id);
GO

IF OBJECT_ID('dbo.fact_production_shift', 'U') IS NOT NULL DROP TABLE dbo.fact_production_shift;
CREATE TABLE dbo.fact_production_shift (
    date_key                 DATE     NOT NULL REFERENCES dbo.dim_date(date_key),
    machine_id                TINYINT NOT NULL REFERENCES dbo.dim_machine(machine_id),
    shift_id                  TINYINT NOT NULL REFERENCES dbo.dim_shift(shift_id),
    total_units                INT NOT NULL,
    defective_units             INT NOT NULL,
    downtime_min                 SMALLINT NOT NULL,
    avg_ideal_cycle_time_sec      DECIMAL(6,2) NOT NULL,
    run_time_min                   DECIMAL(7,1) NOT NULL,
    planned_min                      DECIMAL(7,1) NOT NULL,
    good_units                        INT NOT NULL,
    CONSTRAINT pk_fact_production_shift PRIMARY KEY (date_key, machine_id, shift_id)
);
GO

------------------------------------------------------------------------
-- INVENTORY dimensions & facts
------------------------------------------------------------------------
IF OBJECT_ID('dbo.dim_supplier', 'U') IS NOT NULL DROP TABLE dbo.dim_supplier;
CREATE TABLE dbo.dim_supplier (
    supplier_id      INT          NOT NULL PRIMARY KEY,
    supplier_name    VARCHAR(100) NOT NULL
);
GO

IF OBJECT_ID('dbo.dim_dc', 'U') IS NOT NULL DROP TABLE dbo.dim_dc;
CREATE TABLE dbo.dim_dc (
    dc_id     VARCHAR(20)  NOT NULL PRIMARY KEY,
    dc_name   VARCHAR(20)  NOT NULL,
    region    VARCHAR(20)  NOT NULL
);
GO

IF OBJECT_ID('dbo.dim_category', 'U') IS NOT NULL DROP TABLE dbo.dim_category;
CREATE TABLE dbo.dim_category (
    category_id   INT          NOT NULL PRIMARY KEY,
    category      VARCHAR(50)  NOT NULL
);
GO

IF OBJECT_ID('dbo.dim_sku', 'U') IS NOT NULL DROP TABLE dbo.dim_sku;
CREATE TABLE dbo.dim_sku (
    sku_id         VARCHAR(20)   NOT NULL PRIMARY KEY,
    product_name   VARCHAR(100)  NOT NULL,
    category_id    INT           NOT NULL REFERENCES dbo.dim_category(category_id),
    supplier_id    INT           NOT NULL REFERENCES dbo.dim_supplier(supplier_id),
    unit_price     DECIMAL(8,2)  NOT NULL
);
GO

IF OBJECT_ID('dbo.fact_inventory', 'U') IS NOT NULL DROP TABLE dbo.fact_inventory;
CREATE TABLE dbo.fact_inventory (
    inventory_key             INT           NOT NULL PRIMARY KEY,
    sku_id                    VARCHAR(20)   NOT NULL REFERENCES dbo.dim_sku(sku_id),
    dc_id                     VARCHAR(20)   NOT NULL REFERENCES dbo.dim_dc(dc_id),
    supplier_id               INT           NOT NULL REFERENCES dbo.dim_supplier(supplier_id),
    supplier_lot_id           VARCHAR(20),
    status                    VARCHAR(20)   NOT NULL,
    date_received             DATE,
    last_order_date           DATE,
    expiration_date           DATE,
    stock_quantity            INT           NOT NULL,
    reorder_level             INT           NOT NULL,
    reorder_quantity          INT           NOT NULL,
    sales_volume              INT           NOT NULL,
    vendor_reported_turnover  DECIMAL(6,2),
    recomputed_turnover_rate  DECIMAL(6,2),
    days_of_inventory         DECIMAL(8,1),
    is_below_reorder_point    BIT           NOT NULL,
    revenue_est                DECIMAL(12,2),
    abc_class                  CHAR(1),
    source_address             VARCHAR(200)
);
CREATE INDEX ix_fi_sku ON dbo.fact_inventory(sku_id);
CREATE INDEX ix_fi_dc ON dbo.fact_inventory(dc_id);
GO
