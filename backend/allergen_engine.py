"""
Allergen Detection Engine — VEDANSHU Product Packet Analyser.

Scans extracted ingredients text for common allergens defined by
food safety regulations (FSSAI, EU FIC Regulation 1169/2011, FDA FALCPA).

Allergen categories monitored (13 total):
  Gluten · Milk/Dairy · Peanuts · Tree Nuts · Soy · Eggs · Fish ·
  Crustaceans · Sesame · Mustard · Sulphites · Celery · Molluscs

DISCLAIMER: Allergen detection is based on keyword matching in OCR text.
It is NOT a substitute for reading the actual product label.
False negatives are possible due to OCR errors or unusual label formats.
"""

from typing import Dict, Any, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Allergen Database
# ─────────────────────────────────────────────────────────────────────────────

ALLERGEN_DATABASE: List[Dict[str, Any]] = [
    {
        "name": "Gluten",
        "category": "Cereals containing Gluten",
        "icon": "🌾",
        "search_terms": [
            "wheat", "wheat flour", "refined wheat flour", "maida",
            "whole wheat", "durum", "semolina", "sooji", "suji", "rava",
            "barley", "rye", "oats", "oat", "spelt", "triticale",
            "gluten", "seitan",
        ],
        "severity": "high",
        "note": (
            "May cause adverse reactions in people with celiac disease "
            "or non-celiac gluten sensitivity. Wheat is one of the most "
            "common food allergens globally."
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
            "lactalbumin", "buttermilk",
        ],
        "severity": "high",
        "note": (
            "Contains lactose and milk proteins (casein, whey). "
            "Avoid if lactose intolerant or have a cow's milk protein allergy."
        ),
    },
    {
        "name": "Peanuts / Groundnuts",
        "category": "Peanuts",
        "icon": "🥜",
        "search_terms": [
            "peanut", "peanuts", "groundnut", "groundnuts",
            "peanut oil", "groundnut oil", "arachis oil",
            "peanut butter", "peanut flour",
        ],
        "severity": "high",
        "note": (
            "One of the most common food allergens. Can cause severe "
            "anaphylaxis in allergic individuals. Even trace amounts "
            "may trigger reactions."
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
            "Tree nut allergies are common and can be severe. "
            "Cross-reactivity between different tree nuts is possible."
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
            "Soy is a common allergen. Soy lecithin (emulsifier INS 322) "
            "is widely used in processed foods and may trigger reactions "
            "in highly sensitive individuals."
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
        "note": (
            "Egg allergy is common especially in children. Eggs may be "
            "present in baked goods, sauces, and confectionery."
        ),
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
        "note": (
            "Fish allergy can cause severe reactions. Fish sauce and "
            "extracts may be hidden in Asian sauces and seasonings."
        ),
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
        "note": (
            "Shellfish/crustacean allergy can cause severe anaphylaxis. "
            "One of the most common adult-onset food allergies."
        ),
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
        "note": (
            "Sesame allergy is increasingly recognized worldwide. "
            "Common in Indian and Middle Eastern foods."
        ),
    },
    {
        "name": "Mustard",
        "category": "Mustard",
        "icon": "🟡",
        "search_terms": [
            "mustard", "mustard seed", "mustard oil",
            "mustard powder", "mustard flour",
        ],
        "severity": "moderate",
        "note": (
            "Mustard allergy is more common in Europe and India. "
            "Mustard oil is a major cooking oil in parts of India."
        ),
    },
    {
        "name": "Sulphites",
        "category": "Preservative Allergen",
        "icon": "⚗️",
        "search_terms": [
            "sulphite", "sulfite", "sulphur dioxide", "sulfur dioxide",
            "metabisulphite", "metabisulfite", "sodium sulphite",
            "sodium sulfite", "so2", "ins 220", "ins 221",
            "ins 222", "ins 223", "ins 224", "ins 225",
            "ins 228", "e220", "e221", "e222", "e223", "e224",
        ],
        "severity": "moderate",
        "note": (
            "Sulphites can trigger asthma attacks and allergic reactions "
            "in sensitive individuals. Common in dried fruits, wine, "
            "and preserved foods."
        ),
    },
    {
        "name": "Celery",
        "category": "Celery",
        "icon": "🥬",
        "search_terms": [
            "celery", "celeriac", "celery salt", "celery seed",
        ],
        "severity": "info",
        "note": (
            "Celery allergy is recognized in EU food law. Can cause "
            "reactions ranging from mild oral symptoms to severe anaphylaxis."
        ),
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
        "note": (
            "Mollusc allergy is related to but distinct from crustacean "
            "allergy. Cross-reactivity is possible."
        ),
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Detection function
# ─────────────────────────────────────────────────────────────────────────────

def detect_allergens(raw_ingredients_text: Optional[str]) -> Dict[str, Any]:
    """
    Scans ingredients text for allergen keywords.

    Only flags allergens when search terms are actually found in the text.
    Never assumes or invents allergens.

    Returns:
      {
        "allergens_found": [...],     list of detected allergen dicts
        "allergens_clear": [...],     list of allergen names NOT found
        "has_allergens": bool,
        "ingredients_available": bool,
        "total_checked": int,
        "total_found": int,
      }
    """
    result: Dict[str, Any] = {
        "allergens_found": [],
        "allergens_clear": [],
        "has_allergens": False,
        "ingredients_available": False,
        "total_checked": len(ALLERGEN_DATABASE),
        "total_found": 0,
    }

    if not raw_ingredients_text or not raw_ingredients_text.strip():
        return result

    result["ingredients_available"] = True
    text_lower = raw_ingredients_text.lower()

    for allergen in ALLERGEN_DATABASE:
        found_terms = [
            term for term in allergen["search_terms"]
            if term.lower() in text_lower
        ]

        if found_terms:
            result["allergens_found"].append({
                "name": allergen["name"],
                "category": allergen["category"],
                "icon": allergen["icon"],
                "found_terms": found_terms,
                "severity": allergen["severity"],
                "note": allergen["note"],
            })
        else:
            result["allergens_clear"].append(allergen["name"])

    result["total_found"] = len(result["allergens_found"])
    result["has_allergens"] = result["total_found"] > 0

    return result
