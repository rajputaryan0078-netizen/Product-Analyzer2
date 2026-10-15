"""
Health Score Engine — VEDANSHU Product Packet Analyser.

Computes a 0–100 health score from extracted nutrition data.
The score is a weighted composite of six nutrient evaluations using
NHS UK traffic-light thresholds (per 100g basis).

SCORING METHODOLOGY
-------------------
Each nutrient contributes a component score (0–100):

  PENALTY nutrients (lower is better):
    - Sugar         weight 20  — HIGH>22.5g → 0,  OK≤5g → 100
    - Saturated Fat weight 20  — HIGH>5g    → 0,  OK≤1.5g → 100
    - Trans Fat     weight 15  — HIGH>2g    → 0,  OK≤0.2g → 100
    - Sodium        weight 15  — HIGH>600mg → 0,  OK≤300mg → 100

  REWARD nutrients (higher is better):
    - Protein       weight 15  — LOW<5g     → 0,  HIGH≥10g → 100
    - Dietary Fibre weight 15  — LOW<3g     → 0,  HIGH≥6g  → 100

  Scores for each component are clamped to [0, 100].
  Final score = weighted sum of component scores (sum of weights = 100).
  If a nutrient is not detected, it contributes 50 (neutral — neither rewarded
  nor penalised, since absence of data is not evidence of absence of the nutrient).

GRADE BANDS
-----------
  ≥ 75  →  A  (Green)   — Healthy / Well-balanced
  ≥ 55  →  B  (Cyan)    — Acceptable
  ≥ 35  →  C  (Amber)   — Moderate concern
  <  35  →  D  (Red)     — High concern

DISCLAIMER
----------
This score is a simplified educational estimate. It does not constitute
a medical, dietary, or safety recommendation.  Individual nutritional
requirements vary; consult a registered dietitian for personal advice.
"""

from typing import Dict, Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

_SCORE_CONFIG: Dict[str, Dict[str, Any]] = {
    "Sugar": {
        "weight": 20,
        "direction": "penalty",   # low is better
        "unit": "g",
        "ok_limit":   5.0,        # ≤ this → component score 100
        "high_limit": 22.5,       # ≥ this → component score 0
    },
    "Saturated Fat": {
        "weight": 20,
        "direction": "penalty",
        "unit": "g",
        "ok_limit":   1.5,
        "high_limit": 5.0,
    },
    "Trans Fat": {
        "weight": 15,
        "direction": "penalty",
        "unit": "g",
        "ok_limit":   0.2,
        "high_limit": 2.0,
    },
    "Sodium": {
        "weight": 15,
        "direction": "penalty",
        "unit": "mg",
        "ok_limit":   300.0,
        "high_limit": 600.0,
    },
    "Protein": {
        "weight": 15,
        "direction": "reward",    # high is better
        "unit": "g",
        "low_limit":  5.0,        # ≤ this → component score 0
        "high_limit": 10.0,       # ≥ this → component score 100
    },
    "Dietary Fibre": {
        "weight": 15,
        "direction": "reward",
        "unit": "g",
        "low_limit":  3.0,
        "high_limit": 6.0,
    },
}

_GRADE_BANDS = [
    (75, "A", "Healthy",          "#34D399", "rgba(52,211,153,0.15)",  "rgba(52,211,153,0.5)"),
    (55, "B", "Acceptable",       "#22D3EE", "rgba(34,211,238,0.12)",  "rgba(34,211,238,0.45)"),
    (35, "C", "Moderate Concern", "#FBBF24", "rgba(251,191,36,0.12)",  "rgba(251,191,36,0.45)"),
    ( 0, "D", "High Concern",     "#F87171", "rgba(248,113,113,0.12)", "rgba(248,113,113,0.45)"),
]

_NEUTRAL_SCORE = 50.0  # used when a nutrient value is absent


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _component_score(nutrient: str, value: float, unit: str, cfg: Dict[str, Any]) -> float:
    """Return a 0–100 component score for one nutrient value."""
    # Normalise Sodium: if extracted in grams, convert to mg
    if nutrient == "Sodium" and unit.lower().strip() in ("g", "gm"):
        value = value * 1000.0

    direction = cfg["direction"]

    if direction == "penalty":
        ok   = cfg["ok_limit"]
        high = cfg["high_limit"]
        if value <= ok:
            return 100.0
        if value >= high:
            return 0.0
        # Linear interpolation between ok and high
        return 100.0 * (1.0 - (value - ok) / (high - ok))

    else:  # reward
        low  = cfg["low_limit"]
        high = cfg["high_limit"]
        if value >= high:
            return 100.0
        if value <= low:
            return 0.0
        return 100.0 * (value - low) / (high - low)


def _get_grade(score: float):
    """Return (letter, label, color, bg, border) for a given score."""
    for threshold, letter, label, color, bg, border in _GRADE_BANDS:
        if score >= threshold:
            return letter, label, color, bg, border
    return "D", "High Concern", "#F87171", "rgba(248,113,113,0.12)", "rgba(248,113,113,0.45)"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def compute_health_score(nutrients: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes the health score from the nutrient dict produced by
    extractor.extract_nutrition_values().

    Returns:
      {
        "score":        int,         0–100
        "grade":        str,         "A" / "B" / "C" / "D"
        "grade_label":  str,         e.g. "Healthy"
        "color":        str,         hex color
        "bg":           str,         rgba background
        "border":       str,         rgba border
        "components":   list[dict],  per-nutrient breakdown
        "detected_count": int,       number of nutrients actually detected
        "total_count":  int,         total nutrients evaluated
        "note":         str,         disclaimer
      }
    """
    components = []
    weighted_total = 0.0
    weight_sum = 0

    for nutrient, cfg in _SCORE_CONFIG.items():
        data  = nutrients.get(nutrient, {})
        value = data.get("value")
        unit  = data.get("unit") or cfg["unit"]

        if value is None:
            comp_score = _NEUTRAL_SCORE
            detected   = False
        else:
            comp_score = _component_score(nutrient, value, unit, cfg)
            detected   = True

        weight = cfg["weight"]
        weighted_total += comp_score * weight
        weight_sum     += weight

        components.append({
            "nutrient":    nutrient,
            "value":       value,
            "unit":        unit,
            "component_score": round(comp_score, 1),
            "weight":      weight,
            "direction":   cfg["direction"],
            "detected":    detected,
        })

    final_score = round(weighted_total / weight_sum) if weight_sum > 0 else 50
    final_score = max(0, min(100, final_score))

    detected_count = sum(1 for c in components if c["detected"])
    grade, label, color, bg, border = _get_grade(final_score)

    # Build a short summary sentence
    high_penalty = [c["nutrient"] for c in components
                    if c["direction"] == "penalty" and c["component_score"] <= 30 and c["detected"]]
    high_reward  = [c["nutrient"] for c in components
                    if c["direction"] == "reward"  and c["component_score"] >= 70 and c["detected"]]

    if high_penalty and high_reward:
        summary = f"High in {', '.join(high_penalty)}; good source of {', '.join(high_reward)}."
    elif high_penalty:
        summary = f"Elevated {', '.join(high_penalty)} — consider moderation."
    elif high_reward:
        summary = f"Good source of {', '.join(high_reward)}."
    elif detected_count == 0:
        summary = "No nutrition data detected — score is neutral estimate."
    else:
        summary = "Balanced nutritional profile based on available data."

    return {
        "score":          final_score,
        "grade":          grade,
        "grade_label":    label,
        "color":          color,
        "bg":             bg,
        "border":         border,
        "components":     components,
        "detected_count": detected_count,
        "total_count":    len(components),
        "summary":        summary,
        "note": (
            "Score is a simplified educational estimate based on NHS per-100g "
            "traffic-light thresholds. It does not constitute a medical or dietary "
            "recommendation. Nutrients not detected contribute a neutral 50/100."
        ),
    }
