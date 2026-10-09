"""
MedSafe — Safety Engine Test Suite
====================================
Covers all four verdict statuses and key edge cases.
Run with:  python tests/test_safety_engine.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.safety_engine import (
    run_safety_check,
    STATUS_GREEN, STATUS_YELLOW, STATUS_RED, STATUS_GRAY,
)

PASS = "[PASS]"
FAIL = "[FAIL]"

def test(description, condition):
    status = PASS if condition else FAIL
    print(f"  {status} {description}")
    return condition

results = []

# ---------------------------------------------------------------------------
# GREEN — exact match, low-risk reason
# ---------------------------------------------------------------------------
print("\n--- GREEN: Medicine in discharge prescription, safe reason ---")
r = run_safety_check(
    medicine_name="Amoxicillin",
    strength="500mg",
    patient_reason="It was prescribed to me before",
    current_medications=["Amoxicillin 500mg", "Pantoprazole 40mg"],
)
results.append(test("Status is GREEN",                     r.status == STATUS_GREEN))
results.append(test("Medicine label contains name",        "Amoxicillin" in r.medicine))
results.append(test("Reason mentions current plan",        "current" in r.reason.lower()))
results.append(test("Confidence > 0.8",                    r.confidence > 0.8))
results.append(test("Recommended step present",            bool(r.recommended_next_step)))
results.append(test("Never says 'safe to take'",           "safe to take" not in r.reason.lower()))

# ---------------------------------------------------------------------------
# GREEN via brand-name alias
# ---------------------------------------------------------------------------
print("\n--- GREEN: Brand-name alias resolves to prescription medicine ---")
r2 = run_safety_check(
    medicine_name="Augmentin 625",
    strength="",
    patient_reason="It was prescribed to me before",
    current_medications=["Co-Amoxiclav"],   # same active ingredient AND same DB name
)
# Co-Amoxiclav and Augmentin 625 both resolve to Co-Amoxiclav in the DB
results.append(test("Status is GREEN or YELLOW (alias match)",
                    r2.status in (STATUS_GREEN, STATUS_YELLOW)))
results.append(test("Confidence > 0",                      r2.confidence > 0))

# ---------------------------------------------------------------------------
# YELLOW — medicine in dataset, NOT in current prescription
# ---------------------------------------------------------------------------
print("\n--- YELLOW: Identified medicine, not in current prescription ---")
r3 = run_safety_check(
    medicine_name="Metformin",
    strength="500mg",
    patient_reason="I have similar symptoms again",
    current_medications=["Amoxicillin 500mg", "Pantoprazole 40mg"],
)
results.append(test("Status is YELLOW",                    r3.status == STATUS_YELLOW))
results.append(test("Reason mentions prescription/plan",
                    any(w in r3.reason.lower() for w in ["prescription", "plan", "not"])))
results.append(test("Confidence between 0 and 1",          0 < r3.confidence <= 1.0))
results.append(test("Recommended step present",            bool(r3.recommended_next_step)))
results.append(test("Never says 'safe to take'",           "safe to take" not in r3.reason.lower()))

# ---------------------------------------------------------------------------
# YELLOW — no prescription uploaded
# ---------------------------------------------------------------------------
print("\n--- YELLOW: No prescription available ---")
r4 = run_safety_check(
    medicine_name="Cetirizine",
    strength="10mg",
    patient_reason="It was prescribed to me before",
    current_medications=[],   # empty = no prescription saved
)
results.append(test("Status is YELLOW",                    r4.status == STATUS_YELLOW))
results.append(test("Evidence mentions no prescription",
                    "no discharge prescription" in r4.evidence.lower() or
                    "no" in r4.evidence.lower()))
results.append(test("Recommends uploading prescription",
                    "upload" in r4.recommended_next_step.lower() or
                    "prescription" in r4.recommended_next_step.lower()))

# ---------------------------------------------------------------------------
# RED — active ingredient overlap
# ---------------------------------------------------------------------------
print("\n--- RED: Same active ingredient as current prescription medicine ---")
r5 = run_safety_check(
    medicine_name="Augmentin",          # active ingredient: Amoxicillin
    strength="625mg",
    patient_reason="It was prescribed to me before",
    current_medications=["Amoxicillin 500mg"],  # same active ingredient
)
results.append(test("Status is RED",                       r5.status == STATUS_RED))
results.append(test("Reason mentions overlap/ingredient",
                    any(w in r5.reason.lower() for w in ["overlap", "ingredient", "same"])))
results.append(test("Evidence mentions active ingredient",
                    "active ingredient" in r5.evidence.lower() or
                    "amoxicillin" in r5.evidence.lower()))
results.append(test("Step says do not take / speak to doctor",
                    any(w in r5.recommended_next_step.lower()
                        for w in ["do not", "doctor", "pharmacist", "speak"])))
results.append(test("Never says 'safe to take'",           "safe to take" not in r5.reason.lower()))

# ---------------------------------------------------------------------------
# RED — high-risk reason even when in prescription
# ---------------------------------------------------------------------------
print("\n--- RED: In prescription, but 'Someone recommended it' ---")
r6 = run_safety_check(
    medicine_name="Amoxicillin",
    strength="500mg",
    patient_reason="Someone recommended it",
    current_medications=["Amoxicillin 500mg"],
)
results.append(test("Status is RED",                       r6.status == STATUS_RED))
results.append(test("Reason mentions unclear/confirmation",
                    any(w in r6.reason.lower()
                        for w in ["reason", "confirmation", "professional", "reuse"])))

print("\n--- RED: In prescription, 'I don't remember why I have it' ---")
r7 = run_safety_check(
    medicine_name="Paracetamol",
    strength="500mg",
    patient_reason="I don't remember why I have it",
    current_medications=["Paracetamol 500mg"],
)
results.append(test("Status is RED",                       r7.status == STATUS_RED))

# ---------------------------------------------------------------------------
# YELLOW — in prescription, medium-risk reason
# ---------------------------------------------------------------------------
print("\n--- YELLOW: In prescription, 'I have similar symptoms again' ---")
r8 = run_safety_check(
    medicine_name="Amoxicillin",
    strength="500mg",
    patient_reason="I have similar symptoms again",
    current_medications=["Amoxicillin 500mg"],
)
results.append(test("Status is YELLOW (downgraded from GREEN)",  r8.status == STATUS_YELLOW))
results.append(test("Confidence is lower than full GREEN score", r8.confidence <= 0.96))

# ---------------------------------------------------------------------------
# GRAY — completely unknown medicine
# ---------------------------------------------------------------------------
print("\n--- GRAY: Medicine not in demo dataset ---")
r9 = run_safety_check(
    medicine_name="DragonRoot 200mg",
    strength="",
    patient_reason="Other",
    current_medications=["Amoxicillin 500mg"],
)
results.append(test("Status is GRAY",                       r9.status == STATUS_GRAY))
results.append(test("Confidence is 0.0",                    r9.confidence == 0.0))
results.append(test("Evidence mentions not found",
                    any(w in r9.evidence.lower()
                        for w in ["not found", "demo dataset", "not indicate"])))
results.append(test("Step says do not take",
                    any(w in r9.recommended_next_step.lower()
                        for w in ["do not", "pharmacist", "doctor", "cannot"])))
results.append(test("Never says 'safe to take'",            "safe to take" not in r9.reason.lower()))

# ---------------------------------------------------------------------------
# OCR confidence impact
# ---------------------------------------------------------------------------
print("\n--- Confidence: OCR low-confidence downgrades score ---")
r10_high = run_safety_check(
    medicine_name="Amoxicillin",
    strength="500mg",
    patient_reason="It was prescribed to me before",
    current_medications=["Amoxicillin 500mg"],
    ocr_confidence=95.0,
)
r10_low = run_safety_check(
    medicine_name="Amoxicillin",
    strength="500mg",
    patient_reason="It was prescribed to me before",
    current_medications=["Amoxicillin 500mg"],
    ocr_confidence=20.0,
)
results.append(test("High OCR confidence > low OCR confidence",
                    r10_high.confidence > r10_low.confidence))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total  = len(results)
passed = sum(results)
failed = total - passed
print(f"\n{'='*48}")
print(f"  Results: {passed}/{total} passed  |  {failed} failed")
print(f"{'='*48}\n")
if failed:
    sys.exit(1)
