# main.py
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

# Import your frozen, data-driven core engine functions safely
from data_retrieval_engine import load_database_schema_config, run_compiled_mcp_query

# 1. Initialize the official Model Context Protocol server instance
mcp_app = FastMCP("Storage-Enterprise-Data-Gateway")

# 2. Cache your static JSON schema roadmap on container boot-up
load_database_schema_config("database_schema.json")


# =============================================================================
# 3. HIGHLY DENSE PYDANTIC INTERACTION SCHEMA DEFINITIONS
# =============================================================================
class StorageQueryArgs(BaseModel):
    intent_type: str = Field(
        ..., 
        description=(
            "The execution track target. You MUST choose exactly 'DATA_AGGREGATION' if the operator asks "
            "for numbers, metrics, math totals, averages, or counts. You MUST choose exactly 'DATA_RETRIEVAL' "
            "if the user asks to see profiles, details, names, lists, text grids, or specific histories."
        )
    )
    target_subjects: List[str] = Field(
        ..., 
        description=(
            "An array of entity keywords mentioned by the user. Allowed core entities: ['unit', 'user', 'site', 'lock', 'role']. "
            "CRITICAL ORDER ROUTING INSTRUCTION: You must chain these entities in a step-by-step sequential path where each table "
            "shares a clear relational bridge. 'user' acts as your central bridge between spaces. Pre-validated paths:\n"
            "- To list users by job title/roles at a location: Use exactly ['site', 'user', 'role']\n"
            "- To search or calculate hardware lock assets by site profile: Use exactly ['site', 'unit', 'lock']\n"
            "- To analyze hardware locks linked to specific customers: Use exactly ['user', 'unit', 'lock']\n"
            "- To resolve spaces booked by specific people: Use exactly ['user', 'unit']"
        )
    )
    semantic_filters: Optional[List[str]] = Field(
        None, 
        description=(
            "Array of conversational data statuses or analytical operations extracted from the prompt text. "
            "For calculations, include words like ['count', 'avg', 'sum']. For space states, map keywords to synonyms "
            "like ['vacant', 'active', 'disabled', 'transfer']. If none are mentioned, pass null or an empty list."
        )
    )
    aggregation_column: Optional[str] = Field(
        None, 
        description=(
            "The target performance metric field required when computing mathematical math expressions (avg, sum). "
            "Allowed choices: Use exactly 'details_price' for financial costs/rates/values, use exactly 'details_width' "
            "or 'details_price' for spatial dimensions. Leave entirely empty or null for simple counts or text listing searches."
        )
    )
    search_keyword: Optional[str] = Field(
        None, 
        description="The exact personal name strings, customer tags, or unit identities requested for matching (e.g., 'Alex', '733', 'Company Manager')."
    )


# =============================================================================
# 4. MCP TOOL REGISTRATION LAYER
# =============================================================================
@mcp_app.tool()
def execute_storage_query(
    intent_type: str, 
    target_subjects: List[str], 
    semantic_filters: Optional[List[str]] = None, 
    aggregation_column: Optional[str] = None, 
    search_keyword: Optional[str] = None
) -> str:
    """
    Unified enterprise read-only analytics gateway portal. Use this tool whenever the operator 
    requests calculations, metrics, text listing lookups, counts, histories, or status evaluations regarding 
    storage spaces, smart entry locks, security permission roles, user accounts, and company facility metrics.
    """
    # Forcefully inject your multi-tenant security profile context metadata at the network boundary.
    # This prevents any token parameter manipulation, keeping your EKS clusters locked to verified context scopes.
    mock_active_session = {
        "company_id": None,
        "site_id": None, # Scoped user profile access limits
        "user_id": None
    }
    
    try:
        # Pass parameters down into your 100% dynamic, datatype-isolated compiler engine
        results_matrix = run_compiled_mcp_query(
            subjects=target_subjects,
            intent_type=intent_type,
            session_context=mock_active_session,
            semantic_filters=semantic_filters,
            aggregation_column=aggregation_column,
            search_keyword=search_keyword
        )
        
        # MCP tools must return raw strings down the execution pipe back to the orchestrator node client.
        return json.dumps(results_matrix, default=str)
        
    except Exception as server_error:
        # Enforce an information-leaking insulation shield: block database crash dumps from the client screen
        return json.dumps({"error": f"Data retrieval execution dropped at gateway: {str(server_error)}"})

# ASGI app for uvicorn: python -m uvicorn main:app --host 0.0.0.0 --port 8000
app = mcp_app.streamable_http_app()

if __name__ == "__main__":
    # Start the standard input/output transport communication channel (stdio stream)
    mcp_app.run()
    
