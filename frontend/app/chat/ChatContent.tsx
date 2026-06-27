"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useChatStream } from "@/hooks/useChatStream";
import { MessageList } from "@/components/chat/MessageList";
import { ChatInput } from "@/components/chat/ChatInput";

const STARTER_PROMPTS = [
  "Give me an overview of my portfolio",
  "What are my upcoming obligations?",
  "How have my investments performed so far?",
  "Show me my account statement",
];

export function ChatContent() {
  const params = useSearchParams();
  const router = useRouter();

  const sessionId = params.get("session") ?? "";
  const investorName = params.get("name") ?? "Investor";
  const currency = params.get("currency") ?? "USD";

  // Redirect to home if no session
  if (!sessionId) {
    router.replace("/");
    return null;
  }

  const { messages, isStreaming, activeTools, error, sendMessage } =
    useChatStream(sessionId);

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 57px)" }}>
      {/* Session info bar */}
      <div className="flex items-center gap-3 py-3 border-b border-gray-200 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-semibold text-sm">
            {investorName.charAt(0)}
          </div>
          <div>
            <div className="text-sm font-medium text-gray-900">{investorName}</div>
            <div className="text-xs text-gray-500">Reporting in {currency}</div>
          </div>
        </div>
        <button
          onClick={() => router.push("/")}
          className="ml-auto text-xs text-gray-400 hover:text-gray-600"
        >
          Change investor
        </button>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-6 px-4">
            <div className="text-center">
              <div className="text-2xl mb-2">👋</div>
              <h2 className="text-lg font-semibold text-gray-800">
                Hello, {investorName.split(" ")[0]}
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Ask me anything about your portfolio.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => sendMessage(prompt)}
                  disabled={isStreaming}
                  className="text-left text-sm bg-white border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 rounded-xl px-4 py-3 transition-colors text-gray-700"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <MessageList
            messages={messages}
            activeTools={activeTools}
            isStreaming={isStreaming}
          />
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-2 mb-2 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex-shrink-0">
          {error}
        </div>
      )}

      {/* Input */}
      <div className="flex-shrink-0 pb-4 pt-2">
        <ChatInput onSend={sendMessage} disabled={isStreaming} />
      </div>
    </div>
  );
}
