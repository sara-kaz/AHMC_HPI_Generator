from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Any
import os
from dotenv import load_dotenv

from database import get_db, init_db
from models import Case
from llm import generate_structured_output

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
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


class GenerateRequest(BaseModel):
    er_note: Optional[str] = None
    hp_note: Optional[str] = None


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
    return case


@app.get("/api/cases", response_model=List[CaseResponse])
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(Case).order_by(Case.created_at.desc()).all()
    return cases


@app.get("/api/cases/{case_id}", response_model=CaseResponse)
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


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
        result = generate_structured_output(case.er_note, case.hp_note)
        case.structured_output = result
        case.generation_status = "completed"
        case.edited_fields = []
        case.generation_error = None
    except Exception as e:
        case.generation_status = "failed"
        case.generation_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    db.commit()
    db.refresh(case)
    return case


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
        case.structured_output = payload.structured_output
    if payload.edited_fields is not None:
        case.edited_fields = payload.edited_fields

    db.commit()
    db.refresh(case)
    return case


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    db.delete(case)
    db.commit()
