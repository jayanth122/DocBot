# DocBot

AI-powered document assistant with chat history, PDF upload, and RAG (Retrieval-Augmented Generation).

## Stack

- Frontend: Next.js 16 (`chatbot/`)
- Backend: Flask (`backend/`)
- Auth + DB: Supabase
- Vector DB: Pinecone
- LLM: OpenRouter

## Features

- Email/password login via Supabase
- Chat history sidebar by user session
- PDF upload and chunked indexing to Pinecone
- Session-scoped RAG answers
- Delete chat from sidebar (also deletes messages/session from Supabase and vectors from Pinecone)

## Project Structure

- `chatbot/`: Next.js UI
- `backend/`: Flask API and RAG pipeline
- `supabase/schema.sql`: DB schema and RLS policies

## Prerequisites

- Python 3.10+
- Node.js 20+
- Supabase project
- Pinecone project/index
- OpenRouter API key

## 1. Supabase Setup

1. Create a project at https://supabase.com
2. Enable Email/Password auth.
3. Run the SQL in `supabase/schema.sql`.

## 2. Pinecone Setup

Create an index at https://pinecone.io compatible with `llama-text-embed-v2` embeddings.

- Metric: `cosine`
- Dimensions: `1024`

## 3. Backend Setup (`backend/`)

Install and configure:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set these variables in `backend/.env`:

```env
OPENROUTER_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
PINECONE_API_KEY=
PINECONE_INDEX_NAME=
LLM_MAX_RETRIES=1
LLM_REQUEST_TIMEOUT_SECONDS=20
LLM_TOTAL_TIMEOUT_SECONDS=35
```

Run backend:

```bash
cd backend
source venv/bin/activate
python app.py
```

Backend runs at `http://localhost:5001`.

## 4. Frontend Setup (`chatbot/`)

Install and configure:

```bash
cd chatbot
npm install
```

Create `chatbot/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:5001
```

Run frontend:

```bash
cd chatbot
npm run dev
```

Frontend runs at `http://localhost:3000`.

## API Endpoints

- `GET /health`
- `POST /sessions`
- `GET /sessions`
- `DELETE /sessions/<session_id>?user_id=<user_id>`
- `GET /messages`
- `POST /chat`
- `POST /upload`

## Local Run Checklist

1. Start backend in `backend/` with activated venv.
2. Start frontend in `chatbot/`.
3. Open `http://localhost:3000` and sign in.
