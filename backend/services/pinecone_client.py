import os
from pinecone import Pinecone


pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME", "docbot"))


def upsert_embedding(id, vector, metadata):
    """Store an embedding vector with metadata in Pinecone."""
    index.upsert(vectors=[(id, vector, metadata)])


def query_embedding(vector, top_k=5, filter=None):
    """Query Pinecone for the most similar vectors, optionally filtered."""
    kwargs = {"vector": vector, "top_k": top_k, "include_metadata": True}
    if filter:
        kwargs["filter"] = filter
    results = index.query(**kwargs)
    return results["matches"]


def delete_session_embeddings(session_id):
    """Delete all vectors associated with a chat session."""
    index.delete(filter={"session_id": {"$eq": session_id}})
