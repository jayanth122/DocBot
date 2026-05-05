import os
from supabase import create_client


supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY"),
)


def create_session(user_id):
    """Create a new chat session."""
    result = supabase.table("sessions").insert({"user_id": user_id}).execute()
    return result.data[0]


def get_sessions(user_id):
    """Get all sessions for a user."""
    result = (
        supabase.table("sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def save_message(session_id, role, content):
    """Save a message to the database."""
    supabase.table("messages").insert(
        {"session_id": session_id, "role": role, "content": content}
    ).execute()


def get_messages(session_id):
    """Get all messages for a session."""
    result = (
        supabase.table("messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    return result.data


def delete_session(session_id, user_id):
    """Delete a session and its messages for the given user."""
    session_result = (
        supabase.table("sessions")
        .select("id")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not session_result.data:
        return False

    supabase.table("messages").delete().eq("session_id", session_id).execute()
    supabase.table("sessions").delete().eq("id", session_id).eq("user_id", user_id).execute()
    return True
