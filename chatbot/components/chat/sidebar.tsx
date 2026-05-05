"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseClient } from "@/lib/supabase";
import type { Session, User } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  PanelLeftIcon,
  PlusIcon,
  MessageSquareIcon,
  LogOutIcon,
  Trash2Icon,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

interface ChatSidebarProps {
  user: User;
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
  onToggle: () => void;
}

export function ChatSidebar({
  user,
  currentSessionId,
  onSelectSession,
  onNewChat,
  isOpen,
  onToggle,
}: ChatSidebarProps) {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const supabase = getSupabaseClient();

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_URL}/sessions?user_id=${user.id}`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch (err) {
      console.error("Failed to fetch sessions:", err);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [user.id, currentSessionId]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.push("/login");
  };

  const handleDeleteSession = async (sessionId: string) => {
    const confirmed = window.confirm("Delete this chat permanently?");
    if (!confirmed) return;

    setDeletingSessionId(sessionId);
    try {
      const res = await fetch(
        `${API_URL}/sessions/${sessionId}?user_id=${encodeURIComponent(user.id)}`,
        { method: "DELETE" }
      );

      if (!res.ok) {
        throw new Error("Failed to delete session");
      }

      setSessions((prev) => prev.filter((session) => session.id !== sessionId));
      if (currentSessionId === sessionId) {
        onNewChat();
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    } finally {
      setDeletingSessionId(null);
    }
  };

  return (
    <div
      className={cn(
        "flex h-full flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300",
        isOpen ? "w-64" : "w-0 overflow-hidden"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3">
        <span className="text-sm font-semibold text-sidebar-foreground">
          DocBot
        </span>
        <button
          onClick={onToggle}
          className="rounded-md p-1.5 text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <PanelLeftIcon className="size-4" />
        </button>
      </div>

      {/* New Chat */}
      <div className="px-2 pb-2">
        <button
          onClick={onNewChat}
          className="flex h-9 w-full items-center gap-2 rounded-lg border border-sidebar-border px-3 text-sm text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <PlusIcon className="size-4" />
          <span>New chat</span>
        </button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto px-2">
        <div className="space-y-0.5">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={cn(
                "group flex items-center gap-1 rounded-lg px-1 py-1 text-sm transition-colors",
                currentSessionId === session.id
                  ? "bg-sidebar-accent text-sidebar-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50"
              )}
            >
              <button
                onClick={() => onSelectSession(session.id)}
                className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-1 py-1 text-left"
              >
                <MessageSquareIcon className="size-4 shrink-0" />
                <span className="truncate">
                  {session.title || new Date(session.created_at).toLocaleDateString()}
                </span>
              </button>

              <button
                onClick={() => handleDeleteSession(session.id)}
                disabled={deletingSessionId === session.id}
                className="flex size-7 shrink-0 items-center justify-center rounded-md text-sidebar-foreground/50 opacity-0 transition hover:bg-sidebar-accent hover:text-destructive group-hover:opacity-100 disabled:opacity-50"
                title="Delete chat"
              >
                <Trash2Icon className="size-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Footer - User */}
      <div className="border-t border-sidebar-border px-2 py-3">
        <div className="flex items-center justify-between">
          <span className="truncate text-xs text-sidebar-foreground/60">
            {user.email}
          </span>
          <button
            onClick={handleLogout}
            className="rounded-md p-1.5 text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-foreground"
            title="Sign out"
          >
            <LogOutIcon className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
