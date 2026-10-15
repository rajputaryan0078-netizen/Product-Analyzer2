"""
Pipeline diagnostic script.
Checks Tesseract, preprocessing, OCR, extraction, and risk engine
using a synthetic label image generated in-memory (no uploaded file needed).
"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 1. Tesseract availability ────────────────────────────────────────────────
import ocr_utils
diag = ocr_utils.check_ocr_availability()
print("=" * 60)
print("1. TESSERACT AVAILABILITY")
print(f"   available : {diag['available']}")
print(f"   engine    : {diag['engine']}")
if not diag['available']:
    print(f"   message   : {diag['message'][:300]}")

# ── 2. Test OCR on a simple synthetic label image ────────────────────────────
from PIL import Image, ImageDraw, ImageFont
import io

def make_synthetic_label():
    """
    Creates a white 800x600 image with realistic food-label text.
    Used as a known-good test input when no real photo is available.
    """
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    label_lines = [
        "SUNFEAST DARK FANTASY CHOCO FILLS",
        "Brand: ITC Limited",
        "Net Weight: 300g",
        "M.R.P.: Rs. 80.00",
        "Mfg Date: 01/03/2026",
        "Best Before: 6 months from date of manufacture",
        "Serving Size: 25g",
        "",
        "Ingredients: Refined Wheat Flour (Maida), Sugar,",
        "Hydrogenated Vegetable Oil, Cocoa Powder (3.5%),",
        "Invert Syrup, Salt, Raising Agent (INS 503).",
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
    import image_utils
    processed = image_utils.preprocess_image_for_ocr(synthetic_img)
    ocr_result = ocr_utils.extract_raw_text(processed)
    print(f"   OCR success: {ocr_result['success']}")
    if ocr_result['success']:
        print(f"   OCR text length: {len(ocr_result['text'])} chars")
        print("   First 300 chars of OCR output:")
        print("   " + ocr_result['text'][:300].replace('\n', '\n   '))
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
M.R.P.: Rs. 80.00
Mfg Date: 01/03/2026
Best Before: 6 months from date of manufacture
Serving Size: 25g

Ingredients: Refined Wheat Flour (Maida), Sugar, Hydrogenated Vegetable Oil,
Cocoa Powder (3.5%), Invert Syrup, Salt, Raising Agent (INS 503).

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

import extractor
fields = extractor.extract_product_fields(SYNTHETIC_TEXT)
nutrients = extractor.extract_nutrition_values(SYNTHETIC_TEXT)

print(f"   product_name : {fields['product_name']}")
print(f"   brand_name   : {fields['brand_name']}")
print(f"   mrp          : {fields['mrp']}")
print(f"   mfg_date     : {fields['mfg_date']}")
print(f"   best_before  : {fields['best_before']}")
print(f"   serving_size : {fields['serving_size']}")
print(f"   ingredients  : {str(fields['ingredients'])[:80]}")
print("   Nutrients:")
for name, data in nutrients.items():
    print(f"     {name:20s}: value={data['value']}, unit={data['unit']}, basis={data['serving_basis']}")

# ── 4. Test risk engine ───────────────────────────────────────────────────────
print("\n4. RISK ENGINE")
import risk_engine
risk = risk_engine.run_full_risk_analysis(nutrients, fields.get("ingredients"))
print(f"   nutrition_available   : {risk['nutrition_available']}")
print(f"   ingredients_available : {risk['ingredients_available']}")
print(f"   has_high_alerts       : {risk['has_high_alerts']}")
print(f"   quantitative alerts:")
for a in risk['quantitative_alerts']:
    print(f"     {a['nutrient']:20s}: {a['status']:10s}  value={a['value_display']}")
print(f"   ingredient flags: {[f['name'] for f in risk['ingredient_flags']]}")

# ── 5. Test the actual OCR path if Tesseract available ───────────────────────
if diag['available'] and ocr_result['success']:
    print("\n5. EXTRACTION FROM ACTUAL OCR OUTPUT")
    fields_ocr = extractor.extract_product_fields(ocr_result['text'])
    nutrients_ocr = extractor.extract_nutrition_values(ocr_result['text'])
    detected = {k: v for k, v in fields_ocr.items() if v}
    detected_n = {k: v['value'] for k, v in nutrients_ocr.items() if v['value'] is not None}
    print(f"   Fields detected    : {list(detected.keys())}")
    print(f"   Nutrients detected : {detected_n}")
else:
    print("\n5. EXTRACTION FROM ACTUAL OCR OUTPUT: SKIPPED (OCR unavailable)")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
