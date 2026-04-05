import json
import os
from typing import Optional

import anthropic
import json_repair
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_MODEL = "claude-sonnet-4-6"
# Long clinical notes + revised_hpi often exceed 2k output tokens; truncated JSON causes parse errors.
_DEFAULT_MAX_TOKENS = 8192


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


def _strip_markdown_json(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.rsplit("```", 1)[0].strip()
    return s


def _inner_json_object(s: str) -> str:
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end <= start:
        return s
    return s[start : end + 1]


def _parse_llm_json(raw: str) -> dict:
    s = _strip_markdown_json(raw)
    inner = _inner_json_object(s)
    attempts = []
    for payload in (inner, s):
        if payload in attempts:
            continue
        attempts.append(payload)
        try:
            result = json.loads(payload)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    try:
        repaired = json_repair.loads(inner)
        if isinstance(repaired, dict):
            return repaired
    except Exception:
        pass
    try:
        repaired = json_repair.loads(s)
        if isinstance(repaired, dict):
            return repaired
    except Exception:
        pass

    raise ValueError(
        "Model returned invalid or incomplete JSON (often unescaped quotes or output cut off mid-field). "
        "Try regenerating, shorten the notes, or raise ANTHROPIC_MAX_TOKENS."
    )

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
  "revised_hpi": "A 47-year-old man with a recent diagnosis of diabetes who had started metformin and Jardiance presented to the emergency department after one day of nausea, vomiting, inability to sleep, and difficulty taking deep breaths. In the emergency department, he was described as tachycardic and exhibiting Kussmaul breathing. Laboratory evaluation demonstrated large serum and urine ketones with severe metabolic acidosis, including arterial pH 7.20, bicarbonate 7.4 millimoles per liter, and serum carbon dioxide less than 7 millimoles per liter. Serum glucose was 93 mg/dL, in the normal range. Emergency physicians documented euglycemic diabetic ketoacidosis in the setting of recent Jardiance use. In the emergency department he received bicarbonate, three liters of normal saline, and was started on an insulin infusion after repeated reassessments. Taken together, the documented severe acidosis with ketosis, escalation of emergency department treatment to continuous intravenous therapy, critical care involvement, and planned intensive care unit-level management supported the decision for inpatient admission rather than discharge or observation.",
  "follow_up_questions": []
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
- **No fabrication:** Do not state age, **patient sex or gender**, vitals, labs, medications, allergies, past medical history, timing, staff actions, or disposition unless they appear in the ER/H&P notes or in the CLINICIAN-PROVIDED SUPPLEMENT below. Do not "fill in" plausible but undocumented details to make the narrative sound complete.
- **Inference:** You may only draw **clinical inferences that chain documented data** (e.g. acidosis from documented pH and bicarbonate together). Do not infer **patient-specific** facts that are not written or clearly implied by the text (e.g. do not guess age, comorbidities, or home medications if absent).
- **Glucose vs acid–base terminology (general):** **Euglycemic** and **euglycemic range** refer **only** to **blood glucose**. They do **not** apply to pH, bicarbonate, pCO₂, anion gap, or the words **acidosis** / **metabolic acidosis**. Do **not** write that acidosis or a pH value is **"in the euglycemic range"** or otherwise mix glucose vocabulary with acid–base results. Describe acid–base using the values and terms the chart provides; describe glucose in a **separate sentence** (not a trailing clause glued on with **while**, **whereas**, **although**, or **yet**).
- **Acid–base vs glucose in narrative (Revised HPI and prose):** If the chart documents both **metabolic acidosis / pH / bicarbonate / ketones** and **serum glucose**, use **at least two sentences** — finish the acid–base and ketone picture first, **then** state glucose (e.g. "Serum glucose was 93 mg/dL."). Do **not** write single-sentence patterns like "severe metabolic acidosis with pH … and bicarbonate …, **while** serum glucose was …" — that fuses two clinical domains and invites the "euglycemic acidosis" wording error.
- **Named syndromes (general):** Do **not** infer a specific syndrome (e.g. euglycemic DKA) from **one** isolated lab such as a normal glucose. Use a named diagnosis in narrative or lists **only** if the **source notes** use that language or document the full clinical picture the label implies. If the notes say **DKA** without **euglycemic**, do **not** upgrade the label to euglycemic DKA unless documentation supports it.
- **Multi-lab sentences:** When ketones, acid–base abnormalities, and glucose all appear in the notes, keep **domains distinct**: ketones and acidosis belong together; glucose is **not** evidence of acidosis and should not be phrased as if pH "were euglycemic." Paraphrase the chart in your own words; do **not** copy a fixed template from the few-shot example verbatim when a different structure fits the note equally well.
- **Distinct results and terms (do not fuse):** Whenever the chart lists **separate** findings—labs, vitals, impressions, diagnoses, or named tests on **different lines** or under **different labels**—**do not** collapse them into one paraphrase that **changes meaning**, **drops a documented value**, **invents a single merged number**, **blurs two different tests or concepts**, or **relabels one finding with another’s wording**. **Each** item should remain **traceable** to a specific part of the source (value, inequality, unit, name). If the note gives two distinct results, your narrative should **preserve that separation** (e.g. two clauses or sentences) unless the chart itself ties them together in one phrase.
- **When something is missing:** Say "not documented" or "unknown" in narrative fields where appropriate; add a bullet to **uncertainties** instead of guessing. Keep **key_findings** and lists limited to what the notes support; use fewer items rather than padding with invented content.
- **Revised HPI:** Build only from documented facts and allowed inferences above. If critical facts are missing, write a shorter, honest narrative that does not invent them—do not fabricate demographics or labs to satisfy the MCG narrative shape.
- Use precise medical language and **quote or paraphrase values exactly as documented** when present.
- The Revised HPI must logically support the disposition **only to the extent supported by the notes**.
- Sentence structure when data exists: demographics (if documented) → presentation → objective findings → impression → ED course → admission rationale.
- For each MCG criterion you claim is met, the cited value or finding must appear in the source notes.
- Disposition recommendation: "Admit", "Observe", "Discharge", or "Unknown" — use **"Unknown"** if disposition is not clear from the notes.

MANDATORY DOCUMENTATION CHECKLIST (do not skip — scan the full ER and H&P text):
1. **Patient age**
   - Look for an explicit age (e.g. "34 y/o", "age 47", "47-year-old", numeric age in HPI/demographics). If **no age appears anywhere** in the combined notes:
     - You **MUST** add to **uncertainties**: "Patient age not documented in the source notes."
     - You **MUST NOT** write a specific age or age range in **chief_complaint**, **hpi_summary**, or **revised_hpi** (use neutral phrasing such as "the patient" or "an adult patient" without a number).
     - You **MUST** include **"What is the patient's age?"** (or equivalent) as the **first** entry in **follow_up_questions**, and you **MUST** add a **second** follow-up question for the next most critical gap (e.g. blank disposition below, or confirming disposition intent).
   - If age appears in either note, do not add the age-not-documented uncertainty.

2. **Patient sex / gender**
   - Look for explicit documentation (e.g. male/female, man/woman, M/F, "34 y/o male", pronouns tied to the patient in demographics). If **no sex or gender appears anywhere** in the combined notes:
     - You **MUST** add to **uncertainties**: "Patient sex or gender not documented in the source notes."
     - You **MUST NOT** state the patient's sex or gender in **chief_complaint**, **hpi_summary**, or **revised_hpi** (use neutral phrasing: "the patient", "they" if consistent with your style, or repeat diagnosis-focused language without gendered labels).
     - You **MUST** include **"What is the patient's sex or gender?"** (or equivalent) in **follow_up_questions** — **priority:** if age is **also** missing per (1), put the **age** question **first** and this **second**; if age **is** documented but sex/gender is not, put this question **first** in **follow_up_questions**, and add a **second** question for the next most critical gap (e.g. disposition per below).
   - If sex/gender appears in either note, do not add the sex/gender-not-documented uncertainty.

3. **Disposition and impression (structured fields vs narrative)**
   - If the ER note shows **blank or empty IMPRESSION and/or DISPOSITION** sections (or clearly unfilled lines), you **MUST** add an uncertainty stating that those structured fields were not completed in the source, **and** briefly state whether disposition or disposition intent appears elsewhere (e.g. MDM, Assessment/Plan, "Admit ICU").
   - If **no** disposition or disposition intent appears **anywhere** in the combined ER+H&P text, set **disposition_recommendation** to **"Unknown"**, add an uncertainty that disposition was not documented, and include a follow-up question asking for the documented disposition or disposition intent.
   - Do **not** invent a disposition in **revised_hpi** that is not supported by the text; if you infer from MDM/plan, say so explicitly (e.g. "Disposition header blank; plan documents ICU admission").

4. **follow_up_questions length**
   - Whenever patient age is missing per (1), **follow_up_questions must contain at least two questions** (age + one other critical gap — use sex/gender per (2) if that is also missing, otherwise disposition or the next critical gap). Never return an empty follow_up_questions if age was not documented.
   - Whenever patient sex/gender is missing per (2) but age **is** documented, **follow_up_questions must contain at least two questions** (sex/gender **first**, then another critical gap such as disposition). Never return an empty follow_up_questions if sex/gender was not documented while age was present.

{CASE_A_EXAMPLE}

JSON OUTPUT RULES (required):
- Respond with exactly one JSON object and nothing else (no markdown fences, no commentary).
- In every string value, escape internal double-quotes as backslash-quote (\\"). Never leave a string open-ended.
- Prefer short clause-style sentences in revised_hpi so the object stays valid; avoid pasting raw chart text with quotes inside a JSON string.
- In **revised_hpi**, never join acid–base/ketone findings and serum glucose with **while** / **whereas** / **although** in one sentence — separate sentences (see TRANSFORMATION RULES).
- Include all keys through follow_up_questions; the JSON must be complete.

FOLLOW-UP QUESTIONS (follow_up_questions):
- **Prefer asking over guessing** — never fabricate age, sex/gender, or disposition; see MANDATORY DOCUMENTATION CHECKLIST above.
- **When age is not documented:** you must use a **non-empty** follow_up_questions array with **at least two** questions (first asks for age; second asks for sex/gender if that is also missing, otherwise disposition or another critical gap).
- **When age is documented but sex/gender is not:** you must use a **non-empty** follow_up_questions array with **at least two** questions (first asks for sex/gender; second asks for another critical gap such as disposition).
- **When age is documented** and sex/gender is documented but notes are otherwise critically sparse (multiple pillars missing, no key labs, etc.), you may still use follow_up_questions with **at least two** items, or rely on **uncertainties** if a single non-critical fact is missing.
- Questions must request **missing factual data**, not editorial opinion.
- If a "CLINICIAN-PROVIDED SUPPLEMENT" section exists below, do not ask for information already answered there.

OUTPUT FORMAT — respond ONLY with valid JSON, no prose before or after:
{{
  "chief_complaint": "...",
  "hpi_summary": "...",
  "key_findings": ["...", "..."],
  "suspected_conditions": ["...", "..."],
  "disposition_recommendation": "Admit | Observe | Discharge | Unknown",
  "admission_criteria_met": ["...", "..."],
  "uncertainties": ["...", "..."],
  "revised_hpi": "...",
  "follow_up_questions": []
}}
"""


def generate_structured_output(
    er_note: Optional[str],
    hp_note: Optional[str],
    supplemental_block: Optional[str] = None,
) -> dict:
    """
    Call Claude claude-sonnet-4-6 with few-shot prompt to generate structured clinical output.
    Returns parsed JSON dict (may include follow_up_questions).
    """
    parts = []
    if er_note and er_note.strip():
        parts.append(f"=== ER NOTE ===\n{er_note.strip()}")
    if hp_note and hp_note.strip():
        parts.append(f"=== H&P NOTE ===\n{hp_note.strip()}")
    if supplemental_block and supplemental_block.strip():
        parts.append(
            "=== CLINICIAN-PROVIDED SUPPLEMENT (answers to missing details) ===\n"
            + supplemental_block.strip()
        )

    if not parts:
        raise ValueError("At least one clinical note (ER or H&P) must be provided.")

    user_message = (
        "Please analyze the following clinical note(s) and generate the structured output:\n\n"
        + "\n\n".join(parts)
    )

    model = os.getenv("ANTHROPIC_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    max_tokens = _DEFAULT_MAX_TOKENS
    raw_mt = os.getenv("ANTHROPIC_MAX_TOKENS", "").strip()
    if raw_mt:
        try:
            max_tokens = max(1024, min(32768, int(raw_mt)))
        except ValueError:
            pass
    client = _get_client()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
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
    try:
        result = _parse_llm_json(raw)
    except ValueError as e:
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise ValueError(
                "Model output was truncated (hit max_tokens) before JSON completed. "
                f"Raise ANTHROPIC_MAX_TOKENS (currently {max_tokens}) or shorten the input notes."
            ) from e
        raise

    # Normalize disposition value
    disp = result.get("disposition_recommendation", "Unknown")
    valid_dispositions = {"Admit", "Observe", "Discharge", "Unknown"}
    if disp not in valid_dispositions:
        disp = "Unknown"
    result["disposition_recommendation"] = disp

    fu = result.get("follow_up_questions")
    if not isinstance(fu, list):
        result["follow_up_questions"] = []
    else:
        result["follow_up_questions"] = [str(x).strip() for x in fu if str(x).strip()]

    return result
