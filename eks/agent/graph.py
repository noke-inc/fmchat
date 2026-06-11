"""
agent/graph.py

Intent-based LangGraph for Noke Smart Entry.

Graph topology:

    START
      └─► classify_intent   ← LLM classifies into one of 5 intents
              │
    ┌─────────┼─────────────────────────────────────┐
    │         │                                     │
  units     locks    locks_to_units   schema    general
    │         │            │            │            │
    └─────────┴────────────┴────────────┴────────────┘
                                │
                               END

Benefits over single ReAct agent:
  • LLM only sees the relevant tool — fewer tokens, less hallucination.
  • Each intent node is independently replaceable / testable.
  • Graph is inspectable in LangGraph Studio (`langgraph dev`).
"""

import logging
from typing import Annotated, Literal, Optional, TypedDict

from langchain_aws import ChatBedrock
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent

from mcp_server.config import AGENT_MCP_URL, BEDROCK_MODEL_ID, BEDROCK_REGION

logger = logging.getLogger(__name__)

# ── Intent literal type ───────────────────────────────────────────────────────
Intent = Literal["units", "locks", "locks_to_units", "schema", "general"]

# Which MCP tool each intent should access
INTENT_TOOLS: dict[str, list[str]] = {
    "units":          ["get_units"],
    "locks":          ["get_locks"],
    "locks_to_units": ["get_locks_to_units"],
    "schema":         ["describe_table"],
    "general":        [],
}


# ── Shared state ──────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    """State threaded through every node in the graph."""
    messages: Annotated[list[BaseMessage], add_messages]
    user_id:  int
    site_id:  Optional[int]
    intent:   Optional[Intent]          # set by classify_intent


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
    """Classify the latest HumanMessage to decide which tool node to call."""
    last_human = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        "",
    )
    chain = _CLASSIFY_PROMPT | _llm() | StrOutputParser()
    raw: str = (await chain.ainvoke({"message": last_human})).strip().lower()
    intent: Intent = raw if raw in INTENT_TOOLS else "general"
    logger.info("classify_intent: %r → %s", last_human[:80], intent)
    return {"intent": intent}


# ── Conditional edge: route by intent ────────────────────────────────────────
def route_intent(state: AgentState) -> Intent:
    return state.get("intent") or "general"


# ── Node factory: ReAct sub-agent with a single tool group ───────────────────
_SYSTEM_TEMPLATE = (
    "You are a helpful AI assistant for Noke Smart Entry property management. "
    "You have access to tools that query the Noke database in read-only mode. "
    "Only use the provided tools; do not make up data. "
    "If a tool returns an error, explain it clearly to the user. "
    "Keep answers concise and relevant to property management. "
    "User context: user_id={user_id}, site_id={site_id}."
)


async def _tool_node(state: AgentState, tool_names: list[str]) -> dict:
    """Load the named MCP tools and run a focused ReAct sub-agent."""
    user_id = state.get("user_id", 0)
    site_id = state.get("site_id")
    system_prompt = _SYSTEM_TEMPLATE.format(user_id=user_id, site_id=site_id)

    mcp_client = MultiServerMCPClient(
        {"noke-mcp": {"url": AGENT_MCP_URL, "transport": "sse"}}
    )
    all_tools = await mcp_client.get_tools()
    tools = [t for t in all_tools if t.name in tool_names]
    logger.info(
        "_tool_node intent=%s tools=%s", state.get("intent"), [t.name for t in tools]
    )

    sub = create_react_agent(_llm(), tools, prompt=system_prompt)
    result = await sub.ainvoke({"messages": state["messages"]})
    return {"messages": [result["messages"][-1]]}


# Individual named nodes (required for LangGraph to give them distinct names in Studio)
async def node_units(state: AgentState) -> dict:
    return await _tool_node(state, ["get_units"])


async def node_locks(state: AgentState) -> dict:
    return await _tool_node(state, ["get_locks"])


async def node_locks_to_units(state: AgentState) -> dict:
    return await _tool_node(state, ["get_locks_to_units"])


async def node_schema(state: AgentState) -> dict:
    return await _tool_node(state, ["describe_table"])


async def node_general(state: AgentState) -> dict:
    """Answer general questions with no database tools."""
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
        checkpointer: Optional LangGraph checkpointer (e.g. MemorySaver) for
                      short-term memory / conversation history.  Defaults to
                      None (stateless) for the existing MCP-server path.
    """
    builder = StateGraph(AgentState)

    # Nodes
    builder.add_node("classify_intent",  classify_intent)
    builder.add_node("units",            node_units)
    builder.add_node("locks",            node_locks)
    builder.add_node("locks_to_units",   node_locks_to_units)
    builder.add_node("schema",           node_schema)
    builder.add_node("general",          node_general)

    # Edges
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


# ── Exported graph (consumed by langgraph.json and agent.py) ─────────────────
graph = build_graph()
