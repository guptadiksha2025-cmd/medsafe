# MedSafe — Check Before You Take

> **Patient-Facing Post-Discharge Medication Safety Checkpoint**  
> *Compare an old medicine found at home with your current discharge medication plan before considering reuse.*

---

## 📌 Project Overview

**MedSafe** is a patient-facing digital safety checkpoint designed to prevent accidental medication duplication, adverse reactions, and unsafe reuse after hospital discharge. When patients return home with a newly revised discharge prescription, they frequently encounter leftover medicines in their home cabinets and wonder whether they should or can take them. 

MedSafe compares the old medicine against the patient's active discharge medication plan using a **deterministic, rule-based Safety Decision Engine**, OCR package scanning, and plain-language AI explanation assistance.

---

## ⚠️ The Problem

Post-discharge medication reconciliation is one of the most critical vulnerability windows in patient care:
- Patients leave the hospital with modified drug regimens, brand substitutions, or discontinued medications.
- Older prescription bottles and strips remain in household medicine cabinets.
- When familiar or new symptoms arise, patients may consider reusing old medicines without realizing that:
  1. The drug may have been intentionally stopped by the physician.
  2. The new discharge plan may already contain the same active ingredient under a different brand name (duplicate therapy risk).
  3. Reusing old stock without clinical guidance can lead to toxicity, counteraction, or dosage errors.

---

## 💡 The Solution

MedSafe bridges this home transition gap by serving as a **dedicated decision-support checkpoint**:
1. **Captures Current Discharge Context**: The patient uploads or confirms their latest hospital discharge prescription.
2. **Identifies the Old Medicine**: The patient scans the physical packaging or enters details manually.
3. **Understands Patient Intent**: MedSafe asks *why* the patient is considering taking it (e.g., leftover from before, recurring symptoms, third-party recommendation).
4. **Applies Deterministic Safety Logic**: The Safety Decision Engine compares identities, active ingredients, strengths, and intents to produce a standardized outcome.
5. **Provides Escalation & Next Steps**: When uncertainty or duplicate risks are detected, the system immediately directs the patient to pharmacist or physician consultation.

---

## 🚀 Key Innovation: Four-Part Safety Context

Generic pill identifiers, interaction checkers, and e-commerce platforms evaluate drugs in isolation. MedSafe introduces a structured four-part safety context:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MEDSAFE SAFETY CONTEXT                        │
├───────────────────────────┬─────────────────────────────────────────────┤
│ 1. Patient Intent         │ Why is the patient considering reuse?       │
│ 2. Medicine Provenance    │ Is this an old leftover, new OTC, or saved? │
│ 3. Current Rx Context     │ Does it match or conflict with active plan? │
│ 4. Confidence-Aware Level │ Is identification high-confidence or fuzzy? │
└───────────────────────────┴─────────────────────────────────────────────┘
```

---

## ✨ Key Features

- **Discharge Prescription Ingestion**: Upload digital PDF discharge summaries or take photos (PNG, JPG, WebP) with instant direct text extraction & Tesseract OCR.
- **Native PDF Document Support**: Reads hospital digital PDF summaries directly via PyMuPDF/pypdf and renders scanned PDF pages for OCR.
- **Patient Verification & Review**: Review, edit, add, or remove extracted medications before saving.
- **Dual Old Medicine Input**: Packaging photo/PDF scanning or direct manual name/strength entry.
- **Intent Capture**: 5 structured rationale options assessing reuse context.
- **Controlled Demo Dataset**: Standardized database covering active ingredients, categories, strengths, and brand aliases.
- **Deterministic Safety Decision Engine**: Unbiased Python rule engine delivering four status categories (`GREEN`, `YELLOW`, `RED`, `GRAY`).
- **Confidence Meter**: Clearly banded confidence (`High`, `Medium`, `Low`) without claiming clinical certainty.
- **Assistive AI Explanation**: Plain-language translation powered by LLM API (with full deterministic fallback if offline).
- **Professional Escalation Workflow**: Interactive escalation toolkits for Pharmacist Discussion, Physician Consultation, and Printable Summaries.
- **One-Click Demo Mode (`/demo`)**: Instant access to 4 live test scenarios running through the real backend engine.

---

## 🏛️ System Architecture

```
                               ┌─────────────────────────────┐
                               │ Hospital Discharge Rx Image │
                               └──────────────┬──────────────┘
                                              ▼
                                   [ Tesseract OCR Engine ]
                                              ▼
                               ┌─────────────────────────────┐
                               │  Prescription Review & Edit │
                               └──────────────┬──────────────┘
                                              ▼
┌───────────────────────────┐      ┌─────────────────────────┐
│   Old Medicine Package    │      │  Active Discharge Plan  │
└─────────────┬─────────────┘      └────────────┬────────────┘
              ▼                                 │
   [ OCR / Manual Entry ]                       │
              ▼                                 │
┌───────────────────────────┐                   │
│   Patient Reuse Reason    │                   │
└─────────────┬─────────────┘                   │
              ▼                                 │
┌───────────────────────────┐                   │
│ Medicine Dataset Lookup   │                   │
│ (Brand & Active Ingred.)  │                   │
└─────────────┬─────────────┘                   │
              │                                 │
              └───────────────┬─────────────────┘
                              ▼
             ┌─────────────────────────────────┐
             │  Deterministic Safety Engine    │
             │   (Python Rule-Based Engine)    │
             └────────────────┬────────────────┘
                              ▼
            ┌───────────────────────────────────┐
            │  Status: GREEN / YELLOW / RED /   │
            │          GRAY + Confidence        │
            └─────────────────┬─────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
         [ AI Explanation Layer ]   [ Fallback Engine ]
                    └─────────┬─────────┘
                              ▼
            ┌───────────────────────────────────┐
            │     Patient-Facing Result Page    │
            │  • Verdict Banner  • Evidence     │
            │  • Next Steps      • Escalation   │
            └───────────────────────────────────┘
```

---

## 🚦 The Four Standardized Safety Scenarios

MedSafe evaluates comparisons into exactly four statuses:

| Status | Category Label | Meaning & Evaluation Criteria |
|:---:|:---|:---|
| **`GREEN`** | **CURRENT PLAN MATCH** | The medicine is identified and matches an item in the active discharge plan. |
| **`YELLOW`** | **VERIFY BEFORE TAKING** | The medicine is identified, but is not part of the active discharge plan or context requires verification. |
| **`RED`** | **PROFESSIONAL REVIEW REQUIRED** | A defined concern is detected, such as duplicate active ingredients or unsafe reuse intent. |
| **`GRAY`** | **UNABLE TO VERIFY** | Information is insufficient to confidently identify the medicine. Manual verification required. |

---

## 🛠️ Technology Stack

- **Frontend**: HTML5, Modern CSS3 (Inter Typography, Healthcare Tokens), Vanilla JavaScript (Drag & Drop, Step Animations), Bootstrap 5.3.3, Bootstrap Icons.
- **Backend**: Python 3.10+, Flask 3.0.3 (Blueprints architecture).
- **OCR Engine**: Tesseract OCR & Pillow (PIL) image pre-processing.
- **AI / LLM Assistance**: Google Gemini REST API (Assistive plain-language layer with deterministic fallback).
- **Database & Data**: SQLite & JSON-based controlled demo medication dataset (`data/medicines.json`).
- **Testing**: Python unit & integration test suites.

---

## 📦 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/medsafe.git
cd medsafe
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` if you wish to configure optional LLM explanation keys:
```ini
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=your-secure-secret-key
DATABASE_PATH=database/medsafe.db

# Optional: Google Gemini API key for assistive explanations
LLM_API_KEY=
```
*(Note: If `LLM_API_KEY` is left blank, MedSafe runs completely offline using its built-in standard explanation engine).*

---

## 🏃 Running the Application

Start the local Flask development server:
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🧪 Running Automated Tests

Run the comprehensive test runner covering all normalization, Safety Engine rules, AI fallbacks, and Flask routes:
```bash
python -X utf8 tests/test_all.py
```
Or run individual test modules:
```bash
python -X utf8 tests/test_medicine_service.py
python -X utf8 tests/test_safety_engine.py
python -X utf8 tests/test_ai_service.py
```

---

## 🎬 2–3 Minute Hackathon Demo Video Script

Follow this structured storyline for your presentation or demo video:

| Time | Scene | Action & Narration |
|:---|:---|:---|
| **0:00 – 0:30** | **The Post-Discharge Dilemma** | Show Landing Page (`/`). Explain: *“A patient leaves the hospital with a new prescription. At home, they find an older medicine strip and wonder: Should I take this? MedSafe is their safety checkpoint before they decide.”* |
| **0:30 – 1:00** | **Step 1: Current Prescription** | Click **Start Medication Check**. Upload or review discharge prescription (`Amoxicillin 500mg, Pantoprazole 40mg`). Demonstrate OCR/review tools and click **Save & Continue**. |
| **1:00 – 1:45** | **Step 2: Check Old Medicine** | On `/medicine/check`, enter or scan the old medicine (`Augmentin 625mg`) and select reason (*"It was prescribed to me before"*). Click **Check Medicine** to trigger the animated processing checkpoint. |
| **1:45 – 2:30** | **The Result & Decision Engine** | Show the **RED: Professional Review Required** result. Highlight that MedSafe caught an **active ingredient overlap** (*Augmentin shares Amoxicillin*). Point out the confidence score, assistive explanation, and click **Ask a Pharmacist** to show the escalation toolkit. |
| **2:30 – 3:00** | **Demo Mode Showcase** | Navigate to `/demo` to show the 4 live scenarios (`GREEN`, `YELLOW`, `RED`, `GRAY`). Click any scenario to demonstrate that the engine evaluates in real-time. |

---

## 🔒 Security, Trust & Ethics

- **No Hard-coded Secrets**: All configuration is isolated in environment variables.
- **Privacy First**: Only minimal medication token context is transmitted to the AI explanation layer. No personal patient identifiers or health records are transmitted.
- **Safe File Uploads**: File extensions are restricted to approved image types with randomized UUIDs to prevent file overwrites or execution attacks.
- **Strict Clinical Boundary**: MedSafe strictly maintains decision-support language and never claims *"100% safe"* or presumes physician authority.

---

## 📋 Limitations & Future Scope

- **Demo Dataset Scope**: Uses a controlled 20-record demonstration dataset. Future versions can connect to RxNorm, FDA NDC, or national formulary APIs.
- **Polypharmacy Interactions**: Currently checks for exact matches and active ingredient overlaps. Multi-drug interaction matrix integration is planned for clinical phase 2.
- **EHR Integration**: Future scope includes SMART on FHIR integration directly with hospital discharge portals.

---

## ⚖️ Safety Disclaimer

> **MedSafe is a medication decision-support prototype. It does not diagnose, prescribe, or replace professional medical advice.**  
> Always verify all medication questions with a licensed physician or pharmacist before taking any medication.
