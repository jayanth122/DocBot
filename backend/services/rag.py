from services.embeddings import get_query_embedding
from services.pinecone_client import query_embedding

RELEVANCE_THRESHOLD = 0.25

# Phrases that indicate the user is referring to an uploaded document
DOC_REFERENCE_KEYWORDS = [
    "this document", "the document", "this doc", "the doc", "this pdf",
    "the pdf", "the file", "this file", "uploaded", "attached",
    "summarize it", "summarize this", "summarise", "what does it say",
    "what is it about", "explain it", "explain this",
]


def is_doc_reference(message):
    """Check if the user is referring to an uploaded document."""
    msg_lower = message.lower()
    return any(keyword in msg_lower for keyword in DOC_REFERENCE_KEYWORDS)


def build_chat_prompt(user_msg, history):
    """Build a prompt for normal chatbot mode (no documents)."""
    history_text = ""
    if history:
        history_text = "\n".join(
            [f"{m['role']}: {m['content']}" for m in history[-10:]]
        )

    return f"""You are DOCBot, a helpful and friendly AI assistant. Respond naturally and conversationally. Keep answers clear and well-formatted.

Chat history:
{history_text}

User: {user_msg}
Assistant:"""


def build_rag_prompt(user_msg, history, docs):
    """Build a prompt for RAG mode with document context."""
    history_text = ""
    if history:
        history_text = "\n".join(
            [f"{m['role']}: {m['content']}" for m in history[-10:]]
        )

    docs_text = "\n\n---\n\n".join([d["metadata"]["text"] for d in docs])

    return f"""You are DOCBot, a document-aware AI assistant. Answer the user's question based ONLY on the provided document excerpts. Be precise and cite relevant parts of the documents in your answer. If the documents don't contain enough information, clearly state what you found and what's missing.

Chat history:
{history_text}

Document excerpts:
{docs_text}

User: {user_msg}
Assistant:"""


def build_refine_prompt(user_msg, initial_answer, docs):
    """Build a refinement prompt to improve the initial RAG answer."""
    docs_text = "\n\n---\n\n".join([d["metadata"]["text"] for d in docs])

    return f"""You are a quality-checking assistant. The user asked a question about their documents, and an initial answer was generated. Your job is to refine this answer: make it clearer, more accurate, better structured, and ensure it directly addresses the question. Remove any filler or unnecessary hedging.

User's question: {user_msg}

Document context:
{docs_text}

Initial answer:
{initial_answer}

Provide a refined, polished answer:"""


def retrieve_docs(query, session_id=None):
    """Embed the query and retrieve relevant document chunks from Pinecone."""
    try:
        vector = get_query_embedding(query)
        # Filter by session if provided
        filter_dict = {"session_id": session_id} if session_id else None
        results = query_embedding(vector, top_k=8, filter=filter_dict)
        # Filter by relevance score
        relevant = [r for r in results if r.get("score", 0) >= RELEVANCE_THRESHOLD]
        return relevant
    except Exception:
        return []


def retrieve_all_session_docs(session_id):
    """Retrieve all document chunks for a session (for broad queries like 'summarize')."""
    try:
        # Use a generic embedding and rely on session filter to get all chunks
        vector = get_query_embedding("document content summary overview")
        results = query_embedding(vector, top_k=20, filter={"session_id": session_id})
        return results
    except Exception:
        return []


def has_relevant_docs(docs):
    """Check if retrieved docs are actually relevant enough to use."""
    return len(docs) > 0
