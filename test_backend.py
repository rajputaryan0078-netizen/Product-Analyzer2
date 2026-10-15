"""
Complete test suite — VEDANSHU Product Packet Analyser backend + risk engine.
Run from the project directory:
    py test_backend.py

All 66 tests run in a single pass with a single summary at the end.
"""

import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

PASS = "  PASS"
FAIL = "  FAIL"
_results = []


def check(name, fn):
    try:
        fn()
        _results.append((name, True, ""))
        print(f"✅{PASS}  {name}")
    except Exception as exc:
        _results.append((name, False, str(exc)))
        print(f"❌{FAIL}  {name}")
        print(f"         Reason: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — SYNTAX
# ─────────────────────────────────────────────────────────────────────────────
def _syntax_all():
    import py_compile
    for f in ["image_utils.py", "ocr_utils.py", "extractor.py",
              "nutrition_rules.py", "risk_engine.py", "app.py"]:
        py_compile.compile(os.path.join(_HERE, f), doraise=True)

check("Syntax — all six modules compile without error", _syntax_all)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
def _import_all():
    import image_utils, ocr_utils, extractor, nutrition_rules, risk_engine

check("Import — all backend modules importable", _import_all)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — IMAGE VALIDATION
# ─────────────────────────────────────────────────────────────────────────────
class _FakeFile:
    def __init__(self, name, size, data=b""):
        self.name = name; self.size = size
        self._data = data; self._pos = 0
    def seek(self, pos): self._pos = pos
    def read(self, n=-1):
        chunk = self._data[self._pos:]
        if n >= 0: chunk = chunk[:n]
        self._pos += len(chunk)
        return chunk

def _val_none():
    import image_utils
    ok, msg = image_utils.validate_image_file(None)
    assert not ok and "No file" in msg

def _val_bad_ext():
    import image_utils
    ok, msg = image_utils.validate_image_file(_FakeFile("a.bmp", 100))
    assert not ok and ("Unsupported" in msg or "unsupported" in msg.lower())

def _val_too_large():
    import image_utils
    ok, msg = image_utils.validate_image_file(_FakeFile("a.jpg", 12 * 1024 * 1024))
    assert not ok and ("exceeds" in msg or "MB" in msg)

check("Image validation — None → False", _val_none)
check("Image validation — unsupported extension rejected", _val_bad_ext)
check("Image validation — oversized file rejected", _val_too_large)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — PRODUCT FIELD EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
SAMPLE_LABEL_TEXT = """
SUNFEAST DARK FANTASY CHOCO FILLS
Brand: ITC Limited
Net Weight: 300g
M.R.P.: Rs. 80.00 (Incl. of all taxes)
Mfg Date: 01/03/2026
Best Before: 6 months from date of manufacture
Serving Size: 25g

Ingredients: Refined Wheat Flour (Maida), Sugar, Hydrogenated Vegetable Oil, Cocoa Powder (3.5%),
Invert Syrup, Salt, Raising Agent (INS 503(ii)), Emulsifier (INS 322), Vanilla Flavour.

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

def _ext_name():
    import extractor
    f = extractor.extract_product_fields(SAMPLE_LABEL_TEXT)
    assert f["product_name"] and not f["product_name"].startswith("0")

def _ext_brand():
    import extractor
    f = extractor.extract_product_fields(SAMPLE_LABEL_TEXT)
    assert f["brand_name"] and ("ITC" in f["brand_name"] or "Limited" in f["brand_name"])

def _ext_mrp():
    import extractor
    f = extractor.extract_product_fields(SAMPLE_LABEL_TEXT)
    assert f["mrp"] and "80" in f["mrp"] and "₹" in f["mrp"]

def _ext_mfg():
    import extractor
    f = extractor.extract_product_fields(SAMPLE_LABEL_TEXT)
    assert f["mfg_date"] and any(t in f["mfg_date"] for t in ["2026","03","01"])

def _ext_bestbefore():
    import extractor
    f = extractor.extract_product_fields(SAMPLE_LABEL_TEXT)
    assert f["best_before"] and ("month" in f["best_before"].lower() or "6" in f["best_before"])

def _ext_ingredients():
    import extractor
    f = extractor.extract_product_fields(SAMPLE_LABEL_TEXT)
    assert f["ingredients"] and "heat" in f["ingredients"].lower()

def _ext_serving():
    import extractor
    f = extractor.extract_product_fields(SAMPLE_LABEL_TEXT)
    assert f["serving_size"] and "25" in f["serving_size"]

def _ext_empty():
    import extractor
    f = extractor.extract_product_fields("")
    n = extractor.extract_nutrition_values("")
    assert all(v is None for v in f.values())
    assert all(d["value"] is None for d in n.values())

check("Extraction — product name detected", _ext_name)
check("Extraction — brand name detected", _ext_brand)
check("Extraction — MRP extracted correctly", _ext_mrp)
check("Extraction — manufacturing date detected", _ext_mfg)
check("Extraction — best before detected", _ext_bestbefore)
check("Extraction — ingredients detected", _ext_ingredients)
check("Extraction — serving size detected", _ext_serving)
check("Extraction — empty text returns all None (no crash)", _ext_empty)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — DATE FORMAT VARIATIONS
# ─────────────────────────────────────────────────────────────────────────────
def _date_month_year():
    import extractor
    f = extractor.extract_product_fields("Mfg: Jan 2026\nExp: 15 July 2026\n")
    assert f["mfg_date"], "mfg_date not found for 'Jan 2026'"

def _date_slash():
    import extractor
    f = extractor.extract_product_fields("Mfd: 05/2026\nExpiry Date: 11/2026\n")
    assert f["mfg_date"], "mfg_date not found for '05/2026'"

def _dates_distinct():
    import extractor
    f = extractor.extract_product_fields("Mfg Date: 01/01/2026\nExpiry Date: 01/01/2027\n")
    assert f["mfg_date"] and f["expiry_date"]
    assert f["mfg_date"] != f["expiry_date"]
    assert "2026" in f["mfg_date"] and "2027" in f["expiry_date"]

check("Date parsing — 'Jan 2026' month-year format", _date_month_year)
check("Date parsing — slash-separated MM/YYYY format", _date_slash)
check("Date parsing — mfg (2026) and expiry (2027) not confused", _dates_distinct)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — NUTRITION VALUE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
def _nutr_energy():
    import extractor
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    assert n["Energy"]["value"] == 490.0 and n["Energy"]["unit"] == "kcal"

def _nutr_carbs():
    import extractor
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    assert n["Carbohydrates"]["value"] == 68.0

def _nutr_sugar():
    import extractor
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    assert n["Sugar"]["value"] == 28.0, f"Expected 28.0, got {n['Sugar']['value']}"

def _nutr_fat():
    import extractor
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    assert n["Total Fat"]["value"] == 22.0

def _nutr_sat_fat():
    import extractor
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    assert n["Saturated Fat"]["value"] == 11.0

def _nutr_trans():
    import extractor
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    assert n["Trans Fat"]["value"] == 0.0

def _nutr_protein():
    import extractor
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    assert n["Protein"]["value"] == 6.5

def _nutr_fibre():
    import extractor
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    assert n["Dietary Fibre"]["value"] == 1.5

def _nutr_sodium():
    import extractor
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    assert n["Sodium"]["value"] == 320.0 and n["Sodium"]["unit"] == "mg"

def _nutr_salt():
    import extractor
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    assert n["Salt"]["value"] == 0.8

def _nutr_added_sugar_extraction():
    import extractor
    text = "Nutritional values per 100g\nTotal Carbohydrates: 50g\n  of which Added Sugars: 15g\n"
    n = extractor.extract_nutrition_values(text)
    assert n["Added Sugar"]["value"] == 15.0, f"Got: {n['Added Sugar']['value']}"

def _nutr_gm_unit():
    import extractor
    n = extractor.extract_nutrition_values("Protein: 7.5gm\nFat: 12gm\n")
    assert n["Protein"]["unit"] == "g"
    assert n["Total Fat"]["unit"] == "g"

def _sugar_not_carbs():
    import extractor
    n = extractor.extract_nutrition_values("Total Carbohydrates: 60g\n  of which Sugars: 8g\n")
    assert n["Sugar"]["value"] == 8.0, f"Got {n['Sugar']['value']}"
    assert n["Carbohydrates"]["value"] == 60.0

def _serving_basis_detected():
    import extractor
    n = extractor.extract_nutrition_values("Nutritional values per 30g serving\nProtein: 5g\n")
    assert "30" in n["Protein"]["serving_basis"]

def _long_ingredients_trim():
    import extractor
    long_ing = "Ingredient " + ", Ingredient ".join(str(i) for i in range(200))
    f = extractor.extract_product_fields(f"Ingredients: {long_ing}\nNutritional Information\nSugar: 5g")
    if f["ingredients"]:
        assert len(f["ingredients"]) <= 920  # trimmed at 900 + " ..." suffix

check("Nutrition — Energy (kcal)", _nutr_energy)
check("Nutrition — Carbohydrates", _nutr_carbs)
check("Nutrition — Sugar not confused with Carbs", _nutr_sugar)
check("Nutrition — Total Fat", _nutr_fat)
check("Nutrition — Saturated Fat", _nutr_sat_fat)
check("Nutrition — Trans Fat (zero value)", _nutr_trans)
check("Nutrition — Protein", _nutr_protein)
check("Nutrition — Dietary Fibre", _nutr_fibre)
check("Nutrition — Sodium (mg)", _nutr_sodium)
check("Nutrition — Salt", _nutr_salt)
check("Nutrition — Added Sugar extracted when present", _nutr_added_sugar_extraction)
check("Nutrition — 'gm' normalised to 'g'", _nutr_gm_unit)
check("Nutrition — Sugar ≠ Carbohydrates", _sugar_not_carbs)
check("Nutrition — per-serving basis (30g) detected", _serving_basis_detected)
check("Extraction — long ingredients list trimmed safely", _long_ingredients_trim)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 — NUTRITION RULES (nutrition_rules.py)
# ─────────────────────────────────────────────────────────────────────────────
def _nr_sugar_above():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Sugar", 28.0, "g", "per 100g")
    assert r["status_type"] == "alert" and "Above" in r["status"]

def _nr_sugar_within():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Sugar", 5.0, "g", "per 100g")
    assert r["status_type"] == "success" and "Within" in r["status"]

def _nr_protein_low():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Protein", 2.0, "g", "per 100g")
    assert r["status_type"] == "warning" and "Below" in r["status"]

def _nr_protein_ok():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Protein", 8.5, "g", "per 100g")
    assert r["status_type"] == "success"

def _nr_trans_alert():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Trans Fat", 0.5, "g", "per 100g")
    assert r["status_type"] == "alert"

def _nr_energy_info():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Energy", 490.0, "kcal", "per 100g")
    assert r["status_type"] == "neutral" and r["status"] == "Informational"

def _nr_none_not_detected():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Sugar", None, "g", "per 100g")
    assert r["extracted_value"] == "Not detected"
    assert r["status_type"] == "muted"
    assert r["status"] == "Not detected"

def _nr_sodium_mg_within():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Sodium", 400.0, "mg", "per 100g")
    assert r["status_type"] == "success"

def _nr_sodium_mg_above():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Sodium", 850.0, "mg", "per 100g")
    assert r["status_type"] == "alert"

def _nr_sodium_g_convert():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Sodium", 0.5, "g", "per 100g")
    assert r["status_type"] == "success"

def _nr_serving_mismatch():
    import nutrition_rules
    r = nutrition_rules.evaluate_nutrient("Sugar", 8.0, "g", "per 30g")
    assert r["status_type"] == "warning" and "review" in r["status"].lower()

def _nr_compare_all_length():
    import extractor, nutrition_rules
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    rows = nutrition_rules.compare_all_nutrients(n)
    # DISPLAY_ORDER now has 11 entries (Added Sugar included)
    assert len(rows) == 11, f"Expected 11 rows, got {len(rows)}"
    names = [r["nutrient"] for r in rows]
    assert "Energy" in names
    assert "Added Sugar" in names
    assert "Sugar" in names

check("Nutrition rules — Sugar 28g → ABOVE limit", _nr_sugar_above)
check("Nutrition rules — Sugar 5g → WITHIN limit", _nr_sugar_within)
check("Nutrition rules — Protein 2g → BELOW guideline", _nr_protein_low)
check("Nutrition rules — Protein 8.5g → meets guideline", _nr_protein_ok)
check("Nutrition rules — Trans Fat 0.5g → ABOVE limit", _nr_trans_alert)
check("Nutrition rules — Energy → Informational (no pass/fail)", _nr_energy_info)
check("Nutrition rules — None value → 'Not detected' (not passing)", _nr_none_not_detected)
check("Nutrition rules — Sodium 400mg → WITHIN 600mg limit", _nr_sodium_mg_within)
check("Nutrition rules — Sodium 850mg → ABOVE 600mg limit", _nr_sodium_mg_above)
check("Nutrition rules — Sodium 0.5g (500mg) → WITHIN limit", _nr_sodium_g_convert)
check("Nutrition rules — per-serving basis → 'Needs review'", _nr_serving_mismatch)
check("Nutrition rules — compare_all_nutrients returns 11 rows (inc. Added Sugar)", _nr_compare_all_length)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8 — DEMO DATA
# ─────────────────────────────────────────────────────────────────────────────
def _demo_keys():
    import extractor
    d = extractor.get_demo_packet_data()
    assert d["is_demo"] is True
    for k in ["product_name","brand_name","mrp","mfg_date","best_before","ingredients","serving_size"]:
        assert k in d["fields"], f"Missing: {k}"
    for k in ["Energy","Carbohydrates","Sugar","Total Fat","Saturated Fat",
              "Trans Fat","Protein","Dietary Fibre","Sodium","Salt"]:
        assert k in d["nutrients"], f"Missing nutrient: {k}"
        assert d["nutrients"][k]["value"] is not None

def _demo_flagged():
    import extractor
    assert extractor.get_demo_packet_data()["is_demo"] is True

check("Demo data — all required field and nutrient keys present", _demo_keys)
check("Demo data — explicitly flagged is_demo=True", _demo_flagged)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9 — PREPROCESSING
# ─────────────────────────────────────────────────────────────────────────────
def _preprocess_ok():
    import image_utils
    from PIL import Image
    img = Image.new("RGB", (400, 200), (255, 255, 255))
    result = image_utils.preprocess_image_for_ocr(img)
    assert isinstance(result, Image.Image)

check("Preprocessing — returns PIL Image without crash (OpenCV optional)", _preprocess_ok)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10 — OCR AVAILABILITY CHECK
# ─────────────────────────────────────────────────────────────────────────────
def _ocr_struct():
    import ocr_utils
    r = ocr_utils.check_ocr_availability()
    assert "available" in r and isinstance(r["available"], bool)
    assert "message" in r and len(r["message"]) > 0

def _ocr_fake_image_no_crash():
    """Calling extract_raw_text when Tesseract is unavailable must not crash."""
    import ocr_utils
    from PIL import Image
    img = Image.new("RGB", (200, 100), (255, 255, 255))
    result = ocr_utils.extract_raw_text(img)
    assert "success" in result
    assert isinstance(result["success"], bool)
    # Must never return fabricated text on failure
    if not result["success"]:
        assert result["text"] == ""
        assert result["error_message"]

check("OCR availability — returns correct dict structure", _ocr_struct)
check("OCR extract_raw_text — no crash on fake image, honest failure if no Tesseract", _ocr_fake_image_no_crash)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11 — RISK ENGINE: QUANTITATIVE ALERTS
# ─────────────────────────────────────────────────────────────────────────────
def _re_sugar_high():
    import risk_engine
    alerts = risk_engine.evaluate_quantitative_alerts(
        {"Sugar": {"value": 30.0, "unit": "g", "serving_basis": "per 100g"}})
    a = next(x for x in alerts if x["nutrient"] == "Sugar")
    assert a["status"] == "HIGH"

def _re_sugar_moderate():
    import risk_engine
    alerts = risk_engine.evaluate_quantitative_alerts(
        {"Sugar": {"value": 10.0, "unit": "g", "serving_basis": "per 100g"}})
    a = next(x for x in alerts if x["nutrient"] == "Sugar")
    assert a["status"] == "MODERATE"

def _re_sugar_ok():
    import risk_engine
    alerts = risk_engine.evaluate_quantitative_alerts(
        {"Sugar": {"value": 3.0, "unit": "g", "serving_basis": "per 100g"}})
    a = next(x for x in alerts if x["nutrient"] == "Sugar")
    assert a["status"] == "OK"

def _re_unknown_none():
    import risk_engine
    alerts = risk_engine.evaluate_quantitative_alerts(
        {"Sugar": {"value": None, "unit": "g", "serving_basis": "per 100g"}})
    a = next(x for x in alerts if x["nutrient"] == "Sugar")
    assert a["status"] == "UNKNOWN" and a["value_display"] == "Not detected"

def _re_unknown_per_serving():
    import risk_engine
    alerts = risk_engine.evaluate_quantitative_alerts(
        {"Sugar": {"value": 8.0, "unit": "g", "serving_basis": "per 30g serving"}})
    a = next(x for x in alerts if x["nutrient"] == "Sugar")
    assert a["status"] == "UNKNOWN", f"Per-serving must not compare to per-100g. Got: {a['status']}"
    assert a["basis_warning"]

def _re_sodium_high():
    import risk_engine
    alerts = risk_engine.evaluate_quantitative_alerts(
        {"Sodium": {"value": 850.0, "unit": "mg", "serving_basis": "per 100g"}})
    a = next(x for x in alerts if x["nutrient"] == "Sodium")
    assert a["status"] == "HIGH"

def _re_sodium_g_ok():
    import risk_engine
    # 0.2g = 200mg → OK
    alerts = risk_engine.evaluate_quantitative_alerts(
        {"Sodium": {"value": 0.2, "unit": "g", "serving_basis": "per 100g"}})
    a = next(x for x in alerts if x["nutrient"] == "Sodium")
    assert a["status"] == "OK", f"200mg should be OK. Got: {a['status']}"

def _re_trans_high():
    import risk_engine
    alerts = risk_engine.evaluate_quantitative_alerts(
        {"Trans Fat": {"value": 3.0, "unit": "g", "serving_basis": "per 100g"}})
    a = next(x for x in alerts if x["nutrient"] == "Trans Fat")
    assert a["status"] == "HIGH"

def _re_trans_ok():
    import risk_engine
    alerts = risk_engine.evaluate_quantitative_alerts(
        {"Trans Fat": {"value": 0.0, "unit": "g", "serving_basis": "per 100g"}})
    a = next(x for x in alerts if x["nutrient"] == "Trans Fat")
    assert a["status"] == "OK"

def _re_sat_fat_levels():
    import risk_engine
    for val, expected in [(6.0, "HIGH"), (3.0, "MODERATE"), (1.0, "OK")]:
        alerts = risk_engine.evaluate_quantitative_alerts(
            {"Saturated Fat": {"value": val, "unit": "g", "serving_basis": "per 100g"}})
        a = next(x for x in alerts if x["nutrient"] == "Saturated Fat")
        assert a["status"] == expected, f"SatFat {val}g → {expected}, got {a['status']}"

def _re_all_6_present():
    import risk_engine
    alerts = risk_engine.evaluate_quantitative_alerts({})
    names = {a["nutrient"] for a in alerts}
    for n in ["Sugar","Saturated Fat","Trans Fat","Sodium","Salt","Total Fat"]:
        assert n in names, f"Missing: {n}"

check("Risk engine — Sugar 30g → HIGH", _re_sugar_high)
check("Risk engine — Sugar 10g → MODERATE", _re_sugar_moderate)
check("Risk engine — Sugar 3g → OK", _re_sugar_ok)
check("Risk engine — None value → UNKNOWN (not OK)", _re_unknown_none)
check("Risk engine — per-serving basis → UNKNOWN (not compared to per-100g)", _re_unknown_per_serving)
check("Risk engine — Sodium 850mg → HIGH", _re_sodium_high)
check("Risk engine — Sodium 0.2g (200mg) → OK", _re_sodium_g_ok)
check("Risk engine — Trans Fat 3g → HIGH", _re_trans_high)
check("Risk engine — Trans Fat 0g → OK", _re_trans_ok)
check("Risk engine — Saturated Fat HIGH/MODERATE/OK levels correct", _re_sat_fat_levels)
check("Risk engine — all 6 monitored nutrients appear even when undetected", _re_all_6_present)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12 — RISK ENGINE: INGREDIENT FLAGS
# ─────────────────────────────────────────────────────────────────────────────
def _ing_palm_oil():
    import risk_engine
    flags = risk_engine.evaluate_ingredient_flags(
        "Refined Wheat Flour, Sugar, Palm Oil, Salt, Raising Agent")
    names = [f["name"] for f in flags]
    assert "Palm Oil" in names

def _ing_hydro():
    import risk_engine
    flags = risk_engine.evaluate_ingredient_flags(
        "Vegetable Oil (Partially Hydrogenated), Sugar, Salt")
    names = [f["name"] for f in flags]
    assert any("Hydrogenated" in n or "Trans" in n for n in names)

def _ing_no_false_positive():
    import risk_engine
    flags = risk_engine.evaluate_ingredient_flags(
        "Whole Wheat Flour, Rolled Oats, Honey, Iodized Salt")
    for f in flags:
        assert "palm oil" not in [t.lower() for t in f["found_terms"]]

def _ing_empty():
    import risk_engine
    assert risk_engine.evaluate_ingredient_flags("") == []

def _ing_maida():
    import risk_engine
    flags = risk_engine.evaluate_ingredient_flags(
        "Refined Wheat Flour (Maida), Sugar, Salt")
    names = [f["name"] for f in flags]
    assert any("Maida" in n or "Refined" in n for n in names), f"Got: {names}"

def _ing_msg():
    import risk_engine
    flags = risk_engine.evaluate_ingredient_flags(
        "Wheat Flour, Salt, Monosodium Glutamate, Water")
    names = [f["name"] for f in flags]
    assert any("MSG" in n or "Glutamate" in n for n in names)

check("Ingredient flags — Palm Oil found → flag raised", _ing_palm_oil)
check("Ingredient flags — Partially Hydrogenated → trans fat flag raised", _ing_hydro)
check("Ingredient flags — clean text → no false palm-oil flag", _ing_no_false_positive)
check("Ingredient flags — empty text → empty list (no crash)", _ing_empty)
check("Ingredient flags — Maida/Refined Wheat Flour detected", _ing_maida)
check("Ingredient flags — MSG detected", _ing_msg)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 13 — RISK ENGINE: run_full_risk_analysis
# ─────────────────────────────────────────────────────────────────────────────
def _re_full_structure():
    import extractor, risk_engine
    n = extractor.extract_nutrition_values(SAMPLE_LABEL_TEXT)
    f = extractor.extract_product_fields(SAMPLE_LABEL_TEXT)
    result = risk_engine.run_full_risk_analysis(n, f.get("ingredients"))
    for key in ["quantitative_alerts","ingredient_flags","has_high_alerts",
                "has_moderate_alerts","has_ingredient_flags",
                "nutrition_available","ingredients_available"]:
        assert key in result, f"Missing key: {key}"
    assert isinstance(result["quantitative_alerts"], list)
    assert isinstance(result["has_high_alerts"], bool)

def _re_demo_pipeline():
    import extractor, risk_engine
    demo = extractor.get_demo_packet_data()
    risk = risk_engine.run_full_risk_analysis(
        demo["nutrients"], demo["fields"].get("ingredients"))
    quant = risk["quantitative_alerts"]
    sugar_a = next((a for a in quant if a["nutrient"] == "Sugar"), None)
    assert sugar_a and sugar_a["status"] in ("MODERATE","HIGH"), \
        f"Demo sugar 12.8g should be MODERATE or HIGH. Got: {sugar_a['status']}"
    # "Brown Sugar" is in demo ingredients → added sugar flag expected
    assert risk["has_ingredient_flags"] is True

def _re_ingredients_only_no_quant():
    """When only ingredients text is present (no nutrition values), quantitative
    alerts are all UNKNOWN but the function must not crash."""
    import risk_engine
    result = risk_engine.run_full_risk_analysis(
        {},  # no nutrients
        "Sugar, Palm Oil, Maida, Salt"
    )
    assert result["nutrition_available"] is False
    assert result["ingredients_available"] is True
    assert result["has_ingredient_flags"] is True
    # All quantitative alerts must be UNKNOWN
    for a in result["quantitative_alerts"]:
        assert a["status"] == "UNKNOWN"

def _re_neither_available():
    import risk_engine
    result = risk_engine.run_full_risk_analysis({}, None)
    assert result["nutrition_available"] is False
    assert result["ingredients_available"] is False
    assert result["ingredient_flags"] == []

check("Risk engine — run_full_risk_analysis returns complete structure", _re_full_structure)
check("Risk engine — demo packet: correct MODERATE sugar + ingredient flags", _re_demo_pipeline)
check("Risk engine — ingredients-only input: all quant UNKNOWN, ing flags work", _re_ingredients_only_no_quant)
check("Risk engine — no data at all: returns cleanly without crash", _re_neither_available)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 14 — INTEGRATION: extractor → risk_engine → nutrition_rules pipeline
# ─────────────────────────────────────────────────────────────────────────────
HIGH_RISK_LABEL = """
ULTRA PROCESSED SNACK
Brand: Test Corp
M.R.P.: Rs. 40.00
Mfg: 01/06/2026
Expiry: 01/12/2026

Ingredients: Maida, Vanaspati, Sugar, Salt, Tartrazine (INS 102), Sodium Benzoate (INS 211).

NUTRITIONAL INFORMATION (Per 100g)
Energy: 520 kcal
Total Carbohydrates: 65g
  of which Sugars: 35g
Total Fat: 26g
  Saturated Fat: 9g
  Trans Fat: 3g
Protein: 4g
Dietary Fibre: 0.5g
Sodium: 750mg
Salt: 1.9g
"""

def _pipeline_high_sugar():
    import extractor, risk_engine
    n = extractor.extract_nutrition_values(HIGH_RISK_LABEL)
    result = risk_engine.run_full_risk_analysis(n, None)
    alerts = result["quantitative_alerts"]
    sugar_a = next(a for a in alerts if a["nutrient"] == "Sugar")
    assert sugar_a["status"] == "HIGH", f"35g sugar should be HIGH. Got: {sugar_a['status']}"

def _pipeline_high_sodium():
    import extractor, risk_engine
    n = extractor.extract_nutrition_values(HIGH_RISK_LABEL)
    result = risk_engine.run_full_risk_analysis(n, None)
    na = next(a for a in result["quantitative_alerts"] if a["nutrient"] == "Sodium")
    assert na["status"] == "HIGH", f"750mg sodium should be HIGH. Got: {na['status']}"

def _pipeline_high_trans():
    import extractor, risk_engine
    n = extractor.extract_nutrition_values(HIGH_RISK_LABEL)
    result = risk_engine.run_full_risk_analysis(n, None)
    tf = next(a for a in result["quantitative_alerts"] if a["nutrient"] == "Trans Fat")
    assert tf["status"] == "HIGH", f"3g trans fat should be HIGH. Got: {tf['status']}"

def _pipeline_ingredient_flags_combined():
    import extractor, risk_engine
    f = extractor.extract_product_fields(HIGH_RISK_LABEL)
    n = extractor.extract_nutrition_values(HIGH_RISK_LABEL)
    result = risk_engine.run_full_risk_analysis(n, f.get("ingredients"))
    assert result["has_ingredient_flags"] is True
    flag_names = [x["name"] for x in result["ingredient_flags"]]
    # Vanaspati → partially hydrogenated flag
    assert any("Hydrogenated" in nm or "Trans" in nm for nm in flag_names), \
        f"Vanaspati should trigger trans fat flag. Got: {flag_names}"
    # Tartrazine → artificial colour flag
    assert any("Colour" in nm or "colour" in nm.lower() for nm in flag_names), \
        f"Tartrazine should trigger colour flag. Got: {flag_names}"

def _pipeline_missing_fields_no_crash():
    """App must not crash when fields dict has all-None values."""
    import extractor, nutrition_rules, risk_engine
    fields = extractor.extract_product_fields("")
    nutrients = extractor.extract_nutrition_values("")
    rows = nutrition_rules.compare_all_nutrients(nutrients)
    risk = risk_engine.run_full_risk_analysis(nutrients, fields.get("ingredients"))
    assert len(rows) == 11
    assert all(r["extracted_value"] == "Not detected" for r in rows)
    assert all(a["status"] == "UNKNOWN" for a in risk["quantitative_alerts"])

check("Pipeline — high-sugar label: Sugar 35g → HIGH", _pipeline_high_sugar)
check("Pipeline — high-sodium label: Sodium 750mg → HIGH", _pipeline_high_sodium)
check("Pipeline — high trans-fat label: Trans Fat 3g → HIGH", _pipeline_high_trans)
check("Pipeline — ingredient flags from real label text (vanaspati + tartrazine)", _pipeline_ingredient_flags_combined)
check("Pipeline — all-missing fields do not crash app or return wrong status", _pipeline_missing_fields_no_crash)


# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
passed = sum(1 for _, ok, _ in _results if ok)
failed = sum(1 for _, ok, _ in _results if not ok)
print(f"  Results: {passed} passed / {failed} failed / {len(_results)} total")
print("=" * 65)

if failed > 0:
    print("\nFailed tests:")
    for name, ok, reason in _results:
        if not ok:
            print(f"  ✗  {name}")
            print(f"     Reason: {reason}")
    sys.exit(1)
else:
    print("\n  All tests passed. Backend + Risk Engine verified.")
    sys.exit(0)
