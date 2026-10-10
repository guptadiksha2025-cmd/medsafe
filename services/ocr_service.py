"""
MedSafe OCR & Document Extraction Service
=========================================
Extracts text from medicine packaging images, photos, blister strips, and PDF documents
(such as electronic or scanned hospital discharge prescriptions).

Supports:
- Image formats: PNG, JPG, JPEG, WEBP (via Pillow + Multi-pass Tesseract OCR)
- PDF documents: Digital PDF text extraction & scanned PDF page OCR (via PyMuPDF / pypdf)

OCR output is treated as UNTRUSTED input — the user must always review
and correct the extracted information before proceeding.
"""

import os
import re
import io
import shutil
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from PIL import Image, ImageFilter, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dynamic Tesseract setup — checks all standard Windows installation paths
# ---------------------------------------------------------------------------
try:
    import pytesseract

    def _find_tesseract_binary() -> Optional[str]:
        # Check PATH first
        path_cmd = shutil.which("tesseract")
        if path_cmd and os.path.isfile(path_cmd):
            return path_cmd

        # Check standard Windows directories
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
            os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

    tess_path = _find_tesseract_binary()
    if tess_path:
        pytesseract.pytesseract.tesseract_cmd = tess_path

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# ---------------------------------------------------------------------------
# PyMuPDF / pypdf setup for PDF document support
# ---------------------------------------------------------------------------
try:
    import pymupdf  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

# Confidence threshold (0-100). Below this we flag the result as low-confidence.
CONFIDENCE_THRESHOLD = 40

# Common strength patterns found on medicine labels
_STRENGTH_RE = re.compile(
    r'\b(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|%|iu|units?)(?:\s*/\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|%))?)\b',
    re.IGNORECASE,
)

# Common dosage cues
_DOSAGE_KEYWORDS = [
    'once daily', 'twice daily', 'three times', 'every', 'after food',
    'before food', 'at bedtime', 'as needed', 'tablet', 'capsule',
    'per day', 'morning', 'evening', 'night', 'hours',
]


@dataclass
class OCRResult:
    """Container for OCR and PDF extraction output."""
    raw_text: str = ""
    medicine_name: str = ""
    strength: str = ""
    dosage_info: str = ""
    confidence: float = 0.0
    is_low_confidence: bool = True
    is_pdf: bool = False
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Multi-Pass Image Preprocessing for Packaging & Blister Strips
# ---------------------------------------------------------------------------

def _preprocess_pass1(image: Image.Image) -> Image.Image:
    """Pass 1: Grayscale + Sharpen + Moderate Contrast Boost (for high-contrast packaging)."""
    img = image.convert("L")
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.6)
    return img


def _preprocess_pass2(image: Image.Image) -> Image.Image:
    """Pass 2: Auto-contrast + adaptive thresholding (for foil blister strips & low-light photos)."""
    img = image.convert("L")
    img = ImageOps.autocontrast(img, cutoff=2)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    # Binarize with threshold
    threshold = 140
    img = img.point(lambda p: 255 if p > threshold else 0)
    return img


# ---------------------------------------------------------------------------
# Core OCR Pipeline with Multi-Pass Execution
# ---------------------------------------------------------------------------

def _run_tesseract_ocr(image: Image.Image) -> Tuple[str, float]:
    """
    Run multi-pass Tesseract OCR on a PIL image.
    Uses PSM 3 (auto page segmentation) and PSM 11 (sparse text).
    Returns (raw_text, confidence).
    """
    if not TESSERACT_AVAILABLE:
        return "", 0.0

    best_text = ""
    best_conf = 0.0

    # Ensure tesseract_cmd is set if binary is available
    if not shutil.which("tesseract"):
        found_bin = _find_tesseract_binary()
        if found_bin:
            pytesseract.pytesseract.tesseract_cmd = found_bin

    # Try Pass 1: Standard contrast enhancement with PSM 3 (Auto)
    try:
        p1_img = _preprocess_pass1(image)
        p1_data = pytesseract.image_to_data(p1_img, output_type=pytesseract.Output.DICT, config="--psm 3")
        p1_text = pytesseract.image_to_string(p1_img, config="--psm 3").strip()
        confs = [int(c) for c in p1_data.get("conf", []) if int(c) > -1]
        p1_conf = sum(confs) / len(confs) if confs else 0.0

        if len(p1_text) > len(best_text):
            best_text = p1_text
            best_conf = p1_conf
    except Exception as e:
        logger.debug("Tesseract Pass 1 failed: %s", e)

    # Try Pass 2: Sparse layout / high-contrast threshold with PSM 11
    try:
        p2_img = _preprocess_pass2(image)
        p2_data = pytesseract.image_to_data(p2_img, output_type=pytesseract.Output.DICT, config="--psm 11")
        p2_text = pytesseract.image_to_string(p2_img, config="--psm 11").strip()
        confs2 = [int(c) for c in p2_data.get("conf", []) if int(c) > -1]
        p2_conf = sum(confs2) / len(confs2) if confs2 else 0.0

        # If Pass 2 produced significantly more text or Pass 1 had low confidence
        if (len(p2_text) > len(best_text) and p2_conf >= 30) or not best_text:
            best_text = p2_text
            best_conf = max(best_conf, p2_conf)
        elif p2_text and p1_text and len(p2_text) > 10:
            # Combine any unique text detected
            combined_lines = list(dict.fromkeys(p1_text.splitlines() + p2_text.splitlines()))
            best_text = "\n".join(combined_lines).strip()
    except Exception as e:
        logger.debug("Tesseract Pass 2 failed: %s", e)

    return best_text, best_conf


# ---------------------------------------------------------------------------
# PDF Extraction Handlers
# ---------------------------------------------------------------------------

def _extract_from_pdf(pdf_path: str) -> OCRResult:
    """
    Extract text from a PDF file.
    1. First attempts direct digital text extraction (fast and 100% accurate for digital discharge summaries).
    2. If the PDF is scanned (contains images only), renders pages to high-DPI images and runs Tesseract OCR.
    """
    result = OCRResult(is_pdf=True)

    if not os.path.isfile(pdf_path):
        result.warnings.append("Prescription PDF file not found.")
        return result

    extracted_text = ""

    # Strategy 1: PyMuPDF digital text extraction
    if PYMUPDF_AVAILABLE:
        try:
            doc = pymupdf.open(pdf_path)
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    extracted_text += page_text + "\n"
            doc.close()
        except Exception as exc:
            logger.warning("PyMuPDF digital extraction failed on %s: %s", pdf_path, exc)

    # Strategy 2: pypdf fallback for digital text
    if not extracted_text.strip() and PYPDF_AVAILABLE:
        try:
            reader = pypdf.PdfReader(pdf_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        except Exception as exc:
            logger.warning("pypdf text extraction failed on %s: %s", pdf_path, exc)

    extracted_text = extracted_text.strip()

    # If meaningful digital text was found (> 15 chars), return high-confidence direct extraction
    if len(extracted_text) >= 15:
        result.raw_text = extracted_text
        result.confidence = 95.0
        result.is_low_confidence = False
        result.medicine_name = _identify_or_guess_medicine_name(extracted_text)
        result.strength = _extract_strength(extracted_text)
        result.dosage_info = _extract_dosage(extracted_text)
        return result

    # Strategy 3: Scanned PDF — render pages to image and run multi-pass OCR
    if PYMUPDF_AVAILABLE and TESSERACT_AVAILABLE:
        try:
            doc = pymupdf.open(pdf_path)
            ocr_pages_text = []
            page_confidences = []

            for page_idx, page in enumerate(doc):
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                p_text, p_conf = _run_tesseract_ocr(img)

                if p_text:
                    ocr_pages_text.append(p_text)
                if p_conf > 0:
                    page_confidences.append(p_conf)

            doc.close()

            combined_ocr_text = "\n\n".join(ocr_pages_text).strip()
            if combined_ocr_text:
                result.raw_text = combined_ocr_text
                result.confidence = sum(page_confidences) / len(page_confidences) if page_confidences else 60.0
                result.is_low_confidence = result.confidence < CONFIDENCE_THRESHOLD
                result.medicine_name = _identify_or_guess_medicine_name(combined_ocr_text)
                result.strength = _extract_strength(combined_ocr_text)
                result.dosage_info = _extract_dosage(combined_ocr_text)
                return result

        except Exception as render_err:
            logger.warning("Scanned PDF page rendering failed: %s", render_err)

    # Fallback if text extracted but low confidence
    if extracted_text:
        result.raw_text = extracted_text
        result.confidence = 50.0
        result.is_low_confidence = True
        result.medicine_name = _identify_or_guess_medicine_name(extracted_text)
        result.strength = _extract_strength(extracted_text)
        result.dosage_info = _extract_dosage(extracted_text)
    else:
        result.warnings.append(
            "Could not extract readable text from this PDF. Please verify and enter the medicine details manually."
        )

    return result


# ---------------------------------------------------------------------------
# Core Extraction Pipeline (Images + PDFs)
# ---------------------------------------------------------------------------

def extract_text_from_file(file_path: str) -> OCRResult:
    """
    Unified extraction entry point supporting both image and PDF files.
    """
    if not os.path.isfile(file_path):
        res = OCRResult()
        res.warnings.append("Document file not found.")
        return res

    if file_path.lower().endswith('.pdf'):
        return _extract_from_pdf(file_path)

    return extract_text_from_image(file_path)


def extract_text_from_image(image_path: str) -> OCRResult:
    """
    Run extraction on an image or PDF file and return structured OCR results.
    """
    if image_path.lower().endswith('.pdf'):
        return _extract_from_pdf(image_path)

    result = OCRResult()

    if not os.path.isfile(image_path):
        result.warnings.append("Image file not found.")
        return result

    try:
        image = Image.open(image_path)
    except Exception as exc:
        logger.warning("Failed to open image %s: %s", image_path, exc)
        result.warnings.append("Could not open the image. The file may be corrupted or unreadable.")
        return result

    # Run multi-pass Tesseract extraction
    raw_text, confidence = _run_tesseract_ocr(image)

    result.raw_text = raw_text
    result.confidence = confidence

    if not result.raw_text:
        result.warnings.append(
            "Could not extract clear text from the image. Please enter the medicine name manually below."
        )
        return result

    result.is_low_confidence = result.confidence < CONFIDENCE_THRESHOLD

    if result.is_low_confidence:
        result.warnings.append(
            "Medicine information could not be confidently identified from the image. Please verify details manually."
        )

    # --- Match identified medicine and parse fields ---
    result.medicine_name = _identify_or_guess_medicine_name(result.raw_text)
    result.strength = _extract_strength(result.raw_text)
    result.dosage_info = _extract_dosage(result.raw_text)

    return result


# ---------------------------------------------------------------------------
# Prescription-specific extraction (returns raw text only)
# ---------------------------------------------------------------------------

def extract_prescription_text(file_path: str) -> OCRResult:
    """
    Extract raw text from a discharge prescription image or PDF.
    """
    if file_path.lower().endswith('.pdf'):
        result = _extract_from_pdf(file_path)
    else:
        result = extract_text_from_image(file_path)

    # For prescriptions we intentionally preserve raw text for user review
    result.medicine_name = ""
    result.strength = ""
    result.dosage_info = ""
    return result


# ---------------------------------------------------------------------------
# Heuristic & Intelligent Recognition Helpers
# ---------------------------------------------------------------------------

def _identify_or_guess_medicine_name(text: str) -> str:
    """
    First attempts intelligent lookup against the demo medicine database.
    If no known medicine is matched, applies improved packaging heuristics.
    """
    if not text or not text.strip():
        return ""

    # Strategy 1: Match against known medicines & aliases in database
    try:
        from services.medicine_service import find_medicine_in_text
        found = find_medicine_in_text(text)
        if found and found.get('medicine_name'):
            return found['medicine_name']
    except Exception as e:
        logger.debug("find_medicine_in_text failed: %s", e)

    # Strategy 2: Clean heuristics for unlisted packaging
    return _guess_medicine_name(text)


def _guess_medicine_name(text: str) -> str:
    """
    Heuristic: isolate candidate medicine name from packaging text by
    stripping pharmaceutical boilerplate, licensing, and manufacturer noise.
    """
    boilerplate_words = {
        'mfg', 'mfd', 'exp', 'batch', 'lot', 'store', 'keep', 'warning',
        'caution', 'for', 'use', 'only', 'date', 'manufactured', 'marketed',
        'hospital', 'discharge', 'summary', 'rx', 'prescription', 'patient',
        'tablets', 'capsules', 'strip', 'pack', 'limited', 'ltd', 'pvt',
        'schedule', 'drug', 'dosage', 'directed', 'physician', 'reach',
        'children', 'lic', 'reg', 'composition', 'each', 'contains', 'ip',
        'bp', 'usp', 'price', 'mrp', 'inclusive', 'taxes',
    }

    candidates = []
    for line in text.splitlines():
        cleaned_line = line.strip().lstrip('0123456789.-) ')
        if not cleaned_line or len(cleaned_line) < 3:
            continue

        # Skip lines that are purely numeric, date-like, or dosage
        if re.fullmatch(r'[\d/.\-\s%:mg/]+', cleaned_line, re.IGNORECASE):
            continue

        words = [w.lower().rstrip(':.,;()') for w in cleaned_line.split()]
        # Check if line is purely boilerplate words
        boilerplate_count = sum(1 for w in words if w in boilerplate_words)
        if boilerplate_count >= len(words) * 0.6:
            continue

        # Clean out trailing pharmaceutical terms like "Tablets IP" or "500mg"
        cleaned_line = re.sub(r'\b(Tablets?|Capsules?|IP|BP|USP|Oral|Syrup|Injection)\b', '', cleaned_line, flags=re.IGNORECASE).strip()
        cleaned_line = re.sub(r'\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|%)\b', '', cleaned_line, flags=re.IGNORECASE).strip()

        if len(cleaned_line) >= 3:
            candidates.append(cleaned_line)

    if candidates:
        # Return the shortest non-empty candidate (usually the brand name)
        candidates.sort(key=lambda c: (len(c.split()) > 4, len(c)))
        return candidates[0]

    return ""


def _extract_strength(text: str) -> str:
    """Return the first strength pattern found (e.g. '500mg' or '625 mg')."""
    match = _STRENGTH_RE.search(text)
    return match.group(1).strip() if match else ""


def _extract_dosage(text: str) -> str:
    """Return any line fragment containing dosage-related keywords."""
    fragments = []
    for line in text.splitlines():
        if any(kw in line.lower() for kw in _DOSAGE_KEYWORDS):
            fragments.append(line.strip().lstrip('0123456789.-) '))
    return "; ".join(fragments) if fragments else ""
