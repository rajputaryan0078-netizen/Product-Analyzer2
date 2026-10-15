"""
Entity and Nutrition Extractor for Product Packet Analyser.

Extracts all supported fields from raw OCR text using regular expressions.
Designed to tolerate common OCR errors including:
  - Fused number+unit ("28g" read as "289" — handled in ocr_utils cleanup
    AND in the regex by allowing a trailing unit-like digit)
  - Keyword misspellings (Mig→Mfg, Ingredbents→Ingredients handled in ocr_utils)
  - Inconsistent spacing and punctuation
  - Column-table layouts where value and unit appear on the same line

Rules:
  - Returns None when a field cannot be reliably found.
  - Never invents values.
  - Preserves units and serving basis as extracted.
"""

import re
from typing import Dict, Any, Optional, List


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_match(patterns: List[str], text: str, group: int = 1) -> Optional[str]:
    """Try each pattern; return first match group or None."""
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return m.group(group).strip()
            except IndexError:
                pass
    return None


def _clean_whitespace(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()


def _extract_numeric(pattern: str, text: str) -> Optional[tuple]:
    """
    Extracts (float_value, unit_str) using a pattern that captures
    (number_string, optional_unit_string).

    Handles:
    - Normal: "28g" → ("28", "g")
    - Space-separated: "28 g" → ("28", "g")
    - No unit: "28" → ("28", None)
    - Fused (already cleaned): "28g" in cleaned text → handled

    Returns (float, unit_str) or None.
    """
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    try:
        val = float(m.group(1).replace(',', '.'))
        unit = m.group(2).strip().lower() if (m.lastindex >= 2 and m.group(2)) else None
        if unit == "gm":
            unit = "g"
        return (val, unit)
    except (ValueError, TypeError, IndexError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Product field extraction
# ---------------------------------------------------------------------------

def extract_product_fields(raw_text: str) -> Dict[str, Any]:
    """
    Extracts key product information from raw OCR text.
    Returns dict with keys: product_name, brand_name, mrp,
    mfg_date, pack_date, expiry_date, best_before, ingredients, serving_size.
    Missing fields are None.
    """
    if not raw_text or not raw_text.strip():
        return {
            "product_name": None, "brand_name": None, "mrp": None,
            "mfg_date": None, "pack_date": None, "expiry_date": None,
            "best_before": None, "ingredients": None, "serving_size": None,
        }

    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

    # ── 1. Product name ──────────────────────────────────────────────────────
    product_name = None
    for line in lines[:8]:
        m = re.search(r'(?:product|item|name)\s*[:\-]\s*(.+)', line, re.IGNORECASE)
        if m:
            product_name = m.group(1).strip()
            break
    if not product_name and lines:
        for candidate in lines[:5]:
            if (
                len(candidate) > 4
                and not re.match(r'^[\d\W]+$', candidate)
                and not re.search(r'\d{4,}', candidate)
                and not re.search(
                    r'(?:mfg|mfd|exp|mrp|batch|lot|rs\.|inr|net\s*wt|serving|ingredient)',
                    candidate, re.IGNORECASE
                )
            ):
                product_name = candidate
                break

    # ── 2. Brand name ────────────────────────────────────────────────────────
    brand_name = _first_match([
        r'(?:brand|manufactured\s+by|marketed\s+by|distributed\s+by|mfr\.?\s*by)\s*[:\-]\s*(.+?)(?:\n|$|,|\|)',
        r'(?:brand\s*name)\s*[:\-]\s*(.+?)(?:\n|$)',
    ], raw_text)

    # ── 3. MRP ───────────────────────────────────────────────────────────────
    mrp = None
    mrp_patterns = [
        # Standard MRP with label
        r'(?:m\.?r\.?p\.?|maximum\s+retail\s+price|mrp)\s*[:\-\.]?\s*'
        r'(?:rs\.?|inr|₹)?\s*([0-9]+(?:\.[0-9]{1,2})?)',
        # Currency symbol first
        r'(?:rs\.?|inr|₹)\s*\.?\s*([0-9]+(?:\.[0-9]{1,2})?)',
        # Price keyword
        r'price\s*[:\-]?\s*(?:rs\.?|inr|₹)?\s*([0-9]+(?:\.[0-9]{1,2})?)',
    ]
    raw_mrp = _first_match(mrp_patterns, raw_text)
    if raw_mrp:
        mrp = f"₹ {raw_mrp}"

    # ── 4. Date patterns ─────────────────────────────────────────────────────
    _DATE_BODY = (
        r'(?:'
        r'[0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{2,4}'    # DD/MM/YYYY
        r'|[0-9]{1,2}\s+[a-zA-Z]{3,9}\.?\s+[0-9]{2,4}'       # 12 May 2025
        r'|[a-zA-Z]{3,9}\.?\s*[0-9]{4}'                       # May 2025
        r'|[0-9]{4}[\/\.\-][0-9]{1,2}(?:[\/\.\-][0-9]{1,2})?' # 2025/05
        r'|[0-9]{1,2}[\/\.\-][0-9]{4}'                        # 05/2026
        r')'
    )
    _D = r'(?:\s*(?:date|dt)?\s*)?[:\-\.]?\s*'

    mfg_date = _first_match([
        rf'(?:mfd|mfg|manufactur(?:ed|ing))(?:\s*(?:date|dt)?){_D}({_DATE_BODY})',
        rf'(?:mfd|mfg)\s*[:\-\.]\s*({_DATE_BODY})',
        # OCR sometimes merges "Mfg" and "Date"
        rf'(?:mfg\s*date|mfd\s*date|manufactured\s*date)\s*[:\-\.]?\s*({_DATE_BODY})',
    ], raw_text)

    pack_date = _first_match([
        rf'(?:pack(?:ed|ing|aged|aging)?)(?:\s*date)?{_D}({_DATE_BODY})',
    ], raw_text)
    if pack_date and pack_date == mfg_date:
        pack_date = None

    expiry_date = _first_match([
        rf'(?:exp(?:iry)?(?:\s*date)?|use\s*by(?:\s*date)?){_D}({_DATE_BODY})',
        rf'(?:expires?|expiry)\s*[:\-\.]?\s*({_DATE_BODY})',
    ], raw_text)

    best_before = _first_match([
        rf'(?:best\s*(?:before|by)(?:\s*date)?)(?:\s*[:\-\.]?\s*)'
        rf'({_DATE_BODY}|[0-9]+\s*(?:months?|days?|weeks?|years?)[^,\n]*)',
        rf'(?:best\s*(?:before|by)(?:\s*date)?){_D}'
        rf'({_DATE_BODY}|[0-9]+\s*(?:months?|days?|weeks?|years?)[^,\n]*)',
    ], raw_text)

    # ── 5. Ingredients ───────────────────────────────────────────────────────
    ingredients = None
    # Support common OCR-mangled headings too
    ing_match = re.search(
        r'(?:ingredients?|ingredien[ct]s?|ingredbents?|contains?)\s*[:\-]?\s*'
        r'(.+?)'
        r'(?:\n\s*\n|nutritional|nutrition\s+info|mrp|mfd|mfg|batch|net\s*wt|$)',
        raw_text,
        re.IGNORECASE | re.DOTALL
    )
    if ing_match:
        raw_ing = ing_match.group(1).replace("\n", " ")
        ingredients = _clean_whitespace(raw_ing)
        if len(ingredients) > 900:
            ingredients = ingredients[:900].rsplit(',', 1)[0].strip() + " ..."
        # Remove trailing fragments that are clearly not ingredients
        ingredients = re.sub(
            r'\s*(?:nutritional|nutrition|approx|per\s*100|serving\s*size).*$',
            '', ingredients, flags=re.IGNORECASE
        ).strip()
        if not ingredients:
            ingredients = None

    # ── 6. Serving size ──────────────────────────────────────────────────────
    serving_size = _first_match([
        r'serving\s*size\s*[:\-\.]?\s*([0-9]+(?:\.[0-9]+)?\s*(?:g|ml|oz|cup|tbsp|tsp|piece|biscuit)[^,\n]*)',
        r'(?:per\s*serving|serve\s*size|portion\s*size)\s*[:\-\.]?\s*([0-9]+(?:\.[0-9]+)?\s*(?:g|ml|oz)[^,\n]*)',
        # OCR may omit label: just a number followed by g at start of line
        r'^([0-9]+\s*g)\s*per\s*serving',
    ], raw_text)

    return {
        "product_name": product_name,
        "brand_name": brand_name,
        "mrp": mrp,
        "mfg_date": mfg_date,
        "pack_date": pack_date,
        "expiry_date": expiry_date,
        "best_before": best_before,
        "ingredients": ingredients,
        "serving_size": serving_size,
    }


# ---------------------------------------------------------------------------
# Nutrition value extraction
# ---------------------------------------------------------------------------

# Regex component that matches a numeric value followed by an optional unit.
# Handles:
#   "28g", "28 g", "28gm", "28.5g", "28 mg", "320mg", "0g"
# Does NOT match if the number is followed immediately by more digits
# (which would mean OCR fused the unit into a longer number — those
# cases are pre-cleaned by ocr_utils._clean_ocr_text).
_NUM = r'([0-9]+(?:[.,][0-9]+)?)\s*(g|gm|mg|kcal|kj|cal)?'

# Keyword-to-field patterns. Each entry is a list of regex patterns
# that capture (number, optional_unit).
_NUTRITION_PATTERNS: Dict[str, List[str]] = {
    "Energy": [
        rf'energy\s*[:\-\.]?\s*{_NUM}(?:\s*(?:kcal|kj|cal))?',
        rf'calories?\s*[:\-\.]?\s*{_NUM}(?:\s*(?:kcal|kj|cal))?',
        rf'energy\s+value\s*[:\-\.]?\s*{_NUM}',
    ],
    "Carbohydrates": [
        rf'(?:total\s+)?carbohydrates?\s*[:\-\.]?\s*{_NUM}',
        rf'carbs?\s*[:\-\.]?\s*{_NUM}',
        rf'total\s+carbs?\s*[:\-\.]?\s*{_NUM}',
    ],
    "Sugar": [
        # "of which sugars" must come before plain "sugars" to avoid
        # matching "Total Carbohydrates" subfield incorrectly
        rf'(?:of\s+which\s+)?(?:total\s+)?sugars?\s*[:\-\.]?\s*{_NUM}',
    ],
    "Added Sugar": [
        rf'added\s+sugars?\s*[:\-\.]?\s*{_NUM}',
        rf'(?:of\s+which\s+)?added\s+sugars?\s*[:\-\.]?\s*{_NUM}',
    ],
    "Total Fat": [
        rf'total\s+fat\s*[:\-\.]?\s*{_NUM}',
        # Plain "fat" only when NOT preceded by saturated/trans/mono/poly
        rf'(?<!saturated\s)(?<!trans\s)(?<!mono\s)(?<!poly\s)fat\s*[:\-\.]?\s*{_NUM}',
    ],
    "Saturated Fat": [
        rf'saturated\s+(?:fat|fatty\s*acids?)\s*[:\-\.]?\s*{_NUM}',
        rf'(?:of\s+which\s+)?saturates?\s*[:\-\.]?\s*{_NUM}',
        rf'sat\.?\s*fat\s*[:\-\.]?\s*{_NUM}',
    ],
    "Trans Fat": [
        rf'trans\s+(?:fat|fatty\s*acids?)\s*[:\-\.]?\s*{_NUM}',
        rf'trans\s*fats?\s*[:\-\.]?\s*{_NUM}',
    ],
    "Protein": [
        rf'proteins?\s*[:\-\.]?\s*{_NUM}',
    ],
    "Dietary Fibre": [
        rf'dietary\s+(?:fibre|fiber)\s*[:\-\.]?\s*{_NUM}',
        rf'(?:total\s+)?(?:fibre|fiber)\s*[:\-\.]?\s*{_NUM}',
    ],
    "Sodium": [
        rf'sodium\s*[:\-\.]?\s*{_NUM}',
    ],
    "Salt": [
        # "salt" must not match "iodized salt" in ingredients — only
        # match when it's a standalone nutrient row (preceded by newline
        # or label, followed by value)
        rf'(?:^|\n)\s*salt\s*[:\-\.]?\s*{_NUM}',
        rf'salt\s+content\s*[:\-\.]?\s*{_NUM}',
    ],
}

# Default units when the regex captures no unit
_DEFAULT_UNIT: Dict[str, str] = {
    "Energy": "kcal",
    "Carbohydrates": "g",
    "Sugar": "g",
    "Added Sugar": "g",
    "Total Fat": "g",
    "Saturated Fat": "g",
    "Trans Fat": "g",
    "Protein": "g",
    "Dietary Fibre": "g",
    "Sodium": "mg",
    "Salt": "g",
}


def _detect_serving_basis(text: str) -> str:
    """
    Detect the serving basis declared in the text.
    Returns a string like "per 100g" or "per 30g".
    Defaults to "per 100g" if nothing is found.
    """
    # Explicit "per 100g" or "per 100ml"
    m = re.search(
        r'(?:per|approx\.?(?:\s+values)?|(?:nutritional\s+)?values?\s*per)\s*'
        r'(100\s*(?:g|ml|gm|gram))',
        text, re.IGNORECASE
    )
    if m:
        return f"per {m.group(1).strip().lower()}"

    # Other serving sizes: "per 30g", "per serving (25g)", etc.
    m = re.search(
        r'(?:per|approx\.?(?:\s+values)?|(?:nutritional\s+)?values?\s*per)\s*'
        r'([0-9]+\s*(?:g|ml|gm|gram|serving|pack))',
        text, re.IGNORECASE
    )
    if m:
        return f"per {m.group(1).strip().lower()}"

    # "Approx. values per 100g" — catch it even without "values"
    m = re.search(r'per\s+100\s*(?:g|ml)', text, re.IGNORECASE)
    if m:
        return "per 100g"

    return "per 100g"


def extract_nutrition_values(raw_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Extracts 11 nutrition components from raw OCR text.
    Returns a dict where each key maps to:
      { "value": float or None, "unit": str, "serving_basis": str }
    value=None means the field was not found — never assume zero.
    """
    nutrients: Dict[str, Dict[str, Any]] = {
        k: {"value": None, "unit": _DEFAULT_UNIT[k], "serving_basis": "per 100g"}
        for k in _NUTRITION_PATTERNS
    }

    if not raw_text or not raw_text.strip():
        return nutrients

    detected_basis = _detect_serving_basis(raw_text)

    for nutrient_key, pattern_list in _NUTRITION_PATTERNS.items():
        for pattern in pattern_list:
            result = _extract_numeric(pattern, raw_text)
            if result is not None:
                val, unit = result
                # Resolve unit
                if unit is None:
                    unit = _DEFAULT_UNIT[nutrient_key]
                elif unit == "gm":
                    unit = "g"
                # Sanity guard: per-100g nutrient values can't exceed 100g
                # (except energy in kcal). If they do, the OCR likely fused
                # a 'g' into the number — skip this result.
                if unit in ("g",) and val > 100.0:
                    continue  # try next pattern
                # Additional sanity limits for specific nutrients
                # These prevent OCR-corrupted values being accepted
                _MAX_PLAUSIBLE = {
                    "Sugar": 100.0, "Added Sugar": 100.0,
                    "Total Fat": 100.0, "Saturated Fat": 60.0,
                    "Trans Fat": 30.0, "Protein": 50.0,
                    "Dietary Fibre": 15.0, "Salt": 15.0,
                    "Carbohydrates": 100.0,
                }
                if nutrient_key in _MAX_PLAUSIBLE and unit in ("g",):
                    if val > _MAX_PLAUSIBLE[nutrient_key]:
                        continue  # value is implausibly large — skip
                nutrients[nutrient_key] = {
                    "value": val,
                    "unit": unit,
                    "serving_basis": detected_basis
                }
                break  # stop trying patterns for this nutrient

    return nutrients


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

def get_demo_packet_data() -> Dict[str, Any]:
    """
    Returns sample data for demonstration mode.
    Explicitly flagged as demo so no real OCR claim is made.
    """
    demo_text = (
        "GOOD MORNING CRUNCHY WHOLE GRAIN CEREAL\n"
        "Brand: NutriHarvest Foods\n"
        "Net Weight: 350g\n"
        "M.R.P.: Rs. 145.00 (Incl. of all taxes)\n"
        "Mfg Date: 15/08/2026\n"
        "Best Before: 6 months from mfg date\n"
        "Serving Size: 40g (approx. 1 cup)\n"
        "Ingredients: Whole Wheat Flakes (62%), Rolled Oats (18%), Brown Sugar, "
        "Honey, Vegetable Oil, Iodized Salt, Natural Flavours.\n\n"
        "NUTRITIONAL INFORMATION\n"
        "Approx. Values Per 100g:\n"
        "Energy: 380 kcal\n"
        "Total Carbohydrates: 72g\n"
        "Sugars: 12.8g\n"
        "Total Fat: 4.5g\n"
        "Saturated Fat: 1.2g\n"
        "Trans Fat: 0g\n"
        "Protein: 8.5g\n"
        "Dietary Fibre: 6.4g\n"
        "Sodium: 420mg\n"
        "Salt: 1.1g"
    )

    return {
        "is_demo": True,
        "raw_text": demo_text,
        "fields": {
            "product_name": "GOOD MORNING CRUNCHY WHOLE GRAIN CEREAL",
            "brand_name": "NutriHarvest Foods",
            "mrp": "₹ 145.00",
            "mfg_date": "15/08/2026",
            "pack_date": None,
            "expiry_date": None,
            "best_before": "6 months from mfg date",
            "ingredients": (
                "Whole Wheat Flakes (62%), Rolled Oats (18%), Brown Sugar, "
                "Honey, Vegetable Oil, Iodized Salt, Natural Flavours."
            ),
            "serving_size": "40g (approx. 1 cup)",
        },
        "nutrients": {
            "Energy":        {"value": 380.0,  "unit": "kcal", "serving_basis": "per 100g"},
            "Carbohydrates": {"value": 72.0,   "unit": "g",    "serving_basis": "per 100g"},
            "Sugar":         {"value": 12.8,   "unit": "g",    "serving_basis": "per 100g"},
            "Added Sugar":   {"value": None,   "unit": "g",    "serving_basis": "per 100g"},
            "Total Fat":     {"value": 4.5,    "unit": "g",    "serving_basis": "per 100g"},
            "Saturated Fat": {"value": 1.2,    "unit": "g",    "serving_basis": "per 100g"},
            "Trans Fat":     {"value": 0.0,    "unit": "g",    "serving_basis": "per 100g"},
            "Protein":       {"value": 8.5,    "unit": "g",    "serving_basis": "per 100g"},
            "Dietary Fibre": {"value": 6.4,    "unit": "g",    "serving_basis": "per 100g"},
            "Sodium":        {"value": 420.0,  "unit": "mg",   "serving_basis": "per 100g"},
            "Salt":          {"value": 1.1,    "unit": "g",    "serving_basis": "per 100g"},
        }
    }
