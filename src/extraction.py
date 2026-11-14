import os
import json
import time
from google import genai
from pydantic import ValidationError
from src.schemas import ExtractionResult
from src.context import build_context
from src.config import MODEL_NAME, MAX_RETRIES

def extract_crm_data(meeting_summary: str, existing_records: dict = None) -> ExtractionResult:
    """Extract CRM data using Gemini with Pydantic structured output."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not set. Using empty extraction for mock if needed.")
        
    # We will pass the api_key if available.
    try:
        client = genai.Client(api_key=api_key) if api_key else genai.Client()
    except Exception as e:
        print(f"Could not initialize genai client: {e}")
        return ExtractionResult()
        
    context = build_context(meeting_summary, existing_records)
    
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=context,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractionResult,
                    temperature=0.1,
                )
            )
            
            result_json = response.text
            result_dict = json.loads(result_json)
            return ExtractionResult(**result_dict)
            
        except (json.JSONDecodeError, ValidationError) as e:
            if attempt == MAX_RETRIES - 1:
                print(f"Extraction failed after {MAX_RETRIES} attempts. Last error: {e}")
                return ExtractionResult()
            print(f"Schema validation failed, retrying ({attempt+1}/{MAX_RETRIES})...")
            continue
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if attempt == MAX_RETRIES - 1:
                    print(f"Rate limit exceeded after {MAX_RETRIES} attempts.")
                    return ExtractionResult()
                print(f"Rate limit hit. Waiting 60 seconds before retrying ({attempt+1}/{MAX_RETRIES})...")
                time.sleep(60)
                continue
            
            print(f"API Error during extraction: {e}")
            return ExtractionResult()
            
    return ExtractionResult()
