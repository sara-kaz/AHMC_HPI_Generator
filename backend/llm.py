import json
import os
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_MODEL = "claude-sonnet-4-6"


def _normalize_api_key(raw: Optional[str]) -> str:
    key = (raw or "").strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
        key = key[1:-1].strip()
    return key


def _get_client() -> anthropic.Anthropic:
    key = _normalize_api_key(os.getenv("ANTHROPIC_API_KEY"))
    if not key:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. Add it to backend/.env and restart the API server."
        )
    return anthropic.Anthropic(api_key=key)


def _assistant_text(response: anthropic.types.Message) -> str:
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    if not parts:
        raise ValueError("Model returned no text content blocks; cannot parse JSON.")
    return "\n".join(parts).strip()


def _parse_llm_json(raw: str) -> dict:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.rsplit("```", 1)[0].strip()
    try:
        result = json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start < 0 or end <= start:
            raise
        result = json.loads(s[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError("Model output JSON was not an object.")
    return result

# ─────────────────────────────────────────────────────────────────────────────
# MCG Admission Criteria (condensed from provided guideline)
# ─────────────────────────────────────────────────────────────────────────────
MCG_CRITERIA = """
MCG INPATIENT ADMISSION CRITERIA — DIABETES (ISC M-130, 30th Ed.)

Admission is indicated for ONE OR MORE of the following:

1. DIABETIC KETOACIDOSIS (DKA) — ALL of the following must be met:
   a. Glucose ≥200 mg/dL OR any glucose with prior DM history OR euglycemic DKA risk factors
      (SGLT2 inhibitor use, pregnancy, starvation, heavy alcohol, chronic liver/renal disease,
      sepsis, ketogenic diet, pancreatitis)
   b. Ketonuria/ketonemia: serum beta-hydroxybutyrate ≥3.0 mmol/L, or 2+ urine ketones
   c. Acidosis: arterial/venous pH <7.30, serum bicarbonate ≤18 mEq/L, or anion gap >12

   INPATIENT (vs. observation) if ANY of:
   - pH ≤7.25 or bicarb <15 mEq/L
   - Altered mental status
   - Hypotension
   - AKI (creatinine ≥2× baseline)
   - Persistent dehydration despite observation
   - Unable to maintain oral hydration
   - Significant electrolyte abnormality persisting
   - No known outpatient insulin regimen / newly diagnosed
   - Etiology unclear (not missed insulin doses)
   - Continuous IV insulin infusion required
   - ICU-level monitoring required

2. HYPERGLYCEMIC HYPEROSMOLAR STATE (HHS):
   - Glucose >600 mg/dL AND serum osmolality >320 mOsm/kg

3. HYPERGLYCEMIA REQUIRING INPATIENT CARE:
   - Hemodynamic instability
   - Severe/persistent AMS
   - Inability to maintain oral hydration
"""

# ─────────────────────────────────────────────────────────────────────────────
# Case A — Few-Shot Reference Example
# ─────────────────────────────────────────────────────────────────────────────
CASE_A_EXAMPLE = """
=== FEW-SHOT REFERENCE: CASE A ===

INPUT — ER NOTE:
Chief Complaint: Diabetes issue
HPI: 47-year-old male with recent diagnosis of diabetes, on Jardiance and metformin, presents to ED
for 1 day history of inability to take deep breaths, sleep well, nausea, and vomiting.
Physical Exam: Patient is alert, awake, talking in complete sentences. Kussmaul breathing noted.
Tachycardic. Vitals: BP 130/92 → 105/67 (trending down).
Labs: KETONES LARGE (serum); Urine KETONE 60; ABG: pH 7.200, HCO3 7.4 mmol/L, pCO2 19.4 mmHg;
CMP: CO2 <7, Glucose 93 mg/dL; CBC without leukocytosis.
Impression: Euglycemic DKA. Critical care time 35 minutes.
Course: Given bicarbonate, 3L normal saline, started on insulin drip. Discussed with hospitalist.
Disposition: Admit to ICU.

INPUT — H&P NOTE:
HPI: 47M recently diagnosed diabetes, started on metformin and Jardiance. Became increasingly restless
unable to sleep. Yesterday unable to tolerate PO, had 1 episode of vomiting. This morning several
episodes of vomiting and ongoing nausea, came to ED. In ED: euglycemic DKA, bicarb <7, pH 7.2, glucose 93.
Admission requested for euglycemic DKA in the setting of new Jardiance use.
Physical Exam: Lethargic, ill-appearing, A&Ox3. CTA bilaterally. S1S2 RRR. Abdomen soft, non-tender.
Labs: KETONES LARGE, ABG pH 7.200, HCO3 7.4 mmol/L, CO2 <7, glucose 93.
Assessment/Plan: Euglycemic DKA — ICU admission, insulin drip, IV fluids, BMP q4h, fingerstick q1h.

EXPECTED OUTPUT:
{
  "chief_complaint": "Euglycemic diabetic ketoacidosis in setting of new SGLT2 inhibitor (Jardiance) use",
  "hpi_summary": "A 47-year-old man with recently diagnosed diabetes who was started on metformin and Jardiance presented to the emergency department after one day of nausea, vomiting, restlessness, inability to sleep, and difficulty breathing. Symptoms progressed from mild nausea to multiple vomiting episodes before prompting emergency evaluation.",
  "key_findings": [
    "Tachycardia on exam",
    "Kussmaul breathing pattern",
    "Serum ketones LARGE; urine ketone 60",
    "Arterial pH 7.20 (severe acidosis)",
    "Serum bicarbonate 7.4 mmol/L (critically low)",
    "CO2 <7 mmol/L",
    "Glucose 93 mg/dL (euglycemic — normal range)",
    "Recent SGLT2 inhibitor (Jardiance) initiation",
    "Critical care time 35 minutes in ED",
    "Escalation to insulin drip, bicarbonate, 3L IV normal saline"
  ],
  "suspected_conditions": [
    "Euglycemic diabetic ketoacidosis (SGLT2 inhibitor-induced)",
    "Severe metabolic acidosis"
  ],
  "disposition_recommendation": "Admit",
  "admission_criteria_met": [
    "DKA with pH 7.20 (<7.30) — meets acidosis criterion",
    "Serum bicarbonate 7.4 mEq/L (<15 mEq/L) — meets severe DKA criterion for inpatient over observation",
    "Euglycemic DKA risk factor: active SGLT2 inhibitor use (Jardiance)",
    "Large serum and urine ketones — meets ketonemia/ketonuria criterion",
    "Continuous IV insulin infusion required",
    "ICU-level monitoring planned (fingerstick q1h, BMP q4h)"
  ],
  "uncertainties": [
    "Outpatient insulin regimen not clearly established (newly diagnosed)",
    "Long-term diabetes management plan pending"
  ],
  "revised_hpi": "A 47-year-old man with a recent diagnosis of diabetes who had started metformin and Jardiance presented to the emergency department after one day of nausea, vomiting, inability to sleep, and difficulty taking deep breaths. In the emergency department, he was described as tachycardic and exhibiting Kussmaul breathing. Laboratory evaluation demonstrated large serum and urine ketones with severe metabolic acidosis, including arterial pH 7.20, bicarbonate 7.4 millimoles per liter, and serum carbon dioxide less than 7 millimoles per liter, while serum glucose remained in the normal range. Emergency physicians documented euglycemic diabetic ketoacidosis in the setting of recent Jardiance use. In the emergency department he received bicarbonate, three liters of normal saline, and was started on an insulin infusion after repeated reassessments. Taken together, the documented severe acidosis with ketosis, escalation of emergency department treatment to continuous intravenous therapy, critical care involvement, and planned intensive care unit-level management supported the decision for inpatient admission rather than discharge or observation."
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a clinical documentation specialist who transforms unstructured emergency and inpatient clinical notes into structured summaries and admission-supporting revised HPI narratives.

Your task is to:
1. Extract key clinical information from the provided notes (ER Note and/or H&P)
2. Identify which MCG admission criteria are met
3. Generate a structured summary with all required fields
4. Write a Revised HPI that clearly supports the admission decision

ADMISSION CRITERIA REFERENCE:
{MCG_CRITERIA}

TRANSFORMATION RULES:
- Never invent facts not present in the source notes
- Use precise medical language and values from the notes
- The Revised HPI must logically build toward and support the disposition decision
- Sentence structure: Patient demographics → Presenting symptoms → Objective findings → Diagnosis/Impression → Treatment in ED → Summary of why inpatient admission is warranted
- For each MCG criterion met, cite the specific lab value or finding
- If information is missing or uncertain, explicitly note it
- Disposition recommendation: "Admit", "Observe", "Discharge", or "Unknown"

{CASE_A_EXAMPLE}

OUTPUT FORMAT — respond ONLY with valid JSON, no prose before or after:
{{
  "chief_complaint": "...",
  "hpi_summary": "...",
  "key_findings": ["...", "..."],
  "suspected_conditions": ["...", "..."],
  "disposition_recommendation": "Admit | Observe | Discharge | Unknown",
  "admission_criteria_met": ["...", "..."],
  "uncertainties": ["...", "..."],
  "revised_hpi": "..."
}}
"""


def generate_structured_output(er_note: Optional[str], hp_note: Optional[str]) -> dict:
    """
    Call Claude claude-sonnet-4-6 with few-shot prompt to generate structured clinical output.
    Returns parsed JSON dict.
    """
    parts = []
    if er_note and er_note.strip():
        parts.append(f"=== ER NOTE ===\n{er_note.strip()}")
    if hp_note and hp_note.strip():
        parts.append(f"=== H&P NOTE ===\n{hp_note.strip()}")

    if not parts:
        raise ValueError("At least one clinical note (ER or H&P) must be provided.")

    user_message = (
        "Please analyze the following clinical note(s) and generate the structured output:\n\n"
        + "\n\n".join(parts)
    )

    model = os.getenv("ANTHROPIC_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    client = _get_client()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIStatusError as e:
        detail = e.message
        if isinstance(e.body, dict):
            err = e.body.get("error")
            if isinstance(err, dict) and err.get("message"):
                detail = f"{detail} — {err['message']}"
        msg = f"Anthropic API ({e.status_code}): {detail}"
        if e.status_code == 401:
            msg += (
                " — Update ANTHROPIC_API_KEY in backend/.env with a key from "
                "https://console.anthropic.com/settings/keys (no quotes around the value; restart uvicorn after saving)."
            )
        raise RuntimeError(msg) from e

    raw = _assistant_text(response)
    result = _parse_llm_json(raw)

    # Normalize disposition value
    disp = result.get("disposition_recommendation", "Unknown")
    valid_dispositions = {"Admit", "Observe", "Discharge", "Unknown"}
    if disp not in valid_dispositions:
        disp = "Unknown"
    result["disposition_recommendation"] = disp

    return result
