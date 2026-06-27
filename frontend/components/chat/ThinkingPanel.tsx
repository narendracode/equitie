"use client";

import { useState, useEffect, useRef } from "react";

const LS_KEY = "equitie_thinking_expanded";

export function ThinkingPanel({
  content,
  isStreaming,
}: {
  content: string;
  isStreaming: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  // Load preference from localStorage after mount
  useEffect(() => {
    setExpanded(localStorage.getItem(LS_KEY) === "true");
  }, []);

  // Auto-scroll the thinking body while streaming
  useEffect(() => {
    if (expanded && isStreaming && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [content, expanded, isStreaming]);

  const toggle = () => {
    setExpanded((prev) => {
      const next = !prev;
      localStorage.setItem(LS_KEY, String(next));
      return next;
    });
  };

  if (!content) return null;

  return (
    <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 text-sm overflow-hidden">
      <button
        onClick={toggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-amber-700 hover:bg-amber-100 transition-colors text-left"
      >
        <span className="text-xs">{expanded ? "▼" : "▶"}</span>
        <span className="font-medium text-xs">See reasoning</span>
        {isStreaming && (
          <span className="ml-auto flex items-center gap-1 text-xs text-amber-500">
            <span className="animate-pulse">●</span> thinking…
          </span>
        )}
      </button>
      {expanded && (
        <div
          ref={bodyRef}
          className="px-3 pb-3 pt-1 text-amber-800 text-xs leading-relaxed whitespace-pre-wrap border-t border-amber-200 max-h-48 overflow-y-auto"
        >
          {content}
        </div>
      )}
    </div>
  );
}
