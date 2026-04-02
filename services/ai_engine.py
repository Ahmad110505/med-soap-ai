import os
import json
import logging
from groq import Groq
from database import SoapNoteRecord

logger = logging.getLogger(__name__)

# Initialize the Groq Client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ==========================================
# THE ENTERPRISE PROMPT CHAIN
# ==========================================

LAYER_1_PROMPT = """
You are a clinical documentation extraction assistant.
Extract factual data from the transcript into a structured JSON schema.
IMPORTANT RULES:
1. Use ONLY information explicitly present in the transcript.
2. Do NOT invent, infer, or embellish.
3. If information is not stated, return empty arrays/strings or "Not stated".

OUTPUT FORMAT (You MUST return valid JSON matching this exact structure):
{
  "encounter_context": {"encounter_type": "", "setting": "", "chief_concern": ""},
  "subjective": {"chief_complaint": "", "hpi": {"summary": "", "timeline": "", "associated_symptoms": [], "pertinent_negatives": []}, "past_medical_history": [], "surgical_history": [], "medications": [], "allergies": [], "family_history": [], "social_history": [], "review_of_systems": []},
  "objective": {"vital_signs": {}, "physical_exam": [], "tests_and_results": [], "procedures_performed": []},
  "assessment_relevant": {"primary_problems": [], "documented_diagnoses": [], "differential_diagnoses": [], "chronic_conditions_affecting_management": [], "uncertainty_statements": []},
  "plan_relevant": {"medications": [], "labs_ordered": [], "imaging_ordered": [], "referrals": [], "procedures_planned": [], "counseling": [], "follow_up": {"timing": "", "details": ""}, "return_precautions": []},
  "missing_documentation_items": [],
  "high_risk_documentation_gaps": [],
  "contradictions": [],
  "icd_relevant_terms": {"confirmed": [], "suspected": [], "symptom_based": []}
}
"""

LAYER_2_PROMPT = """
You are a medical documentation assistant.
Generate a professional, concise, clinician-ready SOAP note using ONLY the provided structured JSON extraction.

IMPORTANT RULES:
1. Use ONLY the extracted information provided.
2. Do NOT invent facts, diagnoses, exam findings, vitals, ROS items, tests, or treatment details.
3. If a detail is missing, omit it—do not fill gaps.

OUTPUT FORMAT (You MUST return valid JSON):
{
  "soap_note": {
    "subjective": "...",
    "objective": "...",
    "assessment": "...",
    "plan": "..."
  },
  "metadata": {"note_style": "standard_soap", "language": "English", "requires_physician_review": true}
}
"""

LAYER_3_PROMPT = """
You are a physician-facing clinical documentation review assistant.
Review the provided EXTRACTION JSON and DRAFT SOAP NOTE. Provide a concise review panel to support physician documentation quality.
Do NOT make autonomous medical decisions or invent new facts.

OUTPUT FORMAT (You MUST return valid JSON):
{
  "review_panel": {
    "note_quality_summary": [""],
    "missing_or_incomplete_documentation": [{"item": "", "recommendation": ""}],
    "high_risk_documentation_prompts": [{"item": "", "recommendation": ""}],
    "contradictions_or_internal_inconsistencies": [{"issue": "", "details": ""}],
    "icd10_suggestions_beta": [{"problem": "", "code": "", "label": "", "reason": "", "category": ""}],
    "final_disclaimer": "This output is a documentation support draft for physician review."
  }
}
"""

def call_groq_json(system_prompt: str, user_content: str) -> dict:
    """Helper function to execute a strict JSON call to Groq."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        response_format={"type": "json_object"},
        temperature=0.1 # Low temperature for maximum factual accuracy
    )
    return json.loads(response.choices[0].message.content)

def process_text_to_soap(transcript: str, db) -> dict:
    """Runs the 3-layer AI chain and formats the output for the frontend."""
    logger.info("🧠 LAYER 1: Extracting raw facts...")
    layer_1_extraction = call_groq_json(LAYER_1_PROMPT, transcript)
    
    logger.info("✍️ LAYER 2: Drafting SOAP Note...")
    layer_2_draft = call_groq_json(LAYER_2_PROMPT, json.dumps(layer_1_extraction))
    
    logger.info("🩺 LAYER 3: Generating Clinical Review Panel...")
    review_context = f"EXTRACTION:\n{json.dumps(layer_1_extraction)}\n\nDRAFT NOTE:\n{json.dumps(layer_2_draft)}"
    layer_3_review = call_groq_json(LAYER_3_PROMPT, review_context)

    # ---------------------------------------------------------
    # UI BRIDGE: Convert Layer 2 Paragraphs into Drag/Drop Lists
    # ---------------------------------------------------------
    soap_strings = layer_2_draft.get("soap_note", {})
    
    def split_to_ui_list(text: str):
        if not text or text.strip() == "": return []
        # Split paragraph into sentences by period, remove empties
        sentences = [s.strip() + "." for s in text.split(". ") if s.strip()]
        return [{"text": s, "confidence": 100} for s in sentences]

    frontend_structured_data = {
        "Subjective": split_to_ui_list(soap_strings.get("subjective", "")),
        "Objective": split_to_ui_list(soap_strings.get("objective", "")),
        "Assessment": split_to_ui_list(soap_strings.get("assessment", "")),
        "Plan": split_to_ui_list(soap_strings.get("plan", "")),
        "Needs_Review": [] 
    }

    # Save to Database
    new_record = SoapNoteRecord(
        raw_transcript=transcript,
        structured_data=frontend_structured_data
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    # Return everything to the frontend!
    return {
        "status": "success",
        "note_id": new_record.id,
        "transcript": transcript,
        "data": frontend_structured_data,
        "review_panel": layer_3_review.get("review_panel", {}) # WE NOW SEND THE REVIEW PANEL TO THE UI!
    }