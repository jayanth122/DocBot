from services.embeddings import get_query_embedding
from services.pinecone_client import query_embedding

RELEVANCE_THRESHOLD = 0.25
MAX_HISTORY_TURNS = 6
MAX_DOCS_IN_PROMPT = 4
MAX_DOC_CHARS = 800
SHORT_MSG_THRESHOLD = 6  # word count — skip embedding for trivial messages

# Phrases that indicate the user is referring to an uploaded document
DOC_REFERENCE_KEYWORDS = [
    "this document", "the document", "this doc", "the doc", "this pdf",
    "the pdf", "the file", "this file", "uploaded", "attached",
    "summarize it", "summarize this", "summarise", "what does it say",
    "what is it about", "explain it", "explain this",
    "from the document", "according to the document", "in the pdf",
]


def is_doc_reference(message):
    """Check if the user is referring to an uploaded document."""
    msg_lower = message.lower()
    return any(keyword in msg_lower for keyword in DOC_REFERENCE_KEYWORDS)


def is_trivial_message(message):
    """Return True for short greetings / chitchat that don't need RAG."""
    return len(message.split()) <= SHORT_MSG_THRESHOLD and not is_doc_reference(message)


def _compact_docs(docs, limit=MAX_DOCS_IN_PROMPT):
    cleaned = []
    for doc in docs:
        metadata = doc.get("metadata", {})
        text = (metadata.get("text") or "").strip()
        if not text:
            continue

        score = doc.get("score", 0)
        source = metadata.get("source", "uploaded.pdf")
        excerpt = text[:MAX_DOC_CHARS]
        cleaned.append({"source": source, "score": score, "excerpt": excerpt})

    cleaned.sort(key=lambda d: d["score"], reverse=True)
    return cleaned[:limit]


def _format_docs_for_prompt(docs):
    compact = _compact_docs(docs)
    blocks = []
    for i, doc in enumerate(compact, start=1):
        blocks.append(
            f"[{i}] source={doc['source']} score={doc['score']:.3f}\n{doc['excerpt']}"
        )
    return "\n\n---\n\n".join(blocks)


def build_chat_prompt(user_msg, history):
    """Build a structured prompt for normal chatbot mode (no documents)."""
    return {
        "system": (
            "You are DOCBot, a concise and reliable AI assistant.\n"
            "Be accurate, direct, and brief. Use bullet points when helpful. "
            "Do not invent facts."
        ),
        "user": user_msg,
        "history": history[-MAX_HISTORY_TURNS:] if history else [],
    }


def build_rag_prompt(user_msg, history, docs):
    """Build a structured prompt for RAG mode with document context."""
    docs_text = _format_docs_for_prompt(docs)

    return {
        "system": (
            "You are DOCBot, a document-grounded assistant.\n"
            "Answer using only the excerpts below. "
            "If the answer is not in the excerpts, say so plainly. "
            "Cite evidence as [1], [2], etc. Keep answers concise.\n\n"
            f"Document excerpts:\n{docs_text}"
        ),
        "user": user_msg,
        "history": history[-MAX_HISTORY_TURNS:] if history else [],
    }


def build_refine_prompt(user_msg, initial_answer, docs):
    """Build a structured refinement prompt."""
    docs_text = _format_docs_for_prompt(docs)

    return {
        "system": (
            "You are improving an answer for clarity and factual grounding.\n"
            "Keep only claims supported by excerpts. "
            "Preserve citation tags like [1], [2]. Remove filler.\n\n"
            f"Document context:\n{docs_text}\n\n"
            f"Initial answer:\n{initial_answer}"
        ),
        "user": user_msg,
        "history": [],
    }


def retrieve_docs(query, session_id=None):
    """Embed the query and retrieve relevant document chunks from Pinecone."""
    try:
        vector = get_query_embedding(query)
        # Filter by session if provided
        filter_dict = {"session_id": {"$eq": session_id}} if session_id else None
        results = query_embedding(vector, top_k=8, filter=filter_dict)
        # Filter by relevance score
        relevant = [
            r
            for r in results
            if r.get("score", 0) >= RELEVANCE_THRESHOLD
            and r.get("metadata", {}).get("text")
        ]
        relevant.sort(key=lambda item: item.get("score", 0), reverse=True)
        return relevant[:MAX_DOCS_IN_PROMPT]
    except Exception:
        return []


def retrieve_all_session_docs(session_id):
    """Retrieve all document chunks for a session (for broad queries like 'summarize')."""
    try:
        if not session_id:
            return []

        # Use a generic embedding and rely on session filter to get all chunks
        vector = get_query_embedding("document content summary overview")
        results = query_embedding(
            vector,
            top_k=12,
            filter={"session_id": {"$eq": session_id}},
        )
        docs = [r for r in results if r.get("metadata", {}).get("text")]
        docs.sort(key=lambda item: item.get("score", 0), reverse=True)
        return docs[:MAX_DOCS_IN_PROMPT]
    except Exception:
        return []


def has_relevant_docs(docs):
    """Check if retrieved docs are actually relevant enough to use."""
    return any(d.get("metadata", {}).get("text") for d in docs)
