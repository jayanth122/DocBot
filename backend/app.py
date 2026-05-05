import os
import uuid

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import PyPDF2

from services.llm import call_llm
from services.rag import (
    build_chat_prompt, build_rag_prompt, build_refine_prompt,
    retrieve_docs, retrieve_all_session_docs, has_relevant_docs, is_doc_reference,
)
from services.embeddings import get_embedding
from services.pinecone_client import upsert_embedding, delete_session_embeddings
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
        session = create_session(user_id)
        session_id = session["id"]

    # Fetch chat history
    history = get_messages(session_id)

    # Determine retrieval strategy
    docs = []
    if is_doc_reference(message):
        # User is referring to their uploaded doc — fetch all session chunks
        docs = retrieve_all_session_docs(session_id)
    
    if not docs:
        # Try semantic search filtered by session
        docs = retrieve_docs(message, session_id=session_id)

    if has_relevant_docs(docs):
        # RAG mode: documents found → generate answer from docs, then refine
        rag_prompt = build_rag_prompt(message, history, docs)
        initial_answer = call_llm(rag_prompt)

        # Refine the answer for clarity and accuracy
        refine_prompt = build_refine_prompt(message, initial_answer, docs)
        response = call_llm(refine_prompt)
    else:
        # Normal chatbot mode: no relevant docs, just chat
        chat_prompt = build_chat_prompt(message, history)
        response = call_llm(chat_prompt)

    # Save messages to Supabase
    save_message(session_id, "user", message)
    save_message(session_id, "assistant", response)

    return jsonify({
        "response": response,
        "session_id": session_id,
        "mode": "rag" if has_relevant_docs(docs) else "chat",
    })


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    session_id = request.form.get("session_id", "")
    
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

        # Embed and store each chunk with session metadata
        for i, chunk in enumerate(chunks):
            vector = get_embedding(chunk)
            doc_id = f"{filename}_{i}_{uuid.uuid4().hex[:8]}"
            metadata = {
                "text": chunk,
                "source": filename,
                "session_id": session_id,
            }
            upsert_embedding(doc_id, vector, metadata)

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
