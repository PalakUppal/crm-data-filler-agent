from typing import List
from src.schemas import ExtractionResult, Relationship

def map_relationships(extraction: ExtractionResult) -> List[Relationship]:
    """Map relationships between extracted entities based on logic and deduplicate."""
    relationships = []
    
    for contact in extraction.contacts:
        for company in extraction.companies:
            if contact.name and contact.name.value and company.name and company.name.value:
                relationships.append(
                    Relationship(
                        source_type="Contact",
                        source_name=contact.name.value,
                        target_type="Company",
                        target_name=company.name.value,
                        relationship_type="WORKS_AT",
                        confidence=0.8,
                        evidence=["Inferred from co-occurrence in meeting summary"]
                    )
                )
                
    for deal in extraction.deals:
        for contact in extraction.contacts:
            if deal.deal_name and deal.deal_name.value and contact.name and contact.name.value:
                 relationships.append(
                    Relationship(
                        source_type="Contact",
                        source_name=contact.name.value,
                        target_type="Deal",
                        target_name=deal.deal_name.value,
                        relationship_type="STAKEHOLDER_FOR",
                        confidence=0.7,
                        evidence=["Inferred from co-occurrence in meeting summary"]
                    )
                )
                 
    for deal in extraction.deals:
        for company in extraction.companies:
            if deal.deal_name and deal.deal_name.value and company.name and company.name.value:
                 relationships.append(
                    Relationship(
                        source_type="Company",
                        source_name=company.name.value,
                        target_type="Deal",
                        target_name=deal.deal_name.value,
                        relationship_type="HAS_OPPORTUNITY",
                        confidence=0.9,
                        evidence=["Inferred from co-occurrence in meeting summary"]
                    )
                )
    
    unique_rels = []
    seen = set()
    for rel in relationships:
        key = f"{rel.source_type}:{rel.source_name}-{rel.relationship_type}-{rel.target_type}:{rel.target_name}"
        if key not in seen:
            seen.add(key)
            unique_rels.append(rel)
            
    return unique_rels
