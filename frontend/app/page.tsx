"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Investor = {
  investor_id: string;
  investor_name: string;
  reporting_currency: string;
};

export default function Home() {
  const router = useRouter();
  const [investors, setInvestors] = useState<Investor[]>([]);
  const [selected, setSelected] = useState("");
  const [starting, setStarting] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    fetch(`${API}/chat/investors`)
      .then((r) => r.json())
      .then(setInvestors)
      .catch(() => setLoadError(true));
  }, []);

  const startChat = async () => {
    if (!selected || starting) return;
    setStarting(true);
    try {
      const res = await fetch(`${API}/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ investor_id: selected }),
      });
      const data = await res.json();
      const params = new URLSearchParams({
        session: data.session_id,
        name: data.investor_name,
        currency: data.reporting_currency,
      });
      router.push(`/chat?${params}`);
    } catch {
      setStarting(false);
    }
  };

  return (
    <div className="py-12 max-w-2xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Investor Assistant</h1>
        <p className="text-gray-500 mt-2">
          Select an investor to start a personalised AI-powered portfolio conversation.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-8 space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select investor
          </label>
          {loadError ? (
            <p className="text-sm text-red-500">Could not load investors — is the API running?</p>
          ) : (
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">— choose an investor —</option>
              {investors.map((inv) => (
                <option key={inv.investor_id} value={inv.investor_id}>
                  {inv.investor_name} ({inv.reporting_currency})
                </option>
              ))}
            </select>
          )}
        </div>

        <button
          onClick={startChat}
          disabled={!selected || starting}
          className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
        >
          {starting ? "Starting session…" : "Start Chat →"}
        </button>
      </div>

      <div className="mt-8 grid grid-cols-3 gap-4 text-center text-sm text-gray-500">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="font-semibold text-gray-800 text-lg">112</div>
          <div>Investors</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="font-semibold text-gray-800 text-lg">21</div>
          <div>Deals</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="font-semibold text-gray-800 text-lg">16</div>
          <div>Companies</div>
        </div>
      </div>
    </div>
  );
}
