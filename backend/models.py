from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)

    er_note = Column(Text, nullable=True)
    hp_note = Column(Text, nullable=True)

    # Denormalized cache (kept in sync with relational clinical_* tables)
    structured_output = Column(JSON, nullable=True)

    edited_fields = Column(JSON, default=list)

    generation_status = Column(String(50), default="pending")
    generation_error = Column(Text, nullable=True)

    # When the model needs more detail (e.g. missing age): questions + accumulated answers
    follow_up_questions = Column(JSON, nullable=True)
    supplemental_answers = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    clinical_structured = relationship(
        "ClinicalStructuredOutput",
        back_populates="case",
        uselist=False,
        cascade="all, delete-orphan",
    )
    clinical_list_items = relationship(
        "ClinicalListItem",
        back_populates="case",
        cascade="all, delete-orphan",
    )


class ClinicalStructuredOutput(Base):
    """
    One row per case: scalar fields from the LLM structured JSON.
    List fields live in clinical_list_items.
    """

    __tablename__ = "clinical_structured_outputs"

    case_id = Column(
        Integer,
        ForeignKey("cases.id", ondelete="CASCADE"),
        primary_key=True,
    )
    chief_complaint = Column(Text, nullable=True)
    hpi_summary = Column(Text, nullable=True)
    disposition_recommendation = Column(String(32), nullable=True)
    revised_hpi = Column(Text, nullable=True)

    case = relationship("Case", back_populates="clinical_structured")


class ClinicalListItem(Base):
    """One row per bullet in key_findings, suspected_conditions, etc."""

    __tablename__ = "clinical_list_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(
        Integer,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category = Column(String(64), nullable=False, index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    value = Column(Text, nullable=False)

    case = relationship("Case", back_populates="clinical_list_items")
