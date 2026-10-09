"""
MedSafe Safety Decision Engine
================================
Compares an old medicine against the patient's current discharge prescription
and returns a structured safety verdict.

FOUR STATUSES
-------------
  GREEN  — Medicine matches current discharge plan.
  YELLOW — Medicine identified but not clearly in current plan. Verify first.
  RED    — A defined concern (duplicate/overlap) detected. Professional review required.
  GRAY   — Medicine cannot be confidently identified. Unable to verify.

CRITICAL CONSTRAINT
-------------------
This engine NEVER tells a patient that a medicine is safe to take.
It is a decision-support checkpoint only. Every result includes a
recommended next step that directs the user toward professional verification.
"""

from dataclasses import dataclass, field
from typing import Optional

from services.medicine_service import lookup_medicine, is_current_medicine

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_GREEN  = "GREEN"
STATUS_YELLOW = "YELLOW"
STATUS_RED    = "RED"
STATUS_GRAY   = "GRAY"

# Reasons that raise the risk level regardless of database match
HIGH_RISK_REASONS = {
    "I have similar symptoms again",
    "Someone recommended it",
    "I don't remember why I have it",
    "Other",
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SafetyResult:
    status: str
    medicine: str
    reason: str          # human-readable explanation of the verdict
    evidence: str        # what data drove the decision
    recommended_next_step: str
    confidence: float    # 0.0 – 1.0
    details: dict = field(default_factory=dict)   # raw lookup / comparison data


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def run_safety_check(
    medicine_name: str,
    strength: str,
    patient_reason: str,
    current_medications: list,
    ocr_confidence: Optional[float] = None,
) -> SafetyResult:
    """
    Core safety check entry-point.

    Parameters
    ----------
    medicine_name       : str   — name entered/confirmed by the user
    strength            : str   — strength entered by the user (may be empty)
    patient_reason      : str   — why the patient is considering reuse
    current_medications : list  — list of medicine name strings from discharge Rx
    ocr_confidence      : float — OCR confidence score (0–100), or None if manual

    Returns
    -------
    SafetyResult
    """
    medicine_label = f"{medicine_name} {strength}".strip() if strength else medicine_name

    # ------------------------------------------------------------------ #
    # 1. Identify medicine in demo dataset                                 #
    # ------------------------------------------------------------------ #
    lookup = lookup_medicine(medicine_name)

    # ------------------------------------------------------------------ #
    # 2. GRAY — cannot identify the medicine                              #
    # ------------------------------------------------------------------ #
    if not lookup['identified']:
        return SafetyResult(
            status=STATUS_GRAY,
            medicine=medicine_label,
            reason="Unable to verify — medicine not identified.",
            evidence=(
                f"'{medicine_name}' was not found in the MedSafe demo dataset. "
                "This does not indicate the medicine is safe or unsafe."
            ),
            recommended_next_step=(
                "Show the medicine to your pharmacist or doctor before taking it. "
                "Do not take a medicine that cannot be verified."
            ),
            confidence=0.0,
            details={'lookup': lookup},
        )

    # ------------------------------------------------------------------ #
    # 3. Compute OCR confidence factor                                    #
    # ------------------------------------------------------------------ #
    # If name came from OCR with low confidence, cap our overall confidence
    if ocr_confidence is not None:
        id_confidence = min(ocr_confidence / 100.0, 0.95)
    else:
        id_confidence = 0.95   # manual entry assumed reliable

    # ------------------------------------------------------------------ #
    # 4. Compare against current discharge prescription                   #
    # ------------------------------------------------------------------ #
    rx = is_current_medicine(medicine_name, current_medications)
    high_risk_reason = patient_reason in HIGH_RISK_REASONS

    # ------------------------------------------------------------------ #
    # 5. RED — active ingredient overlap (duplicate risk)                 #
    # ------------------------------------------------------------------ #
    if rx['found_same_ingredient'] and not rx['found_exact']:
        overlap_name = rx['matched_current_medicine'] or 'a medicine in your current plan'
        return SafetyResult(
            status=STATUS_RED,
            medicine=medicine_label,
            reason=(
                f"Active ingredient overlap detected with '{overlap_name}' "
                f"from your current discharge prescription."
            ),
            evidence=(
                f"'{medicine_name}' and '{overlap_name}' share the same active ingredient "
                f"({lookup['active_ingredient']}). Taking both may result in a duplicate dose."
            ),
            recommended_next_step=(
                "Do not take this medicine without first speaking to your doctor or pharmacist. "
                "A duplicate active ingredient can cause unintended side effects."
            ),
            confidence=round(id_confidence, 2),
            details={'lookup': lookup, 'rx_comparison': rx},
        )

    # ------------------------------------------------------------------ #
    # 6. RED — high-risk reason even when medicine is in plan             #
    # ------------------------------------------------------------------ #
    # "Someone recommended it" or "I don't remember" are always RED
    # because intent is unclear even if the medicine matches.
    if rx['found_exact'] and patient_reason in {"Someone recommended it",
                                                 "I don't remember why I have it"}:
        return SafetyResult(
            status=STATUS_RED,
            medicine=medicine_label,
            reason=(
                "This medicine matches your discharge plan, but the stated reason "
                "for reuse requires professional confirmation."
            ),
            evidence=(
                f"Reason given: '{patient_reason}'. Even when a medicine is in your "
                "current prescription, reusing it for unclear reasons requires verification."
            ),
            recommended_next_step=(
                "Contact your prescribing doctor or pharmacist to confirm whether "
                "you should restart this medicine and at what dose."
            ),
            confidence=round(id_confidence, 2),
            details={'lookup': lookup, 'rx_comparison': rx},
        )

    # ------------------------------------------------------------------ #
    # 7. GREEN — exact match in current discharge prescription            #
    # ------------------------------------------------------------------ #
    if rx['found_exact'] and not high_risk_reason:
        matched = rx['matched_current_medicine'] or medicine_name
        return SafetyResult(
            status=STATUS_GREEN,
            medicine=medicine_label,
            reason="Matches your current medication list.",
            evidence=(
                f"'{medicine_name}' was found in your discharge prescription "
                f"(matched: '{matched}'). "
                f"Active ingredient: {lookup['active_ingredient']}."
            ),
            recommended_next_step=(
                "This medicine appears to be part of your current plan. "
                "Confirm the correct dose and timing with your pharmacist or the discharge instructions."
            ),
            confidence=round(id_confidence, 2),
            details={'lookup': lookup, 'rx_comparison': rx},
        )

    # ------------------------------------------------------------------ #
    # 8. GREEN + high-risk reason — downgrade to YELLOW                   #
    # ------------------------------------------------------------------ #
    if rx['found_exact'] and high_risk_reason:
        return SafetyResult(
            status=STATUS_YELLOW,
            medicine=medicine_label,
            reason=(
                "This medicine matches your discharge plan, but the reason "
                "for reuse warrants additional verification."
            ),
            evidence=(
                f"Reason given: '{patient_reason}'. "
                f"Medicine '{medicine_name}' is in your current prescription, "
                "but this reason introduces uncertainty about the appropriateness of reuse."
            ),
            recommended_next_step=(
                "Verify with your doctor or pharmacist whether restarting "
                "this medicine is appropriate given your current health status."
            ),
            confidence=round(id_confidence * 0.85, 2),
            details={'lookup': lookup, 'rx_comparison': rx},
        )

    # ------------------------------------------------------------------ #
    # 9. YELLOW — medicine is in dataset but NOT in current plan          #
    # ------------------------------------------------------------------ #
    if not current_medications:
        # No prescription has been saved
        return SafetyResult(
            status=STATUS_YELLOW,
            medicine=medicine_label,
            reason="Medicine identified, but no discharge prescription has been uploaded for comparison.",
            evidence=(
                f"'{medicine_name}' was found in the demo dataset "
                f"(category: {lookup['category']}), "
                "but no discharge prescription is available to compare against."
            ),
            recommended_next_step=(
                "Upload your discharge prescription first, then re-run this check. "
                "Do not take this medicine until it has been compared with your current plan."
            ),
            confidence=round(id_confidence * 0.7, 2),
            details={'lookup': lookup, 'rx_comparison': rx},
        )

    # Medicine is in dataset, prescription is uploaded, but medicine is not in plan
    return SafetyResult(
        status=STATUS_YELLOW,
        medicine=medicine_label,
        reason=(
            "This medicine was identified, but it does not appear in "
            "your current discharge prescription."
        ),
        evidence=(
            f"'{medicine_name}' (active ingredient: {lookup['active_ingredient']}) "
            "was not found in your discharge medication list."
        ),
        recommended_next_step=(
            "Ask your doctor or pharmacist whether it is appropriate to take this "
            "medicine alongside your current discharge plan."
        ),
        confidence=round(id_confidence * 0.75, 2),
        details={'lookup': lookup, 'rx_comparison': rx},
    )


# ---------------------------------------------------------------------------
# Convenience wrapper for the Flask route layer
# ---------------------------------------------------------------------------

def evaluate_from_session(medicine_check: dict) -> SafetyResult:
    """
    Convenience wrapper that reads the session dict already built by the
    medicine route and calls run_safety_check.
    """
    current_rx = medicine_check.get('prescription_text', '')
    current_medications = [
        line.strip().lstrip('0123456789.-) ')
        for line in current_rx.splitlines()
        if line.strip()
    ] if current_rx else []

    ocr_conf = None
    lookup = medicine_check.get('lookup', {})
    if lookup.get('ocr_confidence') is not None:
        ocr_conf = lookup['ocr_confidence']

    return run_safety_check(
        medicine_name=medicine_check.get('medicine_name', ''),
        strength=medicine_check.get('strength', ''),
        patient_reason=medicine_check.get('reason', ''),
        current_medications=current_medications,
        ocr_confidence=ocr_conf,
    )
