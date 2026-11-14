import re
import unicodedata
from typing import Dict, List

def preprocess_summary(summary: str) -> str:
    """Preprocess the meeting summary by cleaning up whitespace and unicode."""
    if not summary:
        return ""
    # Normalize unicode characters
    summary = unicodedata.normalize('NFKC', summary)
    # Normalize whitespace
    summary = re.sub(r'\s+', ' ', summary).strip()
    return summary

def extract_candidate_signals(summary: str) -> Dict[str, List[str]]:
    """Extract obvious signals like emails, phones, and URLs for early CRM lookup."""
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', summary)
    # Basic phone extraction
    phones = re.findall(r'\+?\d{1,3}[-.\s]?\(?\d{1,4}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}', summary)
    urls = re.findall(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', summary)
    
    return {
        "emails": list(set(emails)),
        "phones": list(set([p for p in phones if len(re.sub(r'\D', '', p)) >= 7])),
        "urls": list(set(urls))
    }
