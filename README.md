# Automated CRM Data Filler Agent

## Overview
The Automated CRM Data Filler Agent leverages Gemini 2.5 Flash to transform unstructured meeting summaries, transcripts, and emails into structured, actionable CRM data. It automatically extracts entities (Contacts, Companies, Deals), establishes relationships between them, validates against business rules, resolves duplicates against existing CRM records, and plans the corresponding CRUD operations.

## Problem Statement
Sales representatives spend a significant portion of their time manually entering data into CRM systems after meetings. This manual process is prone to errors, inconsistencies, and delays, leading to poor data quality and lost opportunities.

## Solution
This agentic pipeline reads natural language text, extracts entities with confidence scoring and evidence tracing, standardizes data, prevents duplicate entries via fuzzy matching, and provides a clear review interface before syncing to the CRM.

## Architecture
```text
[Meeting Summary] 
       │
       ▼
(Preprocessing) -> Extract candidate signals (emails, URLs)
       │
       ▼
(Context Builder) -> Fetch existing CRM records + Add Business Rules
       │
       ▼
(Gemini Extraction) -> Structured Pydantic Output
       │
       ▼
(Relationship Mapper) -> Infer WORKS_AT, HAS_OPPORTUNITY, etc.
       │
       ▼
(Deterministic Validator) -> Check formats, valid stages, requirements
       │
       ▼
(Entity Resolution) -> Fuzzy + Exact duplicate detection
       │
       ▼
(Action Planner) -> Generate CREATE/UPDATE/ASK_FOR_REVIEW operations
       │
       ▼
[Streamlit Interface] -> Approve & Sync
```

## Context Engineering
The application uses Context Engineering to improve LLM extraction accuracy. By injecting existing CRM records (based on candidate signals like emails extracted during preprocessing) and strict business rules directly into the Gemini prompt, the LLM performs implicit resolution and aligns its output with valid schemas.

## Tech Stack
- **AI/LLM**: Google Gemini 2.5 Flash (`google-genai`)
- **Validation**: Pydantic v2
- **Matching**: FuzzyWuzzy
- **UI**: Streamlit with Custom CSS
- **Language**: Python 3

## Quick Start
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Add your GEMINI_API_KEY in .env
   ```
4. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

## Running in Colab
You can easily port the `src/` modules to a Google Colab notebook and run the extraction pipeline headless by calling `process_meeting_summary()` directly.

## CRM Integration Guide
The current implementation uses a `MockCRMClient`. To integrate with Hubspot/Salesforce:
1. Extend `CRMClient` base class in `src/crm_client.py`.
2. Implement API calls using `requests` or official SDKs in the overriden methods.
3. Update `CRM_MODE` in `.env`.

## Limitations & Future Improvements
- **Current Limitations**: Mock CRM only supports basic fuzzy matching in memory. Relationship inference logic is rule-based and simplistic.
- **Future Improvements**: Graph database integration for relationship tracking, webhook listeners for automatic processing of Zoom transcripts, and human-in-the-loop active learning to fine-tune extraction thresholds.

## License
CRMArena-Pro CC-BY-NC 4.0
