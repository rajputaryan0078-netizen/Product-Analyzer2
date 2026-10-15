"""
OCR module for Product Packet Analyser.
Handles integration with Tesseract OCR (pytesseract).

Windows path configuration:
  Tesseract 5.5.3 is installed at C:\\Program Files\\Tesseract-OCR\\tesseract.exe
  We set the path explicitly so it works regardless of PATH configuration.

OCR strategy:
  - Run multiple PSM passes (6, 4, 11) and pick the richest result.
  - Clean the raw OCR text to fix common character confusions before returning.

Critical rule: never fabricate OCR text. On failure, return success=False.
"""

import os
import re
from typing import Dict, Any
from PIL import Image

# ── Try to import pytesseract ────────────────────────────────────────────────
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

# ── Set Tesseract executable path explicitly ─────────────────────────────────
_WINDOWS_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\pc#\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    r"C:\tesseract\tesseract.exe",
]

if PYTESSERACT_AVAILABLE and os.name == "nt":
    for _candidate in _WINDOWS_TESSERACT_PATHS:
        if os.path.isfile(_candidate):
            pytesseract.pytesseract.tesseract_cmd = _candidate
            break


# ── OCR text normalisation ───────────────────────────────────────────────────

def _clean_ocr_text(raw: str) -> str:
    """
    Cleans raw OCR output to fix common confusions that break regex extraction.

    Rules applied (conservative — only when context is clear):
    - Collapse 3+ blank lines to 2.
    - Fix fused number+unit: "28g" OCR'd as "289" → restore the 'g' so
      downstream regex can match it.  Pattern: a digit sequence ending in
      9/0 that appears on a nutrition-table line gets a space+g appended
      when the last char was likely a fused 'g'.
    - 'Rs.' and common currency OCR errors.
    - Common label keyword fixes (Mig→Mfg, Ingredbents→Ingredients, etc.)
    """
    if not raw:
        return raw

    # ── 1. Normalise line endings ────────────────────────────────────────────
    text = raw.replace('\r\n', '\n').replace('\r', '\n')

    # ── 2. Collapse excessive blank lines ───────────────────────────────────
    text = re.sub(r'\n{3,}', '\n\n', text)

    # ── 3. Fix fused numeric unit: e.g. "489" where last digit is OCR'd 'g'
    #   This is the main cause of wrong nutrition values.
    #   Context: lines that contain kcal/energy/fat/protein/carb/sugar/sodium/salt
    #   Pattern: <digits><optional decimal><optional space><fused-9-or-0>
    #   We only apply this on lines that look like nutrition rows.
    #
    #   Strategy: for each line, if it matches a nutrition label pattern and
    #   the value ends with a digit followed by what should be a unit letter
    #   (OCR as 9 for g, or as 0 for o), we insert a space and the unit.
    #
    #   IMPORTANT: only do this when the number would be unreasonably large
    #   if taken at face value (e.g. 689 kcal is plausible, but 689g fat
    #   is not — however we can't know that without context).
    #   Instead: use a simpler heuristic: on nutrition lines where the OCR
    #   likely fused a 'g' suffix, the number ends in '9' (g→9 is the most
    #   common Tesseract confusion) or the unit is absent.
    #
    # Approach: run nutrition-specific line repair.
    repaired_lines = []
    for line in text.splitlines():
        repaired_lines.append(_repair_nutrition_line(line))
    text = '\n'.join(repaired_lines)

    # ── 4. Fix common keyword OCR errors ───────────────────────────────────
    # Manufacturing date keywords
    text = re.sub(r'\bMig\b', 'Mfg', text)
    text = re.sub(r'\bMig\.\b', 'Mfg.', text)
    text = re.sub(r'\bMtg\b', 'Mfg', text)
    text = re.sub(r'\bMfd\b', 'Mfd', text)  # keep as-is (correct)
    text = re.sub(r'\bDale\b', 'Date', text)
    text = re.sub(r'\bDale:\b', 'Date:', text)

    # Expiry / best before
    text = re.sub(r'\bBes[t!]\b', 'Best', text)
    text = re.sub(r'\bBefore\b', 'Before', text)  # keep
    text = re.sub(r'\bExpiry\b', 'Expiry', text)
    text = re.sub(r'\bExp\b', 'Exp', text)

    # Ingredient heading
    text = re.sub(r'Ingredbents?\s*:', 'Ingredients:', text, flags=re.IGNORECASE)
    text = re.sub(r'Ingredien[st]s?\s*:', 'Ingredients:', text, flags=re.IGNORECASE)
    text = re.sub(r'Ingredien[ct]s?\s*:', 'Ingredients:', text, flags=re.IGNORECASE)

    # MRP / price
    text = re.sub(r'\bPs\.?\s*', 'Rs. ', text)   # Ps → Rs.
    text = re.sub(r'\bMRP:\s*Ps', 'MRP: Rs.', text, flags=re.IGNORECASE)

    # Common letter confusions in ingredient names (conservative)
    text = re.sub(r'\bOnl\b', 'Oil', text)        # Onl → Oil
    text = re.sub(r'\bSail\b', 'Salt', text)      # Sail → Salt
    text = re.sub(r'\bMardal\b', 'Maida', text)   # Mardal → Maida
    text = re.sub(r'\bHydrogenaled\b', 'Hydrogenated', text)
    text = re.sub(r'\bCocea\b', 'Cocoa', text)
    text = re.sub(r'\bCocca\b', 'Cocoa', text)

    # ── 5. Remove stray box-drawing or non-ASCII garbage characters ──────────
    # Keep: printable ASCII + common Indian currency ₹ + basic punctuation
    text = re.sub(r'[^\x20-\x7E₹\n]', ' ', text)
    text = re.sub(r' {3,}', '  ', text)

    return text.strip()


def _repair_nutrition_line(line: str) -> str:
    """
    Repairs a single nutrition-table line where Tesseract has fused the unit
    letter into the number digit.

    Most common confusions on food labels:
      - 'g' read as '9' (e.g. "28g" → "289")
      - 'g' read as '0' less often
      - 'ml' read as 'm1' or 'mi'
      - 'kcal' usually survives intact

    Strategy:
      If the line looks like a nutrition row (contains a nutrient keyword)
      AND the numeric value on that line ends with '9' or '0' with no unit
      following it, AND the value would be unreasonably large for that nutrient,
      we strip the last digit and append 'g'.

    Example:
      "Total Carbohydrates: 689" → value would be 689g carbs — unreasonable.
      Strip trailing '9', leaving "68", append "g" → "Total Carbohydrates: 68g"

    Threshold for "unreasonable": > 100 for nutrients measured in grams
    (since per-100g values can't exceed 100g).  Energy (kcal) can be > 100
    so we don't repair kcal lines.

    This is conservative: we only repair when the corrected value makes sense.
    """
    # Only repair lines that look like nutrition entries
    nutrition_keywords = re.compile(
        r'\b(energy|calorie|carbohydrate|carbs?|sugar|fat|saturated|trans|protein|'
        r'fibre|fiber|sodium|salt|dietary)\b',
        re.IGNORECASE
    )
    if not nutrition_keywords.search(line):
        return line

    # Skip lines with 'kcal' or 'kj' — energy values can legitimately be large
    if re.search(r'\b(kcal|kj|cal)\b', line, re.IGNORECASE):
        return line

    # Look for a number ending in 9 or 0 with no unit after it
    # Pattern: word boundary, digits, optional decimal, ending digit, end-of-token
    def fix_fused_unit(m):
        full_num_str = m.group(0)
        last_char = full_num_str[-1]
        core_num_str = full_num_str[:-1]  # strip the potentially-fused char

        try:
            core_val = float(core_num_str)
        except ValueError:
            return full_num_str

        try:
            full_val = float(full_num_str)
        except ValueError:
            return full_num_str

        # Case 1: integer fused 'g' — "689" where core=68, full=689
        # Condition: last char is '9', core ≤ 100, full > 100
        if last_char == '9' and core_val <= 100.0 and full_val > 100.0:
            return core_num_str + 'g'

        # Case 2: decimal fused 'g' — "6.59" where core=6.5, full=6.59
        # Pattern: number has a decimal point, last digit is '9',
        # and core (without last digit) is a "nicer" number like X.5, X.0, X.2
        # Condition: '.' in core_num_str and last char is '9'
        if '.' in core_num_str and last_char == '9':
            # Only repair when the core ends in a single decimal digit
            # (e.g. 6.5 not 6.52) — avoids false positives
            parts = core_num_str.split('.')
            if len(parts) == 2 and len(parts[1]) == 1:
                return core_num_str + 'g'

        return full_num_str

    # Apply to numbers that end without a unit suffix (no g/mg/ml after them)
    repaired = re.sub(
        r'\b(\d+(?:\.\d+)?)\b(?!\s*(?:g|mg|ml|kcal|kj|%|gm))',
        fix_fused_unit,
        line
    )
    return repaired


def check_ocr_availability() -> Dict[str, Any]:
    """
    Checks if pytesseract and the Tesseract binary are both available.
    """
    if not PYTESSERACT_AVAILABLE:
        return {
            "available": False,
            "engine": "Tesseract OCR",
            "message": (
                "The Python package 'pytesseract' is not installed.\n\n"
                "Fix: open a terminal in your project folder and run:\n"
                "  pip install pytesseract opencv-python\n\n"
                "You also need the Tesseract application installed separately — "
                "see README.md for the download link."
            )
        }

    try:
        version = pytesseract.get_tesseract_version()
        return {
            "available": True,
            "engine": f"Tesseract OCR v{version}",
            "message": "OCR engine is ready and active."
        }
    except pytesseract.TesseractNotFoundError:
        return {
            "available": False,
            "engine": "Tesseract OCR",
            "message": (
                "Tesseract OCR is not installed or could not be found.\n\n"
                "Windows installation steps:\n"
                "1. Download the installer from:\n"
                "   https://github.com/UB-Mannheim/tesseract/wiki\n"
                "   (choose tesseract-ocr-w64-setup-5.x.x.exe for 64-bit Windows)\n"
                "2. Run the installer — keep the default install path:\n"
                "   C:\\Program Files\\Tesseract-OCR\\\n"
                "3. Restart your terminal / VS Code after installation.\n\n"
                "You can still use 'Sample Demo Packet' on the landing page to see\n"
                "the full analysis flow without Tesseract installed."
            )
        }
    except Exception as exc:
        return {
            "available": False,
            "engine": "Tesseract OCR",
            "message": f"Unexpected error checking Tesseract: {exc}"
        }


def extract_raw_text(image: Image.Image) -> Dict[str, Any]:
    """
    Runs Tesseract OCR on a PIL Image and returns the cleaned extracted text.

    Strategy:
    - Try PSM 6 (uniform block), PSM 4 (single column), PSM 11 (sparse text).
    - Select the result with the most characters.
    - Apply _clean_ocr_text() to fix systematic OCR confusions.
    - Return the cleaned text plus the truly-raw text for debugging.

    Returns:
      {
        "success":       bool,
        "text":          str,   # cleaned OCR output
        "raw_text":      str,   # unmodified OCR output for debugging
        "error_message": str or None
      }
    """
    status = check_ocr_availability()
    if not status["available"]:
        return {
            "success": False,
            "text": "",
            "raw_text": "",
            "error_message": status["message"]
        }

    try:
        results = []
        # PSM 6: uniform block of text (good for structured tables)
        # PSM 4: single column (good for ingredient paragraphs)
        # PSM 11: sparse text (good for varied layouts)
        # OEM 3: LSTM engine (most accurate for printed text)
        for psm in (6, 4, 11, 3):
            config = f"--oem 3 --psm {psm}"
            try:
                text = pytesseract.image_to_string(image, config=config, lang="eng")
                text = text.strip()
                if text:
                    results.append(text)
            except Exception:
                continue

        if not results:
            return {
                "success": False,
                "text": "",
                "raw_text": "",
                "error_message": (
                    "OCR processed the image but could not extract any readable text.\n\n"
                    "Tips for better results:\n"
                    "• Use a well-lit, sharp photo with the label filling most of the frame.\n"
                    "• Avoid glare, shadows, and extreme angles.\n"
                    "• Minimum recommended resolution: 1000 × 800 px.\n"
                    "• Hold the phone/camera steady and as parallel to the label as possible."
                )
            }

        # Pick the longest result (most text extracted)
        best_raw = max(results, key=len)
        cleaned = _clean_ocr_text(best_raw)

        if not cleaned.strip():
            return {
                "success": False,
                "text": "",
                "raw_text": best_raw,
                "error_message": "OCR returned text that was entirely noise after cleaning."
            }

        return {
            "success": True,
            "text": cleaned,
            "raw_text": best_raw,
            "error_message": None
        }

    except Exception as exc:
        return {
            "success": False,
            "text": "",
            "raw_text": "",
            "error_message": f"An unexpected error occurred during OCR: {exc}"
        }
