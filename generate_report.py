"""
Generates the PBIR report definition (pages + visuals) for the Power BI
Project under powerbi/ManufacturingInventoryDashboard.Report/definition/.

This hand-rolls the PBIR (enhanced report format) JSON schema based on the
publicly documented structure (Microsoft Learn: "Power BI Project (PBIP)
files" / pbi-tools reverse-engineering docs). It was authored without access
to Power BI Desktop (this build sandbox is Linux-only), so treat it as a
strong starting scaffold: if a visual doesn't render exactly as expected,
docs/powerbi_report_guide.md lists the exact fields/measures for every
visual on every page so it can be rebuilt by hand in minutes.

Run: python3 generate_report.py
"""
import json
import os
import uuid

REPORT_DIR = "../powerbi/ManufacturingInventoryDashboard.Report/definition"
PAGE_W, PAGE_H = 1280, 720


def vid():
    return uuid.uuid4().hex[:20]


def measure_field(name):
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": name}},
        "queryRef": f"_Measures.{name}",
        "nativeQueryRef": name,
    }


def column_field(entity, prop):
    return {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": prop,
    }


def visual_container(name, x, y, w, h, visual, tab_order=0):
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.5.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": tab_order, "width": w, "height": h, "tabOrder": tab_order},
        "visual": visual,
    }


def card(title, measure):
    return {
        "visualType": "card",
        "query": {"queryState": {"Values": {"projections": [measure_field(measure)]}}},
        "objects": {
            "labels": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{title}'"}}}}}],
        },
        "title": {"visible": True, "text": title},
    }


def clustered_column(title, category_entity, category_col, measures):
    return {
        "visualType": "clusteredColumnChart",
        "query": {
            "queryState": {
                "Category": {"projections": [column_field(category_entity, category_col)]},
                "Y": {"projections": [measure_field(m) for m in measures]},
            }
        },
        "title": {"visible": True, "text": title},
    }


def line_chart(title, category_entity, category_col, measures):
    return {
        "visualType": "lineChart",
        "query": {
            "queryState": {
                "Category": {"projections": [column_field(category_entity, category_col)]},
                "Y": {"projections": [measure_field(m) for m in measures]},
            }
        },
        "title": {"visible": True, "text": title},
    }


def donut_chart(title, category_entity, category_col, measure):
    return {
        "visualType": "donutChart",
        "query": {
            "queryState": {
                "Category": {"projections": [column_field(category_entity, category_col)]},
                "Y": {"projections": [measure_field(measure)]},
            }
        },
        "title": {"visible": True, "text": title},
    }


def bar_chart(title, category_entity, category_col, measures, series_entity=None, series_col=None):
    cat_proj = [column_field(category_entity, category_col)]
    state = {"Category": {"projections": cat_proj}, "Y": {"projections": [measure_field(m) for m in measures]}}
    if series_entity:
        state["Series"] = {"projections": [column_field(series_entity, series_col)]}
    return {
        "visualType": "barChart",
        "query": {"queryState": state},
        "title": {"visible": True, "text": title},
    }


def table(title, fields):
    """fields: list of (entity, col, is_measure)"""
    projections = []
    for entity, col, is_measure in fields:
        projections.append(measure_field(col) if is_measure else column_field(entity, col))
    return {
        "visualType": "tableEx",
        "query": {"queryState": {"Values": {"projections": projections}}},
        "title": {"visible": True, "text": title},
    }


def slicer(title, entity, col):
    return {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [column_field(entity, col)]}}},
        "title": {"visible": True, "text": title},
    }


def text_box(text):
    return {
        "visualType": "textbox",
        "objects": {
            "general": [{"properties": {"paragraphs": [{"textRuns": [{"value": text}]}]}}]
        },
    }


def write_page(page_id, display_name, ordinal, visuals):
    page_dir = f"{REPORT_DIR}/pages/{page_id}"
    vis_dir = f"{page_dir}/visuals"
    os.makedirs(vis_dir, exist_ok=True)

    page_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.4.0/schema.json",
        "name": page_id,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "height": PAGE_H,
        "width": PAGE_W,
        "ordinal": ordinal,
    }
    with open(f"{page_dir}/page.json", "w") as f:
        json.dump(page_json, f, indent=2)

    for name, x, y, w, h, visual in visuals:
        container = visual_container(name, x, y, w, h, visual)
        vdir = f"{vis_dir}/{name}"
        os.makedirs(vdir, exist_ok=True)
        with open(f"{vdir}/visual.json", "w") as f:
            json.dump(container, f, indent=2)

    print(f"wrote page {page_id} ({len(visuals)} visuals)")


# ---------------------------------------------------------------------------
# PAGE 1 — Executive Summary
# ---------------------------------------------------------------------------
kpi_w, kpi_h = 200, 110
p1_visuals = [
    (vid(), 0, 0, PAGE_W, 40, text_box("Manufacturing & Inventory Analytics — Executive Summary")),
    (vid(), 0, 50, kpi_w, kpi_h, card("Overall OEE", "OEE")),
    (vid(), 210, 50, kpi_w, kpi_h, card("Defect Rate", "Defect Rate")),
    (vid(), 420, 50, kpi_w, kpi_h, card("Avg Stock Turnover", "Avg Stock Turnover")),
    (vid(), 630, 50, kpi_w, kpi_h, card("% SKUs Below Reorder", "% SKUs Below Reorder")),
    (vid(), 840, 50, kpi_w, kpi_h, card("Inventory Revenue", "Total Inventory Revenue")),
    (vid(), 1050, 50, kpi_w, kpi_h, card("Total Units Produced", "Total Units Produced")),
    (vid(), 0, 180, 620, 260, clustered_column("OEE by Machine", "dim_machine", "machine_name", ["OEE"])),
    (vid(), 630, 180, 650, 260, line_chart("OEE Trend by Week", "dim_date", "week_of_year", ["OEE"])),
    (vid(), 0, 450, 620, 260, donut_chart("Inventory Revenue by ABC Class", "fact_inventory", "abc_class", "Total Inventory Revenue")),
    (vid(), 630, 450, 650, 260, bar_chart("Revenue by Category", "dim_category", "category", ["Total Inventory Revenue"])),
]
write_page("ExecutiveSummary", "Executive Summary", 0, p1_visuals)

# ---------------------------------------------------------------------------
# PAGE 2 — Manufacturing OEE Deep Dive
# ---------------------------------------------------------------------------
p2_visuals = [
    (vid(), 0, 0, PAGE_W, 40, text_box("Manufacturing OEE Deep Dive — Plant → Line → Machine → Shift")),
    (vid(), 0, 50, 150, kpi_h, card("Availability", "Availability")),
    (vid(), 160, 50, 150, kpi_h, card("Performance", "Performance (capped)")),
    (vid(), 320, 50, 150, kpi_h, card("Quality", "Quality")),
    (vid(), 480, 50, 150, kpi_h, card("OEE", "OEE")),
    (vid(), 640, 50, 150, kpi_h, card("OEE vs Target", "OEE vs Target")),
    (vid(), 1000, 50, 260, kpi_h,
        slicer("Production Line", "dim_machine", "production_line")),
    (vid(), 0, 180, 620, 260,
        bar_chart("Defect Rate by Machine & Shift", "dim_machine", "machine_name", ["Defect Rate"], "dim_shift", "shift_name")),
    (vid(), 630, 180, 650, 260,
        clustered_column("Downtime Minutes by Failure Mode (Pareto)", "dim_failure_mode", "failure_mode_name", ["Total Downtime (min)"])),
    (vid(), 0, 450, 1280, 260,
        table("Machine-Level OEE Detail", [
            ("dim_machine", "machine_name", False),
            ("dim_machine", "production_line", False),
            ("_Measures", "OEE", True),
            ("_Measures", "Availability", True),
            ("_Measures", "Performance (capped)", True),
            ("_Measures", "Quality", True),
            ("_Measures", "Total Units Produced", True),
            ("_Measures", "Defect Rate", True),
        ])),
]
write_page("ManufacturingOEE", "Manufacturing OEE", 1, p2_visuals)

# ---------------------------------------------------------------------------
# PAGE 3 — Inventory Health
# ---------------------------------------------------------------------------
p3_visuals = [
    (vid(), 0, 0, PAGE_W, 40, text_box("Inventory Health — Warehouse → Category → SKU")),
    (vid(), 0, 50, 190, kpi_h, card("Total Stock On Hand", "Total Stock On Hand")),
    (vid(), 200, 50, 190, kpi_h, card("Total SKUs", "Total SKUs")),
    (vid(), 400, 50, 190, kpi_h, card("Avg Days of Inventory", "Avg Days of Inventory")),
    (vid(), 600, 50, 190, kpi_h, card("Revenue at Risk", "Revenue at Risk (Below Reorder)")),
    (vid(), 800, 50, 460, kpi_h,
        slicer("Distribution Center", "dim_dc", "dc_name")),
    (vid(), 0, 180, 620, 260,
        bar_chart("Avg Stock Turnover by Category", "dim_category", "category", ["Avg Stock Turnover"])),
    (vid(), 630, 180, 650, 260,
        bar_chart("Days of Inventory by Distribution Center", "dim_dc", "dc_name", ["Avg Days of Inventory"])),
    (vid(), 0, 450, 1280, 260,
        table("Reorder Risk — SKUs at or Below Reorder Point", [
            ("fact_inventory", "sku_id", False),
            ("dim_sku", "product_name", False),
            ("dim_category", "category", False),
            ("dim_dc", "dc_name", False),
            ("fact_inventory", "stock_quantity", False),
            ("fact_inventory", "reorder_level", False),
            ("fact_inventory", "status", False),
        ])),
]
write_page("InventoryHealth", "Inventory Health", 2, p3_visuals)

# ---------------------------------------------------------------------------
# pages.json + report.json
# ---------------------------------------------------------------------------
pages_json = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
    "pageOrder": ["ExecutiveSummary", "ManufacturingOEE", "InventoryHealth"],
    "activePageName": "ExecutiveSummary",
}
with open(f"{REPORT_DIR}/pages/pages.json", "w") as f:
    json.dump(pages_json, f, indent=2)

report_json = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.7.0/schema.json",
    "themeCollection": {
        "baseTheme": {
            "name": "CY24SU10",
            "type": "SharedResources",
        }
    },
    "layoutOptimization": "None",
    "publicCustomVisuals": [],
    "resourcePackages": [],
    "settings": {"useStylableVisualContainerHeader": True},
}
with open(f"{REPORT_DIR}/report.json", "w") as f:
    json.dump(report_json, f, indent=2)

print("Done.")
