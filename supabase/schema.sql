-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sessions table
CREATE TABLE sessions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid,
  created_at timestamp DEFAULT now()
);

-- Messages table
CREATE TABLE messages (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id uuid REFERENCES sessions(id) ON DELETE CASCADE,
  role text NOT NULL,
  content text NOT NULL,
  created_at timestamp DEFAULT now()
);

-- Index for faster queries
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_messages_session_id ON messages(session_id);

-- Enable Row Level Security
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Policies: users can only access their own sessions
CREATE POLICY "Users can view own sessions"
  ON sessions FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create own sessions"
  ON sessions FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Policies: users can access messages in their sessions
CREATE POLICY "Users can view messages in own sessions"
  ON messages FOR SELECT
  USING (session_id IN (SELECT id FROM sessions WHERE user_id = auth.uid()));

CREATE POLICY "Users can insert messages in own sessions"
  ON messages FOR INSERT
  WITH CHECK (session_id IN (SELECT id FROM sessions WHERE user_id = auth.uid()));
