"""
Export Engine — VEDANSHU Product Packet Analyser.

Generates downloadable reports from analysis results in two formats:
  - CSV  : UTF-8 with BOM (Excel-compatible) spreadsheet with verified values,
           data coverage notes, allergen classification, and risk alerts.
  - PDF  : Formatted A4 report using reportlab (with fallback to plain-text
           if reportlab is not installed).

Never fabricates default scores or presents unverified recipe titles as commercial products.
"""

import io
import csv
from datetime import datetime
from typing import Dict, Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# CSV Export
# ─────────────────────────────────────────────────────────────────────────────

def generate_csv(results: Dict[str, Any]) -> bytes:
    """
    Generates a UTF-8 CSV report from analysis results.

    Sections (separated by blank rows):
      1. Product Info & Content Classification
      2. Health Score & Data Coverage
      3. Nutrition Values (per 100g and per serving)
      4. Risk Alerts (Quantitative)
      5. Ingredient Flags
      6. Allergen Detection (Declared vs Precautionary)

    Returns bytes with UTF-8 BOM for Excel compatibility.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    fields = results.get("fields", {})
    nutrients = results.get("nutrients", {})
    risk = results.get("risk_analysis", {})
    allergen = results.get("allergen_analysis", {})
    score = results.get("health_score", {})
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Header ──────────────────────────────────────────────────────────────
    writer.writerow(["VEDANSHU PRODUCT PACKET ANALYSER — VERIFIED ANALYSIS REPORT"])
    writer.writerow([f"Generated: {now}"])
    if results.get("is_demo"):
        writer.writerow(["DATA SOURCE: Sample Demonstration Packet"])
    writer.writerow([])

    # ── 1. Product Info ──────────────────────────────────────────────────────
    writer.writerow(["SECTION 1: PRODUCT IDENTIFICATION"])
    writer.writerow(["Field", "Value", "Extraction Status"])

    content_type = fields.get("content_type", "packaged_food")
    type_display = "Commercial Food Package" if content_type == "packaged_food" else content_type.title()
    writer.writerow(["Document Classification", type_display, "Verified"])

    for key, label in [
        ("product_name",     "Product Name"),
        ("product_category", "Category"),
        ("brand_name",       "Brand"),
        ("mrp",              "MRP"),
        ("mfg_date",         "Manufacturing Date"),
        ("pack_date",        "Packaging Date"),
        ("expiry_date",      "Expiry Date"),
        ("best_before",      "Best Before"),
        ("serving_size",     "Serving Size"),
        ("net_quantity",     "Net Quantity"),
    ]:
        val = fields.get(key)
        status = "Detected" if val else ("N/A (Recipe)" if content_type == "recipe" else "Not detected")
        writer.writerow([label, val or "Not detected", status])

    writer.writerow(["Ingredients Listing", fields.get("ingredients") or "Not detected", "Detected" if fields.get("ingredients") else "Not detected"])
    writer.writerow([])

    # ── 2. Health Score ──────────────────────────────────────────────────────
    if score:
        writer.writerow(["SECTION 2: HEALTH SCORE EVALUATION"])
        s_val = score.get("score")
        score_str = f"{s_val}/100" if s_val is not None else "Insufficient Data (Not calculated)"
        writer.writerow(["Score", "Grade", "Status / Label", "Data Coverage", "Summary"])
        writer.writerow([
            score_str,
            score.get("grade") or "N/A",
            score.get("grade_label", "N/A"),
            f"{score.get('detected_count', 0)}/{score.get('total_count', 6)} nutrients detected",
            score.get("summary", ""),
        ])
        writer.writerow([])
        writer.writerow(["Component Breakdown"])
        writer.writerow(["Nutrient", "Value", "Unit", "Component Score (/100)", "Weight (%)", "Evaluation Status"])
        for c in score.get("components", []):
            c_score = c.get("component_score")
            c_score_str = str(c_score) if c_score is not None else "N/A"
            writer.writerow([
                c["nutrient"],
                c["value"] if c["value"] is not None else "Not detected",
                c["unit"],
                c_score_str,
                c["weight"],
                "Evaluated" if c.get("detected") else "Not detected (Excluded from score)",
            ])
        writer.writerow([])

    # ── 3. Nutrition Values ──────────────────────────────────────────────────
    writer.writerow(["SECTION 3: NUTRITION FACTS"])
    writer.writerow(["Nutrient Component", "Value per 100g", "Value per Serving", "Unit", "Serving Basis", "Validation Warning"])
    for name, data in nutrients.items():
        val = data.get("value")
        val_serve = data.get("per_serving_value")
        warn = data.get("plausibility_warning") or ""
        writer.writerow([
            name,
            val if val is not None else "Not detected",
            val_serve if val_serve is not None else "-",
            data.get("unit", "-"),
            data.get("serving_basis", "per 100g"),
            warn,
        ])
    writer.writerow([])

    # ── 4. Risk Alerts ───────────────────────────────────────────────────────
    writer.writerow(["SECTION 4: QUANTITATIVE NUTRITION ALERTS (per 100g benchmarks)"])
    writer.writerow(["Nutrient", "Status", "Extracted Value", "Reference Threshold", "Basis Warning", "Guideline Source"])
    for alert in risk.get("quantitative_alerts", []):
        writer.writerow([
            alert.get("nutrient", ""),
            alert.get("status", ""),
            alert.get("value_display", ""),
            alert.get("threshold_text", ""),
            alert.get("basis_warning") or "None",
            alert.get("source", ""),
        ])
    writer.writerow([])

    # ── 5. Ingredient Flags ──────────────────────────────────────────────────
    writer.writerow(["SECTION 5: INGREDIENT CONCERN FLAGS"])
    ing_flags = risk.get("ingredient_flags", [])
    if ing_flags:
        writer.writerow(["Flag Name", "Category", "Severity", "Matching Terms Found", "Advisory Suggestion"])
        for flag in ing_flags:
            writer.writerow([
                flag.get("name", ""),
                flag.get("category", ""),
                flag.get("severity", ""),
                ", ".join(flag.get("found_terms", [])),
                flag.get("suggestion", ""),
            ])
    else:
        writer.writerow(["No flagged ingredients detected in the readable ingredients listing."])
    writer.writerow([])

    # ── 6. Allergen Detection ────────────────────────────────────────────────
    writer.writerow(["SECTION 6: ALLERGEN DETECTION"])
    if allergen.get("ingredients_available"):
        writer.writerow(["Allergen", "Allergen Type", "Category", "Matching Terms Found", "Severity"])
        # Declared
        for a in allergen.get("declared_allergens", []):
            writer.writerow([
                a.get("name", ""),
                "CONTAINS (Declared Ingredient)",
                a.get("category", ""),
                ", ".join(a.get("found_terms", [])),
                a.get("severity", ""),
            ])
        # Precautionary
        for a in allergen.get("precautionary_allergens", []):
            writer.writerow([
                a.get("name", ""),
                "MAY CONTAIN (Cross-contact Risk)",
                a.get("category", ""),
                ", ".join(a.get("found_terms", [])),
                a.get("severity", ""),
            ])
        for name in allergen.get("allergens_clear", []):
            writer.writerow([name, "NOT DETECTED in text", "-", "-", "-"])
    else:
        writer.writerow(["UNKNOWN: No readable ingredients text detected in the image."])
    writer.writerow([])

    # ── Disclaimer ───────────────────────────────────────────────────────────
    writer.writerow(["REGULATORY & MEDICAL DISCLAIMER"])
    writer.writerow([
        "This automated report is for educational and informational purposes only. "
        "It is not a substitute for reading the physical label, nor does it constitute "
        "medical, nutritional, or regulatory advice. Always verify directly on packaging."
    ])

    return output.getvalue().encode("utf-8-sig")


# ─────────────────────────────────────────────────────────────────────────────
# PDF Export
# ─────────────────────────────────────────────────────────────────────────────

def _pdf_with_reportlab(results: Dict[str, Any]) -> bytes:
    """Generates a styled A4 PDF report using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )

    fields    = results.get("fields", {})
    nutrients = results.get("nutrients", {})
    risk      = results.get("risk_analysis", {})
    allergen  = results.get("allergen_analysis", {})
    score     = results.get("health_score", {})
    now       = datetime.now().strftime("%d %b %Y  %H:%M")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "VTitle",
        parent=styles["Title"],
        fontSize=18, leading=22,
        textColor=colors.HexColor("#0B1220"),
        spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "VSubtitle",
        parent=styles["Normal"],
        fontSize=9, leading=13,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "VSection",
        parent=styles["Heading2"],
        fontSize=11, leading=15,
        textColor=colors.HexColor("#0E7490"),
        spaceBefore=12, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "VBody",
        parent=styles["Normal"],
        fontSize=8.5, leading=12,
        textColor=colors.HexColor("#1E293B"),
    )
    small_style = ParagraphStyle(
        "VSmall",
        parent=styles["Normal"],
        fontSize=7.5, leading=11,
        textColor=colors.HexColor("#64748B"),
        italic=True,
    )

    def _base_table_style(header_bg=colors.HexColor("#0E7490")):
        return TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
            ("TOPPADDING",  (0, 0), (-1, 0), 5),
            ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",    (0, 1), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#F8FAFC"), colors.HexColor("#FFFFFF")]),
            ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",  (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ])

    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    p_name = fields.get("product_name") or "Unspecified Product"
    story.append(Paragraph("VEDANSHU — Product Packet Analyser", title_style))
    story.append(Paragraph(f"Analysis Report · {now}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=colors.HexColor("#0E7490"), spaceAfter=10))

    # ── 1. Product Identification ────────────────────────────────────────────
    story.append(Paragraph("1. Product Information", section_style))
    prod_data = [["Field", "Value"]]
    content_type = fields.get("content_type", "packaged_food")
    if content_type == "recipe":
        prod_data.append(["Classification", "RECIPE DOCUMENT (Not commercial packaged goods)"])

    for key, label in [
        ("product_name",     "Product Name"),
        ("product_category", "Category"),
        ("brand_name",       "Brand"),
        ("mrp",              "MRP"),
        ("mfg_date",         "Mfg Date"),
        ("pack_date",        "Pack Date"),
        ("expiry_date",      "Expiry Date"),
        ("best_before",      "Best Before"),
        ("serving_size",     "Serving Size"),
        ("net_quantity",     "Net Quantity"),
    ]:
        val = fields.get(key) or ("Not applicable (recipe)" if content_type == "recipe" else "Not detected")
        prod_data.append([label, str(val)])

    t_prod = Table(prod_data, colWidths=[4*cm, 13.4*cm])
    t_prod.setStyle(_base_table_style())
    story.append(t_prod)

    # Ingredients
    ing = fields.get("ingredients")
    if ing:
        story.append(Spacer(1, 6))
        story.append(Paragraph("<b>Ingredients Listing:</b>", body_style))
        story.append(Paragraph(ing, body_style))

    # ── 2. Health Score ──────────────────────────────────────────────────────
    if score:
        story.append(Paragraph("2. Health Score Evaluation", section_style))
        s_val = score.get("score")
        if s_val is not None:
            score_disp = f"{s_val}/100"
            s_color = colors.HexColor(score.get("color", "#34D399"))
        else:
            score_disp = "Insufficient Data"
            s_color = colors.HexColor("#64748B")

        score_table_data = [
            ["Health Score", "Grade", "Status / Label", "Summary"],
            [
                score_disp,
                score.get("grade") or "N/A",
                score.get("grade_label") or "Insufficient Data",
                score.get("summary", ""),
            ]
        ]
        t_score = Table(score_table_data, colWidths=[3*cm, 2*cm, 3.5*cm, 8.9*cm])
        ts_score = _base_table_style()
        ts_score.add("TEXTCOLOR", (0, 1), (1, 1), s_color)
        ts_score.add("FONTNAME",  (0, 1), (1, 1), "Helvetica-Bold")
        t_score.setStyle(ts_score)
        story.append(t_score)
        story.append(Paragraph(f"<i>Note: {score.get('note', '')}</i>", small_style))

    # ── 3. Nutrition Facts ───────────────────────────────────────────────────
    story.append(Paragraph("3. Nutrition Values (per 100g)", section_style))
    nut_data = [["Nutrient Component", "Value (per 100g)", "Unit", "Serving Basis"]]
    for name, data in nutrients.items():
        val = data.get("value")
        nut_data.append([
            name,
            str(val) if val is not None else "Not detected",
            data.get("unit", "-"),
            data.get("serving_basis", "per 100g"),
        ])
    t_nut = Table(nut_data, colWidths=[5.5*cm, 3.5*cm, 2.5*cm, 5.9*cm])
    t_nut.setStyle(_base_table_style())
    story.append(t_nut)

    # ── 4. Quantitative Alerts ───────────────────────────────────────────────
    story.append(Paragraph("4. Quantitative Risk Alerts", section_style))
    alerts = risk.get("quantitative_alerts", [])
    if alerts:
        risk_data = [["Nutrient", "Status", "Value", "Threshold Benchmark", "Source"]]
        status_colors = {
            "HIGH":     colors.HexColor("#DC2626"),
            "MODERATE": colors.HexColor("#D97706"),
            "OK":       colors.HexColor("#059669"),
            "UNKNOWN":  colors.HexColor("#64748B"),
        }
        for alert in alerts:
            risk_data.append([
                alert.get("nutrient", ""),
                alert.get("status", ""),
                alert.get("value_display", ""),
                alert.get("threshold_text", ""),
                alert.get("source", ""),
            ])
        t_risk = Table(risk_data, colWidths=[3.5*cm, 2.4*cm, 3.2*cm, 5.3*cm, 3.0*cm])
        ts_risk = _base_table_style()
        for idx, alert in enumerate(alerts, start=1):
            sc = status_colors.get(alert.get("status", ""), colors.HexColor("#64748B"))
            ts_risk.add("TEXTCOLOR", (1, idx), (1, idx), sc)
            ts_risk.add("FONTNAME",  (1, idx), (1, idx), "Helvetica-Bold")
        t_risk.setStyle(ts_risk)
        story.append(t_risk)

    # ── 5. Allergen Detection ────────────────────────────────────────────────
    story.append(Paragraph("5. Allergen Detection", section_style))
    if allergen.get("ingredients_available"):
        all_data = [["Allergen Category", "Classification", "Found Terms in OCR"]]
        has_items = False
        for a in allergen.get("declared_allergens", []):
            all_data.append([a.get("name", ""), "CONTAINS (Ingredient)", ", ".join(a.get("found_terms", []))])
            has_items = True
        for a in allergen.get("precautionary_allergens", []):
            all_data.append([a.get("name", ""), "MAY CONTAIN (Cross-contact)", ", ".join(a.get("found_terms", []))])
            has_items = True

        if not has_items:
            all_data.append(["Monitored Allergens", "NOT DETECTED", "None of 13 monitored allergens found in text"])

        t_all = Table(all_data, colWidths=[5*cm, 5*cm, 7.4*cm])
        t_all.setStyle(_base_table_style(header_bg=colors.HexColor("#6366F1")))
        story.append(t_all)
    else:
        story.append(Paragraph("<i>Allergen status unknown: Ingredients text was not detected.</i>", small_style))

    # ── Footer / Disclaimer ──────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Notice:</b> This analysis was generated automatically by VEDANSHU using OCR and heuristic rules. "
        "It is strictly educational and not a medical diagnosis or safety certification. "
        "Always inspect the physical packaging before consumption.",
        small_style
    ))

    doc.build(story)
    return buf.getvalue()


def _plain_text_fallback(results: Dict[str, Any]) -> bytes:
    """Plain-text fallback when reportlab is not available."""
    lines = [
        "VEDANSHU PRODUCT PACKET ANALYSER — REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
    ]
    fields = results.get("fields", {})
    lines.append("\nPRODUCT IDENTIFICATION:")
    for k, v in fields.items():
        if k != "field_evidence":
            lines.append(f"  {k}: {v or 'Not detected'}")

    score = results.get("health_score", {})
    lines.append(f"\nHEALTH SCORE: {score.get('score', 'Insufficient Data')} (Grade: {score.get('grade', 'N/A')})")

    nutrients = results.get("nutrients", {})
    lines.append("\nNUTRITION VALUES:")
    for k, v in nutrients.items():
        lines.append(f"  {k}: {v.get('value')} {v.get('unit')}")

    return "\n".join(lines).encode("utf-8")


def generate_pdf(results: Dict[str, Any]) -> bytes:
    """Generates PDF report bytes with fallback to plain text if reportlab is unavailable."""
    try:
        import reportlab
        return _pdf_with_reportlab(results)
    except ImportError:
        return _plain_text_fallback(results)
