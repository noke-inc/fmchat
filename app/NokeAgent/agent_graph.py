# agent_graph.py
import json
import os
import sys
import re
from typing import TypedDict, Annotated, Sequence, Optional, List,Literal
from enum import Enum
from langchain_core import messages
from pydantic import create_model
# 1. ─── DYNAMIC PATH INJECTION (Must run BEFORE custom project imports) ───
mcp_server_absolute_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "eks", "mcp_server"))
if mcp_server_absolute_directory not in sys.path:
    sys.path.append(mcp_server_absolute_directory)

# Load environment overrides from local file configurations before model calls occur
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

# Core LangChain and State Graph framework modules
from langchain_aws import ChatBedrock
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage,AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages

import data_retrieval_engine

# 2. FIXED: Reference the absolute layout path through the live module pointer
json_schema_absolute_path = os.path.join(
    os.path.dirname(os.path.abspath(data_retrieval_engine.load_database_schema_config.__code__.co_filename)), 
    "database_schema.json"
)

# 3. Trigger your boot loader schema configuration factory
data_retrieval_engine.load_database_schema_config(json_schema_absolute_path)

# 3. Read the live object anywhere inside your code loops
active_catalog = data_retrieval_engine.SCHEMA_CATALOG


BEDROCK_REGION: str = os.getenv("BEDROCK_REGION", "us-east-2")
BEDROCK_MODEL_ID: str = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-micro-v1:0")

NO_MATCHING_RECORDS_RESPONSE = "No matching records were found for your request."
TOOL_EXECUTION_ERROR_RESPONSE = "Unable to retrieve that information right now. Please try again."
ORCHESTRATOR_TOOLUSE_ERROR_RESPONSE = "Unable to process your request because it does not meet the required input criteria. Please review your request and try again with more specific or relevant information."


# =============================================================================
# 2. SHARED CONVERSATIONAL GRAPH STATE MATRIX
# =============================================================================
class AgentState(TypedDict):
    """
    Tracks conversational stream log array alongside zero-hardcoded multi-tenant primitives.
    Fully extensible for future session variable properties additions.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: Optional[int]
    company_id: Optional[List[int]]             # 🚀 EXPANDED: Global authorized corporate scope [🔒]
    site_id: Optional[List[int]]                # Global authorized facility scope boundary [🔒]
    
    # Hidden session cache cells to track multi-turn user choice memory
    active_session_company: Optional[List[int]]  # Locked query corporate target context [🔒]
    active_session_site: Optional[List[int]]     # Locked query facility target context [🔒]
    
    discovered_company_ids: Optional[List[int]]  # Companies found in the active session
    discovered_site_ids: Optional[List[int]]     # Sites isolated during database sweeps
    pending_user_query: Optional[str]            # Captures original query while waiting for scope selection
    awaiting_site_selection: Optional[bool]      # True when user must provide site id or ALL
    
    # 🚀 SECURED NAME STORAGE: Holds dynamic text maps (e.g. {"site_1001005": "Aex's Office"})
    # Completely replaces fake hardcoded string fallbacks across all menus! [🔒]
    metadata_names_map: Optional[dict] 


# =============================================================================
# 3. DEFINE THE FLAT-STRING OPTIMIZED TOOL INTERFACE SCHEMA
# =============================================================================
@tool
def execute_storage_query(
    intent_type: str, 
    target_subjects: str,       # Simple flat string parameters keep Amazon Nova completely stable
    semantic_filters: Optional[str] = None, 
    aggregation_column: Optional[str] = None, 
    search_keyword: Optional[str] = None
) -> str:
    """
    Unified read-only data gateway portal. Invoke this tool whenever the operator 
    requests calculations, text record lookups, counts, or status metrics regarding 
    any discovered system entities or schema categories.
    """
    raise NotImplementedError("This base tool signature is intercepted dynamically by the Graph node runtime.")


def _llm() -> ChatBedrock:
    """Returns a securely bound Amazon Bedrock client execution instance."""
    return ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        region_name=BEDROCK_REGION,
        model_kwargs={"temperature": 0, "max_tokens": 2048},
    )


def call_bedrock_orchestrator(state: AgentState):
    """The driving LLM node that pre-identifies schemas and forces Nova into strict tool-calling extraction."""
    import re
    import sys
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    messages = state["messages"]
    
    # ─── EXTRACTION FIX: SAFE STRING CONVERSION FOR STUDIO CONTAINERS ─── [▲]
    pending_user_query = state.get("pending_user_query")
    raw_content = messages[-1].content
    orchestrator_user_payload = messages[-1].content
    if pending_user_query and isinstance(messages[-1], HumanMessage):
        selection_text = str(messages[-1].content).lower().strip()
        if re.search(r'\b\d+\b', selection_text) or re.search(r'\ball\b', selection_text):
            raw_content = pending_user_query
            orchestrator_user_payload = pending_user_query
    flat_prompt_string = ""
    if isinstance(raw_content, list):
        for block in raw_content:
            if isinstance(block, dict) and "text" in block:
                flat_prompt_string += block["text"]
            elif isinstance(block, str):
                flat_prompt_string += block
    else:
        flat_prompt_string = str(raw_content)
        
    last_human_prompt = flat_prompt_string.lower().strip()
    
    # Clean out trailing punctuation symbols smoothly and compact white space
    clean_prompt_normalized = re.sub(r'[^\w\s]', ' ', last_human_prompt)
    clean_prompt_normalized = " ".join(clean_prompt_normalized.split())
    
    # =============================================================================
    # ─── EXTRACTION STEP A: LOCAL DUAL-LAYER METADATA DISCOVERY ─── [CP6]
    # =============================================================================
    discovered_entities = []
    pruned_columns_vocabulary = []
    system_isolation_keys = list(state.keys())
    if "messages" in system_isolation_keys:
        system_isolation_keys.remove("messages")
        
    import data_retrieval_engine
    active_catalog = data_retrieval_engine.SCHEMA_CATALOG
    
    # Loop over every table entity registered inside your loaded schema JSON
    for entity_name, entity_meta in active_catalog.get("entities", {}).items():
        is_entity_active = False
        
        # Track 1: Sweep Top-Level Table Aliases
        table_aliases_pool = entity_meta.get("aliases", []) + [entity_name]
        clean_table_aliases = [str(alias).lower().strip() for alias in table_aliases_pool]
        for alias in clean_table_aliases:
            escaped_alias = re.escape(alias)
            if re.search(rf'\b{escaped_alias}\b', clean_prompt_normalized):
                is_entity_active = True
                break
                
        # Track 2: GLOBAL SWEEP - Scan inside column metadata and synonyms arrays [CP6]
        allowed_cols_dict = entity_meta.get("allowed_columns", {})
        column_metadata_dict = entity_meta.get("column_metadata", {})
        active_fields_this_table = []
        
        for col_name, col_props in allowed_cols_dict.items():
            col_meta_block = column_metadata_dict.get(col_name, {})
            col_aliases = col_meta_block.get("aliases", []) or []
            enum_synonyms = []
            for enum_key, enum_list in col_meta_block.get("enum_map", {}).items():
                enum_synonyms.extend(enum_list)
                
            col_pool = (
                {str(ca).lower().strip() for ca in col_aliases} | 
                {col_name.lower()} | 
                {str(es).lower().strip() for es in enum_synonyms}
            )
            
            if col_name in system_isolation_keys or any(re.search(rf'\b{re.escape(c)}\b', clean_prompt_normalized) for c in col_pool):
                active_fields_this_table.append(f"  - Field: Table/Concept '{entity_name}' property column: '{col_name}' (Type: {col_props.get('type')})")
                if col_name not in system_isolation_keys:
                    is_entity_active = True
                    
        if is_entity_active:
            if entity_name not in discovered_entities:
                discovered_entities.append(entity_name)
            for identity_col in ["id", "name"]:
                if identity_col in allowed_cols_dict:
                    identity_str = f"  - Field: Table/Concept '{entity_name}' property column: '{identity_col}' (Type: {allowed_cols_dict[identity_col].get('type')})"
                    if identity_str not in pruned_columns_vocabulary:
                        pruned_columns_vocabulary.append(identity_str)
            for active_field_str in active_fields_this_table:
                if active_field_str not in pruned_columns_vocabulary:
                    pruned_columns_vocabulary.append(active_field_str)

    # =============================================================================
    # ─── EXTRACTION STEP B: OUT-OF-SCOPE DOMAIN PROTECTION GUARD RAIL ─── [🔒]
    # =============================================================================
    if not discovered_entities:
        print("\n🛑" + "─"*32 + " OUT-OF-SCOPE ENFORCEMENT DETECTED " + "─"*31, file=sys.stderr)
        print("Prompt maps to zero database entities. Terminating query loop safely.", file=sys.stderr)
        print("─"*100 + "\n", file=sys.stderr)
        
        refusal_response = "I'm sorry, that information is not available."
        return {"messages": [AIMessage(content=refusal_response)]}

    # Mathematically compute driver Fact Table densities
    fact_table_entity = discovered_entities if discovered_entities else "unresolved"
    max_relationship_density = -1
    for candidate in discovered_entities:
        relationship_count = len(active_catalog["entities"].get(candidate, {}).get("relationships", {}))
        if relationship_count > max_relationship_density:
            max_relationship_density = relationship_count
            fact_table_entity = candidate
            
    vocabulary_text_block = "\n".join(pruned_columns_vocabulary)
    expected_sequence_token = ", ".join(discovered_entities)

    # ── Schema-derived semantic token vocabulary (zero hardcoding) ────────────
    # Aggregation ops come first (from allowed_aggregations), then every
    # enum_map synonym across all column_metadata blocks for the discovered
    # entities.  Adding a new entity or new enum_map entries to
    # database_schema.json automatically expands this list — no code changes.
    _all_semantic_tokens: list = []
    for _ent in discovered_entities:
        _ent_def = active_catalog["entities"].get(_ent, {})
        for _agg_key in (_ent_def.get("allowed_aggregations") or {}):
            if _agg_key not in _all_semantic_tokens:
                _all_semantic_tokens.append(_agg_key)
    for _ent in discovered_entities:
        _ent_def = active_catalog["entities"].get(_ent, {})
        for _col_name, _col_block in _ent_def.get("column_metadata", {}).items():
            for _canonical, _synonyms in (_col_block.get("enum_map") or {}).items():
                for _syn in _synonyms:
                    _syn_lc = str(_syn).lower().strip()
                    if _syn_lc not in _all_semantic_tokens:
                        _all_semantic_tokens.append(_syn_lc)
    semantic_tokens_hint = ", ".join("'" + t + "'" for t in _all_semantic_tokens)

    print("\n🔍" + "─"*30 + " 100% DATA-DRIVEN PRE-IDENTIFICATION SWEEP " + "─"*30, file=sys.stderr)
    print(f"📁 Dynamically Discovered Intents (Entities): {discovered_entities}", file=sys.stderr)
    print(f"📊 Mathematically Derived Fact Table Anchor: '{fact_table_entity}'", file=sys.stderr)
    print("─"*104 + "\n", file=sys.stderr)

    # =============================================================================
    # ─── 🚀 EXTRACTION STEP C: NATIVE STABLE JSON SCHEMAS SPECIFICATION ─── [🔒]
    # =============================================================================
    # This completely replaces Pydantic create_model to achieve flawless Bedrock serialization stability
    native_tool_schema = {
        "name": "execute_storage_query",
        "description": "Unified read-only data gateway portal for executing lookups.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent_type": {
                    "type": "string",
                    "enum": ["DATA_AGGREGATION", "DATA_RETRIEVAL"],
                    "description": "Operational track target. Use 'DATA_AGGREGATION' strictly for math/counts. Use 'DATA_RETRIEVAL' for details grids."
                },
                "target_subjects": {
                    "type": "string",
                    "enum": [expected_sequence_token],
                    "description": f"The active table targets required for this query. You MUST choose exactly the string value: '{expected_sequence_token}'."
                },
                "semantic_filters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "ALL modifier tokens present in the user query as separate list elements. "
                        f"Schema-derived valid tokens for this request: [{semantic_tokens_hint}]. "
                        "Include EVERY token from the user query that matches the list above. "
                        "EXAMPLE: 'how many open units?' -> ['count', 'open']. "
                        "EXAMPLE: 'count active locks' -> ['count', 'active']. "
                        "NEVER omit a status qualifier word."
                    )
                },
                "search_keyword": {
                    "type": "string",
                    "description": "Wildcard search value for specific entity identifiers, human-readable names, or reference labels ONLY (e.g. 'LA879', 'John Smith'). NEVER put numeric site IDs, company IDs, or session context values here — those are already handled by the session security layer."
                },
                "aggregation_column": {
                    "type": "string",
                    "description": "The numerical metric property field required if running calculation total functions."
                }
            },
            "required": ["intent_type", "target_subjects"]
        }
    }

    # =============================================================================
    # ─── EXTRACTION STEP D: CONTEXT-LOCKED TEXT BLUEPRINT INJECTION ─── [🔒]
    # =============================================================================
    system_instruction = (
        "You are the data parameter extraction gateway for the enterprise information infrastructure.\n"
        "Your sole task is to identify requested concepts and isolate text filters.\n"
        "You MUST choose valid options matching the provided schema fields.\n\n"
        "🔏 ENTERPRISE BOUNDARY PROTECTION SHIELD:\n"
        "We have analyzed our data catalog and pre-identified your relevant schema rules locally.\n"
        f"The primary driver Fact Table for this request path is computed as: '{fact_table_entity}'\n"
        "The only valid system database configurations related to the operator's current request are:\n"
        f"{vocabulary_text_block}\n\n"
        "CRITICAL EXTRACTION CONSTRAINTS:\n"
        f"1. Inside the 'target_subjects' string field, you MUST pass a comma-separated list choosing exclusively from this precise list: {discovered_entities}\n"
        " - Never invent concepts. If the question asks about users and site, write exactly: 'site, user'\n"
        f"2. Inside the 'semantic_filters' array, include EVERY modifier token from the user query as a separate element.\n"
        f"   Schema-derived valid tokens for this request: [{semantic_tokens_hint}]\n"
        "   Add every token the user said that matches the list above.\n"
        "   EXAMPLE: 'how many open units?' -> semantic_filters: ['count', 'open']\n"
        "   EXAMPLE: 'count active locks' -> semantic_filters: ['count', 'active']\n"
        "   NEVER omit a status qualifier word from the array.\n"
        "3. Route specific entity reference codes, human names, unit labels, or email values exclusively to 'search_keyword'. Example: unit name 'LA879' belongs in search_keyword.\n"
        "4. NEVER put numeric site IDs, company IDs, or any session identifier into 'search_keyword'. Site and company scope is managed by the session layer automatically.\n"
        "5. Do not invent non-existent column fields. Do not hypothesize parameters outside the provided context block.\n"
        "6. You MUST call the tool 'execute_storage_query' exactly once for this request."
    )
    
    # print("\n📡" + "─"*32 + " OUTGOING AMAZON NOVA SYSTEM INGEST " + "─"*32, file=sys.stderr)
    # print(system_instruction, file=sys.stderr)
    # print(f"💬 Active User Entry Payload: '{orchestrator_user_payload}'", file=sys.stderr)
    # print("─"*100 + "\n", file=sys.stderr)
    # =============================================================================
    # ─── EXTRACTION STEP E: SECURED MEMORY CONTEXT MATRIX ROUTING ─── [🔒]
    # =============================================================================
    # Bind using the ultra-stable native dictionary envelope schema contract [🔒]
    llm_with_tools = _llm().bind_tools([native_tool_schema])
    # Strip historical menu/selection turns so model cannot pick up site IDs from prior context.
    # Keep only: the effective user query. Prior tool/AI/selection messages are excluded.
    from langchain_core.messages import ToolMessage as _ToolMessage
    _menu_markers = ("MULTIPLE FACILITY SITES", "MULTIPLE CORPORATE ACCOUNTS")
    filtered_history = [
        msg for msg in messages
        if not (
            isinstance(msg, (AIMessage, _ToolMessage))
            or (
                isinstance(msg, HumanMessage)
                and re.match(r'^\s*\d+\s*$', str(msg.content).strip())
            )
            or (
                isinstance(msg, AIMessage)
                and any(marker in str(msg.content) for marker in _menu_markers)
            )
        )
    ]
    effective_human = HumanMessage(content=str(orchestrator_user_payload))
    clean_runtime_track = [SystemMessage(content=system_instruction), effective_human]
    try:
        response_message = llm_with_tools.invoke(clean_runtime_track)
    except Exception as orchestrator_fault:
        print("\n💥" + "─"*29 + " ORCHESTRATOR TOOLUSE FAILURE " + "─"*29, file=sys.stderr)
        print(str(orchestrator_fault), file=sys.stderr)
        print("─"*100 + "\n", file=sys.stderr)
        return {"messages": [AIMessage(content=ORCHESTRATOR_TOOLUSE_ERROR_RESPONSE)]}

    print("\n🧠" + "─"*30 + " AMAZON NOVA ORCHESTRATOR RAW OUTPUT " + "─"*30, file=sys.stderr)
    print(f"AIMessage.content: {response_message.content}", file=sys.stderr)
    print(f"AIMessage.tool_calls: {getattr(response_message, 'tool_calls', None)}", file=sys.stderr)
    print(f"AIMessage.additional_kwargs: {getattr(response_message, 'additional_kwargs', {})}", file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)

    return {"messages": [response_message]}

# =============================================================================
# 4. LIVE MCP DATABASE ROUTING NODE (HARDENED SECURITY MATRIX)
# =============================================================================
# In agent_graph.py -> Update your execute_graph_tools orchestration node block

# In agent_graph.py -> Overwrite the top segment of execute_graph_tools completely

def execute_graph_tools(state: AgentState):
    """Secure runtime node that safely locates tool invocation signatures across the state history."""
    import sys
    import json
    import re
    from langchain_core.messages import ToolMessage, HumanMessage, AIMessage
    
    messages = state["messages"]
    if not messages:
        return {"messages": []}
        
    # ─── 🚀 FIXED PERMANENTLY: COMPREHENSIVE BACKWARD TOOL EXTRACTOR ─── [▲]
    # Scans backward through history using your multi-format validation gates 
    # to locate the true initiating AIMessage emitted by Amazon Bedrock Converse!
    target_ai_message = None
    
    for msg in reversed(messages):
        if msg.type == "ai":
            is_valid_tool_msg = False
            
            # Check 1: Standard Class Attribute Payload
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                is_valid_tool_msg = True
            # Check 2: Embedded Content Dictionary Block (Amazon Nova JSON Schemas)
            elif isinstance(getattr(msg, "content", None), list):
                for block in msg.content:
                    if isinstance(block, dict) and ("tool_use" in block or "toolCall" in block or "tool_calls" in block):
                        is_valid_tool_msg = True
                        break
            # Check 3: Additional Keyword Arguments Envelope
            elif hasattr(msg, "additional_kwargs") and ("tool_calls" in msg.additional_kwargs or "tool_use" in msg.additional_kwargs):
                is_valid_tool_msg = True
                
            if is_valid_tool_msg:
                target_ai_message = msg
                break
                
    # Fallback assignment to prevent empty reference exceptions
    if not target_ai_message:
        target_ai_message = messages[-1]
        
    last_message = messages[-1]
    
    jwt_company_fence = state.get("company_id", []) or []
    active_company_cache = state.get("active_session_company", []) or []
    jwt_site_fence = state.get("site_id", []) or []
    active_site_cache = state.get("active_session_site", []) or []
    pending_user_query = state.get("pending_user_query")
    awaiting_site_selection = bool(state.get("awaiting_site_selection", False))
    
    names_catalog = state.get("metadata_names_map", {})
    if not isinstance(names_catalog, dict):
        names_catalog = {}
        
    # Process multi-turn Human wait-state context selections if the user just replied [🔒]
    if isinstance(last_message, HumanMessage):
        flat_text = str(last_message.content).lower().strip()
        digits_match = re.findall(r'\b\d+\b', flat_text)
        # On normal query turns, clear stale pending prompt so synthesis does not reuse prior questions.
        if not awaiting_site_selection and not digits_match and not ("all" in flat_text or "all sites" in flat_text):
            pending_user_query = None
        if digits_match:
            target_digit_id = int(digits_match[0]) # Target the first extracted digit integer slot
            if target_digit_id in jwt_company_fence and not active_company_cache:
                active_company_cache = [target_digit_id]
            elif target_digit_id in jwt_site_fence and not active_site_cache:
                active_site_cache = [target_digit_id]
                awaiting_site_selection = False
        elif "all" in flat_text or "all sites" in flat_text:
            if active_company_cache and not active_site_cache:
                active_site_cache = list(jwt_site_fence)
                awaiting_site_selection = False

    # =============================================================================
    # ─── POSITION-SAFE ISOLATED METADATA LOOKUP QUERIES ─── [🔒]
    # =============================================================================
    if jwt_company_fence:
        try:
            company_ids_placeholder = ", ".join([f"'{int(c_id)}'" for c_id in jwt_company_fence])
            raw_companies = data_retrieval_engine.execute_query(
                f"SELECT id, name FROM companies WHERE id IN ({company_ids_placeholder});", {}
            )
            if not raw_companies:
                raise ValueError(f"No records found in 'companies' table for IDs: {jwt_company_fence}")
            for row in raw_companies:
                if isinstance(row, dict): c_id, c_name = row.get("id"), row.get("name")
                elif isinstance(row, (list, tuple)) and len(row) >= 2: c_id, c_name = row[0], row[1]
                names_catalog[f"company_{c_id}"] = str(c_name)
        except Exception as e:
            raise RuntimeError(f"Critical Corporate Metadata Resolution Fault: {str(e)}")

    if jwt_site_fence:
        try:
            site_ids_placeholder = ", ".join([f"'{int(s_id)}'" for s_id in jwt_site_fence])
            raw_sites = data_retrieval_engine.execute_query(
                f"SELECT id, name FROM sites WHERE id IN ({site_ids_placeholder});", {}
            )
            if not raw_sites:
                raise ValueError(f"No records found in 'sites' table for IDs: {jwt_site_fence}")
            for row in raw_sites:
                if isinstance(row, dict): s_id, s_name = row.get("id"), row.get("name")
                elif isinstance(row, (list, tuple)) and len(row) >= 2: s_id, s_name = row[0], row[1]
                names_catalog[f"site_{s_id}"] = str(s_name)
        except Exception as e:
            raise RuntimeError(f"Critical Site Metadata Resolution Fault: {str(e)}")

    runtime_sites = active_site_cache if active_site_cache else jwt_site_fence
    computed_context = {
        "company_id": active_company_cache if active_company_cache else jwt_company_fence,
        "site_id": runtime_sites,
        "user_id": state.get("user_id")
    }

    print("\n🧩" + "─"*32 + " MCP EXECUTION CONTEXT " + "─"*32, file=sys.stderr)
    print(json.dumps(computed_context, indent=2, default=str), file=sys.stderr)
    print(f"pending_user_query: {pending_user_query}", file=sys.stderr)
    print(f"awaiting_site_selection: {awaiting_site_selection}", file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)
    
    tool_responses = []
    found_site_ids = set()
    
    # 🚀 FIXED: Dynamic tool call extractor compatible with standard attributes and raw dictionaries [▲]
    active_tool_calls_list = []
    if hasattr(target_ai_message, "tool_calls") and target_ai_message.tool_calls:
        active_tool_calls_list = target_ai_message.tool_calls
    elif hasattr(target_ai_message, "additional_kwargs") and "tool_calls" in target_ai_message.additional_kwargs:
        active_tool_calls_list = target_ai_message.additional_kwargs["tool_calls"]
    elif isinstance(getattr(target_ai_message, "content", None), list):
        for block in target_ai_message.content:
            if isinstance(block, dict) and "tool_use" in block:
                # Format raw dictionary payload back to standard format strings natively [▲]
                t_use = block["tool_use"]
                active_tool_calls_list.append({
                    "name": t_use.get("name"),
                    "args": t_use.get("input", {}),
                    "id": t_use.get("toolUseId")
                })

    # Execute your database query blocks perfectly
    # If this turn is only a selection response and we have no tool payload yet,
    # let the router send us to orchestrator with preserved pending query.
    if not active_tool_calls_list and isinstance(last_message, HumanMessage):
        lower_input = str(last_message.content).lower().strip()
        has_selection_digit = bool(re.findall(r'\b\d+\b', lower_input))
        has_all_keyword = bool(re.search(r'\ball\b', lower_input))
        if (has_selection_digit or has_all_keyword) and pending_user_query:
            return {
                "messages": [],
                "discovered_site_ids": list(runtime_sites),
                "discovered_company_ids": list(jwt_company_fence),
                "active_session_company": active_company_cache,
                "active_session_site": active_site_cache,
                "metadata_names_map": names_catalog,
                "pending_user_query": pending_user_query,
                "awaiting_site_selection": awaiting_site_selection
            }

    for tool_call in active_tool_calls_list:
        # Normalize dictionary accesses to support standard items
        tc_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", "")
        tc_args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
        tc_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", "")
        
        if tc_name == "execute_storage_query":
            print("\n🤖" + "─"*30 + " AMAZON NOVA INTERPOLATED TOOL PAYLOAD " + "─"*30, file=sys.stderr)
            print(json.dumps(tc_args, indent=2), file=sys.stderr)
            print("─"*100 + "\n", file=sys.stderr)
            
            parsed_subjects = [s.strip() for s in tc_args.get("target_subjects", "").split(",") if s.strip()]

            # Normalize semantic_filters to list regardless of whether model emits array or comma string.
            raw_filters = tc_args.get("semantic_filters") or []
            if isinstance(raw_filters, list):
                parsed_filters = [str(f).strip() for f in raw_filters if str(f).strip()]
            else:
                parsed_filters = [f.strip() for f in str(raw_filters).split(",") if f.strip()]

            # ── Deterministic enum-synonym injection fallback ─────────────────────
            # If the model omitted a status qualifier that clearly appears in the
            # user query, inject it here by scanning SCHEMA_CATALOG enum_map synonyms
            # for every target entity. Fully schema-driven — new entities/enum_map
            # entries in database_schema.json are covered automatically.
            _uq_text = str(pending_user_query).lower() if pending_user_query else ""
            if not _uq_text:
                for _uq_msg in reversed(messages):
                    if isinstance(_uq_msg, HumanMessage):
                        _uq_text = str(_uq_msg.content).lower()
                        break
            _uq_clean = re.sub(r'[^\w\s]', ' ', _uq_text)
            _se = data_retrieval_engine.SCHEMA_CATALOG.get("entities", {})
            for _subj in parsed_subjects:
                for _col_nm, _col_blk in _se.get(_subj, {}).get("column_metadata", {}).items():
                    for _cano, _syns in (_col_blk.get("enum_map") or {}).items():
                        for _syn in _syns:
                            _syn_lc = str(_syn).lower().strip()
                            if re.search(r'\b' + re.escape(_syn_lc) + r'\b', _uq_clean) and _syn_lc not in parsed_filters:
                                print(f"🔧 Injecting missing semantic token '{_syn_lc}' (col:{_col_nm} -> canonical:'{_cano}')", file=sys.stderr)
                                parsed_filters.append(_syn_lc)

            # Sanitize search_keyword: drop it if it matches any session scope ID.
            raw_search = tc_args.get("search_keyword") or ""
            session_scope_ids = set()
            for _ids in [jwt_company_fence, jwt_site_fence, active_company_cache, active_site_cache]:
                for _id in (_ids or []):
                    session_scope_ids.add(str(_id).strip())
            if raw_search.strip() in session_scope_ids:
                print(f"⚠️  search_keyword '{raw_search}' matches a session scope ID — dropping it to prevent SQL contamination.", file=sys.stderr)
                raw_search = None
            clean_search = raw_search if raw_search and raw_search.strip() else None

            try:
                db_rows_matrix = data_retrieval_engine.run_compiled_mcp_query(
                    subjects=parsed_subjects,
                    intent_type=tc_args.get("intent_type", "DATA_RETRIEVAL"),
                    session_context=computed_context,
                    semantic_filters=parsed_filters,
                    aggregation_column=tc_args.get("aggregation_column"),
                    search_keyword=clean_search
                )
                
                print("\n" + "📝" + "─"*32 + " DYNAMICALLY GENERATED SQL COMMAND " + "─"*31, file=sys.stderr)
                if hasattr(data_retrieval_engine, "LAST_COMPILED_SQL"):
                    print(getattr(data_retrieval_engine, "LAST_COMPILED_SQL"), file=sys.stderr)
                print("─"*100 + "\n", file=sys.stderr)

                # print("\n📦" + "─"*33 + " MCP RAW RESULT PAYLOAD " + "─"*33, file=sys.stderr)
                # print(json.dumps(db_rows_matrix, indent=2, default=str), file=sys.stderr)
                # print("─"*100 + "\n", file=sys.stderr)
                
                if isinstance(db_rows_matrix, list):
                    for row in db_rows_matrix:
                        if isinstance(row, dict):
                            s_id_cell = row.get("site_id") or row.get("site_site_id")
                        elif isinstance(row, (list, tuple)) and len(row) > 0:
                            s_id_cell = row[0]
                        if s_id_cell is not None: found_site_ids.add(int(s_id_cell))
                            
                if isinstance(db_rows_matrix, list):
                    row_count = len(db_rows_matrix)
                    tool_status = "success_with_rows" if row_count > 0 else "success_no_rows"
                    string_payload = json.dumps({
                        "tool_status": tool_status,
                        "row_count": row_count,
                        "data": db_rows_matrix
                    }, default=str)
                else:
                    string_payload = json.dumps({
                        "tool_status": "success_with_rows",
                        "row_count": 1,
                        "data": db_rows_matrix
                    }, default=str)
            except Exception as query_fault:
                string_payload = json.dumps({
                    "tool_status": "error",
                    "row_count": 0,
                    "error": str(query_fault)
                })
                
            tool_responses.append(ToolMessage(content=string_payload, tool_call_id=tc_id, name=tc_name))
                
    final_discovered_sites = list(found_site_ids)
    if not final_discovered_sites and not active_site_cache and len(runtime_sites) > 1:
        final_discovered_sites = [int(s_id) for s_id in runtime_sites]

    return {
        "messages": tool_responses, 
        "discovered_site_ids": final_discovered_sites,
        "discovered_company_ids": list(jwt_company_fence),
        "active_session_company": active_company_cache,
        "active_session_site": active_site_cache,
        "metadata_names_map": names_catalog,
        "pending_user_query": pending_user_query,
        "awaiting_site_selection": awaiting_site_selection
    }


# =============================================================================
# 5. DYNAMIC INTERACTIVE DISAMBIGUATION MENUS
# =============================================================================
# In agent_graph.py -> Overwrite your menu nodes block completely

# In agent_graph.py -> Overwrite your menu nodes block completely

def compile_company_selection_menu(state: AgentState):
    """Dynamically queries the database for corporate names and displays an interactive prompt."""
    import sys
    jwt_company_fence = state.get("company_id", []) or []
    
    if not jwt_company_fence:
         raise RuntimeError("Critical Hierarchy Fault: No corporate privileges passed inside state parameters.")
         
    company_ids_placeholder = ", ".join([f"'{int(c_id)}'" for c_id in jwt_company_fence])
    raw_companies = data_retrieval_engine.execute_query(
        f"SELECT id, name FROM companies WHERE id IN ({company_ids_placeholder});", {}
    )
    if not raw_companies:
         raise RuntimeError(f"Critical System Governance Fault: Unable to resolve company mapping names for IDs: {jwt_company_fence}")
         
    names_map = state.get("metadata_names_map", {}) or {}
    formatted_menu_lines = []
    for row in raw_companies:
        if isinstance(row, dict):
            c_id, c_name = row.get("id"), row.get("name")
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            c_id, c_name = row[0], row[1]
        else:
            c_id, c_name = row, row
            
        names_map[f"company_{c_id}"] = str(c_name)
        formatted_menu_lines.append(f"  -> Type '{c_id}' to select **{c_name}**")
        
    joined_menu_content = "\n".join(formatted_menu_lines)
    prompt_text = (
        "⚠️ MULTIPLE CORPORATE ACCOUNTS IDENTIFIED:\n"
        f"Your profile possesses rights to {len(jwt_company_fence)} distinct corporate accounts.\n"
        "Please select which specific business identity context you wish to open:\n\n"
        f"{joined_menu_content}"
    )
    
    print("\n🎛️" + "─"*32 + " CORPORATE ACCOUNT MENU UNLOCKED " + "─"*30, file=sys.stderr)
    print(prompt_text, file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)
    
    # 🚀 FIXED: Added metadata_names_map back to the return state payload!
    return {
        "messages": [AIMessage(content=prompt_text)], 
        "discovered_company_ids": list(jwt_company_fence),
        "metadata_names_map": names_map
    }


def compile_site_selection_menu(state: AgentState):
    """Dynamically queries the database for site names and displays an interactive prompt."""
    import sys
    jwt_site_fence = state.get("site_id", []) or []
    
    if not jwt_site_fence:
         raise RuntimeError("Critical Hierarchy Fault: No facility privileges passed inside state parameters.")
         
    site_ids_placeholder = ", ".join([f"'{int(s_id)}'" for s_id in jwt_site_fence])
    raw_sites = data_retrieval_engine.execute_query(
        f"SELECT id, name FROM sites WHERE id IN ({site_ids_placeholder});", {}
    )
    if not raw_sites:
         raise RuntimeError(f"Critical System Governance Fault: Unable to resolve site mapping names for IDs: {jwt_site_fence}")
         
    names_map = state.get("metadata_names_map", {}) or {}
    pending_user_query = state.get("pending_user_query")
    if not pending_user_query:
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                pending_user_query = str(msg.content)
                break
    formatted_menu_lines = []
    for row in raw_sites:
        if isinstance(row, dict):
            s_id, s_name = row.get("id"), row.get("name")
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            s_id, s_name = row[0], row[1]
        else:
            s_id, s_name = row, row
            
        names_map[f"site_{s_id}"] = str(s_name)
        formatted_menu_lines.append(f"  -> Type '{s_id}' to select **{s_name}**")
        
    joined_site_content = "\n".join(formatted_menu_lines)
    prompt_text = (
        "⚠️ MULTIPLE FACILITY SITES IDENTIFIED:\n"
        f"Your lookup request maps to {len(jwt_site_fence)} different storage locations.\n"
        "Please specify which storage property location context you wish to inspect:\n\n"
        f"{joined_site_content}\n"
        "  -> Type 'ALL' to view an aggregated summary across the entire portfolio."
    )
    
    print("\n🎛️" + "─"*32 + " INTERACTIVE SITE MENU ACTIVATED " + "─"*31, file=sys.stderr)
    print(prompt_text, file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)
    
    # 🚀 FIXED: Added metadata_names_map back to the return state payload!
    return {
        "messages": [AIMessage(content=prompt_text)], 
        "discovered_site_ids": list(jwt_site_fence),
        "metadata_names_map": names_map,
        "pending_user_query": pending_user_query,
        "awaiting_site_selection": True
    }


def missing_company_scope_response(state: AgentState):
    """Visible stop response when no company scope is available in session state."""
    import sys
    message_text = "I cannot process this request because no company scope is available in this session."
    print("\n🛑" + "─"*30 + " MISSING COMPANY SCOPE " + "─"*30, file=sys.stderr)
    print(message_text, file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)
    return {
        "messages": [AIMessage(content=message_text)],
        "pending_user_query": None,
        "awaiting_site_selection": False
    }


def missing_site_scope_response(state: AgentState):
    """Visible stop response when no site scope is available in session state."""
    import sys
    message_text = "I cannot process this request because no site scope is available in this session."
    print("\n🛑" + "─"*31 + " MISSING SITE SCOPE " + "─"*31, file=sys.stderr)
    print(message_text, file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)
    return {
        "messages": [AIMessage(content=message_text)],
        "pending_user_query": None,
        "awaiting_site_selection": False
    }


def recover_no_tool_after_orchestrator(state: AgentState):
    """Deterministic recovery path if the orchestrator returns text with no tool call."""
    import sys
    import json
    import re

    jwt_company_fence = state.get("company_id", []) or []
    active_company_cache = state.get("active_session_company", []) or []
    jwt_site_fence = state.get("site_id", []) or []
    active_site_cache = state.get("active_session_site", []) or []
    pending_user_query = state.get("pending_user_query")
    awaiting_site_selection = bool(state.get("awaiting_site_selection", False))
    messages = state.get("messages", []) or []

    latest_human_text = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            latest_human_text = str(msg.content)
            break
    effective_query = str(pending_user_query or latest_human_text or "").strip()
    normalized_query = effective_query.lower()

    print("\n🧯" + "─"*24 + " ORCHESTRATOR NO-TOOL RECOVERY " + "─"*24, file=sys.stderr)
    print(f"pending_user_query: {pending_user_query}", file=sys.stderr)
    print(f"effective_query: {effective_query}", file=sys.stderr)
    print(f"awaiting_site_selection: {awaiting_site_selection}", file=sys.stderr)
    print(f"active_session_site: {active_site_cache}", file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)

    # If selection is still unresolved (or active context was cleared), redisplay the site menu.
    if len(jwt_site_fence) > 1 and not active_site_cache:
        return compile_site_selection_menu(state)

    # Schema-driven deterministic fallback when model skips tool calling.
    schema_entities = data_retrieval_engine.SCHEMA_CATALOG.get("entities", {})

    inferred_entities = []
    for entity_name, entity_meta in schema_entities.items():
        alias_pool = entity_meta.get("aliases", []) + [entity_name]
        for alias in alias_pool:
            alias_text = str(alias).lower().strip()
            if alias_text and re.search(rf"\b{re.escape(alias_text)}\b", normalized_query):
                inferred_entities.append(entity_name)
                break

    # Preserve schema order and uniqueness.
    inferred_entities = [e for e in schema_entities.keys() if e in set(inferred_entities)]

    # Infer intent/aggregation in a generic way and gate execution to supported operations.
    wants_count = bool(re.search(r"\b(how many|count|number of|total)\b", normalized_query))
    intent_type = "DATA_AGGREGATION" if wants_count else "DATA_RETRIEVAL"

    semantic_filters = []
    if intent_type == "DATA_AGGREGATION":
        if inferred_entities and "count" in schema_entities[inferred_entities[0]].get("allowed_aggregations", {}):
            semantic_filters.append("count")
        else:
            # Cannot run deterministic aggregation when schema doesn't allow it.
            inferred_entities = []

    # Infer enum-based predicate filters from schema metadata without hardcoded terms.
    for entity_name in inferred_entities:
        entity_meta = schema_entities.get(entity_name, {})
        for _, col_meta in (entity_meta.get("column_metadata", {}) or {}).items():
            enum_map = col_meta.get("enum_map", {}) or {}
            for canonical_value, synonyms in enum_map.items():
                term_pool = {str(canonical_value).lower().strip()} | {str(s).lower().strip() for s in (synonyms or [])}
                if any(term and re.search(rf"\b{re.escape(term)}\b", normalized_query) for term in term_pool):
                    canonical_token = str(canonical_value).lower().strip()
                    if canonical_token and canonical_token not in semantic_filters:
                        semantic_filters.append(canonical_token)

    if inferred_entities:
        runtime_sites = active_site_cache if active_site_cache else jwt_site_fence
        computed_context = {
            "company_id": active_company_cache if active_company_cache else jwt_company_fence,
            "site_id": runtime_sites,
            "user_id": state.get("user_id")
        }

        print("\n🧮" + "─"*18 + " SCHEMA-DRIVEN DETERMINISTIC FALLBACK EXECUTION " + "─"*18, file=sys.stderr)
        print(json.dumps({
            "subjects": inferred_entities,
            "intent_type": intent_type,
            "session_context": computed_context,
            "semantic_filters": semantic_filters
        }, indent=2, default=str), file=sys.stderr)

        try:
            db_rows_matrix = data_retrieval_engine.run_compiled_mcp_query(
                subjects=inferred_entities,
                intent_type=intent_type,
                session_context=computed_context,
                semantic_filters=semantic_filters,
                aggregation_column=None,
                search_keyword=None
            )

            print("\n📝" + "─"*32 + " DYNAMICALLY GENERATED SQL COMMAND " + "─"*31, file=sys.stderr)
            if hasattr(data_retrieval_engine, "LAST_COMPILED_SQL"):
                print(getattr(data_retrieval_engine, "LAST_COMPILED_SQL"), file=sys.stderr)
            print("─"*100 + "\n", file=sys.stderr)

            print("\n📦" + "─"*33 + " MCP RAW RESULT PAYLOAD " + "─"*33, file=sys.stderr)
            print(json.dumps(db_rows_matrix, indent=2, default=str), file=sys.stderr)
            print("─"*100 + "\n", file=sys.stderr)

            count_value = None
            if isinstance(db_rows_matrix, list) and db_rows_matrix:
                first_row = db_rows_matrix[0]
                if isinstance(first_row, dict):
                    count_value = first_row.get("count")
                    if count_value is None:
                        for key, val in first_row.items():
                            if "count" in str(key).lower():
                                count_value = val
                                break
                elif isinstance(first_row, (list, tuple)) and first_row:
                    count_value = first_row[0]

            if count_value is not None:
                answer_text = f"Based on the live record database snapshot, the current count is {int(count_value)}."
            elif isinstance(db_rows_matrix, list):
                if len(db_rows_matrix) == 0:
                    answer_text = NO_MATCHING_RECORDS_RESPONSE
                else:
                    answer_text = f"Based on the live record database snapshot, I found {len(db_rows_matrix)} matching records."
            else:
                answer_text = "I executed the query, but could not summarize a numeric result from the payload."

            return {
                "messages": [AIMessage(content=answer_text)],
                "pending_user_query": None,
                "awaiting_site_selection": False
            }
        except Exception as deterministic_fault:
            print(f"Deterministic fallback failed: {str(deterministic_fault)}", file=sys.stderr)
            print("─"*100 + "\n", file=sys.stderr)

    # Otherwise return a deterministic retry response without stale synthesis.
    fallback_text = (
        "I could not extract a valid database tool call for this turn. "
        "Please re-enter your request, and I will run the query again."
    )
    print(fallback_text, file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)

    return {
        "messages": [AIMessage(content=fallback_text)],
        "pending_user_query": pending_user_query,
        "awaiting_site_selection": awaiting_site_selection
    }



def generate_conversational_response(state: AgentState):
    """Synthesizes raw database JSON row data arrays back into elegant plain sentences."""
    import sys
    import json
    import re
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    
    messages = state["messages"]
    
    # Use latest human query by default. Only reuse pending query during active site-selection flow.
    pending_user_query = state.get("pending_user_query")
    awaiting_site_selection = bool(state.get("awaiting_site_selection", False))

    latest_human_prompt = "What is the requested data lookup?"
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            latest_human_prompt = str(msg.content)
            break

    user_initial_prompt = latest_human_prompt
    if awaiting_site_selection:
        selection_text = latest_human_prompt.lower().strip()
        is_selection_reply = bool(re.findall(r'\b\d+\b', selection_text)) or bool(re.search(r'\ball\b', selection_text))
        if is_selection_reply and pending_user_query:
            user_initial_prompt = str(pending_user_query)
            
    # ─── EXTRACTION STEP A: TRUNCATE AND COMPRESS CONTEXT WINDOW TIMELINE ───
    # We find the raw ToolMessage payload block and parse its row data cells natively
    # Use only tool outputs produced after the latest human turn to avoid stale snapshots.
    database_records_text = ""
    last_human_index = -1
    for idx, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            last_human_index = idx

    fresh_tool_messages = [
        msg for idx, msg in enumerate(messages)
        if msg.type == "tool" and idx > last_human_index
    ]

    for msg in fresh_tool_messages:
        if msg.type == "tool":
            try:
                raw_data = json.loads(msg.content)

                # Preferred envelope format from execute_graph_tools.
                if isinstance(raw_data, dict) and "tool_status" in raw_data:
                    tool_status = str(raw_data.get("tool_status", "")).strip().lower()
                    if tool_status == "success_no_rows":
                        print("\n🛑" + "─"*25 + " DETERMINISTIC NO-DATA RESPONSE " + "─"*25, file=sys.stderr)
                        print("Tool status indicates zero rows. Skipping synthesis.", file=sys.stderr)
                        print("─"*100 + "\n", file=sys.stderr)
                        return {"messages": [AIMessage(content=NO_MATCHING_RECORDS_RESPONSE)]}

                    if tool_status == "error":
                        print("\n🛑" + "─"*24 + " DETERMINISTIC TOOL ERROR RESPONSE " + "─"*24, file=sys.stderr)
                        print(f"Tool error: {raw_data.get('error')}", file=sys.stderr)
                        print("─"*100 + "\n", file=sys.stderr)
                        return {"messages": [AIMessage(content=TOOL_EXECUTION_ERROR_RESPONSE)]}

                    payload_data = raw_data.get("data")
                    if isinstance(payload_data, list) and len(payload_data) > 0:
                        micro_snapshot = payload_data[:3]
                        database_records_text = json.dumps(micro_snapshot, default=str)
                    elif isinstance(payload_data, list) and len(payload_data) == 0:
                        return {"messages": [AIMessage(content=NO_MATCHING_RECORDS_RESPONSE)]}
                    elif isinstance(payload_data, dict):
                        database_records_text = json.dumps(payload_data, default=str)
                    elif payload_data is not None:
                        database_records_text = str(payload_data)
                    else:
                        return {"messages": [AIMessage(content=NO_MATCHING_RECORDS_RESPONSE)]}

                elif isinstance(raw_data, list) and len(raw_data) > 0:
                    # Backward compatibility for legacy non-envelope tool payloads.
                    micro_snapshot = raw_data[:3]
                    database_records_text = json.dumps(micro_snapshot, default=str)
                elif isinstance(raw_data, list) and len(raw_data) == 0:
                    return {"messages": [AIMessage(content=NO_MATCHING_RECORDS_RESPONSE)]}
                elif isinstance(raw_data, dict) and "error" in raw_data:
                    return {"messages": [AIMessage(content=TOOL_EXECUTION_ERROR_RESPONSE)]}
                else:
                    database_records_text = str(raw_data)
            except Exception:
                database_records_text = str(msg.content)[:1000] # Safe clipping guard

    if not database_records_text:
        debug_msg = (
            "No fresh ToolMessage found after the latest HumanMessage. "
            "Skipping synthesis to prevent stale answer generation."
        )
        print("\n🛑" + "─"*27 + " SYNTHESIS DATA GUARD ACTIVATED " + "─"*27, file=sys.stderr)
        print(debug_msg, file=sys.stderr)
        print("─"*100 + "\n", file=sys.stderr)
        return {"messages": [AIMessage(content="I could not retrieve fresh database results for this turn. Please retry your request.")]}
                
    # Re-inject the ultra-compact, compressed database token results footprint cleanly
    compressed_rows_context = f"\n[SECURE REPLICA QUERY RESULTS SNAPSHOT]:\n{database_records_text}\n"
    
    synthesis_guideline = (
        "You are a helpful data analyst summarizing information for a site manager.\n"
        "Your task is to analyze the provided raw replica query results snapshot below and translate it into a friendly conversational sentence.\n"
        "Answer the manager's initial prompt directly, using plain text only. Do not invoke tools. Do not mention code keys or table aliases.\n\n"
        f"OPERATOR INITIAL PROMPT: '{user_initial_prompt}'\n"
        f"{compressed_rows_context}"
    )
    
    # 🚀 ENFORCE A FLAT, CLEAN TWO-MESSAGE SLATE
    # By eliminating previous incomplete tool_calls messages, Nova can no longer get confused.
    # It reads a pure text summary instruction, ensuring maximum response reliability! [▲]
    clean_synthesis_track = [
        SystemMessage(content=synthesis_guideline),
        HumanMessage(content=f"Please answer my initial question: '{user_initial_prompt}' based on the snapshot values provided.")
    ]

    # print("\n🧾" + "─"*31 + " SYNTHESIS MODEL INPUT PAYLOAD " + "─"*31, file=sys.stderr)
    # print(synthesis_guideline, file=sys.stderr)
    # print(f"User synthesis prompt: Please answer my initial question: '{user_initial_prompt}' based on the snapshot values provided.", file=sys.stderr)
    # print("─"*100 + "\n", file=sys.stderr)
    
    # Invoke your raw, un-bound client model instance safely with no tool metadata attached
    conversational_reply = _llm().invoke(clean_synthesis_track)

    # print("\n🧠" + "─"*30 + " SYNTHESIS MODEL RAW OUTPUT " + "─"*31, file=sys.stderr)
    # print(f"Raw synthesis content: {conversational_reply.content}", file=sys.stderr)
    # print("─"*100 + "\n", file=sys.stderr)
    
    # ─── EXTRACTION STEP B: EXCEPTION-PROOF STRING CONVERSION ─── [▲]
    raw_response_content = conversational_reply.content
    flat_text_extracted = ""
    if isinstance(raw_response_content, list):
        for block in raw_response_content:
            if isinstance(block, dict) and "text" in block:
                flat_text_extracted += block["text"]
            elif isinstance(block, str):
                flat_text_extracted += block
    else:
        flat_text_extracted = str(raw_response_content)
        
    # Wipe away any trailing internal XML brackets or hidden thinking tags seamlessly
    clean_narrative_sentence = re.sub(r'<result>.*?</result>', '', flat_text_extracted, flags=re.DOTALL)
    clean_narrative_sentence = re.sub(r'<thinking>.*?</thinking>', '', clean_narrative_sentence, flags=re.DOTALL)
    clean_narrative_sentence = clean_narrative_sentence.strip()
    
    # Re-assign the clean plain-text string back onto the LangGraph state message payload block
    conversational_reply.content = clean_narrative_sentence
    
    # Print the clean narrative text answer directly to your console pane
    print("\n" + "🏁" + "─"*32 + " FINAL CONVERSATIONAL AGENT DIALOGUE " + "─"*31, file=sys.stderr)
    print(f"🤖 BEDROCK AGENT ANSWER:\n{conversational_reply.content}", file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)
    
    # Dynamic Token Telemetry Extraction
    usage_info = getattr(conversational_reply, "usage_metadata", {}) or {}
    if not usage_info and hasattr(conversational_reply, "response_metadata"):
        usage_info = conversational_reply.response_metadata.get("usage", {}) or {}
        
    print("📊" + "─"*35 + " STREAM TELEMETRY METRICS " + "─"*35, file=sys.stderr)
    print(f"   📥 Input Tokens Scanned  : {usage_info.get('input_tokens', 'N/A')}", file=sys.stderr)
    print(f"   📤 Output Tokens Written : {usage_info.get('output_tokens', 'N/A')}", file=sys.stderr)
    print(f"   📊 Combined Request Toll : {usage_info.get('total_tokens', 'N/A')} tokens consumed.", file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)
    
    return {
        "messages": [conversational_reply],
        "pending_user_query": None,
        "awaiting_site_selection": False
    }


#=============================================================================
# 6. DYNAMIC PRE-ROUTING HIERARCHICAL SHIELD EDGE
# =============================================================================
def route_next_node(state: AgentState):
    """
    Production Intent Gatekeeper.
    Strictly forces wait-state pauses the instant an interactive menu is displayed.
    """
    messages = state["messages"]
    if not messages:
        return END
        
    last_message = messages[-1]
    
    # Extract structural state cache boundaries
    jwt_company_fence = state.get("company_id", []) or []
    active_company_cache = state.get("active_session_company", []) or []
    jwt_site_fence = state.get("site_id", []) or []
    active_site_cache = state.get("active_session_site", []) or []
    discovered_sites = state.get("discovered_site_ids", []) or []
    awaiting_site_selection = bool(state.get("awaiting_site_selection", False))
    pending_user_query = state.get("pending_user_query")
    
    # ─── 🚀 FIXED PERMANENTLY: ACTIVE WAIT-STATE TERMINATOR ─── [▲]
    # If the last message written to history is a text selection menu generated by 
    # the graph, TERMINATE the execution pass immediately with END! 
    # This stops the graph from sliding forward into conversational text generation!
    if last_message.type == "ai" and not hasattr(last_message, "tool_calls"):
        flat_text = str(last_message.content)
        if "MULTIPLE FACILITY SITES" in flat_text or "MULTIPLE CORPORATE ACCOUNTS" in flat_text:
            print("\n🛑 ROUTER: Selection menu displayed. Pausing state graph execution turn cleanly.", file=sys.stderr)
            return END
    # ──────────────────────────────────────────────────────────

    # Step 1: Hard stop guards for missing authorization context
    if not jwt_company_fence:
        return "missing_company_scope"

    if not jwt_site_fence:
        return "missing_site_scope"

    # Step 2: Tool Calling Trigger
    has_active_tool_call = False
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        has_active_tool_call = True
    elif isinstance(getattr(last_message, "content", None), list):
        for block in last_message.content:
            if isinstance(block, dict) and ("tool_use" in block or "toolCall" in block or "tool_calls" in block):
                has_active_tool_call = True
                break
    elif hasattr(last_message, "additional_kwargs") and "tool_calls" in last_message.additional_kwargs:
        has_active_tool_call = True

    if has_active_tool_call:
        return "execute_tools"

    # Step 2.5: Orchestrator returned no tool call, route to deterministic recovery.
    if last_message.type == "ai" and not has_active_tool_call:
        flat_text = str(last_message.content)
        if "MULTIPLE FACILITY SITES" not in flat_text and "MULTIPLE CORPORATE ACCOUNTS" not in flat_text:
            return "recover_no_tool_after_orchestrator"
        
    # Step 3: If multiple sites and no active selection, show selection menu.
    if len(jwt_site_fence) > 1 and not active_site_cache and not awaiting_site_selection:
        return "trigger_site_selection"

    # Step 4: Resume selection turn through execute_tools only when waiting.
    if last_message.type == "human" and awaiting_site_selection:
        flat_text = str(last_message.content).lower().strip()
        has_all_keyword = bool(re.search(r'\ball\b', flat_text))
        has_site_digit = bool(re.findall(r'\b\d+\b', flat_text))
        if has_all_keyword or has_site_digit:
            return "execute_tools"

    # Step 5: Chitchat Bypass
    clean_prompt = " ".join(str(last_message.content).lower().split())
    if clean_prompt in {"what is your name", "who are you", "hello", "hi", "hey"}:
        return "conversational_synthesis"

    # Step 6: Company disambiguation (if enabled by session data)
    if len(jwt_company_fence) > 1 and not active_company_cache:
        return "trigger_company_selection"

    # Step 7: Once constraints are satisfied, run orchestration for query turns.
    if last_message.type == "human" and not has_active_tool_call:
        return "bedrock_orchestrator"

    # Step 8: If tool step has no responses but a pending query exists, continue orchestration.
    if pending_user_query and not has_active_tool_call:
        if last_message.type == "human":
            return "bedrock_orchestrator"
        return "conversational_synthesis"

    # Step 9: Final fallback
    return "conversational_synthesis"




# =============================================================================
# 6. ASSEMBLE THE COMPLETE PRODUCTION WORKFLOW STATE MACHINE
# =============================================================================
# =============================================================================
# 7. ASSEMBLE THE COMPLETE PRODUCTION STATE MACHINE WORKFLOW TOPOLOGY
# =============================================================================
workflow = StateGraph(AgentState)

# Register active workspace nodes
workflow.add_node("bedrock_orchestrator", call_bedrock_orchestrator)
workflow.add_node("execute_tools", execute_graph_tools)
workflow.add_node("trigger_company_selection", compile_company_selection_menu)
workflow.add_node("trigger_site_selection", compile_site_selection_menu)
workflow.add_node("conversational_synthesis", generate_conversational_response)
workflow.add_node("missing_company_scope", missing_company_scope_response)
workflow.add_node("missing_site_scope", missing_site_scope_response)
workflow.add_node("recover_no_tool_after_orchestrator", recover_no_tool_after_orchestrator)

# ─── FIXED PERMANENTLY: SYNCHRONIZED START GATE CONDITIONAL DICTIONARY MAP ───
# Added execute_tools to allow the graph to process user menu selection inputs instantly! [🔒]
workflow.add_conditional_edges(
    START,
    route_next_node,
    {
        "trigger_company_selection": "trigger_company_selection",
        "trigger_site_selection": "trigger_site_selection",
        "bedrock_orchestrator": "bedrock_orchestrator",
        "conversational_synthesis": "conversational_synthesis",
        "missing_company_scope": "missing_company_scope",
        "missing_site_scope": "missing_site_scope",
        "recover_no_tool_after_orchestrator": "recover_no_tool_after_orchestrator",
        # 🚀 THE CRITICAL MISSING LINK CHANNEL:
        "execute_tools": "execute_tools",
        END: END
    }
)

# Step 2: Route paths out of the orchestrator node
workflow.add_conditional_edges(
    "bedrock_orchestrator",
    route_next_node,
    {
        "execute_tools": "execute_tools",
        "recover_no_tool_after_orchestrator": "recover_no_tool_after_orchestrator",
        "conversational_synthesis": "conversational_synthesis",
        "missing_company_scope": "missing_company_scope",
        "missing_site_scope": "missing_site_scope",
        END: END
    }
)

# Step 3: Route paths out of the database tool node
workflow.add_conditional_edges(
    "execute_tools",
    route_next_node,
    {
        "trigger_site_selection": "trigger_site_selection",
        "trigger_company_selection": "trigger_company_selection",
        "bedrock_orchestrator": "bedrock_orchestrator",
        "recover_no_tool_after_orchestrator": "recover_no_tool_after_orchestrator",
        "conversational_synthesis": "conversational_synthesis",
        "missing_company_scope": "missing_company_scope",
        "missing_site_scope": "missing_site_scope",
        "execute_tools": "execute_tools",
        END: END
    }
)

# Hard-wired static termination edges for your wait-state menus
workflow.add_edge("trigger_company_selection", END)
workflow.add_edge("trigger_site_selection", END)
workflow.add_edge("conversational_synthesis", END)
workflow.add_edge("missing_company_scope", END)
workflow.add_edge("missing_site_scope", END)
workflow.add_edge("recover_no_tool_after_orchestrator", END)

# Compile into an executable ready-to-run state machine application object
agent_brain_app = workflow.compile()


# =============================================================================
# 7. LOCAL PLAYGROUND TESTING MATRIX CONTROL CENTER (HARDENED INTERACTIVE LOOP)
# =============================================================================
if __name__ == "__main__":
    # Ensure your dynamic metadata catalog is fully initialized before booting your runner loop
    data_retrieval_engine.load_database_schema_config(json_schema_absolute_path)
    
    print("\n" + "═"*80)
    print("🔬 INITIALIZING LIVE SECURE MULTI-TURN TERMINAL LOOP FOR AMAZON NOVA")
    print("═"*80)
    print("📋 SIMULATING SECURED INGEST ENVELOPE PRIVILEGES...")
    
    mock_jwt_company_fence = [1000245] #
    mock_jwt_site_fence = [2223399,2223449] # 2223362,2223395
    
    print(f"   - Company Privilege Fence Scope : {mock_jwt_company_fence}")
    print(f"   - Site Facility Privilege Scope  : {mock_jwt_site_fence}")
    print("💡 SYSTEM ACTIONS AVAILABLE: Type 'clear session' to flush, or 'exit' to quit.\n")
    print("─"*80)

    # Initialize your rolling multi-turn tracking state dictionary
    session_rolling_state = {
        "messages": [],
        "user_id": 1032127,
        "company_id": mock_jwt_company_fence,
        "site_id": mock_jwt_site_fence,
        "active_session_company": [], # Starts empty to test your hierarchy gates
        "active_session_site": [],    # Starts empty to test your hierarchy gates
        "discovered_company_ids": [],
        "discovered_site_ids": [],
        "metadata_names_map": {},
        "pending_user_query": None,
        "awaiting_site_selection": False
    }

    # Start the persistent interactive command line loop
   # agent_graph.py -> Inside your __main__ block loop at the absolute bottom

    # Start the persistent interactive command line loop
    while True:
        try:
            # Capture the manager's live text prompt from the terminal shell entry lane
            user_raw_input = input("\n👤 ENTER YOUR PROMPT: ").strip()
            
            if not user_raw_input:
                continue
                
            if user_raw_input.lower() in ["exit", "quit", "q"]:
                print("\n👋 Terminal loop terminated cleanly. Exiting workspace context.\n")
                break

            # ─── FIXED PERMANENTLY: SESSION PURGE EXPLICIT TRIGGER ─── [🔒]
            if user_raw_input.lower() in ["clear session", "clear", "reset"]:
                print("\n🔄" + "─"*32 + " SESSION CACHE PURGE EXECUTED " + "─"*32, file=sys.stderr)
                session_rolling_state = {
                    "messages": [],
                    "user_id": 1032127,
                    "company_id": mock_jwt_company_fence,
                    "site_id": mock_jwt_site_fence,
                    "active_session_company": [],
                    "active_session_site": [],
                    "discovered_company_ids": [],
                    "discovered_site_ids": [],
                    "metadata_names_map": {},
                    "pending_user_query": None,
                    "awaiting_site_selection": False
                }
                print("🔄 Context memory cleared! Restored to broad portfolio view.\n")
                continue

            if user_raw_input.lower() in ["no company", "simulate no company"]:
                session_rolling_state["company_id"] = []
                session_rolling_state["active_session_company"] = []
                session_rolling_state["pending_user_query"] = None
                session_rolling_state["awaiting_site_selection"] = False
                print("\n🧪 Local test mode: company scope cleared for this session.")
                continue

            if user_raw_input.lower() in ["restore company", "simulate company"]:
                session_rolling_state["company_id"] = list(mock_jwt_company_fence)
                print("\n🧪 Local test mode: company scope restored.")
                continue

            if user_raw_input.lower() in ["no site", "simulate no site"]:
                session_rolling_state["site_id"] = []
                session_rolling_state["active_session_site"] = []
                session_rolling_state["pending_user_query"] = None
                session_rolling_state["awaiting_site_selection"] = False
                print("\n🧪 Local test mode: site scope cleared for this session.")
                continue

            if user_raw_input.lower() in ["restore site", "simulate site"]:
                session_rolling_state["site_id"] = list(mock_jwt_site_fence)
                session_rolling_state["active_session_site"] = []
                session_rolling_state["pending_user_query"] = None
                session_rolling_state["awaiting_site_selection"] = False
                print("\n🧪 Local test mode: site scope restored.")
                continue

            if user_raw_input.lower() in ["clear active site", "simulate clear active site"]:
                session_rolling_state["active_session_site"] = []
                session_rolling_state["awaiting_site_selection"] = False
                session_rolling_state["pending_user_query"] = None
                print("\n🧪 Local test mode: active site selection cache cleared.")
                continue

            # ─── 🚀 FIXED PERMANENTLY: CONTEXT APPEND TRACKING ─── [🔒]
            # Instead of resetting the array block with '=' every turn, we use '.append()'
            # This maintains your complete multi-turn conversational history pipeline!
            session_rolling_state["messages"].append(HumanMessage(content=user_raw_input))
            
            # Execute the compiled LangGraph workflow state machine using the rolling memory logs [🔒]
            updated_state_output = agent_brain_app.invoke(session_rolling_state)

            # ─── CRITICAL STATE PERSISTENCE CROSSOVER BRIDGE ───
            # Preserve full running history by appending only newly emitted messages.
            new_messages = updated_state_output.get("messages", []) or []
            if new_messages:
                session_rolling_state["messages"].extend(new_messages)
            
            # Synchronize configuration parameter overrides [🔒]
            session_rolling_state["active_session_company"] = updated_state_output.get("active_session_company", []) or []
            session_rolling_state["active_session_site"] = updated_state_output.get("active_session_site", []) or []
            session_rolling_state["discovered_site_ids"] = updated_state_output.get("discovered_site_ids", []) or []
            session_rolling_state["discovered_company_ids"] = updated_state_output.get("discovered_company_ids", []) or []
            session_rolling_state["metadata_names_map"] = updated_state_output.get("metadata_names_map", {}) or {}
            session_rolling_state["pending_user_query"] = updated_state_output.get("pending_user_query")
            session_rolling_state["awaiting_site_selection"] = bool(updated_state_output.get("awaiting_site_selection", False))

            if not new_messages and session_rolling_state.get("awaiting_site_selection"):
                print("\n⌛ Waiting for site selection. Enter a site id or ALL.")
            
        except Exception as loop_fault:
            print(f"\n💥 RUNTIME FAULT INTERCEPTED: {str(loop_fault)}", file=sys.stderr)
            import traceback
            traceback.print_exc()
