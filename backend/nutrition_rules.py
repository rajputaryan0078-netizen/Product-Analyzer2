"""
Nutrition rules and thresholds for the Product Packet Analyser.

Thresholds are configured reference guidelines (commonly used per-100g
food labelling benchmarks). They are informational only and do not
constitute medical, dietary, or safety advice.

Nutrients tracked (10 total):
  Energy, Carbohydrates, Sugar, Total Fat, Saturated Fat,
  Trans Fat, Protein, Dietary Fibre, Sodium, Salt.
"""

from typing import Dict, Any, Optional, List


# ---------------------------------------------------------------------------
# Configured thresholds
# ---------------------------------------------------------------------------
# Each entry defines the comparison rule plus display metadata.
# "direction" controls comparison:
#   "max"  → flag as ABOVE limit if value > max_limit (e.g. Sugar, Fat, Sodium)
#   "min"  → flag as BELOW guideline if value < min_limit (e.g. Protein, Fibre)
#   "info" → no pass/fail comparison; display value with informational status

DEFAULT_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "Energy": {
        "direction": "info",
        "unit": "kcal",
        "basis": "per 100g",
        "description": "Energy content — no threshold applied; informational display only.",
    },
    "Carbohydrates": {
        "direction": "info",
        "unit": "g",
        "basis": "per 100g",
        "description": "Total carbohydrates — informational display.",
    },
    "Sugar": {
        "direction": "max",
        "max_limit": 10.0,
        "unit": "g",
        "basis": "per 100g",
        "description": "Standard guideline: high sugar if > 10g per 100g.",
    },
    "Added Sugar": {
        "direction": "info",
        "unit": "g",
        "basis": "per 100g",
        "description": "Added sugar — informational display when present on label.",
    },
    "Total Fat": {
        "direction": "max",
        "max_limit": 17.5,
        "unit": "g",
        "basis": "per 100g",
        "description": "Standard guideline: high fat if > 17.5g per 100g.",
    },
    "Saturated Fat": {
        "direction": "max",
        "max_limit": 5.0,
        "unit": "g",
        "basis": "per 100g",
        "description": "Standard guideline: high saturated fat if > 5g per 100g.",
    },
    "Trans Fat": {
        "direction": "max",
        "max_limit": 0.2,
        "unit": "g",
        "basis": "per 100g",
        "description": "FSSAI guideline: trans fat should be < 0.2g per 100g.",
    },
    "Protein": {
        "direction": "min",
        "min_limit": 5.0,
        "unit": "g",
        "basis": "per 100g",
        "description": "Indicative: protein < 5g per 100g is considered low.",
    },
    "Dietary Fibre": {
        "direction": "min",
        "min_limit": 3.0,
        "unit": "g",
        "basis": "per 100g",
        "description": "Indicative: fibre < 3g per 100g is considered low.",
    },
    "Sodium": {
        "direction": "max",
        "max_limit": 600.0,    # mg per 100g
        "unit": "mg",
        "basis": "per 100g",
        "description": "Standard guideline: high sodium if > 600mg per 100g.",
    },
    "Salt": {
        "direction": "max",
        "max_limit": 1.5,
        "unit": "g",
        "basis": "per 100g",
        "description": "Standard guideline: high salt if > 1.5g per 100g.",
    },
}

# Ordered list for consistent display in the results table
DISPLAY_ORDER: List[str] = [
    "Energy",
    "Carbohydrates",
    "Sugar",
    "Added Sugar",
    "Total Fat",
    "Saturated Fat",
    "Trans Fat",
    "Protein",
    "Dietary Fibre",
    "Sodium",
    "Salt",
]


# ---------------------------------------------------------------------------
# Single-nutrient evaluation
# ---------------------------------------------------------------------------

def evaluate_nutrient(
    nutrient_name: str,
    extracted_value: Optional[float],
    unit: Optional[str],
    serving_basis: Optional[str],
) -> Dict[str, Any]:
    """
    Evaluates one nutrient value against its configured threshold.

    Status codes:
      "Not detected"             — field not found in OCR text
      "Informational"            — direction=info; displayed without pass/fail
      "Within configured limit"  — value satisfies the threshold
      "Above configured limit"   — value exceeds max threshold (alert)
      "Below guideline"          — value is under min threshold (warning)
      "Needs review"             — unit or basis is incompatible
      "No comparison configured" — nutrient not in DEFAULT_THRESHOLDS
    """
    config = DEFAULT_THRESHOLDS.get(nutrient_name)

    # ── Not detected ─────────────────────────────────────────────────────────
    if extracted_value is None:
        threshold_str = "N/A"
        if config:
            direction = config.get("direction", "info")
            if direction == "max":
                threshold_str = f"≤ {config['max_limit']} {config['unit']}"
            elif direction == "min":
                threshold_str = f"≥ {config['min_limit']} {config['unit']}"
            else:
                threshold_str = "Informational"
        return {
            "nutrient": nutrient_name,
            "extracted_value": "Not detected",
            "unit": unit or "-",
            "serving_basis": serving_basis or "-",
            "threshold": threshold_str,
            "status": "Not detected",
            "status_type": "muted",
            "description": config.get("description", "") if config else "",
        }

    # ── No threshold configured ───────────────────────────────────────────────
    if not config:
        return {
            "nutrient": nutrient_name,
            "extracted_value": str(extracted_value),
            "unit": unit or "-",
            "serving_basis": serving_basis or "-",
            "threshold": "Not configured",
            "status": "No comparison configured",
            "status_type": "neutral",
            "description": "",
        }

    direction = config.get("direction", "info")
    threshold_unit = config["unit"].lower()
    threshold_basis = config["basis"].lower()
    clean_unit = (unit or "").strip().lower()
    clean_basis = (serving_basis or "").strip().lower()

    # ── Normalise common unit differences ────────────────────────────────────
    effective_value = extracted_value
    effective_unit = clean_unit

    # gm → g
    if effective_unit == "gm":
        effective_unit = "g"

    # Sodium: if label says mg but threshold is mg — fine.
    # If label says g but threshold is mg — convert g → mg.
    if nutrient_name == "Sodium":
        if effective_unit == "g" and threshold_unit == "mg":
            effective_value = extracted_value * 1000.0
            effective_unit = "mg"
        elif effective_unit == "mg" and threshold_unit == "g":
            effective_value = extracted_value / 1000.0
            effective_unit = "g"

    # ── Unit compatibility check ─────────────────────────────────────────────
    if effective_unit and threshold_unit and effective_unit != threshold_unit:
        return {
            "nutrient": nutrient_name,
            "extracted_value": str(extracted_value),
            "unit": unit or "-",
            "serving_basis": serving_basis or "-",
            "threshold": _threshold_display(config),
            "status": "Needs review (unit mismatch)",
            "status_type": "warning",
            "description": config.get("description", ""),
        }

    # ── Serving basis check ───────────────────────────────────────────────────
    # Accept "per 100g", "per 100ml", or basis that contains the threshold basis
    compatible_basis = (
        "per 100" in clean_basis
        or threshold_basis in clean_basis
        or clean_basis in threshold_basis
    )
    if not compatible_basis:
        return {
            "nutrient": nutrient_name,
            "extracted_value": str(extracted_value),
            "unit": unit or "-",
            "serving_basis": serving_basis or "-",
            "threshold": _threshold_display(config),
            "status": "Needs review (serving basis differs)",
            "status_type": "warning",
            "description": config.get("description", ""),
        }

    # ── Informational (no pass/fail) ─────────────────────────────────────────
    if direction == "info":
        return {
            "nutrient": nutrient_name,
            "extracted_value": str(extracted_value),
            "unit": unit or threshold_unit,
            "serving_basis": serving_basis or threshold_basis,
            "threshold": "Informational",
            "status": "Informational",
            "status_type": "neutral",
            "description": config.get("description", ""),
        }

    # ── Max threshold evaluation ──────────────────────────────────────────────
    if direction == "max":
        limit = config["max_limit"]
        if effective_value > limit:
            status_text = "Above configured limit"
            status_type = "alert"
        else:
            status_text = "Within configured limit"
            status_type = "success"

    # ── Min threshold evaluation ──────────────────────────────────────────────
    elif direction == "min":
        limit = config["min_limit"]
        if effective_value < limit:
            status_text = "Below guideline"
            status_type = "warning"
        else:
            status_text = "Meets guideline"
            status_type = "success"

    else:
        status_text = "Informational"
        status_type = "neutral"

    return {
        "nutrient": nutrient_name,
        "extracted_value": str(extracted_value),
        "unit": unit or threshold_unit,
        "serving_basis": serving_basis or threshold_basis,
        "threshold": _threshold_display(config),
        "status": status_text,
        "status_type": status_type,
        "description": config.get("description", ""),
    }


def _threshold_display(config: Dict[str, Any]) -> str:
    """Format a threshold for display in the results table."""
    direction = config.get("direction", "info")
    if direction == "max":
        return f"≤ {config['max_limit']} {config['unit']} ({config['basis']})"
    elif direction == "min":
        return f"≥ {config['min_limit']} {config['unit']} ({config['basis']})"
    return "Informational"


# ---------------------------------------------------------------------------
# Batch evaluation
# ---------------------------------------------------------------------------

def compare_all_nutrients(extracted_nutrients: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Evaluates all nutrients in DISPLAY_ORDER.
    Accepts the dict produced by extractor.extract_nutrition_values().
    Returns a list of evaluation result dicts in display order.
    """
    results = []
    for nutrient in DISPLAY_ORDER:
        data = extracted_nutrients.get(nutrient, {})
        val = data.get("value")
        unit = data.get("unit")
        basis = data.get("serving_basis")
        results.append(evaluate_nutrient(nutrient, val, unit, basis))
    return results
