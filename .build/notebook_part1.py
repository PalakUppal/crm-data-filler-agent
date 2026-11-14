# %% [markdown]
# # Automated CRM Data Filler Agent (Part 1)
# 
# ## Section 1 — Project Overview
# 
# **Problem:** B2B sales representatives spend a significant amount of their time manually converting meeting notes, transcripts, and summaries into structured CRM records (Contacts, Companies, Deals, and their associations). This manual data entry is error-prone, time-consuming, and leads to stale or incomplete CRM data.
# 
# **Users:** 
# - **Sales Reps:** To save time and focus on selling.
# - **Sales Managers:** To get accurate pipeline visibility.
# - **Developers:** To maintain and extend the automation workflows.
# 
# **Input:** Unstructured B2B sales meeting summaries (text).
# **Output:** Validated, relationship-aware CRM actions (Creates, Updates, etc.).
# 
# ### Architecture Diagram
# ```text
# Meeting Summary 
#       ↓
# Preprocessing & Entity Resolution (Mock CRM Check)
#       ↓
# Context Engineering (Schema + Rules + Context)
#       ↓
# Gemini 2.5 Flash Extraction (Structured JSON Output)
#       ↓
# Relationship Mapping (WORKS_AT, HAS_OPPORTUNITY)
#       ↓
# Validation (Business Rules)
#       ↓
# Duplicate Detection (Fuzzy matching with CRM state)
#       ↓
# CRM Operation Planning (CREATE, UPDATE, NO_OP, ASK_FOR_REVIEW)
#       ↓
# Human Approval / Execution (CRM API)
# ```
# 
# ### Why this is Context Engineering
# This is not simple Prompt Engineering. We are not just asking an LLM to "extract data." We are assembling a robust, programmatic context. **Context Engineering** involves dynamically injecting our CRM schema, deterministic business rules (e.g., valid deal stages, required fields), existing CRM state, and few-shot examples into the LLM's prompt. We guide the LLM exactly on *how* to represent its confidence, *what* evidence to cite, and *why* it should never hallucinate missing information.

# %% [markdown]
# ## Section 2 — Environment Setup

# %%
# Install required libraries
# !pip install google-genai pydantic pandas python-dotenv fuzzywuzzy python-Levenshtein requests matplotlib -q

import os
import json
import re
import uuid
import datetime
from typing import List, Optional, Any, Dict, Tuple
import pandas as pd
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError
import google.genai as genai
from fuzzywuzzy import fuzz, process
from dotenv import load_dotenv

# Load environment variables if running locally
load_dotenv()

# Setup API Key (In Colab, you would use userdata.get('GEMINI_API_KEY'))
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'YOUR_API_KEY_HERE')

print("Environment Setup Complete.")
print(f"GenAI SDK Version: {genai.__version__}")
print(f"Pandas Version: {pd.__version__}")

# %% [markdown]
# ## Section 3 — Configuration

# %%
class CRMConfig:
    MODEL_NAME = 'gemini-2.5-flash'
    CRM_PLATFORM = 'hubspot'
    CRM_MODE = 'mock'  # 'mock' or 'hubspot'
    CONFIDENCE_THRESHOLD = 0.7
    HIGH_CONFIDENCE_THRESHOLD = 0.9
    VALID_DEAL_STAGES = [
        'appointmentscheduled', 
        'qualifiedtobuy', 
        'presentationscheduled', 
        'decisionmakerboughtin', 
        'contractsent', 
        'closedwon', 
        'closedlost'
    ]
    VALID_CURRENCIES = ['USD', 'EUR', 'GBP', 'INR', 'CAD', 'AUD']
    REQUIRED_CONTACT_FIELDS = ['name']
    REQUIRED_COMPANY_FIELDS = ['name']
    REQUIRED_DEAL_FIELDS = ['deal_name']
    MAX_RETRIES = 3

CONFIG = {k: v for k, v in CRMConfig.__dict__.items() if not k.startswith('__')}
print("--- CRM Configuration ---")
for key, value in CONFIG.items():
    print(f"{key}: {value}")

# %% [markdown]
# ## Section 4 — Meeting Summary Dataset

# %%
def generate_synthetic_dataset() -> List[Dict]:
    """Generates 40 synthetic meeting summaries covering 20 different scenarios (2 examples each)."""
    dataset = []
    
    # Base templates and variations for the 20 scenarios
    scenarios = [
        # 1. Clean meeting summary with all information
        {
            "type": "clean",
            "summary": "Met with Sarah Chen, VP of Engineering at CloudScale Industries (sarah.c@cloudscale.com, 555-0192). They are a SaaS company with 500 employees looking to upgrade their data infrastructure. Budget is clearly defined at $120,000 USD. We agreed to move to the 'presentationscheduled' stage for the 'CloudScale Q3 Infrastructure Upgrade' deal. Next step is a technical demo next Tuesday.",
        },
        {
            "type": "clean",
            "summary": "Great intro call with Marcus Rodriguez, Director of Sales at NexaFlow Technologies. NexaFlow is an Enterprise FinTech firm (1200 people). Marcus (marcus.r@nexaflow.tech, 555-9834) confirmed a $85,000 USD budget for the 'NexaFlow CRM Migration' project. They are currently 'qualifiedtobuy'. He is the primary decision maker.",
        },
        
        # 2. Short summary (2-3 sentences)
        {
            "type": "short_summary",
            "summary": "Spoke to Priya Sharma at DataForge Analytics. She wants to buy our pro tier software for $15,000. Deal name is 'DataForge Pro Tier'.",
        },
        {
            "type": "short_summary",
            "summary": "James O'Brien from BrightPath Solutions called. Moving 'BrightPath Expansion' deal to contractsent. Value: $40,000.",
        },

        # 3. Long detailed summary (paragraph+)
        {
            "type": "long_detailed",
            "summary": "We had an extensive 90-minute discovery workshop with the team from Vertex Manufacturing. The primary contact was David Kim, the Chief Operating Officer (david.kim@vertexmfg.com, +1-555-0199). Vertex is a traditional manufacturing firm dealing with supply chain modernization challenges, currently sitting at around 850 employees. We discussed the 'Vertex Supply Chain Modernization' deal. The current legacy system is failing them, leading to a 15% drop in efficiency. They have allocated a budget of $250,000 USD for this year. Competitors mentioned include Oracle and SAP. We are moving this opportunity to 'decisionmakerboughtin' since David gave verbal approval. Next steps involve legal review.",
        },
        {
            "type": "long_detailed",
            "summary": "Met with Elena Rostova, VP of Marketing at Global E-commerce Partners (elena.r@gep.net). GEP has 300 employees and is struggling with customer retention metrics. The 'GEP Retention Platform' deal is progressing nicely. During the hour-long session, we mapped out their entire user journey. Elena is highly motivated to solve this before Q4. The deal value is estimated at $65,000 EUR. They are currently evaluating us against Salesforce. I'm moving the deal stage to 'presentationscheduled' because she wants her entire team to see the platform next week. Her phone number is 555-8821.",
        },

        # 4. Conversational/informal style
        {
            "type": "informal_style",
            "summary": "Hey team, just got off the phone with Tom from HealthTech Innovators. He's totally sold on our idea. Tom's email is tom@healthtech.com. Deal 'HealthTech Pilot' is worth like 20k USD. Put it in qualifiedtobuy.",
        },
        {
            "type": "informal_style",
            "summary": "Awesome catchup with Rachel over at SaaSify today. She's the CEO (rach@saasify.io). Wants to do the 'SaaSify Enterprise' package, guessing it'll be around 50k. Moving to appointmentscheduled.",
        },

        # 5. Bullet-point format
        {
            "type": "bullet_points",
            "summary": "- Client: Apex Logistics\n- Contact: Michael Chang (Logistics Manager)\n- Email: m.chang@apex.com\n- Deal: Apex Routing Software ($35,000 USD)\n- Stage: qualifiedtobuy",
        },
        {
            "type": "bullet_points",
            "summary": "* Company: Quantum Financial\n* Person: Sarah Jenkins\n* Phone: 555-4432\n* Deal Name: Quantum Audit Automation\n* Value: 90,000 EUR\n* Status: presentationscheduled",
        },

        # 6. Missing email
        {
            "type": "missing_email",
            "summary": "Met with Robert Hughes, CFO of ConstructCorp. Phone is 555-1122. Discussed the 'ConstructCorp Q1 License' deal for $25,000. Stage is qualifiedtobuy.",
        },
        {
            "type": "missing_email",
            "summary": "Talked to Amanda at RetailGiant. She is the Head of Procurement. The 'RetailGiant Bulk Order' is for $120,000 USD. Reached her at 555-9988. Stage: contractsent.",
        },

        # 7. Missing phone
        {
            "type": "missing_phone",
            "summary": "Chatted with Leo Tolstoy, Author at Classic Books Inc. Email is leo@classicbooks.com. Deal 'Classic Books digitization' is $10,000 USD. Stage: appointmentscheduled.",
        },
        {
            "type": "missing_phone",
            "summary": "Emailed with Clara from TechStartups. Clara.s@techstartups.io. Moving 'TechStartups Seed Package' to qualifiedtobuy. Value is 5000 USD.",
        },

        # 8. No explicit budget/deal value
        {
            "type": "no_explicit_budget",
            "summary": "Met with Tim Cook at AppleCore. tim@applecore.com. He's interested in the 'AppleCore Cloud Migration' deal. Moving to presentationscheduled, but we haven't discussed pricing yet.",
        },
        {
            "type": "no_explicit_budget",
            "summary": "Discussed 'BetaCorp Analytics' with Mary (mary@betacorp.com). She is the CTO of BetaCorp. Stage is qualifiedtobuy. Need to send a pricing sheet next.",
        },

        # 9. Ambiguous timeline
        {
            "type": "ambiguous_timeline",
            "summary": "Spoke to Dan at FutureVision (dan@fv.com). 'FV NextGen AI' deal ($45,000) is qualifiedtobuy. He said they might sign sometime later this year or early next year.",
        },
        {
            "type": "ambiguous_timeline",
            "summary": "Lisa from EduTech Solutions (lisa@edutech.org) loves the 'EduTech Platform' deal. $30,000 USD. Stage: decisionmakerboughtin. Timeline is whenever they get their next funding round.",
        },

        # 10. Contains one competitor
        {
            "type": "one_competitor",
            "summary": "Met Paul from AutoMakers (paul@automakers.com). Deal: 'AutoMakers CRM' ($55,000). Stage: presentationscheduled. They are also looking at HubSpot heavily.",
        },
        {
            "type": "one_competitor",
            "summary": "Nina from BioPharma (nina@biopharma.com) said the 'BioPharma LIMS' deal ($150,000) is at contractsent. We just need to beat Veeva Systems.",
        },

        # 11. Contains multiple competitors
        {
            "type": "multiple_competitors",
            "summary": "Called Greg from SkyAirlines (greg@sky.com). The 'SkyAirlines Booking Engine' ($200,000) is at qualifiedtobuy. They are evaluating us, Salesforce, and Microsoft Dynamics.",
        },
        {
            "type": "multiple_competitors",
            "summary": "Talked to Sam at RetailX (sam@retailx.com). Deal 'RetailX POS' ($75,000). Stage: presentationscheduled. Mentioned they are currently talking to Square, Toast, and Lightspeed.",
        },

        # 12. Existing customer scenario
        {
            "type": "existing_customer",
            "summary": "Quarterly review with existing client, MegaCorp. Talked to existing contact Jane Doe (jane@megacorp.com). Discussed a new upsell deal 'MegaCorp Expansion 2024' for $30,000. Stage: qualifiedtobuy.",
        },
        {
            "type": "existing_customer",
            "summary": "Renewal call with John Smith at OldReliable Inc (john@oldreliable.com). They are renewing the 'OldReliable Annual License' for $12,000. Moved to closedwon.",
        },

        # 13. Contact already exists (same email)
        {
            "type": "contact_exists",
            "summary": "Follow up with existing prospect Alan Turing (alan.t@enigma.com) from Enigma Corp. Starting a new deal 'Enigma Decryption Services' for $95,000. Stage: appointmentscheduled.",
        },
        {
            "type": "contact_exists",
            "summary": "Grace Hopper (grace@navy.gov) reached out again. She's at NavyTech now. New deal 'NavyTech Compiler' for $45,000. Stage: qualifiedtobuy.",
        },

        # 14. Company already exists (same name)
        {
            "type": "company_exists",
            "summary": "Met a new person at Acme Corp: Wile E. Coyote (wile@acme.com). He's buying the 'Acme Rocket Skates' for $15,000. Stage: contractsent.",
        },
        {
            "type": "company_exists",
            "summary": "Spoke to new hire Daffy Duck (daffy@wb.com) at Warner Bros. 'WB Animation Suite' deal is for $80,000. Stage: presentationscheduled.",
        },

        # 15. Both contact and company exist
        {
            "type": "both_exist",
            "summary": "Quick touchbase with Bruce Wayne (bruce@wayneenterprises.com) at Wayne Enterprises. 'Wayne Security Update' deal ($500,000) is closedwon.",
        },
        {
            "type": "both_exist",
            "summary": "Checked in with Clark Kent (clark@dailyplanet.com) at Daily Planet. 'Planet CMS' deal ($25,000) is decisionmakerboughtin.",
        },

        # 16. Conflicting information
        {
            "type": "conflicting_info",
            "summary": "Spoke to Alice at Wonderland Inc. Email is alice@wonderland.com, but she also said to use alice.liddell@gmail.com. Deal 'Wonderland Portal' might be $10k, but she later mentioned $20k. Stage is qualifiedtobuy.",
        },
        {
            "type": "conflicting_info",
            "summary": "Met Bob Builder (bob@build.com) at ConstructionCo. Deal is 'Build Tools'. He said budget is USD, but the RFP says EUR. Amount is 50,000. Stage: presentationscheduled.",
        },

        # 17. Implicit deal value
        {
            "type": "implicit_value",
            "summary": "Met with Charlie (charlie@chocolate.com) at Wonka Industries. The 'Wonka Factory Sensors' deal is in qualifiedtobuy stage. He mentioned they have around thirty grand set aside for this.",
        },
        {
            "type": "implicit_value",
            "summary": "Talked to Dorothy (dorothy@oz.com) from Emerald City Corp. The 'Emerald Pathway' deal is presentationscheduled. Cost is looking like half a million dollars.",
        },

        # 18. Explicit deal value
        {
            "type": "explicit_value",
            "summary": "Talked to Evan (evan@startup.com) at FastStartup. 'FastStartup Series A Tools' deal is strictly $42,500 USD. Stage is contractsent.",
        },
        {
            "type": "explicit_value",
            "summary": "Met Fiona (fiona@swamp.com) at Ogre LLC. 'Ogre Swamp Drainage' deal is $115,000 EUR. Stage: decisionmakerboughtin.",
        },

        # 19. Multiple contacts mentioned
        {
            "type": "multiple_contacts",
            "summary": "Met with the DataCorp team. Main contact is George (george@datacorp.com), the CEO. Also present was Hannah (hannah@datacorp.com), the CTO. The 'DataCorp AI Platform' deal ($150,000) is in presentationscheduled.",
        },
        {
            "type": "multiple_contacts",
            "summary": "Call with MarketingInc. Ian (ian@marketinginc.com) and Jenny (jenny@marketinginc.com) attended. Ian is the decision maker. Deal 'MarketingInc Automation' ($60,000) is qualifiedtobuy.",
        },

        # 20. Multiple companies mentioned
        {
            "type": "multiple_companies",
            "summary": "Spoke with Kevin (kevin@synergy.com) from SynergyTech. They are partnering with GlobalNet for the 'Synergy-Global Joint Infrastructure' deal ($300,000). Stage: appointmentscheduled. Kevin is driving it for SynergyTech.",
        },
        {
            "type": "multiple_companies",
            "summary": "Met Laura (laura@alpha.com) from AlphaGroup. She is moving from BetaCorp. Deal is 'AlphaGroup Implementation' for $45,000. Stage: qualifiedtobuy.",
        }
    ]
    
    # Generate the 40 items
    for i, s in enumerate(scenarios):
        dataset.append({
            "meeting_id": str(uuid.uuid4()),
            "summary": s["summary"],
            "scenario_type": s["type"],
            "notes": f"Scenario {s['type']} - Example {(i % 2) + 1}",
            # For simplicity in this mock data, we leave expected objects empty as we focus on LLM extraction output.
            "expected_contacts": [],
            "expected_companies": [],
            "expected_deals": [],
            "expected_relationships": []
        })
        
    return dataset

MEETING_SUMMARIES = generate_synthetic_dataset()
df_meetings = pd.DataFrame(MEETING_SUMMARIES)

# %% [markdown]
# ## Section 5 — Dataset Exploration

# %%
print(f"Total Meeting Summaries: {len(df_meetings)}")

# Calculate lengths
df_meetings['char_length'] = df_meetings['summary'].apply(len)
df_meetings['word_count'] = df_meetings['summary'].apply(lambda x: len(x.split()))

print("\n--- Summary Length Statistics (Characters) ---")
print(df_meetings['char_length'].describe())

print("\n--- Summary Length Statistics (Words) ---")
print(df_meetings['word_count'].describe())

print("\n--- Distribution of Scenario Types ---")
print(df_meetings['scenario_type'].value_counts())

# Simple Text-based Histogram for Colab output
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 4))
plt.hist(df_meetings['word_count'], bins=10, color='skyblue', edgecolor='black')
plt.title('Distribution of Word Counts in Meeting Summaries')
plt.xlabel('Word Count')
plt.ylabel('Frequency')
plt.grid(axis='y', alpha=0.75)
plt.show()

print("\n--- Example Summaries ---")
examples = df_meetings[df_meetings['scenario_type'].isin(['clean', 'missing_email', 'multiple_contacts'])].drop_duplicates(subset=['scenario_type'])
for _, row in examples.iterrows():
    print(f"\n[{row['scenario_type'].upper()}]")
    print(row['summary'])

# Simple regex heuristics to count occurrences for EDA
has_email = df_meetings['summary'].apply(lambda x: bool(re.search(r'[\w\.-]+@[\w\.-]+', x)))
has_phone = df_meetings['summary'].apply(lambda x: bool(re.search(r'\d{3}[-\.\s]??\d{4}', x)))
has_money = df_meetings['summary'].apply(lambda x: bool(re.search(r'\$|\b(USD|EUR)\b|\bgrand\b|\bthousand\b', x, re.IGNORECASE)))

print(f"\n--- Heuristic Check ---")
print(f"Summaries with Email: {has_email.sum()}")
print(f"Summaries with Phone: {has_phone.sum()}")
print(f"Summaries with Deal Value mentioned: {has_money.sum()}")

# %% [markdown]
# ## Section 6 — CRM Schema (Pydantic Models)

# %%
class ExtractedField(BaseModel):
    value: Any
    confidence: float = 1.0
    evidence: Optional[str] = None

class ExtractedContact(BaseModel):
    name: str
    designation: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    seniority: Optional[str] = None
    decision_making_authority: Optional[str] = None
    decision_maker_flag: Optional[bool] = None
    preferred_contact_method: Optional[str] = None
    availability: Optional[str] = None
    timezone: Optional[str] = None
    confidence: float = 0.0
    evidence: List[str] = []

class ExtractedCompany(BaseModel):
    name: str
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    website: Optional[str] = None
    business_challenges: Optional[List[str]] = None
    pain_points: Optional[List[str]] = None
    technology_stack: Optional[List[str]] = None
    competitors: Optional[List[str]] = None
    budget_range: Optional[str] = None
    growth_stage: Optional[str] = None
    confidence: float = 0.0
    evidence: List[str] = []

class ExtractedDeal(BaseModel):
    deal_name: str
    value: Optional[float] = None
    currency: Optional[str] = 'USD'
    timeline: Optional[str] = None
    sales_stage: Optional[str] = None
    decision_criteria: Optional[List[str]] = None
    next_steps: Optional[List[str]] = None
    proposal_requirements: Optional[List[str]] = None
    competitors: Optional[List[str]] = None
    competitive_differentiators: Optional[List[str]] = None
    confidence: float = 0.0
    evidence: List[str] = []

class Relationship(BaseModel):
    source: str
    relation_type: str  # WORKS_AT, STAKEHOLDER_FOR, HAS_OPPORTUNITY
    target: str
    confidence: float = 0.0
    evidence: Optional[str] = None

class ExtractionResult(BaseModel):
    contacts: List[ExtractedContact] = Field(default_factory=list)
    companies: List[ExtractedCompany] = Field(default_factory=list)
    deals: List[ExtractedDeal] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    raw_response: Optional[str] = None

# Test instantiation
test_contact = ExtractedContact(name="Alice Smith", email="alice@test.com", confidence=0.95, evidence=["Met with Alice Smith (alice@test.com)"])
print("Test Pydantic Model Instantiation:")
print(test_contact.model_dump_json(indent=2))


# %% [markdown]
# ## Section 7 — CRM Business Rules

# %%
class ValidationError(BaseModel):
    field: str
    entity_type: str
    error_type: str
    message: str
    severity: str = 'error'

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)

def validate_email(email: str) -> bool:
    if not email:
        return True # Optional field
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    if not phone:
        return True # Optional field
    # Basic check: at least 7 digits, allowing +, -, spaces
    digits = re.sub(r'\D', '', phone)
    return len(digits) >= 7

def validate_deal_stage(stage: str) -> bool:
    if not stage:
        return True
    return stage.lower() in CRMConfig.VALID_DEAL_STAGES

def validate_contact(contact: ExtractedContact) -> ValidationResult:
    errors = []
    warnings = []
    
    if not contact.name:
        errors.append(ValidationError(field="name", entity_type="contact", error_type="missing_required", message="Contact name is required."))
    
    if contact.email and not validate_email(contact.email):
        errors.append(ValidationError(field="email", entity_type="contact", error_type="invalid_format", message=f"Invalid email format: {contact.email}"))
        
    if contact.phone and not validate_phone(contact.phone):
        warnings.append(ValidationError(field="phone", entity_type="contact", error_type="invalid_format", message=f"Phone number looks unusual: {contact.phone}", severity="warning"))
        
    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

def validate_company(company: ExtractedCompany) -> ValidationResult:
    errors = []
    if not company.name:
        errors.append(ValidationError(field="name", entity_type="company", error_type="missing_required", message="Company name is required."))
    
    if company.employee_count is not None and company.employee_count < 0:
        errors.append(ValidationError(field="employee_count", entity_type="company", error_type="invalid_value", message="Employee count cannot be negative."))
        
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)

def validate_deal(deal: ExtractedDeal) -> ValidationResult:
    errors = []
    if not deal.deal_name:
        errors.append(ValidationError(field="deal_name", entity_type="deal", error_type="missing_required", message="Deal name is required."))
        
    if deal.value is not None and deal.value < 0:
        errors.append(ValidationError(field="value", entity_type="deal", error_type="negative_value", message="Deal value cannot be negative."))
        
    if deal.sales_stage and not validate_deal_stage(deal.sales_stage):
        errors.append(ValidationError(field="sales_stage", entity_type="deal", error_type="invalid_stage", message=f"Invalid deal stage: {deal.sales_stage}"))
        
    if deal.currency and deal.currency not in CRMConfig.VALID_CURRENCIES:
        errors.append(ValidationError(field="currency", entity_type="deal", error_type="invalid_value", message=f"Invalid currency: {deal.currency}"))
        
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)

def validate_extraction(result: ExtractionResult) -> ValidationResult:
    all_errors = []
    all_warnings = []
    
    for c in result.contacts:
        v = validate_contact(c)
        all_errors.extend(v.errors)
        all_warnings.extend(v.warnings)
        
    for comp in result.companies:
        v = validate_company(comp)
        all_errors.extend(v.errors)
        all_warnings.extend(v.warnings)
        
    for d in result.deals:
        v = validate_deal(d)
        all_errors.extend(v.errors)
        all_warnings.extend(v.warnings)
        
    return ValidationResult(is_valid=len(all_errors) == 0, errors=all_errors, warnings=all_warnings)

# Test Validation
print("--- Testing Business Rules ---")
bad_deal = ExtractedDeal(deal_name="", value=-100, sales_stage="fake_stage", currency="XYZ")
bad_validation = validate_deal(bad_deal)
print(bad_validation.model_dump_json(indent=2))


# %% [markdown]
# ## Section 8 — Context Engineering

# %%
def build_context(meeting_summary: str, existing_records: dict = None, config: dict = None) -> str:
    """Assembles the robust context for the LLM."""
    if config is None:
        config = CONFIG
        
    existing_str = json.dumps(existing_records, indent=2) if existing_records else "None"
    
    prompt = f"""
SYSTEM ROLE:
You are an expert CRM Data Extraction Agent. Your task is to accurately map unstructured B2B meeting summaries into a structured JSON schema for a CRM system. 
You are meticulous, objective, and strict.

BUSINESS RULES & CONSTRAINTS:
1. DO NOT HALLUCINATE OR INVENT DATA. If a field is not explicitly mentioned or clearly implied, use `null`.
2. Confidence scores should strictly reflect how explicitly the data was stated (0.0 to 1.0).
3. Always provide exact quote strings as `evidence` where applicable.
4. VALID DEAL STAGES: {config['VALID_DEAL_STAGES']}
5. VALID CURRENCIES: {config['VALID_CURRENCIES']}
6. Normalize money amounts to purely numerical values (e.g., "$30k" -> 30000).
7. Required fields for Contact: {config['REQUIRED_CONTACT_FIELDS']}
8. Required fields for Company: {config['REQUIRED_COMPANY_FIELDS']}
9. Required fields for Deal: {config['REQUIRED_DEAL_FIELDS']}

EXISTING CRM RECORDS (Use this to resolve ambiguities, if provided):
{existing_str}

FEW-SHOT EXAMPLE:
Input: "Met with Sarah (sarah@test.com) from Acme Corp. Selling them Acme Pro for $50k. Moving to qualifiedtobuy."
Expected Logic: Extract Contact (Sarah, sarah@test.com), Company (Acme Corp), Deal (Acme Pro, 50000 USD, qualifiedtobuy). Add relationship WORKS_AT from Sarah to Acme Corp.

INSTRUCTIONS:
Read the following meeting summary. Extract the Contacts, Companies, Deals, and their Relationships.
Return the result strictly as a valid JSON object conforming to the provided schema.

MEETING SUMMARY:
{meeting_summary}
"""
    return prompt

print("--- Example Context ---")
print(build_context("Test meeting summary"))

# %% [markdown]
# ## Section 9 — LLM Extraction

# %%
def extract_crm_data(meeting_summary: str, existing_records: dict = None) -> ExtractionResult:
    """Calls Gemini to perform structured extraction based on engineered context."""
    context = build_context(meeting_summary, existing_records)
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    retries = 0
    while retries < CRMConfig.MAX_RETRIES:
        try:
            response = client.models.generate_content(
                model=CRMConfig.MODEL_NAME,
                contents=context,
                config=genai.types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=ExtractionResult,
                    temperature=0.1,
                )
            )
            
            raw_text = response.text
            
            # Pydantic validation
            parsed_dict = json.loads(raw_text)
            extraction = ExtractionResult(**parsed_dict)
            extraction.raw_response = raw_text
            
            return extraction
            
        except PydanticValidationError as e:
            print(f"Pydantic Validation Error on attempt {retries+1}: {e}")
            retries += 1
        except Exception as e:
            print(f"Extraction Error on attempt {retries+1}: {e}")
            retries += 1
            
    # Return empty result if all retries fail
    print("Failed to extract data after maximum retries.")
    return ExtractionResult()

# To actually test this, you must have a valid GEMINI_API_KEY.
# For notebook continuity, we mock the call if no key is found.
def mock_extract_crm_data(meeting_summary: str) -> ExtractionResult:
    """Mock implementation for testing without API Key"""
    if "Sarah Chen" in meeting_summary:
        return ExtractionResult(
            contacts=[ExtractedContact(name="Sarah Chen", email="sarah.c@cloudscale.com", phone="555-0192", confidence=0.99)],
            companies=[ExtractedCompany(name="CloudScale Industries", employee_count=500, confidence=0.99)],
            deals=[ExtractedDeal(deal_name="CloudScale Q3 Infrastructure Upgrade", value=120000.0, sales_stage="presentationscheduled", confidence=0.99)]
        )
    return ExtractionResult()

print("--- Testing LLM Extraction (Mocked) ---")
test_summary = df_meetings.iloc[0]['summary']
res = mock_extract_crm_data(test_summary) # Replace with extract_crm_data(test_summary) in actual run
print(res.model_dump_json(indent=2))


# %% [markdown]
# ## Section 10 — Relationship Mapping

# %%
def map_relationships(extraction: ExtractionResult) -> List[Relationship]:
    """Infers relationships based on extracted entities, avoiding duplicates."""
    relationships = extraction.relationships.copy()
    existing_pairs = {(r.source, r.relation_type, r.target) for r in relationships}
    
    # Heuristic: If 1 company and 1 contact, they likely work there
    if len(extraction.contacts) == 1 and len(extraction.companies) == 1:
        c_name = extraction.contacts[0].name
        comp_name = extraction.companies[0].name
        pair = (c_name, "WORKS_AT", comp_name)
        if pair not in existing_pairs:
            relationships.append(Relationship(source=c_name, relation_type="WORKS_AT", target=comp_name, confidence=0.8, evidence="Inferred from single entity context"))
            existing_pairs.add(pair)
            
    # Heuristic: If 1 deal and 1 contact, they are a stakeholder
    if len(extraction.contacts) == 1 and len(extraction.deals) == 1:
        c_name = extraction.contacts[0].name
        d_name = extraction.deals[0].deal_name
        pair = (c_name, "STAKEHOLDER_FOR", d_name)
        if pair not in existing_pairs:
            relationships.append(Relationship(source=c_name, relation_type="STAKEHOLDER_FOR", target=d_name, confidence=0.8, evidence="Inferred from single entity context"))
            existing_pairs.add(pair)
            
    # Heuristic: If 1 deal and 1 company, the deal belongs to the company
    if len(extraction.companies) == 1 and len(extraction.deals) == 1:
        comp_name = extraction.companies[0].name
        d_name = extraction.deals[0].deal_name
        pair = (comp_name, "HAS_OPPORTUNITY", d_name)
        if pair not in existing_pairs:
            relationships.append(Relationship(source=comp_name, relation_type="HAS_OPPORTUNITY", target=d_name, confidence=0.8, evidence="Inferred from single entity context"))
            existing_pairs.add(pair)

    return relationships

print("--- Testing Relationship Mapping ---")
mapped_rels = map_relationships(res)
for r in mapped_rels:
    print(r)

# %% [markdown]
# ## Section 11 — Validation Pipeline

# %%
def validate_and_normalize(extraction: ExtractionResult) -> Tuple[ExtractionResult, ValidationResult]:
    # Normalize data
    for c in extraction.contacts:
        if c.email:
            c.email = c.email.lower().strip()
        if c.phone:
            # Strip extra spaces
            c.phone = c.phone.strip()
            
    for d in extraction.deals:
        if d.sales_stage:
            d.sales_stage = d.sales_stage.lower().replace(" ", "").replace("_", "")
            
    # Map Relationships
    extraction.relationships = map_relationships(extraction)
            
    # Run Validation
    validation_res = validate_extraction(extraction)
    return extraction, validation_res

print("--- Testing Validation Pipeline ---")
normalized_ext, val_res = validate_and_normalize(res)
print(f"Is Valid: {val_res.is_valid}")


# %% [markdown]
# ## Section 12 — Duplicate Detection & Entity Resolution

# %%
class DuplicateMatch(BaseModel):
    match_found: bool
    match_type: str
    confidence: float
    existing_id: Optional[str] = None
    existing_record: Optional[dict] = None
    details: Optional[str] = None

class DuplicateResult(BaseModel):
    contact_matches: List[DuplicateMatch] = Field(default_factory=list)
    company_matches: List[DuplicateMatch] = Field(default_factory=list)
    deal_matches: List[DuplicateMatch] = Field(default_factory=list)

# Mock CRM Database for duplicate matching
MOCK_CRM_DB = {
    "contacts": [
        {"id": "c1", "name": "Alan Turing", "email": "alan.t@enigma.com", "company_id": "comp1"},
        {"id": "c2", "name": "Sarah Chen", "email": "sarah.c@cloudscale.com", "company_id": "comp2"}
    ],
    "companies": [
        {"id": "comp1", "name": "Enigma Corp", "domain": "enigma.com"},
        {"id": "comp2", "name": "CloudScale Industries", "domain": "cloudscale.com"}
    ],
    "deals": [
        {"id": "d1", "deal_name": "Enigma Decryption Services", "company_id": "comp1"}
    ]
}

def detect_duplicates(extraction: ExtractionResult, crm_db: dict) -> DuplicateResult:
    result = DuplicateResult()
    
    # Check Contacts
    for c in extraction.contacts:
        match = DuplicateMatch(match_found=False, match_type="none", confidence=0.0)
        # Priority 1: Email exact match
        if c.email:
            for db_c in crm_db['contacts']:
                if db_c.get('email') == c.email:
                    match = DuplicateMatch(match_found=True, match_type="exact_email", confidence=1.0, existing_id=db_c['id'], existing_record=db_c)
                    break
        
        # Priority 2: Fuzzy Name Match (fallback)
        if not match.match_found and c.name:
            db_names = [db_c['name'] for db_c in crm_db['contacts']]
            if db_names:
                best_match, score = process.extractOne(c.name, db_names, scorer=fuzz.token_sort_ratio)
                if score >= 85:
                    db_c = next(item for item in crm_db['contacts'] if item["name"] == best_match)
                    match = DuplicateMatch(match_found=True, match_type="fuzzy_name", confidence=score/100.0, existing_id=db_c['id'], existing_record=db_c)
                    
        result.contact_matches.append(match)
        
    # Check Companies
    for comp in extraction.companies:
        match = DuplicateMatch(match_found=False, match_type="none", confidence=0.0)
        
        if comp.name:
            db_names = [db_comp['name'] for db_comp in crm_db['companies']]
            if db_names:
                best_match, score = process.extractOne(comp.name, db_names, scorer=fuzz.token_sort_ratio)
                if score >= 90:
                    db_comp = next(item for item in crm_db['companies'] if item["name"] == best_match)
                    match = DuplicateMatch(match_found=True, match_type="fuzzy_name", confidence=score/100.0, existing_id=db_comp['id'], existing_record=db_comp)
                    
        result.company_matches.append(match)

    # Check Deals (Simplified to fuzzy name check)
    for d in extraction.deals:
        match = DuplicateMatch(match_found=False, match_type="none", confidence=0.0)
        if d.deal_name:
            db_names = [db_d['deal_name'] for db_d in crm_db['deals']]
            if db_names:
                best_match, score = process.extractOne(d.deal_name, db_names, scorer=fuzz.token_sort_ratio)
                if score >= 90:
                    db_d = next(item for item in crm_db['deals'] if item["deal_name"] == best_match)
                    match = DuplicateMatch(match_found=True, match_type="fuzzy_name", confidence=score/100.0, existing_id=db_d['id'], existing_record=db_d)
        result.deal_matches.append(match)

    return result

print("--- Testing Duplicate Detection ---")
dupe_res = detect_duplicates(normalized_ext, MOCK_CRM_DB)
print(dupe_res.model_dump_json(indent=2))


# %% [markdown]
# ## Section 13 — CRM Operation Planning (Action Planner)

# %%
class CRMOperation(BaseModel):
    entity_type: str
    operation: str  # 'CREATE', 'UPDATE', 'NO_OP', 'ASK_FOR_REVIEW'
    entity_id: Optional[str] = None
    data: dict = Field(default_factory=dict)
    reason: str = ''
    evidence: List[str] = Field(default_factory=list)
    current_values: Optional[dict] = None
    proposed_values: Optional[dict] = None
    warnings: List[str] = Field(default_factory=list)

def plan_operations(extraction: ExtractionResult, duplicates: DuplicateResult, validation: ValidationResult) -> List[CRMOperation]:
    operations = []
    
    # Process Contacts
    for i, contact in enumerate(extraction.contacts):
        match = duplicates.contact_matches[i]
        
        if match.match_found and match.confidence >= CRMConfig.HIGH_CONFIDENCE_THRESHOLD:
            # We have a strong match. Check if there's new data to update.
            # (Simplified check: if phone is provided and wasn't in mock DB)
            has_new_data = False
            updates = {}
            if contact.phone and not match.existing_record.get('phone'):
                has_new_data = True
                updates['phone'] = contact.phone
                
            if has_new_data:
                operations.append(CRMOperation(
                    entity_type="contact", operation="UPDATE", entity_id=match.existing_id,
                    data=updates, reason="High confidence match with new data",
                    current_values=match.existing_record, proposed_values=updates
                ))
            else:
                operations.append(CRMOperation(
                    entity_type="contact", operation="NO_OP", entity_id=match.existing_id,
                    reason="Entity exists, no new actionable data."
                ))
        elif match.match_found and match.confidence < CRMConfig.HIGH_CONFIDENCE_THRESHOLD:
            operations.append(CRMOperation(
                entity_type="contact", operation="ASK_FOR_REVIEW", entity_id=match.existing_id,
                data=contact.model_dump(), reason=f"Fuzzy match with {match.confidence} confidence. Requires human review."
            ))
        else:
            operations.append(CRMOperation(
                entity_type="contact", operation="CREATE", data=contact.model_dump(),
                reason="No matching existing record found."
            ))
            
    # Similar logic for Companies
    for i, company in enumerate(extraction.companies):
        match = duplicates.company_matches[i]
        if match.match_found:
             operations.append(CRMOperation(
                entity_type="company", operation="NO_OP", entity_id=match.existing_id,
                reason="Company already exists."
            ))
        else:
             operations.append(CRMOperation(
                entity_type="company", operation="CREATE", data=company.model_dump(),
                reason="New company."
            ))
             
    # Similar logic for Deals
    for i, deal in enumerate(extraction.deals):
        match = duplicates.deal_matches[i]
        if match.match_found:
             operations.append(CRMOperation(
                entity_type="deal", operation="UPDATE", entity_id=match.existing_id,
                data=deal.model_dump(), reason="Updating existing deal status/value."
            ))
        else:
             operations.append(CRMOperation(
                entity_type="deal", operation="CREATE", data=deal.model_dump(),
                reason="New deal opportunity."
            ))

    return operations

print("--- Testing Operation Planning ---")
ops = plan_operations(normalized_ext, dupe_res, val_res)
for op in ops:
    print(op.model_dump_json(indent=2))

