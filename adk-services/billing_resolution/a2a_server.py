from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .agent import root_agent


app = to_a2a(
    root_agent,
    host="localhost",
    port=8002,
)

#start a2a server
#uvicorn billing_resolution.a2a_server:app --host 0.0.0.0 --port 8002

#verify agent card
#Invoke-WebRequest http://localhost:8002/.well-known/agent-card.json