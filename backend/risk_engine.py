"""
Nutrition Risk Alert Engine — VEDANSHU Product Packet Analyser.

Produces two independent, clearly separated outputs:

A. QUANTITATIVE ALERTS
   Compare extracted nutrition values against documented reference thresholds.
   Status levels: HIGH · MODERATE · OK · UNKNOWN.
   Units and serving basis are checked before comparing; mismatched bases
   produce UNKNOWN rather than a wrong HIGH/OK result.

B. INGREDIENT FLAGS
   Scan the raw ingredients text for specific terms actually present in the OCR.
   Flags are educational notes, never diagnoses.
   Flags are only raised when the term is found in the text — never assumed.

Reference sources used for thresholds (documented inline per nutrient):
  - WHO / FAO 2003 (sugar, saturated fat, trans fat, sodium)
  - NHS UK traffic-light guidelines per 100g (sugar, fat, saturated fat, salt)
  - FSSAI Draft Regulations 2022 (trans fat ≤ 2g per 100g for Indian foods)
  - American Heart Association (added sugar daily limits used as population ref)

DISCLAIMER: All outputs are educational / informational.
This engine does not diagnose, prescribe, or make medical recommendations.
"""

from typing import Dict, Any, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# A. QUANTITATIVE THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────

# Each nutrient entry:
#   unit          : expected unit for comparison (g or mg)
#   basis         : expected serving basis substring ("per 100")
#   high          : value strictly above this → HIGH
#   moderate      : value above this (and ≤ high) → MODERATE   (None = no band)
#   low_high      : for min-type nutrients — value below this → HIGH concern
#   low_moderate  : for min-type nutrients — value below this (and ≥ low_high) → MODERATE
#   direction     : "max" (high is bad) | "min" (low is bad) | "info" (no level)
#   source        : reference citation string
#   why           : plain-English reason the value deserves attention
#   risk          : possible long-term risk phrased as possibility, not certainty
#   suggestion    : simple actionable suggestion
#   display_unit  : how to show the unit in the UI

QUANTITATIVE_RULES: Dict[str, Dict[str, Any]] = {

    "Sugar": {
        "direction": "max",
        "unit": "g",
        "basis": "per 100",
        # NHS traffic-light: HIGH > 22.5g per 100g, MEDIUM > 5g per 100g
        "high": 22.5,
        "moderate": 5.0,
        "source": "NHS UK traffic-light labelling (per 100g)",
        "why": (
            "Added and total sugars are compared against the NHS per-100g "
            "traffic-light threshold. Values above 22.5g per 100g are "
            "classified as high sugar by this guideline."
        ),
        "risk": (
            "Excessive sugar intake may contribute to weight gain, increased "
            "risk of type 2 diabetes, and tooth decay over time. "
            "These are possible risks associated with consistently high intake, "
            "not guaranteed outcomes from a single serving."
        ),
        "suggestion": (
            "Look for products with less than 5g sugar per 100g. "
            "Check for added sugars, syrups, or concentrated fruit juice in "
            "the ingredients list."
        ),
        "display_unit": "g per 100g",
    },

    "Saturated Fat": {
        "direction": "max",
        "unit": "g",
        "basis": "per 100",
        # NHS traffic-light: HIGH > 5g per 100g, MEDIUM > 1.5g per 100g
        "high": 5.0,
        "moderate": 1.5,
        "source": "NHS UK traffic-light labelling (per 100g)",
        "why": (
            "Saturated fat is compared against the NHS per-100g traffic-light "
            "threshold. Values above 5g per 100g are considered high."
        ),
        "risk": (
            "Consistently high saturated fat intake may raise LDL ('bad') "
            "cholesterol, which is associated with increased cardiovascular "
            "risk. This is a possible long-term risk for consistently high "
            "dietary intake, not a guaranteed outcome."
        ),
        "suggestion": (
            "Choose products with less than 1.5g saturated fat per 100g where "
            "possible. Prefer unsaturated fats (olive oil, nuts, seeds) as "
            "everyday alternatives."
        ),
        "display_unit": "g per 100g",
    },

    "Trans Fat": {
        "direction": "max",
        "unit": "g",
        "basis": "per 100",
        # WHO: <1% of energy. FSSAI: ≤2g per 100g total fat. Practical label limit:
        # > 0.2g per 100g of product raises concern; > 2g is high.
        "high": 2.0,
        "moderate": 0.2,
        "source": (
            "FSSAI Draft Regulations 2022 (≤2g per 100g of total fat); "
            "WHO recommends <1% of total energy from trans fat"
        ),
        "why": (
            "Industrial trans fats (partially hydrogenated oils) raise LDL "
            "and lower HDL cholesterol simultaneously. Even small amounts "
            "above 0.2g per 100g on the product label may indicate the "
            "presence of partially hydrogenated oil."
        ),
        "risk": (
            "Regular intake of industrial trans fats is consistently linked "
            "to increased LDL cholesterol and reduced HDL cholesterol, raising "
            "cardiovascular risk. WHO recommends eliminating industrial trans "
            "fats from the food supply."
        ),
        "suggestion": (
            "Avoid products containing 'partially hydrogenated' oils. "
            "Choose products labelled 0g trans fat per serving; confirm by "
            "checking the ingredients for 'partially hydrogenated'."
        ),
        "display_unit": "g per 100g",
    },

    "Sodium": {
        "direction": "max",
        "unit": "mg",
        "basis": "per 100",
        # NHS traffic-light: HIGH > 600mg per 100g, MEDIUM > 300mg per 100g
        # (Note: sodium, not salt)
        "high": 600.0,
        "moderate": 300.0,
        "source": "NHS UK traffic-light labelling for sodium (per 100g)",
        "why": (
            "Sodium is compared against the NHS per-100g traffic-light "
            "threshold. Values above 600mg per 100g are considered high. "
            "Sodium is the component of salt that raises blood pressure."
        ),
        "risk": (
            "Consistently high sodium intake may raise blood pressure, "
            "increasing the risk of heart disease and stroke over time. "
            "These are possible long-term risks from a habitually high-sodium "
            "diet, not guaranteed outcomes from a single food."
        ),
        "suggestion": (
            "Adults should aim for less than 2000mg sodium per day (WHO). "
            "Check portion sizes carefully — high-sodium foods consumed in "
            "large amounts add up quickly."
        ),
        "display_unit": "mg per 100g",
    },

    "Salt": {
        "direction": "max",
        "unit": "g",
        "basis": "per 100",
        # NHS traffic-light: HIGH > 1.5g salt per 100g, MEDIUM > 0.3g per 100g
        "high": 1.5,
        "moderate": 0.3,
        "source": "NHS UK traffic-light labelling for salt (per 100g)",
        "why": (
            "Salt content is compared against the NHS per-100g traffic-light "
            "threshold. Values above 1.5g per 100g are considered high. "
            "Salt = sodium × 2.5."
        ),
        "risk": (
            "Regularly eating high-salt foods may contribute to elevated blood "
            "pressure over time. This is a possible risk associated with a "
            "consistently high-salt diet, not a guaranteed outcome."
        ),
        "suggestion": (
            "Adults should consume no more than 5g salt per day (WHO). "
            "Look for products with less than 0.3g salt per 100g."
        ),
        "display_unit": "g per 100g",
    },

    "Total Fat": {
        "direction": "max",
        "unit": "g",
        "basis": "per 100",
        # NHS traffic-light: HIGH > 17.5g per 100g, MEDIUM > 3g per 100g
        "high": 17.5,
        "moderate": 3.0,
        "source": "NHS UK traffic-light labelling for fat (per 100g)",
        "why": (
            "Total fat is compared against the NHS per-100g traffic-light "
            "threshold. Values above 17.5g per 100g are considered high. "
            "Note that fat type matters — check saturated and trans fat separately."
        ),
        "risk": (
            "Very high total fat intake combined with physical inactivity may "
            "contribute to weight gain over time. The risk is more specifically "
            "associated with saturated and trans fat fractions."
        ),
        "suggestion": (
            "Prioritise checking saturated fat and trans fat rather than "
            "total fat alone. Unsaturated fats from nuts, seeds, and oily "
            "fish are generally considered beneficial in moderate amounts."
        ),
        "display_unit": "g per 100g",
    },
}

# Status level display colours (used to build CSS badge class names in the UI)
STATUS_CONFIG = {
    "HIGH":     {"badge": "risk-high",     "emoji": "🔴", "label": "HIGH"},
    "MODERATE": {"badge": "risk-moderate", "emoji": "🟡", "label": "MODERATE"},
    "OK":       {"badge": "risk-ok",       "emoji": "🟢", "label": "OK"},
    "UNKNOWN":  {"badge": "risk-unknown",  "emoji": "⬜", "label": "UNKNOWN"},
}


# ─────────────────────────────────────────────────────────────────────────────
# B. INGREDIENT FLAGS
# ─────────────────────────────────────────────────────────────────────────────

# Each flag is only raised when the search_terms are found in the OCR text.
# Flags are educational notes, never diagnoses or guaranteed risks.

INGREDIENT_FLAGS: List[Dict[str, Any]] = [
    {
        "name": "Palm Oil",
        "search_terms": ["palm oil", "palm olein", "palm stearin", "vegetable oil (palm)"],
        "category": "Fat Quality",
        "note": (
            "Palm oil is high in saturated fat (about 50% of its fatty acid "
            "content). Regularly consuming large amounts of saturated fat may "
            "raise LDL cholesterol. Palm oil production also has documented "
            "environmental concerns (deforestation)."
        ),
        "suggestion": "Prefer products using sunflower, rapeseed, or olive oil where alternatives are available.",
        "severity": "moderate",
    },
    {
        "name": "Partially Hydrogenated Oil (Trans Fat source)",
        "search_terms": ["partially hydrogenated", "hydrogenated vegetable fat",
                         "hydrogenated vegetable oil", "vanaspati"],
        "category": "Trans Fat",
        "note": (
            "Partially hydrogenated oils are the primary source of industrial "
            "trans fats. WHO recommends eliminating industrial trans fats from "
            "the food supply. Even if the nutrition label shows 0g trans fat, "
            "small amounts may be present below the rounding threshold."
        ),
        "suggestion": "Avoid products listing 'partially hydrogenated' oil in the ingredients.",
        "severity": "high",
    },
    {
        "name": "High-Fructose Corn Syrup / Corn Syrup",
        "search_terms": ["high fructose corn syrup", "hfcs", "corn syrup", "glucose-fructose syrup",
                         "isoglucose"],
        "category": "Added Sugar",
        "note": (
            "High-fructose corn syrup is a form of added sugar. Consistently "
            "high added-sugar intake may contribute to weight gain, insulin "
            "resistance, and dental decay. It is functionally similar to other "
            "added sugars but is often used in large quantities in processed foods."
        ),
        "suggestion": "Look for products where sugar or sweetener is not among the first three ingredients.",
        "severity": "moderate",
    },
    {
        "name": "Artificial Sweetener (Aspartame)",
        "search_terms": ["aspartame", "ins 951", "e951"],
        "category": "Additive",
        "note": (
            "Aspartame (INS 951) is an approved artificial sweetener used in "
            "low-calorie products. It is generally considered safe by regulatory "
            "bodies (FSSAI, EFSA, FDA) at normal dietary intakes. In 2023 IARC "
            "classified it as 'possibly carcinogenic to humans' (Group 2B) based "
            "on limited evidence; JECFA concluded it remains safe within the ADI "
            "of 40mg/kg body weight per day. People with phenylketonuria (PKU) "
            "must avoid it."
        ),
        "suggestion": "People with PKU must avoid aspartame. For general consumers, intake within normal dietary levels is considered safe by major regulators.",
        "severity": "info",
    },
    {
        "name": "Artificial Sweetener (Saccharin)",
        "search_terms": ["saccharin", "ins 954", "e954"],
        "category": "Additive",
        "note": (
            "Saccharin is an approved artificial sweetener. It is considered "
            "safe within approved daily intake levels (FSSAI, FDA, EFSA). "
            "Early animal studies suggested a cancer link that has not been "
            "confirmed in humans at normal dietary intakes."
        ),
        "suggestion": "Intake within approved daily limits is considered safe by major regulatory bodies.",
        "severity": "info",
    },
    {
        "name": "Monosodium Glutamate (MSG)",
        "search_terms": ["monosodium glutamate", "msg", "ins 621", "e621"],
        "category": "Flavour Enhancer",
        "note": (
            "MSG is a common flavour enhancer. It is approved and considered "
            "safe by FSSAI, FDA, and EFSA within normal dietary use. It "
            "contributes to sodium intake; relevant for people monitoring "
            "total sodium consumption."
        ),
        "suggestion": "MSG contributes to total sodium intake. People on sodium-restricted diets should account for it.",
        "severity": "info",
    },
    {
        "name": "Artificial Colour / Food Dye",
        "search_terms": [
            "tartrazine", "ins 102", "e102",
            "sunset yellow", "ins 110", "e110",
            "allura red", "ins 129", "e129",
            "brilliant blue", "ins 133", "e133",
            "carmoisine", "ins 122", "e122",
            "ponceau", "ins 124", "e124",
        ],
        "category": "Additive",
        "note": (
            "Some artificial food colours (tartrazine, sunset yellow, etc.) "
            "have been linked in some studies to increased hyperactivity in "
            "children with ADHD. The UK FSA recommends parents reduce "
            "consumption of these specific colours if they notice an effect. "
            "These colours are approved within set limits by FSSAI, EFSA, and FDA."
        ),
        "suggestion": "For children sensitive to food colours, reducing products containing these additives may be worth considering. Not all children are affected.",
        "severity": "moderate",
    },
    {
        "name": "Sodium Benzoate (Preservative)",
        "search_terms": ["sodium benzoate", "ins 211", "e211"],
        "category": "Preservative",
        "note": (
            "Sodium benzoate is a common preservative. When combined with "
            "ascorbic acid (Vitamin C) it can form benzene, a known carcinogen, "
            "though at very low levels typically found in food. It also "
            "contributes to sodium intake."
        ),
        "suggestion": "Considered safe at approved levels. Check if the same product also lists ascorbic acid/Vitamin C.",
        "severity": "info",
    },
    {
        "name": "Refined Wheat Flour / Maida",
        "search_terms": ["refined wheat flour", "maida", "refined flour",
                         "enriched flour", "bleached flour"],
        "category": "Refined Grain",
        "note": (
            "Refined wheat flour (maida) has most of its fibre, vitamins, and "
            "minerals removed during processing. Products made primarily from "
            "refined flour have a high glycaemic index, meaning they raise blood "
            "sugar more quickly than whole-grain alternatives."
        ),
        "suggestion": "Look for whole wheat or whole grain as the first ingredient for products with higher fibre content.",
        "severity": "info",
    },
    {
        "name": "Added Sugar (Brown Sugar / Invert Sugar / Dextrose)",
        "search_terms": [
            "brown sugar", "invert sugar", "invert syrup", "dextrose",
            "maltose", "corn syrup solids", "golden syrup", "treacle",
            "cane sugar", "beet sugar", "raw sugar", "demerara",
        ],
        "category": "Added Sugar",
        "note": (
            "These are forms of added sugar that contribute to total sugar "
            "intake. They are metabolically similar to regular sugar. "
            "Consistently high added-sugar intake is associated with weight "
            "gain, insulin resistance, and dental decay."
        ),
        "suggestion": "Check the total sugars value on the nutrition label. ICMR recommends limiting added sugars to less than 10% of total energy.",
        "severity": "moderate",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Engine functions
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_sodium(value: float, unit: str) -> tuple:
    """
    Ensure sodium is in mg for comparison against the 600mg threshold.
    Returns (normalised_value, normalised_unit).
    """
    u = (unit or "mg").lower().strip()
    if u in ("g", "gm"):
        return value * 1000.0, "mg"
    return value, "mg"


def _serving_basis_is_per_100(basis: Optional[str]) -> bool:
    """
    Returns True if the extracted serving basis is compatible with a
    per-100g/per-100ml reference threshold.
    Only per-100 comparisons are valid — we refuse to compare per-serving
    values against per-100g limits.
    """
    if not basis:
        return False
    b = basis.lower().strip()
    return "per 100" in b


def evaluate_quantitative_alerts(
    nutrients: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Compares extracted nutrition values against QUANTITATIVE_RULES.

    Returns a list of alert dicts, one per monitored nutrient:
      nutrient       : str
      value_display  : str   ("12.8 g per 100g" or "UNKNOWN")
      status         : "HIGH" | "MODERATE" | "OK" | "UNKNOWN"
      threshold_text : str
      source         : str
      why            : str
      risk           : str
      suggestion     : str
      basis_warning  : str or None   (set when basis is not per-100)
    """
    alerts = []

    for nutrient_name, rule in QUANTITATIVE_RULES.items():
        data = nutrients.get(nutrient_name, {})
        raw_value = data.get("value")
        raw_unit = (data.get("unit") or "").strip().lower()
        raw_basis = data.get("serving_basis") or ""

        # ── UNKNOWN: value not extracted ─────────────────────────────────────
        if raw_value is None:
            alerts.append({
                "nutrient": nutrient_name,
                "value_display": "Not detected",
                "status": "UNKNOWN",
                "threshold_text": _threshold_text(rule),
                "source": rule["source"],
                "why": rule["why"],
                "risk": rule["risk"],
                "suggestion": rule["suggestion"],
                "basis_warning": None,
            })
            continue

        # ── Normalise sodium if extracted in grams ───────────────────────────
        effective_value = raw_value
        effective_unit = raw_unit
        if nutrient_name == "Sodium":
            effective_value, effective_unit = _normalise_sodium(raw_value, raw_unit)

        # ── UNKNOWN: serving basis is not per-100 ────────────────────────────
        basis_ok = _serving_basis_is_per_100(raw_basis)
        if not basis_ok:
            alerts.append({
                "nutrient": nutrient_name,
                "value_display": f"{raw_value} {rule['display_unit'].split()[0]} ({raw_basis})",
                "status": "UNKNOWN",
                "threshold_text": _threshold_text(rule),
                "source": rule["source"],
                "why": rule["why"],
                "risk": rule["risk"],
                "suggestion": rule["suggestion"],
                "basis_warning": (
                    f"Value is given {raw_basis}, but the reference threshold is "
                    f"{rule['display_unit']}. Cannot compare reliably without "
                    f"knowing the portion weight."
                ),
            })
            continue

        # ── Determine status ─────────────────────────────────────────────────
        direction = rule.get("direction", "max")

        if direction == "max":
            high_limit = rule["high"]
            mod_limit = rule.get("moderate")

            if effective_value > high_limit:
                status = "HIGH"
            elif mod_limit is not None and effective_value > mod_limit:
                status = "MODERATE"
            else:
                status = "OK"

        elif direction == "min":
            # Not currently used in QUANTITATIVE_RULES but kept for completeness
            low_high = rule.get("low_high", 0)
            low_mod = rule.get("low_moderate")
            if effective_value < low_high:
                status = "HIGH"
            elif low_mod is not None and effective_value < low_mod:
                status = "MODERATE"
            else:
                status = "OK"
        else:
            status = "OK"

        # Format display value
        disp_unit = rule["display_unit"].split()[0]  # just "g" or "mg"
        value_display = f"{effective_value} {disp_unit} per 100g"

        alerts.append({
            "nutrient": nutrient_name,
            "value_display": value_display,
            "status": status,
            "threshold_text": _threshold_text(rule),
            "source": rule["source"],
            "why": rule["why"],
            "risk": rule["risk"],
            "suggestion": rule["suggestion"],
            "basis_warning": None,
        })

    return alerts


def _threshold_text(rule: Dict[str, Any]) -> str:
    """Format a human-readable threshold description."""
    direction = rule.get("direction", "max")
    unit = rule["display_unit"]
    if direction == "max":
        high = rule["high"]
        mod = rule.get("moderate")
        if mod is not None:
            return (
                f"OK ≤ {mod} {unit} · "
                f"MODERATE {mod}–{high} {unit} · "
                f"HIGH > {high} {unit}"
            )
        return f"HIGH > {high} {unit}"
    elif direction == "min":
        return f"LOW < {rule.get('low_high', '?')} {unit}"
    return "Informational"


def evaluate_ingredient_flags(raw_ingredients_text: str) -> List[Dict[str, Any]]:
    """
    Scans raw ingredients text for flagged terms.
    Returns only flags where at least one search term is found in the text.
    Does NOT raise flags for terms absent from the text.

    Returns a list of flag dicts:
      name         : str   (flag name)
      found_terms  : list  (actual matching terms found in text)
      category     : str
      severity     : "high" | "moderate" | "info"
      note         : str
      suggestion   : str
    """
    if not raw_ingredients_text or not raw_ingredients_text.strip():
        return []

    text_lower = raw_ingredients_text.lower()
    raised_flags = []

    for flag in INGREDIENT_FLAGS:
        found = [
            term for term in flag["search_terms"]
            if term.lower() in text_lower
        ]
        if found:
            raised_flags.append({
                "name": flag["name"],
                "found_terms": found,
                "category": flag["category"],
                "severity": flag["severity"],
                "note": flag["note"],
                "suggestion": flag["suggestion"],
            })

    return raised_flags


def run_full_risk_analysis(
    nutrients: Dict[str, Dict[str, Any]],
    raw_ingredients_text: Optional[str],
) -> Dict[str, Any]:
    """
    Top-level function called by app.py.
    Returns:
      {
        "quantitative_alerts": [...],
        "ingredient_flags":    [...],
        "has_high_alerts":     bool,
        "has_moderate_alerts": bool,
        "has_ingredient_flags": bool,
        "nutrition_available": bool,   True if at least one nutrient was extracted
        "ingredients_available": bool, True if ingredients text was provided
      }
    """
    quant_alerts = evaluate_quantitative_alerts(nutrients)
    ing_flags = evaluate_ingredient_flags(raw_ingredients_text or "")

    nutrition_available = any(
        nutrients.get(n, {}).get("value") is not None
        for n in QUANTITATIVE_RULES
    )
    ingredients_available = bool(
        raw_ingredients_text and raw_ingredients_text.strip()
    )

    high_count = sum(1 for a in quant_alerts if a["status"] == "HIGH")
    mod_count = sum(1 for a in quant_alerts if a["status"] == "MODERATE")

    return {
        "quantitative_alerts": quant_alerts,
        "ingredient_flags": ing_flags,
        "has_high_alerts": high_count > 0,
        "has_moderate_alerts": mod_count > 0,
        "has_ingredient_flags": len(ing_flags) > 0,
        "nutrition_available": nutrition_available,
        "ingredients_available": ingredients_available,
    }
