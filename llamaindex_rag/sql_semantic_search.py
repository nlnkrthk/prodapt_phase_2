
import os
import truststore
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import create_engine
from pathlib import Path
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import (
    SQLDatabase,
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Settings,
)
from llama_index.core.objects import (
    SQLTableSchema,
    SQLTableNodeMapping,
    ObjectIndex,
)
from llama_index.core.query_engine import SQLTableRetrieverQueryEngine
from llama_index.core.llms import (
    CustomLLM,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
)


# =========================================================
# Environment
# =========================================================

truststore.inject_into_ssl()
load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

if not NVIDIA_API_KEY:
    raise ValueError("NVIDIA_API_KEY was not found in the .env file.")


# =========================================================
# NVIDIA LLM
# =========================================================

nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)


class NVIDIA_LLM(CustomLLM):

    model_name: str = "openai/gpt-oss-20b"
    temperature: float = 0.2
    max_tokens: int = 500

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=32768,
            num_output=self.max_tokens,
            model_name=self.model_name,
        )

    def complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs,
    ) -> CompletionResponse:
        print("\n===== NVIDIA LLM CALLED =====")
        print(prompt[:2000])
        print("=============================\n")

        response = nvidia_client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        return CompletionResponse(
            text=response.choices[0].message.content
        )

    def stream_complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs,
    ) -> CompletionResponseGen:

        yield self.complete(
            prompt,
            formatted=formatted,
            **kwargs,
        )


llm = NVIDIA_LLM()


# =========================================================
# Database
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / "data" / "telecom_ops.db"

engine = create_engine(f"sqlite:///{DATABASE_PATH}")

sql_database = SQLDatabase(engine)

print("Database connected successfully!")


# =========================================================
# Table descriptions
# =========================================================

table_descriptions = {

    "network_towers": """
    Contains information about telecom network towers,
    including tower name, region, city, state, technology,
    status, location, and commissioning date.
    """,

    "network_outages": """
    Contains historical network outage records,
    including region, severity, start and end time,
    duration, affected customers, root cause, status,
    and outage description.
    """,

    "tower_performance": """
    Contains network tower performance measurements,
    including latency, packet loss, download and upload
    throughput, signal strength, and active connections.
    """,

    "open_incidents": """
    Contains network incidents, including tower,
    severity, status, title, description, opening time,
    classification, and assigned team.
    """,

    "customer_subscriptions": """
    Contains customer subscription information,
    including customer details, account type, plan,
    monthly fee, region, location, subscription status,
    line count, and start date.
    """,

    "billing_accounts": """
    Contains customer billing account information,
    including account balance, currency, service region,
    billing cycle, auto-pay status, and account status.
    """,

    "billing_charges": """
    Contains customer billing charges, including charge
    description, amount, billing period, charge date,
    charge type, duplicate flag, and invoice status.
    """,

    "billing_credits": """
    Contains billing credits issued to customers,
    including credit amount, reason, status, creation date,
    and related billing charge.
    """,

    "billing_disputes": """
    Contains customer billing disputes, including disputed
    charge, reason, status, opening and resolution dates,
    and resolution notes.
    """,
}

print(
    "Table descriptions created:",
    len(table_descriptions),
)


# =========================================================
# SQL table schemas
# =========================================================

table_schemas = []

for table_name, description in table_descriptions.items():

    table_schemas.append(
        SQLTableSchema(
            table_name=table_name,
            context_str=description,
        )
    )

print(
    "SQL table schemas created:",
    len(table_schemas),
)


# =========================================================
# Table-node mapping
# =========================================================

table_node_mapping = SQLTableNodeMapping(
    sql_database
)

print("SQL table node mapping created!")


# =========================================================
# Embedding model
# =========================================================

embed_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

Settings.embed_model = embed_model


# =========================================================
# Semantic SQL vector index
# =========================================================

PERSIST_DIR = "data/semantic_sql_index"


if os.path.exists(PERSIST_DIR):

    storage_context = StorageContext.from_defaults(
        persist_dir=PERSIST_DIR
    )

    index = load_index_from_storage(
        storage_context,
        embed_model=embed_model,
    )

    obj_index = ObjectIndex(
        index,
        table_node_mapping,
    )

    print("ObjectIndex loaded from storage!")

else:

    obj_index = ObjectIndex.from_objects(
        table_schemas,
        table_node_mapping,
        index_cls=VectorStoreIndex,
        embed_model=embed_model,
    )

    obj_index.index.storage_context.persist(
        persist_dir=PERSIST_DIR
    )

    print("ObjectIndex created and persisted!")


# =========================================================
# SQL query engine
# =========================================================

query_engine = SQLTableRetrieverQueryEngine(
    sql_database,
    obj_index.as_retriever(
        similarity_top_k=1
    ),
    llm=llm,
)

print("SQL Table Retriever Query Engine created!")

query = input("Enter the query : ")

print("\nQuery:", query)

response = query_engine.query(query)

print("\nAnswer:")
print(response)