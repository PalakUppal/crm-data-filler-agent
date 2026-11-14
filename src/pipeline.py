from src.preprocessing import preprocess_summary, extract_candidate_signals
from src.extraction import extract_crm_data
from src.relationships import map_relationships
from src.validation import validate_extraction
from src.entity_resolution import detect_duplicates
from src.action_planner import plan_operations
from src.crm_client import MockCRMClient
from src.schemas import AgentResult
from src.config import CRM_MODE

def process_meeting_summary(summary: str, crm_client=None, auto_approve: bool = False) -> AgentResult:
    """End-to-end pipeline to process a meeting summary."""
    if crm_client is None:
        crm_client = MockCRMClient() if CRM_MODE == 'mock' else MockCRMClient()
        
    try:
        clean_summary = preprocess_summary(summary)
        signals = extract_candidate_signals(clean_summary)
        existing_records = {}
        for email in signals['emails']:
             res = crm_client.search_contacts(email=email)
             if res: existing_records[f"Contact_{email}"] = res[0]
        
        extraction = extract_crm_data(clean_summary, existing_records)
        if not extraction.contacts and not extraction.companies and not extraction.deals:
             return AgentResult(status="EMPTY", message="No CRM entities extracted.")
             
        extraction.relationships = map_relationships(extraction)
        
        validation = validate_extraction(extraction)
        
        duplicates = detect_duplicates(validation.normalized_data, crm_client)
        
        operations = plan_operations(validation.normalized_data, duplicates, validation)
        
        result = AgentResult(
            extraction=validation.normalized_data,
            validation=validation,
            duplicates=duplicates,
            operations=operations,
            status="SUCCESS",
            message="Successfully processed meeting summary"
        )
        
        if auto_approve:
            execute_operations(result, crm_client)
            
        return result

    except Exception as e:
        return AgentResult(status="ERROR", message=str(e))

def execute_operations(result: AgentResult, crm_client, edits: dict | None = None) -> AgentResult:
    """Execute planned CRM operations.

    edits: optional mapping of the form {"<EntityType>|<EntityName>": {field: {"value": ... , ...}, ...}}
    Any 'value' entries found in edits will overwrite the prepared op.data before sending to the CRM.
    """
    edits = edits or {}
    sync_results = []

    for op in result.operations:
        op_key = f"{op.entity_type}|{op.entity_name}"
        merged_data = dict(op.data) if op.data else {}

        # Merge edits (guarded)
        edit_for_op = edits.get(op_key)
        if edit_for_op is not None:
            if not isinstance(edit_for_op, dict):
                sync_results.append({
                    "entity_type": op.entity_type,
                    "entity_name": op.entity_name,
                    "operation": op.operation_type,
                    "status": "FAILED",
                    "detail": "Invalid edit format (expected dict)"
                })
                result.status = "PARTIAL_ERROR"
                result.message = (result.message or "") + f" | Invalid edits for {op_key}"
                continue

            # Each entry in edit_for_op is expected to be { field_name: { 'value': <val>, ... } }
            for fld, fld_val in edit_for_op.items():
                if isinstance(fld_val, dict) and 'value' in fld_val:
                    merged_data[fld] = fld_val['value']
                else:
                    # skip malformed field edits but record warning
                    result.status = "PARTIAL_ERROR"
                    result.message = (result.message or "") + f" | Skipped malformed edit field '{fld}' for {op_key}"

        # Execute the resulting operation with merged data
        try:
            if op.operation_type in ("CREATE", "ASK_FOR_REVIEW"):
                if op.entity_type == "Contact":
                    cid = crm_client.create_contact(merged_data)
                    sync_results.append({"entity_type": op.entity_type, "entity_name": op.entity_name, "operation": op.operation_type, "status": "CREATED", "id": cid})
                elif op.entity_type == "Company":
                    cid = crm_client.create_company(merged_data)
                    sync_results.append({"entity_type": op.entity_type, "entity_name": op.entity_name, "operation": op.operation_type, "status": "CREATED", "id": cid})
                elif op.entity_type == "Deal":
                    cid = crm_client.create_deal(merged_data)
                    sync_results.append({"entity_type": op.entity_type, "entity_name": op.entity_name, "operation": op.operation_type, "status": "CREATED", "id": cid})
            elif op.operation_type == "UPDATE" and op.entity_id:
                success = False
                if op.entity_type == "Contact": success = crm_client.update_contact(op.entity_id, merged_data)
                elif op.entity_type == "Company": success = crm_client.update_company(op.entity_id, merged_data)
                elif op.entity_type == "Deal": success = crm_client.update_deal(op.entity_id, merged_data)

                sync_results.append({"entity_type": op.entity_type, "entity_name": op.entity_name, "operation": op.operation_type, "status": "UPDATED" if success else "FAILED", "id": op.entity_id})
            else:
                sync_results.append({"entity_type": op.entity_type, "entity_name": op.entity_name, "operation": op.operation_type, "status": "SKIPPED", "detail": "No action taken"})
        except Exception as e:
            result.status = result.status if result.status != "PARTIAL_ERROR" else result.status
            sync_results.append({"entity_type": op.entity_type, "entity_name": op.entity_name, "operation": op.operation_type, "status": "FAILED", "detail": str(e)})
            result.status = "PARTIAL_ERROR"
            result.message = (result.message or "") + f" | Failed to {op.operation_type} {op.entity_type}: {e}"

    # Finalize
    if result.status != "PARTIAL_ERROR":
        result.status = "SUCCESS"
        result.message = "All operations executed successfully."

    result.sync_results = sync_results
    return result
