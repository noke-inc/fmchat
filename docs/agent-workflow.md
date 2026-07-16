# Noke FM Chat — Agent Workflow Diagram

```mermaid
flowchart TD
    U([👤 User Prompt]) --> APPEND[Append HumanMessage to state]
    APPEND --> INVOKE[agent_brain_app.invoke]
    INVOKE --> ROUTER{route_next_node}

    ROUTER -->|form_wait_state + Human| GATE
    ROUTER -->|assign / create keyword| GATE
    ROUTER -->|multi-site not selected| SITE_MENU[Site Selection Menu\nshow site list]
    ROUTER -->|read query| ORCH

    SITE_MENU -->|user selects site| ORCH

    ORCH[call_bedrock_orchestrator\nNova Micro discovers entities\nbuilds tool call]

    ORCH -->|tool_call: execute_storage_query| TOOLS
    ORCH -->|no entities matched — out of scope| END_CLEAN([END — refusal message])

    TOOLS[execute_graph_tools\nTrack A — MCP DB query\nTrack B — REST API call]

    TOOLS -->|READ: DB rows in ToolMessage| SYNTH
    TOOLS -->|WRITE: API result in ToolMessage| SYNTH

    SYNTH[generate_conversational_response\nNova Micro plain-English summary]
    SYNTH --> DISPLAY([💬 Answer shown to user])

    GATE[dynamic_mutation_gatekeeper_node\nSlot-filling form engine\napi_mutation_schema.json]
    GATE -->|fields still missing| WAIT([END — show next field prompt])
    GATE -->|all fields complete| TOOLS

    style U fill:#4A90D9,color:#fff
    style DISPLAY fill:#27AE60,color:#fff
    style WAIT fill:#E67E22,color:#fff
    style END_CLEAN fill:#E74C3C,color:#fff
    style ROUTER fill:#8E44AD,color:#fff
    style ORCH fill:#2980B9,color:#fff
    style GATE fill:#E67E22,color:#fff
```

## Node Descriptions

| Node | Role |
|---|---|
| `route_next_node` | Central traffic controller — inspects state and decides the next node |
| `call_bedrock_orchestrator` | Calls Amazon Nova Micro to identify DB entities and build a tool call |
| `execute_graph_tools` | **Track A** runs an MCP/DB query; **Track B** calls a REST API mutation |
| `generate_conversational_response` | Synthesises raw DB/API results into a plain-English answer |
| `dynamic_mutation_gatekeeper_node` | Slot-filling form engine driven by `api_mutation_schema.json` |
| `trigger_site_selection` | Displays an interactive site-picker menu when the user has multiple sites |

## Scenario Quick Reference

| User says | Track | Key nodes |
|---|---|---|
| "How many active units?" | Read / Aggregation | orchestrator → execute_tools (MCP) → synthesis |
| "What is the status of unit LA879?" | Read / Retrieval | orchestrator → execute_tools (MCP) → synthesis |
| "Assign a unit?" | Write / Form | gatekeeper (multi-turn) → execute_tools (REST API) → synthesis |
