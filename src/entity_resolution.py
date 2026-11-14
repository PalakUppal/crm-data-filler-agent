from fuzzywuzzy import fuzz
from src.schemas import ExtractionResult, DuplicateResult, DuplicateMatch

def detect_duplicates(extraction: ExtractionResult, crm_client) -> DuplicateResult:
    """Detect duplicates against existing CRM data using exact and fuzzy matching."""
    matches = []
    
    # 1. Contacts
    for contact in extraction.contacts:
        if not contact.name or not contact.name.value:
             continue
        name = contact.name.value
        email = contact.email.value if contact.email else ""
        phone = contact.phone.value if contact.phone else ""
        
        found = False
        if email:
            results = crm_client.search_contacts(email=email)
            if results:
                matches.append(DuplicateMatch(
                    entity_type="Contact", extracted_name=name, matched_id=results[0]['id'],
                    matched_name=results[0]['name'], match_score=100.0, match_method="Exact Email"
                ))
                found = True
        
        if not found and phone:
             results = crm_client.search_contacts(phone=phone)
             if results:
                 matches.append(DuplicateMatch(
                    entity_type="Contact", extracted_name=name, matched_id=results[0]['id'],
                    matched_name=results[0]['name'], match_score=100.0, match_method="Exact Phone"
                ))
                 found = True
                 
        if not found:
             results = crm_client.search_contacts(name=name)
             for res in results:
                 score = fuzz.ratio(name.lower(), res['name'].lower())
                 if score > 85:
                      matches.append(DuplicateMatch(
                        entity_type="Contact", extracted_name=name, matched_id=res['id'],
                        matched_name=res['name'], match_score=score, match_method="Fuzzy Name"
                    ))
                      break
                      
    # 2. Companies
    for company in extraction.companies:
        if not company.name or not company.name.value:
            continue
        name = company.name.value
        website = company.website.value if company.website else ""
        
        found = False
        if website:
             domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
             results = crm_client.search_companies(domain=domain)
             if results:
                 matches.append(DuplicateMatch(
                    entity_type="Company", extracted_name=name, matched_id=results[0]['id'],
                    matched_name=results[0]['name'], match_score=100.0, match_method="Domain"
                ))
                 found = True
                 
        if not found:
             results = crm_client.search_companies(name=name)
             for res in results:
                 score = fuzz.ratio(name.lower(), res['name'].lower())
                 if score > 85:
                      matches.append(DuplicateMatch(
                        entity_type="Company", extracted_name=name, matched_id=res['id'],
                        matched_name=res['name'], match_score=score, match_method="Fuzzy Name"
                    ))
                      break
                      
    # 3. Deals
    for deal in extraction.deals:
         if not deal.deal_name or not deal.deal_name.value:
             continue
         name = deal.deal_name.value
         results = crm_client.search_deals(name=name)
         for res in results:
             score = fuzz.ratio(name.lower(), res['name'].lower())
             if score > 90:
                  matches.append(DuplicateMatch(
                    entity_type="Deal", extracted_name=name, matched_id=res['id'],
                    matched_name=res['name'], match_score=score, match_method="Fuzzy Deal Name"
                ))
                  break

    return DuplicateResult(matches=matches)
