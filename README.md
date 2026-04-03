# AHMC Clinical HPI Generator

A full-stack web application that transforms unstructured clinical notes (ER notes and H&P) into structured summaries with admission-supporting Revised HPI narratives, powered by Claude claude-sonnet-4-6.

## Live Demo

> **Frontend:** [Deploy to Vercel — link here after deployment]
> **Backend API:** [Deploy to Railway — link here after deployment]

---

## Architecture Overview

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
│  Routes:                                                        │
│  POST /api/cases          — create case (optional body `id`)   │
│  POST /api/cases/:id/generate — call LLM, store output          │
│  PUT  /api/cases/:id      — title, structured_output, edits     │
│  GET  /api/cases          — list all cases                      │
│  GET  /api/cases/:id      — get case by ID                      │
│  DELETE /api/cases/:id    — delete case                         │
│  POST /api/generate       — ad-hoc generation (no save)         │
└────────────────────────┬────────────────────────────────────────┘
                         │ Anthropic Python SDK
┌────────────────────────▼────────────────────────────────────────┐
│              ANTHROPIC API (claude-sonnet-4-6)                  │
│  Few-shot prompt with:                                          │
│  - MCG ISC Diabetes admission criteria                          │
│  - Case A as reference transformation example                   │
│  - Structured JSON output schema                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack & Rationale

| Layer | Choice | Why |
|-------|--------|-----|
| LLM | Claude claude-sonnet-4-6 | Best-in-class clinical reasoning, structured JSON output, large context for few-shot prompting |
| Backend | FastAPI (Python) | Native async, Pydantic validation, auto OpenAPI docs, natural fit for Anthropic Python SDK |
| Database | SQLite (SQLAlchemy) | Zero-config for dev; structured LLM fields stored relationally (see below) |
| Frontend | React + Vite + TypeScript | Fast build, strong typing for structured medical data |
| Styling | Tailwind CSS v4 | Rapid UI iteration, no runtime overhead |
| HTTP Client | axios | Surfaces FastAPI `detail` in the UI on errors |
| JSON repair | [json-repair](https://pypi.org/project/json-repair/) | Recovers many near-valid JSON responses from the LLM when strict parsing fails |

---

## LLM Approach: Few-Shot Prompting with Claude claude-sonnet-4-6

### Why "pretrained + refine via prompting" rather than fine-tuning

The task requires **clinical reasoning**, not just pattern matching. Claude claude-sonnet-4-6 already has extensive medical knowledge. Fine-tuning on 2 cases would be counterproductive — it would overfit and destroy generalization. Instead, we use:

1. **System prompt as the "refinement layer"** — encodes MCG admission criteria, transformation rules, and output schema
2. **Case A as few-shot example** — shows the exact input→output transformation pattern
3. **Structured JSON output** — parsed with strict `json.loads`, then **`json-repair`** as a fallback; generous **`max_tokens`** (default 8192) reduces truncated JSON on long `revised_hpi` outputs

### Prompt Architecture

```
SYSTEM:
  - Role definition (clinical documentation specialist)
  - MCG Diabetes admission criteria (verbatim from provided guideline)
  - Transformation rules (no invented facts, cite specific values, etc.)
  - Case A few-shot example (ER Note + H&P → structured JSON with Revised HPI)
  - Output schema (JSON only, no prose wrapper)

USER:
  === ER NOTE ===
  <pasted content>

  === H&P NOTE ===
  <pasted content>
```

### How the Revised HPI is structured

The Revised HPI follows a 6-sentence narrative arc proven in Case A:

1. **Demographics + presentation** — age, key PMH, chief complaint
2. **Objective ED findings** — vital sign abnormalities, exam findings
3. **Laboratory results** — specific values mapped to MCG criteria
4. **Clinical impression** — diagnosis as documented by treating physicians
5. **Treatment escalation** — what interventions were required in ED
6. **Admission justification** — synthesis connecting findings to inpatient necessity

### Handling uncertainty and missing information

- The `uncertainties` field explicitly captures what was unclear or absent
- The model is instructed never to invent facts not in the source notes
- If key MCG criterion values are not documented, this is noted as a gap

---

## Structured Output Fields

| Field | Description |
|-------|-------------|
| `chief_complaint` | Primary reason for ED visit |
| `hpi_summary` | Concise narrative of presenting illness |
| `key_findings` | Bulleted objective findings (labs, vitals, exam) |
| `suspected_conditions` | Working diagnoses |
| `disposition_recommendation` | Admit / Observe / Discharge / Unknown |
| `admission_criteria_met` | Specific MCG criteria met, with values cited |
| `uncertainties` | Missing or unclear information |
| `revised_hpi` | Full admission-supporting narrative |

---

## Relational storage for structured output

Generated clinical structure is stored in **normalized tables** (not only as JSON on `cases`):

| Table | Purpose |
|-------|---------|
| `cases` | Case metadata, raw ER/H&P notes, generation status, `edited_fields`, and a **JSON cache** of `structured_output` kept in sync for exports and compatibility |
| `clinical_structured_outputs` | **One row per case**: `chief_complaint`, `hpi_summary`, `disposition_recommendation`, `revised_hpi` |
| `clinical_list_items` | **One row per list entry**: `category` (`key_findings`, `suspected_conditions`, `admission_criteria_met`, `uncertainties`), `sort_order`, `value` |

Foreign keys use **`ON DELETE CASCADE`**: deleting a case removes its structured rows. SQLite runs with **`PRAGMA foreign_keys=ON`**.

On startup, any legacy case that still has JSON but no relational rows is **migrated automatically** into these tables.

## Case identity and organization

- Each case has a numeric **database ID** shown on the list and detail screens (`Case ID` / `ID n`).
- **New Case**: optional **Case ID** field — leave blank for auto-increment; or set a positive integer to use as the primary key (must be unique; API returns **409** if already taken).
- **All cases**: search box filters the list by ID (digits only; substring match, e.g. `12` matches `12` and `112`).
- **Case detail**: edit the **title** in place (pencil icon); saves via `PUT /api/cases/:id`.

---

## Edit Tracking

The system distinguishes AI-generated vs. user-edited content:

- Every field shows an `🤖 AI` badge when generated
- On first edit and save, the badge changes to `✏️ Edited`
- The `edited_fields` array in the database records which fields were modified
- A left amber border visually marks edited fields
- The case list shows the count of edited fields per case

---

## How to Run Locally

### Prerequisites

- **Python 3.9+** (3.11+ recommended)
- **Node.js 18+**
- **Anthropic** API key with billing/credits for the Messages API
- *(Optional)* A **SQLite viewer** if you want to inspect `cases.db` directly — see [Viewing the database](#viewing-the-database-optional) below (not required to run the app)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env
cp .env.example .env
# Edit .env — see Environment variables below

uvicorn main:app --reload --port 8000
```

API docs available at http://localhost:8000/docs

### Environment variables (backend)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Secret key from [Anthropic Console → API keys](https://console.anthropic.com/settings/keys). One line, no extra quotes. |
| `ANTHROPIC_MODEL` | No | Defaults to `claude-sonnet-4-6`. Override if your account uses a different model id. |
| `ANTHROPIC_MAX_TOKENS` | No | Max completion tokens (default **8192**, clamped ~1024–32768). Raise if generation fails with truncated or invalid JSON on very long notes. |
| `DATABASE_URL` | No | Defaults to `sqlite:///./cases.db`. |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins; default includes `http://localhost:5173` and `http://localhost:3000`. |

A **401** or **credit balance** message from Anthropic is a key or billing issue, not an application bug. Restart Uvicorn after changing `.env`.

### Viewing the database (optional)

The default database is **SQLite** at **`backend/cases.db`** (same folder you run `uvicorn` from, unless `DATABASE_URL` points elsewhere). Nothing extra is installed by this repo to browse it—you use any SQLite-capable tool:

| Tool | Requirement | Notes |
|------|-------------|--------|
| **sqlite3** (terminal) | Usually preinstalled on macOS; otherwise your OS/package manager | `cd backend && sqlite3 cases.db` → `.tables` → `SELECT * FROM cases LIMIT 5;` → `.quit` |
| **[DB Browser for SQLite](https://sqlitebrowser.org/)** | Free desktop app | Open `cases.db`, use **Browse Data** on `cases`, `clinical_structured_outputs`, `clinical_list_items` |
| **TablePlus**, **DBeaver**, **DataGrip** | Install separately | Add a SQLite connection to `backend/cases.db` |
| **VS Code / Cursor** | Install a marketplace extension such as **SQLite Viewer** | Open `cases.db` from the workspace |

**Tip:** If the API is writing to the DB, some GUI tools may show a locked file—open read-only or pause Uvicorn briefly if you run into locking issues.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at http://localhost:5173. In development, `vite.config.ts` proxies `/api` to `http://localhost:8000`. For production builds, set `VITE_API_URL` to the API base URL (e.g. `https://your-api.example.com`).

### Try Case B immediately

1. Open the app → click **New Case**
2. Click **Load Case B** button (pre-loads the provided Case B ER note + H&P)
3. Click **Generate Structured Output + Revised HPI**
4. Review the generated output, edit any fields, and save

---

## Deployment

### Backend → Railway

1. Create a Railway project
2. Link your GitHub repo, set root directory to `backend/`
3. Set environment variables:
   - `ANTHROPIC_API_KEY`
   - `ALLOWED_ORIGINS=https://your-vercel-app.vercel.app`
   - Optional: `ANTHROPIC_MODEL`, `ANTHROPIC_MAX_TOKENS`
4. Railway auto-detects the `requirements.txt` and deploys

### Frontend → Vercel

1. Import repo to Vercel, set root directory to `frontend/`
2. Set environment variable:
   - `VITE_API_URL=https://your-railway-backend.railway.app`
3. Deploy

---

## AI Tool Usage Disclosure

### Tools Used

| Tool | Purpose |
|------|---------|
| Claude Code (claude-sonnet-4-6) | Full-stack implementation, prompt design, architecture |
| Claude claude-sonnet-4-6 (runtime) | Clinical note analysis and HPI generation |

### What was AI-assisted

- **Backend**: FastAPI structure, SQLAlchemy models, API routes, LLM service layer
- **Frontend**: React component architecture, Tailwind styling, TypeScript types
- **Prompt engineering**: MCG criteria condensation, few-shot example structure, output schema

### What was manually designed

- **Clinical prompt architecture**: The 6-sentence Revised HPI structure was derived from analyzing the Case A example transformation (sentence-by-sentence comparison table in the provided docx)
- **MCG criteria selection**: Condensed the full MCG guideline to the admission-relevant decision points
- **Edit tracking schema**: The `edited_fields` array approach to distinguish AI vs. human content
- **Few-shot formatting**: How Case A is embedded in the system prompt to maximize transfer to Case B

### How correctness was verified

- Case A output was compared against the human-optimized Revised HPI provided in the exercise
- Key lab values (pH 7.20, bicarb 7.4, glucose 93) verified to be correctly extracted and cited
- MCG criteria mapping verified against the full guideline PDF
- Frontend type safety enforced via TypeScript throughout

### Prompts used for scaffolding

**Backend structure prompt:** "Build a FastAPI backend with SQLite for storing clinical cases. Each case has an ER note, H&P note, structured JSON output, and an edited_fields array to track user modifications."

**Frontend structure prompt:** "React TypeScript app with react-router-dom. Pages: case list, new case (textarea inputs), case detail (editable structured output with AI/edited badges)."

---

## If I Had More Time

1. **Streaming generation** — stream Claude's response token-by-token to the UI for faster perceived performance
2. **Multi-case learning** — store approved human-edited outputs as additional few-shot examples for future generations
3. **PDF/DOCX upload** — parse uploaded clinical note files directly rather than requiring paste
4. **Diff viewer** — side-by-side comparison between original AI output and user edits
5. **Audit trail** — timestamp each field edit for compliance purposes
6. **Authentication** — user accounts with case ownership
7. **Export** — download Revised HPI as Word document

---

## Project Structure

```
ahmc-hpi/
├── backend/
│   ├── main.py             # FastAPI app + all routes
│   ├── models.py           # Case + relational clinical_* models
│   ├── clinical_storage.py # Persist / load structured output (relational + JSON cache)
│   ├── database.py         # Engine, SQLite FK pragma, init + legacy migration
│   ├── llm.py              # Claude integration, prompt, JSON parse + repair
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/client.ts       # axios API wrapper
│   │   ├── types/index.ts      # TypeScript interfaces
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
