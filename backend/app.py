import os
import uuid

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
import PyPDF2

from services.llm import call_llm, LLMServiceError
from services.rag import (
    build_chat_prompt, build_rag_prompt, build_refine_prompt,
    retrieve_docs, retrieve_all_session_docs, has_relevant_docs, is_doc_reference,
)
from services.embeddings import get_embeddings
from services.pinecone_client import upsert_embeddings, delete_session_embeddings
from services.supabase_client import (
    create_session,
    delete_session,
    get_sessions,
    save_message,
    get_messages,
)

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "/tmp/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ENABLE_RAG_REFINE = os.getenv("ENABLE_RAG_REFINE", "false").lower() == "true"


@app.errorhandler(HTTPException)
def handle_http_error(err):
    """Ensure Flask HTTP errors are returned as JSON."""
    return jsonify({"error": err.name, "message": err.description}), err.code


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    """Catch unexpected failures and return a stable JSON response."""
    app.logger.exception("Unhandled backend error: %s", err)
    return jsonify(
        {
            "error": "Internal Server Error",
            "message": "The server hit an unexpected issue. Please retry.",
        }
    ), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/sessions", methods=["POST"])
def new_session():
    data = request.json
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    session = create_session(user_id)
    return jsonify(session)


@app.route("/sessions", methods=["GET"])
def list_sessions():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    sessions = get_sessions(user_id)
    return jsonify(sessions)


@app.route("/sessions/<session_id>", methods=["DELETE"])
def remove_session(session_id):
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    deleted = delete_session(session_id, user_id)
    if not deleted:
        return jsonify({"error": "Session not found"}), 404

    try:
        delete_session_embeddings(session_id)
    except Exception as err:
        app.logger.warning("Failed to delete Pinecone vectors for session %s: %s", session_id, err)

    return jsonify({"success": True})


@app.route("/messages", methods=["GET"])
def list_messages():
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    messages = get_messages(session_id)
    return jsonify(messages)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message")
    session_id = data.get("session_id")
    user_id = data.get("user_id")

    if not message:
        return jsonify({"error": "message required"}), 400

    # Create session if not provided
    if not session_id:
        if not user_id:
            return jsonify({"error": "user_id required when session_id is missing"}), 400
        session = create_session(user_id)
        session_id = session["id"]

    # Fetch chat history
    try:
        history = get_messages(session_id)
    except Exception as err:
        app.logger.warning("Failed to load history for session %s: %s", session_id, err)
        history = []

    # Determine retrieval strategy
    docs = []
    doc_intent = is_doc_reference(message)
    if doc_intent:
        # User is referring to their uploaded doc — fetch all session chunks
        docs = retrieve_all_session_docs(session_id)
    
    if not docs:
        # Try semantic search filtered by session
        docs = retrieve_docs(message, session_id=session_id)

    has_docs = has_relevant_docs(docs)

    try:
        if doc_intent and not has_docs:
            response = (
                "I couldn't find indexed document chunks in this chat session yet. "
                "Please upload a PDF in this session, then ask your document question again."
            )
        elif has_docs:
            # RAG mode: documents found → generate answer from docs.
            rag_prompt = build_rag_prompt(message, history, docs)
            initial_answer = call_llm(rag_prompt)

            if ENABLE_RAG_REFINE:
                # Try to refine the answer, but keep the initial answer if refinement fails.
                try:
                    refine_prompt = build_refine_prompt(message, initial_answer, docs)
                    response = call_llm(refine_prompt)
                except LLMServiceError:
                    response = initial_answer
            else:
                response = initial_answer
        else:
            # Normal chatbot mode: no relevant docs, just chat.
            chat_prompt = build_chat_prompt(message, history)
            response = call_llm(chat_prompt)
    except LLMServiceError as err:
        app.logger.warning("LLM request failed: %s", err)
        response = str(err) or "The AI provider is temporarily unavailable."

    # Save messages to Supabase
    try:
        save_message(session_id, "user", message)
        save_message(session_id, "assistant", response)
    except Exception as err:
        app.logger.warning("Failed to persist messages for session %s: %s", session_id, err)

    return jsonify({
        "response": response,
        "session_id": session_id,
        "mode": "rag" if has_docs else "chat",
    })


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    session_id = request.form.get("session_id", "")

    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        # Extract text from PDF
        text = extract_pdf_text(filepath)

        # Chunk the text
        chunks = chunk_text(text, chunk_size=500, overlap=50)

        # Embed chunks in batches to reduce latency and provider round trips.
        vectors = get_embeddings(chunks, input_type="passage")
        pinecone_vectors = []

        # Store each chunk with session metadata
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            doc_id = f"{filename}_{i}_{uuid.uuid4().hex[:8]}"
            metadata = {
                "text": chunk,
                "source": filename,
                "session_id": session_id,
            }
            pinecone_vectors.append((doc_id, vector, metadata))

        upsert_embeddings(pinecone_vectors)

        return jsonify({
            "message": f"Uploaded and processed {filename}",
            "chunks": len(chunks),
        })
    finally:
        # Clean up uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)


def extract_pdf_text(filepath):
    """Extract all text from a PDF file."""
    text = ""
    with open(filepath, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def chunk_text(text, chunk_size=500, overlap=50):
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
