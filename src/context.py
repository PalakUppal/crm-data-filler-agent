from src.config import VALID_DEAL_STAGES, VALID_CURRENCIES

def build_context(meeting_summary: str, existing_records: dict = None, config: dict = None) -> str:
    """Build the context for the LLM prompt including schema, rules and examples."""
    context = f"""You are an expert CRM Data Extraction Agent. Your task is to extract structured entities (Contacts, Companies, Deals) and their relationships from the provided meeting summary.

BUSINESS RULES:
1. Valid Deal Stages: {', '.join(VALID_DEAL_STAGES)}
2. Valid Currencies: {', '.join(VALID_CURRENCIES)}
3. Extract data with high precision. If unsure, assign a lower confidence score.
4. Provide direct quotes as evidence for each extracted field.
5. All extracted entity models should have confidence (float) and evidence (List[str]) fields.

EXISTING CRM RECORDS (For entity resolution context):
{existing_records if existing_records else "None available."}

MEETING SUMMARY:
{meeting_summary}

INSTRUCTIONS:
Output valid JSON matching the requested schema. Ensure all confidence scores are between 0.0 and 1.0.
"""
    return context
