"""
VEDANSHU - Product Packet Analyser  (v2 — Complete)
AI-powered food label analysis platform.

Project Structure:
  backend/
    __init__.py
    allergen_engine.py   — 13-allergen keyword detection
    export_engine.py     — PDF + CSV download generation
    extractor.py         — regex field & nutrition extraction
    health_score.py      — real 0-100 health score formula
    image_utils.py       — image validation & OpenCV preprocessing
    nutrition_rules.py   — NHS/FSSAI threshold evaluations
    ocr_utils.py         — Tesseract multi-PSM OCR
    risk_engine.py       — quantitative alerts + ingredient flags
    scan_history.py      — session scan log

  frontend/
    __init__.py
    components.py        — health score, allergen & history panels
    styles.css           — unified CSS design system

  app.py                 — Streamlit entry point (this file)

Screens:
  1. Landing  — Hero + Features + How It Works + Health Score preview
  2. Upload   — Holographic scanner chamber
  3. Results  — Full analysis: health score, nutrients, risk, allergens, export
  4. History  — Session scan log
"""

import os
import sys
import time
import streamlit as st

# ── Resolve project root so imports work from any working directory ──────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from PIL import Image

# Backend modules
from backend import (
    image_utils,
    ocr_utils,
    extractor,
    nutrition_rules,
    risk_engine,
    allergen_engine,
    health_score as hs_module,
    export_engine,
    scan_history,
)

# Frontend components
from frontend.components import (
    risk_badge_html,
    ing_badge_html,
    render_health_score,
    render_allergen_panel,
    render_scan_history,
)

# ==============================================================================
# Page Configuration
# ==============================================================================
st.set_page_config(
    page_title="VEDANSHU | Product Packet Analyser",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==============================================================================
# CSS Injection
# ==============================================================================
def inject_custom_css():
    css_path = os.path.join(_ROOT, "frontend", "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

inject_custom_css()


# ==============================================================================
# Session State Initialization
# ==============================================================================
_defaults = {
    "screen":           "landing",
    "uploaded_file_obj": None,
    "analysis_results": None,
    "is_demo_mode":     False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

scan_history.init_history(st.session_state)


def go_to_screen(target: str):
    st.session_state["screen"] = target


# ==============================================================================
# Helpers
# ==============================================================================
def _run_full_pipeline(raw_text: str, raw_ocr_text: str, is_demo: bool = False) -> dict:
    """
    Runs the complete analysis pipeline on extracted OCR text.
    Returns the full results dict stored in session_state["analysis_results"].
    """
    fields          = extractor.extract_product_fields(raw_text)
    nutrients       = extractor.extract_nutrition_values(raw_text)
    risk_analysis   = risk_engine.run_full_risk_analysis(
        nutrients, fields.get("ingredients")
    )
    allergen_result = allergen_engine.detect_allergens(fields.get("ingredients"))
    score_data      = hs_module.compute_health_score(nutrients)

    return {
        "is_demo":          is_demo,
        "raw_text":         raw_text,
        "raw_ocr_text":     raw_ocr_text,
        "fields":           fields,
        "nutrients":        nutrients,
        "risk_analysis":    risk_analysis,
        "allergen_analysis": allergen_result,
        "health_score":     score_data,
    }


# ==============================================================================
# Navbar
# ==============================================================================
def render_navbar():
    current = st.session_state.get("screen", "landing")

    nav_html = """<div class="vedanshu-nav-bar">
<div class="brand-wrapper">
<div class="brand-icon">⚡</div>
<span class="brand-logo-text">VEDANSHU</span>
</div>
<div style="display:flex; align-items:center; gap:12px;">
<span class="brand-sub-badge">PRODUCT PACKET ANALYSER</span>
</div>
</div>"""
    st.markdown(nav_html, unsafe_allow_html=True)

    # Quick nav row (only on non-landing screens)
    if current != "landing":
        nav_cols = st.columns([1.2, 1.2, 1.2, 6])
        n1, n2, n3, _ = nav_cols[0], nav_cols[1], nav_cols[2], nav_cols[3]
        with n1:
            if st.button("🏠 Home", key="nav_home", use_container_width=True):
                go_to_screen("landing")
                st.rerun()
        with n2:
            if st.button("📡 Scanner", key="nav_scan", use_container_width=True):
                go_to_screen("upload")
                st.rerun()
        with n3:
            history_count = len(scan_history.get_history(st.session_state))
            if st.button(f"🕓 History ({history_count})", key="nav_hist", use_container_width=True):
                go_to_screen("history")
                st.rerun()
        st.write("")


# ==============================================================================
# SCREEN 1: Landing
# ==============================================================================
def render_packet_mockup():
    mockup_html = """<div class="mockup-stage-wrap">
<div class="mockup-packet-card">
<div class="mockup-laser-line"></div>
<div class="mockup-header-row">
<span class="mockup-badge-authentic"><span>⚡</span> AUTHENTIC SCAN</span>
<span class="mockup-badge-core">AI CORE</span>
</div>
<div class="mockup-center-graphic">
<div class="mockup-food-icon">🥣</div>
<div class="mockup-product-name">CRUNCHY WHOLE GRAIN</div>
<div class="mockup-product-sub">Oats &amp; Honey &bull; High Fiber</div>
</div>
<div class="mockup-nutrition-strip">
<div class="mockup-nutrient-line">
<span class="mockup-nutrient-label">SUGAR: 12.8g</span>
<span class="mockup-nutrient-status-alert">MODERATE</span>
</div>
<div class="mockup-nutrient-line">
<span class="mockup-nutrient-label">FAT: 4.5g</span>
<span class="mockup-nutrient-status-good">OK</span>
</div>
<div class="mockup-nutrient-line">
<span class="mockup-nutrient-label">PROTEIN: 8.5g</span>
<span class="mockup-nutrient-status-good">OPTIMAL</span>
</div>
</div>
</div>
</div>"""
    st.markdown(mockup_html, unsafe_allow_html=True)


def render_hero():
    col_text, col_mockup = st.columns([1.15, 0.85], gap="large")

    with col_text:
        st.markdown("""<div class="hero-container">
<div class="hero-eyebrow">
<span class="hero-pulse-dot"></span>
AI-POWERED FOOD LABEL DECODER
</div>
<div class="hero-headline">
Analyze your <span class="gradient-text">product.</span>
</div>
<div class="hero-subtext">
Discover product details, ingredients, allergens, and nutrition benchmarks
from a single packet image — powered by OCR and rule-based AI.
</div>
</div>""", unsafe_allow_html=True)

        btn_col1, btn_col2 = st.columns([1.3, 1.2])
        with btn_col1:
            if st.button("Analyze Your Product →", type="primary",
                         key="cta_go_upload", use_container_width=True):
                go_to_screen("upload")
                st.rerun()

        with btn_col2:
            if st.button("▶ Sample Demo Packet", type="secondary",
                         key="cta_demo_landing", use_container_width=True):
                demo_raw = extractor.get_demo_packet_data()
                results  = _run_full_pipeline(
                    demo_raw["raw_text"], demo_raw["raw_text"], is_demo=True
                )
                # Merge demo fields (already cleaned) directly
                results["fields"]    = demo_raw["fields"]
                results["nutrients"] = demo_raw["nutrients"]
                # Re-run downstream on the clean demo nutrients
                results["risk_analysis"]    = risk_engine.run_full_risk_analysis(
                    demo_raw["nutrients"], demo_raw["fields"].get("ingredients")
                )
                results["allergen_analysis"] = allergen_engine.detect_allergens(
                    demo_raw["fields"].get("ingredients")
                )
                results["health_score"] = hs_module.compute_health_score(demo_raw["nutrients"])
                results["is_demo"] = True

                st.session_state["analysis_results"] = results
                st.session_state["is_demo_mode"] = True
                scan_history.add_to_history(st.session_state, results)
                go_to_screen("results")
                st.rerun()

    with col_mockup:
        render_packet_mockup()


def render_features():
    st.markdown("""<div class="features-container">
<div class="section-label">CAPABILITIES</div>
<div class="section-title">Precision Insights from Any Package</div>
</div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.markdown("""<div class="feature-card">
<div class="feature-icon-box">🌿</div>
<div class="feature-title">Ingredients Parsing</div>
<div class="feature-desc">Detect hidden sugars, palm oils, artificial sweeteners, and E-number chemical additives instantly.</div>
</div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""<div class="feature-card">
<div class="feature-icon-box">⚠️</div>
<div class="feature-title">Allergen Detection</div>
<div class="feature-desc">Spot 13 critical allergen categories including gluten, dairy, peanuts, tree nuts, soy, eggs, fish, and shellfish.</div>
</div>""", unsafe_allow_html=True)
    with c3:
        st.markdown("""<div class="feature-card">
<div class="feature-icon-box">📊</div>
<div class="feature-title">Nutrition Benchmarks</div>
<div class="feature-desc">Compare sugars, saturated fats, sodium and more against NHS/FSSAI per-100g health guidelines with a real score.</div>
</div>""", unsafe_allow_html=True)

    c4, c5, c6 = st.columns(3, gap="medium")
    with c4:
        st.markdown("""<div class="feature-card">
<div class="feature-icon-box">💯</div>
<div class="feature-title">Health Score</div>
<div class="feature-desc">A real 0–100 weighted health score with grade (A–D) computed from nutrient thresholds — not a mockup.</div>
</div>""", unsafe_allow_html=True)
    with c5:
        st.markdown("""<div class="feature-card">
<div class="feature-icon-box">📥</div>
<div class="feature-title">PDF &amp; CSV Export</div>
<div class="feature-desc">Download your complete analysis as a formatted PDF report or a CSV spreadsheet for further use.</div>
</div>""", unsafe_allow_html=True)
    with c6:
        st.markdown("""<div class="feature-card">
<div class="feature-icon-box">🕓</div>
<div class="feature-title">Scan History</div>
<div class="feature-desc">Every scan is logged in your session. Compare past analyses without re-uploading.</div>
</div>""", unsafe_allow_html=True)


def render_how_it_works():
    st.markdown("""<div class="how-it-works-container">
<div class="section-label">HOW IT WORKS</div>
<div class="section-title">Three Steps to Transparent Nutrition</div>
</div>""", unsafe_allow_html=True)

    s1, s2, s3 = st.columns(3, gap="medium")
    with s1:
        st.markdown("""<div class="step-card">
<span class="step-number">STEP 01</span>
<div class="step-title">Upload Package</div>
<div class="step-desc">Capture or select any packaged food label photo in JPG or PNG format.</div>
</div>""", unsafe_allow_html=True)
    with s2:
        st.markdown("""<div class="step-card">
<span class="step-number">STEP 02</span>
<div class="step-title">Optical AI Analysis</div>
<div class="step-desc">Tesseract OCR extracts tables, ingredient blocks, MRP, and manufacturing dates via multi-PSM passes.</div>
</div>""", unsafe_allow_html=True)
    with s3:
        st.markdown("""<div class="step-card">
<span class="step-number">STEP 03</span>
<div class="step-title">Explore Insights</div>
<div class="step-desc">Get your health score, allergen flags, nutrient benchmarks, risk alerts, and a downloadable report.</div>
</div>""", unsafe_allow_html=True)

    st.write("")

    # Health Score preview card — now reflects real scoring methodology
    preview_score_html = """<div class="health-score-preview-box">
<div class="score-badge-circle">
<div class="score-number-pill">72</div>
<div>
<div class="score-details-heading">Sample Telemetry Preview: Balanced Profile</div>
<div class="score-details-sub">Based on demo cereal data — real score computed from NHS/FSSAI thresholds</div>
</div>
</div>
<div class="score-metrics-strip">
<span class="score-chip score-chip-accent">🌾 High Fiber (+6.4g)</span>
<span class="score-chip score-chip-accent">💪 Good Protein (8.5g)</span>
<span class="score-chip" style="color:#FBBF24; border-color:rgba(245,158,11,0.3);">⚠️ Moderate Sugar (12.8g)</span>
<span class="score-chip score-chip-accent">🛡️ Low Sat. Fat (1.2g)</span>
</div>
</div>"""
    st.markdown(preview_score_html, unsafe_allow_html=True)


def render_screen_1_landing():
    render_hero()
    render_features()
    render_how_it_works()


# ==============================================================================
# SCREEN 2: Upload Scanner
# ==============================================================================
def render_screen_2_upload():
    if st.button("← Back to Landing", key="back_to_landing"):
        go_to_screen("landing")
        st.rerun()

    st.markdown("""<div style="text-align:center; max-width:720px; margin:10px auto 30px auto;">
<div style="font-family:'JetBrains Mono',monospace; font-size:0.76rem; color:#34D399;
letter-spacing:0.18em; text-transform:uppercase; margin-bottom:6px;">
HOLOGRAPHIC SCANNER CHAMBER
</div>
<div style="font-family:'Space Grotesk',sans-serif; font-size:2.5rem; font-weight:800;
color:#FFFFFF; margin-bottom:10px; letter-spacing:-0.02em;">
LET'S ANALYZE YOUR PRODUCT
</div>
<div style="font-size:1.02rem; color:#9AA7B5; line-height:1.6;">
Drop your product into the scanner. We'll extract the details that matter.
</div>
</div>""", unsafe_allow_html=True)

    uploaded_file = st.session_state.get("uploaded_file_obj")

    st.markdown('<div class="scanner-chamber-wrap"><div class="chamber-portal">', unsafe_allow_html=True)

    if uploaded_file is None:
        st.markdown("""<div class="chamber-empty-hologram">
<div style="font-size:3.5rem; margin-bottom:12px;">📡</div>
<div style="font-family:'Space Grotesk',sans-serif; font-size:1.3rem; font-weight:700;
color:#FFFFFF; margin-bottom:6px;">Drop Product Image Here</div>
<div style="font-size:0.86rem; color:#9AA7B5; max-width:380px; margin:0 auto 16px auto;">
Supports JPG, JPEG, and PNG packet labels up to 10MB.
</div>
</div>""", unsafe_allow_html=True)

        new_file = st.file_uploader(
            "CHOOSE PRODUCT IMAGE",
            type=["jpg", "jpeg", "png"],
            key="chamber_uploader",
            label_visibility="collapsed",
        )
        if new_file is not None:
            st.session_state["uploaded_file_obj"] = new_file
            st.rerun()
    else:
        is_valid, validation_err = image_utils.validate_image_file(uploaded_file)
        if not is_valid:
            st.error(f"❌ {validation_err}")
            if st.button("Try Another File", key="err_reset_btn"):
                st.session_state["uploaded_file_obj"] = None
                st.rerun()
        else:
            active_img = image_utils.load_image(uploaded_file)
            meta = image_utils.get_image_metadata(active_img, uploaded_file.name, uploaded_file.size)

            st.markdown(f"""<div class="preview-chamber-frame">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
<span style="font-family:'JetBrains Mono',monospace; font-size:0.76rem; color:#34D399; font-weight:700;">
● PRODUCT INGESTED IN CHAMBER
</span>
<span style="font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#9AA7B5;">
{meta['filename']}
</span>
</div>""", unsafe_allow_html=True)

            st.image(active_img, use_container_width=True)

            st.markdown(f"""<div class="meta-chip-row">
<span class="meta-chip"><span>📐</span> RESOLUTION: <strong>{meta['resolution']}</strong></span>
<span class="meta-chip"><span>💾</span> FILE SIZE: <strong>{meta['filesize']}</strong></span>
<span class="meta-chip"><span>🏷️</span> FORMAT: <strong>{meta['format']}</strong></span>
</div></div>""", unsafe_allow_html=True)

            st.write("")
            col_act1, col_act2 = st.columns([1.6, 1])
            with col_act1:
                run_ocr = st.button("🔬 ANALYZE LABEL", key="btn_run_analyze_label",
                                    use_container_width=True)
            with col_act2:
                if st.button("🗑️ Remove / Replace", key="btn_remove_chamber",
                             use_container_width=True):
                    st.session_state["uploaded_file_obj"] = None
                    st.session_state["analysis_results"]  = None
                    st.rerun()

            if run_ocr:
                st.session_state["is_demo_mode"] = False
                ocr_diag = ocr_utils.check_ocr_availability()

                if not ocr_diag["available"]:
                    st.error(f"❌ OCR Engine Unavailable:\n{ocr_diag['message']}")
                    st.info(
                        "💡 **Demo Available:** Return to the Landing Page and click "
                        "'Sample Demo Packet' to inspect the full results flow!"
                    )
                else:
                    progress_ph = st.empty()
                    with progress_ph.container():
                        st.markdown("""<div class="chamber-terminal">
&gt; [CAMERA] Reading optical sensor array...<br>
&gt; [PREPROCESS] Normalizing image channels &amp; contrast...
</div>""", unsafe_allow_html=True)
                        time.sleep(0.3)
                        processed_img = image_utils.preprocess_image_for_ocr(active_img)

                    with progress_ph.container():
                        st.markdown("""<div class="chamber-terminal">
&gt; [PREPROCESS] Done. [OK]<br>
&gt; [OCR] Extracting packaging text with Tesseract...
</div>""", unsafe_allow_html=True)
                        time.sleep(0.3)
                        ocr_result = ocr_utils.extract_raw_text(processed_img)

                    progress_ph.empty()

                    if not ocr_result["success"]:
                        st.warning(f"⚠️ {ocr_result['error_message']}")
                        if ocr_result.get("raw_text"):
                            with st.expander("📄 Raw OCR output (for debugging)", expanded=True):
                                st.text_area("Raw OCR", value=ocr_result["raw_text"],
                                             height=180, disabled=True,
                                             label_visibility="collapsed")
                    else:
                        extracted_text = ocr_result["text"]
                        raw_ocr_text   = ocr_result.get("raw_text", extracted_text)

                        results = _run_full_pipeline(extracted_text, raw_ocr_text)
                        st.session_state["analysis_results"] = results
                        scan_history.add_to_history(st.session_state, results)
                        go_to_screen("results")
                        st.rerun()

    st.markdown('</div></div>', unsafe_allow_html=True)


# ==============================================================================
# SCREEN 3: Results Dashboard
# ==============================================================================
def render_screen_3_results():
    # Top nav
    top_cols = st.columns([1.2, 1.2, 1.2, 5])
    top_col1, top_col2, top_col3, _ = top_cols[0], top_cols[1], top_cols[2], top_cols[3]
    with top_col1:
        if st.button("← Scan Another", key="btn_scan_another"):
            go_to_screen("upload")
            st.rerun()
    with top_col2:
        if st.button("🕓 History", key="btn_view_hist"):
            go_to_screen("history")
            st.rerun()

    results = st.session_state.get("analysis_results")
    if not results:
        st.warning("⚠️ No analysis data. Please upload an image first.")
        if st.button("Go to Scanner"):
            go_to_screen("upload")
            st.rerun()
        return

    fields      = results.get("fields", {})
    nutrients   = results.get("nutrients", {})
    score_data  = results.get("health_score", {})
    is_demo     = results.get("is_demo", False)

    # Safe fallbacks
    p_name    = fields.get("product_name") or "Not detected"
    p_brand   = fields.get("brand_name")   or "Not detected"
    p_mrp     = fields.get("mrp")          or "Not detected"
    p_mfg     = fields.get("mfg_date")     or "Not detected"
    p_pack    = fields.get("pack_date")    or "Not detected"
    p_exp     = fields.get("expiry_date")  or "Not detected"
    p_best    = fields.get("best_before")  or "Not detected"
    p_ing     = fields.get("ingredients")  or "Not detected"
    p_serving = fields.get("serving_size") or "Not detected"
    name_detected = bool(fields.get("product_name"))

    # ── Hero card ─────────────────────────────────────────────────────────────
    st.markdown(f"""<div class="results-hero-card">
<div style="display:flex; justify-content:space-between; align-items:center;">
<span style="font-family:'JetBrains Mono',monospace; font-size:0.75rem; color:#34D399;
font-weight:700; letter-spacing:0.1em;">EXTRACTED PRODUCT IDENTITY</span>
<span class="status-pill {'status-success' if name_detected else 'status-muted'}">
{'DETECTED' if name_detected else 'NOT DETECTED'}
</span>
</div>
<div class="product-hero-title">{p_name}</div>
<div style="display:flex; flex-wrap:wrap; gap:16px; font-family:'JetBrains Mono',monospace;
font-size:0.8rem; color:#9AA7B5; margin-top:6px;">
<span>BRAND: <strong style="color:#FFFFFF;">{p_brand}</strong></span>
<span>&bull;</span>
<span>MRP: <strong style="color:#FFFFFF;">{p_mrp}</strong></span>
<span>&bull;</span>
<span>MFG: <strong style="color:#FFFFFF;">{p_mfg}</strong></span>
<span>&bull;</span>
<span>BEST BEFORE: <strong style="color:#FFFFFF;">
{p_best if p_best != "Not detected" else p_exp}
</strong></span>
</div>
</div>""", unsafe_allow_html=True)

    # ── Telemetry row 1 ───────────────────────────────────────────────────────
    tel_cols1 = st.columns(4)
    for i, (label, icon, val) in enumerate([
        ("MRP / PRICE",   "💳", p_mrp),
        ("MFG DATE",      "🏭", p_mfg),
        ("PACK DATE",     "📦", p_pack),
        ("EXPIRY DATE",   "⏳", p_exp),
    ]):
        with tel_cols1[i]:
            st.markdown(f"""<div class="telemetry-card">
<div class="telemetry-label">{icon} {label}</div>
<div class="telemetry-value">{val}</div>
</div>""", unsafe_allow_html=True)

    st.write("")

    # ── Telemetry row 2 ───────────────────────────────────────────────────────
    tel_cols2 = st.columns(4)
    ing_count = len(p_ing.split(",")) if fields.get("ingredients") else 0
    for i, (label, icon, val) in enumerate([
        ("BEST BEFORE",       "📅", p_best),
        ("SERVING SIZE",      "🥣", p_serving),
        ("BRAND",             "🏷️", p_brand),
        ("INGREDIENTS COUNT", "🌱",
         f"{ing_count} detected" if ing_count else "Not detected"),
    ]):
        with tel_cols2[i]:
            st.markdown(f"""<div class="telemetry-card">
<div class="telemetry-label">{icon} {label}</div>
<div class="telemetry-value" style="font-size:1rem;">{val}</div>
</div>""", unsafe_allow_html=True)

    st.write("")

    # ── Ingredients block ─────────────────────────────────────────────────────
    st.markdown(f"""<div class="telemetry-card" style="margin-bottom:24px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
<div class="telemetry-label" style="margin-bottom:0;">🥗 FULL INGREDIENTS LISTING</div>
<span class="status-pill {'status-success' if fields.get('ingredients') else 'status-muted'}">
{'PARSED' if fields.get('ingredients') else 'NOT DETECTED'}
</span>
</div>
<div style="font-size:0.95rem; line-height:1.65;
color:{'#F1F5F9' if fields.get('ingredients') else '#64748B'};">{p_ing}</div>
</div>""", unsafe_allow_html=True)

    # ── Health Score ──────────────────────────────────────────────────────────
    st.markdown("""<div style="font-family:'Space Grotesk',sans-serif; font-size:1.35rem;
font-weight:700; color:#FFFFFF; margin-bottom:14px; display:flex; align-items:center; gap:8px;">
<span style="color:#22D3EE;">💯</span> Health Score
</div>""", unsafe_allow_html=True)
    if score_data:
        render_health_score(score_data)

    # ── Nutrition matrix heading ───────────────────────────────────────────────
    st.markdown("""<div style="font-family:'Space Grotesk',sans-serif; font-size:1.35rem;
font-weight:700; color:#FFFFFF; margin-bottom:14px; display:flex; align-items:center; gap:8px;">
<span style="color:#34D399;">📊</span> Nutrition Evaluation Matrix (Per 100g Guidelines)
</div>""", unsafe_allow_html=True)

    evaluation_rows = nutrition_rules.compare_all_nutrients(nutrients)

    # 5-column metric cards — row A (nutrients 0-4)
    cols_a = st.columns(5)
    for idx, row in enumerate(evaluation_rows[:5]):
        st_type = row["status_type"]
        badge_class = f"status-{st_type}" if st_type in ["success","alert","warning","neutral"] else "status-muted"
        val_display = (
            f"{row['extracted_value']} {row['unit']}"
            if row['extracted_value'] != "Not detected" else "Not detected"
        )
        val_color = (
            "#F87171" if st_type == "alert" else
            "#34D399" if st_type == "success" else
            "#FBBF24" if st_type == "warning" else "#F1F5F9"
        )
        with cols_a[idx]:
            st.markdown(f"""<div class="nutrient-metric-box">
<div style="font-family:'JetBrains Mono',monospace; font-size:0.72rem;
color:#A7F3D0; font-weight:700; text-transform:uppercase;">{row['nutrient']}</div>
<div class="nutrient-metric-value" style="color:{val_color};">{val_display}</div>
<div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem;
color:#9AA7B5; margin-bottom:10px;">BENCHMARK: {row['threshold']}</div>
<span class="status-pill {badge_class}">{row['status']}</span>
</div>""", unsafe_allow_html=True)

    st.write("")

    # 5-column metric cards — row B (nutrients 5-9)
    cols_b = st.columns(5)
    for idx, row in enumerate(evaluation_rows[5:10]):
        st_type = row["status_type"]
        badge_class = f"status-{st_type}" if st_type in ["success","alert","warning","neutral"] else "status-muted"
        val_display = (
            f"{row['extracted_value']} {row['unit']}"
            if row['extracted_value'] != "Not detected" else "Not detected"
        )
        val_color = (
            "#F87171" if st_type == "alert" else
            "#34D399" if st_type == "success" else
            "#FBBF24" if st_type == "warning" else "#F1F5F9"
        )
        with cols_b[idx]:
            st.markdown(f"""<div class="nutrient-metric-box">
<div style="font-family:'JetBrains Mono',monospace; font-size:0.72rem;
color:#A7F3D0; font-weight:700; text-transform:uppercase;">{row['nutrient']}</div>
<div class="nutrient-metric-value" style="color:{val_color};">{val_display}</div>
<div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem;
color:#9AA7B5; margin-bottom:10px;">BENCHMARK: {row['threshold']}</div>
<span class="status-pill {badge_class}">{row['status']}</span>
</div>""", unsafe_allow_html=True)

    st.write("")

    # Full nutrition table
    rows_html = ""
    for row in evaluation_rows:
        st_type = row["status_type"]
        badge_class = f"status-{st_type}" if st_type in ["success","alert","warning","neutral"] else "status-muted"
        badge_html  = f'<span class="status-pill {badge_class}">{row["status"]}</span>'
        ext_display = (
            f"{row['extracted_value']} {row['unit']}"
            if row['extracted_value'] != "Not detected"
            else '<span style="color:#64748B; font-style:italic;">Not detected</span>'
        )
        rows_html += f"""<tr>
<td style="font-weight:600; color:#FFFFFF;">{row['nutrient']}</td>
<td style="font-family:'JetBrains Mono',monospace; font-weight:600;">{ext_display}</td>
<td style="color:#9AA7B5; font-family:'JetBrains Mono',monospace;">{row['serving_basis']}</td>
<td style="color:#CBD5E1; font-family:'JetBrains Mono',monospace;">{row['threshold']}</td>
<td>{badge_html}</td>
</tr>"""

    st.markdown(f"""<table class="cyber-table">
<thead><tr>
<th>Nutrient Component</th><th>Extracted Value</th>
<th>Serving Basis</th><th>Configured Threshold</th><th>Status</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>""", unsafe_allow_html=True)

    # Missing fields notice
    missing_fields = [
        name for name, val in {
            "Product Name":          fields.get("product_name"),
            "Brand":                 fields.get("brand_name"),
            "MRP":                   fields.get("mrp"),
            "Mfg Date":              fields.get("mfg_date"),
            "Expiry / Best Before":  fields.get("expiry_date") or fields.get("best_before"),
            "Ingredients":           fields.get("ingredients"),
            "Serving Size":          fields.get("serving_size"),
        }.items() if not val
    ]
    missing_nutrients = [
        r["nutrient"] for r in evaluation_rows if r["extracted_value"] == "Not detected"
    ]
    if missing_fields or missing_nutrients:
        st.write("")
        all_missing = missing_fields + missing_nutrients
        st.markdown(f"""<div style="background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.3);
border-radius:12px; padding:14px 18px; margin-top:4px;">
<span style="font-family:'JetBrains Mono',monospace; font-size:0.74rem; color:#FBBF24; font-weight:700;">
⚠ NOT DETECTED / NEEDS REVIEW
</span>
<div style="font-size:0.88rem; color:#CBD5E1; margin-top:6px; line-height:1.6;">
The following fields could not be reliably extracted:
<strong style="color:#FDE68A;">{", ".join(all_missing)}</strong>.<br>
Please verify these directly on the physical product packaging.
</div>
</div>""", unsafe_allow_html=True)

    st.write("")

    # ── Risk Alerts ───────────────────────────────────────────────────────────
    render_risk_alerts(results)

    st.write("")

    # ── Allergen Detection ────────────────────────────────────────────────────
    render_allergen_panel(
        results.get("allergen_analysis", {}),
        is_demo=results.get("is_demo", False),
    )

    st.write("")

    # ── Export Section ────────────────────────────────────────────────────────
    render_export_section(results)

    st.write("")

    # ── Raw OCR Expander ──────────────────────────────────────────────────────
    with st.expander("📄 View Raw Extracted OCR Text", expanded=False):
        raw_stream      = results.get("raw_text", "")
        raw_ocr_unclean = results.get("raw_ocr_text", "")
        if not raw_stream.strip():
            st.warning("No readable text detected in current buffer.")
        else:
            if results.get("is_demo"):
                st.caption("💡 Stream sourced from sample demonstration packet (not real OCR output):")
            st.caption("Cleaned text (used for extraction):")
            st.text_area("Cleaned Text Buffer", value=raw_stream, height=180,
                         disabled=True, label_visibility="collapsed", key="cleaned_ocr_ta")
            if raw_ocr_unclean and raw_ocr_unclean != raw_stream:
                st.caption("Raw Tesseract output (before cleanup):")
                st.text_area("Raw OCR Buffer", value=raw_ocr_unclean, height=140,
                             disabled=True, label_visibility="collapsed", key="raw_ocr_ta")


# ==============================================================================
# Risk Alerts (inline in results)
# ==============================================================================
def render_risk_alerts(results: dict) -> None:
    risk    = results.get("risk_analysis")
    is_demo = results.get("is_demo", False)
    if not risk:
        return

    st.markdown(f"""
<div style="font-family:'Space Grotesk',sans-serif; font-size:1.35rem; font-weight:700;
color:#FFFFFF; margin:28px 0 6px 0; display:flex; align-items:center; gap:8px;">
<span style="color:#F87171;">🚨</span> Nutrition Risk Alerts
</div>
<div style="font-size:0.82rem; color:#9AA7B5; margin-bottom:16px; line-height:1.5;
font-family:'Inter',sans-serif; max-width:820px;">
<strong style="color:#FBBF24;">Educational disclaimer:</strong>
Alerts are informational comparisons against documented reference thresholds.
They are <em>not</em> a medical diagnosis or recommendation to avoid any food.
{"<br><strong style='color:#34D399;'>ℹ This is a demonstration with sample data.</strong>" if is_demo else ""}
</div>
""", unsafe_allow_html=True)

    # Part A
    quant = risk.get("quantitative_alerts", [])
    if not risk.get("nutrition_available"):
        st.markdown("""<div class="risk-no-data-box"><span>📊</span>
<div><strong>No nutrition values detected</strong><br>
<span style="color:#9AA7B5; font-size:0.88rem;">
Quantitative alerts require a nutrition facts table in the OCR output.
</span></div></div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div style="font-family:'JetBrains Mono',monospace; font-size:0.74rem;
color:#34D399; letter-spacing:0.1em; font-weight:700; margin-bottom:10px;">
PART A — QUANTITATIVE NUTRITION ALERTS (per 100g thresholds)
</div>""", unsafe_allow_html=True)

        ordered = (
            [a for a in quant if a["status"] == "HIGH"] +
            [a for a in quant if a["status"] == "MODERATE"] +
            [a for a in quant if a["status"] == "OK"] +
            [a for a in quant if a["status"] == "UNKNOWN"]
        )
        for alert in ordered:
            status = alert["status"]
            badge  = risk_badge_html(status)
            border_color = {
                "HIGH":     "rgba(248,113,113,0.45)",
                "MODERATE": "rgba(251,191,36,0.45)",
                "OK":       "rgba(52,211,153,0.3)",
                "UNKNOWN":  "rgba(100,116,139,0.3)",
            }.get(status, "rgba(100,116,139,0.3)")
            bg_color = {
                "HIGH":     "rgba(248,113,113,0.06)",
                "MODERATE": "rgba(251,191,36,0.05)",
                "OK":       "rgba(52,211,153,0.04)",
                "UNKNOWN":  "rgba(100,116,139,0.05)",
            }.get(status, "rgba(100,116,139,0.05)")

            expanded = ""
            if status in ("HIGH", "MODERATE"):
                expanded = f"""
<div class="risk-detail-row">
<span class="risk-detail-label">Why this matters</span>
<span class="risk-detail-text">{alert['why']}</span>
</div>
<div class="risk-detail-row">
<span class="risk-detail-label">Possible long-term risk</span>
<span class="risk-detail-text" style="color:#FBBF24;">{alert['risk']}</span>
</div>
<div class="risk-detail-row">
<span class="risk-detail-label">Suggestion</span>
<span class="risk-detail-text" style="color:#A7F3D0;">{alert['suggestion']}</span>
</div>"""

            basis_warn_html = ""
            if alert.get("basis_warning"):
                basis_warn_html = f"""
<div style="background:rgba(251,191,36,0.08); border:1px solid rgba(251,191,36,0.3);
border-radius:8px; padding:8px 12px; margin-top:8px; font-size:0.82rem; color:#FDE68A;">
⚠ Serving basis note: {alert['basis_warning']}
</div>"""

            st.markdown(f"""
<div style="background:{bg_color}; border:1px solid {border_color};
border-radius:14px; padding:16px 20px; margin-bottom:12px;">
<div style="display:flex; justify-content:space-between; align-items:center;
flex-wrap:wrap; gap:8px;">
<div style="font-family:'Space Grotesk',sans-serif; font-size:1.05rem;
font-weight:700; color:#FFFFFF;">{alert['nutrient']}</div>
{badge}
</div>
<div style="display:flex; flex-wrap:wrap; gap:20px; margin-top:10px;
font-family:'JetBrains Mono',monospace; font-size:0.8rem;">
<span style="color:#E2E8F0;">Value: <strong>{alert['value_display']}</strong></span>
<span style="color:#9AA7B5;">Threshold: {alert['threshold_text']}</span>
</div>
<div style="font-size:0.77rem; color:#64748B; margin-top:6px;
font-family:'Inter',sans-serif;">Source: {alert['source']}</div>
{expanded}{basis_warn_html}
</div>
""", unsafe_allow_html=True)

    st.write("")

    # Part B
    ing_flags = risk.get("ingredient_flags", [])
    st.markdown("""<div style="font-family:'JetBrains Mono',monospace; font-size:0.74rem;
color:#34D399; letter-spacing:0.1em; font-weight:700; margin-bottom:10px;">
PART B — INGREDIENT FLAGS (based on terms found in OCR text)
</div>""", unsafe_allow_html=True)

    if not risk.get("ingredients_available"):
        st.markdown("""<div class="risk-no-data-box"><span>🥗</span>
<div><strong>No ingredients text detected</strong><br>
<span style="color:#9AA7B5; font-size:0.88rem;">
Ingredient flags require a readable ingredients list.
</span></div></div>""", unsafe_allow_html=True)
    elif not ing_flags:
        st.markdown("""<div class="risk-no-data-box" style="border-color:rgba(52,211,153,0.3);
background:rgba(52,211,153,0.04);">
<span>✅</span>
<div><strong style="color:#34D399;">No flagged ingredients detected</strong><br>
<span style="color:#9AA7B5; font-size:0.88rem;">
None of the monitored ingredient terms were found in the extracted text.
</span></div></div>""", unsafe_allow_html=True)
    else:
        sev_order = {"high": 0, "moderate": 1, "info": 2}
        sorted_flags = sorted(ing_flags, key=lambda f: sev_order.get(f["severity"], 3))
        for flag in sorted_flags:
            sev   = flag["severity"]
            badge = ing_badge_html(sev)
            found_str = ", ".join(f"<code>{t}</code>" for t in flag["found_terms"])
            border_color = {
                "high":     "rgba(248,113,113,0.4)",
                "moderate": "rgba(251,191,36,0.4)",
                "info":     "rgba(52,211,153,0.25)",
            }.get(sev, "rgba(100,116,139,0.3)")
            bg_color = {
                "high":     "rgba(248,113,113,0.05)",
                "moderate": "rgba(251,191,36,0.04)",
                "info":     "rgba(52,211,153,0.03)",
            }.get(sev, "rgba(100,116,139,0.04)")

            st.markdown(f"""
<div style="background:{bg_color}; border:1px solid {border_color};
border-radius:14px; padding:16px 20px; margin-bottom:12px;">
<div style="display:flex; justify-content:space-between; align-items:center;
flex-wrap:wrap; gap:8px;">
<div style="font-family:'Space Grotesk',sans-serif; font-size:1.0rem;
font-weight:700; color:#FFFFFF;">{flag['name']}</div>
{badge}
</div>
<div style="font-size:0.8rem; color:#94A3B8; margin-top:6px;
font-family:'JetBrains Mono',monospace;">
Category: {flag['category']} &nbsp;·&nbsp; Found in label: {found_str}
</div>
<div style="font-size:0.88rem; color:#E2E8F0; margin-top:10px;
line-height:1.6; font-family:'Inter',sans-serif;">{flag['note']}</div>
<div style="font-size:0.84rem; color:#A7F3D0; margin-top:8px;
font-family:'Inter',sans-serif;"><strong>Suggestion:</strong> {flag['suggestion']}</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("""
<div style="background:rgba(100,116,139,0.06); border:1px solid rgba(100,116,139,0.2);
border-radius:10px; padding:12px 16px; margin-top:8px; font-size:0.8rem;
color:#64748B; line-height:1.6; font-family:'Inter',sans-serif;">
⚠ <strong style="color:#94A3B8;">Important:</strong>
These alerts are educational comparisons against publicly available reference thresholds
(NHS UK, WHO, FSSAI). They are not medical diagnoses, safety guarantees, or dietary
prescriptions. Individual nutritional needs vary. Consult a registered dietitian for
personal dietary advice.
</div>
""", unsafe_allow_html=True)


# ==============================================================================
# Export Section
# ==============================================================================
def render_export_section(results: dict) -> None:
    st.markdown("""<div style="font-family:'Space Grotesk',sans-serif; font-size:1.35rem;
font-weight:700; color:#FFFFFF; margin:28px 0 6px 0; display:flex; align-items:center; gap:8px;">
<span style="color:#34D399;">📥</span> Download Report
</div>
<div style="font-size:0.82rem; color:#9AA7B5; margin-bottom:16px;">
Export the full analysis as a PDF report or CSV spreadsheet.
</div>""", unsafe_allow_html=True)

    product_name = (results.get("fields") or {}).get("product_name") or "analysis"
    safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in product_name)
    safe_name = safe_name.strip().replace(' ', '_')[:40]

    col_csv, col_pdf = st.columns([1, 1])

    with col_csv:
        try:
            csv_bytes = export_engine.generate_csv(results)
            st.download_button(
                label="⬇ Download CSV Report",
                data=csv_bytes,
                file_name=f"vedanshu_{safe_name}.csv",
                mime="text/csv",
                use_container_width=True,
                key="dl_csv",
            )
        except Exception as e:
            st.error(f"CSV generation failed: {e}")

    with col_pdf:
        try:
            pdf_bytes = export_engine.generate_pdf(results)
            mime_type = "application/pdf"
            ext       = "pdf"
            # If reportlab missing, it falls back to plaintext
            try:
                import reportlab
            except ImportError:
                mime_type = "text/plain"
                ext       = "txt"
            st.download_button(
                label="⬇ Download PDF Report",
                data=pdf_bytes,
                file_name=f"vedanshu_{safe_name}.{ext}",
                mime=mime_type,
                use_container_width=True,
                key="dl_pdf",
            )
            if ext == "txt":
                st.caption(
                    "💡 Install `reportlab` for a proper PDF: `pip install reportlab`. "
                    "Currently downloading as plain text."
                )
        except Exception as e:
            st.error(f"PDF generation failed: {e}")


# ==============================================================================
# SCREEN 4: Scan History
# ==============================================================================
def render_screen_4_history():
    if st.button("← Back", key="hist_back"):
        prev = "results" if st.session_state.get("analysis_results") else "landing"
        go_to_screen(prev)
        st.rerun()

    st.markdown("""<div style="font-family:'Space Grotesk',sans-serif; font-size:2rem;
font-weight:800; color:#FFFFFF; margin-bottom:6px;">🕓 Scan History</div>
<div style="font-size:0.9rem; color:#9AA7B5; margin-bottom:20px;">
Session log of all analyses. Cleared when you close the browser tab.
</div>""", unsafe_allow_html=True)

    history = scan_history.get_history(st.session_state)

    hc1, hc2 = st.columns([3, 1])
    with hc2:
        if history and st.button("🗑️ Clear History", key="clear_hist_btn",
                                  use_container_width=True):
            scan_history.clear_history(st.session_state)
            st.rerun()

    render_scan_history(history)


# ==============================================================================
# Footer
# ==============================================================================
def render_footer():
    st.markdown("""<div class="vedanshu-footer">
VEDANSHU &bull; PRODUCT PACKET ANALYSER &bull; INFORMATIONAL PROTOTYPE &bull; NOT MEDICAL ADVICE
</div>""", unsafe_allow_html=True)


# ==============================================================================
# Main Router
# ==============================================================================
render_navbar()

current_screen = st.session_state.get("screen", "landing")

if current_screen == "landing":
    render_screen_1_landing()
elif current_screen == "upload":
    render_screen_2_upload()
elif current_screen == "results":
    render_screen_3_results()
elif current_screen == "history":
    render_screen_4_history()
else:
    go_to_screen("landing")
    st.rerun()

render_footer()
