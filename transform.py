"""
ETL: Transform raw public datasets into a star-schema warehouse
for the Manufacturing & Inventory Analytics dashboard.

Sources (raw, unmodified, saved under data/raw/):
  1. ai4i2020.csv        - AI4I 2020 Predictive Maintenance Dataset (UCI ML Repository,
                            CC BY 4.0). 10,000 real sensor/production readings for a
                            milling process: temperatures, rotational speed, torque,
                            tool wear, and 5 machine-failure flags.
                            https://archive.ics.uci.edu/dataset/601
  2. grocery_inventory.csv - Grocery Inventory dataset (public, MIT-licensed GitHub
                            mirror of a Kaggle-style grocery/retail inventory dataset).
                            990 SKU-level inventory records: stock on hand, reorder
                            points, supplier, category, sales volume.
                            https://github.com/piumalnipun9/Inventory-Management-Forecasting-using-Machine-Learning

Neither source dataset ships OEE-ready fields (planned time, downtime minutes,
ideal cycle time) or a true multi-warehouse structure out of the box, so this
script applies a small, fully-documented set of business rules to derive a
production-grade star schema on top of the *real* raw values. All derived
columns are clearly named `derived_*` or documented below and in
docs/data_dictionary.md so nothing is hidden. No source measurement
(temperature, torque, tool wear, stock quantity, sales volume, price, ...) is
invented -- only the operational context needed to compute OEE / stock KPIs
(machine, shift, calendar date, distribution center) is assigned.

Run: python3 transform.py
Outputs CSVs into data/processed/ ready to bulk-load into SQL Server / Postgres.
"""
import hashlib
import re
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

RAW = "../data/raw"
OUT = "../data/processed"
SEED = 42
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# 1. MANUFACTURING DOMAIN  (source: ai4i2020.csv)
# ---------------------------------------------------------------------------
ai4i = pd.read_csv(f"{RAW}/ai4i2020.csv")
ai4i.columns = [c.strip() for c in ai4i.columns]
ai4i = ai4i.rename(columns={
    "UDI": "udi",
    "Product ID": "product_code",
    "Type": "product_type",
    "Air temperature [K]": "air_temp_k",
    "Process temperature [K]": "process_temp_k",
    "Rotational speed [rpm]": "rotational_speed_rpm",
    "Torque [Nm]": "torque_nm",
    "Tool wear [min]": "tool_wear_min",
    "Machine failure": "is_defective",
    "TWF": "twf", "HDF": "hdf", "PWF": "pwf", "OSF": "osf", "RNF": "rnf",
})

N_MACHINES = 6
SHIFTS = [(1, "Day", "06:00", "14:30"), (2, "Night", "14:30", "23:00")]
PROD_START = datetime(2026, 1, 5)
N_DAYS = 84  # ~12 weeks (one quarter) of production history for trend charts

# --- derived operational context (documented business rules) --------------
# machine / shift / day are assigned via independent hashes of the unit id so
# the three dimensions are statistically decorrelated (a naive udi % N
# assignment made shift a deterministic function of machine, collapsing the
# machine x shift x date grid to 1/4 of its cells -- caught during validation
# and fixed here).
def _stable_int(udi: int, salt: str, mod: int) -> int:
    h = hashlib.md5(f"{salt}-{udi}".encode()).hexdigest()
    return int(h, 16) % mod

ai4i["derived_machine_id"] = ai4i["udi"].apply(lambda u: _stable_int(u, "machine", N_MACHINES) + 1)
ai4i["derived_shift_id"] = ai4i["udi"].apply(lambda u: _stable_int(u, "shift", 2) + 1)
ai4i["derived_day_offset"] = ai4i["udi"].apply(lambda u: _stable_int(u, "day", N_DAYS))
ai4i["derived_date"] = ai4i["derived_day_offset"].apply(lambda d: (PROD_START + timedelta(days=int(d))).date())

CYCLE_TIME_SEC = {"L": 18, "M": 25, "H": 35}       # ideal cycle time by product tier
# Minutes lost per individual failure event (a single unit's tool change /
# reset / restart), not a whole-shift outage -- these are small batches
# (~40 units), so event downtime is scaled accordingly.
DOWNTIME_MIN = {"twf": 8, "hdf": 12, "pwf": 15, "osf": 10, "rnf": 5}

ai4i["derived_ideal_cycle_time_sec"] = ai4i["product_type"].map(CYCLE_TIME_SEC)
ai4i["derived_downtime_min"] = (
    ai4i["twf"] * DOWNTIME_MIN["twf"] + ai4i["hdf"] * DOWNTIME_MIN["hdf"] +
    ai4i["pwf"] * DOWNTIME_MIN["pwf"] + ai4i["osf"] * DOWNTIME_MIN["osf"] +
    ai4i["rnf"] * DOWNTIME_MIN["rnf"]
)

def failure_mode(row):
    for code in ["twf", "hdf", "pwf", "osf", "rnf"]:
        if row[code] == 1:
            return code.upper()
    return "RNF" if row["is_defective"] == 1 else "NONE"

ai4i["derived_failure_mode"] = ai4i.apply(failure_mode, axis=1)

# dim_machine ----------------------------------------------------------------
LINES = {1: "Line A", 2: "Line A", 3: "Line B", 4: "Line B", 5: "Line C", 6: "Line C"}
dim_machine = pd.DataFrame({
    "machine_id": range(1, N_MACHINES + 1),
    "machine_name": [f"MCH-{i:02d}" for i in range(1, N_MACHINES + 1)],
    "production_line": [LINES[i] for i in range(1, N_MACHINES + 1)],
    "plant": "Plant 1 - Springfield",
})

# dim_shift --------------------------------------------------------------
# Note: planned production minutes are NOT fixed here -- batch size varies
# by machine/shift/date, so planned time is derived per-bucket below from
# actual throughput (see fact_production_shift).
dim_shift = pd.DataFrame({
    "shift_id": [s[0] for s in SHIFTS],
    "shift_name": [s[1] for s in SHIFTS],
    "start_time": [s[2] for s in SHIFTS],
    "end_time": [s[3] for s in SHIFTS],
})

# dim_product_type ---------------------------------------------------------
dim_product_type = pd.DataFrame({
    "product_type_code": ["L", "M", "H"],
    "product_type_name": ["Economy", "Standard", "Premium"],
    "ideal_cycle_time_sec": [CYCLE_TIME_SEC["L"], CYCLE_TIME_SEC["M"], CYCLE_TIME_SEC["H"]],
})

# dim_failure_mode -----------------------------------------------------------
dim_failure_mode = pd.DataFrame({
    "failure_mode_code": ["NONE", "TWF", "HDF", "PWF", "OSF", "RNF"],
    "failure_mode_name": [
        "No failure", "Tool Wear Failure", "Heat Dissipation Failure",
        "Power Failure", "Overstrain Failure", "Random Failure",
    ],
    "avg_downtime_min": [0, DOWNTIME_MIN["twf"], DOWNTIME_MIN["hdf"], DOWNTIME_MIN["pwf"],
                          DOWNTIME_MIN["osf"], DOWNTIME_MIN["rnf"]],
})

# fact_production_unit (grain: 1 row = 1 manufactured unit) ------------------
fact_production_unit = ai4i[[
    "udi", "derived_date", "derived_machine_id", "derived_shift_id", "product_type",
    "product_code", "air_temp_k", "process_temp_k", "rotational_speed_rpm", "torque_nm",
    "tool_wear_min", "is_defective", "derived_failure_mode", "derived_downtime_min",
    "derived_ideal_cycle_time_sec",
]].rename(columns={
    "udi": "unit_id", "derived_date": "date_key", "derived_machine_id": "machine_id",
    "derived_shift_id": "shift_id", "product_type": "product_type_code",
    "derived_failure_mode": "failure_mode_code", "derived_downtime_min": "downtime_min",
    "derived_ideal_cycle_time_sec": "ideal_cycle_time_sec",
})

# fact_production_shift (grain: machine x shift x date, pre-aggregated for fast OEE) --
# Planned production time is derived, not assumed: we know actual output
# (total_units) and each product's ideal cycle time, so "ideal run time" =
# units x ideal cycle time. Real lines never run at 100% of ideal speed even
# outside of logged failure events (minor stops, material handling, small
# speed losses) -- we apply a per-bucket, per-machine "speed factor" drawn
# from a realistic Normal(0.83, 0.06) distribution (typical of discrete
# manufacturing) to derive actual run time, then planned time = run time +
# logged failure downtime. This is the one fully-synthetic input in the
# manufacturing model (documented in docs/data_dictionary.md); every other
# quantity used in the OEE formula -- unit counts, cycle time, downtime,
# good/defective split -- is derived directly from the real AI4I2020 values.
agg = fact_production_unit.groupby(["date_key", "machine_id", "shift_id"]).agg(
    total_units=("unit_id", "count"),
    defective_units=("is_defective", "sum"),
    downtime_min=("downtime_min", "sum"),
    avg_ideal_cycle_time_sec=("ideal_cycle_time_sec", "mean"),
).reset_index()

speed_factor = rng.normal(0.83, 0.06, size=len(agg)).clip(0.65, 0.97)
ideal_run_time_min = (agg["avg_ideal_cycle_time_sec"] * agg["total_units"]) / 60.0
agg["run_time_min"] = (ideal_run_time_min / speed_factor).round(1)
agg["planned_min"] = (agg["run_time_min"] + agg["downtime_min"]).round(1)
agg["good_units"] = agg["total_units"] - agg["defective_units"]
fact_production_shift = agg

# ---------------------------------------------------------------------------
# 2. INVENTORY DOMAIN  (source: grocery_inventory.csv)
# ---------------------------------------------------------------------------
inv = pd.read_csv(f"{RAW}/grocery_inventory.csv")
inv.columns = [c.strip() for c in inv.columns]
inv = inv.rename(columns={"Catagory": "category"})
inv["category"] = inv["category"].fillna("Uncategorized")
inv["Unit_Price"] = inv["Unit_Price"].str.replace("$", "", regex=False).astype(float)
for c in ["Date_Received", "Last_Order_Date", "Expiration_Date"]:
    inv[c] = pd.to_datetime(inv[c], errors="coerce")

# --- derived distribution-center dimension ---------------------------------
# Source data has a unique street address per row (no real facility grouping),
# so we deterministically bucket each SKU-lot into one of 5 named distribution
# centers using a stable hash of Product_ID. The original street address is
# preserved as `source_address` for traceability.
DCS = ["DC-East", "DC-West", "DC-Central", "DC-North", "DC-South"]

def dc_for(pid: str) -> str:
    h = int(hashlib.md5(pid.encode()).hexdigest(), 16)
    return DCS[h % len(DCS)]

inv["derived_dc"] = inv["Product_ID"].apply(dc_for)

# --- recomputed inventory turnover -----------------------------------------
# The source `Inventory_Turnover_Rate` column is statistically indistinguishable
# from noise (uniform ~1-100, independent of Stock_Quantity/Sales_Volume) --
# see docs/data_dictionary.md for the check. We keep it as
# `vendor_reported_turnover` for traceability and compute a proper metric:
#   turnover_rate = Sales_Volume / Average_Inventory
#   Average_Inventory ~= (Stock_Quantity + Reorder_Level) / 2   [documented approximation,
#     dataset is a point-in-time snapshot with no opening-balance history]
inv["avg_inventory_est"] = (inv["Stock_Quantity"] + inv["Reorder_Level"]) / 2.0
inv["recomputed_turnover_rate"] = (inv["Sales_Volume"] / inv["avg_inventory_est"]).round(2)
inv["days_of_inventory"] = (365 / inv["recomputed_turnover_rate"].replace(0, np.nan)).round(1)
inv["is_below_reorder_point"] = inv["Stock_Quantity"] <= inv["Reorder_Level"]
inv["revenue_est"] = inv["Unit_Price"] * inv["Sales_Volume"]

# ABC classification (revenue-based Pareto: A = top ~70% of cumulative
# revenue, B = next ~20%, C = remaining ~10%) -- computed once here so the
# same, already SQL-validated logic (sql/*/03_kpi_views.sql vw_inventory_abc)
# is available directly as a column for Power BI / simple reporting tools.
inv_sorted = inv.sort_values("revenue_est", ascending=False).copy()
inv_sorted["cum_revenue_pct"] = inv_sorted["revenue_est"].cumsum() / inv_sorted["revenue_est"].sum()
inv_sorted["abc_class"] = pd.cut(inv_sorted["cum_revenue_pct"], bins=[0, 0.70, 0.90, 1.0 + 1e-9],
                                  labels=["A", "B", "C"])
inv = inv.merge(inv_sorted[["Product_ID", "abc_class"]], on="Product_ID", how="left")

# NOTE: Supplier_ID in the source is a unique per-row lot identifier, not a
# true supplier master key (350 distinct Supplier_Name values share it across
# multiple Supplier_IDs). We build the supplier dimension on Supplier_Name and
# keep the original Supplier_ID on the fact row as `supplier_lot_id` for
# traceability back to the source file.
dim_supplier = pd.DataFrame({"supplier_name": sorted(inv["Supplier_Name"].dropna().unique())})
dim_supplier["supplier_id"] = range(1, len(dim_supplier) + 1)
dim_supplier = dim_supplier[["supplier_id", "supplier_name"]]
inv = inv.merge(dim_supplier, left_on="Supplier_Name", right_on="supplier_name", how="left")
inv = inv.rename(columns={"Supplier_ID": "supplier_lot_id", "supplier_id": "resolved_supplier_id"})

dim_dc = pd.DataFrame({"dc_id": DCS, "dc_name": DCS,
                        "region": ["East", "West", "Central", "North", "South"]})

dim_category = pd.DataFrame({"category": sorted(inv["category"].dropna().unique())})
dim_category["category_id"] = range(1, len(dim_category) + 1)
dim_category = dim_category[["category_id", "category"]]

dim_sku = inv[["Product_ID", "Product_Name", "category", "resolved_supplier_id", "Unit_Price"]].rename(
    columns={"Product_ID": "sku_id", "Product_Name": "product_name",
             "resolved_supplier_id": "supplier_id", "Unit_Price": "unit_price"})
dim_sku = dim_sku.merge(dim_category, on="category", how="left")[
    ["sku_id", "product_name", "category_id", "supplier_id", "unit_price"]]

fact_inventory = inv[[
    "Product_ID", "derived_dc", "resolved_supplier_id", "supplier_lot_id", "Status",
    "Date_Received", "Last_Order_Date", "Expiration_Date",
    "Stock_Quantity", "Reorder_Level", "Reorder_Quantity", "Sales_Volume",
    "Inventory_Turnover_Rate", "recomputed_turnover_rate", "days_of_inventory",
    "is_below_reorder_point", "revenue_est", "abc_class", "Warehouse_Location",
]].rename(columns={
    "Product_ID": "sku_id", "derived_dc": "dc_id", "resolved_supplier_id": "supplier_id",
    "Status": "status", "Date_Received": "date_received", "Last_Order_Date": "last_order_date",
    "Expiration_Date": "expiration_date", "Stock_Quantity": "stock_quantity",
    "Reorder_Level": "reorder_level", "Reorder_Quantity": "reorder_quantity",
    "Sales_Volume": "sales_volume", "Inventory_Turnover_Rate": "vendor_reported_turnover",
    "Warehouse_Location": "source_address",
})
fact_inventory.insert(0, "inventory_key", range(1, len(fact_inventory) + 1))

# ---------------------------------------------------------------------------
# 3. SHARED dim_date (covers both domains)
# ---------------------------------------------------------------------------
all_dates = pd.concat([
    pd.Series(pd.to_datetime(fact_production_shift["date_key"])),
    inv["Date_Received"].dropna(),
    inv["Last_Order_Date"].dropna(),
])
d_min, d_max = all_dates.min(), all_dates.max()
dim_date = pd.DataFrame({"date_key": pd.date_range(d_min, d_max, freq="D")})
dim_date["date_key"] = dim_date["date_key"].dt.date
dd = pd.to_datetime(dim_date["date_key"])
dim_date["year"] = dd.dt.year
dim_date["quarter"] = dd.dt.quarter
dim_date["month"] = dd.dt.month
dim_date["month_name"] = dd.dt.strftime("%b")
dim_date["day"] = dd.dt.day
dim_date["day_name"] = dd.dt.strftime("%a")
dim_date["week_of_year"] = dd.dt.isocalendar().week.astype(int)
dim_date["is_weekend"] = dd.dt.dayofweek >= 5

# ---------------------------------------------------------------------------
# WRITE OUTPUTS
# ---------------------------------------------------------------------------
tables = {
    "dim_date": dim_date,
    "dim_machine": dim_machine,
    "dim_shift": dim_shift,
    "dim_product_type": dim_product_type,
    "dim_failure_mode": dim_failure_mode,
    "fact_production_unit": fact_production_unit,
    "fact_production_shift": fact_production_shift,
    "dim_supplier": dim_supplier,
    "dim_dc": dim_dc,
    "dim_category": dim_category,
    "dim_sku": dim_sku,
    "fact_inventory": fact_inventory,
}

import os
os.makedirs(OUT, exist_ok=True)
for name, df in tables.items():
    df.to_csv(f"{OUT}/{name}.csv", index=False)
    print(f"{name:24s} {len(df):>6d} rows  {list(df.columns)}")

print("\nDone. Processed tables written to", OUT)
