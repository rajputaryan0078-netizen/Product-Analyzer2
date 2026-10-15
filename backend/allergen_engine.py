"""
Allergen Detection Engine — VEDANSHU Product Packet Analyser.

Scans extracted ingredients and packaging declarations for allergens defined by
major food safety regulations (FSSAI, EU FIC 1169/2011, US FDA FALCPA).

KEY REQUIREMENTS:
-----------------
1. Regex word-boundary matching:
   Strict `\\b` word boundaries prevent false substring positives (e.g. "oat" matching
   "chocolate", "nut" matching "minute", "pea" matching "peanut", "egg" matching "veggie").
2. Separate declared ingredients from precautionary statements:
   Distinguishes explicit ingredients ("CONTAINS") from cross-contamination warnings ("MAY CONTAIN").
3. Explicit 4-state reporting:
   - CONTAINS
   - MAY_CONTAIN
   - NOT_DETECTED
   - UNKNOWN (when ingredients text is absent/unreadable)
4. Never assume allergen absence:
   Absence of a keyword in OCR is never presented as a guarantee of allergen absence.
"""

import re
from typing import Dict, Any, List, Optional


ALLERGEN_DATABASE: List[Dict[str, Any]] = [
    {
        "name": "Gluten",
        "category": "Cereals containing Gluten",
        "icon": "🌾",
        "search_terms": [
            "wheat", "wheat flour", "refined wheat flour", "maida",
            "whole wheat", "durum", "semolina", "sooji", "suji", "rava",
            "barley", "rye", "oats", "oat", "spelt", "triticale",
            "gluten", "seitan", "malt",
        ],
        "severity": "high",
        "note": (
            "Wheat/gluten is one of the most common allergens. Individuals with "
            "celiac disease or gluten sensitivity must avoid gluten-containing cereals."
        ),
    },
    {
        "name": "Milk / Dairy",
        "category": "Dairy",
        "icon": "🥛",
        "search_terms": [
            "milk", "milk solids", "milk powder", "skimmed milk",
            "whole milk", "cream", "butter", "ghee", "cheese",
            "paneer", "curd", "yogurt", "yoghurt", "whey",
            "whey protein", "casein", "caseinate", "lactose",
            "lactalbumin", "buttermilk", "dairy",
        ],
        "severity": "high",
        "note": (
            "Contains milk proteins (casein, whey) and lactose. "
            "Relevant for both cow's milk protein allergy and lactose intolerance."
        ),
    },
    {
        "name": "Peanuts",
        "category": "Peanuts & Groundnuts",
        "icon": "🥜",
        "search_terms": [
            "peanut", "peanuts", "groundnut", "groundnuts",
            "peanut oil", "groundnut oil", "arachis oil",
            "peanut butter", "peanut flour",
        ],
        "severity": "high",
        "note": (
            "Peanuts are a potent allergen capable of causing severe anaphylaxis. "
            "Distinct from tree nuts (peanuts are legumes)."
        ),
    },
    {
        "name": "Tree Nuts",
        "category": "Tree Nuts",
        "icon": "🌰",
        "search_terms": [
            "almond", "almonds", "walnut", "walnuts",
            "cashew", "cashews", "cashew nut",
            "pistachio", "pistachios", "hazelnut", "hazelnuts",
            "macadamia", "pecan", "pecans", "brazil nut",
            "pine nut", "pine nuts", "chestnut", "chestnuts",
        ],
        "severity": "high",
        "note": (
            "Tree nut allergies can be severe. Cross-reactivity between "
            "different botanical tree nuts is common."
        ),
    },
    {
        "name": "Soy / Soybean",
        "category": "Soy",
        "icon": "🫘",
        "search_terms": [
            "soy", "soya", "soybean", "soybeans",
            "soy lecithin", "soya lecithin", "soy protein",
            "soy sauce", "tofu", "edamame", "tempeh",
            "soy flour", "soya flour",
        ],
        "severity": "moderate",
        "note": (
            "Soy is commonly used in emulsifiers (INS 322 / soy lecithin) and "
            "protein isolates across processed foods."
        ),
    },
    {
        "name": "Eggs",
        "category": "Eggs",
        "icon": "🥚",
        "search_terms": [
            "egg", "eggs", "egg white", "egg yolk",
            "albumin", "ovalbumin", "ovomucin",
            "lysozyme", "mayonnaise", "meringue",
        ],
        "severity": "high",
        "note": "Common trigger in baked goods, confectionery, and sauces.",
    },
    {
        "name": "Fish",
        "category": "Fish",
        "icon": "🐟",
        "search_terms": [
            "fish", "cod", "salmon", "tuna", "sardine", "sardines",
            "anchovy", "anchovies", "mackerel", "herring",
            "fish sauce", "fish oil", "fish extract",
        ],
        "severity": "high",
        "note": "Can trigger severe reactions. Often found in savory sauces and gelatin.",
    },
    {
        "name": "Crustaceans",
        "category": "Shellfish",
        "icon": "🦐",
        "search_terms": [
            "shrimp", "prawn", "prawns", "crab", "lobster",
            "crayfish", "crawfish", "crustacean", "shellfish",
        ],
        "severity": "high",
        "note": "Shellfish allergen (tropomyosin protein). High risk of severe allergic response.",
    },
    {
        "name": "Sesame",
        "category": "Sesame",
        "icon": "⚪",
        "search_terms": [
            "sesame", "sesame seeds", "sesame oil", "til", "tahini",
            "gingelly oil", "til oil",
        ],
        "severity": "moderate",
        "note": "Common in Indian, Middle Eastern, and Asian foods.",
    },
    {
        "name": "Mustard",
        "category": "Mustard",
        "icon": "🟡",
        "search_terms": [
            "mustard", "mustard seed", "mustard oil",
            "mustard powder", "mustard flour", "sarson",
        ],
        "severity": "moderate",
        "note": "Widely used in Indian culinary preparations and European condiments.",
    },
    {
        "name": "Sulphites",
        "category": "Preservatives",
        "icon": "⚗️",
        "search_terms": [
            "sulphite", "sulfite", "sulphur dioxide", "sulfur dioxide",
            "metabisulphite", "metabisulfite", "sodium sulphite",
            "sodium sulfite", "so2", "ins 220", "ins 221",
            "ins 222", "ins 223", "ins 224", "e220", "e221", "e222", "e223", "e224",
        ],
        "severity": "moderate",
        "note": "Can trigger bronchospasm and asthma exacerbations in sensitive individuals.",
    },
    {
        "name": "Celery",
        "category": "Celery",
        "icon": "🥬",
        "search_terms": [
            "celery", "celeriac", "celery salt", "celery seed",
        ],
        "severity": "info",
        "note": "Mandatory allergen disclosure under EU regulations.",
    },
    {
        "name": "Molluscs",
        "category": "Molluscs",
        "icon": "🦑",
        "search_terms": [
            "squid", "oyster", "oysters", "mussel", "mussels",
            "clam", "clams", "scallop", "scallops", "octopus",
            "snail", "mollusc", "mollusk",
        ],
        "severity": "moderate",
        "note": "Distinct class of shellfish allergy.",
    },
]


def _match_terms_with_word_boundary(text: str, terms: List[str]) -> List[str]:
    """
    Finds exact word-boundary matches for terms in text.
    Prevents false substring matches like 'oat' in 'chocolate' or 'nut' in 'minute'.
    """
    matched = []
    for term in terms:
        # Require word boundary on both sides
        pattern = rf'\b{re.escape(term.lower())}\b'
        if re.search(pattern, text):
            matched.append(term)
    return matched


def detect_allergens(
    raw_ingredients_text: Optional[str],
    declared_statements: Optional[str] = None,
    precautionary_statements: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Scans ingredients and package statements for allergens.
    Distinguishes direct inclusion (CONTAINS) from precautionary warnings (MAY_CONTAIN).

    Returns:
      {
        "allergens_found": [...],          # Combined for frontend rendering
        "allergens_clear": [...],          # Unfound allergens (checked in text)
        "declared_allergens": [...],       # Directly in ingredients/contains
        "precautionary_allergens": [...],  # In "may contain" / facility warnings
        "has_allergens": bool,
        "ingredients_available": bool,
        "total_checked": int,
        "total_found": int,
        "status": "detected" | "not_detected" | "unknown",
        "disclaimer": str,
      }
    """
    total_checked = len(ALLERGEN_DATABASE)

    result: Dict[str, Any] = {
        "allergens_found": [],
        "allergens_clear": [],
        "declared_allergens": [],
        "precautionary_allergens": [],
        "has_allergens": False,
        "ingredients_available": False,
        "total_checked": total_checked,
        "total_found": 0,
        "status": "unknown",
        "disclaimer": (
            "Absence of evidence is not evidence of absence. Allergen detection relies "
            "on keyword matching from OCR text. Always verify against the physical package."
        ),
    }

    # Combined corpus
    has_text = bool(
        (raw_ingredients_text and raw_ingredients_text.strip()) or
        (declared_statements and declared_statements.strip()) or
        (precautionary_statements and precautionary_statements.strip())
    )

    if not has_text:
        result["status"] = "unknown"
        result["allergens_clear"] = []  # Do not declare clean when text is missing!
        return result

    result["ingredients_available"] = True

    ing_corpus = (raw_ingredients_text or "").lower()
    decl_corpus = (declared_statements or "").lower()
    prec_corpus = (precautionary_statements or "").lower()

    # Also detect inline "may contain" within ingredients text if present
    inline_prec = ""
    may_match = re.search(r'\b(?:may\s+contain|manufactured\s+in|processed\s+in)\b.*', ing_corpus)
    if may_match:
        inline_prec = may_match.group(0)
        # Strip precautionary tail from primary ingredient text
        ing_corpus = ing_corpus[:may_match.start()]

    full_prec_corpus = f"{prec_corpus} {inline_prec}".strip()
    primary_corpus = f"{ing_corpus} {decl_corpus}".strip()

    for allergen in ALLERGEN_DATABASE:
        terms = allergen["search_terms"]

        # 1. Check primary ingredients / declared "contains"
        found_primary = _match_terms_with_word_boundary(primary_corpus, terms)

        # 2. Check precautionary statements ("may contain")
        found_precautionary = _match_terms_with_word_boundary(full_prec_corpus, terms)

        if found_primary:
            entry = {
                "name": allergen["name"],
                "category": allergen["category"],
                "icon": allergen["icon"],
                "found_terms": found_primary,
                "severity": allergen["severity"],
                "type": "CONTAINS",
                "status_label": "Contains (Ingredient)",
                "note": allergen["note"],
            }
            result["declared_allergens"].append(entry)
            result["allergens_found"].append(entry)
        elif found_precautionary:
            entry = {
                "name": allergen["name"],
                "category": allergen["category"],
                "icon": allergen["icon"],
                "found_terms": found_precautionary,
                "severity": "moderate" if allergen["severity"] == "high" else "info",
                "type": "MAY_CONTAIN",
                "status_label": "May Contain (Cross-contact Risk)",
                "note": f"Precautionary statement on packaging: May contain {', '.join(found_precautionary)}.",
            }
            result["precautionary_allergens"].append(entry)
            result["allergens_found"].append(entry)
        else:
            result["allergens_clear"].append(allergen["name"])

    result["total_found"] = len(result["allergens_found"])
    result["has_allergens"] = result["total_found"] > 0
    result["status"] = "detected" if result["has_allergens"] else "not_detected"

    return result
