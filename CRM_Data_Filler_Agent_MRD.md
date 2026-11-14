# Master Requirements Document (MRD)
## Automated Data Filler Agent — B2B Sales Meeting → CRM

**Version:** 1.0  
**Date:** 14 August 2026  
**Status:** Project baseline / implementation specification

## 1. Executive Summary

- The Automated Data Filler Agent converts unstructured B2B sales meeting summaries into validated, relationship-aware CRM actions. It is not merely an LLM-to-JSON extractor: it combines CRM lookup, local context retrieval/RAG, Gemini semantic extraction, deterministic validation, entity resolution, duplicate/change detection, action planning, human review, and HubSpot writes.
- Baseline flow: Meeting Summary → preprocessing → HubSpot lookup → local context/RAG → Gemini structured extraction → relationship mapping → validation → entity resolution → CREATE/UPDATE/NO-OP/ASK_FOR_REVIEW → human review → HubSpot.
- Primary implementation CRM: HubSpot. Primary CRM-agent dataset/reference: Salesforce CRMArena-Pro B2B. Optional robustness data: SalesAgent-Consultant. Optional factuality stress test: SummEdits.

## 2. Problem Statement

- B2B sales representatives spend substantial time manually converting meeting notes into CRM records. Unstructured notes can contain contacts, companies, opportunities, budgets, timelines, decision makers, competitors, pain points, next actions, and incomplete or conflicting information.
- The system must understand unstructured sales summaries, extract business entities and deal information, map relationships, validate fields, detect existing CRM records and duplicates, and create accurate CRM entries.
- Target CRMs in the original problem statement are HubSpot, Salesforce, and Zoho. HubSpot is the first implementation target because a HubSpot credential is available.

## 3. Goals

- Extract Contact, Company, and Deal information from unstructured B2B sales summaries.
- Map Contact–Company, Contact–Deal, and Company–Deal relationships.
- Use CRM schema, business rules, stage definitions, and existing CRM records as context.
- Search before creating records; resolve entities and detect duplicates.
- Differentiate CREATE, UPDATE, NO-OP, and ASK_FOR_REVIEW.
- Validate all proposed values before any CRM write.
- Provide evidence and confidence for important extracted fields.
- Evaluate the system quantitatively on held-out data.
- Provide a Streamlit interface for the complete workflow.

## 4. Non-Goals

- Replacing a CRM.
- Building a general autonomous sales representative.
- Training a foundation model.
- Supporting all CRMs in the first version.
- Using paid infrastructure such as a managed vector database.
- Sending real confidential customer meetings through the unpaid Gemini tier.

## 5. Users and User Stories

- Sales representative: paste a meeting summary and receive a structured CRM update proposal.
- Sales representative: see matched CRM records, extracted values, evidence, warnings, and proposed changes.
- Sales manager: review ambiguous or consequential changes before they are written.
- Developer/researcher: evaluate extraction, relationships, entity resolution, action planning, and end-to-end CRM accuracy.

## 6. End-to-End Functional Flow

- 1. User enters a meeting summary.
- 2. Preprocessor normalizes text and identifies candidate lookup signals.
- 3. HubSpot search retrieves candidate contacts, companies, and deals.
- 4. Local retrieval selects relevant CRM schema, field definitions, stage definitions, business rules, validation rules, and few-shot examples.
- 5. Gemini receives the bounded context and returns structured extraction with evidence, confidence, missing information, and conflicts.
- 6. Python constructs the relationship graph.
- 7. Pydantic and deterministic business rules validate the output.
- 8. Entity resolution compares extracted entities with HubSpot candidates.
- 9. Duplicate detection and change detection determine whether records are new, duplicated, or changed.
- 10. Action planner selects CREATE, UPDATE, NO-OP, or ASK_FOR_REVIEW.
- 11. Streamlit displays the proposed CRM diff.
- 12. After approval, HubSpot objects and associations are created/updated.
- 13. The system returns confirmation and an audit result.

## 7. Canonical CRM Schema

- Contact: name, designation/title, email, phone, department, seniority, decision-making authority, decision-maker flag, preferred contact method, availability, timezone.
- Company: name, industry, employee count/team size, website, business challenges, pain points, technology stack, competitors, budget range, growth stage.
- Deal: deal/opportunity name, value, currency, timeline, sales stage, decision criteria, next steps, proposal requirements, alternatives/competitors, competitive differentiators.
- Relationships: Contact WORKS_AT Company; Contact STAKEHOLDER_FOR Deal; Company HAS_OPPORTUNITY Deal.
- Canonical fields must be CRM-neutral. A separate HubSpot mapping configuration translates them into HubSpot property names.

## 8. Gemini Extraction Contract

- Gemini handles semantic interpretation: entity extraction, sales-context understanding, decision-maker interpretation, stage interpretation, evidence extraction, and relationship interpretation.
- Gemini must return structured output conforming to Pydantic models.
- Important fields should contain evidence references and confidence.
- Unknown information must be null/unknown and listed in missing_information; the model must not invent values.
- Gemini proposes actions but does not directly control CRM writes.

## 9. RAG / Context Engineering

- RAG is used to provide CRM/business knowledge, not as a privacy mechanism.
- Local knowledge base: CRM schema, HubSpot field mapping, stage definitions, business rules, validation rules, relationship definitions, and selected few-shot examples.
- Use local sentence-transformers + FAISS, or a simple local retriever if the corpus remains small. No paid vector database is required.
- Retrieval should be selective: retrieve only rules/examples relevant to the entities and fields involved in the current meeting.
- Existing HubSpot records are separate dynamic context and should be retrieved through the HubSpot API rather than embedded permanently.

## 10. Entity Resolution, Duplicate Detection, and Change Detection

- Entity resolution asks whether an extracted entity corresponds to an existing CRM entity.
- Duplicate detection asks whether two records likely represent the same real-world entity.
- Change detection asks whether the meeting contains new information that should modify an existing record.
- Contact matching priority: exact email → exact phone → strong name + company → fuzzy candidate review.
- Company matching priority: exact domain → normalized company name → strong contextual match.
- Deal matching: existing deal ID when available, then company + deal/opportunity name + contextual signals.
- Ambiguous matches must be routed to ASK_FOR_REVIEW rather than silently merging or creating records.

## 11. Action Planner

- CREATE: no sufficiently reliable existing record and creation requirements are satisfied.
- UPDATE: an existing record is confidently matched and the meeting provides supported new/changed information.
- NO-OP: the existing record already contains the supported information and no meaningful change is required.
- ASK_FOR_REVIEW: ambiguous match, conflicting evidence, low confidence, unsupported destructive update, or other safety concern.
- Every update should expose current value → proposed value → evidence → reason.

## 12. HubSpot Integration

- Implement an isolated HubSpot client module.
- Required operations: search/get contacts, companies, and deals; create/update contacts, companies, and deals; create/read notes or meeting records where appropriate; create associations.
- Use official HubSpot API documentation for current endpoint/property details.
- Keep HubSpot credentials in environment variables or Streamlit secrets and never commit them.

## 13. Dataset Decision

- PRIMARY: Salesforce CRMArena-Pro B2B. It is explicitly designed for professional CRM-agent evaluation and provides a B2B CRM environment, schema, CRM objects, and VoiceCallTranscript data. It is much closer to the actual CRM-agent problem than a generic sales-conversation dataset.
- SECONDARY OPTIONAL: SalesAgent-Consultant. Use a small subset for sales-language and industry robustness. Do not make the project dependent on the full dataset.
- FACTUALITY OPTIONAL: SummEdits. The uploaded sales_call records are useful for testing factual consistency/hallucination, but they are not a complete B2B CRM dataset and should not be the primary source.
- Because no public dataset exactly provides Meeting Summary → Contact/Company/Deal ground truth, create a small manually verified gold annotation layer for the selected evaluation examples. Never use the agent itself to generate its own ground truth.
- CRMArena-Pro is research-oriented; its official repository states that the repository is not for commercial use. Preserve attribution/license information and do not assume commercial rights.

## 14. Dataset and Evaluation Design

- Use a focused subset of CRMArena-Pro B2B relevant to sales/voice-call/CRM-update tasks rather than processing the entire benchmark.
- Recommended split: 70% development, 15% validation, 15% final held-out evaluation.
- Keep final evaluation examples out of prompt examples.
- Include stress cases: missing budget, missing contact details, multiple stakeholders, multiple companies, competitors, ambiguous authority, approximate amounts, conflicting information, follow-up meetings, existing CRM records, changed titles/company size, duplicate candidates, and no-deal meetings.

## 15. Evaluation Metrics

- Field-level exact accuracy for normalized fields.
- Entity precision/recall/F1 where gold labels exist.
- Numeric and date normalization accuracy.
- Relationship precision/recall/F1.
- Entity-resolution accuracy.
- CREATE/UPDATE/NO-OP/ASK_FOR_REVIEW action accuracy.
- Change-detection precision.
- Unsupported-field hallucination rate.
- Validation failure and recovery rate.
- HubSpot write success rate.
- End-to-end success rate.
- Latency and approximate token/API usage.

## 16. Evaluation Methodology

- Run ablations: A) Gemini only; B) Gemini + CRM schema context; C) Gemini + local RAG + CRM context; D) full pipeline with deterministic validation and entity resolution.
- Use selected SummEdits cases as a secondary factuality stress test.
- Evaluate each pipeline layer separately so failures can be attributed to extraction, retrieval, resolution, validation, action planning, or API execution.
- Do not report only a single overall accuracy number.

## 17. Privacy and Security

- Use public/synthetic project data with the unpaid Gemini tier.
- Google's current Gemini terms state that unpaid-service content may be used to improve products and may be reviewed by humans; they explicitly advise not submitting sensitive, confidential, or personal information to unpaid services.
- RAG does not solve privacy: meeting content is still sent to the LLM if Gemini performs extraction.
- For confidential production data, use an appropriately governed paid/enterprise Gemini setup or local inference.
- Never hard-code API keys. Use .env locally and deployment secrets.
- Do not log raw meeting text or CRM dumps by default.
- Never store HubSpot credentials in SQLite or source control.

## 18. Error Handling

- Malformed Gemini output → bounded repair/retry; otherwise ASK_FOR_REVIEW.
- Missing information → null + missing_information; never fabricate.
- Low confidence → review.
- Conflicting statements → preserve conflict/evidence; avoid destructive automatic update.
- Multiple CRM matches → review.
- HubSpot 4xx → classify and surface; do not blindly retry.
- HubSpot 5xx/network failure → bounded retry with backoff.
- Invalid CRM property/stage → reject before API call.
- Before create, re-check for duplicates to reduce race-condition duplicates.

## 19. Human Review

- The first implementation should require approval before HubSpot writes.
- Review screen: matched records, extracted fields, current values, proposed values, evidence, confidence, warnings, and action.
- Automatic updates can be considered later with configurable thresholds; they are not required for v1.

## 20. 18-Step Notebook Plan

- Step 1 Import Required Libraries.
- Step 2 Define Project Configuration.
- Step 3 Load / Create Meeting Summary Dataset.
- Step 4 Explore the Meeting Data.
- Step 5 Define CRM Schema.
- Step 6 Build Context.
- Step 7 LLM Extraction.
- Step 8 Relationship Mapping.
- Step 9 Data Validation.
- Step 10 Duplicate Detection.
- Step 11 CRM Field Mapping.
- Step 12 End-to-End Agent.
- Step 13 Evaluate the Agent.
- Step 14 Test on New Meeting.
- Step 15 Save Configuration.
- Step 16 Build Streamlit App.
- Step 17 Create requirements.txt.
- Step 18 Deployment.

## 21. Recommended Code Structure

- CRM_Data_Filler_Agent/
- ├── notebook/CRM_Data_Filler_Agent.ipynb
- ├── app/streamlit_app.py
- ├── src/config.py
- ├── src/schemas.py
- ├── src/preprocessing.py
- ├── src/retrieval.py
- ├── src/gemini_extractor.py
- ├── src/relationships.py
- ├── src/validation.py
- ├── src/entity_resolution.py
- ├── src/action_planner.py
- ├── src/hubspot_client.py
- ├── src/pipeline.py
- ├── knowledge/
- ├── data/development/
- ├── data/validation/
- ├── data/evaluation/
- ├── tests/
- ├── .env.example
- ├── .gitignore
- ├── requirements.txt
- └── README.md

## 22. Free/Open-Source Technology Stack

- Python — application/orchestration.
- Gemini API via available AI Studio key — semantic extraction/reasoning.
- Pydantic — deterministic schema validation.
- sentence-transformers + FAISS — local retrieval, if needed.
- HubSpot REST API — CRM system of record.
- SQLite — local audit/configuration persistence.
- Streamlit — UI/demo.
- No paid vector database is required. LangGraph/Airbyte are optional reference technologies, not required dependencies.

## 23. Cost and Data-Use Strategy

- The project is designed around free/open-source components and the credentials already available.
- Gemini currently provides a free tier with selected models and free input/output subject to rate limits. The free tier is appropriate for public/synthetic project data.
- HubSpot provides developer/test account paths and CRM APIs; exact account limits should be checked at implementation time.
- Free does not mean confidential: unpaid Gemini data-use terms are the reason real confidential meetings should not be used in the free-tier demo.

## 24. Performance Targets

- Schema-valid extraction ≥ 98% target.
- Critical-field factual precision ≥ 90% target.
- Relationship F1 ≥ 90% target where sufficient gold labels exist.
- CREATE/UPDATE/NO-OP/ASK action accuracy ≥ 90% target on the curated evaluation set.
- Unsupported-field hallucination rate < 5% target.
- 100% of CRM writes pass deterministic validation.
- 100% of ambiguous matches are routed to review.
- Typical demo latency target: <15 seconds per meeting, excluding transient API/network delays.

## 25. Acceptance Criteria

- Clean B2B meeting → valid Contact/Company/Deal extraction.
- Existing CRM record → correct resolution without unnecessary duplicate creation.
- Changed title/company/deal field → explicit UPDATE diff.
- New record → CREATE proposal when requirements are satisfied.
- Ambiguous match → no automatic write.
- Missing information → null/missing_information rather than invented value.
- Critical extracted fields → supporting evidence.
- Invalid stage/property/value → rejected before HubSpot write.
- Correct Contact–Company–Deal associations.
- Evaluation notebook reports field, relationship, action, hallucination, and end-to-end metrics.
- Streamlit demonstrates the same pipeline.
- Credentials are absent from source-controlled code.

## 26. Risks and Mitigations

- LLM hallucination → evidence, null-on-unknown, validation, factuality tests.
- Dataset mismatch → CRMArena-Pro B2B primary + manually verified evaluation layer.
- Synthetic-data bias → optional SalesAgent-Consultant robustness set + custom unseen meetings.
- Duplicate creation → search-before-create + entity resolution + re-check before write.
- Incorrect updates → explicit diff + review gate.
- API instability → retries and error classification.
- Privacy → public/synthetic data with unpaid Gemini; governed paid/local inference for confidential data.
- Overengineering → ordinary Python modules first; add orchestration frameworks only if complexity requires them.
- License mismatch → keep CRMArena-Pro research/non-commercial; use permissive data for future commercial work.

## 27. Development Phases

- Phase 1 — Dataset, schema, annotation, evaluation protocol.
- Phase 2 — Gemini extraction and structured output.
- Phase 3 — Local retrieval/context engineering.
- Phase 4 — HubSpot lookup, entity resolution, duplicate/change detection.
- Phase 5 — Action planner, human review, CRM writes.
- Phase 6 — Evaluation and ablations.
- Phase 7 — Streamlit, documentation, deployment.

## 28. Reference Architecture Sources

- Oliv AI: reference for meeting intelligence, CRM object resolution, associations, and change synchronization.
- Granola-style meeting-summary-to-CRM workflow: reference for extraction followed by CRM search and create/update decisions.
- Airbyte HubSpot agent connector: reference for typed CRM operations; not a required dependency.
- Gemini + HubSpot open-source sales workflow: reference for combining Gemini with HubSpot and retrieval/agent patterns.
- Playcall-style sales intelligence: reference for sales context/playbooks.

## 29. Final Architecture Decision

- Meeting Summary → Preprocess → HubSpot candidate lookup → Local RAG/Context Builder → Gemini structured extraction → Evidence/Confidence → Relationship Mapping → Pydantic/Business Validation → Entity Resolution → Duplicate Detection → Change Detection → CREATE/UPDATE/NO-OP/ASK_FOR_REVIEW → Human Review → HubSpot.
- The central separation of responsibilities is: Gemini understands; retrieval supplies CRM knowledge; Python validates/resolves/plans; HubSpot is the system of record; the user approves ambiguous or consequential changes.

## 30. Deliverables

- MRD.
- CRM_Data_Filler_Agent.ipynb with the 18-step implementation.
- Selected CRMArena-Pro B2B data and project annotation schema.
- Local CRM knowledge base/retrieval index.
- Gemini extraction module and Pydantic schemas.
- HubSpot client and association logic.
- Entity-resolution and action-planning modules.
- Evaluation report with ablations.
- Streamlit application.
- requirements.txt, .env.example, .gitignore, README.

## 31. References

- CRMArena official repository: https://github.com/SalesforceAIResearch/CRMArena
- CRMArena-Pro dataset: https://huggingface.co/datasets/Salesforce/CRMArenaPro
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini API terms: https://ai.google.dev/gemini-api/terms
- HubSpot developer documentation: https://developers.hubspot.com/
- SummEdits dataset: https://huggingface.co/datasets/Salesforce/summedits

> Licensing, API limits, and data-use terms should be rechecked at implementation/deployment time.
