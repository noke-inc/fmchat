# agent_graph.py
import json
import os
import sys
from typing import TypedDict, Annotated, Sequence, Optional, List,Literal
from enum import Enum
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
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
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


# =============================================================================
# 2. SHARED CONVERSATIONAL GRAPH STATE MATRIX
# =============================================================================
class AgentState(TypedDict):
    """Tracks conversational stream log array alongside system primitives."""
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int
    site_id: Optional[list[int]]
    company_id: Optional[int]


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
    """The driving LLM node that pre-identifies schemas and forces Nova into strict token extraction."""
    from pydantic import BaseModel, Field, create_model
    from enum import Enum
    import re
    
    messages = state["messages"]
    last_human_prompt = messages[-1].content.lower().strip()
    
    # Clean out trailing punctuation symbols smoothly (e.g. converting "site?" natively to "site") [🔒]
    clean_prompt_normalized = re.sub(r'[^\w\s]', ' ', last_human_prompt)
    # Ensure inner white spaces are compacted uniformly
    clean_prompt_normalized = " ".join(clean_prompt_normalized.split())
    
    # Create word tokens for fine-grained column mapping sweeps [🔒]
    prompt_words = set(clean_prompt_normalized.split())
          
    # =============================================================================
    # ─── EXTRACTION STEP A: LOCAL DUAL-LAYER METADATA DISCOVERY (UPGRADED) ───
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
        # Track if this entity gets activated either by its table name OR its column keywords
        is_entity_active = False
        
        # Track 1: Sweep Top-Level Table Aliases
        table_aliases_pool = entity_meta.get("aliases", []) + [entity_name]
        clean_table_aliases = [str(alias).lower().strip() for alias in table_aliases_pool]
        
        for alias in clean_table_aliases:
            escaped_alias = re.escape(alias)
            if re.search(rf'\b{escaped_alias}\b', clean_prompt_normalized):
                is_entity_active = True
                break
        
        # Track 2: GLOBAL SWEEP - Scan inside column metadata and synonyms arrays [🔒]
        # Even if "unit" isn't typed, matching "rental state" pulls the unit table into view!
        allowed_cols_dict = entity_meta.get("allowed_columns", {})
        column_metadata_dict = entity_meta.get("column_metadata", {})
        
        active_fields_this_table = []
        
        for col_name, col_props in allowed_cols_dict.items():
            # Extract configured aliases for this specific property field column
            col_meta_block = column_metadata_dict.get(col_name, {})
            col_aliases = col_meta_block.get("aliases", []) or []
            
            # Extract child enum values (like checking if user typed "vacant", "active", etc.)
            enum_synonyms = []
            for enum_key, enum_list in col_meta_block.get("enum_map", {}).items():
                enum_synonyms.extend(enum_list)
                
            # Flatten all possible structural names for this specific database column cell
            col_pool = (
                {str(ca).lower().strip() for ca in col_aliases} | 
                {col_name.lower()} | 
                {str(es).lower().strip() for es in enum_synonyms}
            )
            # Match condition: Always keep tenant isolation keys, or match column names/synonyms
            if col_name in system_isolation_keys or any(re.search(rf'\b{re.escape(c)}\b', clean_prompt_normalized) for c in col_pool):
                active_fields_this_table.append(f"  - Field: Table/Concept '{entity_name}' property column: '{col_name}' (Type: {col_props.get('type')})")
                # Found a valid column synonym mentioned in the prompt! Activate the parent table!
                if col_name not in system_isolation_keys:
                    is_entity_active = True
                    
        # If either Track 1 or Track 2 passed, register the table and append its active fields
        if is_entity_active:
            if entity_name not in discovered_entities:
                discovered_entities.append(entity_name)
                
            # Guarantee that every discovered entity retains its core relational identity fields 'id' or 'name'
            for identity_col in ["id", "name"]:
                if identity_col in allowed_cols_dict:
                    identity_str = f"  - Field: Table/Concept '{entity_name}' property column: '{identity_col}' (Type: {allowed_cols_dict[identity_col].get('type')})"
                    if identity_str not in pruned_columns_vocabulary:
                        pruned_columns_vocabulary.append(identity_str)
                        
            # Append all specific fields that matched the user's prompt text
            for active_field_str in active_fields_this_table:
                if active_field_str not in pruned_columns_vocabulary:
                    pruned_columns_vocabulary.append(active_field_str)


    # ─── EXTRACTION STEP B: DYNAMIC FACT TABLE SELECTION ───
    fact_table_entity = discovered_entities if discovered_entities else "unresolved"
    max_relationship_density = -1
    for candidate in discovered_entities:
        relationship_count = len(active_catalog["entities"].get(candidate, {}).get("relationships", {}))
        if relationship_count > max_relationship_density:
            max_relationship_density = relationship_count
            fact_table_entity = candidate

    vocabulary_text_block = "\n".join(pruned_columns_vocabulary)

    print("\n" + "🔍" + "─"*30 + " 100% DATA-DRIVEN PRE-IDENTIFICATION SWEEP " + "─"*30, file=sys.stderr)
    print(f"📁 Dynamically Discovered Intents (Entities): {discovered_entities}", file=sys.stderr)
    print(f"📊 Mathematically Derived Fact Table Anchor: '{fact_table_entity}'", file=sys.stderr)
    print("─"*104 + "\n", file=sys.stderr)

    # =============================================================================
    # ─── EXTRACTION STEP C: MANUFACTURE STRICT DYNAMIC EXTRACTION SHIELD ───
    # =============================================================================
    class StrictIntentType(str, Enum):
        DATA_AGGREGATION = "DATA_AGGREGATION"
        DATA_RETRIEVAL = "DATA_RETRIEVAL"
    
        # agent_graph.py (Update the search_keyword field inside Extraction Step C)
    
    expected_sequence_token = ", ".join(discovered_entities)
    
    class StrictIntentType(str, Enum):
        DATA_AGGREGATION = "DATA_AGGREGATION"
        DATA_RETRIEVAL = "DATA_RETRIEVAL"
    
    # Dynamically compile an ironclad schema payload contract on the fly
    DynamicNovaArgsSchema = create_model(
        "DynamicNovaArgsSchema",
        intent_type=(StrictIntentType, Field(
            ..., 
            description="Operational track target. Use 'DATA_AGGREGATION' strictly for math/counts. Use 'DATA_RETRIEVAL' for details grids."
        )),
        
        # ─── THE UNBREAKABLE LITERAL FENCE: Enforces exact, untruncated string mapping! ───
        target_subjects=(Literal[expected_sequence_token], Field(
            ..., 
            description=f"The active table targets required for this query. You MUST choose exactly the string value: '{expected_sequence_token}'."
        )),
        
        semantic_filters=(Optional[str], Field(
            None, 
            description="Comma-separated string listing modifier status terms or math actions (e.g. 'count, active')."
        )),
        search_keyword=(Optional[str], Field(
            None, 
            description=(
                "Wildcard search text matching specific names, descriptions, or tracking labels. "
                "CRITICAL PARALLEL EXECUTION GUARD: You are strictly forbidden from calling this tool multiple times. "
                "If the operator mentions multiple entities or locations, you MUST combine them into a single comma-separated string."
            )
        )),
        aggregation_column=(Optional[str], Field(
            None, 
            description="The numerical metric property field required if running calculation total functions."
        ))
    )

    # Re-declare the local tool signature mapping to bind the rigid schema contract natively
    @tool(args_schema=DynamicNovaArgsSchema)
    def execute_storage_query(
        intent_type: StrictIntentType, 
        target_subjects: str,  # Keeps tool parameter flat for safe LangChain serialization
        semantic_filters: Optional[str] = None, 
        search_keyword: Optional[str] = None, 
        aggregation_column: Optional[str] = None
    ) -> str:
        """Unified enterprise read-only data gateway portal for executing pre-identified system lookups."""
        raise NotImplementedError()
    # =============================================================================
    # ─── EXTRACTION STEP D: CONTEXT-LOCKED TEXT BLUEPRINT INJECTION ───
    # =============================================================================
    system_instruction = (
        "You are the data parameter extraction gateway for the enterprise information infrastructure.\n"
        "Your sole task is to identify requested concepts and isolate text filters.\n"
        "You MUST choose valid options matching the provided schema fields.\n\n"
        "🔒 ENTERPRISE BOUNDARY PROTECTION SHIELD:\n"
        "We have analyzed our data catalog and pre-identified your relevant schema rules locally.\n"
        f"The primary driver Fact Table for this request path is computed as: '{fact_table_entity}'\n"
        "The only valid system database configurations related to the operator's current request are:\n"
        f"{vocabulary_text_block}\n\n"
        "CRITICAL EXTRACTION CONSTRAINTS:\n"
        f"1. Inside the 'target_subjects' string field, you MUST pass a comma-separated list choosing exclusively from this precise list: {discovered_entities}\n"
        "   - Never invent concepts. If the question asks about users and site, write exactly: 'site, user'\n"
        "2. Inside the 'semantic_filters' string field, pass your operational modifiers as a comma-separated string (e.g. 'count, active').\n"
        "3. Route specific proper human names, emails, unique labels, or identifier codes exclusively to 'search_keyword'.\n"
        "4. Do not invent non-existent column fields. Do not hypothesize parameters outside the provided context block."
    )
    # ─── ADD THIS PRINT BLOCK RIGHT HERE TO SEE THE LIVE OUTGOING LLM REQUEST ───
    print("\n" + "📡" + "─"*32 + " OUTGOING AMAZON NOVA SYSTEM INGEST " + "─"*32, file=sys.stderr)
    print(system_instruction, file=sys.stderr)
    print(f"💬 Active User Entry Payload: '{messages[-1].content}'", file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)
    # ───────────────────────────────────────────────────────────────────────────
    
    llm_with_tools = _llm().bind_tools([execute_storage_query])
    complete_message_track = [SystemMessage(content=system_instruction)] + list(messages)
    
    response_message = llm_with_tools.invoke(complete_message_track)
    return {"messages": [response_message]}



# agent_graph.py (Update your simulate_terminal_synthesis function block)

def simulate_terminal_synthesis(state: AgentState):
    """Bypasses MCP execution and aggregates conversational outputs for pure tuning inspection."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # Intercept and display the flat parameter payload generated by Amazon Nova
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            print("🤖" + "─"*30 + " AMAZON NOVA INTERPOLATED TOOL PAYLOAD " + "─"*30, file=sys.stderr)
            print(json.dumps(tool_call["args"], indent=2), file=sys.stderr)
            print("─"*100 + "\n", file=sys.stderr)
            
    # ─── FIXED: Dynamic Amazon Nova Token Telemetry Extraction ─── [▲]
    # Nova passes standard dictionary token structures inside 'usage_metadata' natively!
    usage_info = getattr(last_message, "usage_metadata", {}) or {}
    
    # Fallback to response_metadata if usage_metadata is missing
    if not usage_info and hasattr(last_message, "response_metadata"):
        usage_info = last_message.response_metadata.get("usage", {}) or {}
        
    print("📊" + "─"*35 + " STREAM TELEMETRY METRICS " + "─"*35, file=sys.stderr)
    print(f"   📥 Input Tokens Scanned  : {usage_info.get('input_tokens', 'N/A')}", file=sys.stderr)
    print(f"   📤 Output Tokens Written : {usage_info.get('output_tokens', 'N/A')}", file=sys.stderr)
    print(f"   📊 Combined Request Toll : {usage_info.get('total_tokens', 'N/A')} tokens consumed.", file=sys.stderr)
    print("─"*100 + "\n", file=sys.stderr)
    
    return {"messages": []}

#=============================================================================
# 5. ASSEMBLE THE COMPLETE WORKFLOW STATE MACHINE
#=============================================================================
workflow = StateGraph(AgentState)
# Register workflow processing nodes
workflow.add_node("bedrock_orchestrator", call_bedrock_orchestrator)
workflow.add_node("simulate_synthesis", simulate_terminal_synthesis)
# Attach graph entry points
workflow.add_edge(START, "bedrock_orchestrator")
workflow.add_edge("bedrock_orchestrator", "simulate_synthesis")
workflow.add_edge("simulate_synthesis", END)
# Compile into an executable state graph application object
agent_brain_app = workflow.compile()

#=============================================================================
# --- LOCAL PRODUCTION PLAYGROUND TESTING MATRIX CONTROL CENTER ---
#=============================================================================
if __name__ == "__main__":
    print("\n" + "═"*80)
    print("🔬 INITIALIZING 100% NON-HARDCODED METADATA TUNER FOR AMAZON NOVA")
    print("═"*80)
    # ─── CHANGE THE PROMPT HERE TO SCROLL THROUGH ALL INTENT SCENARIOS NATIVELY ───
    #test_user_prompt = "what is the status of unit LA879 ?"
    #test_user_prompt = "What is the unit status for Service Unit 2256149?"
    # test_user_prompt = "rental state for user Johnny?"
    #test_user_prompt = "what is the email of the user who is assigned to the unit LA879?"
    #test_user_prompt = "How many open units?"
    # Inside agent_graph.py -> __main__ block
    test_user_prompt = "What is the monday open timing for site Mateo's House?"

    initial_graph_state = {"messages": [HumanMessage(content=test_user_prompt)],
                           "user_id": None,
                           "site_id":[2223399],
                           "company_id": None}
    print(f"💬 MANAGER INPUT PROMPT: '{test_user_prompt}'")
    print(f"🔒 PRIVILEGES ENFORCED: User {initial_graph_state['user_id']} | Sites {initial_graph_state['site_id']}\n")
    try:
        agent_brain_app.invoke(initial_graph_state)
    except Exception as e:
        print(f"\n💥 RUNTIME DROPPED: {str(e)}\n")