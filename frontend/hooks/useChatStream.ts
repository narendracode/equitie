"use client";

import { useState, useRef, useCallback, useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking: string;
};

export type ActiveTool = {
  tool: string;
  label: string;
};

export function useChatStream(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTools, setActiveTools] = useState<ActiveTool[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Accumulate streaming content without triggering per-char re-renders
  const streamingRef = useRef({ content: "", thinking: "", assistantId: "" });
  const esRef = useRef<EventSource | null>(null);
  // Flush interval so the UI updates in batches (~16ms)
  const flushRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startFlush = (assistantId: string) => {
    flushRef.current = setInterval(() => {
      const { content, thinking } = streamingRef.current;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content, thinking } : m
        )
      );
    }, 50);
  };

  const stopFlush = () => {
    if (flushRef.current) {
      clearInterval(flushRef.current);
      flushRef.current = null;
    }
  };

  // Clean up EventSource and flush interval on unmount
  useEffect(() => {
    return () => {
      esRef.current?.close();
      stopFlush();
    };
  }, []);

  const sendMessage = useCallback(
    (text: string) => {
      if (isStreaming || !text.trim()) return;

      const userId = crypto.randomUUID();
      const assistantId = crypto.randomUUID();

      streamingRef.current = { content: "", thinking: "", assistantId };

      setMessages((prev) => [
        ...prev,
        { id: userId, role: "user", content: text, thinking: "" },
        { id: assistantId, role: "assistant", content: "", thinking: "" },
      ]);
      setIsStreaming(true);
      setError(null);
      setActiveTools([]);

      startFlush(assistantId);

      const url = `${API}/chat/${sessionId}/stream?message=${encodeURIComponent(text)}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case "thinking_delta":
              streamingRef.current.thinking += data.content;
              break;

            case "token":
              streamingRef.current.content += data.content;
              break;

            case "tool_start":
              setActiveTools((prev) => [
                ...prev,
                { tool: data.tool, label: data.label },
              ]);
              break;

            case "tool_end":
              setActiveTools((prev) =>
                prev.filter((t) => t.tool !== data.tool)
              );
              break;

            case "done":
              es.close();
              esRef.current = null;
              stopFlush();
              // Final flush with complete content
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: streamingRef.current.content,
                        thinking: streamingRef.current.thinking,
                      }
                    : m
                )
              );
              setIsStreaming(false);
              setActiveTools([]);
              break;

            case "error":
              es.close();
              esRef.current = null;
              stopFlush();
              setIsStreaming(false);
              setActiveTools([]);
              setError(data.content ?? "An error occurred");
              break;
          }
        } catch {
          // ignore JSON parse errors on malformed chunks
        }
      };

      es.onerror = () => {
        es.close();
        esRef.current = null;
        stopFlush();
        setIsStreaming(false);
        setActiveTools([]);
        if (!streamingRef.current.content) {
          setError("Connection error — please try again");
        }
      };
    },
    [sessionId, isStreaming]
  );

  return { messages, isStreaming, activeTools, error, sendMessage };
}
