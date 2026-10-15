"""
OCR module for Product Packet Analyser.
Handles integration with Tesseract OCR (pytesseract), automatic binary discovery,
multilingual recognition (English + Hindi), image quality pre-flight checks,
multi-pass page segmentation, layout preservation, and food content classification.
"""

import os
import re
import shutil
from typing import Dict, Any, List, Optional
from PIL import Image

# ── Try to import pytesseract ────────────────────────────────────────────────
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False


def _discover_tesseract_binary() -> Optional[str]:
    """
    Dynamically discovers the Tesseract executable path across Windows,
    Linux, and macOS installations.
    """
    # 1. User-specified environment variable
    env_path = os.environ.get("TESSERACT_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. System PATH
    which_path = shutil.which("tesseract")
    if which_path and os.path.isfile(which_path):
        return which_path

    # 3. Known Windows locations
    if os.name == "nt":
        windows_candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\tesseract\tesseract.exe",
        ]
        for candidate in windows_candidates:
            if candidate and os.path.isfile(candidate):
                return candidate
    else:
        linux_candidates = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",
        ]
        for candidate in linux_candidates:
            if candidate and os.path.isfile(candidate):
                return candidate

    return None


# Initialize Tesseract path
_TESSERACT_BIN = _discover_tesseract_binary()
if PYTESSERACT_AVAILABLE and _TESSERACT_BIN:
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_BIN

    # Set TESSDATA_PREFIX automatically if not already configured in environment
    if "TESSDATA_PREFIX" not in os.environ:
        tessdata_dir = os.path.join(os.path.dirname(_TESSERACT_BIN), "tessdata")
        if os.path.isdir(tessdata_dir):
            os.environ["TESSDATA_PREFIX"] = tessdata_dir


def check_ocr_availability() -> Dict[str, Any]:
    """
    Checks if pytesseract and the Tesseract binary are available and configured.
    """
    global _TESSERACT_BIN
    if not PYTESSERACT_AVAILABLE:
        return {
            "available": False,
            "engine": "Tesseract OCR",
            "message": (
                "The Python package 'pytesseract' is not installed.\n"
                "Install via: pip install pytesseract"
            )
        }

    # Re-check binary discovery if not yet found
    if not _TESSERACT_BIN:
        _TESSERACT_BIN = _discover_tesseract_binary()
        if _TESSERACT_BIN:
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT_BIN

    try:
        version = pytesseract.get_tesseract_version()
        available_langs = []
        try:
            available_langs = pytesseract.get_languages()
        except Exception:
            available_langs = ["eng"]

        return {
            "available": True,
            "engine": f"Tesseract OCR v{version}",
            "languages": available_langs,
            "binary_path": _TESSERACT_BIN or pytesseract.pytesseract.tesseract_cmd,
            "message": "OCR engine is ready and active."
        }
    except pytesseract.TesseractNotFoundError:
        return {
            "available": False,
            "engine": "Tesseract OCR",
            "message": (
                "Tesseract OCR executable was not found.\n"
                "Please install Tesseract OCR from https://github.com/UB-Mannheim/tesseract/wiki\n"
                "or set TESSERACT_PATH environment variable."
            ),
        }
    except Exception as exc:
        return {
            "available": False,
            "engine": "Tesseract OCR",
            "message": f"Error verifying Tesseract OCR: {exc}"
        }


# ── OCR text normalisation & line repair ──────────────────────────────────────

def _clean_ocr_text(raw: str) -> str:
    """
    Cleans raw OCR output to fix common character confusions that break regex extraction.
    Preserves line breaks and structural layout.
    """
    if not raw:
        return raw

    # 1. Normalise line endings
    text = raw.replace('\r\n', '\n').replace('\r', '\n')

    # 2. Collapse excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 3. Nutrition line repair (e.g. fused unit digits like "289" -> "28g")
    repaired_lines = []
    for line in text.splitlines():
        repaired_lines.append(_repair_nutrition_line(line))
    text = '\n'.join(repaired_lines)

    # 4. Keyword corrections
    text = re.sub(r'\bMig\b', 'Mfg', text)
    text = re.sub(r'\bMig\.\b', 'Mfg.', text)
    text = re.sub(r'\bMtg\b', 'Mfg', text)
    text = re.sub(r'\bDale\b', 'Date', text)
    text = re.sub(r'\bBes[t!]\b', 'Best', text)

    # Heading corrections
    text = re.sub(r'Ingredbents?\s*:', 'Ingredients:', text, flags=re.IGNORECASE)
    text = re.sub(r'Ingredien[st]s?\s*:', 'Ingredients:', text, flags=re.IGNORECASE)
    text = re.sub(r'Ingredien[ct]s?\s*:', 'Ingredients:', text, flags=re.IGNORECASE)
    text = re.sub(r'Nutritienal\s+', 'Nutritional ', text, flags=re.IGNORECASE)

    # Currency corrections
    text = re.sub(r'\bPs\.?\s*', 'Rs. ', text)
    text = re.sub(r'\bMRP:\s*Ps', 'MRP: Rs.', text, flags=re.IGNORECASE)

    # Filter control characters while preserving printable UTF-8 (including Hindi & currency symbols)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    return text.strip()


def _repair_nutrition_line(line: str) -> str:
    """
    Repairs a single nutrition-table line where Tesseract fused the unit letter 'g'
    into the digit '9' or '0' (e.g. "Total Carbohydrates: 689" -> "68g").
    """
    nutrition_keywords = re.compile(
        r'\b(energy|calorie|carbohydrate|carbs?|sugar|fat|saturated|trans|protein|'
        r'fibre|fiber|sodium|salt|dietary)\b',
        re.IGNORECASE
    )
    if not nutrition_keywords.search(line):
        return line

    if re.search(r'\b(kcal|kj|cal)\b', line, re.IGNORECASE):
        return line

    def fix_fused_unit(m):
        full_num_str = m.group(0)
        last_char = full_num_str[-1]
        core_num_str = full_num_str[:-1]

        try:
            core_val = float(core_num_str)
            full_val = float(full_num_str)
        except ValueError:
            return full_num_str

        # e.g. "689" -> core 68 <= 100 and full 689 > 100
        if last_char == '9' and core_val <= 100.0 and full_val > 100.0:
            return core_num_str + 'g'

        # Decimal fused unit e.g. "6.59" -> core 6.5
        if '.' in core_num_str and last_char == '9':
            parts = core_num_str.split('.')
            if len(parts) == 2 and len(parts[1]) == 1:
                return core_num_str + 'g'

        return full_num_str

    repaired = re.sub(
        r'\b(\d+(?:\.\d+)?)\b(?!\s*(?:g|mg|ml|kcal|kj|%|gm))',
        fix_fused_unit,
        line
    )
    return repaired


# ── Content classification: Packaged Food vs Recipe vs Receipt vs Unrelated ──

def classify_content_type(text: str) -> Dict[str, Any]:
    """
    Determines whether OCR text is from a commercial food package label,
    a cooking recipe, a sales receipt/bill, or unrelated text.
    """
    if not text or not text.strip():
        return {
            "content_type": "empty",
            "is_package": False,
            "confidence": 0.0,
            "reason": "No readable text extracted.",
        }

    text_lower = text.lower()

    # Package label indicator patterns
    pkg_indicators = [
        r'\bingredients?\b',
        r'\bnutrition(?:al)?\s+(?:information|facts|values?)\b',
        r'\bm\.?r\.?p\.?\b',
        r'\bmfg(?:\.?|\s+date)\b',
        r'\bmfd(?:\.?|\s+date)\b',
        r'\bpkd(?:\.?|\s+date)\b',
        r'\bexp(?:iry)?(?:\.?|\s+date)\b',
        r'\bbest\s+before\b',
        r'\bnet\s+(?:wt|weight|qty|quantity)\b',
        r'\bserving\s+size\b',
        r'\bper\s+100\s*(?:g|ml)\b',
        r'\bfssai\b',
        r'\blic(?:ense)?\s*no\b',
        r'\bbatch\s*no\b',
    ]
    pkg_score = sum(1 for p in pkg_indicators if re.search(p, text_lower))

    # Recipe indicator patterns
    recipe_indicators = [
        r'\brecipe\b',
        r'\bprep(?:\.?|\s+time)\b',
        r'\bcook\s+time\b',
        r'\btotal\s+time\b',
        r'\bservings?\s*:\s*\d+\s*(?:people|portions|servings)?\b',
        r'\byield\s*:\b',
        r'\bdirections\b',
        r'\binstructions\b',
        r'\bmethod\b',
        r'\bstep\s*\d+\b',
        r'\bpreheat\s+(?:the\s+)?oven\b',
        r'\bbake\s+(?:at|for)\b',
        r'\bwhisk\s+(?:together|in|the)\b',
        r'\btablespoons?\b',
        r'\bteaspoons?\b',
        r'\btbsp\b',
        r'\btsp\b',
        r'\bcups?\s+of\b',
    ]
    recipe_score = sum(1 for p in recipe_indicators if re.search(p, text_lower))

    # Receipt indicator patterns
    receipt_indicators = [
        r'\btax\s+invoice\b',
        r'\bcash\s+receipt\b',
        r'\bbill\s+to\b',
        r'\bsubtotal\b',
        r'\bpos\s+(?:system|receipt)\b',
        r'\bpayment\s+mode\b',
        r'\bchange\s+due\b',
    ]
    receipt_score = sum(1 for p in receipt_indicators if re.search(p, text_lower))

    if recipe_score >= 3 and recipe_score > pkg_score:
        return {
            "content_type": "recipe",
            "is_package": False,
            "confidence": min(1.0, 0.4 + 0.15 * recipe_score),
            "reason": (
                "Text contains recipe structure (cooking directions, prep time, "
                "or culinary measurements). It is not a commercial product package label."
            ),
        }

    if receipt_score >= 2 and receipt_score > pkg_score:
        return {
            "content_type": "receipt",
            "is_package": False,
            "confidence": min(1.0, 0.4 + 0.2 * receipt_score),
            "reason": "Text appears to be a sales receipt or invoice, not a product food label.",
        }

    if pkg_score >= 2:
        return {
            "content_type": "packaged_food",
            "is_package": True,
            "confidence": min(1.0, 0.3 + 0.15 * pkg_score),
            "reason": "Identified standard commercial packaged food labelling markers.",
        }

    # Weak or ambiguous content
    return {
        "content_type": "unrelated",
        "is_package": False,
        "confidence": 0.2,
        "reason": "Text does not contain recognizable food packaging markers (ingredients, nutrition facts, or dates).",
    }


# ── Core OCR execution ────────────────────────────────────────────────────────

def extract_raw_text(image: Image.Image) -> Dict[str, Any]:
    """
    Runs Tesseract OCR on a PIL Image with multilingual support (eng+hin),
    multi-PSM execution, layout preservation, and content classification.

    Returns:
      {
        "success": bool,
        "text": str,
        "raw_text": str,
        "classification": dict,
        "quality": dict,
        "error_message": str or None,
        "warnings": list[str]
      }
    """
    from backend import image_utils

    # 1. Image quality assessment
    quality = image_utils.assess_image_quality(image)
    warnings = []
    if quality.get("warning"):
        warnings.append(quality["warning"])

    status = check_ocr_availability()
    if not status["available"]:
        return {
            "success": False,
            "text": "",
            "raw_text": "",
            "classification": {"content_type": "error", "is_package": False, "confidence": 0.0},
            "quality": quality,
            "error_message": status["message"],
            "warnings": warnings,
        }

    # Severe blur check
    if quality.get("is_blurry") and quality.get("blur_score", 100.0) < 15.0:
        return {
            "success": False,
            "text": "",
            "raw_text": "",
            "classification": {"content_type": "unreadable", "is_package": False, "confidence": 0.0},
            "quality": quality,
            "error_message": (
                "The image is too blurry to read food label text reliably "
                f"(sharpness score: {quality.get('blur_score')}). "
                "Please hold the camera steady and capture a clearer photograph."
            ),
            "warnings": warnings,
        }

    # 2. Configure languages (English + Hindi if available)
    available_langs = status.get("languages", ["eng"])
    ocr_lang = "eng+hin" if "hin" in available_langs else "eng"

    candidates = []

    # Passes:
    # PSM 6: Uniform block of text (ideal for structured nutrition tables)
    # PSM 4: Single column of variable sizes (ideal for ingredient blocks)
    # PSM 3: Fully automatic page segmentation (ideal for complex packaging)
    # PSM 11: Sparse text
    for psm in (6, 4, 3, 11):
        config = f"--oem 3 --psm {psm} -c preserve_interword_spaces=1"
        try:
            txt = pytesseract.image_to_string(image, config=config, lang=ocr_lang)
            txt = txt.strip()
            if txt:
                candidates.append((len(txt), psm, txt))
        except Exception:
            # Fallback to English only if multilingual failed
            if ocr_lang != "eng":
                try:
                    txt = pytesseract.image_to_string(image, config=config, lang="eng")
                    txt = txt.strip()
                    if txt:
                        candidates.append((len(txt), psm, txt))
                except Exception:
                    pass

    # If first round yielded very little text, try soft preprocessed variant
    if not candidates or max(c[0] for c in candidates) < 40:
        soft_img = image_utils.preprocess_image_for_ocr_soft(image)
        for psm in (6, 3):
            config = f"--oem 3 --psm {psm} -c preserve_interword_spaces=1"
            try:
                txt = pytesseract.image_to_string(soft_img, config=config, lang=ocr_lang)
                txt = txt.strip()
                if txt:
                    candidates.append((len(txt), psm, txt))
            except Exception:
                pass

    if not candidates:
        return {
            "success": False,
            "text": "",
            "raw_text": "",
            "classification": {"content_type": "empty", "is_package": False, "confidence": 0.0},
            "quality": quality,
            "error_message": (
                "OCR could not detect readable packaging text in this photograph.\n\n"
                "Recommendations:\n"
                "• Ensure packaging text is oriented right-side up.\n"
                "• Avoid harsh lighting reflections or deep shadows.\n"
                "• Frame the label closely so text is sharp and legible."
            ),
            "warnings": warnings,
        }

    # Select the richest text result
    best_raw = max(candidates, key=lambda c: c[0])[2]
    cleaned = _clean_ocr_text(best_raw)

    if not cleaned.strip():
        return {
            "success": False,
            "text": "",
            "raw_text": best_raw,
            "classification": {"content_type": "noise", "is_package": False, "confidence": 0.0},
            "quality": quality,
            "error_message": "OCR output contained only noise or unreadable characters.",
            "warnings": warnings,
        }

    classification = classify_content_type(cleaned)
    if classification["content_type"] == "recipe":
        warnings.append(
            "Note: The image appears to be a recipe rather than a commercial product label."
        )

    return {
        "success": True,
        "text": cleaned,
        "raw_text": best_raw,
        "classification": classification,
        "quality": quality,
        "error_message": None,
        "warnings": warnings,
    }
