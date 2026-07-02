# agent_graph.py
import json
import os
import sys
import re
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
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage
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
    
    # ─── EXTRACTION STEP E: SECURED MEMORY CONTEXT MATRIX ROUTING ───
    llm_with_tools = _llm().bind_tools([execute_storage_query])
    
    # 🚀 FIXED: We build a temporary list payload strictly for this cloud call turn.
    # This prevents duplicate history logs from stacking in LangGraph memory states! [▲]
    clean_runtime_track = [SystemMessage(content=system_instruction)] + list(messages)
    
    # Fire the AWS Bedrock client using the lightweight instruction array
    response_message = llm_with_tools.invoke(clean_runtime_track)
    
    # 🚀 SAFE RETURN: Return ONLY the single new message token object [▲]
    return {"messages": [response_message]}



# =============================================================================
# 5. LIVE MCP TOOL EXECUTION AND DATA RETRIEVAL WORKFLOW NODES
# =============================================================================
def execute_graph_tools(state: AgentState):
    """Secure runtime bridge node that validates boundaries and executes your dynamic MCP joins."""
    import sys
    messages = state["messages"]
    last_message = messages[-1]
    
    # Reassemble your multi-tenant security context directly from your system state memory variables
    computed_session_context = {
        "company_id": state.get("company_id"),
        "site_id": state.get("site_id"),
        "user_id": state.get("user_id")
    }
    
    tool_responses = []
    for tool_call in last_message.tool_calls:
        # Check against your abstract data gateway identifier
        if tool_call["name"] == "execute_storage_query":
            args = tool_call["args"]
            
            # Print outgoing JSON arguments array metrics cleanly to console terminal
            print("\n" + "🤖" + "─"*30 + " AMAZON NOVA INTERPOLATED TOOL PAYLOAD " + "─"*30, file=sys.stderr)
            print(json.dumps(args, indent=2), file=sys.stderr)
            print("─"*100 + "\n", file=sys.stderr)
            
            # Cleanly split the flat text string tokens back into standard list arrays natively
            raw_subjects_str = args.get("target_subjects", "")
            raw_filters_str = args.get("semantic_filters", "")
            
            parsed_subjects = [s.strip() for s in raw_subjects_str.split(",") if s.strip()] if raw_subjects_str else []
            parsed_filters = [f.strip() for f in raw_filters_str.split(",") if f.strip()] if raw_filters_str else []
            
            try:
                # ─── MULTI-INTENT SPINNING TREE REPLICATOR RUNTIME ───
                # Your Spanning Tree Pathfinder reads the intents list dynamically on the fly,
                # maps session variables, calculates shortest join sequences, and outputs valid SQL
                db_rows_matrix = data_retrieval_engine.run_compiled_mcp_query(
                    subjects=parsed_subjects,
                    intent_type=args.get("intent_type", "DATA_RETRIEVAL"),
                    session_context=computed_session_context, # Clean context injection handled perfectly!
                    semantic_filters=parsed_filters,
                    aggregation_column=args.get("aggregation_column"),
                    search_keyword=args.get("search_keyword")
                )

                  # ─── SUCCESS TRACK LOGGING ───
                print("\n" + "📝" + "─"*32 + " DYNAMICALLY GENERATED SQL COMMAND " + "─"*31, file=sys.stderr)
                # Check your data engine's exact dictionary structure output keys
                if isinstance(db_rows_matrix, dict) and "compiled_sql" in db_rows_matrix:
                    print(db_rows_matrix["compiled_sql"], file=sys.stderr)
                elif hasattr(data_retrieval_engine, "LAST_COMPILED_SQL"):
                    # Fallback check to see if your module file caches the latest query text globally
                    print(getattr(data_retrieval_engine, "LAST_COMPILED_SQL"), file=sys.stderr)
                else:
                    print(f"✅ SQL compiled and dispatched successfully for targets list: {parsed_subjects}", file=sys.stderr)
                print("─"*100 + "\n", file=sys.stderr)
                
                string_payload = json.dumps(db_rows_matrix, default=str)
                
            except Exception as query_fault:
                # ─── FAULT TRACK LOGGING (CAPTURES SILENT COMPILER DROPS) ───
                print("\n" + "💥" + "─"*32 + " CORE DATABASE COMPILER RUNTIME FAULT " + "─"*30, file=sys.stderr)
                print(f"Reason: {str(query_fault)}", file=sys.stderr)
                print(f"Active targets sent during drop: {parsed_subjects}", file=sys.stderr)
                print(f"Enforced session filters on drop: {computed_session_context}", file=sys.stderr)
                print("─"*100 + "\n", file=sys.stderr)
                
                string_payload = json.dumps({"error": f"Dynamic query pathfinder execution dropped: {str(query_fault)}"})                
            tool_responses.append(
                ToolMessage(
                    content=string_payload,
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"]
                )
            )
            
    return {"messages": tool_responses}


# agent_graph.py (Update your conversational response synthesis node block)

def generate_conversational_response(state: AgentState):
    """Synthesizes raw database JSON row data arrays back into elegant plain sentences."""
   
    messages = state["messages"]
    
    # ─── FIXED: TRUNCATE AND COMPRESS CONTEXT WINDOW TIMELINE ───
    # We inspect the history and isolate the giant tool message text data cells [▲]
    clean_historical_track = []
    database_records_text = ""
    
    for msg in messages:
        if msg.type == "tool":
            # Isolate the heavy raw rows database payload text string cell [▲]
            try:
                raw_data = json.loads(msg.content)
                # Keep only a micro-subset snapshot of the records for the final text summary turn!
                # This compresses 33,000+ tokens of repetitive rows text cells down to <100 tokens! [▲]
                if isinstance(raw_data, list) and len(raw_data) > 0:
                    # Pick just the first 3 relevant row items to prove the structural values
                    micro_snapshot = raw_data[:3]
                    database_records_text = json.dumps(micro_snapshot, default=str)
                else:
                    database_records_text = str(raw_data)
            except Exception:
                database_records_text = str(msg.content)[:1000] # Safe fallback clipping guard rail [▲]
        else:
            # Keep clean system message instructions or human query entry tokens intact
            clean_historical_track.append(msg)
            
    # Re-inject the ultra-compact, compressed database token results footprint cleanly [▲]
    compressed_rows_context = f"\n[SECURE REPLICA QUERY RESULTS SNAPSHOT]:\n{database_records_text}\n"
    
    synthesis_guideline = (
        "SYSTEM DIRECTIVE: The operator's requested database query results have executed successfully.\n"
        "Analyze the provided raw rows dataset array text content found below in the compressed context.\n"
        "Summarize the findings and answer the manager's initial prompt directly in a friendly conversational sentence.\n"
        "Do not invoke any tools. Do not mention table aliases or SQL keys. Output raw plain text only.\n\n"
        f"{compressed_rows_context}"
    )
    
    # 🚀 SECURED CONTEXT WINDOW TRACK: Ingest prompt footprint size drops to ~800 tokens!
    clean_synthesis_track = clean_historical_track + [SystemMessage(content=synthesis_guideline)]
    
    # Call a pure _llm() instance with NO tools bound to stop infinite loops natively
    conversational_reply = _llm().invoke(clean_synthesis_track)
    
    clean_narrative_sentence = re.sub(r'<result>.*?</result>', '', conversational_reply.content, flags=re.DOTALL)
    clean_narrative_sentence = clean_narrative_sentence.strip()
    
    # Update the reply object content text field natively so the downstream graph shares the clean string [🔒]
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
    
    return {"messages": [conversational_reply]}





def route_next_node(state: AgentState):
    """Inspects messages to decide whether to trigger tools or close the state loop."""
    messages = state["messages"]
    
    if not messages:
        return END
    
    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_tools"
    return END


# =============================================================================
# 6. ASSEMBLE THE COMPLETE PRODUCTION WORKFLOW STATE MACHINE
# =============================================================================
workflow = StateGraph(AgentState)

# Register active workspace operational nodes
workflow.add_node("bedrock_orchestrator", call_bedrock_orchestrator)
workflow.add_node("execute_tools", execute_graph_tools)
workflow.add_node("conversational_synthesis", generate_conversational_response)

# Attach graph entry connections
workflow.add_edge(START, "bedrock_orchestrator")

# Hook routing conditional rule boundaries
workflow.add_conditional_edges(
    "bedrock_orchestrator",
    route_next_node,
    {
        "execute_tools": "execute_tools",
        END: END
    }
)

# Pipe data rows into synthesis before completion loops terminate
workflow.add_edge("execute_tools", "conversational_synthesis")
workflow.add_edge("conversational_synthesis", END)

# Compile into a ready-to-run state machine application object
agent_brain_app = workflow.compile()

#=============================================================================
# --- LOCAL PRODUCTION PLAYGROUND TESTING MATRIX CONTROL CENTER ---
#=============================================================================
if __name__ == "__main__":
    print("\n" + "═"*80)
    print("🔬 INITIALIZING 100% NON-HARDCODED METADATA TUNER FOR AMAZON NOVA")
    print("═"*80)
    # ─── CHANGE THE PROMPT HERE TO SCROLL THROUGH ALL INTENT SCENARIOS NATIVELY  2223399───
    #test_user_prompt = "what is the status of unit LA879 ?"
    #test_user_prompt = "What is the unit status for Service Unit 2256149?"
    # test_user_prompt = "rental state for user Johnny?"
    #test_user_prompt = "what is the email of the user who is assigned to the unit LA879 / 2223399?"
    #test_user_prompt = "How many open units?"
    test_user_prompt = "What is the Weekdays open timing for site Sugar Hill 1?"

    initial_graph_state = {"messages": [HumanMessage(content=test_user_prompt)],
                           "user_id": None,
                           "site_id":[2223362],
                           "company_id": None}
    print(f"💬 MANAGER INPUT PROMPT: '{test_user_prompt}'")
    print(f"🔒 PRIVILEGES ENFORCED: User {initial_graph_state['user_id']} | Sites {initial_graph_state['site_id']}\n")
    try:
        agent_brain_app.invoke(initial_graph_state)
    except Exception as e:
        print(f"\n💥 RUNTIME DROPPED: {str(e)}\n")