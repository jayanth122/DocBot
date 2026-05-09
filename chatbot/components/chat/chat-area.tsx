"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Message, User } from "@/lib/types";
import { cn, generateId } from "@/lib/utils";
import { apiFetch, apiFetchJson, toUserFacingError } from "@/lib/api";
import { ChatInput } from "./chat-input";
import { Greeting } from "./greeting";
import { PanelLeftIcon } from "lucide-react";

interface ChatAreaProps {
  user: User;
  sessionId: string | null;
  onSessionCreated: (id: string) => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export function ChatArea({
  user,
  sessionId,
  onSessionCreated,
  sidebarOpen,
  onToggleSidebar,
}: ChatAreaProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Load messages when session changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }

    const loadMessages = async () => {
      try {
        const data = await apiFetchJson<Message[]>(`/messages?session_id=${sessionId}`);
        setMessages(data);
      } catch (err) {
        console.error("Failed to load messages:", err);
      }
    };

    loadMessages();
  }, [sessionId]);

  // Scroll to bottom on new messages
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = useCallback(
    async (input: string) => {
      if (!input.trim()) return;

      setIsLoading(true);

      // Optimistic user message
      const userMsg: Message = {
        id: generateId(),
        role: "user",
        content: input,
      };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const data = await apiFetchJson<{ response: string; session_id: string }>(`/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: input,
            session_id: sessionId,
            user_id: user.id,
          }),
        });

        // If a new session was created
        if (!sessionId && data.session_id) {
          onSessionCreated(data.session_id);
        }

        const assistantMsg: Message = {
          id: generateId(),
          role: "assistant",
          content: data.response,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err: unknown) {
        console.error("Chat error:", err);
        const errorMsg: Message = {
          id: generateId(),
          role: "assistant",
          content: toUserFacingError(err),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, user.id, onSessionCreated]
  );

  const handleUpload = useCallback(
    async (file: File) => {
      // Ensure we have a session
      let activeSessionId = sessionId;
      if (!activeSessionId) {
        try {
          const data = await apiFetchJson<{ id: string }>(`/sessions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: user.id }),
          });
          activeSessionId = data.id;
          onSessionCreated(data.id);
        } catch (err) {
          console.error("Failed to create session:", err);
          const errorMsg: Message = {
            id: generateId(),
            role: "assistant",
            content: toUserFacingError(err),
          };
          setMessages((prev) => [...prev, errorMsg]);
          return;
        }
      }

      const formData = new FormData();
      formData.append("file", file);
      formData.append("session_id", activeSessionId!);

      // Show upload message
      const uploadMsg: Message = {
        id: generateId(),
        role: "user",
        content: `📎 Uploading: ${file.name}`,
      };
      setMessages((prev) => [...prev, uploadMsg]);
      setIsLoading(true);

      try {
        const data = await apiFetchJson<{ message: string; chunks: number }>(`/upload`, {
          method: "POST",
          body: formData,
        });

        const resultMsg: Message = {
          id: generateId(),
          role: "assistant",
          content: `✅ ${data.message} (${data.chunks} chunks indexed). You can now ask questions about this document.`,
        };
        setMessages((prev) => [...prev, resultMsg]);
      } catch (err: unknown) {
        const errorMsg: Message = {
          id: generateId(),
          role: "assistant",
          content: toUserFacingError(err),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, user.id, onSessionCreated]
  );

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Header */}
      <header className="flex h-12 items-center gap-2 border-b border-border px-4">
        {!sidebarOpen && (
          <button
            onClick={onToggleSidebar}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <PanelLeftIcon className="size-4" />
          </button>
        )}
        <h2 className="text-sm font-medium text-foreground">Chat</h2>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 && !isLoading ? (
          <div className="flex h-full items-center justify-center">
            <Greeting />
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isLoading && <ThinkingIndicator />}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border px-4 py-3">
        <div className="mx-auto max-w-3xl">
          <ChatInput
            onSend={handleSend}
            onUpload={handleUpload}
            isLoading={isLoading}
          />
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <SparklesIcon />
        </div>
      )}

      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        )}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  );
}

function ThinkingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        <SparklesIcon />
      </div>
      <div className="flex items-center gap-1 rounded-2xl bg-muted px-4 py-2.5">
        <div className="size-2 animate-pulse rounded-full bg-muted-foreground" />
        <div className="size-2 animate-pulse rounded-full bg-muted-foreground [animation-delay:150ms]" />
        <div className="size-2 animate-pulse rounded-full bg-muted-foreground [animation-delay:300ms]" />
      </div>
    </div>
  );
}

function SparklesIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="currentColor"
    >
      <path d="M8 0L9.5 5.5L15 7L9.5 8.5L8 14L6.5 8.5L1 7L6.5 5.5L8 0Z" />
    </svg>
  );
}
