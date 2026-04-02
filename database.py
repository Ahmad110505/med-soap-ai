import os
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Look for Postgres. If it fails, fall back to SQLite.
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "sqlite:///./clinical_notes.db"
)

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SoapNoteRecord(Base):
    __tablename__ = "soap_notes"
    id = Column(Integer, primary_key=True, index=True)
    raw_transcript = Column(Text, nullable=False)
    structured_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class FeedbackRecord(Base):
    __tablename__ = "feedback_logs"
    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, nullable=False)
    sentence = Column(Text, nullable=False)
    correct_label = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()