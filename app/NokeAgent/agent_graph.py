# agent_graph.py
import json
import os
import sys
import types
from typing import TypedDict, Annotated, Sequence, Optional
from langchain_aws import ChatBedrock
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from config import BEDROCK_MODEL_ID, BEDROCK_REGION, AGENT_GATEWAY_URL, AGENT_GATEWAY_REGION
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages

from data_retrieval_engine import SCHEMA_CATALOG, load_database_schema_config, run_compiled_mcp_query

# Cache your static JSON configuration catalog matrix on startup
json_schema_absolute_path = os.path.join(
    os.path.dirname(os.path.abspath(run_compiled_mcp_query.__code__.co_filename)), 
    "database_schema.json"
)
load_database_schema_config(json_schema_absolute_path)

# =============================================================================
# 1. SHARED STATE STRUCTURE DEFINITION MATRIX
# =============================================================================
class AgentState(TypedDict):
    """Tracks the conversational memory stream alongside system context parameters."""
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int
    site_id: Optional[list[int]]  # Array list matching your multi-value security needs
    company_id: Optional[int]


# =============================================================================
# 2. THE AWS BEDROCK LLM FACTORY CALL
# =============================================================================
# ── LLM factory ──────────────────────────────────────────────────────────────
def _llm() -> ChatBedrock:
    return ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        region_name=BEDROCK_REGION,
        model_kwargs={"temperature": 0, "max_tokens": 2048},
    )


# =============================================================================
# 3. EXPOSE THE DATABASE COMPILER PORTAL AS A BINDABLE LANGCHAIN TOOL
# =============================================================================
@tool
def execute_storage_query(
    intent_type: str, 
    target_subjects: list[str], 
    semantic_filters: list[str] = None, 
    aggregation_column: str = None, 
    search_keyword: str = None
) -> str:
    """
    Unified read-only data gateway. Invoke this tool whenever the operator 
    requests calculations, text record lookups, counts, or status metrics 
    regarding storage spaces, smart locks, user accounts, roles, or facilities.
    
    CRITICAL PATH PARAMETERS:
    - intent_type: Use 'DATA_AGGREGATION' for math/counts or 'DATA_RETRIEVAL' for details/lists.
    - target_subjects: Connected path sequence list. Allowed core tokens: ['unit', 'user', 'site', 'lock', 'role']. 
      You MUST chain them using 'user' as your middleman bridge (e.g. ['site', 'user', 'role']).
    - semantic_filters: Keyword modifier filters (e.g. ['count', 'vacant', 'active', 'noke volt']).
    - aggregation_column: Mathematical column identifier targeting metric costs/rates (e.g. 'details_price').
    - search_keyword: Raw wildcard search string input (e.g. 'Alex', '733', 'Company Manager').
    """
    raise NotImplementedError("This base tool signature is intercepted dynamically by the Graph node runtime.")


# =============================================================================
# 4. SYSTEM LOGICAL GRAPH NODES (BUILT FROM SCRATCH)
# =============================================================================
def call_bedrock_orchestrator(state: AgentState):
    """The driving LLM node that analyzes prompts and structures tool parameters."""
    messages = state["messages"]
    
    # Compile a clear, context-locked security instruction block
    system_instruction = (
        "You are the centralized analytical interface for the Noke Smart Entry infrastructure.\n"
        "Your only resource for fetching system counts, metrics, and profile listings is 'execute_storage_query'.\n"
        "You MUST construct the 'target_subjects' array as a sequential relational pipeline path. "
        "Pre-validated relationship order strings you must choose from:\n"
        "- Users by permission roles at a location: Use exactly ['site', 'user', 'role']\n"
        "- Hardware locks or firmware codes by facility: Use exactly ['site', 'unit', 'lock']\n"
        "- Smart lock hardware versions linked to customers: Use exactly ['user', 'unit', 'lock']\n"
        "- Storage spaces/units booked by specific individuals: Use exactly ['user', 'unit']\n\n"
        "If a manager asks for a hardware model count, pass its concept title (e.g. 'noke volt') inside semantic_filters.\n"
        "Do not invent column text fields. Do not expose physical tables or backend structures to the user."
    )
    
    # Initialize your Amazon Bedrock model instance and bind your secure tool schema contract
    llm_with_tools = _llm().bind_tools([execute_storage_query])
    
    # Prepend the system prompt instruction to the active conversation history track
    complete_message_track = [SystemMessage(content=system_instruction)] + list(messages)
    
    # Dispatch parameters down to AWS Bedrock runtime layers
    response_message = llm_with_tools.invoke(complete_message_track)
   
    return {"messages": [response_message]}


def execute_graph_tools(state: AgentState):
    """Secure backend execution bridge node that injects token contexts into your query compiler."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # Package your active session values to align with data retrieval requirements
    # Translates your state primitives into your core query engine session context dictionary
    computed_session_context = {
        "company_id": state.get("company_id"),
        "site_id": state.get("site_id"),
        "user_id": state.get("user_id")
    }
    
    tool_responses = []
    for tool_call in last_message.tool_calls:
        if tool_call["name"] == "execute_storage_query":
            args = tool_call["args"]

            print("\n" + "═"*40 + " OUTGOING MCP TOOL ARGUMENTS JSON " + "═"*40, file=sys.stderr)
            print(json.dumps(args, indent=2), file=sys.stderr)
            print("═"*114 + "\n", file=sys.stderr)
            try:
                # ─── MULTI-TENANT CONTEXT INJECTION GUARD SHIELD ───
                # Overwrites parameters with state variables to block user injection attempts
                db_rows_matrix = run_compiled_mcp_query(
                    subjects=args.get("target_subjects", []),
                    intent_type=args.get("intent_type"),
                    session_context=computed_session_context,
                    semantic_filters=args.get("semantic_filters"),
                    aggregation_column=args.get("aggregation_column"),
                    search_keyword=args.get("search_keyword")
                )
                string_payload = json.dumps(db_rows_matrix, default=str)
            except Exception as query_fault:
                string_payload = json.dumps({"error": f"Query engine processing dropped: {str(query_fault)}"})
                
            tool_responses.append(
                ToolMessage(
                    content=string_payload,
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"]
                )
            )
            
    return {"messages": tool_responses}


def generate_conversational_response(state: AgentState):
    """Synthesizes raw database JSON row data arrays back into elegant plain sentences."""
    messages = state["messages"]
    
    # Hand the complete historical message track (including the raw database row payloads) 
    # back into Bedrock to generate a conversational, human-friendly summary text response
    conversational_reply = _llm().invoke(messages)
    return {"messages": [conversational_reply]}


# =============================================================================
# 5. DEFINE CONDITIONAL ROUTING ROUTERS
# =============================================================================
def route_next_node(state: AgentState):
    """Inspects messages to decide whether to trigger tools or close the state loop."""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_tools"
    return END


# =============================================================================
# 6. ASSEMBLE THE COMPLETE STATE MACHINE WORKFLOW GRAPH
# =============================================================================
workflow = StateGraph(AgentState)

# Register workflow operational nodes
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


# =============================================================================
# --- LOCAL PRODUCTION LIVE CONNECTION TESTING HARNESS ---
# =============================================================================

if __name__ == "__main__":
    print("\n" + "═"*80)
    print("🧠 LANGGRAPH AGENT ORCHESTRATOR CONNECTED TO LIVE AMAZON BEDROCK RUNTIME")
    print("═"*80)
    
    # Simulating a live user prompt string input targeting your actual hardware models
    manager_prompt_input = "How many Noke Volt locks are managed at our site?"
    
    # FIXED: Explicitly use the native LangChain HumanMessage constructor cleanly 
    # to avoid colliding with any 'types' module namespaces imports from the top of the file!
    from langchain_core.messages import HumanMessage
    
    # Initialize the active state values matching your system specifications
    initial_graph_state = {
        "messages": [HumanMessage(content=manager_prompt_input)],        
        "site_id": [1001005]
    }
    
    print(f"💬 MANAGER INPUT PROMPT: '{manager_prompt_input}'")
    print(f"🔒 ACCOUNT PRIVILEGES ENFORCED:  Sites {initial_graph_state['site_id']}\n")
    
    try:
        # Dispatch the conversational payload straight into the graph compiler engine
        final_state_output = agent_brain_app.invoke(initial_graph_state)
        
        print("\n" + "═"*80)
        print("🏁 CONVERSATIONAL AGENT DIALOGUE COMPLETION SUMMARY SUCCESSFUL")
        print("═"*80)
        print(f"🤖 BEDROCK AGENT ANSWER: \"{final_state_output['messages'][-1].content}\"")
        print("═"*80 + "\n")
        
    except Exception as bedrock_connection_fault:
        print(f"\n💥 PIPELINE CRASH: Could not handshake with AWS Bedrock endpoints.")
        print(f"   Ensure AWS credentials (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) are exported in your terminal context.")
        print(f"   Details: {bedrock_connection_fault}\n")
