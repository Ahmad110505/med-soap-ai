import os
import logging
import tempfile
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from groq import Groq

from database import get_db, SoapNoteRecord, FeedbackRecord
from services.ai_engine import process_text_to_soap
from pdf_generator import create_soap_pdf

logger = logging.getLogger(__name__)
router = APIRouter()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


class TranscriptRequest(BaseModel):
    text: str
    return_pdf: bool = False


class FeedbackRequest(BaseModel):
    note_id: int
    sentence: str
    correct_label: str


class UpdateNoteRequest(BaseModel):
    structured_data: dict


@router.get("/health")
def api_health():
    return {"status": "ok", "service": "Clinical SOAP AI API"}


@router.post("/generate-soap")
def generate_structured_soap(
    request: TranscriptRequest,
    db: Session = Depends(get_db)
):
    transcript = request.text.strip()

    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript text cannot be empty.")

    try:
        ai_result = process_text_to_soap(transcript, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating SOAP note: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate SOAP note.")

    if request.return_pdf:
        pdf_buffer = create_soap_pdf(
            soap_data=ai_result["data"],
            transcript=ai_result["transcript"]
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="SOAP_Note_{timestamp}.pdf"'
            }
        )

    return ai_result


@router.post("/upload-audio")
async def process_audio_dictation(
    file: UploadFile = File(...),
    return_pdf: bool = Form(False),
    db: Session = Depends(get_db)
):
    logger.info(f"Received audio file: {file.filename}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    allowed_extensions = (".wav", ".mp3", ".m4a", ".ogg", ".webm")
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="Unsupported file format.")

    temp_file_path = None

    try:
        file_ext = os.path.splitext(file.filename)[1].lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_audio:
            content = await file.read()
            temp_audio.write(content)
            temp_file_path = temp_audio.name

        logger.info("Transcribing audio with Groq...")

        prompt = (
            "Patient presents with a cough. Chest X-ray is clear. "
            "Diagnosis is bronchitis. Will prescribe albuterol."
        )

        with open(temp_file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3-turbo",
                prompt=prompt
            )

        full_transcript = (transcription.text or "").strip()

        logger.info(f"Groq transcript: '{full_transcript}'")

        if not full_transcript:
            raise HTTPException(status_code=400, detail="Could not detect any speech in audio.")

        ai_result = process_text_to_soap(full_transcript, db)

        if return_pdf:
            pdf_buffer = create_soap_pdf(
                soap_data=ai_result["data"],
                transcript=ai_result["transcript"]
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="Voice_SOAP_{timestamp}.pdf"'
                }
            )

        return ai_result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing audio file.")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@router.get("/notes")
def get_all_saved_notes(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    notes = (
        db.query(SoapNoteRecord)
        .order_by(SoapNoteRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"total_returned": len(notes), "notes": notes}


@router.get("/notes/{note_id}/pdf")
def download_past_pdf(
    note_id: int,
    db: Session = Depends(get_db)
):
    record = db.query(SoapNoteRecord).filter(SoapNoteRecord.id == note_id).first()

    if not record:
        raise HTTPException(status_code=404, detail=f"Note #{note_id} not found.")

    pdf_buffer = create_soap_pdf(
        soap_data=record.structured_data,
        transcript=record.raw_transcript
    )
    timestamp = record.created_at.strftime("%Y%m%d")

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Archived_SOAP_{note_id}_{timestamp}.pdf"'
        }
    )


@router.post("/submit-feedback")
def submit_ai_correction(
    request: FeedbackRequest,
    db: Session = Depends(get_db)
):
    clean_label = request.correct_label.strip().upper()

    if clean_label not in ["S", "O", "A", "P"]:
        raise HTTPException(status_code=400, detail="Label must be S, O, A, or P.")

    try:
        new_feedback = FeedbackRecord(
            note_id=request.note_id,
            sentence=request.sentence.strip(),
            correct_label=clean_label
        )
        db.add(new_feedback)
        db.commit()

        logger.info(
            f"Feedback saved. Sentence '{request.sentence}' categorized as {clean_label}."
        )
        return {"status": "success", "message": "Correction saved successfully."}

    except Exception as e:
        logger.error(f"Failed to save feedback: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save correction to database.")


@router.put("/notes/{note_id}")
def update_saved_note(
    note_id: int,
    request: UpdateNoteRequest,
    db: Session = Depends(get_db)
):
    record = db.query(SoapNoteRecord).filter(SoapNoteRecord.id == note_id).first()

    if not record:
        raise HTTPException(status_code=404, detail=f"Note #{note_id} not found.")

    record.structured_data = request.structured_data
    db.commit()

    return {"status": "success", "message": "Note updated successfully."}