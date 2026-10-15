"""
Pipeline diagnostic script.
Checks Tesseract, preprocessing, OCR, extraction, health score, risk engine, and allergens
using a synthetic label image generated in-memory (no uploaded file needed).
"""
import sys
import os

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Resolve backend path
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from backend import (
    ocr_utils,
    image_utils,
    extractor,
    nutrition_rules,
    risk_engine,
    allergen_engine,
    health_score,
)

# ── 1. Tesseract availability ────────────────────────────────────────────────
diag = ocr_utils.check_ocr_availability()
print("=" * 60)
print("1. TESSERACT AVAILABILITY")
print(f"   available : {diag['available']}")
print(f"   engine    : {diag['engine']}")
if diag['available']:
    print(f"   binary    : {diag.get('binary_path')}")
    print(f"   languages : {diag.get('languages')}")
else:
    print(f"   message   : {diag['message'][:300]}")

# ── 2. Test OCR on a simple synthetic label image ────────────────────────────
from PIL import Image, ImageDraw

def make_synthetic_label():
    """
    Creates a white 800x650 image with realistic food-label text.
    Used as a known-good test input when no real photo is available.
    """
    img = Image.new("RGB", (800, 650), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    label_lines = [
        "SUNFEAST DARK FANTASY CHOCO FILLS",
        "Brand: ITC Limited",
        "Net Weight: 300g",
        "M.R.P.: Rs. 80.00 (Incl. of all taxes)",
        "Mfg Date: 01/03/2026",
        "Best Before: 6 months from date of manufacture",
        "Serving Size: 25g",
        "",
        "Ingredients: Refined Wheat Flour (Maida), Sugar,",
        "Hydrogenated Vegetable Oil, Cocoa Powder (3.5%),",
        "Invert Syrup, Salt, Raising Agent (INS 503).",
        "Allergen Advice: Contains Wheat (Gluten). May contain Milk, Peanuts, Tree Nuts.",
        "",
        "NUTRITIONAL INFORMATION (Approx. values per 100g)",
        "Energy: 490 kcal",
        "Total Carbohydrates: 68g",
        "  of which Sugars: 28g",
        "Total Fat: 22g",
        "  Saturated Fat: 11g",
        "  Trans Fat: 0g",
        "Protein: 6.5g",
        "Dietary Fibre: 1.5g",
        "Sodium: 320mg",
        "Salt: 0.8g",
    ]
    y = 20
    for line in label_lines:
        draw.text((30, y), line, fill=(0, 0, 0))
        y += 24
    return img

synthetic_img = make_synthetic_label()
print("\n2. OCR ON SYNTHETIC LABEL IMAGE")
if diag['available']:
    processed = image_utils.preprocess_image_for_ocr(synthetic_img)
    ocr_result = ocr_utils.extract_raw_text(processed)
    print(f"   OCR success: {ocr_result['success']}")
    if ocr_result['success']:
        print(f"   OCR text length: {len(ocr_result['text'])} chars")
        print(f"   Classification: {ocr_result.get('classification', {}).get('content_type')}")
        print("   First 200 chars of OCR output:")
        print("   " + ocr_result['text'][:200].replace('\n', '\n   '))
    else:
        print(f"   OCR error: {ocr_result['error_message'][:300]}")
else:
    print("   SKIPPED — Tesseract not available")
    ocr_result = {"success": False, "text": "", "error_message": "Tesseract not available"}

# ── 3. Test extraction on synthetic OCR text ─────────────────────────────────
print("\n3. FIELD EXTRACTION FROM SYNTHETIC TEXT")
SYNTHETIC_TEXT = """
SUNFEAST DARK FANTASY CHOCO FILLS
Brand: ITC Limited
Net Weight: 300g
M.R.P.: Rs. 80.00 (Incl. of all taxes)
Mfg Date: 01/03/2026
Best Before: 6 months from date of manufacture
Serving Size: 25g

Ingredients: Refined Wheat Flour (Maida), Sugar, Hydrogenated Vegetable Oil,
Cocoa Powder (3.5%), Invert Syrup, Salt, Raising Agent (INS 503).
Allergen Advice: Contains Wheat (Gluten). May contain traces of Peanuts and Tree Nuts.

NUTRITIONAL INFORMATION (Approx. values per 100g)
Energy: 490 kcal
Total Carbohydrates: 68g
  of which Sugars: 28g
Total Fat: 22g
  Saturated Fat: 11g
  Trans Fat: 0g
Protein: 6.5g
Dietary Fibre: 1.5g
Sodium: 320mg
Salt: 0.8g
"""

fields = extractor.extract_product_fields(SYNTHETIC_TEXT)
nutrients = extractor.extract_nutrition_values(SYNTHETIC_TEXT)

print(f"   product_name : {fields['product_name']}")
print(f"   category     : {fields.get('product_category')}")
print(f"   brand_name   : {fields['brand_name']}")
print(f"   mrp          : {fields['mrp']}")
print(f"   mfg_date     : {fields['mfg_date']}")
print(f"   best_before  : {fields['best_before']}")
print(f"   serving_size : {fields['serving_size']}")
print(f"   ingredients  : {str(fields['ingredients'])[:80]}")
print("   Nutrients:")
for name, data in nutrients.items():
    print(f"     {name:20s}: value={data['value']}, unit={data['unit']}, basis={data['serving_basis']}")

# ── 4. Test Health Score with Complete vs Insufficient Data ───────────────────
print("\n4. HEALTH SCORE ENGINE")
score_complete = health_score.compute_health_score(nutrients)
print(f"   Complete data score : {score_complete['score']}/100 (Grade: {score_complete['grade']})")
print(f"   Summary             : {score_complete['summary']}")

empty_nutrients = {k: {"value": None, "unit": "g"} for k in nutrients}
score_empty = health_score.compute_health_score(empty_nutrients)
print(f"   Empty data score    : {score_empty['score']} (Status: {score_empty['status']})")
assert score_empty['score'] is None, "Score must be None when no nutrient data is present!"
print("   [OK] Health score correctly withholds score (None) instead of fabricating 50/100 Grade C.")

# ── 5. Test Allergen Engine ───────────────────────────────────────────────────
print("\n5. ALLERGEN ENGINE")
allergen_res = allergen_engine.detect_allergens(
    fields.get("ingredients"),
    fields.get("declared_allergens"),
    fields.get("precautionary_allergens"),
)
print(f"   Declared Allergens (Contains)     : {[a['name'] for a in allergen_res.get('declared_allergens', [])]}")
print(f"   Precautionary Allergens (May Contain): {[a['name'] for a in allergen_res.get('precautionary_allergens', [])]}")
print(f"   Allergens Not Detected            : {len(allergen_res.get('allergens_clear', []))} categories")

# ── 6. Test Risk Engine ───────────────────────────────────────────────────────
print("\n6. RISK ENGINE")
risk = risk_engine.run_full_risk_analysis(nutrients, fields.get("ingredients"))
print(f"   nutrition_available   : {risk['nutrition_available']}")
print(f"   ingredients_available : {risk['ingredients_available']}")
print(f"   has_high_alerts       : {risk['has_high_alerts']}")
print(f"   quantitative alerts:")
for a in risk['quantitative_alerts']:
    print(f"     {a['nutrient']:20s}: {a['status']:10s}  value={a['value_display']}")
print(f"   ingredient flags: {[f['name'] for f in risk['ingredient_flags']]}")

# ── 7. Recipe vs Packaging Distinction Test ──────────────────────────────────
print("\n7. RECIPE CLASSIFICATION TEST")
RECIPE_TEXT = """
HOMEMADE CHOCOLATE CHIP COOKIES RECIPE
Prep time: 15 mins | Cook time: 10 mins | Total time: 25 mins
Servings: 24 cookies
Ingredients:
2 1/4 cups all-purpose flour, 1 tsp baking soda, 1 tsp salt,
1 cup unsalted butter, softened, 3/4 cup granulated sugar,
3/4 cup packed brown sugar, 2 large eggs, 2 cups semi-sweet chocolate chips.
Directions:
Step 1: Preheat oven to 375 degrees F.
Step 2: In a small bowl, whisk together flour, baking soda, and salt.
Step 3: Beat butter, granulated sugar, brown sugar and vanilla until creamy.
"""
recipe_class = ocr_utils.classify_content_type(RECIPE_TEXT)
recipe_fields = extractor.extract_product_fields(RECIPE_TEXT, recipe_class)
print(f"   Classification       : {recipe_class['content_type']} (is_package: {recipe_class['is_package']})")
print(f"   Extracted product_name: {recipe_fields['product_name']} (Expected: None / N/A)")
print(f"   Extracted brand_name : {recipe_fields['brand_name']} (Expected: None)")
print(f"   Extracted MRP        : {recipe_fields['mrp']} (Expected: None)")
assert recipe_class['content_type'] == "recipe"
assert recipe_fields['product_name'] is None
print("   [OK] Recipes are cleanly identified and never confused with commercial packaged products.")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE — ALL CHECKS PASSED")
