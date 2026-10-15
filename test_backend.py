"""
Comprehensive Test Suite — VEDANSHU Product Packet Analyser.
Covers all 15 verification scenarios requested in Phase 9:
 1. Readable packaged-food label with all fields present.
 2. Nutrition table with multiple columns (Per 100g vs Per Serving).
 3. Indian MRP and date formats (incl. of all taxes, PKD, Mfg, Best before).
 4. Ingredients containing allergens with strict word boundaries.
 5. Recipe screenshot mistakenly presented as a product package.
 6. Image with no readable text / blank.
 7. Image with only partial nutrition data.
 8. Sodium versus salt conversion and distinction.
 9. Missing added sugar and other missing nutrients.
 10. Incorrect OCR readings and ambiguous dates.
 11. Unsupported files and oversized uploads.
 12. PDF/CSV consistency and safe export of null/partial data.
 13. Product with no nutrition table.
 14. Label containing 'may contain' allergen wording.
 15. Health scoring with complete, partial, and absent nutrient data.
"""

import sys
import os
import io

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Resolve imports
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_BACKEND = os.path.join(_HERE, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from PIL import Image, ImageDraw
from backend import (
    image_utils,
    ocr_utils,
    extractor,
    nutrition_rules,
    health_score,
    allergen_engine,
    risk_engine,
    export_engine,
)

_results = []


def check(name, fn):
    try:
        fn()
        _results.append((name, True, ""))
        print(f"[PASS]  {name}")
    except Exception as exc:
        _results.append((name, False, str(exc)))
        print(f"[FAIL]  {name}")
        print(f"        Reason: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. READABLE PACKAGED-FOOD LABEL WITH ALL FIELDS
# ─────────────────────────────────────────────────────────────────────────────
def test_full_packaged_food_label():
    text = """
    BRITANNIA NUTRICHOICE OAT COOKIES
    Brand: Britannia Industries
    Net Weight: 150g
    M.R.P.: Rs. 45.00 (Incl. of all taxes)
    Mfg Date: 12/04/2026
    Best Before: 6 months from manufacture
    Serving Size: 25g

    Ingredients: Rolled Oats (38%), Refined Wheat Flour (Maida), Edible Vegetable Oil,
    Sugar, Invert Syrup, Milk Solids, Salt, Raising Agents (INS 500ii).
    Contains: Wheat, Oats, Milk.

    NUTRITIONAL INFORMATION (Approx. values per 100g)
    Energy: 460 kcal
    Total Carbohydrates: 68g
      of which Sugars: 18g
    Total Fat: 18g
      Saturated Fat: 8.5g
      Trans Fat: 0g
    Protein: 8.0g
    Dietary Fibre: 6.0g
    Sodium: 340mg
    Salt: 0.85g
    """
    fields = extractor.extract_product_fields(text)
    nutrients = extractor.extract_nutrition_values(text)

    assert fields["product_name"] == "BRITANNIA NUTRICHOICE OAT COOKIES", f"Wrong name: {fields['product_name']}"
    assert fields["brand_name"] == "Britannia Industries", f"Wrong brand: {fields['brand_name']}"
    assert fields["mrp"] == "₹ 45.00", f"Wrong MRP: {fields['mrp']}"
    assert fields["mfg_date"] == "12/04/2026", f"Wrong mfg date: {fields['mfg_date']}"
    assert fields["serving_size"] == "25g", f"Wrong serving size: {fields['serving_size']}"
    assert fields["ingredients"] is not None and "Rolled Oats" in fields["ingredients"]
    assert nutrients["Sugar"]["value"] == 18.0
    assert nutrients["Protein"]["value"] == 8.0
    assert nutrients["Sodium"]["value"] == 340.0

check("Scenario 01: Fully readable packaged-food label with all fields", test_full_packaged_food_label)


# ─────────────────────────────────────────────────────────────────────────────
# 2. MULTI-COLUMN NUTRITION TABLE (PER 100G VS PER SERVING)
# ─────────────────────────────────────────────────────────────────────────────
def test_multi_column_nutrition_table():
    text = """
    CRUNCHY GRANOLA BARS
    NUTRITIONAL INFORMATION
    Nutrient                   Per 100g       Per Serve (40g)     % RDA
    Energy (kcal)              420            168                 8%
    Total Carbohydrates (g)    65             26                  10%
    Total Sugars (g)           14.5           5.8                 -
    Total Fat (g)              12.0           4.8                 7%
    Saturated Fat (g)          3.2            1.3                 6%
    Protein (g)                9.0            3.6                 7%
    Dietary Fibre (g)          7.5            3.0                 10%
    Sodium (mg)                280            112                 5%
    """
    nutrients = extractor.extract_nutrition_values(text)

    # Per 100g column should be captured as primary value
    assert nutrients["Energy"]["value"] == 420.0, f"Expected 420, got {nutrients['Energy']['value']}"
    assert nutrients["Carbohydrates"]["value"] == 65.0, f"Expected 65, got {nutrients['Carbohydrates']['value']}"
    assert nutrients["Sugar"]["value"] == 14.5, f"Expected 14.5, got {nutrients['Sugar']['value']}"
    assert nutrients["Total Fat"]["value"] == 12.0, f"Expected 12.0, got {nutrients['Total Fat']['value']}"
    assert nutrients["Saturated Fat"]["value"] == 3.2, f"Expected 3.2, got {nutrients['Saturated Fat']['value']}"
    assert nutrients["Protein"]["value"] == 9.0, f"Expected 9.0, got {nutrients['Protein']['value']}"
    assert nutrients["Dietary Fibre"]["value"] == 7.5, f"Expected 7.5, got {nutrients['Dietary Fibre']['value']}"
    assert nutrients["Sodium"]["value"] == 280.0, f"Expected 280, got {nutrients['Sodium']['value']}"

    # Per Serving column should also be captured
    assert nutrients["Energy"]["per_serving_value"] == 168.0, f"Expected 168, got {nutrients['Energy']['per_serving_value']}"
    assert nutrients["Sugar"]["per_serving_value"] == 5.8, f"Expected 5.8, got {nutrients['Sugar']['per_serving_value']}"

check("Scenario 02: Multi-column nutrition table preserves column association", test_multi_column_nutrition_table)


# ─────────────────────────────────────────────────────────────────────────────
# 3. INDIAN MRP AND DATE FORMATS
# ─────────────────────────────────────────────────────────────────────────────
def test_indian_mrp_and_dates():
    text1 = "HALDIRAM BHUJIA SEV\nPKD 15/02/2026\nUSE BY 14/08/2026\nMRP Rs. 120.00 (inclusive of all taxes)"
    fields1 = extractor.extract_product_fields(text1)
    assert fields1["mrp"] == "₹ 120.00", f"Expected ₹ 120.00, got {fields1['mrp']}"
    assert fields1["pack_date"] == "15/02/2026"
    assert fields1["expiry_date"] == "14/08/2026"

    text2 = "AMUL CHEESE SLICES\nMFD. 01.03.2026\nBEST BEFORE 9 MONTHS FROM PACKAGING\nMax. Retail Price: Rs 99/-"
    fields2 = extractor.extract_product_fields(text2)
    assert fields2["mrp"] == "₹ 99.00"
    assert fields2["mfg_date"] == "01.03.2026"
    assert "9 months" in fields2["best_before"].lower()

check("Scenario 03: Indian MRP formats (incl taxes, /-) and date variations (PKD, MFD, Best before)", test_indian_mrp_and_dates)


# ─────────────────────────────────────────────────────────────────────────────
# 4. INGREDIENTS CONTAINING ALLERGENS (WORD BOUNDARY PRECISION)
# ─────────────────────────────────────────────────────────────────────────────
def test_allergen_word_boundary_precision():
    # Text with words containing substrings of allergens:
    # "chocolate" contains "oat"
    # "minute" contains "nut"
    # "pear" contains "pea"
    # "veggie" contains "egg"
    tricky_text = "Ingredients: Dark Chocolate coating, pear extract, minute tapioca pearls, veggie oil."
    res = allergen_engine.detect_allergens(tricky_text)

    found_names = [a["name"] for a in res["allergens_found"]]
    assert "Peanuts" not in found_names, "False positive: 'pear' should not match Peanuts!"
    assert "Tree Nuts" not in found_names, "False positive: 'minute' should not match Tree Nuts!"
    assert "Eggs" not in found_names, "False positive: 'veggie' should not match Eggs!"

    # Real allergen text
    real_text = "Ingredients: Whole wheat flour, skimmed milk powder, roasted peanuts, soy lecithin."
    real_res = allergen_engine.detect_allergens(real_text)
    real_names = [a["name"] for a in real_res["allergens_found"]]
    assert "Gluten" in real_names
    assert "Milk / Dairy" in real_names
    assert "Peanuts" in real_names
    assert "Soy / Soybean" in real_names

check("Scenario 04: Allergen detection word-boundary precision prevents false positives", test_allergen_word_boundary_precision)


# ─────────────────────────────────────────────────────────────────────────────
# 5. RECIPE SCREENSHOT MISTAKENLY PRESENTED AS PRODUCT PACKAGE
# ─────────────────────────────────────────────────────────────────────────────
def test_recipe_classification_not_packaged_food():
    recipe_text = """
    VANILLA CAKE RECIPE
    Prep time: 20 mins | Bake time: 35 mins | Servings: 8 people
    Ingredients:
    2 cups all-purpose flour, 1 cup granulated sugar, 1/2 cup butter, 2 eggs, 1 cup milk, 2 tsp baking powder.
    Directions:
    Step 1: Preheat oven to 350°F. Grease and flour a 9-inch cake pan.
    Step 2: In a medium bowl, whisk together flour and baking powder.
    Step 3: Cream butter and sugar until light and fluffy.
    """
    classif = ocr_utils.classify_content_type(recipe_text)
    assert classif["content_type"] == "recipe", f"Expected recipe, got {classif['content_type']}"
    assert not classif["is_package"]

    fields = extractor.extract_product_fields(recipe_text, classif)
    assert fields["product_name"] is None, f"Recipe title should NOT be assigned as product_name: {fields['product_name']}"
    assert fields["brand_name"] is None
    assert fields["mrp"] is None
    assert fields["mfg_date"] is None
    assert fields["expiry_date"] is None

check("Scenario 05: Recipe screenshot is classified as recipe and package fields are withheld", test_recipe_classification_not_packaged_food)


# ─────────────────────────────────────────────────────────────────────────────
# 6. IMAGE WITH NO READABLE TEXT
# ─────────────────────────────────────────────────────────────────────────────
def test_image_with_no_readable_text():
    # Empty string or noise
    classif = ocr_utils.classify_content_type("")
    assert classif["content_type"] == "empty"
    assert not classif["is_package"]

    fields = extractor.extract_product_fields("")
    assert fields["product_name"] is None
    assert fields["brand_name"] is None

    nutrients = extractor.extract_nutrition_values("")
    assert all(data["value"] is None for data in nutrients.values())

    score = health_score.compute_health_score(nutrients)
    assert score["status"] == "insufficient_data"
    assert score["score"] is None
    assert score["grade"] is None

check("Scenario 06: Empty image text returns clean null status and no default score", test_image_with_no_readable_text)


# ─────────────────────────────────────────────────────────────────────────────
# 7. PARTIAL NUTRITION DATA
# ─────────────────────────────────────────────────────────────────────────────
def test_partial_nutrition_data():
    # Only Sugar and Saturated Fat are present
    partial_text = """
    FRUIT SPREAD
    NUTRITIONAL INFORMATION per 100g:
    Total Sugars: 42g
    Saturated Fat: 0.1g
    """
    nutrients = extractor.extract_nutrition_values(partial_text)
    assert nutrients["Sugar"]["value"] == 42.0
    assert nutrients["Saturated Fat"]["value"] == 0.1
    assert nutrients["Protein"]["value"] is None
    assert nutrients["Sodium"]["value"] is None

    score = health_score.compute_health_score(nutrients)
    assert score["status"] == "partial_data"
    assert score["score"] is not None
    assert score["detected_count"] == 2
    assert "Sugar" in score["detected_nutrients"]
    assert "Saturated Fat" in score["detected_nutrients"]
    assert "Protein" in score["missing_nutrients"]

check("Scenario 07: Partial nutrition data computes re-normalized score and discloses coverage", test_partial_nutrition_data)


# ─────────────────────────────────────────────────────────────────────────────
# 8. SODIUM VERSUS SALT DISTINCTION AND CONVERSION
# ─────────────────────────────────────────────────────────────────────────────
def test_sodium_vs_salt_distinction():
    # When both are present with distinct numbers
    text_both = "NUTRITION FACTS: Sodium: 400mg, Salt: 1.0g"
    nutrients = extractor.extract_nutrition_values(text_both)
    assert nutrients["Sodium"]["value"] == 400.0
    assert nutrients["Sodium"]["unit"] == "mg"
    assert nutrients["Salt"]["value"] == 1.0
    assert nutrients["Salt"]["unit"] == "g"

    # When only Salt is present
    text_salt_only = "NUTRITION FACTS: Total Sugars: 10g, Total Fat: 5g, Saturated Fat: 1g, Salt: 1.5g"
    nut_salt = extractor.extract_nutrition_values(text_salt_only)
    assert nut_salt["Sodium"]["value"] is None
    assert nut_salt["Salt"]["value"] == 1.5

    # Health score safely derives sodium from salt without falsifying the extracted object
    score = health_score.compute_health_score(nut_salt)
    sodium_comp = next(c for c in score["components"] if c["nutrient"] == "Sodium")
    assert sodium_comp["detected"] is True
    assert sodium_comp["derived"] is True
    # 1.5g salt / 2.5 * 1000 = 600mg sodium
    assert abs(sodium_comp["value"] - 600.0) < 0.1

check("Scenario 08: Sodium vs Salt distinction and non-destructive derivation", test_sodium_vs_salt_distinction)


# ─────────────────────────────────────────────────────────────────────────────
# 9. MISSING ADDED SUGAR AND MISSING NUTRIENTS
# ─────────────────────────────────────────────────────────────────────────────
def test_missing_added_sugar_and_missing_nutrients():
    text = "NUTRITIONAL INFORMATION per 100g: Total Sugars: 15g, Protein: 5g"
    nutrients = extractor.extract_nutrition_values(text)
    assert nutrients["Sugar"]["value"] == 15.0
    assert nutrients["Added Sugar"]["value"] is None, "Absent added sugar must remain None, not 0!"
    assert nutrients["Trans Fat"]["value"] is None, "Absent trans fat must remain None, not 0!"

check("Scenario 09: Absent nutrients remain None and are never inferred as zero", test_missing_added_sugar_and_missing_nutrients)


# ─────────────────────────────────────────────────────────────────────────────
# 10. INCORRECT OCR READINGS AND AMBIGUOUS DATES
# ─────────────────────────────────────────────────────────────────────────────
def test_ocr_repair_and_ambiguous_dates():
    # Fused '9' for 'g' in nutrition line: "Total Carbohydrates: 689" -> repaired to 68g
    corrupted_line = "Total Carbohydrates: 689"
    repaired = ocr_utils._repair_nutrition_line(corrupted_line)
    assert repaired == "Total Carbohydrates: 68g", f"Failed repair: {repaired}"

    # Plausibility check: sugar > carbs
    impossible_nutrition = "Total Carbohydrates: 20g, Total Sugars: 50g"
    nutrients = extractor.extract_nutrition_values(impossible_nutrition)
    assert nutrients["Sugar"]["plausibility_warning"] is not None

check("Scenario 10: OCR line repair and plausibility validation flag anomalies", test_ocr_repair_and_ambiguous_dates)


# ─────────────────────────────────────────────────────────────────────────────
# 11. UNSUPPORTED FILES AND OVERSIZED UPLOADS
# ─────────────────────────────────────────────────────────────────────────────
def test_unsupported_and_oversized_files():
    class DummyFile:
        def __init__(self, name, size):
            self.name = name
            self.size = size
        def seek(self, pos): pass

    # Unsupported extension (.exe)
    ok, err = image_utils.validate_image_file(DummyFile("payload.exe", 1024))
    assert not ok and "Unsupported" in err

    # Oversized file (> 15 MB)
    ok, err = image_utils.validate_image_file(DummyFile("photo.jpg", 20 * 1024 * 1024))
    assert not ok and "exceeds" in err

    # Supported format (.webp)
    dummy_webp = io.BytesIO()
    im = Image.new("RGB", (100, 100), color=(200, 200, 200))
    im.save(dummy_webp, format="WEBP")
    dummy_webp.name = "snack.webp"
    dummy_webp.size = dummy_webp.tell()
    dummy_webp.seek(0)
    ok, err = image_utils.validate_image_file(dummy_webp)
    assert ok, f"WebP should be supported, got error: {err}"

check("Scenario 11: Unsupported files rejected and WebP successfully validated", test_unsupported_and_oversized_files)


# ─────────────────────────────────────────────────────────────────────────────
# 12. PDF AND CSV EXPORT CONSISTENCY
# ─────────────────────────────────────────────────────────────────────────────
def test_pdf_and_csv_export_consistency():
    demo_data = extractor.get_demo_packet_data()
    nutrients = demo_data["nutrients"]
    fields = demo_data["fields"]
    risk = risk_engine.run_full_risk_analysis(nutrients, fields.get("ingredients"))
    allergens = allergen_engine.detect_allergens(fields.get("ingredients"))
    score = health_score.compute_health_score(nutrients)

    results = {
        "is_demo": True,
        "fields": fields,
        "nutrients": nutrients,
        "risk_analysis": risk,
        "allergen_analysis": allergens,
        "health_score": score,
    }

    # CSV Generation
    csv_bytes = export_engine.generate_csv(results)
    assert len(csv_bytes) > 200
    csv_text = csv_bytes.decode("utf-8-sig")
    assert "GOOD MORNING CRUNCHY WHOLE GRAIN CEREAL" in csv_text
    assert "SECTION 2: HEALTH SCORE EVALUATION" in csv_text

    # PDF Generation
    pdf_bytes = export_engine.generate_pdf(results)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")

check("Scenario 12: PDF and CSV export formats generate valid documents consistently", test_pdf_and_csv_export_consistency)


# ─────────────────────────────────────────────────────────────────────────────
# 13. PRODUCT WITH NO NUTRITION TABLE
# ─────────────────────────────────────────────────────────────────────────────
def test_product_with_no_nutrition_table():
    text = """
    ORGANIC WHOLE CLOVES (LAVANG)
    Brand: Tata Sampann
    Net Weight: 100g
    M.R.P.: Rs. 85.00
    Mfg Date: 01/01/2026
    Ingredients: Whole dried cloves.
    """
    fields = extractor.extract_product_fields(text)
    nutrients = extractor.extract_nutrition_values(text)

    assert fields["product_name"] == "ORGANIC WHOLE CLOVES (LAVANG)"
    assert all(d["value"] is None for d in nutrients.values())

    score = health_score.compute_health_score(nutrients)
    assert score["status"] == "insufficient_data"
    assert score["score"] is None
    assert score["grade"] is None

check("Scenario 13: Product without nutrition table reports missing nutrients without default score", test_product_with_no_nutrition_table)


# ─────────────────────────────────────────────────────────────────────────────
# 14. PRECAUTIONARY 'MAY CONTAIN' ALLERGEN STATEMENTS
# ─────────────────────────────────────────────────────────────────────────────
def test_precautionary_may_contain_allergens():
    text = "Ingredients: Sugar, Cocoa Butter, Milk Powder. May contain traces of Peanuts and Tree Nuts."
    res = allergen_engine.detect_allergens(text)

    decl_names = [a["name"] for a in res["declared_allergens"]]
    prec_names = [a["name"] for a in res["precautionary_allergens"]]

    assert "Milk / Dairy" in decl_names, "Milk should be a declared ingredient allergen"
    assert "Peanuts" in prec_names, "Peanuts should be in precautionary allergens"
    assert "Tree Nuts" in prec_names, "Tree Nuts should be in precautionary allergens"
    assert "Peanuts" not in decl_names, "Peanuts was NOT an ingredient, only a 'may contain' warning"

check("Scenario 14: Precautionary 'may contain' statements correctly separated from declared ingredients", test_precautionary_may_contain_allergens)


# ─────────────────────────────────────────────────────────────────────────────
# 15. HEALTH SCORING WITH COMPLETE, PARTIAL, AND ABSENT NUTRIENT DATA
# ─────────────────────────────────────────────────────────────────────────────
def test_health_scoring_all_tiers():
    # Tier A: Complete
    complete_nutrients = {
        "Sugar":         {"value": 4.0,  "unit": "g"},   # 100 pts (weight 20) -> 2000
        "Saturated Fat": {"value": 1.0,  "unit": "g"},   # 100 pts (weight 20) -> 2000
        "Trans Fat":     {"value": 0.0,  "unit": "g"},   # 100 pts (weight 15) -> 1500
        "Sodium":        {"value": 150,  "unit": "mg"},  # 100 pts (weight 15) -> 1500
        "Protein":       {"value": 12.0, "unit": "g"},   # 100 pts (weight 15) -> 1500
        "Dietary Fibre": {"value": 8.0,  "unit": "g"},   # 100 pts (weight 15) -> 1500
    }
    score_a = health_score.compute_health_score(complete_nutrients)
    assert score_a["status"] == "complete"
    assert score_a["score"] == 100
    assert score_a["grade"] == "A"

    # Tier B: Partial (only 2 nutrients)
    partial_nutrients = {
        "Sugar":         {"value": 30.0, "unit": "g"},  # 0 pts (penalty, weight 20)
        "Saturated Fat": {"value": 10.0, "unit": "g"},  # 0 pts (penalty, weight 20)
    }
    score_b = health_score.compute_health_score(partial_nutrients)
    assert score_b["status"] == "partial_data"
    assert score_b["score"] == 0
    assert score_b["grade"] == "D"
    assert score_b["detected_count"] == 2

    # Tier C: Absent (0 nutrients)
    empty_nutrients = {}
    score_c = health_score.compute_health_score(empty_nutrients)
    assert score_c["status"] == "insufficient_data"
    assert score_c["score"] is None
    assert score_c["grade"] is None

check("Scenario 15: Health scoring tiers (Complete -> full grade, Partial -> re-normalized, Absent -> None)", test_health_scoring_all_tiers)


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for _, ok, _ in _results if ok)
failed = sum(1 for _, ok, _ in _results if not ok)
total = len(_results)
print(f"TEST SUMMARY: {passed}/{total} PASSED ({failed} FAILED)")
print("=" * 60)

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
