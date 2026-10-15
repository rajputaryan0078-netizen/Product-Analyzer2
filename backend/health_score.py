"""
Health Score Engine — VEDANSHU Product Packet Analyser.

Computes an evidence-based 0–100 health score from extracted nutrition facts.
The score is derived from reference per-100g guidelines (adapted from UK NHS/FSA
traffic-light benchmarks).

CRITICAL SCIENTIFIC & ENGINEERING PRINCIPLES:
---------------------------------------------
1. Never invent or assume missing data:
   If no usable nutrients are detected, score and grade are set to None with
   status="insufficient_data". No fake 50/100 Grade C is ever awarded.
2. Partial data handling:
   If at least 2 scoring nutrients are available, a partial score is calculated
   by re-normalizing weights across detected nutrients ONLY. Missing nutrients
   are never assigned an arbitrary neutral score (50).
3. Data coverage transparency:
   Reports exact nutrient coverage (e.g. 3/6 nutrients), list of evaluated nutrients,
   and list of missing nutrients.
4. Clear educational disclaimer:
   Educational reference estimate only. Not an official medical, dietary, or regulatory rating.
"""

from typing import Dict, Any, Optional, List, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Scoring Configuration (Reference per-100g benchmarks)
# ─────────────────────────────────────────────────────────────────────────────

_SCORE_CONFIG: Dict[str, Dict[str, Any]] = {
    "Sugar": {
        "weight": 20,
        "direction": "penalty",   # Lower is better
        "unit": "g",
        "ok_limit":   5.0,        # <= 5g/100g -> 100 pts
        "high_limit": 22.5,       # >= 22.5g/100g -> 0 pts
        "description": "Total/Added sugars benchmarked against NHS per-100g threshold",
    },
    "Saturated Fat": {
        "weight": 20,
        "direction": "penalty",
        "unit": "g",
        "ok_limit":   1.5,        # <= 1.5g/100g -> 100 pts
        "high_limit": 5.0,        # >= 5.0g/100g -> 0 pts
        "description": "Saturated fatty acids benchmarked against NHS per-100g threshold",
    },
    "Trans Fat": {
        "weight": 15,
        "direction": "penalty",
        "unit": "g",
        "ok_limit":   0.2,        # <= 0.2g/100g -> 100 pts
        "high_limit": 2.0,        # >= 2.0g/100g -> 0 pts
        "description": "Trans fat benchmarked against FSSAI/WHO guideline (<0.2g is optimal)",
    },
    "Sodium": {
        "weight": 15,
        "direction": "penalty",
        "unit": "mg",
        "ok_limit":   300.0,      # <= 300mg/100g -> 100 pts
        "high_limit": 600.0,      # >= 600mg/100g -> 0 pts
        "description": "Sodium content (mg per 100g). If only salt is present, converted safely",
    },
    "Protein": {
        "weight": 15,
        "direction": "reward",     # Higher is better
        "unit": "g",
        "low_limit":  5.0,        # <= 5g/100g -> 0 pts
        "high_limit": 10.0,       # >= 10g/100g -> 100 pts
        "description": "Protein content per 100g",
    },
    "Dietary Fibre": {
        "weight": 15,
        "direction": "reward",
        "unit": "g",
        "low_limit":  3.0,        # <= 3g/100g -> 0 pts
        "high_limit": 6.0,        # >= 6g/100g -> 100 pts
        "description": "Dietary fibre per 100g",
    },
}

_GRADE_BANDS = [
    (75, "A", "Healthy / Well-balanced", "#34D399", "rgba(52,211,153,0.15)",  "rgba(52,211,153,0.5)"),
    (55, "B", "Acceptable Profile",       "#22D3EE", "rgba(34,211,238,0.12)",  "rgba(34,211,238,0.45)"),
    (35, "C", "Moderate Concern",         "#FBBF24", "rgba(251,191,36,0.12)",  "rgba(251,191,36,0.45)"),
    ( 0, "D", "High Concern",             "#F87171", "rgba(248,113,113,0.12)", "rgba(248,113,113,0.45)"),
]

MIN_NUTRIENTS_FOR_SCORE = 2


# ─────────────────────────────────────────────────────────────────────────────
# Calculation Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _component_score(nutrient: str, value: float, unit: str, cfg: Dict[str, Any]) -> float:
    """Calculates a normalized 0–100 component score for a nutrient."""
    # Convert Sodium in grams to mg if needed
    if nutrient == "Sodium" and unit.lower().strip() in ("g", "gm"):
        value = value * 1000.0

    direction = cfg["direction"]

    if direction == "penalty":
        ok = cfg["ok_limit"]
        high = cfg["high_limit"]
        if value <= ok:
            return 100.0
        if value >= high:
            return 0.0
        return 100.0 * (1.0 - (value - ok) / (high - ok))
    else:  # reward
        low = cfg["low_limit"]
        high = cfg["high_limit"]
        if value >= high:
            return 100.0
        if value <= low:
            return 0.0
        return 100.0 * (value - low) / (high - low)


def _get_grade(score: int) -> Tuple[str, str, str, str, str]:
    """Returns (letter, label, color, bg, border) for a score."""
    for threshold, letter, label, color, bg, border in _GRADE_BANDS:
        if score >= threshold:
            return letter, label, color, bg, border
    return "D", "High Concern", "#F87171", "rgba(248,113,113,0.12)", "rgba(248,113,113,0.45)"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def compute_health_score(nutrients: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes health score from extracted nutrient facts.

    Behavior:
    - 0 or < 2 detected scoring nutrients -> status="insufficient_data", score=None, grade=None
    - >= 2 detected nutrients -> re-normalized weighted score with explicit coverage notice
    - All detected nutrients -> complete score
    """
    components = []
    evaluated_weights_sum = 0
    weighted_total = 0.0
    detected_nutrients = []
    missing_nutrients = []

    # Check for Sodium fallback to Salt: if Sodium is missing but Salt is present
    effective_nutrients = dict(nutrients)
    if effective_nutrients.get("Sodium", {}).get("value") is None and effective_nutrients.get("Salt", {}).get("value") is not None:
        salt_val = effective_nutrients["Salt"]["value"]
        # Salt (g) / 2.5 * 1000 = Sodium (mg)
        derived_sodium = (salt_val / 2.5) * 1000.0
        effective_nutrients["Sodium"] = {
            "value": derived_sodium,
            "unit": "mg",
            "derived_from": "Salt",
            "serving_basis": effective_nutrients["Salt"].get("serving_basis", "per 100g")
        }

    for nutrient, cfg in _SCORE_CONFIG.items():
        data = effective_nutrients.get(nutrient, {})
        val = data.get("value")
        unit = data.get("unit") or cfg["unit"]

        if val is not None:
            comp_score = _component_score(nutrient, val, unit, cfg)
            weight = cfg["weight"]
            weighted_total += comp_score * weight
            evaluated_weights_sum += weight
            detected_nutrients.append(nutrient)

            components.append({
                "nutrient": nutrient,
                "value": val,
                "unit": unit,
                "component_score": round(comp_score, 1),
                "weight": weight,
                "direction": cfg["direction"],
                "detected": True,
                "derived": bool(data.get("derived_from")),
            })
        else:
            missing_nutrients.append(nutrient)
            components.append({
                "nutrient": nutrient,
                "value": None,
                "unit": cfg["unit"],
                "component_score": None,
                "weight": cfg["weight"],
                "direction": cfg["direction"],
                "detected": False,
                "derived": False,
            })

    detected_count = len(detected_nutrients)
    total_count = len(_SCORE_CONFIG)
    coverage_pct = round((detected_count / total_count) * 100)

    # ── CASE 1: Insufficient Data (< MIN_NUTRIENTS_FOR_SCORE) ────────────────
    if detected_count < MIN_NUTRIENTS_FOR_SCORE:
        return {
            "status": "insufficient_data",
            "score": None,
            "grade": None,
            "grade_label": "Insufficient Data",
            "color": "#94A3B8",
            "bg": "rgba(100,116,139,0.10)",
            "border": "rgba(100,116,139,0.30)",
            "components": components,
            "detected_count": detected_count,
            "total_count": total_count,
            "coverage_pct": coverage_pct,
            "detected_nutrients": detected_nutrients,
            "missing_nutrients": missing_nutrients,
            "summary": (
                "Insufficient nutrition data detected on the package to calculate a "
                "reliable health score. A score is only computed when measured values are present."
            ),
            "note": (
                "Score is withheld because fewer than 2 scoring nutrients were found. "
                "VEDANSHU never fabricates neutral scores when label data is absent."
            ),
        }

    # ── CASE 2: Partial or Full Score Calculation ────────────────────────────
    final_score = round(weighted_total / evaluated_weights_sum)
    final_score = max(0, min(100, final_score))
    grade, label, color, bg, border = _get_grade(final_score)

    is_partial = detected_count < total_count

    # Build clear explanatory summary
    high_penalty = [
        c["nutrient"] for c in components
        if c["detected"] and c["direction"] == "penalty" and c["component_score"] <= 30
    ]
    high_reward = [
        c["nutrient"] for c in components
        if c["detected"] and c["direction"] == "reward" and c["component_score"] >= 70
    ]

    parts = []
    if high_penalty and high_reward:
        parts.append(f"High in {', '.join(high_penalty)}; good source of {', '.join(high_reward)}.")
    elif high_penalty:
        parts.append(f"Elevated {', '.join(high_penalty)} — moderation advised.")
    elif high_reward:
        parts.append(f"Favorable profile with good {', '.join(high_reward)}.")
    else:
        parts.append("Balanced profile across detected benchmarks.")

    if is_partial:
        parts.append(f"Partial evaluation based on {detected_count}/{total_count} nutrients.")
        status = "partial_data"
    else:
        status = "complete"

    summary_str = " ".join(parts)

    return {
        "status": status,
        "score": final_score,
        "grade": grade,
        "grade_label": label,
        "color": color,
        "bg": bg,
        "border": border,
        "components": components,
        "detected_count": detected_count,
        "total_count": total_count,
        "coverage_pct": coverage_pct,
        "detected_nutrients": detected_nutrients,
        "missing_nutrients": missing_nutrients,
        "summary": summary_str,
        "note": (
            "Score is a simplified educational estimate based on reference per-100g "
            "guidelines (NHS/WHO). It does not constitute an official medical, FSSAI, or dietary rating."
        ),
    }
