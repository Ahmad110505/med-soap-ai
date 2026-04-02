import os
import json
import logging
from groq import Groq
from sqlalchemy.orm import Session
from database import SoapNoteRecord

logger = logging.getLogger(__name__)

# Initialize the Groq client. 
# We will set the API key in your environment variables later.
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def process_text_to_soap(raw_text: str, db: Session):
    """Sends the Whisper transcript to Llama-3 to categorize into SOAP JSON."""
    
    logger.info("Sending text to SOAP formatting...")

    system_prompt = """
    You are an expert clinical AI assistant. Categorize the medical dictation into SOAP format.
    Fix any speech-to-text spelling errors (e.g., 'lysin proled' -> 'lisinopril').
    
    STRICT RULES FOR CATEGORIZATION:
    - Subjective: Must include patient age, gender, symptoms, history, and exact Pain Scale numbers (e.g., 8/10).
    - Objective: Must include all vitals (BP, HR, Weight) and physical exam findings.
    - Assessment: Must include the exact diagnosis or suspected conditions.
    - Plan: Must include ALL medications, exact dosages (e.g., 600mg, 10mg), frequency, and follow-up timelines.
    
    You MUST return ONLY a raw JSON object with this exact structure, with no markdown formatting:
    {
        "Subjective": [{"text": "...", "confidence": 100}],
        "Objective": [{"text": "...", "confidence": 100}],
        "Assessment": [{"text": "...", "confidence": 100}],
        "Plan": [{"text": "...", "confidence": 100}],
        "Needs_Review": []
    }
    """

    try:
        # Call the blazing fast Llama-3 model
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            response_format={ "type": "json_object" }, # Forces strict JSON output
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Dictation: {raw_text}"}
            ],
            temperature=0.1 # Keep it strictly factual, no creative writing
        )

        # Parse the JSON response
        raw_json_string = response.choices[0].message.content
        soap_note = json.loads(raw_json_string)

        # Save to Database permanently (Option B)
        db_record = SoapNoteRecord(raw_transcript=raw_text, structured_data=soap_note)
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        
        logger.info(f"💾 Successfully saved SOAP Note #{db_record.id} to the database!")

        return {
            "status": "success",
            "note_id": db_record.id,
            "transcript": raw_text,
            "data": soap_note
        }

    except Exception as e:
        logger.error(f"⚠️ LLM API Error: {str(e)}")
        db.rollback()
        raise ValueError("Failed to process SOAP note via API.")