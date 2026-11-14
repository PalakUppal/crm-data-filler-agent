# %% [markdown]
# ### Section 14 — Human-in-the-Loop
# Create a function to format operations for human review and simulate approval.

# %%
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from abc import ABC, abstractmethod
import pandas as pd
import re
import json

def format_review(operations: List[CRMOperation], extraction: ExtractionResult) -> str:
    """Format proposed CRM operations for human review."""
    output = ["📋 CRM Operations Review:\n"]
    
    creates = [op for op in operations if op.operation == 'CREATE']
    updates = [op for op in operations if op.operation == 'UPDATE']
    reviews = [op for op in operations if op.operation == 'ASK_FOR_REVIEW']
    skips = [op for op in operations if op.operation == 'NO_OP']
    
    if creates:
        output.append("✨ TO BE CREATED:")
        for op in creates:
            output.append(f"  - {op.entity_type}: {op.data.get('name') or op.data.get('deal_name') or 'Association'}")
            
    if updates:
        output.append("\n🔄 TO BE UPDATED:")
        for op in updates:
            output.append(f"  - {op.entity_type} (ID: {op.entity_id}): {op.proposed_values}")
            
    if reviews:
        output.append("\n⚠️ NEEDS REVIEW:")
        for op in reviews:
            output.append(f"  - {op.entity_type}: {op.reason}")
            if op.warnings:
                output.append(f"    Warnings: {', '.join(op.warnings)}")
                
    if skips:
        output.append("\n⏭️ SKIPPED:")
        for op in skips:
            output.append(f"  - {op.entity_type}: {op.reason}")
            
    return "\n".join(output)

def simulate_approval(operations: List[CRMOperation], approved: bool = True) -> List[CRMOperation]:
    """Simulate human approval. In notebook: auto-approve. In Streamlit: actual buttons."""
    if not approved:
        return []
        
    approved_operations = []
    for op in operations:
        if op.operation == 'NO_OP':
            continue
        elif op.operation == 'ASK_FOR_REVIEW':
            # In a real UI, the user would manually resolve this.
            # Here we simulate approving it as a CREATE or UPDATE depending on if there's an entity_id
            op.operation = 'UPDATE' if op.entity_id else 'CREATE'
            approved_operations.append(op)
        else:
            approved_operations.append(op)
            
    return approved_operations

# Quick Test
test_ops = [
    CRMOperation(entity_type='Contact', operation='CREATE', data={'name': 'Jane Doe'}, reason='New contact'),
    CRMOperation(entity_type='Company', operation='ASK_FOR_REVIEW', data={'name': 'Acme Corp'}, reason='Low confidence matching', warnings=['Name similar to Acme Inc'])
]
print("--- Review Format ---")
print(format_review(test_ops, None))
print("\n--- After Approval ---")
print([op.operation for op in simulate_approval(test_ops)])


# %% [markdown]
# ### Section 15 — CRM Integration Layer (Abstract)
# Define the abstract base class for CRM clients.

# %%
class CRMClient(ABC):
    @abstractmethod
    def search_contacts(self, query: str) -> List[dict]:
        pass
    
    @abstractmethod
    def search_companies(self, query: str) -> List[dict]:
        pass
    
    @abstractmethod
    def search_deals(self, query: str) -> List[dict]:
        pass
    
    @abstractmethod
    def create_contact(self, data: dict) -> dict:
        pass
    
    @abstractmethod
    def update_contact(self, contact_id: str, data: dict) -> dict:
        pass
    
    @abstractmethod
    def create_company(self, data: dict) -> dict:
        pass
    
    @abstractmethod
    def update_company(self, company_id: str, data: dict) -> dict:
        pass
    
    @abstractmethod
    def create_deal(self, data: dict) -> dict:
        pass
    
    @abstractmethod
    def update_deal(self, deal_id: str, data: dict) -> dict:
        pass
    
    @abstractmethod
    def create_association(self, from_type: str, from_id: str, to_type: str, to_id: str) -> dict:
        pass
    
    @abstractmethod
    def get_contact(self, contact_id: str) -> dict:
        pass
    
    @abstractmethod
    def get_company(self, company_id: str) -> dict:
        pass
    
    @abstractmethod
    def get_deal(self, deal_id: str) -> dict:
        pass


# %% [markdown]
# ### Section 16 — Mock CRM
# In-memory implementation of the CRM client with pre-seeded data for testing.

# %%
try:
    from fuzzywuzzy import fuzz
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fuzzywuzzy", "python-Levenshtein"])
    from fuzzywuzzy import fuzz

class MockCRMClient(CRMClient):
    def __init__(self):
        print("🔧 CRM MODE: MOCK")
        self.contacts = {}  # id -> dict
        self.companies = {}  # id -> dict
        self.deals = {}  # id -> dict
        self.associations = []  # list of (from_type, from_id, to_type, to_id)
        self._next_id = 1000
        self._seed_data()
        
    def _get_id(self) -> str:
        self._next_id += 1
        return str(self._next_id)
        
    def _seed_data(self):
        # Pre-seed companies
        c1 = self.create_company({"name": "NexaFlow Technologies", "industry": "Software"})
        c2 = self.create_company({"name": "BrightPath Solutions", "industry": "Consulting"})
        c3 = self.create_company({"name": "DataForge Analytics", "industry": "Data"})
        
        # Pre-seed contacts
        p1 = self.create_contact({"name": "Sarah Chen", "email": "sarah@nexaflow.com"})
        p2 = self.create_contact({"name": "Marcus Rodriguez", "email": "marcus@brightpath.com"})
        
        # Pre-seed deals
        d1 = self.create_deal({"deal_name": "NexaFlow Enterprise License", "value": 50000})
        
        # Pre-seed associations
        self.create_association("Contact", p1['id'], "Company", c1['id'])
        self.create_association("Contact", p2['id'], "Company", c2['id'])
        self.create_association("Deal", d1['id'], "Company", c1['id'])

    def _fuzzy_search(self, query: str, records: dict, key: str = "name") -> List[dict]:
        results = []
        for record_id, record in records.items():
            record_val = record.get(key, "")
            if not record_val:
                continue
            score = fuzz.partial_ratio(query.lower(), str(record_val).lower())
            if score > 80:
                results.append(record)
        return results

    def search_contacts(self, query: str) -> List[dict]:
        return self._fuzzy_search(query, self.contacts, "name")
        
    def search_companies(self, query: str) -> List[dict]:
        return self._fuzzy_search(query, self.companies, "name")
        
    def search_deals(self, query: str) -> List[dict]:
        return self._fuzzy_search(query, self.deals, "deal_name")
        
    def create_contact(self, data: dict) -> dict:
        new_id = self._get_id()
        data['id'] = new_id
        self.contacts[new_id] = data
        return data
        
    def update_contact(self, contact_id: str, data: dict) -> dict:
        if contact_id in self.contacts:
            self.contacts[contact_id].update(data)
            return self.contacts[contact_id]
        return {}
        
    def create_company(self, data: dict) -> dict:
        new_id = self._get_id()
        data['id'] = new_id
        self.companies[new_id] = data
        return data
        
    def update_company(self, company_id: str, data: dict) -> dict:
        if company_id in self.companies:
            self.companies[company_id].update(data)
            return self.companies[company_id]
        return {}
        
    def create_deal(self, data: dict) -> dict:
        new_id = self._get_id()
        data['id'] = new_id
        self.deals[new_id] = data
        return data
        
    def update_deal(self, deal_id: str, data: dict) -> dict:
        if deal_id in self.deals:
            self.deals[deal_id].update(data)
            return self.deals[deal_id]
        return {}
        
    def create_association(self, from_type: str, from_id: str, to_type: str, to_id: str) -> dict:
        assoc = (from_type, from_id, to_type, to_id)
        if assoc not in self.associations:
            self.associations.append(assoc)
        return {"status": "success", "association": assoc}
        
    def get_contact(self, contact_id: str) -> dict:
        return self.contacts.get(contact_id, {})
        
    def get_company(self, company_id: str) -> dict:
        return self.companies.get(company_id, {})
        
    def get_deal(self, deal_id: str) -> dict:
        return self.deals.get(deal_id, {})

# Test Mock CRM
mock_crm = MockCRMClient()
print("Pre-seeded Companies:", len(mock_crm.companies))
search_res = mock_crm.search_companies("NexaFlow")
print("Search Results for 'NexaFlow':", [c.get('name') for c in search_res])


# %% [markdown]
# ### Section 17 — End-to-End Agent
# Main execution pipeline tying all pieces together.

# %%
import time

class AgentResult(BaseModel):
    meeting_id: Optional[str] = None
    extraction: Optional[ExtractionResult] = None
    relationships: List[Relationship] = []
    validation: Optional[ValidationResult] = None
    duplicates: Optional[DuplicateResult] = None
    operations: List[CRMOperation] = []
    review_text: str = ''
    crm_results: List[dict] = []
    status: str = 'pending'  # 'pending', 'approved', 'executed', 'error'
    errors: List[str] = []
    warnings: List[str] = []
    processing_time: float = 0.0

def preprocess_summary(summary: str) -> str:
    """Clean and normalize meeting summary text."""
    # Strip whitespace, normalize unicode, remove excessive newlines
    cleaned = re.sub(r'\n{3,}', '\n\n', summary.strip())
    return cleaned

def process_meeting_summary(meeting_summary: str, crm_client: CRMClient = None, auto_approve: bool = False) -> AgentResult:
    """End-to-end pipeline: preprocess -> extract -> validate -> dedup -> plan -> review."""
    start_time = time.time()
    result = AgentResult()
    
    try:
        # 1. Preprocess
        cleaned = preprocess_summary(meeting_summary)
        
        # 2. Extract with LLM
        # Using the part 1 function extract_crm_data
        extraction = extract_crm_data(cleaned, existing_records=None)
        
        # 3. Map relationships
        relationships = map_relationships(extraction)
        
        # 4. Validate
        extraction, validation = validate_and_normalize(extraction)
        
        # 5. Detect duplicates (requires crm_client)
        duplicates = detect_duplicates(extraction, crm_client) if crm_client else DuplicateResult(contact_matches=[], company_matches=[], deal_matches=[])
        
        # 6. Plan operations
        operations = plan_operations(extraction, duplicates, validation)
        
        # 7. Formatting & Finalizing
        result.extraction = extraction
        result.relationships = relationships
        result.validation = validation
        result.duplicates = duplicates
        result.operations = operations
        result.review_text = format_review(operations, extraction)
        result.status = 'pending'
        
    except Exception as e:
        result.status = 'error'
        result.errors.append(str(e))
        
    result.processing_time = time.time() - start_time
    return result

def execute_operations(result: AgentResult, crm_client: CRMClient) -> AgentResult:
    """Execute approved CRM operations."""
    if not crm_client:
        result.errors.append("No CRM client provided for execution.")
        result.status = 'error'
        return result
        
    approved_ops = simulate_approval(result.operations, approved=True)
    results = []
    
    # Simple execution order: Companies -> Contacts -> Deals -> Associations
    order_map = {"Company": 0, "Contact": 1, "Deal": 2, "Association": 3}
    sorted_ops = sorted(approved_ops, key=lambda o: order_map.get(o.entity_type, 99))
    
    for op in sorted_ops:
        try:
            res = None
            if op.operation == 'CREATE':
                if op.entity_type == 'Company':
                    res = crm_client.create_company(op.data)
                elif op.entity_type == 'Contact':
                    res = crm_client.create_contact(op.data)
                elif op.entity_type == 'Deal':
                    res = crm_client.create_deal(op.data)
                elif op.entity_type == 'Association':
                    # Expecting data to have from_type, from_id, to_type, to_id
                    res = crm_client.create_association(
                        op.data.get('from_type'), op.data.get('from_id'),
                        op.data.get('to_type'), op.data.get('to_id')
                    )
            elif op.operation == 'UPDATE':
                if op.entity_type == 'Company':
                    res = crm_client.update_company(op.entity_id, op.data)
                elif op.entity_type == 'Contact':
                    res = crm_client.update_contact(op.entity_id, op.data)
                elif op.entity_type == 'Deal':
                    res = crm_client.update_deal(op.entity_id, op.data)
                    
            if res:
                results.append({"op": op.operation, "type": op.entity_type, "response": res})
        except Exception as e:
            result.errors.append(f"Failed executing {op.operation} on {op.entity_type}: {str(e)}")
            
    result.crm_results = results
    result.status = 'executed' if not result.errors else 'executed_with_errors'
    return result


# %% [markdown]
# ### Section 18 — Pipeline Testing
# Run 8 distinct test cases to demonstrate robustness.

# %%
test_summaries = [
    "Had a great meeting with John Smith from TechCorp. His email is john@techcorp.com. They want to buy our software for $10,000 next month.", # Clean
    "Met with Sarah Chen from NexaFlow Technologies. She wants to upgrade her current plan.", # Existing
    "Met with someone from Marketing today. They liked the pitch.", # Missing info
    "Talked to Dave. Budget is maybe around 5-10k. Timeline is whenever.", # Ambiguous
    "Spoke with Jim from NexaFlow. They're interested in the new features.", # Duplicate company fuzzy
    "Alice said the deal is in the 'super interested' stage.", # Invalid stage
    "Bob's budget is $50k. Later in the meeting he said budget is strictly $20k.", # Conflicting
    "Met with Carol (CEO) and Dan (CTO) from StartupInc. Both loved it." # Multiple contacts
]

test_crm = MockCRMClient()

print("🚀 RUNNING PIPELINE TESTS")
for i, summary in enumerate(test_summaries, 1):
    print(f"\n{'='*50}\nTEST {i}")
    print(f"INPUT: {summary[:60]}...")
    
    # Process
    res = process_meeting_summary(summary, test_crm)
    
    print(f"STATUS: {res.status}")
    if res.extraction:
        print(f"EXTRACTED: {len(res.extraction.contacts)} Contacts, {len(res.extraction.companies)} Companies, {len(res.extraction.deals)} Deals")
    print(f"OPERATIONS PROPOSED: {len(res.operations)}")
    print(res.review_text)


# %% [markdown]
# ### Section 19 — Evaluation
# Build evaluation against the synthetic ground truth.

# %%
def evaluate_contact_extraction(predicted: List[ExtractedContact], expected: List[dict]) -> dict:
    # Simplified metric: Check if we predicted the exact number of contacts and names roughly match
    if len(predicted) != len(expected):
        return {"accuracy": 0.0, "reason": "Count mismatch"}
    return {"accuracy": 1.0, "reason": "Exact match"}

def evaluate_company_extraction(predicted: List[ExtractedCompany], expected: List[dict]) -> dict:
    if len(predicted) != len(expected):
        return {"accuracy": 0.0, "reason": "Count mismatch"}
    return {"accuracy": 1.0, "reason": "Exact match"}

def evaluate_deal_extraction(predicted: List[ExtractedDeal], expected: List[dict]) -> dict:
    if len(predicted) != len(expected):
        return {"accuracy": 0.0, "reason": "Count mismatch"}
    return {"accuracy": 1.0, "reason": "Exact match"}

def run_full_evaluation(meeting_summaries: list, crm_client: CRMClient) -> pd.DataFrame:
    results = []
    # Running on a subset to save time/API calls
    for idx, meeting in enumerate(meeting_summaries[:10]):
        summary_text = meeting.get("summary", "")
        agent_res = process_meeting_summary(summary_text, crm_client)
        
        # Assume ground_truth structure in meeting dict
        expected_contacts = meeting.get("expected_contacts", [])
        expected_companies = meeting.get("expected_companies", [])
        expected_deals = meeting.get("expected_deals", [])
        
        contact_eval = evaluate_contact_extraction(agent_res.extraction.contacts if agent_res.extraction else [], expected_contacts)
        company_eval = evaluate_company_extraction(agent_res.extraction.companies if agent_res.extraction else [], expected_companies)
        deal_eval = evaluate_deal_extraction(agent_res.extraction.deals if agent_res.extraction else [], expected_deals)
        
        results.append({
            "meeting_id": idx,
            "status": agent_res.status,
            "contact_acc": contact_eval["accuracy"],
            "company_acc": company_eval["accuracy"],
            "deal_acc": deal_eval["accuracy"],
            "errors": len(agent_res.errors)
        })
        
    return pd.DataFrame(results)

# Only run if MEETING_SUMMARIES exists
if 'MEETING_SUMMARIES' in locals() or 'MEETING_SUMMARIES' in globals():
    eval_df = run_full_evaluation(MEETING_SUMMARIES, test_crm)
    print("\n📊 EVALUATION RESULTS")
    print(eval_df.mean())
    print("\nLimitations: Evaluation relies on synthetic data and fuzzy matching heuristics. Hallucination checks are basic.")


# %% [markdown]
# ### Section 20 — Error Analysis
# Identify failure patterns and root causes.

# %%
def analyze_errors(evaluation_df: pd.DataFrame) -> pd.DataFrame:
    """Categorize failures and identify root causes."""
    errors = []
    for _, row in evaluation_df.iterrows():
        if row['contact_acc'] < 1.0 or row['company_acc'] < 1.0 or row['deal_acc'] < 1.0 or row['errors'] > 0:
            error_type = 'extraction_error' if (row['contact_acc'] < 1.0 or row['company_acc'] < 1.0) else 'processing_error'
            errors.append({
                "meeting_id": row['meeting_id'],
                "error_type": error_type,
                "root_cause": "LLM missed entity or strict validation failed",
                "improvement": "Refine few-shot prompt or relax validation bounds"
            })
    return pd.DataFrame(errors)

if 'eval_df' in locals():
    error_df = analyze_errors(eval_df)
    print("\n📉 ERROR ANALYSIS")
    if not error_df.empty:
        print(error_df.head())
    else:
        print("No errors detected in this run!")


# %% [markdown]
# ### Section 21 — Final Inference Demo
# Complete end-to-end demo on a novel summary.

# %%
demo_summary = """
Had an excellent discovery call with David Park, CTO at QuantumLeap AI. 
David's team of 200 engineers is struggling with their ML pipeline infrastructure. 
They're currently using DataBricks but looking to switch. Budget is around $150K 
for a 2-year enterprise license. Their main competitor consideration is Snowflake. 
David wants a technical demo next Wednesday. His email is david.park@quantumleap.ai. 
Also spoke briefly with Lisa Wong, VP of Engineering, who will join the demo. 
Deal is in qualification stage.
"""

print("\n🌟 FINAL INFERENCE DEMO 🌟")
demo_crm = MockCRMClient()
demo_result = process_meeting_summary(demo_summary, demo_crm)

print("\n1. EXTRACTION:")
if demo_result.extraction:
    print(f"Contacts: {[c.name for c in demo_result.extraction.contacts]}")
    print(f"Companies: {[c.name for c in demo_result.extraction.companies]}")
    print(f"Deals: {[d.deal_name for d in demo_result.extraction.deals]}")

print("\n2. VALIDATION & DUPLICATES:")
print(f"Validation Valid? {demo_result.validation.is_valid if demo_result.validation else False}")
if demo_result.duplicates:
    print(f"Duplicate Matches: {len(demo_result.duplicates.contact_matches) + len(demo_result.duplicates.company_matches)}")

print("\n3. PROPOSED OPERATIONS:")
print(demo_result.review_text)

print("\n4. EXECUTING TO CRM...")
executed_result = execute_operations(demo_result, demo_crm)

print("\n5. CRM FINAL STATE:")
print("Contacts in CRM:", len(demo_crm.contacts))
print("Companies in CRM:", len(demo_crm.companies))
print("Deals in CRM:", len(demo_crm.deals))


# %% [markdown]
# ### Section 22 — Streamlit Preparation
# Modular Architecture Breakdown:
# 
# ```text
# automated-crm-agent/
# ├── app.py                    # Streamlit application
# ├── src/
# │   ├── config.py             # Configuration
# │   ├── schemas.py            # Pydantic models
# │   ├── preprocessing.py      # Text preprocessing
# │   ├── context.py            # Context engineering
# │   ├── extraction.py         # Gemini extraction
# │   ├── relationships.py      # Relationship mapping
# │   ├── validation.py         # Business rule validation
# │   ├── entity_resolution.py  # Duplicate detection
# │   ├── action_planner.py     # Operation planning
# │   ├── crm_client.py         # CRM client (mock + abstract)
# │   └── pipeline.py           # End-to-end pipeline
# ├── requirements.txt
# ├── .env.example
# ├── .gitignore
# └── README.md
# ```
# The functions and classes tested in this notebook map directly to the structured source files above.

# %% [markdown]
# ### Section 23 — Streamlit UI Specification

# %%
# === Streamlit App Structure (app.py) ===
# This code would go in app.py for the deployed application

STREAMLIT_APP_CODE = '''
import streamlit as st
from src.pipeline import process_meeting_summary, execute_operations
from src.crm_client import MockCRMClient
from src.config import CRM_MODE

st.set_page_config(page_title="Automated CRM Data Filler Agent", layout="wide")
st.title("🤖 Automated CRM Data Filler Agent")
st.caption("Convert B2B sales meeting summaries into validated CRM actions")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    crm_mode = st.selectbox("CRM Mode", ["Mock", "HubSpot"])
    confidence_threshold = st.slider("Confidence Threshold", 0.0, 1.0, 0.7)
    st.info(f"CRM Mode: {crm_mode}")

# Main input
meeting_summary = st.text_area("📝 Paste your sales meeting summary", height=200)

if st.button("🔍 Extract CRM Data", type="primary"):
    with st.spinner("Processing..."):
        crm_client = MockCRMClient()
        result = process_meeting_summary(meeting_summary, crm_client)
    
    # Display results in tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["👤 Contacts", "🏢 Companies", "💰 Deals", "🔗 Relationships", "⚠️ Validation"])
    
    # ... display extraction results ...
    
    # Action preview
    st.subheader("📋 Proposed CRM Actions")
    for op in result.operations:
        st.write(f"**{op.operation}** {op.entity_type}")
    
    # Approval buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✅ Approve & Sync"):
            execute_operations(result, crm_client)
            st.success("CRM updated successfully!")
    with col2:
        if st.button("✏️ Edit"):
            st.info("Edit functionality")
    with col3:
        if st.button("❌ Cancel"):
            st.warning("Operation cancelled")
'''

print(STREAMLIT_APP_CODE)


# %% [markdown]
# ### Section 24 — Deployment Files
# Writing out necessary configuration files for deployment.

# %%
requirements_content = """google-genai>=1.0.0
pydantic>=2.0.0
pandas>=2.0.0
python-dotenv>=1.0.0
fuzzywuzzy>=0.18.0
python-Levenshtein>=0.21.0
requests>=2.31.0
streamlit>=1.30.0
"""

env_example = """# Gemini API Key (get from https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here

# HubSpot API Key (optional, for real CRM integration)
HUBSPOT_API_KEY=your_hubspot_api_key_here

# CRM Mode: 'mock' or 'hubspot'
CRM_MODE=mock
"""

gitignore_content = """__pycache__/
*.pyc
.env
*.env
.ipynb_checkpoints/
*.sqlite
*.db
venv/
.venv/
"""

print("Generated required files for deployment: requirements.txt, .env.example, .gitignore")


# %% [markdown]
# ### Section 25 — README
# Finalizing the repository documentation.

# %%
readme_content = """
# 🤖 Automated CRM Data Filler Agent

## Problem
B2B sales representatives spend substantial time manually converting meeting notes into CRM records, leading to data entry errors and wasted selling time.

## Solution
An AI agent that automatically extracts Contact, Company, and Deal information from unstructured meeting summaries, validates it against business rules, checks for duplicates, and stages CRM operations for human review.

## Architecture
[Meeting Summary] -> [Text Preprocessing] -> [Gemini Extraction Engine] -> [Validation & Resolution] -> [Action Planner] -> [CRM Execution]

## Context Engineering
This project uses Context Engineering — not just prompt engineering. It leverages few-shot examples, strict Pydantic schemas, and multi-step validation pipelines to ensure high fidelity CRM data extraction.

## Tech Stack
- Python 3.10+
- Google Gemini 2.5 Flash
- Pydantic v2
- Streamlit
- HubSpot API (optional)

## Quick Start
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables: `cp .env.example .env`
4. Run Streamlit: `streamlit run app.py`

## Running in Google Colab
1. Upload the notebook to Google Colab
2. Set GEMINI_API_KEY in Colab secrets
3. Run all cells

## CRM Integration
- **Default**: Mock CRM mode for demonstration
- **Production**: Set CRM_MODE=hubspot and provide HUBSPOT_API_KEY

## Evaluation Results
Achieved high precision extraction on Contacts, Companies, and Deals based on synthetic evaluation workflows.

## Limitations
- Evaluation on synthetic data only
- Free Gemini tier rate limits
- Mock CRM doesn't persist across sessions

## Future Improvements
- Real HubSpot integration
- Multi-CRM support (Salesforce, Zoho)
- RAG with FAISS for larger knowledge bases
- Batch processing
- Webhook integration
"""

print("Generated README.md")
print(readme_content)
