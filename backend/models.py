from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from database import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)

    # Original input notes
    er_note = Column(Text, nullable=True)
    hp_note = Column(Text, nullable=True)

    # Generated structured output (JSON)
    structured_output = Column(JSON, nullable=True)

    # Tracks which fields were edited by user after generation
    edited_fields = Column(JSON, default=list)

    # Generation status
    generation_status = Column(String(50), default="pending")  # pending, generating, completed, failed
    generation_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
