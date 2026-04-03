from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cases.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)


@event.listens_for(engine, "connect")
def _sqlite_enforce_foreign_keys(dbapi_connection, connection_record):
    if "sqlite" not in DATABASE_URL:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import Case, ClinicalListItem, ClinicalStructuredOutput  # noqa: F401

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        from clinical_storage import migrate_legacy_json_rows

        migrate_legacy_json_rows(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
