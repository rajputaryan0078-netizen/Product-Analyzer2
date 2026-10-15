"""
Export Engine — VEDANSHU Product Packet Analyser.

Generates downloadable reports from analysis results in two formats:
  - CSV  : Flat-file nutrition + risk + allergen data (pandas)
  - PDF  : Formatted A4 report using reportlab (with fallback to plain-text
           if reportlab is not installed)

Both functions return raw bytes suitable for st.download_button().
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
      1. Product Info
      2. Nutrition Values
      3. Risk Alerts (Quantitative)
      4. Ingredient Flags
      5. Allergen Detection

    Returns bytes.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    fields   = results.get("fields", {})
    nutrients = results.get("nutrients", {})
    risk     = results.get("risk_analysis", {})
    allergen = results.get("allergen_analysis", {})
    score    = results.get("health_score", {})

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Header ──────────────────────────────────────────────────────────────
    writer.writerow(["VEDANSHU PRODUCT PACKET ANALYSER — ANALYSIS REPORT"])
    writer.writerow([f"Generated: {now}"])
    writer.writerow([])

    # ── 1. Product Info ──────────────────────────────────────────────────────
    writer.writerow(["SECTION 1: PRODUCT INFORMATION"])
    writer.writerow(["Field", "Value"])
    for key, label in [
        ("product_name", "Product Name"),
        ("brand_name",   "Brand"),
        ("mrp",          "MRP"),
        ("mfg_date",     "Manufacturing Date"),
        ("pack_date",    "Pack Date"),
        ("expiry_date",  "Expiry Date"),
        ("best_before",  "Best Before"),
        ("serving_size", "Serving Size"),
        ("ingredients",  "Ingredients"),
    ]:
        val = fields.get(key) or "Not detected"
        writer.writerow([label, val])
    writer.writerow([])

    # ── 2. Health Score ──────────────────────────────────────────────────────
    if score:
        writer.writerow(["SECTION 2: HEALTH SCORE"])
        writer.writerow(["Score", "Grade", "Label", "Summary"])
        writer.writerow([
            score.get("score", "N/A"),
            score.get("grade", "N/A"),
            score.get("grade_label", "N/A"),
            score.get("summary", ""),
        ])
        writer.writerow([])
        writer.writerow(["Component Breakdown"])
        writer.writerow(["Nutrient", "Value", "Unit", "Component Score (/100)", "Weight", "Detected"])
        for c in score.get("components", []):
            writer.writerow([
                c["nutrient"],
                c["value"] if c["value"] is not None else "Not detected",
                c["unit"],
                c["component_score"],
                c["weight"],
                "Yes" if c["detected"] else "No",
            ])
        writer.writerow([])

    # ── 3. Nutrition Values ──────────────────────────────────────────────────
    writer.writerow(["SECTION 3: NUTRITION VALUES (per 100g)"])
    writer.writerow(["Nutrient", "Value", "Unit", "Serving Basis"])
    for name, data in nutrients.items():
        val = data.get("value")
        writer.writerow([
            name,
            val if val is not None else "Not detected",
            data.get("unit", "-"),
            data.get("serving_basis", "-"),
        ])
    writer.writerow([])

    # ── 4. Risk Alerts ───────────────────────────────────────────────────────
    writer.writerow(["SECTION 4: QUANTITATIVE RISK ALERTS"])
    writer.writerow(["Nutrient", "Status", "Value", "Threshold", "Source"])
    for alert in risk.get("quantitative_alerts", []):
        writer.writerow([
            alert.get("nutrient", ""),
            alert.get("status", ""),
            alert.get("value_display", ""),
            alert.get("threshold_text", ""),
            alert.get("source", ""),
        ])
    writer.writerow([])

    # ── 5. Ingredient Flags ──────────────────────────────────────────────────
    writer.writerow(["SECTION 5: INGREDIENT FLAGS"])
    writer.writerow(["Flag Name", "Category", "Severity", "Found Terms", "Suggestion"])
    for flag in risk.get("ingredient_flags", []):
        writer.writerow([
            flag.get("name", ""),
            flag.get("category", ""),
            flag.get("severity", ""),
            ", ".join(flag.get("found_terms", [])),
            flag.get("suggestion", ""),
        ])
    writer.writerow([])

    # ── 6. Allergen Detection ────────────────────────────────────────────────
    writer.writerow(["SECTION 6: ALLERGEN DETECTION"])
    if allergen.get("ingredients_available"):
        writer.writerow(["Allergen", "Status", "Category", "Found Terms", "Severity"])
        for a in allergen.get("allergens_found", []):
            writer.writerow([
                a.get("name", ""),
                "DETECTED",
                a.get("category", ""),
                ", ".join(a.get("found_terms", [])),
                a.get("severity", ""),
            ])
        for name in allergen.get("allergens_clear", []):
            writer.writerow([name, "Not detected", "", "", ""])
    else:
        writer.writerow(["No ingredients text available for allergen detection."])
    writer.writerow([])

    # ── Disclaimer ───────────────────────────────────────────────────────────
    writer.writerow(["DISCLAIMER"])
    writer.writerow([
        "This report is for informational/educational purposes only. "
        "It is not a medical diagnosis or dietary prescription. "
        "Always verify information on the physical product label. "
        "Consult a registered dietitian for personal dietary advice."
    ])

    return output.getvalue().encode("utf-8-sig")   # BOM for Excel compatibility


# ─────────────────────────────────────────────────────────────────────────────
# PDF Export
# ─────────────────────────────────────────────────────────────────────────────

def _pdf_with_reportlab(results: Dict[str, Any]) -> bytes:
    """Generates a styled PDF using reportlab."""
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
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "VTitle",
        parent=styles["Title"],
        fontSize=20, leading=26,
        textColor=colors.HexColor("#0B1220"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "VSubtitle",
        parent=styles["Normal"],
        fontSize=10, leading=14,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "VSection",
        parent=styles["Heading2"],
        fontSize=12, leading=16,
        textColor=colors.HexColor("#0E7490"),
        spaceBefore=16, spaceAfter=6,
        borderPad=4,
    )
    body_style = ParagraphStyle(
        "VBody",
        parent=styles["Normal"],
        fontSize=9, leading=13,
        textColor=colors.HexColor("#1E293B"),
    )
    small_style = ParagraphStyle(
        "VSmall",
        parent=styles["Normal"],
        fontSize=7.5, leading=11,
        textColor=colors.HexColor("#64748B"),
        italic=True,
    )

    # Table style helpers
    def _base_table_style(header_bg=colors.HexColor("#0E7490")):
        return TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING",  (0, 0), (-1, 0), 6),
            ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",    (0, 1), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#F8FAFC"), colors.HexColor("#FFFFFF")]),
            ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",  (0, 1), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",(0, 0), (-1, -1), 8),
        ])

    story = []

    # ── Title ────────────────────────────────────────────────────────────────
    product_name = fields.get("product_name") or "Unknown Product"
    story.append(Paragraph("VEDANSHU — Product Packet Analyser", title_style))
    story.append(Paragraph(f"Analysis Report · {now}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=colors.HexColor("#0E7490"), spaceAfter=12))

    # ── Product Info ─────────────────────────────────────────────────────────
    story.append(Paragraph("1. Product Information", section_style))
    prod_data = [["Field", "Value"]]
    for key, label in [
        ("product_name", "Product Name"),
        ("brand_name",   "Brand"),
        ("mrp",          "MRP"),
        ("mfg_date",     "Mfg Date"),
        ("pack_date",    "Pack Date"),
        ("expiry_date",  "Expiry Date"),
        ("best_before",  "Best Before"),
        ("serving_size", "Serving Size"),
    ]:
        prod_data.append([label, fields.get(key) or "Not detected"])
    t = Table(prod_data, colWidths=[4*cm, 13*cm])
    t.setStyle(_base_table_style())
    story.append(t)

    # Ingredients
    ing = fields.get("ingredients")
    if ing:
        story.append(Spacer(1, 8))
        story.append(Paragraph("<b>Ingredients:</b>", body_style))
        story.append(Paragraph(ing, body_style))

    # ── Health Score ─────────────────────────────────────────────────────────
    if score:
        story.append(Paragraph("2. Health Score", section_style))
        s_color = colors.HexColor(score.get("color", "#34D399"))
        score_data = [
            ["Score", "Grade", "Label", "Summary"],
            [
                str(score.get("score", "N/A")) + "/100",
                score.get("grade", "N/A"),
                score.get("grade_label", "N/A"),
                score.get("summary", ""),
            ]
        ]
        st_score = _base_table_style()
        st_score.add("TEXTCOLOR", (0, 1), (1, 1), s_color)
        st_score.add("FONTNAME",  (0, 1), (1, 1), "Helvetica-Bold")
        t2 = Table(score_data, colWidths=[2.5*cm, 2*cm, 4*cm, 8.5*cm])
        t2.setStyle(st_score)
        story.append(t2)
        story.append(Paragraph(
            f"<i>Disclaimer: {score.get('note', '')}</i>", small_style))

    # ── Nutrition ────────────────────────────────────────────────────────────
    story.append(Paragraph("3. Nutrition Values (per 100g)", section_style))
    nut_data = [["Nutrient", "Value", "Unit", "Serving Basis"]]
    for name, data in nutrients.items():
        val = data.get("value")
        nut_data.append([
            name,
            str(val) if val is not None else "Not detected",
            data.get("unit", "-"),
            data.get("serving_basis", "-"),
        ])
    t3 = Table(nut_data, colWidths=[5*cm, 3*cm, 2.5*cm, 6.5*cm])
    t3.setStyle(_base_table_style())
    story.append(t3)

    # ── Risk Alerts ──────────────────────────────────────────────────────────
    story.append(Paragraph("4. Quantitative Risk Alerts", section_style))
    risk_data = [["Nutrient", "Status", "Value", "Threshold", "Source"]]
    status_colors = {
        "HIGH":     colors.HexColor("#DC2626"),
        "MODERATE": colors.HexColor("#D97706"),
        "OK":       colors.HexColor("#059669"),
        "UNKNOWN":  colors.HexColor("#64748B"),
    }
    for i, alert in enumerate(risk.get("quantitative_alerts", []), start=1):
        risk_data.append([
            alert.get("nutrient", ""),
            alert.get("status", ""),
            alert.get("value_display", ""),
            alert.get("threshold_text", ""),
            alert.get("source", ""),
        ])
    t4 = Table(risk_data, colWidths=[3.5*cm, 2.5*cm, 3.5*cm, 5*cm, 2.5*cm])
    ts4 = _base_table_style()
    for i, alert in enumerate(risk.get("quantitative_alerts", []), start=1):
        sc = status_colors.get(alert.get("status", ""), colors.HexColor("#64748B"))
        ts4.add("TEXTCOLOR", (1, i), (1, i), sc)
        ts4.add("FONTNAME",  (1, i), (1, i), "Helvetica-Bold")
    t4.setStyle(ts4)
    story.append(t4)

    # ── Ingredient Flags ─────────────────────────────────────────────────────
    flags = risk.get("ingredient_flags", [])
    if flags:
        story.append(Paragraph("5. Ingredient Flags", section_style))
        flag_data = [["Flag", "Category", "Severity", "Found Terms"]]
        for f in flags:
            flag_data.append([
                f.get("name", ""),
                f.get("category", ""),
                f.get("severity", "").upper(),
                ", ".join(f.get("found_terms", [])),
            ])
        t5 = Table(flag_data, colWidths=[5.5*cm, 3.5*cm, 2.5*cm, 5.5*cm])
        t5.setStyle(_base_table_style(header_bg=colors.HexColor("#92400E")))
        story.append(t5)

    # ── Allergens ────────────────────────────────────────────────────────────
    story.append(Paragraph("6. Allergen Detection", section_style))
    detected = allergen.get("allergens_found", [])
    clear    = allergen.get("allergens_clear", [])
    if not allergen.get("ingredients_available"):
        story.append(Paragraph("No ingredients text available.", body_style))
    else:
        alg_data = [["Allergen", "Status", "Category", "Found Terms"]]
        for a in detected:
            alg_data.append([
                a.get("name", ""),
                "⚠ DETECTED",
                a.get("category", ""),
                ", ".join(a.get("found_terms", [])),
            ])
        for name in clear:
            alg_data.append([name, "Clear", "", ""])
        t6 = Table(alg_data, colWidths=[4.5*cm, 3*cm, 3.5*cm, 6*cm])
        ts6 = _base_table_style(header_bg=colors.HexColor("#7C3AED"))
        for i, a in enumerate(detected, start=1):
            ts6.add("TEXTCOLOR", (1, i), (1, i), colors.HexColor("#DC2626"))
            ts6.add("FONTNAME",  (1, i), (1, i), "Helvetica-Bold")
        t6.setStyle(ts6)
        story.append(t6)

    # ── Disclaimer ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#CBD5E1"), spaceAfter=8))
    story.append(Paragraph(
        "DISCLAIMER: This report is for informational and educational purposes only. "
        "Alerts are comparisons against published reference thresholds (NHS UK, WHO, FSSAI). "
        "They are not a medical diagnosis, safety verdict, or dietary prescription. "
        "Always verify information on the physical product label. "
        "Consult a registered dietitian for personal dietary advice.",
        small_style,
    ))

    doc.build(story)
    return buf.getvalue()


def _pdf_plaintext_fallback(results: Dict[str, Any]) -> bytes:
    """Plain-text PDF fallback when reportlab is not installed."""
    fields    = results.get("fields", {})
    nutrients = results.get("nutrients", {})
    risk      = results.get("risk_analysis", {})
    score     = results.get("health_score", {})
    now       = datetime.now().strftime("%d %b %Y  %H:%M")

    lines = [
        "VEDANSHU — PRODUCT PACKET ANALYSER",
        f"Analysis Report | Generated: {now}",
        "=" * 60,
        "",
        "PRODUCT INFORMATION",
        "-" * 40,
    ]
    for key, label in [
        ("product_name", "Product Name"),
        ("brand_name",   "Brand"),
        ("mrp",          "MRP"),
        ("mfg_date",     "Mfg Date"),
        ("expiry_date",  "Expiry Date"),
        ("best_before",  "Best Before"),
        ("serving_size", "Serving Size"),
    ]:
        lines.append(f"  {label}: {fields.get(key) or 'Not detected'}")
    lines.append("")

    if score:
        lines += [
            "HEALTH SCORE",
            "-" * 40,
            f"  Score: {score.get('score', 'N/A')}/100  Grade: {score.get('grade', 'N/A')}  ({score.get('grade_label', '')})",
            f"  {score.get('summary', '')}",
            "",
        ]

    lines += ["NUTRITION VALUES", "-" * 40]
    for name, data in nutrients.items():
        val = data.get("value")
        lines.append(f"  {name}: {val if val is not None else 'Not detected'} {data.get('unit', '')}")
    lines.append("")

    lines += ["RISK ALERTS", "-" * 40]
    for alert in risk.get("quantitative_alerts", []):
        lines.append(f"  {alert['nutrient']}: {alert['status']} — {alert.get('value_display', '')}")
    lines.append("")

    lines += [
        "DISCLAIMER",
        "-" * 40,
        "  This report is for informational/educational purposes only.",
        "  Always verify on the physical product label.",
        "  Consult a registered dietitian for personal dietary advice.",
    ]

    return "\n".join(lines).encode("utf-8")


def generate_pdf(results: Dict[str, Any]) -> bytes:
    """
    Generates a PDF report. Uses reportlab if available, otherwise plain text.
    Returns bytes.
    """
    try:
        import reportlab
        return _pdf_with_reportlab(results)
    except ImportError:
        return _pdf_plaintext_fallback(results)
