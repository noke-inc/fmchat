# dynamic_mutation_validator.py
import os
import re
import sys
import json
from langchain_core.messages import AIMessage, HumanMessage

def audit_mutation_form_progress(state: dict, schema_catalog_path: str = "api_mutation_schema.json") -> dict:
    """
    Generic Slot-Filling State Machine Engine.
    Audits conversational history against api_mutation_schema.json for ANY transactional intent.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"active_mutation_intent": None}
        
    last_message = messages[-1]
    
    # 1. Load the dynamic mutations catalog file configuration safely
    if not os.path.exists(schema_catalog_path):
        raise FileNotFoundError(f"Mutation schema rules missing from disk location: {schema_catalog_path}")
        
    with open(schema_catalog_path, "r") as f:
        mutation_catalog = json.load(f)
        
    intent = state.get("active_mutation_intent")
    
    # 🚀 FIXED PERMANENTLY: Force explicit dictionary duplication to prevent memory reference leaks! [🔒]
    raw_payload_buffer = state.get("gathered_form_payload", {}) or {}
    form_buffer = dict(raw_payload_buffer).copy()
    
    just_initialized_intent = False
    
    # ─── TRACK-ISOLATED INTENT DISCOVERY ───
    if not intent:
        flat_input = str(last_message.content).lower().strip()
        # If the last message is a bare site/company selection digit, the mutation
        # intent is in pending_user_query — fall back to it for intent detection.
        if re.match(r'^\d+$', flat_input):
            flat_input = str(state.get("pending_user_query") or "").lower().strip()

        for candidate_intent in mutation_catalog.keys():
            words_pool = [w.lower() for w in candidate_intent.split("_")]
            
            # Match keywords strictly on the fresh user message block
            if any(word in flat_input for word in words_pool if len(word) > 3):
                intent = candidate_intent
                form_buffer = {} 
                just_initialized_intent = True 
                print(f"\n📂 VALIDATOR: Successfully locked session intent context to '{intent}' natively.", file=sys.stderr)
                break
                
    if not intent or intent == "FORM_COMPLETE":
        return {"active_mutation_intent": intent if intent else None}

    schema_rules = mutation_catalog.get(intent, {})
    required_keys = schema_rules.get("required_fields", {})
    
    # =============================================================================
    # ─── 🚀 FIXED PERMANENTLY: ZERO-BLEED RECENT MESSAGE PARAMETER EXTRACTION ─── [🔒]
    # =============================================================================
    # We do NOT concatenate the entire rolling chat history string! We parse ONLY the current turn.
    if not just_initialized_intent and isinstance(last_message, HumanMessage):
        current_turn_text = str(last_message.content).strip()
        missing_before_turn = [k for k in required_keys.keys() if k not in form_buffer]
        
        # Track if an explicit key=value parameter format was processed
        explicit_assignment_matched = False
        
        for field_key in required_keys.keys():
            if field_key not in form_buffer:
                # Scan for explicit assignments on the current text line (e.g., lastName=John)
                match = re.search(rf'\b{field_key}\s*=\s*([^\s,]+)', current_turn_text, re.IGNORECASE)
                if match:
                    form_buffer[field_key] = match.group(1).strip()
                    explicit_assignment_matched = True
                # Direct type extraction convenience checks
                elif field_key == "email" and "@" in current_turn_text and "." in current_turn_text:
                    form_buffer["email"] = current_turn_text
                    explicit_assignment_matched = True

        # Positional 7-digit unit identifier extractor fallback
        if "unitUUID" in required_keys and "unitUUID" not in form_buffer:
            raw_digits = re.findall(r'\b\d{7}\b', current_turn_text)
            if raw_digits:
                form_buffer["unitUUID"] = str(raw_digits[0])
                explicit_assignment_matched = True
                print(f"\n📂 VALIDATOR: Automatically mapped raw input text to slot 'unitUUID': '{form_buffer['unitUUID']}'", file=sys.stderr)

        # 🚀 SMART CONVERSATIONAL FALLBACK: If no explicit 'key=' pattern matched, 
        # map the raw reply directly to the single active slot the system is waiting for! [🔒]
        if not explicit_assignment_matched and not "=" in current_turn_text:
            if missing_before_turn:
                active_waiting_field = str(missing_before_turn[0]).strip()
                
                if active_waiting_field == "email" and not "@" in current_turn_text:
                    print("\n⚠️ VALIDATOR: Input ignored. Expected an email format structure.", file=sys.stderr)
                elif active_waiting_field == "unitUUID" and not re.match(r'^\d{7}$', current_turn_text):
                    print("\n⚠️ VALIDATOR: Input ignored. Expected a 7-digit unit ID code cell.", file=sys.stderr)
                else:
                    form_buffer[active_waiting_field] = current_turn_text
                    print(f"\n📂 VALIDATOR: Automatically mapped raw conversational reply to slot '{active_waiting_field}': '{current_turn_text}'", file=sys.stderr)

    # 3. IDENTIFY MISSING SLOTS
    missing_fields_list = []
    next_prompt_text = ""
    dynamic_lookup_records = []
    
    for field_key, field_props in required_keys.items():
        if field_key not in form_buffer:
            missing_fields_list.append(field_key)
            if not next_prompt_text:
                next_prompt_text = field_props.get("prompt")
                
                if "dynamic_lookup_query" in field_props:
                    try:
                        import data_retrieval_engine
                        active_sites = state.get("site_id", []) or []
                        if active_sites:
                            site_params = ", ".join([str(int(s)) for s in active_sites])
                            compiled_sql = field_props["dynamic_lookup_query"] % site_params
                            dynamic_lookup_records = data_retrieval_engine.execute_query(compiled_sql, {})
                    except Exception as db_fault:
                        print(f"📡 Dynamic validation lookups sweep crashed: {str(db_fault)}", file=sys.stderr)

    # 🛑 SCENARIO A: FORM IS INCOMPLETE - DISPLAY REMAINING FIELDS AND HALT
    if missing_fields_list:
        menu_lines = [
            f"⚠️ MISSING REQUIRED PARAMETERS FOR TRANSACTION TRACK '{intent}':",
            f"Remaining fields needed: {missing_fields_list}\n",
            next_prompt_text
        ]
        
        if dynamic_lookup_records:
            menu_lines.append("\nAvailable Selection Resource Records Choices:")
            for row in dynamic_lookup_records:
                if isinstance(row, dict): u_id, u_name = row.get("id"), row.get("name")
                elif isinstance(row, (list, tuple)) and len(row) >= 2: u_id, u_name = row[0], row[1]
                else: u_id, u_name = row, row
                menu_lines.append(f"  -> Select Target ID Identifier: '{u_id}' ({u_name})")
                
        menu_prompt_message = AIMessage(content="\n".join(menu_lines))
        print(f"\n{menu_prompt_message.content}\n", file=sys.stderr)
        
        # Return explicit shadow copies to insulate memory reference frames [🔒]
        return {
            "messages": [menu_prompt_message],
            "active_mutation_intent": intent,
            "gathered_form_payload": dict(form_buffer).copy(),
            "discovered_site_ids": ["form_wait_state"]
        }

    # 🔓 SCENARIO B: FORM IS 100% COMPLETE - COMPILE TRANSACTION PAYLOAD AND DISPATCH
    print(f"\n🔏 ALL REQUIRED TRANSACTION SLOTS GATHERED: {form_buffer}", file=sys.stderr)
    
    for optional_key, optional_props in schema_rules.get("optional_fields", {}).items():
        if optional_key not in form_buffer:
            form_buffer[optional_key] = optional_props.get("default")

    # Package into your uniform twin-track tool contract schema format
    tool_call_signature = AIMessage(
        content="Form compiled. Dispatching live database execution payloads...",
        tool_calls=[{
            "name": "mutate_storage_records",
            "args": {
                "action_type": intent,
                "resource_identifier": str(form_buffer.get("unitUUID")),
                "mutation_payload_value": json.dumps(form_buffer)
            },
            "id": "dynamic_form_call_101"
        }]
    )
    
    return {
        "messages": [tool_call_signature],
        "active_mutation_intent": "FORM_COMPLETE",
        "gathered_form_payload": dict(form_buffer).copy(),
        "discovered_site_ids": [] 
    }
