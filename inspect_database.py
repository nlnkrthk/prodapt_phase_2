import os

import truststore
from dotenv import load_dotenv
from openai import OpenAI
truststore.inject_into_ssl()
load_dotenv()

api_key = os.getenv("NVIDIA_API_KEY")

if not api_key:
    raise ValueError("NVIDIA_API_KEY not found in .env")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key
)

print("Calling NVIDIA LLM...")

response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[
        {
            "role": "user",
            "content": """
Which region had the most CRITICAL network outages?

Table:
network_outages(
    outage_id TEXT,
    region TEXT,
    severity TEXT,
    start_time TEXT,
    end_time TEXT,
    duration_hours REAL,
    affected_customers INTEGER,
    root_cause TEXT,
    status TEXT,
    description TEXT
)

Return only the SQLite SQL query.
"""
        }
    ],
    temperature=0.2,
    max_tokens=500,
    stream=False
)

print("\nNVIDIA response:")
print(response.choices[0].message.content)