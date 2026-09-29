import truststore
# Import os for environment variables and paths
import os

# Load variables from the .env file
from dotenv import load_dotenv

# NVIDIA uses an OpenAI-compatible API
from openai import OpenAI

# Base classes required to create a custom LlamaIndex LLM
from llama_index.core.llms import (
    CustomLLM,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
)

# LlamaIndex document loader
from llama_index.core import SimpleDirectoryReader

# LlamaIndex vector index
from llama_index.core import VectorStoreIndex

# LlamaIndex storage utilities
from llama_index.core import StorageContext
from llama_index.core import load_index_from_storage

# Local HuggingFace embedding model
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

truststore.inject_into_ssl()
# =========================================================
# Load environment variables
# =========================================================

load_dotenv()


# =========================================================
# Project paths
# =========================================================

DOCUMENT_PATH = "data/documents"

VECTOR_INDEX_PATH = "data/vector_index"


# =========================================================
# NVIDIA API key
# =========================================================

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

if not NVIDIA_API_KEY:
    raise ValueError(
        "NVIDIA_API_KEY was not found in the .env file."
    )


# =========================================================
# NVIDIA OpenAI-compatible client
# =========================================================

nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)


# =========================================================
# Custom NVIDIA LLM for LlamaIndex
# =========================================================

class NVIDIA_LLM(CustomLLM):

    # Store basic model information
    model_name: str = "openai/gpt-oss-20b"

    temperature: float = 0.2

    max_tokens: int = 500

    # Return model information to LlamaIndex
    @property
    def metadata(self) -> LLMMetadata:

        return LLMMetadata(
            context_window=32768,
            num_output=self.max_tokens,
            model_name=self.model_name
        )

    # Generate a response from NVIDIA
    def complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs
    ) -> CompletionResponse:

        # Send the prompt to NVIDIA
        response = nvidia_client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        # Get the generated text
        text = response.choices[0].message.content

        # Return the response in LlamaIndex format
        return CompletionResponse(
            text=text
        )

    # Streaming is not required for this project
    def stream_complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs
    ) -> CompletionResponseGen:

        # Generate the normal response
        response = self.complete(
            prompt,
            formatted=formatted,
            **kwargs
        )

        # Return the response
        yield response


# =========================================================
# Create the NVIDIA LLM
# =========================================================

llm = NVIDIA_LLM()


# =========================================================
# Create the local embedding model
# =========================================================

embedding_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# =========================================================
# Load or create the vector index
# =========================================================

def load_or_create_index():

    # Check whether the vector index already exists
    if os.path.exists(VECTOR_INDEX_PATH):

        print("Vector index found.")

        print("Loading existing vector index...")

        # Load the saved index
        storage_context = StorageContext.from_defaults(
            persist_dir=VECTOR_INDEX_PATH
        )

        # Reconstruct the vector index
        index = load_index_from_storage(
            storage_context,
            embed_model=embedding_model
        )

        print("Vector index loaded successfully.")

        return index

    # Create the index if it does not exist
    print("Vector index not found.")

    print("Loading policy documents...")

    # Load all TXT files from the policy folder
    reader = SimpleDirectoryReader(
        input_dir=DOCUMENT_PATH,
        required_exts=[".txt"]
    )

    documents = reader.load_data()

    print(f"Documents loaded: {len(documents)}")

    # Create embeddings and the vector index
    print("Creating vector index...")

    index = VectorStoreIndex.from_documents(
        documents,
        embed_model=embedding_model
    )

    print("Vector index created successfully.")

    # Save the index
    print("Saving vector index...")

    index.storage_context.persist(
        persist_dir=VECTOR_INDEX_PATH
    )

    print("Vector index saved successfully.")

    return index


# =========================================================
# Create the LlamaIndex query engine
# =========================================================

def create_query_engine(index):

    # Create the LlamaIndex query engine
    query_engine = index.as_query_engine(
        llm=llm,
        similarity_top_k=3
    )

    return query_engine


# =========================================================
# Answer a policy question
# =========================================================

def answer_policy_question(question: str) -> str:

    # Load or create the vector index
    index = load_or_create_index()

    # Create the query engine
    query_engine = create_query_engine(index)

    # LlamaIndex performs retrieval and generation
    response = query_engine.query(question)

    # Return the final answer
    return str(response)


# =========================================================
# Test the Policy RAG
# =========================================================

if __name__ == "__main__":

    print()
    print("========================================")
    print("          PRODAPT POLICY RAG")
    print("========================================")

    # Get the question from the user
    question = input(
        "\nEnter your policy question: "
    )

    print()
    print("Searching policy documents...")

    # Run the RAG pipeline
    answer = answer_policy_question(question)

    print()
    print("========================================")
    print("                 ANSWER")
    print("========================================")

    print(answer)

    print()
    print("========================================")

