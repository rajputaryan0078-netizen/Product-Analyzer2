"""
Image processing utilities for Product Packet Analyser.
Provides image loading, validation, metadata extraction, quality assessment
(blurriness, exposure), orientation correction, deskewing, and a robust
multi-stage OpenCV preprocessing pipeline tuned for real smartphone food-label photos.
"""

from io import BytesIO
from typing import Dict, Any, Tuple, Optional
from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
MAX_FILE_SIZE_MB = 15
MIN_IMAGE_DIMENSION = 50
BLUR_THRESHOLD_VAR = 25.0  # Laplacian variance below this indicates severe blur


def validate_image_file(uploaded_file) -> Tuple[bool, str]:
    """
    Validates uploaded file format, size, and image integrity.
    Supports JPG, JPEG, PNG, and WebP up to 15MB.
    Returns (is_valid, error_message).
    """
    if uploaded_file is None:
        return False, "No file provided."

    file_name = getattr(uploaded_file, "name", "").lower()
    ext = file_name.split(".")[-1] if "." in file_name else ""
    if ext not in SUPPORTED_EXTENSIONS:
        return False, (
            f"Unsupported format (.{ext}). Supported formats: "
            f"{', '.join(ext.upper() for ext in SUPPORTED_EXTENSIONS)}."
        )

    file_size_bytes = getattr(uploaded_file, "size", 0)
    file_size_mb = file_size_bytes / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return False, f"File size ({file_size_mb:.2f} MB) exceeds the {MAX_FILE_SIZE_MB} MB limit."

    try:
        uploaded_file.seek(0)
        test_img = Image.open(uploaded_file)
        test_img.verify()

        # Reopen to check dimensions after verify() closes the file
        uploaded_file.seek(0)
        reopened = Image.open(uploaded_file)
        w, h = reopened.size
        if w < MIN_IMAGE_DIMENSION or h < MIN_IMAGE_DIMENSION:
            return False, f"Image dimensions ({w}x{h}) are too small for OCR (minimum {MIN_IMAGE_DIMENSION}px)."
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
    Safely opens uploaded image file using Pillow, corrects EXIF orientation,
    and converts to RGB.
    """
    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        # Automatically rotate according to EXIF orientation metadata
        image = ImageOps.exif_transpose(image)
        if image.mode in ("RGBA", "P", "LA", "L"):
            image = image.convert("RGB")
        return image
    except Exception:
        return None


def get_image_metadata(image: Image.Image, file_name: str, file_size_bytes: int) -> Dict[str, Any]:
    """Returns image metadata and optical quality assessment."""
    width, height = image.size
    size_kb = file_size_bytes / 1024
    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{(size_kb / 1024):.2f} MB"

    quality = assess_image_quality(image)

    return {
        "filename": file_name,
        "resolution": f"{width} × {height} px",
        "format": getattr(image, "format", None) or "JPEG/PNG/WebP",
        "mode": image.mode,
        "filesize": size_str,
        "quality": quality,
    }


def assess_image_quality(image: Image.Image) -> Dict[str, Any]:
    """
    Assesses image sharpness (Laplacian variance) and lighting conditions
    to identify blurry, excessively dark, or overexposed captures.
    """
    try:
        import cv2
        import numpy as np

        img_np = np.array(image.convert("RGB"))
        grey = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

        # Sharpness / Blur metric
        lap_var = float(cv2.Laplacian(grey, cv2.CV_64F).var())
        is_blurry = lap_var < BLUR_THRESHOLD_VAR

        # Lighting metrics
        mean_brightness = float(np.mean(grey))
        std_contrast = float(np.std(grey))

        is_dark = mean_brightness < 40.0
        is_overexposed = mean_brightness > 235.0

        warnings = []
        if is_blurry:
            warnings.append("Image appears blurry or out of focus. Text may not extract reliably.")
        if is_dark:
            warnings.append("Image is very dark. Contrast enhancement has been applied, but well-lit photos work best.")
        if is_overexposed:
            warnings.append("Image is overexposed or has severe glare. Text may be washed out.")

        return {
            "is_blurry": is_blurry,
            "blur_score": round(lap_var, 1),
            "brightness": round(mean_brightness, 1),
            "contrast": round(std_contrast, 1),
            "is_dark": is_dark,
            "is_overexposed": is_overexposed,
            "warning": " ".join(warnings) if warnings else None,
        }
    except Exception:
        return {
            "is_blurry": False,
            "blur_score": 100.0,
            "brightness": 128.0,
            "contrast": 50.0,
            "is_dark": False,
            "is_overexposed": False,
            "warning": None,
        }


def deskew_image(grey_np) -> Tuple[Any, float]:
    """
    Estimates skew angle of text lines using minAreaRect on foreground contours
    and rotates image to level text within a [-20, 20] degree range.
    """
    try:
        import cv2
        import numpy as np

        # Find coordinates of all foreground pixels
        thresh = cv2.threshold(grey_np, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 100:
            return grey_np, 0.0

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        elif angle > 45:
            angle = 90 - angle

        # Only correct moderate tilt within 20 degrees
        if abs(angle) > 0.5 and abs(angle) <= 20.0:
            h, w = grey_np.shape[:2]
            center = (w // 2, h // 2)
            rot_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                grey_np, rot_matrix, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )
            return rotated, float(angle)

        return grey_np, 0.0
    except Exception:
        return grey_np, 0.0


def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    """
    Multi-stage OpenCV preprocessing pipeline for real food-label photos.

    Pipeline:
      1. Upscale to minimum 1800px on the long edge so fine print is clear.
      2. Greyscale conversion and deskewing.
      3. CLAHE (Contrast Limited Adaptive Histogram Equalization) to balance lighting.
      4. Bilateral filtering to reduce sensor noise and halftone print patterns
         while preserving crisp character edges.
      5. Dark-background detection: Invert if text is light-on-dark (e.g. chocolate wrappers).
      6. Adaptive Gaussian thresholding with a generous block size.
      7. Morphological closing to reconnect broken character strokes.

    Falls back to original image if OpenCV is not installed.
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

        # ── Step 2: Greyscale & Deskew ───────────────────────────────────────
        grey = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        grey, _skew_angle = deskew_image(grey)

        # ── Step 3: CLAHE for contrast normalisation ─────────────────────────
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        grey = clahe.apply(grey)

        # ── Step 4: Bilateral filter to smooth grain while keeping sharp edges
        denoised = cv2.bilateralFilter(grey, d=5, sigmaColor=35, sigmaSpace=35)

        # ── Step 5: Detect white-on-dark text and invert if background is dark
        # Sample borders to estimate background brightness
        h_d, w_d = denoised.shape
        border_pixels = np.concatenate([
            denoised[0:max(1, h_d // 20), :].ravel(),
            denoised[-max(1, h_d // 20):, :].ravel(),
            denoised[:, 0:max(1, w_d // 20)].ravel(),
            denoised[:, -max(1, w_d // 20):].ravel(),
        ])
        if np.mean(border_pixels) < 95.0:
            # Predominantly dark packaging background with light text
            denoised = cv2.bitwise_not(denoised)

        # ── Step 6: Adaptive Gaussian thresholding ───────────────────────────
        binary = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            41,
            13
        )

        # ── Step 7: Morphological closing to fix broken character strokes ────
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        return Image.fromarray(cleaned)

    except Exception:
        return image


def preprocess_image_for_ocr_soft(image: Image.Image) -> Image.Image:
    """
    Lighter preprocessing variant — greyscale + CLAHE + unsharp mask sharpening only.
    Used as an alternate pass when harsh binarisation degrades colored or glossy packaging text.
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
            img_bgr = cv2.resize(
                img_bgr, (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_CUBIC
            )

        grey = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8))
        grey = clahe.apply(grey)

        # Sharpen with unsharp mask
        blurred = cv2.GaussianBlur(grey, (0, 0), 2)
        sharpened = cv2.addWeighted(grey, 1.4, blurred, -0.4, 0)

        return Image.fromarray(sharpened)
    except Exception:
        return image
