# AHMC Clinical HPI Generator

Take-home exercise for AHMC. The goal: take messy ER notes and H&P documents and turn them into a structured summary plus a clean Revised HPI that justifies why the patient needs to be admitted — through a usable web interface.

## Live Demo

> **Frontend:** [Vercel link — add after deployment]
> **Backend API:** [Railway link — add after deployment]

---

## What it does

You paste in an ER note and/or H&P, click generate, and get back:

- A structured breakdown — chief complaint, key findings, suspected diagnoses, which MCG admission criteria are met
- A Revised HPI written as a coherent narrative that builds toward and supports the admission decision
- Every field is editable in the UI, with a visual distinction between what the model generated and what you changed
- Cases are saved so you can come back and review them
- **Optional:** if the chart is *critically* thin, the model may ask for follow-up details (only after **two or more** questions — see `MIN_FOLLOW_UP_QUESTIONS`). Normal notes just finish; small gaps go in **uncertainties**, not a questionnaire.

The **Load Case B** button on the new case page pre-fills the evaluation case from the exercise so you can test immediately.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                             │
│  React + Vite + Tailwind CSS                                    │
│  ┌───────────┐ ┌──────────────┐ ┌───────────────────────────┐   │
│  │ CaseList  │ │ NewCase      │ │ CaseDetail                │   │
│  │ list + ID │ │ notes + opt. │ │ case ID, edit title,      │   │
│  │ search    │ │ manual ID    │ │ view/edit structured out  │   │
│  └───────────┘ └──────────────┘ └───────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │ REST API (axios)
┌────────────────────────▼────────────────────────────────────────┐
│                   FASTAPI BACKEND                               │
│  Python 3.9+ · Uvicorn · SQLAlchemy · SQLite                    │
│                                                                 │
│  POST /api/cases                — create case                   │
│  POST /api/cases/:id/generate   — call LLM, store output        │
│  PUT  /api/cases/:id            — save edits                    │
│  GET  /api/cases                — list all cases                │
│  GET  /api/cases/:id            — get one case                  │
│  DELETE /api/cases/:id          — delete case                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ Anthropic Python SDK
┌────────────────────────▼────────────────────────────────────────┐
│              ANTHROPIC API (claude-sonnet-4-6)                  │
│  System prompt: MCG criteria + Case A few-shot example          │
│  Output: structured JSON → parsed into relational DB tables     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| LLM | Claude claude-sonnet-4-6 | Strong clinical reasoning; handles the few-shot pattern well |
| Backend | FastAPI | Quick REST endpoints, plays nicely with the Anthropic Python SDK |
| Database | SQLite + SQLAlchemy | No setup overhead; easy to swap for Postgres later |
| Frontend | React + Vite + TypeScript | TypeScript keeps the structured output types honest across the stack |
| Styling | Tailwind CSS v4 | Fast to iterate on without fighting a component library |
| JSON repair | [json-repair](https://pypi.org/project/json-repair/) | LLMs occasionally produce near-valid JSON; this recovers those cases instead of failing hard |

---

## How I structured the clinical note

### Why prompting instead of fine-tuning

Fine-tuning on 2 examples would just memorize them. The model already understands clinical medicine — what it needs is the MCG admission criteria and an example of the exact transformation. So the system prompt does three things:

1. Embeds the relevant MCG ISC Diabetes admission criteria (condensed from the provided guideline PDF)
2. Includes Case A as a complete few-shot example — ER note + H&P in, structured JSON with Revised HPI out
3. Enforces a strict JSON output schema so parsing is predictable

### Prompt structure

```
SYSTEM:
  - Role: clinical documentation specialist
  - MCG Diabetes admission criteria (verbatim thresholds)
  - Transformation rules: no invented facts, cite exact lab values, flag gaps
  - Case A as few-shot example
  - JSON schema (all 8 fields required)

USER:
  === ER NOTE ===
  <pasted content>

  === H&P NOTE ===
  <pasted content>
```

### How the Revised HPI is structured

I read through the sentence-by-sentence breakdown in the Case A reference document and pulled out the pattern:

1. Demographics + what brought them in
2. Objective exam findings in the ED
3. Lab results — with specific values mapped to the MCG thresholds
4. Clinical impression as documented by treating physicians
5. What treatment was escalated to in the ED
6. Why all of the above justifies inpatient admission rather than discharge or observation

### Uncertainty and missing information

The `uncertainties` field is required in every output. The model is told not to invent values — if a lab result or detail isn't in the notes, it flags it rather than fills it in.

---

## Structured output fields

| Field | What it captures |
|-------|-----------------|
| `chief_complaint` | Primary reason for the ED visit |
| `hpi_summary` | Short narrative of the presenting illness |
| `key_findings` | Objective findings: labs, vitals, exam |
| `suspected_conditions` | Working diagnoses |
| `disposition_recommendation` | Admit / Observe / Discharge / Unknown |
| `admission_criteria_met` | Which MCG criteria are satisfied, with cited values |
| `uncertainties` | What's missing or unclear from the notes |
| `revised_hpi` | The full admission-supporting narrative |

---

## Database schema

The structured output is stored in relational tables (not just a JSON blob), with a denormalized JSON column kept in sync for quick reads:

| Table | What's in it |
|-------|-------------|
| `cases` | Case metadata, raw notes, generation status, `edited_fields`, JSON cache |
| `clinical_structured_outputs` | One row per case: `chief_complaint`, `hpi_summary`, `disposition_recommendation`, `revised_hpi` |
| `clinical_list_items` | One row per bullet: `key_findings`, `suspected_conditions`, `admission_criteria_met`, `uncertainties` |

Foreign keys cascade on delete. SQLite runs with `PRAGMA foreign_keys=ON`. On startup, any cases with only the old JSON column get migrated into the relational tables automatically.

### Case identity

- Each case gets a numeric ID shown in the list and on the detail page
- You can optionally set a specific ID when creating; the API returns 409 if it's already taken
- The case list has a search box that filters by ID

---

## Edit tracking

The UI shows `🤖 AI` on every generated field. Once you edit and save a field, the badge switches to `✏️ Edited` and an amber left border appears. The `edited_fields` array in the database records which fields changed, and the case list shows the count.

---

## Running locally

### Requirements

- Python 3.9+ (3.11+ is smoother for pip)
- Node.js 18+
- Anthropic API key — get one at [console.anthropic.com](https://console.anthropic.com/settings/keys)

### Backend

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

`main.py` lives in `backend/`, so the command above assumes your shell’s current directory is `backend/`. If you see **Could not import module "main"**, you ran uvicorn from the repo root (or another folder). Either `cd backend` first, or from the repo root run:

```bash
python -m uvicorn main:app --app-dir backend --reload --port 8000
```

API docs at http://localhost:8000/docs

### Environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `ANTHROPIC_API_KEY` | Yes | No quotes. Restart uvicorn after changing. |
| `ANTHROPIC_MODEL` | No | Default: `claude-sonnet-4-6` |
| `ANTHROPIC_MAX_TOKENS` | No | Default: 8192. Increase if you get truncated JSON on long notes. |
| `MIN_FOLLOW_UP_QUESTIONS` | No | Default: **2**. The optional “missing info” question UI only appears when the model returns at least this many follow-up questions; otherwise gaps stay in `uncertainties` and generation completes normally. |
| `DATABASE_URL` | No | Default: `sqlite:///./cases.db` |
| `ALLOWED_ORIGINS` | No | Default includes localhost:5173 and localhost:3000 |

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App at http://localhost:5173. Vite proxies `/api` to port 8000 in dev. For production, set `VITE_API_URL` to the deployed backend URL.

### Quick test

1. Open the app → **New Case**
2. Click **Load Case B** — pre-fills the evaluation case from the exercise
3. Click **Generate**
4. Review, edit any fields, save

---

## Deployment

### Backend → Railway

1. New project → link this repo, root directory: `backend/`
2. Set env vars: `ANTHROPIC_API_KEY`, `ALLOWED_ORIGINS=https://your-vercel-app.vercel.app`
3. Railway picks up `requirements.txt` automatically

### Frontend → Vercel

1. Import repo → root directory: `frontend/`
2. Set `VITE_API_URL=https://your-railway-backend.railway.app`
3. Deploy

---

## AI tool usage disclosure

### Tools used

| Tool | Purpose |
|------|---------|
| Claude Code | Generated the initial backend and frontend skeleton to get moving quickly |
| Claude claude-sonnet-4-6 (runtime) | Powers the actual note analysis and HPI generation in the app |
| Cursor | Used for debugging and iterating on features after the initial scaffold |

### What AI generated

Claude Code produced the starting point: a basic FastAPI app with simple CRUD routes, a single `cases` table with a JSON column, and a React frontend with three pages wired together. Think of it as a working boilerplate — the kind of thing that saves you from writing the same `GET /items/{id}` route for the hundredth time.

The scaffolding prompt for the backend was roughly: *"FastAPI app with SQLite for storing clinical cases — each case has an ER note, H&P note, a JSON output field, and a list of which fields the user has edited."* For the frontend: *"React + TypeScript with react-router-dom, three pages: case list, new case with two note textareas, and a case detail page that shows the structured output with editable fields and AI/user-edited badges."*

### What I designed and built

**The clinical prompt** — This was the most important part and the AI couldn't do it for me. I read through the Case A reference document carefully, including the sentence-by-sentence comparison table, to understand the transformation pattern: why each sentence was included, which MCG criteria it addressed, and how the narrative builds toward justifying admission. I then wrote the system prompt from scratch — the MCG criteria condensation, the six-sentence arc, the rules about citing exact values, and the instruction to flag missing information rather than fill it in.

**The database schema** — The scaffold stored everything as a single JSON blob. I replaced that with proper relational tables: `clinical_structured_outputs` for the scalar fields and `clinical_list_items` for the bulleted lists, with cascade delete and SQLite foreign key enforcement. I also wrote the `clinical_storage.py` module that handles persisting to and reading from those tables, keeping a JSON cache in sync for fast list reads, and migrating any old JSON-only rows on startup.

**Edit tracking** — The `edited_fields` string array on the case, and the logic that reads it to toggle between the `🤖 AI` and `✏️ Edited` badges in the UI. Simple mechanism but it required thinking through the round-trip: generate → display → edit → save → reload should all stay consistent.

**Error handling and robustness** — Added `json-repair` after noticing the model occasionally produces near-valid JSON that `json.loads` rejects outright (usually unescaped quotes inside field values). The flow is: strict parse → repair fallback → clear error message if both fail. Also wired up proper error surfacing from the Anthropic API (auth failures, token limit hits) through to the UI so errors are readable rather than just a 500.

**Frontend feature additions** — Case ID search on the list page, inline title editing on the detail page, the regenerate flow with confirmation, and the Case B pre-fill button.

### How I checked the output

I ran Case A through the system and compared the generated Revised HPI against the human-written version in the reference document. The specific things I checked: all key lab values present and cited correctly (pH 7.20, bicarb 7.4, glucose 93), clinical context included (Kussmaul breathing, SGLT2 inhibitor trigger), escalation documented (insulin drip, bicarbonate, 3L saline, ICU plan), and the MCG criteria in `admission_criteria_met` actually matching the thresholds in the guideline PDF (pH < 7.30, bicarb ≤ 18 mEq/L, 2+ ketonuria). Then tested the edit tracking round-trip and the main error paths.

I also tested **thin charts** — notes where important things were left out on purpose (e.g. no age, blank IMPRESSION/DISPOSITION lines). I’d generate once, read the JSON and the Revised HPI, and check whether the model **invented** age or disposition to sound complete, whether **`uncertainties`** actually called out what was missing, and whether the **follow-up question** path fired when it should. Then I used the app’s **clarify / supplemental** flow: I supplied the missing facts (like age or disposition) the way a clinician would, regenerated, and compared the second pass to the first — did it incorporate the new info without contradicting the chart, and did it stop hallucinating gaps?

When I saw the model **fill in** undocumented demographics or disposition, or stay silent in `uncertainties` while still writing a confident narrative, I treated that as a failure mode and **tightened `llm.py`**: stronger “no fabrication” rules, a mandatory checklist for age and blank disposition fields, and instructions to prefer **uncertainties** and **follow-up questions** over guessing. That iteration loop — run a bad note → inspect output for hallucination → adjust the prompt → re-run — is how the current system prompt got to where it is.

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
│   ├── main.py              # FastAPI app and all routes
│   ├── models.py            # SQLAlchemy models (Case + clinical tables)
│   ├── clinical_storage.py  # Read/write structured output (relational + JSON cache)
│   ├── database.py          # Engine, SQLite FK pragma, init + migration
│   ├── llm.py               # Claude prompt, JSON parsing, error handling
│   ├── requirements.txt
│   └── .env.example
├── frontend/
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
