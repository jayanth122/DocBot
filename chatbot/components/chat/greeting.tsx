"use client";

export function Greeting() {
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <h2 className="text-2xl font-semibold text-foreground">
        Welcome to DocBot
      </h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        Upload a PDF and ask questions about it, or start a conversation.
      </p>
    </div>
  );
}
