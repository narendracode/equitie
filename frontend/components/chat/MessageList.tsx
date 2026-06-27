"use client";

import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message, ActiveTool } from "@/hooks/useChatStream";
import { ThinkingPanel } from "./ThinkingPanel";
import { ToolStatusChip } from "./ToolStatusChip";

// Markdown component overrides — styled without requiring @tailwindcss/typography
const mdComponents = {
  h1: ({ children }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h1 className="text-base font-bold mt-3 mb-1">{children}</h1>
  ),
  h2: ({ children }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="text-sm font-bold mt-3 mb-1">{children}</h2>
  ),
  h3: ({ children }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>
  ),
  p: ({ children }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="mb-2 leading-relaxed last:mb-0">{children}</p>
  ),
  strong: ({ children }: React.HTMLAttributes<HTMLElement>) => (
    <strong className="font-semibold">{children}</strong>
  ),
  ul: ({ children }: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="list-disc list-inside mb-2 space-y-0.5">{children}</ul>
  ),
  ol: ({ children }: React.HTMLAttributes<HTMLOListElement>) => (
    <ol className="list-decimal list-inside mb-2 space-y-0.5">{children}</ol>
  ),
  li: ({ children }: React.HTMLAttributes<HTMLLIElement>) => (
    <li className="leading-relaxed">{children}</li>
  ),
  table: ({ children }: React.HTMLAttributes<HTMLTableElement>) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <thead className="bg-gray-50">{children}</thead>
  ),
  th: ({ children }: React.HTMLAttributes<HTMLTableCellElement>) => (
    <th className="border border-gray-200 px-3 py-1.5 text-left font-semibold text-gray-700 whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }: React.HTMLAttributes<HTMLTableCellElement>) => (
    <td className="border border-gray-200 px-3 py-1.5 text-gray-700">{children}</td>
  ),
  blockquote: ({ children }: React.HTMLAttributes<HTMLElement>) => (
    <blockquote className="border-l-4 border-indigo-200 pl-3 my-2 text-gray-600 italic">
      {children}
    </blockquote>
  ),
  code: ({ children, className }: React.HTMLAttributes<HTMLElement>) => {
    const isBlock = className?.includes("language-");
    return isBlock ? (
      <pre className="bg-gray-100 rounded p-3 my-2 overflow-x-auto text-xs">
        <code>{children}</code>
      </pre>
    ) : (
      <code className="bg-gray-100 rounded px-1 py-0.5 text-xs font-mono">{children}</code>
    );
  },
  hr: () => <hr className="my-3 border-gray-200" />,
};

export function MessageList({
  messages,
  activeTools,
  isStreaming,
}: {
  messages: Message[];
  activeTools: ActiveTool[];
  isStreaming: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activeTools]);

  return (
    <div className="flex flex-col gap-4 py-6 px-2">
      {messages.map((msg, i) => {
        const isLastAssistant =
          msg.role === "assistant" && i === messages.length - 1;

        if (msg.role === "user") {
          return (
            <div key={msg.id} className="flex justify-end">
              <div className="max-w-[75%] bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm whitespace-pre-wrap">
                {msg.content}
              </div>
            </div>
          );
        }

        return (
          <div key={msg.id} className="flex justify-start">
            <div className="max-w-[85%] space-y-1">
              {msg.thinking && (
                <ThinkingPanel
                  content={msg.thinking}
                  isStreaming={isLastAssistant && isStreaming}
                />
              )}

              {isLastAssistant && activeTools.length > 0 && (
                <div className="mb-2 space-y-1">
                  {activeTools.map((t) => (
                    <ToolStatusChip key={t.tool} label={t.label} />
                  ))}
                </div>
              )}

              {msg.content ? (
                <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={mdComponents as Record<string, React.ComponentType>}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              ) : isLastAssistant && isStreaming ? (
                <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3">
                  <span className="inline-flex gap-1">
                    <span
                      className="animate-bounce w-1.5 h-1.5 bg-gray-400 rounded-full"
                      style={{ animationDelay: "0ms" }}
                    />
                    <span
                      className="animate-bounce w-1.5 h-1.5 bg-gray-400 rounded-full"
                      style={{ animationDelay: "150ms" }}
                    />
                    <span
                      className="animate-bounce w-1.5 h-1.5 bg-gray-400 rounded-full"
                      style={{ animationDelay: "300ms" }}
                    />
                  </span>
                </div>
              ) : null}
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
