import sys
sys.path.insert(0, '.')

from graph import build_graph
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langgraph.checkpoint.memory import MemorySaver

m = MemorySaver()
g = build_graph(checkpointer=m)
print("ALL IMPORTS OK")
print("Graph type:", type(g).__name__)
app = BedrockAgentCoreApp()
print("BedrockAgentCoreApp OK")
