"""
MedSafe AI Service
==================
Uses an LLM (Google Gemini via REST) ONLY as an explanation layer.

ARCHITECTURE CONSTRAINT
------------------------
The AI service is strictly assistive:
  - It CANNOT change the Safety Engine's verdict (GREEN / YELLOW / RED / GRAY).
  - It CANNOT claim a medicine is safe or unsafe.
  - It CANNOT prescribe, diagnose, or override clinical guidance.
  - It translates the deterministic engine's output into simple patient language.

If the API is unavailable for any reason the application continues to work
using the deterministic Safety Engine output directly.

PRIVACY
-------
Only the minimum medication context is sent:
  - medicine name, status, reason, evidence, recommended next step.
  - No patient name, age, personal identifiers, or medical history.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_API_KEY: Optional[str] = None
_API_TIMEOUT_SECONDS = 8
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key={key}"
)

# Maximum characters of explanation text we'll accept from the LLM.
_MAX_EXPLANATION_LENGTH = 600


def _get_api_key() -> Optional[str]:
    """Read the LLM API key from environment (loaded via python-dotenv)."""
    global _API_KEY
    if _API_KEY is None:
        _API_KEY = os.environ.get("LLM_API_KEY", "").strip() or None
    return _API_KEY


# ---------------------------------------------------------------------------
# Prompt builder — minimal, privacy-safe
# ---------------------------------------------------------------------------

def _build_prompt(
    medicine: str,
    status: str,
    reason: str,
    evidence: str,
    recommended_next_step: str,
    current_medicines: list,
) -> str:
    """
    Build a tightly scoped prompt.  Only medication context — no personal data.
    """
    current_str = ", ".join(current_medicines) if current_medicines else "none provided"
    status_map = {
        "GREEN":  "Matches current medication list",
        "YELLOW": "Verify before taking",
        "RED":    "Professional review required",
        "GRAY":   "Unable to verify",
    }
    status_label = status_map.get(status, status)

    return f"""You are a patient-information assistant for a medication safety checkpoint tool called MedSafe.
A safety engine has already analysed this situation and produced a deterministic verdict.
Your task is ONLY to rewrite the verdict in simple, clear language that a patient can understand.

RULES YOU MUST FOLLOW:
- Do NOT change the status verdict.
- Do NOT say the medicine is safe or unsafe.
- Do NOT diagnose or prescribe.
- Do NOT claim medical certainty.
- Keep the explanation to 2-3 short sentences.
- Use plain English that a non-medical person can understand.
- Always recommend the patient speak to a pharmacist or doctor when the status is YELLOW, RED, or GRAY.

SAFETY ENGINE OUTPUT:
Medicine checked: {medicine}
Current discharge medicines: {current_str}
Status: {status} — {status_label}
Reason: {reason}
Evidence: {evidence}
Recommended next step: {recommended_next_step}

Write a patient-friendly explanation of this result. Do not add any new medical information."""


# ---------------------------------------------------------------------------
# Core API call
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str, api_key: str) -> Optional[str]:
    """
    Call the Gemini REST API synchronously.
    Returns the text response, or None on any failure.
    """
    url = _GEMINI_URL.format(key=api_key)
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,        # low temperature = consistent, factual tone
            "maxOutputTokens": 150,    # short explanation only
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            # Navigate Gemini response structure
            text = (
                body
                .get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            if not text:
                logger.warning("AI service returned an empty response body.")
                return None
            return text[:_MAX_EXPLANATION_LENGTH]

    except urllib.error.HTTPError as exc:
        logger.warning("AI API HTTP error %s: %s", exc.code, exc.reason)
    except urllib.error.URLError as exc:
        logger.warning("AI API URL error: %s", exc.reason)
    except TimeoutError:
        logger.warning("AI API request timed out after %ss.", _API_TIMEOUT_SECONDS)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("AI API response parse error: %s", exc)
    except Exception as exc:  # noqa: BLE001 — intentionally broad fallback
        logger.warning("Unexpected AI API error: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def explain_safety_result(
    medicine: str,
    status: str,
    reason: str,
    evidence: str,
    recommended_next_step: str,
    current_medicines: Optional[list] = None,
) -> dict:
    """
    Generate a patient-friendly explanation of the Safety Engine's verdict.

    Returns
    -------
    dict with keys:
        explanation (str)   — the explanation text (AI or fallback)
        ai_used (bool)      — True if the LLM produced this explanation
        error (str | None)  — error description if AI was unavailable
    """
    if current_medicines is None:
        current_medicines = []

    api_key = _get_api_key()

    # ── No API key configured — use deterministic fallback immediately ──
    if not api_key:
        return {
            "explanation": _deterministic_explanation(status, reason, recommended_next_step),
            "ai_used": False,
            "error": "AI explanation unavailable (no API key configured).",
        }

    prompt = _build_prompt(
        medicine=medicine,
        status=status,
        reason=reason,
        evidence=evidence,
        recommended_next_step=recommended_next_step,
        current_medicines=current_medicines,
    )

    ai_text = _call_gemini(prompt, api_key)

    if ai_text:
        return {
            "explanation": ai_text,
            "ai_used": True,
            "error": None,
        }

    # ── API failed — graceful fallback ──
    return {
        "explanation": _deterministic_explanation(status, reason, recommended_next_step),
        "ai_used": False,
        "error": "AI explanation temporarily unavailable. Showing standard result.",
    }


def parse_ocr_text_with_ai(raw_ocr_text: str) -> dict:
    """
    Use the LLM to extract structured fields from messy OCR prescription text.

    Returns a dict with keys: medicine_name, strength, dosage, notes.
    Falls back to empty strings on any failure.
    """
    api_key = _get_api_key()

    _empty = {"medicine_name": "", "strength": "", "dosage": "", "notes": ""}

    if not api_key or not raw_ocr_text.strip():
        return _empty

    prompt = f"""You are a medication label text parser.
Extract the following fields from this raw OCR text from a medicine label or prescription.
Return a JSON object with exactly these keys: medicine_name, strength, dosage, notes.
If a field cannot be determined, use an empty string.
Do NOT invent information that is not in the text.
Do NOT add medical advice.

RAW OCR TEXT:
{raw_ocr_text[:800]}

Return only valid JSON. No explanation."""

    api_text = _call_gemini(prompt, api_key)

    if not api_text:
        return _empty

    # Strip markdown code fences if present
    cleaned = api_text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

    try:
        parsed = json.loads(cleaned)
        return {
            "medicine_name": str(parsed.get("medicine_name", "")),
            "strength":      str(parsed.get("strength", "")),
            "dosage":        str(parsed.get("dosage", "")),
            "notes":         str(parsed.get("notes", "")),
        }
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Could not parse AI OCR response as JSON: %s", exc)
        return _empty


# ---------------------------------------------------------------------------
# Deterministic fallback — used when AI is unavailable
# ---------------------------------------------------------------------------

def _deterministic_explanation(status: str, reason: str, recommended_next_step: str) -> str:
    """
    Build a plain-English explanation from the Safety Engine fields alone,
    without calling any external API.
    """
    intros = {
        "GREEN":  "This medicine appears to match your current discharge medication list.",
        "YELLOW": "This medicine needs to be verified before you take it.",
        "RED":    "This medicine requires a professional review before you consider taking it.",
        "GRAY":   "This medicine could not be verified by the system.",
    }
    intro = intros.get(status, "The system could not determine the status of this medicine.")
    return f"{intro} {reason} {recommended_next_step}"
