from typing import List, Dict, Any
from src.schemas import ExtractionResult, DuplicateResult, ValidationResult, CRMOperation

def plan_operations(extraction: ExtractionResult, duplicates: DuplicateResult, validation: ValidationResult) -> List[CRMOperation]:
    """Plan operations based on extracted data, validation rules and duplicate detection."""
    operations = []
    
    dup_map = {m.extracted_name: m for m in duplicates.matches}
    
    def process_entities(entities, entity_type):
        for item in entities:
            name = item.name.value if hasattr(item, 'name') and item.name else getattr(item, 'deal_name').value if hasattr(item, 'deal_name') and item.deal_name else None
            if not name: continue
            
            data = {k: v.get("value") for k, v in item.model_dump().items() if isinstance(v, dict) and v.get("value") is not None}
            
            if name in dup_map:
                match = dup_map[name]
                if match.match_score == 100.0:
                     operations.append(CRMOperation(
                         operation_type="UPDATE", entity_type=entity_type, entity_name=name,
                         entity_id=match.matched_id, data=data, reason=f"Exact match found via {match.match_method}"
                     ))
                else:
                     operations.append(CRMOperation(
                         operation_type="ASK_FOR_REVIEW", entity_type=entity_type, entity_name=name,
                         entity_id=match.matched_id, data=data, reason=f"Fuzzy match found ({match.match_score}%) via {match.match_method}"
                     ))
            else:
                operations.append(CRMOperation(
                         operation_type="CREATE", entity_type=entity_type, entity_name=name,
                         data=data, reason="No duplicates found"
                ))
                
    process_entities(extraction.contacts, "Contact")
    process_entities(extraction.companies, "Company")
    process_entities(extraction.deals, "Deal")
    
    # Post-process: flag contacts missing email as ASK_FOR_REVIEW
    for op in operations:
        if op.entity_type == "Contact" and not op.data.get("email"):
            op.operation_type = "ASK_FOR_REVIEW"
            op.reason = f"⚠️ Missing email — contact will be saved without it. {op.reason}"

    # Post-process: flag entities with validation errors
    invalid_entities = {err.entity_name for err in validation.errors}
    for op in operations:
        if op.entity_name in invalid_entities and op.operation_type != "ASK_FOR_REVIEW":
            op.operation_type = "ASK_FOR_REVIEW"
            op.reason += " | Validation errors detected"
            
    return operations

def format_review(operations: List[CRMOperation], extraction: ExtractionResult) -> str:
    """Format operations into a readable string."""
    res = ""
    for op in operations:
        res += f"[{op.operation_type}] {op.entity_type}: {op.entity_name} - {op.reason}\n"
    return res
