from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
import os
from dotenv import load_dotenv

from database import get_db, init_db
from models import Case
from llm import generate_structured_output
from clinical_storage import (
    batch_structured_outputs,
    load_structured_output,
    persist_structured_output,
)

load_dotenv()

app = FastAPI(title="AHMC Clinical HPI Generator", version="1.0.0")

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class CaseCreate(BaseModel):
    title: str
    er_note: Optional[str] = None
    hp_note: Optional[str] = None
    id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Optional manual case ID. Must be unique; omit for auto-assigned ID.",
    )


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    structured_output: Optional[dict] = None
    edited_fields: Optional[List[str]] = None


class CaseResponse(BaseModel):
    id: int
    title: str
    er_note: Optional[str]
    hp_note: Optional[str]
    structured_output: Optional[Any]
    edited_fields: Optional[List[str]]
    generation_status: str
    generation_error: Optional[str]
    follow_up_questions: Optional[List[str]] = None
    supplemental_answers: Optional[Dict[str, str]] = None
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


def _norm_supplemental_dict(supp: Optional[Any]) -> Optional[Dict[str, str]]:
    if supp is None or not isinstance(supp, dict):
        return None
    return {str(k): str(v) for k, v in supp.items()}


def _format_supplemental(answers: Optional[Any]) -> Optional[str]:
    if not answers or not isinstance(answers, dict):
        return None
    lines = []
    for q, a in answers.items():
        if a is None or str(a).strip() == "":
            continue
        lines.append(f"Q: {str(q).strip()}\nA: {str(a).strip()}")
    return "\n\n".join(lines) if lines else None


def _min_follow_up_questions() -> int:
    """Only enable the clarification UI when the model returns this many questions (default 2)."""
    raw = os.getenv("MIN_FOLLOW_UP_QUESTIONS", "2").strip()
    try:
        n = int(raw)
        return max(1, min(10, n))
    except ValueError:
        return 2


def _run_generation(db: Session, case: Case) -> None:
    supp = _format_supplemental(case.supplemental_answers)
    result = generate_structured_output(case.er_note, case.hp_note, supplemental_block=supp)
    followups = result.pop("follow_up_questions", None)
    if not isinstance(followups, list):
        followups = []
    followups = [str(x).strip() for x in followups if str(x).strip()]
    persist_structured_output(db, case.id, result)

    min_q = _min_follow_up_questions()
    if len(followups) >= min_q:
        case.follow_up_questions = followups
        case.generation_status = "awaiting_clarification"
    else:
        case.follow_up_questions = None
        case.generation_status = "completed"
    case.generation_error = None
    case.edited_fields = []


def _case_response(db: Session, case: Case) -> CaseResponse:
    structured = load_structured_output(db, case)
    supp = _norm_supplemental_dict(case.supplemental_answers)
    return CaseResponse(
        id=case.id,
        title=case.title,
        er_note=case.er_note,
        hp_note=case.hp_note,
        structured_output=structured,
        edited_fields=case.edited_fields or [],
        generation_status=case.generation_status,
        generation_error=case.generation_error,
        follow_up_questions=case.follow_up_questions,
        supplemental_answers=supp,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _cases_response(db: Session, cases: List[Case]) -> List[CaseResponse]:
    batch = batch_structured_outputs(db, [c.id for c in cases])
    out: List[CaseResponse] = []
    for case in cases:
        structured = batch.get(case.id)
        if structured is None:
            structured = load_structured_output(db, case)
        supp = _norm_supplemental_dict(case.supplemental_answers)
        out.append(
            CaseResponse(
                id=case.id,
                title=case.title,
                er_note=case.er_note,
                hp_note=case.hp_note,
                structured_output=structured,
                edited_fields=case.edited_fields or [],
                generation_status=case.generation_status,
                generation_error=case.generation_error,
                follow_up_questions=case.follow_up_questions,
                supplemental_answers=supp,
                created_at=case.created_at,
                updated_at=case.updated_at,
            )
        )
    return out


class GenerateRequest(BaseModel):
    er_note: Optional[str] = None
    hp_note: Optional[str] = None


class ClarifyRequest(BaseModel):
    """Answers in the same order as case.follow_up_questions."""
    answers: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/cases", response_model=CaseResponse, status_code=201)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    if payload.id is not None:
        existing = db.query(Case).filter(Case.id == payload.id).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Case ID {payload.id} is already in use. Choose another ID or leave blank for auto-assign.",
            )
        case = Case(
            id=payload.id,
            title=payload.title,
            er_note=payload.er_note,
            hp_note=payload.hp_note,
            generation_status="pending",
        )
    else:
        case = Case(
            title=payload.title,
            er_note=payload.er_note,
            hp_note=payload.hp_note,
            generation_status="pending",
        )
    db.add(case)
    db.commit()
    db.refresh(case)
    return _case_response(db, case)


@app.get("/api/cases", response_model=List[CaseResponse])
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(Case).order_by(Case.created_at.desc()).all()
    return _cases_response(db, cases)


@app.get("/api/cases/{case_id}", response_model=CaseResponse)
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_response(db, case)


@app.post("/api/cases/{case_id}/generate", response_model=CaseResponse)
def generate_for_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if not case.er_note and not case.hp_note:
        raise HTTPException(status_code=400, detail="No clinical notes provided")

    case.generation_status = "generating"
    db.commit()

    try:
        _run_generation(db, case)
    except Exception as e:
        case.generation_status = "failed"
        case.generation_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    db.commit()
    db.refresh(case)
    return _case_response(db, case)


@app.post("/api/cases/{case_id}/clarify", response_model=CaseResponse)
def clarify_and_regenerate(
    case_id: int, payload: ClarifyRequest, db: Session = Depends(get_db)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.generation_status != "awaiting_clarification":
        raise HTTPException(
            status_code=400,
            detail="Case is not waiting for clarification. Use Generate instead.",
        )
    qs = case.follow_up_questions or []
    if not qs:
        raise HTTPException(status_code=400, detail="No follow-up questions on this case.")

    if case.supplemental_answers is None or not isinstance(case.supplemental_answers, dict):
        case.supplemental_answers = {}
    for i, q in enumerate(qs):
        if i < len(payload.answers) and str(payload.answers[i]).strip():
            case.supplemental_answers[q] = str(payload.answers[i]).strip()

    case.generation_status = "generating"
    db.commit()

    try:
        _run_generation(db, case)
    except Exception as e:
        case.generation_status = "failed"
        case.generation_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    db.commit()
    db.refresh(case)
    return _case_response(db, case)


@app.post("/api/generate", response_model=dict)
def generate_adhoc(payload: GenerateRequest):
    """Generate structured output without saving to DB — for quick preview."""
    if not payload.er_note and not payload.hp_note:
        raise HTTPException(status_code=400, detail="At least one note required")
    try:
        result = generate_structured_output(payload.er_note, payload.hp_note)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/cases/{case_id}", response_model=CaseResponse)
def update_case(case_id: int, payload: CaseUpdate, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if payload.title is not None:
        case.title = payload.title
    if payload.structured_output is not None:
        persist_structured_output(db, case.id, payload.structured_output)
    if payload.edited_fields is not None:
        case.edited_fields = payload.edited_fields

    db.commit()
    db.refresh(case)
    return _case_response(db, case)


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    db.delete(case)
    db.commit()
