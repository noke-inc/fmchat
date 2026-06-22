"""
app/NokeAgent/graph.py

Intent-routing LangGraph for Noke Smart Entry — AgentCore deployment version.

Topology identical to agent/graph.py but:
  • Imports from local config.py (no mcp_server/ dependency)
  • build_graph() accepts an optional checkpointer for short-term memory
  • Module-level `graph` is NOT compiled here (main.py compiles with MemorySaver)
"""

import json
import logging
from pathlib import Path
import re
from difflib import get_close_matches
from typing import Annotated, Literal, Optional, TypedDict

from langchain_aws import ChatBedrock
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from config import BEDROCK_MODEL_ID, BEDROCK_REGION, AGENT_GATEWAY_URL, AGENT_GATEWAY_REGION
from mcp_client.client import get_noke_tools

logger = logging.getLogger(__name__)


def _msg_text(content) -> str:
    """Normalize HumanMessage.content to plain text.
    LangChain may represent content as a list of parts, e.g.
    [{"type": "text", "text": "..."}, ...]. This flattens it to a string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


_DATA_HINT_TERMS = (
    "unit", "units", "site", "sites", "lock", "locks", "count", "how many",
    "number", "list", "show", "which", "status", "active", "available", "occupied",
)

# ── Intent literal type ───────────────────────────────────────────────────────
Intent = Literal["units", "locks", "locks_to_units", "sites"]

INTENT_TOOLS: dict[str, list[str]] = {
    "units":          ["aggregate_query", "search_records"],
    "locks":          ["search_records"],
    "locks_to_units": ["search_records"],
    "sites":          ["aggregate_query", "search_records"],
}

INTENT_ENTITY: dict[str, str] = {
    "units":          "unit",
    "locks":          "unit",
    "locks_to_units": "unit",
    "sites":          "site",
}


# ── Shared state ──────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages:     Annotated[list[BaseMessage], add_messages]
    user_id:      int
    site_id:      Optional[int]
    company_uuid: Optional[str]
    intent:       Optional[Intent]


# ── LLM factory ──────────────────────────────────────────────────────────────
def _llm() -> ChatBedrock:
    return ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        region_name=BEDROCK_REGION,
        model_kwargs={"temperature": 0, "max_tokens": 2048},
    )


# ── Node: classify_intent ─────────────────────────────────────────────────────
_CLASSIFY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Classify the user's question into EXACTLY one of these categories and "
        "respond with ONLY the category name — no explanation, no punctuation.\n\n"
        "  units          → questions about storage units, unit counts, unit details\n"
        "  locks          → questions about locks, lock status, lock type\n"
        "  locks_to_units → questions about which lock is on which unit, "
                               "lock-to-unit assignments or mappings\n"
        "  sites          → questions about site names or listing sites for a company\n",
    ),
    ("human", "{message}"),
])


async def classify_intent(state: AgentState) -> dict:
    last_human = _msg_text(next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        "",
    ))
    chain = _CLASSIFY_PROMPT | _llm() | StrOutputParser()
    raw: str = (await chain.ainvoke({"message": last_human})).strip().lower()
    intent: Intent = raw if raw in INTENT_TOOLS else "units"
    logger.info("classify_intent: %r → %s", last_human[:80], intent)
    return {"intent": intent}


def route_intent(state: AgentState) -> Intent:
    return state.get("intent") or "units"


_SYSTEM_TEMPLATE = (
    "You are a direct assistant for a Noke Smart Entry site manager.\n\n"

    "Rules (CRITICAL - follow exactly):\n"
    "1. For ANY factual/domain question you MUST call a tool before answering. No exceptions.\n"
    "2. Never explain your process, plan, or which tool you chose. Just answer.\n"
    "3. Output ONLY the direct answer in 1-4 sentences. No preamble, no reasoning, no XML tags.\n"
    "4. Never show raw JSON, IDs, table names, SQL, or internal fields.\n"
    "5. If a tool fails or returns no data respond exactly: "
      "'Unable to retrieve that information. Please contact support if this persists.'\n"
    "6. If the question is outside this domain respond exactly: "
      "'That information is not available.'\n\n"

    "COLUMN BINDING RULE (STRICT - MANDATORY):\n"
    "If a user query contains ANY word that appears in a column's enum_map from the schema,\n"
    "you MUST:\n"
    "  1. Identify the column that defines that enum_map\n"
    "  2. Add a filter using that column\n"
    "  3. Use the user’s word EXACTLY as the filter value\n"
    "\n"
    "You MUST NOT:\n"
    "  - Guess columns\n"
    "  - Skip filters\n"
    "  - Ignore enum_map matches\n"
    "\n"
    "Example mappings:\n"
    "  'active'   → column='rental_state' → filters=[{{'column':'rental_state','operator':'=','value':'active'}}]\n"
    "  'vacant'   → column='rental_state'\n"
    "  'occupied' → column='rental_state'\n"
    "\n"
    "If an enum_map value appears in the query and you do not include the corresponding filter,\n"
    "your response is INVALID.\n\n"

    "FILTER RULE (MANDATORY):\n"
    "  If the user's question includes any qualifier, status, or attribute word "
      "(e.g. active, available, occupied, rented, vacant, free, in-use, "
      "any named state/type/location), you MUST pass a filters argument to the tool.\n"
    "  Translate qualifier words into filter conditions. Examples:\n"
    "    'active units'     -> filters=[{{'column':'rental_state','operator':'=','value':'active'}}]\n"
    "    'available units'  -> filters=[{{'column':'rental_state','operator':'=','value':'available'}}]\n"
    "    'occupied units'   -> filters=[{{'column':'rental_state','operator':'=','value':'occupied'}}]\n"
    "    'rentable locks'   -> filters=[{{'column':'access_type','operator':'=','value':'rentable'}}]\n"
    "    'sites in georgia' -> filters=[{{'column':'name','operator':'LIKE','value':'%Georgia%'}}]\n"
    "  The server auto-normalizes synonyms (active->inuse, vacant->available, etc.).\n"
    "  NEVER omit filters when a qualifier or location word is present.\n\n"

    "VALID vs INVALID examples:\n"
    "User: 'active unit count'\n"
    "  ✅ CORRECT: tool call WITH filters on rental_state\n"
    "  ❌ WRONG: tool call WITHOUT filters\n\n"

    "Tool usage:\n"
    "  - aggregate_query: counts, totals, grouped summaries. "
      "Always pass user_id={user_id} and entity='{entity}'.\n"
    "  - search_records: listings, field lookups. "
      "Always pass user_id={user_id} and entity='{entity}'.\n"

    "Context: user_id={user_id}, site_id={site_id}, company_uuid={company_uuid}."
)


def _contains_tool_message(messages: list[BaseMessage]) -> bool:
    for m in messages:
        if isinstance(m, ToolMessage):
            return True
        if isinstance(m, AIMessage):
            if getattr(m, "tool_calls", None):
                return True
            if (getattr(m, "additional_kwargs", None) or {}).get("tool_calls"):
                return True
    return False


def _likely_data_prompt(messages: list[BaseMessage]) -> bool:
    last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    if not last_human:
        return False
    text = _msg_text(last_human.content).strip().lower()
    return any(term in text for term in _DATA_HINT_TERMS)


# ── Schema-driven filter hint ─────────────────────────────────────────────────
_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        schema_path = (
            Path(__file__).parent.parent.parent
            / "eks" / "mcp_server" / "schema.json"
        )
        with schema_path.open() as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


def _build_schema_context() -> str:
    """
    Build a compact, human-readable schema summary for the LLM system prompt.
    Covers: entity names & aliases, exposed columns with descriptions,
    allowed enum values, and filter synonym normalization rules.
    Fully driven by schema.json — no hardcoded entity or column names.
    """
    try:
        schema = _load_schema()
    except Exception:
        logger.warning("_build_schema_context: failed to load schema")
        return ""

    physical = schema.get("physical_schema", {})
    semantic = schema.get("semantic_layer", {})
    lines: list[str] = ["DATABASE SCHEMA (authoritative reference — use this to choose columns and filters):"]

    for entity_key, entity_def in semantic.get("entities", {}).items():
        table = entity_def.get("physical_table", "")
        aliases = ", ".join(entity_def.get("aliases", [])[:5])
        lines.append(f"\nEntity '{entity_key}' (table: {table}) — also referred to as: {aliases}")
        if entity_def.get("description"):
            lines.append(f"  Description: {entity_def['description']}")

        table_def = physical.get(table, {})
        exposed_cols = {
            col: defn
            for col, defn in table_def.get("columns", {}).items()
            if defn.get("expose")
        }
        if exposed_cols:
            lines.append("  Queryable columns:")
            for col_name, col_def in exposed_cols.items():
                desc = col_def.get("description", "")
                col_type = col_def.get("type", "")
                lines.append(f"    • {col_name} ({col_type}): {desc}")

    # Enum / synonym rules from semantic layer
    enum_lines: list[str] = []
    for col_key, col_def in semantic.get("columns", {}).items():
        enum_map = col_def.get("enum_map")
        if enum_map:
            pairs = ", ".join(f"'{k}'→'{v}'" for k, v in enum_map.items())
            desc = col_def.get("description", "")
            enum_lines.append(f"  {col_key}: {pairs}")
            if desc:
                enum_lines.append(f"    ({desc})")

    if enum_lines:
        lines.append("\nFilter synonym normalization (server auto-converts these):")
        lines.extend(enum_lines)

    # Allowed aggregations
    agg_meta = schema.get("aggregation_metadata", {})
    allowed_aggs = agg_meta.get("allowed_aggregations", {})
    if allowed_aggs:
        lines.append("\nSupported aggregations: " + ", ".join(allowed_aggs.keys()))

    return "\n".join(lines)

def _extract_enum_filters(prompt: str, schema: dict) -> list[dict]:
    text = prompt.lower()

    # normalize phrases
    text = text.replace("in use", "inuse").replace("in-use", "inuse")

    words = set(re.findall(r"\b[a-z]+\b", text))

    filters: list[dict] = []

    for col, col_def in schema.get("semantic_layer", {}).get("columns", {}).items():
        enum_map = col_def.get("enum_map", {})

        candidates = set(enum_map.keys()) | set(enum_map.values())

        for candidate in candidates:
            candidate = candidate.lower()

            # ✅ exact match
            if candidate in words:
                logger.info("enum filter extracted (exact): %s=%s", col, candidate)
                filters.append({
                    "column": col,
                    "operator": "=",
                    "value": candidate
                })
                break

            # ✅ fuzzy match
            close = get_close_matches(candidate, words, n=1, cutoff=0.8)
            if close:
                logger.warning("Fuzzy match: '%s' → '%s'", close[0], candidate)
                filters.append({
                    "column": col,
                    "operator": "=",
                    "value": candidate
                })
                break

    return filters

async def _tool_node(state: AgentState, tool_names: list[str], entity: str) -> dict:
    user_id = state.get("user_id", 0)
    site_id = state.get("site_id")
    company_uuid = state.get("company_uuid")
    logger.info("_tool_node start: intent=%s entity=%s user_id=%s site_id=%s company_uuid=%s",
                state.get("intent"), entity, user_id, site_id, company_uuid)
    last_human_text = _msg_text(next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        "",
    ))

    system_prompt = _SYSTEM_TEMPLATE.format(
        user_id=user_id, site_id=site_id, company_uuid=company_uuid, entity=entity
    )
    schema_context = _build_schema_context()
    
    if schema_context:
        system_prompt = system_prompt + "\n\n" + schema_context

    mcp_tools = await get_noke_tools(AGENT_GATEWAY_URL, AGENT_GATEWAY_REGION)
    logger.info("Available tools from MCP: %s", [t.name for t in mcp_tools])
    def _matches(tool_name: str, desired: str) -> bool:
        return tool_name == desired or tool_name.endswith(f"___{desired}")

    tools = [t for t in mcp_tools if any(_matches(t.name, n) for n in tool_names)]
    logger.info("_tool_node intent=%s entity=%s tools=%s", state.get("intent"), entity, [t.name for t in tools])
    logger.info("_tool_node setup: intent=%s entity=%s tools=%s", state.get("intent"), entity, [t.name for t in tools])
    
    llm = _llm()
    llm_with_tools = llm.bind_tools(tools)
    messages_for_llm = [SystemMessage(content=system_prompt)] + list(state["messages"])

    # Step 1: LLM decides which tool + base args
    ai_response = await llm_with_tools.ainvoke(messages_for_llm)
 
    logger.warning(
        "RAW TOOL CALLS (formatted): %s",
        json.dumps(ai_response.tool_calls, indent=2)
    )

    logger.info("LLM response: %s", ai_response)

    if not ai_response.tool_calls:
        if _likely_data_prompt(state["messages"]):
            logger.warning("LLM did not call a tool; retrying.")
            retry_msgs = messages_for_llm + [
                HumanMessage(content="You must call one of the available tools to answer this. Do not answer without a tool call.")
            ]
            ai_response = await llm_with_tools.ainvoke(retry_msgs)
        if not ai_response.tool_calls:
            return {"messages": [ai_response]}

    # Step 2: Validate tool call against schema
    required_filters = _extract_enum_filters(last_human_text, _load_schema())
    logger.warning(
        "ENUM FILTERS | query='%s' | extracted=%s",
        last_human_text,
        required_filters,
    )
    print("Required filters:", required_filters)

    invalid = False
    # ✅ FORCE inject required filters (DO THIS ALWAYS)
  
    if required_filters:
        new_tool_calls = []

        for tc in ai_response.tool_calls:
            args = dict(tc.get("args", {}) or {})
            existing = args.get("filters") or []

            # Normalize existing filters
            existing_keys = {
                (f.get("column"), str(f.get("value", "")).lower().strip())
                for f in existing if isinstance(f, dict)
            }

            # ✅ Inject missing filters
            for rf in required_filters:
                key = (rf["column"], rf["value"].lower().strip())
                if key not in existing_keys:
                    logger.warning(
                        "Injecting missing filter: %s=%s",
                        rf["column"], rf["value"]
                    )
                    existing.append(rf)
                    existing_keys.add(key)

            # ✅ Update args
            args["filters"] = existing

            # ✅ Validate AFTER injection
            present_filters = {
                (f.get("column"), str(f.get("value", "")).lower().strip())
                for f in existing if isinstance(f, dict)
            }

            required_filters_set = {
                (f["column"], str(f["value"]).lower().strip())
                for f in required_filters
            }

            if not required_filters_set.issubset(present_filters):
                logger.warning(
                    "Filter validation failed | required=%s | present=%s",
                    required_filters_set,
                    present_filters,
                )
                invalid = True

            # ✅ IMPORTANT: build new tool call (this fixes your bug)
            new_tool_calls.append({
                **tc,
                "args": args
            })

        # ✅ overwrite tool_calls
        ai_response.tool_calls = new_tool_calls

        # ✅ FIX: Deduplicate tool calls (keep only first)
        if ai_response.tool_calls:
            if len(ai_response.tool_calls) > 1:
                logger.warning(
                    "Multiple tool calls detected (%d) — keeping only first",
                    len(ai_response.tool_calls)
                )
            ai_response.tool_calls = [ai_response.tool_calls[0]]

  
    # Step 3: Execute tool calls
    tool_map = {t.name: t for t in tools}
    print("Executing tool calls...")
    tool_messages: list[BaseMessage] = [ai_response]    
    logger.warning("FINAL TOOL CALLS: %s", ai_response.tool_calls)
    for tc in ai_response.tool_calls:
        tool = tool_map.get(tc["name"]) or next(
            (t for t in tools if _matches(t.name, tc["name"].split("___")[-1])), None
        )
        if tool:
            try:
                raw = await tool.ainvoke(tc["args"])
            except Exception as e:
                raw = f"Tool error: {e}"                
            tool_messages.append(ToolMessage(content=str(raw), tool_call_id=tc["id"]))
            logger.info("Tool result [%s]: %s", tc["name"], str(raw)[:500])

    # Step 4: Final response (CLEAN context)

    final_llm = _llm()

    # ✅ Extract original question
    user_msg = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )

    # ✅ Extract last tool result
    last_tool_msg = next(
        (m for m in reversed(tool_messages) if isinstance(m, ToolMessage)),
        None,
    )

    # ✅ Build clean minimal prompt
    final_messages_clean = [
        SystemMessage(content=(
            "You are a helpful assistant.\n"
            "You are given a user question and a tool result.\n"
            "Return ONLY a concise final answer based on the tool result.\n"
            "Do NOT call tools. Do NOT explain reasoning."
        )),
    ]

    if user_msg:
        final_messages_clean.append(user_msg)

    if last_tool_msg:
        final_messages_clean.append(last_tool_msg)

    # ✅ Final answer generation (no tools!)
    final_response = await final_llm.ainvoke(final_messages_clean)

    return {"messages": [final_response]}  
    

async def node_units(state: AgentState) -> dict:
    return await _tool_node(state, ["aggregate_query", "search_records"], "unit")

async def node_locks(state: AgentState) -> dict:
    return await _tool_node(state, ["search_records"], "unit")

async def node_locks_to_units(state: AgentState) -> dict:
    return await _tool_node(state, ["search_records"], "unit")

async def node_sites(state: AgentState) -> dict:
    return await _tool_node(state, ["aggregate_query", "search_records"], "site")


def build_graph(checkpointer=None):
    """Compile the intent-routing StateGraph.

    Args:
        checkpointer: Optional LangGraph checkpointer for short-term memory
                      (MemorySaver in main.py gives per-session history).
    """
    builder = StateGraph(AgentState)

    builder.add_node("classify_intent",  classify_intent)
    builder.add_node("units",            node_units)
    builder.add_node("locks",            node_locks)
    builder.add_node("locks_to_units",   node_locks_to_units)
    builder.add_node("sites",            node_sites)

    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_intent,
        {
            "units":          "units",
            "locks":          "locks",
            "locks_to_units": "locks_to_units",
            "sites":          "sites",
        },
    )
    for node_name in ("units", "locks", "locks_to_units", "sites"):
        builder.add_edge(node_name, END)

    return builder.compile(checkpointer=checkpointer)
