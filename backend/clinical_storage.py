"""Normalized persistence for LLM structured output (relational + JSON cache on Case)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import Case, ClinicalListItem, ClinicalStructuredOutput

LIST_CATEGORIES = (
    "key_findings",
    "suspected_conditions",
    "admission_criteria_met",
    "uncertainties",
)

VALID_DISPOSITIONS = frozenset({"Admit", "Observe", "Discharge", "Unknown"})


def _normalize_disposition(raw: Any) -> str:
    disp = raw if isinstance(raw, str) else "Unknown"
    return disp if disp in VALID_DISPOSITIONS else "Unknown"


def structured_output_to_dict(db: Session, case_id: int) -> Optional[dict]:
    row = db.query(ClinicalStructuredOutput).filter_by(case_id=case_id).first()
    if row is None:
        return None
    out: Dict[str, Any] = {
        "chief_complaint": row.chief_complaint or "",
        "hpi_summary": row.hpi_summary or "",
        "disposition_recommendation": row.disposition_recommendation or "Unknown",
        "revised_hpi": row.revised_hpi or "",
    }
    for cat in LIST_CATEGORIES:
        items = (
            db.query(ClinicalListItem)
            .filter_by(case_id=case_id, category=cat)
            .order_by(ClinicalListItem.sort_order)
            .all()
        )
        out[cat] = [i.value for i in items]
    return out


def persist_structured_output(db: Session, case_id: int, data: dict) -> dict:
    """Write scalars + list rows; sync Case.structured_output JSON cache; return canonical dict."""
    disp = _normalize_disposition(data.get("disposition_recommendation"))

    row = db.query(ClinicalStructuredOutput).filter_by(case_id=case_id).first()
    if row is None:
        row = ClinicalStructuredOutput(case_id=case_id)
        db.add(row)
    row.chief_complaint = data.get("chief_complaint") or ""
    row.hpi_summary = data.get("hpi_summary") or ""
    row.disposition_recommendation = disp
    row.revised_hpi = data.get("revised_hpi") or ""

    db.query(ClinicalListItem).filter(ClinicalListItem.case_id == case_id).delete(
        synchronize_session=False
    )

    for cat in LIST_CATEGORIES:
        for order, val in enumerate(data.get(cat) or []):
            if val is None:
                continue
            db.add(
                ClinicalListItem(
                    case_id=case_id,
                    category=cat,
                    sort_order=order,
                    value=str(val),
                )
            )

    db.flush()
    canonical = structured_output_to_dict(db, case_id)
    if canonical is None:
        raise RuntimeError("Failed to read back structured output after persist")

    case = db.query(Case).filter(Case.id == case_id).first()
    if case is not None:
        case.structured_output = canonical
        case.updated_at = datetime.now(timezone.utc)

    return canonical


def load_structured_output(db: Session, case: Case) -> Optional[dict]:
    """Prefer relational rows; migrate from legacy JSON on Case if needed."""
    d = structured_output_to_dict(db, case.id)
    if d is not None:
        return d
    legacy = case.structured_output
    if isinstance(legacy, dict) and legacy:
        return persist_structured_output(db, case.id, legacy)
    return None


def batch_structured_outputs(db: Session, case_ids: List[int]) -> Dict[int, Optional[dict]]:
    if not case_ids:
        return {}
    id_set = list(dict.fromkeys(case_ids))
    out: Dict[int, Optional[dict]] = {cid: None for cid in id_set}

    scalars = (
        db.query(ClinicalStructuredOutput)
        .filter(ClinicalStructuredOutput.case_id.in_(id_set))
        .all()
    )
    scalar_by_case = {r.case_id: r for r in scalars}

    lists = (
        db.query(ClinicalListItem)
        .filter(ClinicalListItem.case_id.in_(id_set))
        .order_by(
            ClinicalListItem.case_id,
            ClinicalListItem.category,
            ClinicalListItem.sort_order,
        )
        .all()
    )
    lists_by_case: Dict[int, Dict[str, List[str]]] = {}
    for item in lists:
        lists_by_case.setdefault(item.case_id, {}).setdefault(item.category, []).append(
            item.value
        )

    for cid in id_set:
        row = scalar_by_case.get(cid)
        if row is None:
            continue
        d = {
            "chief_complaint": row.chief_complaint or "",
            "hpi_summary": row.hpi_summary or "",
            "disposition_recommendation": row.disposition_recommendation
            or "Unknown",
            "revised_hpi": row.revised_hpi or "",
        }
        cat_map = lists_by_case.get(cid, {})
        for cat in LIST_CATEGORIES:
            d[cat] = cat_map.get(cat, [])
        out[cid] = d

    return out


def migrate_legacy_json_rows(db: Session) -> int:
    """Copy Case.structured_output JSON into relational tables when rows are missing."""
    n = 0
    cases = db.query(Case).filter(Case.structured_output.isnot(None)).all()
    for case in cases:
        if not isinstance(case.structured_output, dict):
            continue
        if db.query(ClinicalStructuredOutput).filter_by(case_id=case.id).first():
            continue
        persist_structured_output(db, case.id, case.structured_output)
        n += 1
    return n
