from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .agent import root_agent


app = to_a2a(
    root_agent,
    host="localhost",
    port=8001,
)

#start a2a service
#uvicorn network_diagnostics.a2a_server:app --host 0.0.0.0 --port 8001

#verify agent card
#curl http://localhost:8001/.well-known/agent-card.json