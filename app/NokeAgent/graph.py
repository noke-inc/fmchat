"""
app/NokeAgent/graph.py

Intent-routing LangGraph for Noke Smart Entry — AgentCore deployment version.

Topology identical to agent/graph.py but:
  • Imports from local config.py (no mcp_server/ dependency)
  • build_graph() accepts an optional checkpointer for short-term memory
  • Module-level `graph` is NOT compiled here (main.py compiles with MemorySaver)
"""

import logging
from typing import Annotated, Literal, Optional, TypedDict

from langchain_aws import ChatBedrock
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent

from config import BEDROCK_MODEL_ID, BEDROCK_REGION, AGENT_GATEWAY_URL, AGENT_GATEWAY_REGION
from mcp_client.client import get_noke_tools

logger = logging.getLogger(__name__)

# ── Intent literal type ───────────────────────────────────────────────────────
Intent = Literal["units", "locks", "locks_to_units", "schema", "general"]

INTENT_TOOLS: dict[str, list[str]] = {
    "units":          ["get_units"],
    "locks":          ["get_locks"],
    "locks_to_units": ["get_locks_to_units"],
    "schema":         ["describe_table"],
    "general":        [],
}


# ── Shared state ──────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id:  int
    site_id:  Optional[int]
    intent:   Optional[Intent]


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
        "  schema         → questions about table columns, database structure, "
                           "what fields / attributes exist\n"
        "  general        → greetings, general help, anything else\n",
    ),
    ("human", "{message}"),
])


async def classify_intent(state: AgentState) -> dict:
    last_human = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        "",
    )
    chain = _CLASSIFY_PROMPT | _llm() | StrOutputParser()
    raw: str = (await chain.ainvoke({"message": last_human})).strip().lower()
    intent: Intent = raw if raw in INTENT_TOOLS else "general"
    logger.info("classify_intent: %r → %s", last_human[:80], intent)
    return {"intent": intent}


def route_intent(state: AgentState) -> Intent:
    return state.get("intent") or "general"


_SYSTEM_TEMPLATE = (
    "You are a direct assistant for a Noke Smart Entry site manager.\n\n"
    "Rules (CRITICAL):\n"
    "1. NEVER explain your process, planning, or what tool you will use. Just answer.\n"
    "2. If you need data, call the tool silently. If no tool exists for the question, "
      "respond: 'That information is not available.'\n"
    "3. Output ONLY the direct answer in 1–4 sentences. No preamble, no reasoning.\n"
    "4. For data results: summarize clearly (e.g., '42 active units'). Never show raw JSON or IDs.\n"
    "5. Never use or mention: user_id, site_id, table names, database terms, internal fields.\n"
    "6. Do not use ANY XML tags like <thinking>, <answer>, etc. Plain text only.\n"
    "7. If a tool fails or data is missing, respond: 'Unable to retrieve that information. "
      "Please contact support if this persists.'\n\n"
    "Your tools: units, locks, lock-to-unit mappings, table schemas. Nothing else.\n"
    "Context: user_id={user_id}, site_id={site_id}."
)


async def _tool_node(state: AgentState, tool_names: list[str]) -> dict:
    user_id = state.get("user_id", 0)
    site_id = state.get("site_id")
    system_prompt = _SYSTEM_TEMPLATE.format(user_id=user_id, site_id=site_id)

    mcp_tools = await get_noke_tools(AGENT_GATEWAY_URL, AGENT_GATEWAY_REGION)

    # Gateway prefixes tool names with target name (e.g. "NokeMCPEksTarget___get_units").
    # Match by suffix after "___" separator.
    def _matches(tool_name: str, desired: str) -> bool:
        return tool_name == desired or tool_name.endswith(f"___{desired}")

    tools = [t for t in mcp_tools if any(_matches(t.name, n) for n in tool_names)]
    logger.info(
        "_tool_node intent=%s tools=%s", state.get("intent"), [t.name for t in tools]
    )

    sub = create_react_agent(_llm(), tools, prompt=system_prompt)
    result = await sub.ainvoke({"messages": state["messages"]})
    return {"messages": [result["messages"][-1]]}


async def node_units(state: AgentState) -> dict:
    return await _tool_node(state, ["get_units"])

async def node_locks(state: AgentState) -> dict:
    return await _tool_node(state, ["get_locks"])

async def node_locks_to_units(state: AgentState) -> dict:
    return await _tool_node(state, ["get_locks_to_units"])

async def node_schema(state: AgentState) -> dict:
    return await _tool_node(state, ["describe_table"])

async def node_general(state: AgentState) -> dict:
    user_id = state.get("user_id", 0)
    site_id = state.get("site_id")
    system_prompt = _SYSTEM_TEMPLATE.format(user_id=user_id, site_id=site_id)
    last_human = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        "",
    )
    answer: AIMessage = await _llm().ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=last_human)]
    )
    return {"messages": [answer]}


# ── Build & compile ───────────────────────────────────────────────────────────
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
    builder.add_node("schema",           node_schema)
    builder.add_node("general",          node_general)

    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_intent,
        {
            "units":          "units",
            "locks":          "locks",
            "locks_to_units": "locks_to_units",
            "schema":         "schema",
            "general":        "general",
        },
    )
    for node_name in ("units", "locks", "locks_to_units", "schema", "general"):
        builder.add_edge(node_name, END)

    return builder.compile(checkpointer=checkpointer)
