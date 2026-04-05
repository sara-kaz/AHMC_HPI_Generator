# AHMC Clinical HPI Generator

Task: turn messy ER notes and H&P documents into a structured summary plus a Revised HPI that supports admission — delivered through a web app you can try in the browser.

## Know How

**Try the app first (no login):** open **[the live app](https://ahmc-hpi-generator.vercel.app)** → **New Case** → **Load Case B** → **Generate**, then explore the structured fields and Revised HPI. Cases persist for that deployment (SQLite on the server).

**Demo video:** [screen recording — how I use the app](https://drive.google.com/file/d/1r9hDp0ZkflKjfyTF0Novc-kA8HDHwOe4/view?usp=sharing) (Google Drive).

**Run it on your own machine:** clone the repo and follow **[Running locally](#running-locally)** — you need two terminals (FastAPI on port **8000**, Vite on **5173**), an **Anthropic API key** in `backend/.env`, and Node + Python as listed there.

**What to read in this README:** [Live demo & links](#live-demo) (hosted app + demo video) → [What it does](#what-it-does) → [Architecture](#architecture) → [How I structured the clinical note](#how-i-structured-the-clinical-note) → [Testing & prompt iteration](#how-i-checked-the-output) (under *AI tool usage disclosure*) → [AI tool usage disclosure](#ai-tool-usage-disclosure). **[Deployment](#deployment)** is only if you want to host your own copy (not required to use the app).

---

## Live demo


| What                         | Link                                                                                                          |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Web app (use this one)**   | **[https://ahmc-hpi-generator.vercel.app](https://ahmc-hpi-generator.vercel.app)**                            |
| **Demo video** (walkthrough) | [Google Drive — Demo.mov](https://drive.google.com/file/d/1r9hDp0ZkflKjfyTF0Novc-kA8HDHwOe4/view?usp=sharing) |
| OpenAPI / Swagger            | [API `/docs](https://web-production-843a9.up.railway.app/docs)`                                               |
| API base (health: `/health`) | [https://web-production-843a9.up.railway.app](https://web-production-843a9.up.railway.app)                    |


---

## What it does

You paste in an ER note and/or H&P, click generate, and get back:

- A structured breakdown — chief complaint, key findings, suspected diagnoses, and which MCG admission criteria are met
- A Revised HPI written as a coherent narrative that builds toward and supports the admission decision
- Every field is editable in the UI, with a visual distinction between what the model generated and what you changed
- Cases are saved so you can come back and review them
- **Optional clarification path:** if the model returns enough follow-up questions (default **≥2**, tunable via `MIN_FOLLOW_UP_QUESTIONS`), the case moves to `**awaiting_clarification`**, the detail page shows a short form, and `**POST /api/cases/:id/clarify`** resubmits answers as a supplement block for the next generation — optional questions aimed at filling gaps the chart left open. Otherwise, generation completes with status `completed`; thin charts without that threshold still record gaps in `**uncertainties**`.

The **Load Case B** button on the new case page pre-fills the evaluation case from the exercise, so it can be tested immediately.

---

## Architecture

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                        USER BROWSER                             │
    │  React + Vite + Tailwind CSS                                    │
    │  ┌───────────┐ ┌──────────────┐ ┌───────────────────────────┐   │
    │  │ CaseList  │ │ NewCase      │ │ CaseDetail                │   │
    │  │ list + ID │ │ notes + opt. │ │ edit title, structured out│   │
    │  │ search    │ │ manual ID    │ │ regenerate, clarify Q&A   │   │
    │  └───────────┘ └──────────────┘ └───────────────────────────┘   │
    └────────────────────────┬────────────────────────────────────────┘
                             │ REST API (axios)
┌────────────────────────────▼────────────────────────────────────────────┐
│                   FASTAPI BACKEND                                       │
│  Python 3.9+ · Uvicorn · SQLAlchemy · SQLite                            │
│                                                                         │
│  POST /api/cases                  — create case (optional body `id`)    │
│  POST /api/cases/:id/generate     — LLM; may set awaiting_clarification │
│  POST /api/cases/:id/clarify      — answers → regenerate with supplement│
│  PUT  /api/cases/:id              — title, structured_output, edits     │
│  GET  /api/cases                  — list (batched structured reads)     │
│  GET  /api/cases/:id              — one case                            │
│  DELETE /api/cases/:id            — delete (cascades clinical rows)     │
│  POST /api/generate               — ad-hoc JSON only (nothing saved)    │
│  GET  /health                     — liveness                            │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │ Anthropic Python SDK
   ┌────────────────────────▼──────────────────────────────────────────┐
   │              ANTHROPIC API (claude-sonnet-4-6)                    │
   │  System prompt: MCG criteria + Case A few-shot example            │
   │  Model JSON: clinical fields + follow_up_questions; scalars/lists │
   │  → relational tables + Case JSON cache; follow-ups on Case row    │
   └───────────────────────────────────────────────────────────────────┘
```

---

## Tech stack


| Layer       | Choice                                               | Why                                                                                          |
| ----------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| LLM         | Claude claude-sonnet-4-6                             | Strong clinical reasoning; handles the few-shot pattern well                                 |
| Backend     | FastAPI                                              | Quick REST endpoints, plays nicely with the Anthropic Python SDK                             |
| Database    | SQLite + SQLAlchemy                                  | No setup overhead; easy to swap for Postgres later                                           |
| Frontend    | React + Vite + TypeScript                            | TypeScript keeps the structured output types honest across the stack                         |
| Styling     | Tailwind CSS v4                                      | Fast to iterate on without fighting a component library                                      |
| JSON repair | [json-repair](https://pypi.org/project/json-repair/) | LLMs occasionally produce near-valid JSON; this recovers those cases instead of failing hard |


---

## How I structured the clinical note

### Why prompting instead of fine-tuning

Fine-tuning on 2 examples would just memorize them. The model already understands clinical medicine — what it needs is the MCG admission criteria and an example of the exact transformation. So the system prompt does four things:

1. Embeds the relevant MCG ISC Diabetes admission criteria (condensed from the provided guideline PDF)
2. Includes Case A as a complete few-shot example — ER note + H&P in, structured JSON with Revised HPI out
3. Applies **transformation rules** (no fabrication; inference limits; acid–base vs glucose wording; “distinct results” so lines aren’t fused; uncertainties when data are missing; Revised HPI only from documented facts)
4. Applies a **mandatory documentation checklist** (age, sex/gender, disposition/impression) plus **JSON output rules** and **follow_up_questions** rules — implementation lives in `**backend/llm.py`** (`SYSTEM_PROMPT`)

### Prompt structure

This matches how `**generate_structured_output`** in `**llm.py`** builds the Anthropic call: one **system** string and one **user** message.

```
SYSTEM (abridged outline — full text in llm.py):
  - Role + task list (extract notes, map MCG criteria, structured fields, Revised HPI)
  - ADMISSION CRITERIA REFERENCE: embedded MCG Diabetes thresholds (condensed PDF)
  - TRANSFORMATION RULES: no fabrication (including age and patient sex/gender), inference limits,
    glucose vs acid–base wording, named syndromes, multi-lab / distinct-results discipline,
    uncertainties + Revised HPI discipline, disposition enum
  - MANDATORY DOCUMENTATION CHECKLIST: age → sex/gender → disposition/impression;
    required uncertainties and follow_up_questions ordering when demographics or disposition are missing
  - Case A few-shot JSON example (embedded string)
  - JSON OUTPUT RULES (single JSON object, escaping, etc.)
  - FOLLOW-UP QUESTIONS rules (pair with checklist; supplement-aware)

USER (built in code):
  Please analyze the following clinical note(s) and generate the structured output:

  === ER NOTE ===
  <content or omitted if empty>

  === H&P NOTE ===
  <content or omitted if empty>

  === CLINICIAN-PROVIDED SUPPLEMENT (answers to missing details) ===   ← only after POST /clarify
  <formatted answers>
```

If only one note is present, the other block is omitted. The supplement block is appended when the user submits clarification answers, so the model does not re-ask for facts already supplied.

### How the Revised HPI is structured

I read through the sentence-by-sentence breakdown in the Case A reference document and pulled out the pattern:

1. Demographics + what brought them in
2. Objective exam findings in the ED/ER
3. Lab results — with specific values mapped to the MCG thresholds
4. Clinical impression as documented by treating physicians
5. What treatment was escalated to in the ED
6. Why do all of the above justify inpatient admission rather than discharge or observation

### Uncertainty and missing information

The `uncertainties` field is required in every output. The model is told not to invent values — if a lab result or detail isn't in the notes, it flags it rather than fills it in.

**Optional follow-up questions:** we also added `follow_up_questions` so the model can ask targeted questions to help fill those gaps (e.g., missing **age** or **sex/gender** — both treated as crucial when absent — plus unclear disposition). When there are enough of them (see `MIN_FOLLOW_UP_QUESTIONS`**), the app optionally pauses for clarification before a second generation; if not, gaps remain visible under** `uncertainties` and the generation can still complete without the Q&A step.

---

## Structured output fields

These eight fields are what gets persisted in `**clinical_structured_outputs`**, `**clinical_list_items`**, and the denormalized `**cases.structured_output**` cache. The LLM also returns `**follow_up_questions**`; the backend uses it to decide whether to pause for clarification, then strips it before persistence (questions and any `**supplemental_answers**` live on the `**cases`** row instead).


| Field                        | What it captures                                                                                           |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `chief_complaint`            | Primary reason for the ED visit                                                                            |
| `hpi_summary`                | Short narrative of the presenting illness                                                                  |
| `key_findings`               | Objective findings: labs, vitals, exam                                                                     |
| `suspected_conditions`       | Working diagnoses                                                                                          |
| `disposition_recommendation` | Admit / Observe / Discharge / Unknown                                                                      |
| `admission_criteria_met`     | Which MCG criteria are satisfied, with cited values                                                        |
| `uncertainties`              | What's missing or unclear from the notes (complements optional `**follow_up_questions`** for filling gaps) |
| `revised_hpi`                | The full admission-supporting narrative                                                                    |



| Case-level (not in relational clinical tables) | What it captures                                                                   |
| ---------------------------------------------- | ---------------------------------------------------------------------------------- |
| `follow_up_questions`                          | Questions from the last generation when status is `**awaiting_clarification`**     |
| `supplemental_answers`                         | Map of question → answer text, filled when the user submits the clarification form |


---

## Database schema

The structured output is stored in relational tables (not just a JSON blob), with a denormalized JSON column kept in sync for quick reads:


| Table                         | What's in it                                                                                                                                                                                               |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cases`                       | Title, raw `er_note` / `hp_note`, `edited_fields`, `**generation_status`**, `**generation_error`**, `**follow_up_questions**`, `**supplemental_answers**`, denormalized `**structured_output**` JSON cache |
| `clinical_structured_outputs` | One row per case: scalar fields (`chief_complaint`, `hpi_summary`, `disposition_recommendation`, `revised_hpi`)                                                                                            |
| `clinical_list_items`         | One row per bullet: `key_findings`, `suspected_conditions`, `admission_criteria_met`, `uncertainties` (ordered by `sort_order`)                                                                            |


### Case identity

- Each case gets a numeric ID shown in the list and on the detail page
- You can optionally set a specific ID when creating; the API returns 409 if it's already taken
- The case list has a search box that filters by ID

---

## Edit tracking

The UI shows `🤖 AI` on every generated field. Once you edit and save a field, the badge switches to `✏️ Edited` and an amber left border appears. The `edited_fields` array in the database records which fields changed, and the case list shows the count.

---

## Running locally

Use these steps on **macOS, Windows, or Linux** after cloning the repository. You will run **two processes**: the API first, then the web UI.

### Requirements

- Python 3.9+ (3.11+ is smoother for pip)
- Node.js 18+
- Anthropic API key — get one at [console.anthropic.com](https://console.anthropic.com/settings/keys)

### 1. Backend (terminal 1)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install --upgrade pip       # important on Python 3.9 with old pip
pip install -r requirements.txt

cp .env.example .env
# Open .env and add your ANTHROPIC_API_KEY — no quotes, just the raw value

uvicorn main:app --reload --port 8000
```

Leave this running. You should see Uvicorn listening on **8000**. Open **[http://localhost:8000/docs](http://localhost:8000/docs)** to confirm the API loads.

`main.py` lives in `backend/`, so the commands above assume your shell’s current directory is `backend/`. If you see **Could not import module "main"**, you ran uvicorn from the repo root (or another folder). Either `cd backend` first, or from the repo root run:

```bash
python -m uvicorn main:app --app-dir backend --reload --port 8000
```

SQLite data is stored as `**backend/cases.db**` by default (created on first request).

### 2. Frontend (terminal 2)

Open a **second** terminal (keep the backend running). From the repo root:

```bash
cd frontend
npm install
npm run dev
```

Then open **[http://localhost:5173](http://localhost:5173)** in your browser.

In development, Vite **proxies** requests from `/api` to **[http://localhost:8000](http://localhost:8000)** (see `frontend/vite.config.ts`), so you do **not** need `VITE_API_URL` for local dev unless you change ports or call the API from a different host.

### Quick test

1. Open the app → **New Case**
2. Click **Load Case B** — pre-fills the evaluation case from the exercise
3. Click **Generate**
4. Review, edit any fields, save

---

## Deployment

**Reviewers do not need to run Railway or Vercel.** Use the **[live demo](https://ahmc-hpi-generator.vercel.app)** links here or above — that is the deployment already configured for this project.

The rest of this section is **optional**: use it if you **fork the repo**, need a **separate** API or frontend URL, or want to understand how the hosted stack is wired.

### Overview


| Piece       | Platform                       | Why                                                            |
| ----------- | ------------------------------ | -------------------------------------------------------------- |
| FastAPI API | [Railway](https://railway.app) | Simple Python deploy, `PORT`, HTTPS URL                        |
| React SPA   | [Vercel](https://vercel.com)   | Vite build, global CDN, SPA routing via `frontend/vercel.json` |


**CORS:** The browser loads the UI from Vercel and calls the API on another origin. Set `**ALLOWED_ORIGINS`** to your exact production URL(s), comma-separated. For **every new preview deployment,** Vercel uses a different subdomain (`…-hash-….vercel.app`); either add each origin to `**ALLOWED_ORIGINS`** or set `**ALLOWED_ORIGINS_REGEX`** to `^https://.*\.vercel\.app$` on Railway (demo convenience). `?_vercel_share=…` is only for opening the preview in the browser; CORS uses the **origin** (`https://hostname.vercel.app`), not the query string.

**Database:** The default `**DATABASE_URL`** is SQLite (`cases.db` in the service working directory). It is fine for a demo; data can reset if the container is redeployed or replaced. For durable storage, point `**DATABASE_URL`** at a managed Postgres and add a driver (e.g. `psycopg[binary]`) — SQLAlchemy already supports it.

---

### 1. Backend (Railway)

1. Create a [Railway](https://railway.app) project → **Deploy from GitHub** → select this repo.
2. **Settings → Service → Root directory:** `backend`
  (Railway runs from that folder so `main:app` and `requirements.txt` resolve correctly.)
3. **Settings → Deploy → Custom start command** (if not inferred):
  `uvicorn main:app --host 0.0.0.0 --port $PORT`  
   (A `backend/Procfile` with the same command is included for compatibility.)
4. **Variables** (minimum):

  | Name                    | Value                                                                                                                        |
  | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
  | `ANTHROPIC_API_KEY`     | Your key from [Anthropic Console](https://console.anthropic.com/settings/keys) (no quotes).                                  |
  | `ALLOWED_ORIGINS`       | Production URL(s), e.g. `https://ahmc-hpi-generator.vercel.app` (comma-separated list, no spaces).                           |
  | `ALLOWED_ORIGINS_REGEX` | *(Optional: Used)* `^https://.*\.vercel\.app$` — allows **any** Vercel preview/share URL without updating Railway each time. |

   Optional: `ANTHROPIC_MODEL`, `ANTHROPIC_MAX_TOKENS`, `MIN_FOLLOW_UP_QUESTIONS`, `DATABASE_URL`.
5. Deploy and wait for a successful build. Open **Settings → Networking → Generate domain** (or use the default `*.up.railway.app` URL). Copy the **HTTPS** public URL — this is your API base (e.g. `https://ahmc-hpi-production.up.railway.app`).
6. Sanity check: visit `https://<your-api-host>/health` → `{"status":"ok"}` and `https://<your-api-host>/docs` for OpenAPI.

---

### 2. Frontend (Vercel)

1. [Vercel](https://vercel.com) → **Add New… → Project** → import the same GitHub repo.
2. **Root directory:** `frontend`
3. **Framework preset:** Vite (auto-detected). Build: `npm run build`, output: `dist`.
4. **Environment variables:**

  | Name           | Value                                                                                                        |
  | -------------- | ------------------------------------------------------------------------------------------------------------ |
  | `VITE_API_URL` | The Railway API origin **only** — e.g. `https://ahmc-hpi-production.up.railway.app` — **no trailing slash**. |

5. Deploy. `**VITE_API_URL` is injected at build time** — if you add or change it later, open **Deployments → … → Redeploy** so the new value is compiled in. If the app shell loads but data never appears, the list page shows an API error banner; otherwise check the browser **Network** tab: requests to `/api/...` should go to your **Railway** host (not `vercel.app`). If the API was not in `**ALLOWED_ORIGINS`** yet, add your production Vercel URL to Railway `**ALLOWED_ORIGINS`** and **redeploy the backend**.
6. **SPA routing:** `frontend/vercel.json` rewrites unknown paths to `index.html` so deep links like `/cases/123` work on refresh.

---

### 3. After deploy

- If the UI shows CORS or network errors: `**VITE_API_URL`** on Vercel must be set for **Production** (and redeploy); Railway `**ALLOWED_ORIGINS`** must include the exact origin you open, **or** set `**ALLOWED_ORIGINS_REGEX`** to `^https://.*\.vercel\.app$` and redeploy the backend.

**Backend is self-contained:** Python dependencies and runtime live only under `**backend/`** (`requirements.txt`, `runtime.txt`, `Procfile`). On **Railway** (and similar hosts), set the service **Root directory** to `**backend`** so the builder sees a normal Python app and `uvicorn main:app` runs from that folder. Deploying from the **repository root** without extra config is not supported — use `**backend`** as the service root.

---

## AI tool usage disclosure

### Tools used


| Tool                               | Purpose                                                                   |
| ---------------------------------- | ------------------------------------------------------------------------- |
| Claude Code                        | Generated the initial backend and frontend skeleton to get moving quickly |
| Claude claude-sonnet-4-6 (runtime) | Powers the actual note analysis and HPI generation in the app             |
| Cursor                             | Used for debugging and iterating on features after the initial scaffold   |
| ChatGPT                            | Used for medical terminology and clarification                            |


### What AI generated

Claude Code produced the starting point (backbone): a basic FastAPI app with simple CRUD routes, a single `cases` table with a JSON column, and a React frontend with three pages wired together. Think of it as a working boilerplate — the kind of thing that saves you from writing the same `GET /items/{id}` route for the hundredth time. In addition, Claude and cursor were used for debugging and syntax checks (especially for TypeScript). 

The scaffolding prompt for the backend was roughly: *"FastAPI app with SQLite for storing clinical cases — each case has an ER note, H&P note, a JSON output field, and a list of which fields the user has edited."* For the frontend: *"React + TypeScript with react-router-dom, three pages: case list, new case with two note textareas, and a case detail page that shows the structured output with editable fields and AI/user-edited badges."*

### What I designed and built

**Research — reading the clinical materials before writing any code.** Before touching the prompt I read through all the provided documents: the MCG ISC Diabetes guideline PDF (not just skimming — working out what each admission criterion actually means and which specific thresholds trigger inpatient vs. observation), the Case A ER note and H&P, and most importantly the sentence-by-sentence comparison table in the Case A Revised HPI document. That table was the key artifact — it maps each sentence in the output back to the source line in the chart and explains *why* it supports admission under the MCG criteria. I used it to understand the transformation pattern before writing a single line of prompt.

**The clinical prompt** — This was the most important engineering decision, and the AI couldn't do it for me. After reading the MCG guideline and the Case A breakdown, I wrote the system prompt from scratch: condensed the MCG criteria to the admission-relevant thresholds, structured the six-sentence narrative arc I extracted from the reference, and added explicit rules about citing exact lab values, keeping glucose and acid-base language in separate domains, not inferring named syndromes from a single lab, and flagging missing information rather than filling it in. These rules came from actual output problems I found during testing — not from guessing upfront.

**The clarification flow** — When I tested with incomplete or ambiguous notes, the model would sometimes fabricate demographics or disposition rather than admit it didn't have enough to work with. I designed the `awaiting_clarification` status and `follow_up_questions` / `supplemental_answers` fields on the Case model to handle this: if the model returns questions, the UI surfaces them as a form instead of showing a completed result. The user answers them, and those answers are injected into the next generation as a supplemental block. This required coordinating changes across the DB schema, the API routes, the LLM prompt, and the frontend state.

**The database schema** — The scaffold stored everything as a single JSON blob. I replaced that with proper relational tables — `clinical_structured_outputs` for the scalar fields and `clinical_list_items` for the bulleted lists — and wrote `clinical_storage.py` to handle persisting, loading, batched reads for the case list, and migrating old JSON-only rows on startup. I also added SQLite column migration so existing `cases.db` files from earlier versions of the app don't break when the new columns are added.

**Edit tracking** — The `edited_fields` string array on the case, and the logic that reads it to drive the `🤖 AI` / `✏️ Edited` badge state in the UI. Required thinking through the round-trip carefully: generate → display → edit → save → reload → all states stay consistent.

**Deployment debugging — CORS and environment wiring.** Getting the frontend on Vercel talking to the backend on Railway took more iteration than expected. The main issues: `VITE_API_URL` is baked in at build time (so changing it requires a redeploy, not just a save), Vercel's Production and Preview environments are separate (so an env var set for Production doesn't apply to preview deployments), and Railway's `ALLOWED_ORIGINS` has to exactly match the origin the browser sends. I added `ALLOWED_ORIGINS_REGEX` support so a single pattern covers all Vercel preview URLs without updating Railway on every deployment. I also added a frontend error banner that detects the likely cause (missing `VITE_API_URL` vs. CORS blocked) and shows a specific fix rather than a generic failure message.

**Error handling and robustness** — Added `json-repair` after the model produced near-valid JSON that `json.loads` rejected (unescaped quotes inside field values). Flow: strict parse → repair fallback → clear error if both fail. Also found and fixed a bug where API keys wrapped in quotes in `.env` (e.g. `ANTHROPIC_API_KEY="sk-ant-..."`) caused silent auth failures — added normalization to strip them. Surfaced Anthropic API errors (auth, token limits) through to the UI as readable messages instead of bare 500s.

### How I checked the output

**Case A against the reference (with extra data).** I pasted the Case A ER note and H&P from the exercise materials, added a **small amount of extra realistic chart text** (the kind of clutter or add-on lines you might see in a real record), and ran **Generate**. I then compared the model’s **Revised HPI** line by line to the **human-written Revised HPI** in the reference document. For each sentence or clause I marked it in two colors: **green** where the model had **correctly woven in** the extra information without distorting the clinical story, and **red** where it made an **incorrect connection** or **hallucination** (e.g. tying a normal lab to a named syndrome the chart did not support, or inventing facts not present in the source). Those red marks drove concrete edits to `**llm.py**`.

Beyond narrative wording, I checked structured fields the same way: key labs cited correctly (pH 7.20, bicarb 7.4, glucose 93 where documented), clinical context (Kussmaul breathing, SGLT2 inhibitor trigger), escalation (insulin drip, bicarbonate, 3L saline, ICU plan), and `admission_criteria_met` aligned with the guideline PDF (pH < 7.30, bicarb ≤ 18 mEq/L, 2+ ketonuria). I also exercised the **edit tracking** round-trip and main API error paths.

**From specific Revised HPI problems to generalized rules.** When something in the **Revised HPI** looked wrong, I treated it as a **symptom** of a broader failure mode, not a one-off wording tweak. I wrote **principle-based** instructions in `**llm.py**` so the same class of mistake is discouraged on **any** chart—not only Case A. Examples of that pattern:


| Kind of problem I saw in the output                                                                               | Generalized rule (intent)                                                                                                              |
| ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Normal glucose used to justify a named syndrome or “euglycemic” wording the chart did not support                 | Named syndromes and labels only when the **source** supports them; do not infer from a **single** lab.                                 |
| “Euglycemic” or “euglycemic range” attached to **pH** or **acidosis** (wrong domain—euglycemic means **glucose**) | Glucose-related vocabulary **only** for glucose; acid–base described with pH/bicarbonate/etc., separately.                             |
| Two **different** result lines (e.g. bicarbonate value vs chemistry **CO₂**) collapsed into one wrong summary     | **Distinct results and terms (do not fuse):** separate chart lines stay **separate** in the narrative; no merged or mislabeled values. |


I **avoided overfitting to Case A** by **not** adding rules that require copying the few-shot **sentence structure** or fixed openers. Case A remains one **example** in the prompt; the **TRANSFORMATION RULES** are stated as **general** constraints (terminology, syndromes, fusing, fabrication, thin-chart behavior). That way the model can still paraphrase naturally for other presentations while respecting the same guardrails.

**Thin charts.** I tested notes where important items were left out on purpose (e.g. no age, no sex/gender, blank IMPRESSION/DISPOSITION). I’d generate once, read the JSON and the Revised HPI, and check whether the model **invented** demographics or disposition, whether `**uncertainties`** called out what was missing, and whether the **follow-up question** path fired when it should. I used the app’s **clarify / supplemental** flow: supplied missing facts as a clinician would, regenerated, and compared the second pass to the first—did it incorporate the new info without contradicting the chart?

**Iteration.** Whenever red marks or thin-chart failures pointed to the same failure mode, I **tightened the system prompt** in `**llm.py`**: stronger “no fabrication” rules, the mandatory age / sex–gender / disposition checklist, preference for **uncertainties** and **follow-up questions** over guessing, and the **general** rules above. The loop—**run → spot a bad Revised HPI → name the pattern → add a generalized rule → re-run**—is how the current prompt reached its present form.

---

## If I had more time

1. **More training examples** — One few-shot example is fragile. With more human-reviewed cases across different presentations, the output would be more consistent. Right now I can't tell if Case B works well because the model is generalizing or because it's similar enough to Case A.
2. **Broader input types** — The prompt is designed around diabetes/DKA and the MCG ISC guideline. To handle other conditions (cardiac, respiratory, etc.) I'd need a way to select or inject the right guideline and probably rethink how the few-shot examples are organized.
3. **Export to Word** — Clinicians need to paste this into EHR systems. A download as `.docx` would make it actually useful in the workflow.
4. **PDF/DOCX upload** — Pasting notes manually works for a demo but adds friction. Drag-and-drop with text extraction would be more realistic.
5. **Diff view** — Side-by-side between the original AI output and the saved version, so reviewers can see exactly what was changed.
6. **Authentication** — Right now it's single-user. Real deployment would need accounts.

---

## Project structure

```
ahmc-hpi/
├── backend/
│   ├── Procfile             # Railway: uvicorn on $PORT (service root = backend/)
│   ├── main.py              # FastAPI app, routes, clarification + generation orchestration
│   ├── models.py            # SQLAlchemy models (Case + clinical tables)
│   ├── clinical_storage.py  # Read/write structured output (relational + JSON cache, batch reads)
│   ├── database.py          # Engine, SQLite FK pragma, init, column migration, legacy JSON migration
│   ├── llm.py               # Claude prompt, supplemental block, JSON parsing, error handling
│   ├── requirements.txt     # Python deps (set deploy root to `backend/` on Railway, etc.)
│   ├── runtime.txt          # Python version for Railway / mise (e.g. python-3.11.9)
│   └── .env.example
├── frontend/
│   ├── vercel.json          # SPA fallback for client-side routes
│   ├── .env.example         # VITE_API_URL for production
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/client.ts        # axios wrapper + error surfacing
│   │   ├── types/index.ts       # TypeScript types
│   │   ├── components/
│   │   │   ├── Badge.tsx
│   │   │   ├── EditableField.tsx
│   │   │   ├── EditableList.tsx
│   │   │   ├── DispositionSelect.tsx
│   │   │   └── StructuredOutput.tsx
│   │   └── pages/
│   │       ├── CaseList.tsx
│   │       ├── NewCase.tsx
│   │       └── CaseDetail.tsx
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

