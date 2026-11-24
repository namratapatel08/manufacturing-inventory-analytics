/* =====================================================================
   VALIDATION-ONLY schema (PostgreSQL 16).
   The cloud sandbox used to build this project has no outbound network
   access to Docker Hub / Microsoft Container Registry, so a real SQL
   Server instance could not be provisioned here. This PostgreSQL schema
   is logically identical to sql/sqlserver/01_create_schema.sql and is
   used ONLY to load the real data and execute every KPI query end-to-end
   so the numbers in the README/dashboard are verified, not guessed.
   The T-SQL under sql/sqlserver/ is the actual project deliverable.
   ===================================================================== */

DROP TABLE IF EXISTS fact_inventory CASCADE;
DROP TABLE IF EXISTS dim_sku CASCADE;
DROP TABLE IF EXISTS dim_category CASCADE;
DROP TABLE IF EXISTS dim_dc CASCADE;
DROP TABLE IF EXISTS dim_supplier CASCADE;
DROP TABLE IF EXISTS fact_production_shift CASCADE;
DROP TABLE IF EXISTS fact_production_unit CASCADE;
DROP TABLE IF EXISTS dim_failure_mode CASCADE;
DROP TABLE IF EXISTS dim_product_type CASCADE;
DROP TABLE IF EXISTS dim_shift CASCADE;
DROP TABLE IF EXISTS dim_machine CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;

CREATE TABLE dim_date (
    date_key      DATE        NOT NULL PRIMARY KEY,
    year          SMALLINT    NOT NULL,
    quarter       SMALLINT    NOT NULL,
    month         SMALLINT    NOT NULL,
    month_name    VARCHAR(3)  NOT NULL,
    day           SMALLINT    NOT NULL,
    day_name      VARCHAR(3)  NOT NULL,
    week_of_year  SMALLINT    NOT NULL,
    is_weekend    BOOLEAN     NOT NULL
);

CREATE TABLE dim_machine (
    machine_id       SMALLINT    NOT NULL PRIMARY KEY,
    machine_name     VARCHAR(10) NOT NULL,
    production_line  VARCHAR(20) NOT NULL,
    plant            VARCHAR(50) NOT NULL
);

CREATE TABLE dim_shift (
    shift_id         SMALLINT    NOT NULL PRIMARY KEY,
    shift_name       VARCHAR(10) NOT NULL,
    start_time       VARCHAR(5)  NOT NULL,
    end_time         VARCHAR(5)  NOT NULL
);

CREATE TABLE dim_product_type (
    product_type_code    CHAR(1)     NOT NULL PRIMARY KEY,
    product_type_name    VARCHAR(20) NOT NULL,
    ideal_cycle_time_sec SMALLINT    NOT NULL
);

CREATE TABLE dim_failure_mode (
    failure_mode_code  VARCHAR(4)  NOT NULL PRIMARY KEY,
    failure_mode_name  VARCHAR(40) NOT NULL,
    avg_downtime_min   SMALLINT    NOT NULL
);

CREATE TABLE fact_production_unit (
    unit_id               INT         NOT NULL PRIMARY KEY,
    date_key               DATE       NOT NULL REFERENCES dim_date(date_key),
    machine_id              SMALLINT  NOT NULL REFERENCES dim_machine(machine_id),
    shift_id                 SMALLINT NOT NULL REFERENCES dim_shift(shift_id),
    product_type_code         CHAR(1) NOT NULL REFERENCES dim_product_type(product_type_code),
    product_code               VARCHAR(10),
    air_temp_k                  NUMERIC(6,2),
    process_temp_k                NUMERIC(6,2),
    rotational_speed_rpm            INT,
    torque_nm                        NUMERIC(6,2),
    tool_wear_min                     SMALLINT,
    is_defective                       BOOLEAN NOT NULL,
    failure_mode_code                   VARCHAR(4) NOT NULL REFERENCES dim_failure_mode(failure_mode_code),
    downtime_min                         SMALLINT NOT NULL,
    ideal_cycle_time_sec                  SMALLINT NOT NULL
);
CREATE INDEX ix_fpu_date_machine_shift ON fact_production_unit(date_key, machine_id, shift_id);

CREATE TABLE fact_production_shift (
    date_key                DATE      NOT NULL REFERENCES dim_date(date_key),
    machine_id               SMALLINT NOT NULL REFERENCES dim_machine(machine_id),
    shift_id                  SMALLINT NOT NULL REFERENCES dim_shift(shift_id),
    total_units                 INT NOT NULL,
    defective_units               INT NOT NULL,
    downtime_min                   SMALLINT NOT NULL,
    avg_ideal_cycle_time_sec         NUMERIC(6,2) NOT NULL,
    run_time_min                       NUMERIC(7,1) NOT NULL,
    planned_min                          NUMERIC(7,1) NOT NULL,
    good_units                             INT NOT NULL,
    PRIMARY KEY (date_key, machine_id, shift_id)
);

CREATE TABLE dim_supplier (
    supplier_id    INT          NOT NULL PRIMARY KEY,
    supplier_name  VARCHAR(100) NOT NULL
);

CREATE TABLE dim_dc (
    dc_id    VARCHAR(20) NOT NULL PRIMARY KEY,
    dc_name  VARCHAR(20) NOT NULL,
    region   VARCHAR(20) NOT NULL
);

CREATE TABLE dim_category (
    category_id  INT         NOT NULL PRIMARY KEY,
    category     VARCHAR(50) NOT NULL
);

CREATE TABLE dim_sku (
    sku_id        VARCHAR(20)  NOT NULL PRIMARY KEY,
    product_name  VARCHAR(100) NOT NULL,
    category_id   INT          NOT NULL REFERENCES dim_category(category_id),
    supplier_id   INT          NOT NULL REFERENCES dim_supplier(supplier_id),
    unit_price    NUMERIC(8,2) NOT NULL
);

CREATE TABLE fact_inventory (
    inventory_key             INT           NOT NULL PRIMARY KEY,
    sku_id                    VARCHAR(20)   NOT NULL REFERENCES dim_sku(sku_id),
    dc_id                     VARCHAR(20)   NOT NULL REFERENCES dim_dc(dc_id),
    supplier_id               INT           NOT NULL REFERENCES dim_supplier(supplier_id),
    supplier_lot_id           VARCHAR(20),
    status                    VARCHAR(20)   NOT NULL,
    date_received             DATE,
    last_order_date           DATE,
    expiration_date           DATE,
    stock_quantity            INT           NOT NULL,
    reorder_level             INT           NOT NULL,
    reorder_quantity          INT           NOT NULL,
    sales_volume              INT           NOT NULL,
    vendor_reported_turnover  NUMERIC(6,2),
    recomputed_turnover_rate  NUMERIC(6,2),
    days_of_inventory         NUMERIC(8,1),
    is_below_reorder_point    BOOLEAN       NOT NULL,
    revenue_est               NUMERIC(12,2),
    abc_class                 CHAR(1),
    source_address            VARCHAR(200)
);
CREATE INDEX ix_fi_sku ON fact_inventory(sku_id);
CREATE INDEX ix_fi_dc ON fact_inventory(dc_id);
