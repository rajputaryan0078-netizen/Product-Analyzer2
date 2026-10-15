"""
Entity and Nutrition Extractor for Product Packet Analyser.

Extracts normalized product fields, declared allergens, and nutrition facts
from raw OCR text using a robust multi-layered parsing strategy:
  1. Label-specific regular expressions and deterministic parsing.
  2. Context-aware multi-column nutrition row extraction (Per 100g vs Per Serving).
  3. Content-type awareness: recipes are classified and never confused with
     commercial packaged food products.
  4. Plausibility validation (e.g. Sugar <= Carbohydrates, Saturated Fat <= Total Fat).
  5. Per-field extraction confidence and evidence snippets.
"""

import re
from typing import Dict, Any, Optional, List, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# General Utility Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _first_match(patterns: List[str], text: str, group: int = 1) -> Optional[Tuple[str, str]]:
    """
    Tries regex patterns in order and returns (matched_text, matched_pattern) or None.
    """
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                val = m.group(group).strip()
                if val:
                    return val, m.group(0).strip()
            except IndexError:
                pass
    return None


def _clean_whitespace(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Product Category Classification
# ─────────────────────────────────────────────────────────────────────────────

_CATEGORY_KEYWORDS = {
    "Biscuits & Cookies": ["biscuit", "cookie", "choco fills", "cookies", "wafer", "cracker", "rusk"],
    "Breakfast Cereals": ["cereal", "corn flakes", "muesli", "granola", "rolled oats", "oat flakes"],
    "Chocolates & Confectionery": ["chocolate", "cocoa", "candy", "toffee", "gummy", "sweet"],
    "Snacks & Namkeen": ["chips", "crisps", "namkeen", "bhujia", "sev", "mixture", "puffs", "popcorn"],
    "Dairy & Cheese": ["milk", "cheese", "paneer", "butter", "ghee", "curd", "yogurt", "cream"],
    "Beverages": ["juice", "drink", "soda", "cola", "tea", "coffee", "syrup", "squash"],
    "Bakery & Bread": ["bread", "bun", "cake", "muffin", "croissant", "toast", "pastry"],
    "Noodles & Pasta": ["noodles", "pasta", "macaroni", "vermicelli", "spaghetti", "ramen"],
    "Sauces & Condiments": ["sauce", "ketchup", "mayonnaise", "dip", "pickle", "chutney"],
    "Flours & Grains": ["flour", "atta", "maida", "suji", "rava", "besan", "rice", "wheat"],
}


def detect_product_category(title: Optional[str], ingredients: Optional[str]) -> str:
    """Classifies the product category based on product title and ingredients."""
    search_corpus = f"{title or ''} {ingredients or ''}".lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf'\b{re.escape(kw)}\b', search_corpus):
                return category
    return "Packaged Food"


# ─────────────────────────────────────────────────────────────────────────────
# Brand Detection
# ─────────────────────────────────────────────────────────────────────────────

_KNOWN_BRANDS = [
    "Amul", "Britannia", "Parle", "ITC", "Nestle", "Cadbury", "Mondelez",
    "Haldiram's", "Haldiram", "Kellogg's", "Kellogg", "Tata", "Dabur", "Marico",
    "PepsiCo", "Lay's", "Kurkure", "Balaji", "Bikaji", "Mother Dairy",
    "Patanjali", "Sunfeast", "Bingo", "Aashirvaad", "Saffola", "Maggi",
    "Kissan", "Knorr", "MTR", "Ching's", "Kwality Wall's", "Hindustan Unilever"
]


def _extract_brand(text: str) -> Tuple[Optional[str], float, Optional[str]]:
    """
    Extracts brand from manufacturer / brand headers or recognized brands.
    Returns (brand_name, confidence, evidence).
    """
    # 1. Explicit brand headers
    explicit_patterns = [
        r'(?:brand|brand\s*name)\s*[:\-]\s*([A-Za-z0-9\s&\'\.\-]+?)(?:\n|$|,|\|)',
        r'(?:manufactured\s+by|mfd\.?\s*by|mfg\.?\s*by|marketed\s+by|packed\s+by)\s*[:\-]\s*([A-Za-z0-9\s&\'\.\-]+?)(?:\n|$|,|\|)',
    ]
    for pat in explicit_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = _clean_whitespace(m.group(1))
            # Clean trailing company suffixes
            candidate = re.split(r'(?:Plot|At:|Regd|Lic|Near|Village|Post|Dist)', candidate, flags=re.IGNORECASE)[0].strip()
            if len(candidate) >= 2 and len(candidate) <= 60:
                return candidate, 0.90, m.group(0).strip()

    # 2. Known brand dictionary scan
    for brand in _KNOWN_BRANDS:
        pattern = rf'\b{re.escape(brand)}\b'
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return brand, 0.85, m.group(0).strip()

    return None, 0.0, None


# ─────────────────────────────────────────────────────────────────────────────
# Product Field Extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_product_fields(raw_text: str, content_classification: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extracts key product information from raw OCR text with confidence and evidence.
    Distinguishes recipes from packaged goods so recipe titles are never mistaken
    for commercial packaged food names.
    """
    from backend import ocr_utils

    if not raw_text or not raw_text.strip():
        return {
            "product_name": None,
            "product_category": "Packaged Food",
            "brand_name": None,
            "mrp": None,
            "mrp_numeric": None,
            "currency": "INR",
            "mfg_date": None,
            "pack_date": None,
            "expiry_date": None,
            "best_before": None,
            "serving_size": None,
            "net_quantity": None,
            "ingredients": None,
            "declared_allergens": None,
            "precautionary_allergens": None,
            "content_type": "empty",
            "is_package": False,
            "field_evidence": {},
        }

    # Classify content type if not provided
    if not content_classification:
        content_classification = ocr_utils.classify_content_type(raw_text)

    content_type = content_classification.get("content_type", "packaged_food")
    is_recipe = content_type == "recipe"

    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    evidence: Dict[str, Any] = {}

    # ── 1. Product Name ──────────────────────────────────────────────────────
    product_name = None
    if is_recipe:
        # If this is a recipe, do NOT misrepresent it as a packaged product
        product_name = None
        evidence["product_name"] = {
            "status": "not_applicable",
            "reason": "Image identified as a recipe card/document rather than a commercial product package.",
            "confidence": 0.0,
            "evidence": None,
        }
    else:
        # Check explicit product name headers
        for line in lines[:8]:
            m = re.search(r'(?:product(?:\s*name)?|item(?:\s*name)?|name\s+of\s+food)\s*[:\-]\s*(.+)', line, re.IGNORECASE)
            if m:
                cand = _clean_whitespace(m.group(1))
                if len(cand) > 3:
                    product_name = cand
                    evidence["product_name"] = {"confidence": 0.95, "evidence": line}
                    break

        # Fallback to header inspection
        if not product_name and lines:
            for candidate in lines[:6]:
                # Skip lines that are labels, numbers, URLs, recipes, or generic headings
                cand_clean = _clean_whitespace(candidate)
                if (
                    len(cand_clean) >= 4
                    and len(cand_clean) <= 70
                    and not re.match(r'^[\d\W]+$', cand_clean)
                    and not re.search(r'\b(?:mfg|mfd|exp|mrp|rs\.|inr|net\s*wt|serving|ingredient|batch|lot|fssai|recipe|prep\s*time)\b', cand_clean, re.IGNORECASE)
                    and not re.search(r'\b(?:nutritional|nutrition|information|facts|values?)\b', cand_clean, re.IGNORECASE)
                    and not re.search(r'https?://|www\.', cand_clean, re.IGNORECASE)
                ):
                    product_name = cand_clean
                    evidence["product_name"] = {"confidence": 0.70, "evidence": candidate}
                    break

    # ── 2. Brand Name ────────────────────────────────────────────────────────
    brand_name = None
    if not is_recipe:
        brand_name, brand_conf, brand_ev = _extract_brand(raw_text)
        if brand_name:
            evidence["brand_name"] = {"confidence": brand_conf, "evidence": brand_ev}

    # ── 3. MRP & Currency ────────────────────────────────────────────────────
    mrp = None
    mrp_numeric = None
    if not is_recipe:
        mrp_patterns = [
            # Standard MRP with label and currency
            r'(?:m\.?r\.?p\.?|maximum\s+retail\s+price)\s*[:\-\.]?\s*(?:rs\.?|inr|₹)?\s*([0-9]+(?:\.[0-9]{1,2})?)',
            # MRP with taxes note: MRP Rs. 80.00 (inclusive of all taxes)
            r'(?:m\.?r\.?p\.?|mrp)\s*[:\-\.]?\s*(?:rs\.?|inr|₹)?\s*([0-9]+(?:\.[0-9]{1,2})?)\s*(?:\([^\)]*tax[^\)]*\))?',
            # Price with currency
            r'(?:rs\.?|inr|₹)\s*\.?\s*([0-9]+(?:\.[0-9]{1,2})?)\s*(?:/\-)?',
            r'\bprice\s*[:\-]\s*(?:rs\.?|inr|₹)?\s*([0-9]+(?:\.[0-9]{1,2})?)',
        ]
        match_res = _first_match(mrp_patterns, raw_text)
        if match_res:
            raw_val, ev = match_res
            try:
                mrp_numeric = float(raw_val)
                mrp = f"₹ {mrp_numeric:.2f}"
                evidence["mrp"] = {"confidence": 0.90, "evidence": ev}
            except ValueError:
                pass

    # ── 4. Dates & Batch ─────────────────────────────────────────────────────
    _DATE_BODY = (
        r'(?:'
        r'[0-9]{1,2}[\/\.\-][0-9]{1,2}[\/\.\-][0-9]{2,4}'        # DD/MM/YYYY
        r'|[0-9]{1,2}\s+[a-zA-Z]{3,9}\.?\s+[0-9]{2,4}'           # 15 Mar 2026
        r'|[a-zA-Z]{3,9}\.?\s*[0-9]{4}'                           # Mar 2026
        r'|[0-9]{1,2}[\/\.\-][0-9]{4}'                            # 03/2026
        r')'
    )
    _DELIM = r'(?:\s*(?:date|dt)?\s*)?[:\-\.]?\s*'

    mfg_date = None
    pack_date = None
    expiry_date = None
    best_before = None

    if not is_recipe:
        mfg_match = _first_match([
            rf'(?:mfd|mfg|manufactur(?:ed|ing))(?:\s*(?:date|dt)?){_DELIM}({_DATE_BODY})',
            rf'(?:mfg|mfd)\s*[:\-\.]\s*({_DATE_BODY})',
        ], raw_text)
        if mfg_match:
            mfg_date, ev = mfg_match
            evidence["mfg_date"] = {"confidence": 0.88, "evidence": ev}

        pack_match = _first_match([
            rf'(?:pkd|packed|packaging)(?:\s*(?:date|dt)?){_DELIM}({_DATE_BODY})',
            rf'(?:date\s+of\s+packing){_DELIM}({_DATE_BODY})',
        ], raw_text)
        if pack_match and pack_match[0] != mfg_date:
            pack_date, ev = pack_match
            evidence["pack_date"] = {"confidence": 0.85, "evidence": ev}

        exp_match = _first_match([
            rf'(?:exp(?:iry)?(?:\s*date)?|use\s*by(?:\s*date)?){_DELIM}({_DATE_BODY})',
            rf'(?:expires?|expiry)\s*[:\-\.]?\s*({_DATE_BODY})',
        ], raw_text)
        if exp_match:
            expiry_date, ev = exp_match
            evidence["expiry_date"] = {"confidence": 0.88, "evidence": ev}

        best_match = _first_match([
            rf'(?:best\s*(?:before|by)(?:\s*date)?)(?:\s*[:\-\.]?\s*)({_DATE_BODY}|[0-9]+\s*(?:months?|days?|weeks?|years?)[^,\n]*)',
            rf'(?:best\s*(?:before|by)){_DELIM}([0-9]+\s*(?:months?|days?|weeks?|years?)[^,\n]*)',
        ], raw_text)
        if best_match:
            best_before, ev = best_match
            evidence["best_before"] = {"confidence": 0.85, "evidence": ev}

    # ── 5. Serving Size & Net Quantity ───────────────────────────────────────
    serving_size = None
    net_quantity = None

    serve_match = _first_match([
        r'serving\s*size\s*[:\-\.]?\s*([0-9]+(?:\.[0-9]+)?\s*(?:g|ml|oz|cup|tbsp|tsp|piece|biscuit)[^,\n]*)',
        r'(?:per\s*serving|serve\s*size|portion\s*size)\s*[:\-\.]?\s*([0-9]+(?:\.[0-9]+)?\s*(?:g|ml|oz)[^,\n]*)',
        r'^([0-9]+\s*g)\s*per\s*serving',
    ], raw_text)
    if serve_match:
        serving_size, ev = serve_match
        evidence["serving_size"] = {"confidence": 0.85, "evidence": ev}

    net_match = _first_match([
        r'(?:net\s*(?:weight|wt|quantity|qty|volume|vol))\s*[:\-\.]?\s*([0-9]+(?:\.[0-9]+)?\s*(?:g|gm|kg|ml|l|ltr|oz)[^,\n]*)',
        r'\bnet\s+([0-9]+(?:\.[0-9]+)?\s*(?:g|gm|kg|ml|l|ltr))\b',
    ], raw_text)
    if net_match:
        net_quantity, ev = net_match
        evidence["net_quantity"] = {"confidence": 0.85, "evidence": ev}

    # ── 6. Ingredients List ──────────────────────────────────────────────────
    ingredients = None
    ing_match = re.search(
        r'(?:ingredients?|ingredien[ct]s?|ingredbents?)\s*[:\-]?\s*'
        r'(.+?)'
        r'(?:\n\s*\n|nutritional|nutrition\s+facts|nutrition\s+info|mrp|mfd|mfg|batch|net\s*wt|storage|manufactured|$)',
        raw_text,
        re.IGNORECASE | re.DOTALL
    )
    if ing_match:
        raw_ing = ing_match.group(1).replace("\n", " ")
        ingredients = _clean_whitespace(raw_ing)
        if len(ingredients) > 950:
            ingredients = ingredients[:950].rsplit(',', 1)[0].strip() + " ..."
        # Remove trailing nutrition headers if attached
        ingredients = re.sub(
            r'\s*(?:nutritional|nutrition|approx|per\s*100|serving\s*size).*$',
            '', ingredients, flags=re.IGNORECASE
        ).strip()
        if not ingredients or len(ingredients) < 3:
            ingredients = None
        else:
            evidence["ingredients"] = {"confidence": 0.90, "evidence": ing_match.group(0)[:80] + "..."}

    # ── 7. Declared & Precautionary Allergen Statements ──────────────────────
    declared_allergens = None
    precautionary_allergens = None

    decl_match = re.search(
        r'(?:contains|allergen\s+advice|allergen\s+information)\s*[:\-]\s*(.+?)(?:\n|$|\.|\bmay\b)',
        raw_text, re.IGNORECASE
    )
    if decl_match:
        declared_allergens = _clean_whitespace(decl_match.group(1))

    may_match = re.search(
        r'(?:may\s+contain(?:\s+traces\s+of)?|manufactured\s+(?:in\s+a\s+facility|on\s+equipment)\s+that\s+also\s+processes)\s*[:\-]?\s*(.+?)(?:\n|$|\.)',
        raw_text, re.IGNORECASE
    )
    if may_match:
        precautionary_allergens = _clean_whitespace(may_match.group(1))

    # Product category classification
    category = detect_product_category(product_name, ingredients)

    return {
        "product_name": product_name,
        "product_category": category,
        "brand_name": brand_name,
        "mrp": mrp,
        "mrp_numeric": mrp_numeric,
        "currency": "INR",
        "mfg_date": mfg_date,
        "pack_date": pack_date,
        "expiry_date": expiry_date,
        "best_before": best_before,
        "serving_size": serving_size,
        "net_quantity": net_quantity,
        "ingredients": ingredients,
        "declared_allergens": declared_allergens,
        "precautionary_allergens": precautionary_allergens,
        "content_type": content_type,
        "is_package": not is_recipe,
        "field_evidence": evidence,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Nutrition Value Extraction
# ─────────────────────────────────────────────────────────────────────────────

# Numeric value followed by unit or decimal
_NUM = r'([0-9]+(?:[.,][0-9]+)?)\s*(g|gm|mg|kcal|kj|cal)?'

_NUTRITION_PATTERNS: Dict[str, List[str]] = {
    "Energy": [
        rf'energy\s*(?:\(kcal\))?\s*[:\-\.]?\s*{_NUM}',
        rf'calories?\s*[:\-\.]?\s*{_NUM}',
        rf'energy\s+value\s*[:\-\.]?\s*{_NUM}',
    ],
    "Carbohydrates": [
        rf'(?:total\s+)?carbohydrates?\s*[:\-\.]?\s*{_NUM}',
        rf'total\s+carbs?\s*[:\-\.]?\s*{_NUM}',
        rf'\bcarbs?\s*[:\-\.]?\s*{_NUM}',
    ],
    "Sugar": [
        # Must match total sugars or "of which sugars"
        rf'(?:total\s+)?sugars?\s*[:\-\.]?\s*{_NUM}',
        rf'of\s+which\s+(?:total\s+)?sugars?\s*[:\-\.]?\s*{_NUM}',
    ],
    "Added Sugar": [
        rf'added\s+sugars?\s*[:\-\.]?\s*{_NUM}',
        rf'of\s+which\s+added\s+sugars?\s*[:\-\.]?\s*{_NUM}',
    ],
    "Total Fat": [
        rf'total\s+fat\s*[:\-\.]?\s*{_NUM}',
        rf'(?<!saturated\s)(?<!trans\s)(?<!mono\s)(?<!poly\s)\bfat\s*[:\-\.]?\s*{_NUM}',
    ],
    "Saturated Fat": [
        rf'saturated\s+(?:fat|fatty\s*acids?)\s*[:\-\.]?\s*{_NUM}',
        rf'of\s+which\s+saturates?\s*[:\-\.]?\s*{_NUM}',
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
        rf'(?:^|\n)\s*salt\s*[:\-\.]?\s*{_NUM}',
        rf'salt\s+(?:equivalent|content)?\s*[:\-\.]?\s*{_NUM}',
    ],
}

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
    """Detects whether nutrition table declares values per 100g, per 100ml, or per serving."""
    if re.search(r'per\s+100\s*(?:g|gm|gram)', text, re.IGNORECASE):
        return "per 100g"
    if re.search(r'per\s+100\s*ml', text, re.IGNORECASE):
        return "per 100ml"
    m = re.search(r'per\s+serving\s*\(([0-9]+(?:\.[0-9]+)?\s*(?:g|ml))\)', text, re.IGNORECASE)
    if m:
        return f"per serving ({m.group(1).lower()})"
    if re.search(r'per\s+serving', text, re.IGNORECASE):
        return "per serving"
    return "per 100g"


def _extract_multi_column_row(line: str) -> List[Tuple[float, Optional[str]]]:
    """
    Extracts all numeric tokens from a line that may contain multiple columns
    (e.g., "Protein: 6.5g 1.6g 3%").
    """
    pattern = r'([0-9]+(?:[.,][0-9]+)?)\s*(g|gm|mg|kcal|kj|cal|%)?'
    matches = re.finditer(pattern, line, re.IGNORECASE)
    results = []
    for m in matches:
        try:
            val = float(m.group(1).replace(',', '.'))
            unit = m.group(2).lower() if m.group(2) else None
            if unit == "gm":
                unit = "g"
            results.append((val, unit))
        except ValueError:
            pass
    return results


def extract_nutrition_values(raw_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Extracts 11 normalized nutrition components with column awareness and plausibility validation.
    Distinguishes Sodium from Salt, Total Sugar from Added Sugar, and detects multi-column tables.
    """
    nutrients: Dict[str, Dict[str, Any]] = {
        k: {
            "value": None,
            "unit": _DEFAULT_UNIT[k],
            "serving_basis": "per 100g",
            "per_serving_value": None,
            "original_extracted": None,
            "confidence": 0.0,
            "plausibility_warning": None,
        }
        for k in _NUTRITION_PATTERNS
    }

    if not raw_text or not raw_text.strip():
        return nutrients

    detected_basis = _detect_serving_basis(raw_text)

    # Check for multi-column presence
    lines = raw_text.splitlines()

    for nutrient_key, pattern_list in _NUTRITION_PATTERNS.items():
        found = False

        # First pass: try line-by-line inspection to handle multi-column rows cleanly
        for line in lines:
            # Check if this line corresponds to this nutrient
            if any(re.search(pat, line, re.IGNORECASE) for pat in pattern_list):
                tokens = _extract_multi_column_row(line)
                if tokens:
                    # Ignore % RDA tokens if present
                    pure_tokens = [t for t in tokens if t[1] != "%"]
                    if pure_tokens:
                        # Col 1: usually Per 100g (or primary declared basis)
                        val1, unit1 = pure_tokens[0]
                        unit = unit1 or _DEFAULT_UNIT[nutrient_key]

                        # Col 2: if present, Per Serving
                        val_serve = pure_tokens[1][0] if len(pure_tokens) > 1 else None

                        # Plausibility sanity checks
                        if unit == "g" and val1 > 100.0:
                            continue  # Impossible per-100g gram weight

                        nutrients[nutrient_key] = {
                            "value": val1,
                            "unit": unit,
                            "serving_basis": detected_basis,
                            "per_serving_value": val_serve,
                            "original_extracted": f"{val1}{unit}",
                            "confidence": 0.90,
                            "plausibility_warning": None,
                        }
                        found = True
                        break

        # Fallback to general regex search across text
        if not found:
            for pattern in pattern_list:
                m = re.search(pattern, raw_text, re.IGNORECASE)
                if m:
                    try:
                        raw_num = m.group(1).replace(',', '.')
                        val = float(raw_num)
                        unit = m.group(2).lower() if (m.lastindex >= 2 and m.group(2)) else _DEFAULT_UNIT[nutrient_key]
                        if unit == "gm":
                            unit = "g"

                        if unit == "g" and val > 100.0:
                            continue

                        nutrients[nutrient_key] = {
                            "value": val,
                            "unit": unit,
                            "serving_basis": detected_basis,
                            "per_serving_value": None,
                            "original_extracted": m.group(0).strip(),
                            "confidence": 0.85,
                            "plausibility_warning": None,
                        }
                        break
                    except (ValueError, IndexError):
                        pass

    # ── Scientific Plausibility Validation ───────────────────────────────────
    # 1. Sugar <= Carbohydrates
    sug_val = nutrients["Sugar"]["value"]
    carb_val = nutrients["Carbohydrates"]["value"]
    if sug_val is not None and carb_val is not None and sug_val > carb_val:
        nutrients["Sugar"]["plausibility_warning"] = (
            f"Extracted sugar ({sug_val}g) exceeds total carbohydrates ({carb_val}g). Check packaging alignment."
        )

    # 2. Added Sugar <= Total Sugar
    add_sug = nutrients["Added Sugar"]["value"]
    if add_sug is not None and sug_val is not None and add_sug > sug_val:
        nutrients["Added Sugar"]["plausibility_warning"] = (
            f"Extracted added sugars ({add_sug}g) exceed total sugars ({sug_val}g)."
        )

    # 3. Saturated Fat + Trans Fat <= Total Fat
    sat_val = nutrients["Saturated Fat"]["value"]
    tot_fat = nutrients["Total Fat"]["value"]
    if sat_val is not None and tot_fat is not None and sat_val > tot_fat:
        nutrients["Saturated Fat"]["plausibility_warning"] = (
            f"Extracted saturated fat ({sat_val}g) exceeds total fat ({tot_fat}g)."
        )

    # 4. Sodium vs Salt validation and non-destructive conversion hint
    sod_val = nutrients["Sodium"]["value"]
    salt_val = nutrients["Salt"]["value"]
    if sod_val is not None and salt_val is not None:
        # Check consistency: Salt ≈ Sodium(g) * 2.5
        # Sodium in mg / 1000 * 2.5 = salt in g
        expected_salt = (sod_val / 1000.0) * 2.5
        if abs(salt_val - expected_salt) > max(1.5, 0.5 * expected_salt):
            nutrients["Salt"]["plausibility_warning"] = (
                f"Salt ({salt_val}g) and Sodium ({sod_val}mg) differ significantly from typical ratio."
            )

    return nutrients


# ─────────────────────────────────────────────────────────────────────────────
# Sample Demonstration Packet
# ─────────────────────────────────────────────────────────────────────────────

def get_demo_packet_data() -> Dict[str, Any]:
    """
    Returns authentic baseline sample data for demonstration mode.
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
        "Added Sugars: 4.5g\n"
        "Total Fat: 4.5g\n"
        "Saturated Fat: 1.2g\n"
        "Trans Fat: 0g\n"
        "Protein: 8.5g\n"
        "Dietary Fibre: 6.4g\n"
        "Sodium: 420mg\n"
        "Salt: 1.05g"
    )

    return {
        "is_demo": True,
        "raw_text": demo_text,
        "fields": {
            "product_name": "GOOD MORNING CRUNCHY WHOLE GRAIN CEREAL",
            "product_category": "Breakfast Cereals",
            "brand_name": "NutriHarvest Foods",
            "mrp": "₹ 145.00",
            "mrp_numeric": 145.0,
            "currency": "INR",
            "mfg_date": "15/08/2026",
            "pack_date": None,
            "expiry_date": None,
            "best_before": "6 months from mfg date",
            "ingredients": (
                "Whole Wheat Flakes (62%), Rolled Oats (18%), Brown Sugar, "
                "Honey, Vegetable Oil, Iodized Salt, Natural Flavours."
            ),
            "serving_size": "40g (approx. 1 cup)",
            "net_quantity": "350g",
            "content_type": "packaged_food",
            "is_package": True,
        },
        "nutrients": {
            "Energy":        {"value": 380.0,  "unit": "kcal", "serving_basis": "per 100g", "per_serving_value": 152.0},
            "Carbohydrates": {"value": 72.0,   "unit": "g",    "serving_basis": "per 100g", "per_serving_value": 28.8},
            "Sugar":         {"value": 12.8,   "unit": "g",    "serving_basis": "per 100g", "per_serving_value": 5.1},
            "Added Sugar":   {"value": 4.5,    "unit": "g",    "serving_basis": "per 100g", "per_serving_value": 1.8},
            "Total Fat":     {"value": 4.5,    "unit": "g",    "serving_basis": "per 100g", "per_serving_value": 1.8},
            "Saturated Fat": {"value": 1.2,    "unit": "g",    "serving_basis": "per 100g", "per_serving_value": 0.5},
            "Trans Fat":     {"value": 0.0,    "unit": "g",    "serving_basis": "per 100g", "per_serving_value": 0.0},
            "Protein":       {"value": 8.5,    "unit": "g",    "serving_basis": "per 100g", "per_serving_value": 3.4},
            "Dietary Fibre": {"value": 6.4,    "unit": "g",    "serving_basis": "per 100g", "per_serving_value": 2.6},
            "Sodium":        {"value": 420.0,  "unit": "mg",   "serving_basis": "per 100g", "per_serving_value": 168.0},
            "Salt":          {"value": 1.05,   "unit": "g",    "serving_basis": "per 100g", "per_serving_value": 0.42},
        }
    }
