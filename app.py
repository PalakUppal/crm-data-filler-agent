import streamlit as st
import pandas as pd
from src.pipeline import process_meeting_summary, execute_operations
from src.crm_client import MockCRMClient, HubSpotCRMClient
from src.transcription import transcribe_audio
from src.config import CRM_MODE

st.set_page_config(page_title="Automated CRM Data Filler Agent", layout="wide")

# Custom CSS for premium UI
st.markdown("""
<style>
    /* Global styles */
    .stApp {
        background: #0f172a;
        color: #f8fafc;
    }
    
    /* Headers with Gradients */
    h1, h2, h3 {
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-family: 'Inter', sans-serif;
    }
    
    /* Glassmorphism Cards */
    .css-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .css-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }
    
    /* CRM Mode Badge */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        background-color: #312e81;
        color: #c7d2fe;
        border: 1px solid #4f46e5;
    }
    
    /* Operation Colors */
    .op-CREATE { color: #34d399; font-weight: bold; }
    .op-UPDATE { color: #60a5fa; font-weight: bold; }
    .op-NO_OP { color: #94a3b8; font-weight: bold; }
    .op-ASK_FOR_REVIEW { color: #fb923c; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🤖 Automated CRM Data Filler Agent")
st.markdown(f"<div><span class='badge'>🔧 CRM MODE: {CRM_MODE.upper()}</span></div><br/>", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    confidence_threshold = st.slider("Confidence Threshold", 0.0, 1.0, 0.7, 0.05)
    st.markdown("---")
    st.markdown("Made by:")
    st.code(
    "Palak"
    "\nMoksh"
    "\nRishu"
    "\nHarshita"
    )

# Initialize session state
if 'result' not in st.session_state:
    st.session_state.result = None
if 'client' not in st.session_state:
    if CRM_MODE.lower() == 'hubspot':
        st.session_state.client = HubSpotCRMClient()
    else:
        st.session_state.client = MockCRMClient()

st.markdown("### 🎙️ Voice-to-CRM")
col_mic, col_upload = st.columns([1, 1])

with col_mic:
    audio_value = st.audio_input("Record a meeting summary directly")

with col_upload:
    uploaded_file = st.file_uploader("Or upload an audio recording", type=["mp3", "wav", "m4a"])

audio_to_process = audio_value or uploaded_file

if audio_to_process is not None:
    if st.button("Transcribe Audio to Text", type="secondary"):
        with st.spinner("Transcribing with Gemini..."):
            mime_type = audio_to_process.type
            transcript = transcribe_audio(audio_to_process.getvalue(), mime_type=mime_type)
            if transcript:
                st.session_state.transcribed_text = transcript
                st.success("Transcription complete! Review the text below.")
            else:
                st.error("Failed to transcribe audio.")

# Initialize session state for transcribed text if not exists
if 'transcribed_text' not in st.session_state:
    st.session_state.transcribed_text = ""

st.markdown("### Meeting Summary")
summary = st.text_area("Input meeting transcript, notes, or email thread...", value=st.session_state.transcribed_text, height=200, placeholder="E.g., Just got off a great call with Sarah Chen, VP of Engineering at NexaFlow Technologies. They are looking to upgrade their Q3 Enterprise systems with a $150k budget...")

if st.button("🚀 Extract CRM Data", type="primary", use_container_width=True):
    if not summary.strip():
        st.error("Please enter a meeting summary.")
    else:
        with st.spinner("Analyzing text and extracting CRM entities..."):
            result = process_meeting_summary(summary, crm_client=st.session_state.client)
            st.session_state.result = result
            if result.status == "ERROR":
                st.error(f"Error processing: {result.message}")

if st.session_state.result and st.session_state.result.status == "SUCCESS":
    result = st.session_state.result
    
    st.success("Extraction Complete!")
    
    tabs = st.tabs(["Operations Preview", "Contacts", "Companies", "Deals", "Relationships", "Validation"])
    
    # Tab: Operations
    with tabs[0]:
        st.markdown("### CRM Action Plan")
        if not result.operations:
            st.info("No operations to perform.")
        for op in result.operations:
            st.markdown(f"""
            <div class="css-card">
                <div><span class="op-{op.operation_type}">{op.operation_type}</span> <b>{op.entity_type}</b>: {op.entity_name}</div>
                <div style="font-size: 0.9em; color: #cbd5e1; margin-top: 8px;">Reason: {op.reason}</div>
            </div>
            """, unsafe_allow_html=True)
            
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Approve & Sync", use_container_width=True, type="primary"):
                with st.spinner("Syncing to CRM..."):
                    # Build edits mapping keyed by "<EntityType>|<EntityName>" so pipeline can merge them
                    edits_map = {}
                    edits_raw = st.session_state.get('edits', {}) if isinstance(st.session_state.get('edits', {}), dict) else {}

                    # Map contact/company/deal edits to entity name keys
                    for k, v in edits_raw.items():
                        # keys were created like "contact-0", "company-1", etc.
                        try:
                            parts = k.split('-', 1)
                            typ = parts[0]
                            idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                        except Exception:
                            typ = None
                            idx = None

                        if typ and idx is not None:
                            if typ == 'contact' and idx < len(result.extraction.contacts):
                                name = result.extraction.contacts[idx].model_dump().get('name', {}).get('value')
                                if name:
                                    edits_map[f"Contact|{name}"] = v
                            elif typ == 'company' and idx < len(result.extraction.companies):
                                name = result.extraction.companies[idx].model_dump().get('name', {}).get('value')
                                if name:
                                    edits_map[f"Company|{name}"] = v
                            elif typ == 'deal' and idx < len(result.extraction.deals):
                                name = result.extraction.deals[idx].model_dump().get('deal_name', {}).get('value')
                                if name:
                                    edits_map[f"Deal|{name}"] = v

                    # Call pipeline with edits; it will merge and return sync_results
                    result = execute_operations(result, st.session_state.client, edits=edits_map)
                    st.session_state.result = result

                    # Show per-entity confirmations
                    if result.sync_results:
                        for r in result.sync_results:
                            status = r.get('status', 'UNKNOWN')
                            ent = f"{r.get('entity_type')} - {r.get('entity_name')}"
                            if status in ("CREATED", "UPDATED"):
                                st.success(f"{ent}: {status}")
                            elif status == "SKIPPED":
                                st.info(f"{ent}: SKIPPED ({r.get('detail', '')})")
                            else:
                                st.error(f"{ent}: {status} ({r.get('detail','')})")

        with col2:
            # Toggle showing all entity editors at once
            if st.button("Edit", use_container_width=True):
                st.session_state['show_all_editors'] = not st.session_state.get('show_all_editors', False)
        with col3:
            if st.button("Cancel", use_container_width=True):
                 st.session_state.result = None
                 st.rerun()

    # Generic extraction rendering
    def render_entity(entity, title_field="name", edit_key=None):
        data = entity.model_dump()
        # Apply any local edits saved in session_state
        edits = st.session_state.get('edits', {}) if isinstance(st.session_state.get('edits', {}), dict) else {}
        if edit_key and edit_key in edits:
            # merge edited fields into data for display
            # edits[edit_key] is expected to be a dict of field -> { 'value': ..., 'confidence': ... }
            merged = dict(data)
            for k, v in edits[edit_key].items():
                merged[k] = v
            data = merged

        # Collect fields that have values
        fields = []
        for k, v in data.items():
            if isinstance(v, dict) and 'value' in v and v.get('value') not in (None, ""):
                fields.append((k, v.get('value'), v.get('confidence', 0)))

        name = data.get(title_field, {}).get("value") if data.get(title_field) else "Unknown"
        st.markdown(f"#### {name}")

        if fields:
            for k, val, conf in fields:
                color = "green" if conf >= confidence_threshold else "orange"
                st.markdown(f"- **{k.replace('_', ' ').title()}**: {val} _(Conf: <span style='color:{color}'>{conf:.2f}</span>)_", unsafe_allow_html=True)
        else:
            st.info("No extracted fields found for this entity. Use Edit to add data or correct values.")

        # Edit expander with a small form to update values locally
        expanded_flag = st.session_state.get('show_all_editors', False)
        with st.expander("Edit", expanded=expanded_flag):
            form = st.form(key=f"form-{edit_key or id(entity)}")
            new_fields = {}
            # Pre-populate editable fields using current data
            for k, v in data.items():
                if isinstance(v, dict) and 'value' in v:
                    val = v.get('value') or ""
                    # Use a unique key per input to avoid collisions
                    # Use shorter, stable keys for better UI rendering
                    input_key = f"{edit_key}-{k}"
                    new_val = form.text_input(f"{k.replace('_', ' ').title()}", value=str(val), key=input_key)
                    new_fields[k] = {'value': new_val, 'confidence': v.get('confidence', 1.0)}
            # Allow adding one extra field
            add_name = form.text_input("Add field name (optional)", key=f"{edit_key}-new-name")
            add_val = form.text_input("Add field value (optional)", key=f"{edit_key}-new-val")
            submit = form.form_submit_button("Save")
            if submit:
                if add_name and add_val:
                    new_fields[add_name] = {'value': add_val, 'confidence': 1.0}
                if 'edits' not in st.session_state or not isinstance(st.session_state.get('edits'), dict):
                    st.session_state['edits'] = {}
                st.session_state['edits'][edit_key] = new_fields
                st.success("Saved edits locally. Click 'Approve & Sync' to push changes to CRM.")

    # Tab: Contacts
    with tabs[1]:
        for i, c in enumerate(result.extraction.contacts):
            with st.container():
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                render_entity(c, "name", edit_key=f"contact-{i}")
                st.markdown('</div>', unsafe_allow_html=True)

    # Tab: Companies
    with tabs[2]:
         for i, c in enumerate(result.extraction.companies):
            with st.container():
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                render_entity(c, "name", edit_key=f"company-{i}")
                st.markdown('</div>', unsafe_allow_html=True)

    # Tab: Deals
    with tabs[3]:
        for i, d in enumerate(result.extraction.deals):
            with st.container():
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                render_entity(d, "deal_name", edit_key=f"deal-{i}")
                st.markdown('</div>', unsafe_allow_html=True)

    # Tab: Relationships
    with tabs[4]:
         for r in result.extraction.relationships:
             st.markdown(f"""
             <div class="css-card">
                <b>{r.source_name}</b> ({r.source_type}) 
                <span style="color:#818cf8; font-weight:bold;">→ {r.relationship_type} →</span> 
                <b>{r.target_name}</b> ({r.target_type})
             </div>
             """, unsafe_allow_html=True)

    # Tab: Validation
    with tabs[5]:
         if result.validation.is_valid:
             st.success("All extracted entities passed validation.")
         else:
             st.warning("Validation warnings detected:")
             for err in result.validation.errors:
                 st.markdown(f"- **{err.entity_type}** ({err.entity_name}): {err.field} - {err.message}")
