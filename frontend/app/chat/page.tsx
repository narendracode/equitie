import { Suspense } from "react";
import { ChatContent } from "./ChatContent";

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-[calc(100vh-57px)]">
          <div className="text-sm text-gray-400">Loading…</div>
        </div>
      }
    >
      <ChatContent />
    </Suspense>
  );
}
