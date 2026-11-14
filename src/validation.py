import re
from typing import List, Tuple
from src.schemas import ExtractionResult, ValidationResult, ValidationError
from src.config import VALID_DEAL_STAGES, VALID_CURRENCIES, REQUIRED_CONTACT_FIELDS, REQUIRED_COMPANY_FIELDS, REQUIRED_DEAL_FIELDS

def validate_email(email: str) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", str(email)))

def validate_phone(phone: str) -> bool:
    return len(re.sub(r'\D', '', str(phone))) >= 7

def validate_deal_stage(stage: str) -> str:
    stage_lower = stage.lower().replace(" ", "").replace("_", "")
    for valid_stage, stage_id in VALID_DEAL_STAGES.items():
        if valid_stage.lower() == stage_lower:
            return stage_id
    return None

def validate_contact(contact: dict, index: int) -> List[ValidationError]:
    errors = []
    name = contact.get("name", {}).get("value") if contact.get("name") else f"Contact_{index}"
    
    for field in REQUIRED_CONTACT_FIELDS:
        if not contact.get(field) or not contact.get(field).get("value"):
            errors.append(ValidationError(entity_type="Contact", entity_name=name, field=field, message="Missing required field"))
            
    email_obj = contact.get("email")
    if email_obj and email_obj.get("value") and not validate_email(email_obj.get("value")):
        errors.append(ValidationError(entity_type="Contact", entity_name=name, field="email", message="Invalid email format"))
        
    phone_obj = contact.get("phone")
    if phone_obj and phone_obj.get("value") and not validate_phone(phone_obj.get("value")):
        errors.append(ValidationError(entity_type="Contact", entity_name=name, field="phone", message="Invalid phone format"))
        
    return errors

def validate_company(company: dict, index: int) -> List[ValidationError]:
    errors = []
    name = company.get("name", {}).get("value") if company.get("name") else f"Company_{index}"
    
    for field in REQUIRED_COMPANY_FIELDS:
        if not company.get(field) or not company.get(field).get("value"):
            errors.append(ValidationError(entity_type="Company", entity_name=name, field=field, message="Missing required field"))
            
    return errors

def validate_deal(deal: dict, index: int) -> Tuple[List[ValidationError], dict]:
    errors = []
    name = deal.get("deal_name", {}).get("value") if deal.get("deal_name") else f"Deal_{index}"
    
    for field in REQUIRED_DEAL_FIELDS:
        if not deal.get(field) or not deal.get(field).get("value"):
            errors.append(ValidationError(entity_type="Deal", entity_name=name, field=field, message="Missing required field"))
            
    val_obj = deal.get("value")
    if val_obj and val_obj.get("value"):
        try:
            val = float(val_obj.get("value"))
            if val < 0:
                errors.append(ValidationError(entity_type="Deal", entity_name=name, field="value", message="Value cannot be negative"))
        except:
             errors.append(ValidationError(entity_type="Deal", entity_name=name, field="value", message="Value must be a number"))
             
    stage_obj = deal.get("sales_stage")
    if stage_obj and stage_obj.get("value"):
        normalized = validate_deal_stage(stage_obj.get("value"))
        if not normalized:
            errors.append(ValidationError(entity_type="Deal", entity_name=name, field="sales_stage", message=f"Invalid stage. Must be one of {list(VALID_DEAL_STAGES.keys())}"))
        else:
            deal["sales_stage"]["value"] = normalized
            
    curr_obj = deal.get("currency")
    if curr_obj and curr_obj.get("value"):
        curr = str(curr_obj.get("value")).upper()
        if curr not in VALID_CURRENCIES:
             errors.append(ValidationError(entity_type="Deal", entity_name=name, field="currency", message=f"Invalid currency. Must be one of {VALID_CURRENCIES}"))
        else:
            deal["currency"]["value"] = curr

    return errors, deal

def validate_and_normalize(extraction: ExtractionResult) -> ValidationResult:
    all_errors = []
    extraction_dict = extraction.model_dump()
    
    for i, contact in enumerate(extraction_dict.get("contacts", [])):
        all_errors.extend(validate_contact(contact, i))
        
    for i, company in enumerate(extraction_dict.get("companies", [])):
        all_errors.extend(validate_company(company, i))
        
    for i, deal in enumerate(extraction_dict.get("deals", [])):
        errors, norm_deal = validate_deal(deal, i)
        all_errors.extend(errors)
        extraction_dict["deals"][i] = norm_deal
        
    is_valid = len(all_errors) == 0
    return ValidationResult(
        is_valid=is_valid,
        errors=all_errors,
        normalized_data=ExtractionResult(**extraction_dict)
    )

def validate_extraction(extraction: ExtractionResult) -> ValidationResult:
    return validate_and_normalize(extraction)
