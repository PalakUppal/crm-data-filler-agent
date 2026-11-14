from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any

class ExtractedField(BaseModel):
    value: str | int | float | bool | list[str] | None = None
    confidence: float
    evidence: List[str]

class ExtractedContact(BaseModel):
    name: Optional[ExtractedField] = None
    designation_title: Optional[ExtractedField] = None
    email: Optional[ExtractedField] = None
    phone: Optional[ExtractedField] = None
    department: Optional[ExtractedField] = None
    seniority: Optional[ExtractedField] = None
    decision_making_authority: Optional[ExtractedField] = None
    decision_maker_flag: Optional[ExtractedField] = None
    preferred_contact_method: Optional[ExtractedField] = None
    availability: Optional[ExtractedField] = None
    timezone: Optional[ExtractedField] = None

class ExtractedCompany(BaseModel):
    name: Optional[ExtractedField] = None
    industry: Optional[ExtractedField] = None
    employee_count: Optional[ExtractedField] = None
    website: Optional[ExtractedField] = None
    business_challenges: Optional[ExtractedField] = None
    pain_points: Optional[ExtractedField] = None
    technology_stack: Optional[ExtractedField] = None
    competitors: Optional[ExtractedField] = None
    budget_range: Optional[ExtractedField] = None
    growth_stage: Optional[ExtractedField] = None

class ExtractedDeal(BaseModel):
    deal_name: Optional[ExtractedField] = None
    value: Optional[ExtractedField] = None
    currency: Optional[ExtractedField] = None
    timeline: Optional[ExtractedField] = None
    sales_stage: Optional[ExtractedField] = None
    decision_criteria: Optional[ExtractedField] = None
    next_steps: Optional[ExtractedField] = None
    proposal_requirements: Optional[ExtractedField] = None
    competitors: Optional[ExtractedField] = None
    competitive_differentiators: Optional[ExtractedField] = None

class Relationship(BaseModel):
    source_type: Literal["Contact", "Company", "Deal"]
    source_name: str
    target_type: Literal["Contact", "Company", "Deal"]
    target_name: str
    relationship_type: Literal["WORKS_AT", "STAKEHOLDER_FOR", "HAS_OPPORTUNITY"]
    confidence: float
    evidence: List[str]

class ExtractionResult(BaseModel):
    contacts: List[ExtractedContact] = []
    companies: List[ExtractedCompany] = []
    deals: List[ExtractedDeal] = []
    relationships: List[Relationship] = []

class ValidationError(BaseModel):
    entity_type: str
    entity_name: str
    field: str
    message: str

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[ValidationError] = []
    normalized_data: ExtractionResult

class DuplicateMatch(BaseModel):
    entity_type: str
    extracted_name: str
    matched_id: str
    matched_name: str
    match_score: float
    match_method: str

class DuplicateResult(BaseModel):
    matches: List[DuplicateMatch] = []

class CRMOperation(BaseModel):
    operation_type: Literal["CREATE", "UPDATE", "NO_OP", "ASK_FOR_REVIEW"]
    entity_type: str
    entity_name: str
    entity_id: Optional[str] = None
    data: Dict[str, Any]
    reason: str

class AgentResult(BaseModel):
    extraction: Optional[ExtractionResult] = None
    validation: Optional[ValidationResult] = None
    duplicates: Optional[DuplicateResult] = None
    operations: List[CRMOperation] = []
    status: str
    message: str
    # Results from syncing operations to the CRM (populated by execute_operations)
    sync_results: Optional[List[Dict[str, Any]]] = None
