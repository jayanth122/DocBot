import os
from pinecone import Pinecone


pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))


def get_embedding(text):
    """Get embedding vector using Pinecone's built-in inference (llama-text-embed-v2)."""
    embedding = pc.inference.embed(
        model="llama-text-embed-v2",
        inputs=[text],
        parameters={"input_type": "passage"}
    )
    return embedding.data[0].values


def get_query_embedding(text):
    """Get embedding for a query (uses query input_type for better retrieval)."""
    embedding = pc.inference.embed(
        model="llama-text-embed-v2",
        inputs=[text],
        parameters={"input_type": "query"}
    )
    return embedding.data[0].values
