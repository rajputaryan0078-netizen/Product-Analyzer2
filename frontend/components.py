"""
Reusable UI component functions for VEDANSHU Product Packet Analyser.

Extracted from app.py for cleaner separation of concerns.
All functions return HTML strings or render directly via st.markdown().
"""

import streamlit as st
from typing import Dict, Any, List


# ─────────────────────────────────────────────────────────────────────────────
# Badge helpers
# ─────────────────────────────────────────────────────────────────────────────

def risk_badge_html(status: str) -> str:
    cfg = {
        "HIGH":     ("risk-badge-high",     "🔴 HIGH"),
        "MODERATE": ("risk-badge-moderate", "🟡 MODERATE"),
        "OK":       ("risk-badge-ok",       "🟢 OK"),
        "UNKNOWN":  ("risk-badge-unknown",  "⬜ UNKNOWN"),
    }
    css, label = cfg.get(status, ("risk-badge-unknown", status))
    return f'<span class="{css}">{label}</span>'


def ing_badge_html(severity: str) -> str:
    sev_map = {
        "high":     ("risk-badge-high",     "⚠ High Concern"),
        "moderate": ("risk-badge-moderate", "⚡ Moderate Note"),
        "info":     ("risk-badge-info",     "ℹ Info"),
    }
    css, label = sev_map.get(severity, ("risk-badge-info", "Info"))
    return f'<span class="{css}">{label}</span>'


def allergen_badge_html(severity: str) -> str:
    cfg = {
        "high":     ("risk-badge-high",     "🚨 High Risk"),
        "moderate": ("risk-badge-moderate", "⚠ Moderate"),
        "info":     ("risk-badge-info",     "ℹ Info"),
    }
    css, label = cfg.get(severity, ("risk-badge-info", severity.title()))
    return f'<span class="{css}">{label}</span>'


# ─────────────────────────────────────────────────────────────────────────────
# Health Score Panel
# ─────────────────────────────────────────────────────────────────────────────

def render_health_score(score_data: Dict[str, Any]) -> None:
    """Renders the real-time computed health score card."""
    score = score_data.get("score")
    grade = score_data.get("grade") or "N/A"
    label = score_data.get("grade_label") or "Insufficient Data"
    color = score_data.get("color") or "#94A3B8"
    bg = score_data.get("bg") or "rgba(100,116,139,0.12)"
    border = score_data.get("border") or "rgba(100,116,139,0.35)"
    summary = score_data.get("summary", "")
    note = score_data.get("note", "")
    components = score_data.get("components", [])
    detected = score_data.get("detected_count", 0)
    total = score_data.get("total_count", 6)

    # Score progress bar fill width
    score_display = str(score) if score is not None else "—"
    bar_pct = min(100, max(0, score)) if score is not None else 0

    st.markdown(f"""
<div style="background:{bg}; border:1px solid {border};
border-radius:18px; padding:26px 30px; margin-bottom:24px;">

  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
    <div style="display:flex; align-items:center; gap:20px;">
      <!-- Score Circle -->
      <div style="width:80px; height:80px; border-radius:50%;
           background:radial-gradient(circle, {bg} 0%, rgba(11,18,32,0.8) 70%);
           border:3px solid {color};
           display:flex; flex-direction:column; align-items:center; justify-content:center;
           box-shadow:0 0 24px {border}; flex-shrink:0;">
        <div style="font-family:'Space Grotesk',sans-serif; font-size:1.6rem; font-weight:800;
             color:#FFFFFF; line-height:1;">{score_display}</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:0.6rem; color:{color};
             letter-spacing:0.05em;">/100</div>
      </div>
      <div>
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
          <span style="font-family:'Space Grotesk',sans-serif; font-size:1.5rem;
               font-weight:800; color:{color};">{'Grade ' + grade if grade != 'N/A' else 'Rating Unavailable'}</span>
          <span style="font-family:'JetBrains Mono',monospace; font-size:0.75rem;
               background:{bg}; border:1px solid {border}; color:{color};
               padding:3px 10px; border-radius:999px;">{label}</span>
        </div>
        <div style="font-size:0.9rem; color:#CBD5E1; line-height:1.5;">{summary}</div>
        <div style="font-size:0.75rem; color:#64748B; margin-top:4px;">
          Based on {detected}/{total} nutrients detected
        </div>
      </div>
    </div>
  </div>

  <!-- Progress Bar -->
  <div style="margin-top:18px;">
    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
      <span style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:#64748B;">
        HEALTH SCORE
      </span>
      <span style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:{color};">
        {score_display}/100
      </span>
    </div>
    <div style="height:8px; background:rgba(255,255,255,0.08); border-radius:999px; overflow:hidden;">
      <div style="height:100%; width:{bar_pct}%; background:linear-gradient(90deg, {color}, {color}88);
           border-radius:999px; transition:width 0.6s ease;"></div>
    </div>
  </div>

</div>
<div style="font-size:0.74rem; color:#475569; margin:-16px 0 20px 4px; font-style:italic;">
  ⚠ {note}
</div>
""", unsafe_allow_html=True)

    # Component breakdown (collapsible)
    with st.expander("📊 Score Component Breakdown", expanded=False):
        cols = st.columns(3)
        for i, comp in enumerate(components):
            detected_tag = "" if comp["detected"] else " (not detected)"
            direction_icon = "📉" if comp["direction"] == "penalty" else "📈"
            col_score = comp["component_score"]
            if col_score is None:
                col_display = "N/A"
                col_color = "#64748B"
            else:
                col_display = str(col_score)
                col_color = (
                    "#F87171" if col_score <= 30 else
                    "#FBBF24" if col_score <= 60 else
                    "#34D399"
                )
            with cols[i % 3]:
                st.markdown(f"""
<div style="background:rgba(17,26,43,0.6); border:1px solid rgba(255,255,255,0.06);
border-radius:10px; padding:12px; margin-bottom:10px; text-align:center;">
  <div style="font-family:'JetBrains Mono',monospace; font-size:0.68rem;
       color:#6EE7B7; text-transform:uppercase; margin-bottom:4px;">
    {direction_icon} {comp['nutrient']}
  </div>
  <div style="font-size:1.3rem; font-weight:700; color:{col_color};
       font-family:'Space Grotesk',sans-serif;">{col_display}</div>
  <div style="font-size:0.68rem; color:#64748B;">weight {comp['weight']}%{detected_tag}</div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Allergen Panel
# ─────────────────────────────────────────────────────────────────────────────

def render_allergen_panel(allergen_data: Dict[str, Any], is_demo: bool = False) -> None:
    """Renders the allergen detection results section."""
    st.markdown(f"""
<div style="font-family:'Space Grotesk',sans-serif; font-size:1.35rem; font-weight:700;
color:#FFFFFF; margin:28px 0 6px 0; display:flex; align-items:center; gap:8px;">
<span style="color:#A78BFA;">⚠️</span> Allergen Detection
</div>
<div style="font-size:0.82rem; color:#9AA7B5; margin-bottom:16px; line-height:1.5;
font-family:'Inter',sans-serif; max-width:820px;">
<strong style="color:#FBBF24;">Note:</strong>
Allergen detection is based on keyword matching in OCR-extracted text.
Always verify against the physical product label — OCR errors or unusual formatting
may cause false negatives.
{"<br><strong style='color:#34D399;'>ℹ This is a demonstration with sample data.</strong>" if is_demo else ""}
</div>
""", unsafe_allow_html=True)

    if not allergen_data.get("ingredients_available"):
        st.markdown("""<div class="risk-no-data-box">
<span style="font-size:1.1rem;">🥗</span>
<div>
<strong>No ingredients text detected</strong><br>
<span style="color:#9AA7B5; font-size:0.88rem;">
Allergen detection requires a readable ingredients list in the OCR output.
</span>
</div>
</div>""", unsafe_allow_html=True)
        return

    allergens_found = allergen_data.get("allergens_found", [])
    allergens_clear = allergen_data.get("allergens_clear", [])
    total_checked   = allergen_data.get("total_checked", 13)

    # Summary chips row
    found_count = len(allergens_found)
    clear_count = len(allergens_clear)

    summary_color = "#F87171" if found_count > 0 else "#34D399"
    summary_bg    = "rgba(248,113,113,0.08)" if found_count > 0 else "rgba(52,211,153,0.08)"
    summary_border= "rgba(248,113,113,0.35)" if found_count > 0 else "rgba(52,211,153,0.3)"
    summary_icon  = "🚨" if found_count > 0 else "✅"
    summary_text  = (
        f"{found_count} allergen(s) detected in this product"
        if found_count > 0
        else "No monitored allergens detected in the ingredients text"
    )

    st.markdown(f"""
<div style="background:{summary_bg}; border:1px solid {summary_border};
border-radius:12px; padding:14px 20px; margin-bottom:16px;
display:flex; align-items:center; gap:14px;">
  <span style="font-size:1.4rem;">{summary_icon}</span>
  <div>
    <div style="font-family:'Space Grotesk',sans-serif; font-size:1rem;
         font-weight:700; color:{summary_color};">{summary_text}</div>
    <div style="font-size:0.8rem; color:#94A3B8; margin-top:2px;">
      {total_checked} allergen categories checked · {found_count} detected · {clear_count} clear
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Detected allergens
    if allergens_found:
        st.markdown("""<div style="font-family:'JetBrains Mono',monospace; font-size:0.74rem;
color:#F87171; letter-spacing:0.1em; font-weight:700; margin-bottom:10px;">
⚠ ALLERGENS DETECTED
</div>""", unsafe_allow_html=True)

        sev_order = {"high": 0, "moderate": 1, "info": 2}
        sorted_found = sorted(allergens_found, key=lambda a: sev_order.get(a.get("severity", "info"), 3))

        for allergen in sorted_found:
            sev    = allergen.get("severity", "info")
            badge  = allergen_badge_html(sev)
            icon   = allergen.get("icon", "⚠️")
            found_str = ", ".join(f"<code>{t}</code>" for t in allergen.get("found_terms", []))
            border_color = {
                "high":     "rgba(248,113,113,0.45)",
                "moderate": "rgba(251,191,36,0.4)",
                "info":     "rgba(52,211,153,0.25)",
            }.get(sev, "rgba(100,116,139,0.3)")
            bg_color = {
                "high":     "rgba(248,113,113,0.07)",
                "moderate": "rgba(251,191,36,0.05)",
                "info":     "rgba(52,211,153,0.04)",
            }.get(sev, "rgba(100,116,139,0.04)")

            st.markdown(f"""
<div style="background:{bg_color}; border:1px solid {border_color};
border-radius:14px; padding:16px 20px; margin-bottom:12px;">
  <div style="display:flex; justify-content:space-between; align-items:center;
       flex-wrap:wrap; gap:8px;">
    <div style="display:flex; align-items:center; gap:10px;">
      <span style="font-size:1.3rem;">{icon}</span>
      <span style="font-family:'Space Grotesk',sans-serif; font-size:1.0rem;
           font-weight:700; color:#FFFFFF;">{allergen['name']}</span>
    </div>
    {badge}
  </div>
  <div style="font-size:0.8rem; color:#94A3B8; margin-top:6px;
       font-family:'JetBrains Mono',monospace;">
    Category: {allergen.get('category', '')} &nbsp;·&nbsp; Found: {found_str}
  </div>
  <div style="font-size:0.88rem; color:#E2E8F0; margin-top:10px;
       line-height:1.6; font-family:'Inter',sans-serif;">
    {allergen.get('note', '')}
  </div>
</div>
""", unsafe_allow_html=True)

    # Clear allergens (compact chip list)
    if allergens_clear:
        with st.expander(f"✅ {clear_count} allergen categories not detected (expand to view)", expanded=False):
            chips = "".join(
                f'<span style="background:rgba(52,211,153,0.08); border:1px solid rgba(52,211,153,0.25); '
                f'color:#6EE7B7; padding:3px 10px; border-radius:999px; '
                f'font-family:JetBrains Mono,monospace; font-size:0.72rem; '
                f'margin:3px; display:inline-block;">{name}</span>'
                for name in allergens_clear
            )
            st.markdown(f'<div style="padding:6px 0;">{chips}</div>', unsafe_allow_html=True)
            st.caption(
                "These allergens were not detected based on keyword matching. "
                "This does not guarantee their absence — OCR errors or cross-contamination "
                "warnings on the label may not be captured."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Scan History Panel
# ─────────────────────────────────────────────────────────────────────────────

def render_scan_history(history: List[Dict[str, Any]]) -> None:
    """Renders the scan history panel."""
    if not history:
        st.markdown("""<div class="risk-no-data-box">
<span style="font-size:1.1rem;">🕓</span>
<div>
<strong>No scans yet this session</strong><br>
<span style="color:#9AA7B5; font-size:0.88rem;">
Analyse a product to start building your scan history.
</span>
</div>
</div>""", unsafe_allow_html=True)
        return

    for idx, entry in enumerate(history):
        score = entry.get("health_score")
        grade = entry.get("grade")
        color = entry.get("grade_color", "#94A3B8")
        score_display = f"{score}/100 · Grade {grade}" if score is not None else "Score N/A"

        high_badges = "".join(
            f'<span style="background:rgba(248,113,113,0.12); color:#F87171; '
            f'border:1px solid rgba(248,113,113,0.35); padding:2px 8px; '
            f'border-radius:999px; font-size:0.68rem; font-family:JetBrains Mono,monospace; '
            f'margin-right:4px;">🔴 {n}</span>'
            for n in entry.get("high_alerts", [])
        )
        allergen_badges = "".join(
            f'<span style="background:rgba(167,139,250,0.12); color:#A78BFA; '
            f'border:1px solid rgba(167,139,250,0.3); padding:2px 8px; '
            f'border-radius:999px; font-size:0.68rem; font-family:JetBrains Mono,monospace; '
            f'margin-right:4px;">⚠️ {a}</span>'
            for a in entry.get("allergens", [])
        )
        demo_tag = (
            ' <span style="background:rgba(52,211,153,0.1); color:#34D399; '
            'border:1px solid rgba(52,211,153,0.25); padding:2px 7px; '
            'border-radius:999px; font-size:0.65rem;">DEMO</span>'
            if entry.get("is_demo") else ""
        )

        st.markdown(f"""
<div style="background:rgba(17,26,43,0.6); border:1px solid rgba(255,255,255,0.07);
border-radius:12px; padding:14px 18px; margin-bottom:10px;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start;
       flex-wrap:wrap; gap:8px;">
    <div>
      <div style="font-family:'Space Grotesk',sans-serif; font-size:0.95rem;
           font-weight:700; color:#FFFFFF;">
        #{len(history) - idx}. {entry['product_name']}{demo_tag}
      </div>
      <div style="font-size:0.78rem; color:#9AA7B5; margin-top:2px;
           font-family:'Inter',sans-serif;">
        {entry['brand']} · {entry['mrp']} · {entry['timestamp']}
      </div>
    </div>
    <div style="font-family:'Space Grotesk',sans-serif; font-size:0.88rem;
         font-weight:700; color:{color};">{score_display}</div>
  </div>
  {"<div style='margin-top:8px;'>" + high_badges + allergen_badges + "</div>" if high_badges or allergen_badges else ""}
</div>
""", unsafe_allow_html=True)
