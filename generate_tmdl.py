"""
Generates the Power BI Project (PBIP) semantic-model TMDL table files from
the processed star-schema CSVs, so column lists/types always match the real
data exactly. Measures, relationships, model.tmdl, database.tmdl and the
report (PBIR) files are hand-authored separately (see powerbi/ and
docs/powerbi_report_guide.md).

Run: python3 generate_tmdl.py
"""
import uuid
import pandas as pd
import os

PROCESSED = "../data/processed"
OUT_DIR = "../powerbi/ManufacturingInventoryDashboard.SemanticModel/definition/tables"
os.makedirs(OUT_DIR, exist_ok=True)

# table -> (display name in model, description)
TABLES = {
    "dim_date": "Date dimension shared by both domains.",
    "dim_machine": "Manufacturing machine / production line dimension.",
    "dim_shift": "Production shift dimension (Day / Night).",
    "dim_product_type": "Product tier dimension (Economy/Standard/Premium).",
    "dim_failure_mode": "Machine failure-mode dimension.",
    "fact_production_unit": "Grain: 1 manufactured unit. Sensor readings + defect/failure detail.",
    "fact_production_shift": "Grain: machine x shift x date. Pre-aggregated OEE inputs.",
    "dim_supplier": "Inventory supplier dimension.",
    "dim_dc": "Distribution-center dimension.",
    "dim_category": "Product category dimension.",
    "dim_sku": "SKU / product master dimension.",
    "fact_inventory": "Grain: 1 SKU-lot inventory snapshot record.",
}

DATE_COLS = {"date_key", "date_received", "last_order_date", "expiration_date"}

def m_type(dtype: str, colname: str) -> tuple[str, str]:
    """Return (TMDL dataType, Power Query type literal) for a pandas dtype."""
    if colname in DATE_COLS:
        return "dateTime", "type date"
    if dtype == "int64":
        return "int64", "Int64.Type"
    if dtype == "float64":
        return "double", "type number"
    if dtype == "bool":
        return "boolean", "type logical"
    return "string", "type text"

def fmt_string(dtype: str, colname: str) -> str | None:
    if colname in DATE_COLS:
        return "Long Date"
    if dtype == "int64":
        return "0"
    if dtype == "float64":
        return "0.00"
    return None

def summarize_by(dtype: str, colname: str) -> str:
    # Keys / codes / flags should not auto-sum in visuals
    if colname.endswith("_id") or colname.endswith("_code") or colname.endswith("_key"):
        return "none"
    if dtype in ("int64", "float64") and not colname.endswith("_id"):
        return "sum" if colname in {
            "total_units", "defective_units", "good_units", "downtime_min",
            "stock_quantity", "sales_volume", "revenue_est", "reorder_quantity",
        } else "none"
    return "none"

def write_table_tmdl(name: str, df: pd.DataFrame, description: str):
    lines = []
    lines.append(f"table {name}")
    lines.append(f"\tlineageTag: {uuid.uuid4()}")
    lines.append("")
    for col in df.columns:
        dtype = str(df[col].dtype)
        tmdl_type, pq_type = m_type(dtype, col)
        lines.append(f"\tcolumn {col}")
        lines.append(f"\t\tdataType: {tmdl_type}")
        fs = fmt_string(dtype, col)
        if fs:
            lines.append(f"\t\tformatString: {fs}")
        lines.append(f"\t\tlineageTag: {uuid.uuid4()}")
        lines.append(f"\t\tsummarizeBy: {summarize_by(dtype, col)}")
        lines.append(f"\t\tsourceColumn: {col}")
        lines.append("")
        lines.append("\t\tannotation SummarizationSetBy = Automatic")
        lines.append("")

    # partition: M query loads from the processed CSV via a shared folder parameter
    col_types_m = ", ".join(
        f'{{"{c}", {m_type(str(df[c].dtype), c)[1]}}}' for c in df.columns
    )
    lines.append(f"\tpartition {name} = m")
    lines.append("\t\tmode: import")
    lines.append("\t\tsource =")
    lines.append("\t\t\t\tlet")
    lines.append(f'\t\t\t\t    Source = Csv.Document(File.Contents(ProcessedDataFolder & "{name}.csv"),[Delimiter=",", Columns={len(df.columns)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),')
    lines.append('\t\t\t\t    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),')
    lines.append(f'\t\t\t\t    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",{{{col_types_m}}})')
    lines.append("\t\t\t\tin")
    lines.append('\t\t\t\t    #"Changed Type"')
    lines.append("")
    lines.append(f"\tannotation PBI_ResultType = Table")
    lines.append("")

    with open(f"{OUT_DIR}/{name}.tmdl", "w") as f:
        f.write("\n".join(lines))
    print(f"wrote {name}.tmdl ({len(df.columns)} cols, {len(df)} rows)")

for tbl, desc in TABLES.items():
    df = pd.read_csv(f"{PROCESSED}/{tbl}.csv")
    write_table_tmdl(tbl, df, desc)

print("Done.")
