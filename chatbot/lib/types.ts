export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
}

export interface Session {
  id: string;
  user_id: string;
  title?: string;
  created_at: string;
}

export interface User {
  id: string;
  email: string;
}
