"""
Image processing utilities for Product Packet Analyser.
Provides image loading, validation, metadata extraction, and a robust OpenCV
preprocessing pipeline tuned for real smartphone food-label photos.
"""

from io import BytesIO
from typing import Dict, Any, Tuple, Optional
from PIL import Image

SUPPORTED_EXTENSIONS = ["jpg", "jpeg", "png"]
MAX_FILE_SIZE_MB = 10


def validate_image_file(uploaded_file) -> Tuple[bool, str]:
    """
    Validates uploaded file format and size.
    Returns (is_valid, error_message).
    """
    if uploaded_file is None:
        return False, "No file provided."

    file_name = uploaded_file.name.lower()
    ext = file_name.split(".")[-1] if "." in file_name else ""
    if ext not in SUPPORTED_EXTENSIONS:
        return False, f"Unsupported format (.{ext}). Supported formats: JPG, JPEG, PNG."

    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return False, f"File size ({file_size_mb:.2f} MB) exceeds the {MAX_FILE_SIZE_MB} MB limit."

    try:
        uploaded_file.seek(0)
        test_img = Image.open(uploaded_file)
        test_img.verify()
    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return False, "The file appears corrupted or is not a valid image."
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    return True, ""


def load_image(uploaded_file) -> Optional[Image.Image]:
    """
    Safely opens uploaded image file using Pillow.
    Always resets the stream before reading.
    """
    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        if image.mode in ("RGBA", "P", "LA", "L"):
            image = image.convert("RGB")
        return image
    except Exception:
        return None


def get_image_metadata(image: Image.Image, file_name: str, file_size_bytes: int) -> Dict[str, Any]:
    """Returns basic image metadata for display."""
    width, height = image.size
    size_kb = file_size_bytes / 1024
    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{(size_kb / 1024):.2f} MB"
    return {
        "filename": file_name,
        "resolution": f"{width} × {height} px",
        "format": image.format or "JPEG/PNG",
        "mode": image.mode,
        "filesize": size_str
    }


def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    """
    Multi-stage OpenCV preprocessing pipeline for real food-label photos.

    Pipeline (in order):
      1. Upscale to minimum 1600px on the long edge (characters need to be large).
      2. Greyscale conversion.
      3. CLAHE (Contrast Limited Adaptive Histogram Equalization) to fix
         uneven lighting and low-contrast sections without blowing out text.
      4. Mild Gaussian blur to reduce sensor noise.
      5. Adaptive Gaussian thresholding with a generous block size to handle
         curved surfaces and shadows.
      6. Morphological closing to reconnect broken character strokes.

    Falls back to the original image if OpenCV is not installed.
    Always returns a PIL Image.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return image

    try:
        img_np = np.array(image.convert("RGB"))
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # ── Step 1: Upscale ──────────────────────────────────────────────────
        h, w = img_bgr.shape[:2]
        target_long_edge = 1800
        if max(h, w) < target_long_edge:
            scale = target_long_edge / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img_bgr = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

        # ── Step 2: Greyscale ────────────────────────────────────────────────
        grey = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # ── Step 3: CLAHE for contrast normalisation ─────────────────────────
        # clipLimit=2.0 and tileGridSize=(8,8) work well for food labels
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        grey = clahe.apply(grey)

        # ── Step 4: Mild Gaussian blur to reduce noise ───────────────────────
        denoised = cv2.GaussianBlur(grey, (3, 3), 0)

        # ── Step 5: Adaptive thresholding ────────────────────────────────────
        # blockSize=41 for large images; C=15 to suppress background noise
        binary = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            41,
            15
        )

        # ── Step 6: Morphological closing to fix broken character strokes ────
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        return Image.fromarray(cleaned)

    except Exception:
        return image


def preprocess_image_for_ocr_soft(image: Image.Image) -> Image.Image:
    """
    Lighter preprocessing variant — greyscale + mild sharpen only.
    Used as a fallback when aggressive thresholding hurts readability
    (e.g. for images that already have very clean contrast).
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return image

    try:
        img_np = np.array(image.convert("RGB"))
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        h, w = img_bgr.shape[:2]
        if max(h, w) < 1600:
            scale = 1600 / max(h, w)
            img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)),
                                  interpolation=cv2.INTER_CUBIC)

        grey = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # Sharpen with unsharp mask
        blurred = cv2.GaussianBlur(grey, (0, 0), 3)
        sharpened = cv2.addWeighted(grey, 1.5, blurred, -0.5, 0)

        return Image.fromarray(sharpened)
    except Exception:
        return image
