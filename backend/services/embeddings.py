import os
from pinecone import Pinecone


pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
EMBED_MODEL = os.getenv("PINECONE_EMBEDDING_MODEL", "llama-text-embed-v2")
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "32"))


def _batch(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def get_embeddings(texts, input_type="passage"):
    """Get embedding vectors in batches for efficiency."""
    if not texts:
        return []

    vectors = []
    for batch in _batch(texts, EMBED_BATCH_SIZE):
        embedding = pc.inference.embed(
            model=EMBED_MODEL,
            inputs=batch,
            parameters={"input_type": input_type},
        )
        vectors.extend(item.values for item in embedding.data)

    return vectors


def get_query_embedding(text):
    """Get embedding for a query (uses query input_type for better retrieval)."""
    vectors = get_embeddings([text], input_type="query")
    return vectors[0]
