"""
MedSafe — AI Service Test Suite
=================================
Tests the AI service in isolation, specifically the graceful fallback
behaviour when the API key is missing or the API is unavailable.

All core safety functionality must work without any LLM.

Run with:  python tests/test_ai_service.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force API key to empty before importing service so we test the no-key path
os.environ.pop("LLM_API_KEY", None)

from services.ai_service import (
    explain_safety_result,
    parse_ocr_text_with_ai,
    _deterministic_explanation,
    _build_prompt,
)

PASS = "[PASS]"
FAIL = "[FAIL]"

def test(description, condition):
    status = PASS if condition else FAIL
    print(f"  {status} {description}")
    return condition

results = []

# ---------------------------------------------------------------------------
# Fallback: no API key
# ---------------------------------------------------------------------------
print("\n--- Fallback: no API key configured ---")

r = explain_safety_result(
    medicine="Amoxicillin 500mg",
    status="GREEN",
    reason="Matches your current medication list.",
    evidence="Found in discharge prescription.",
    recommended_next_step="Confirm dose with pharmacist.",
    current_medicines=["Amoxicillin 500mg"],
)
results.append(test("Returns a dict",                      isinstance(r, dict)))
results.append(test("ai_used is False",                    r['ai_used'] is False))
results.append(test("Explanation is non-empty",            bool(r['explanation'])))
results.append(test("Error field present and non-empty",   bool(r.get('error'))))
results.append(test("Never says 'safe to take'",           "safe to take" not in r['explanation'].lower()))

# ---------------------------------------------------------------------------
# Fallback: empty medicine name
# ---------------------------------------------------------------------------
print("\n--- Fallback: called with empty medicine name ---")
r2 = explain_safety_result(
    medicine="",
    status="GRAY",
    reason="Medicine not identified.",
    evidence="Not in demo dataset.",
    recommended_next_step="See a pharmacist.",
)
results.append(test("Returns a dict",                      isinstance(r2, dict)))
results.append(test("ai_used is False",                    r2['ai_used'] is False))
results.append(test("Explanation present",                 bool(r2['explanation'])))

# ---------------------------------------------------------------------------
# Deterministic fallback for all four statuses
# ---------------------------------------------------------------------------
print("\n--- Deterministic fallback: all four statuses ---")
for status, expected_word in [
    ("GREEN",  "match"),
    ("YELLOW", "verified"),
    ("RED",    "professional"),
    ("GRAY",   "could not"),
]:
    exp = _deterministic_explanation(status, "Some reason.", "Next step.")
    results.append(test(
        f"{status} fallback contains expected word '{expected_word}'",
        expected_word in exp.lower()
    ))

# ---------------------------------------------------------------------------
# Deterministic fallback: never prescribes or claims safety
# ---------------------------------------------------------------------------
print("\n--- Deterministic fallback: safety language check ---")
for status in ["GREEN", "YELLOW", "RED", "GRAY"]:
    exp = _deterministic_explanation(status, "Reason.", "Next step.")
    results.append(test(
        f"{status}: does not say 'safe to take'",
        "safe to take" not in exp.lower()
    ))
    results.append(test(
        f"{status}: does not say 'you are safe'",
        "you are safe" not in exp.lower()
    ))

# ---------------------------------------------------------------------------
# OCR parsing fallback: no API key -> returns empty dict
# ---------------------------------------------------------------------------
print("\n--- OCR AI parsing: no API key -> clean empty fallback ---")
parsed = parse_ocr_text_with_ai("Amoxicillin 500mg Take 1 capsule three times daily")
results.append(test("Returns a dict",                      isinstance(parsed, dict)))
results.append(test("Has medicine_name key",               "medicine_name" in parsed))
results.append(test("Has strength key",                    "strength" in parsed))
results.append(test("Has dosage key",                      "dosage" in parsed))
results.append(test("All values are strings",              all(isinstance(v, str) for v in parsed.values())))

# ---------------------------------------------------------------------------
# OCR parsing fallback: empty input
# ---------------------------------------------------------------------------
print("\n--- OCR AI parsing: empty string ---")
parsed2 = parse_ocr_text_with_ai("")
results.append(test("Returns empty strings on empty input", all(v == "" for v in parsed2.values())))

# ---------------------------------------------------------------------------
# Prompt builder: minimal, privacy-safe content
# ---------------------------------------------------------------------------
print("\n--- Prompt builder: privacy and content checks ---")
prompt = _build_prompt(
    medicine="Amoxicillin 500mg",
    status="YELLOW",
    reason="Not in current plan.",
    evidence="Not found.",
    recommended_next_step="See pharmacist.",
    current_medicines=["Pantoprazole 40mg"],
)
results.append(test("Prompt contains medicine name",        "Amoxicillin" in prompt))
results.append(test("Prompt contains status",               "YELLOW" in prompt))
results.append(test("Prompt contains RULES section",        "RULES" in prompt))
results.append(test("Prompt does not contain personal data",
                    "patient name" not in prompt.lower() and
                    "date of birth" not in prompt.lower()))
results.append(test("Prompt instructs not to claim safety",
                    "safe" in prompt.lower() and "Do NOT" in prompt))

# ---------------------------------------------------------------------------
# Workflow: full safety check works without AI
# ---------------------------------------------------------------------------
print("\n--- Full workflow without AI (safety engine still works) ---")
from services.safety_engine import run_safety_check, STATUS_GREEN, STATUS_GRAY

sr = run_safety_check(
    medicine_name="Amoxicillin",
    strength="500mg",
    patient_reason="It was prescribed to me before",
    current_medications=["Amoxicillin 500mg"],
)
results.append(test("Safety engine GREEN without AI",       sr.status == STATUS_GREEN))

ai_fallback = explain_safety_result(
    medicine=sr.medicine,
    status=sr.status,
    reason=sr.reason,
    evidence=sr.evidence,
    recommended_next_step=sr.recommended_next_step,
)
results.append(test("AI fallback explanation is usable",    bool(ai_fallback['explanation'])))
results.append(test("Application works end-to-end",         ai_fallback['ai_used'] is False))

sr2 = run_safety_check(
    medicine_name="UnknownDrug XYZ",
    strength="",
    patient_reason="Other",
    current_medications=[],
)
results.append(test("Safety engine GRAY without AI",        sr2.status == STATUS_GRAY))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total  = len(results)
passed = sum(results)
failed = total - passed
print(f"\n{'='*50}")
print(f"  Results: {passed}/{total} passed  |  {failed} failed")
print(f"{'='*50}\n")
if failed:
    sys.exit(1)
