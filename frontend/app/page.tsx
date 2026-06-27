"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Investor = {
  investor_id: string;
  investor_name: string;
  reporting_currency: string;
};

type InvestorDetail = {
  investor_id: string;
  investor_name: string;
  investor_type: string;
  country: string;
  reporting_currency: string;
  kyc_status: string;
  tech_savviness: string;
  deal_count: number;
  top_sectors: { sector: string; deals: number }[];
};

type PlatformStats = {
  investors: number;
  deals: number;
  companies: number;
};

const CURRENCY_SYMBOL: Record<string, string> = {
  GBP: "£", USD: "$", EUR: "€", AED: "د.إ",
};

const AI_CAPABILITIES = [
  { icon: "📊", label: "Portfolio summary", desc: "MOIC, DPI, RVPI across all positions" },
  { icon: "📅", label: "Upcoming obligations", desc: "Capital calls and fees with due dates" },
  { icon: "📈", label: "Valuation history", desc: "Full mark history per company and round" },
  { icon: "💸", label: "Distributions", desc: "Gross, carry withheld, net proceeds" },
  { icon: "💱", label: "Multi-currency reporting", desc: "GBP, USD, EUR, AED — always converted" },
  { icon: "🔍", label: "Natural language", desc: "No forms — just ask in plain English" },
];

export default function Home() {
  const router = useRouter();

  const [investors, setInvestors] = useState<Investor[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [selected, setSelected] = useState("");
  const [profile, setProfile] = useState<InvestorDetail | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [loadError, setLoadError] = useState(false);

  // Load dropdown + platform stats on mount
  useEffect(() => {
    Promise.all([
      fetch(`${API}/chat/investors`).then((r) => r.json()),
      fetch(`${API}/investors?limit=1`).then((r) => r.json()),
      fetch(`${API}/deals?limit=1`).then((r) => r.json()),
      fetch(`${API}/portfolio-companies`).then((r) => r.json()),
    ])
      .then(([inv, investors, deals, companies]) => {
        setInvestors(inv);
        setStats({
          investors: investors.total ?? 0,
          deals: deals.total ?? 0,
          companies: companies.total ?? 0,
        });
      })
      .catch(() => setLoadError(true));
  }, []);

  // Fetch profile preview when investor is selected
  useEffect(() => {
    if (!selected) { setProfile(null); return; }
    setProfileLoading(true);
    fetch(`${API}/investors/${selected}`)
      .then((r) => r.json())
      .then((data) => { setProfile(data); setProfileLoading(false); })
      .catch(() => setProfileLoading(false));
  }, [selected]);

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
    <div className="py-8 space-y-6">

      {/* ── Simulation notice ─────────────────────────────────────── */}
      <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
        <span className="text-base mt-0.5">🧪</span>
        <div>
          <span className="font-semibold">Simulation environment — </span>
          investor selection below replaces a real login flow. In production each
          investor authenticates individually and only sees their own portfolio.
          No real capital or positions are represented.
        </div>
      </div>

      {/* ── Page header ───────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Investor Portal</h1>
        <p className="text-sm text-gray-500 mt-1">
          AI-powered portfolio intelligence — ask anything about your investments in plain English.
        </p>
      </div>

      {/* ── Two-column body ───────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* LEFT — Simulated sign-in */}
        <div className="lg:col-span-7 space-y-4">

          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Sign in as investor</h2>
              <p className="text-xs text-gray-500 mt-1">
                Select a profile to load a personalised session. The assistant adapts its
                tone and depth to each investor's experience level.
              </p>
            </div>

            {loadError ? (
              <p className="text-sm text-red-500">
                Could not reach the API — is Docker running?
              </p>
            ) : (
              <div className="space-y-3">
                <label className="block text-xs font-medium text-gray-600 uppercase tracking-wide">
                  Choose investor
                </label>
                <select
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                >
                  <option value="">— select an investor —</option>
                  {investors.map((inv) => (
                    <option key={inv.investor_id} value={inv.investor_id}>
                      {inv.investor_name} ({inv.reporting_currency})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Investor profile preview */}
            {selected && (
              <div className="rounded-lg border border-indigo-100 bg-indigo-50 p-4">
                {profileLoading ? (
                  <div className="flex items-center gap-2 text-sm text-indigo-400">
                    <span className="animate-pulse">●</span> Loading profile…
                  </div>
                ) : profile ? (
                  <div className="space-y-3">
                    {/* Name row */}
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
                        {profile.investor_name.charAt(0)}
                      </div>
                      <div className="min-w-0">
                        <div className="font-semibold text-gray-900 text-sm">
                          {profile.investor_name}
                        </div>
                        <div className="text-xs text-gray-500 flex items-center gap-2 flex-wrap">
                          <span>{profile.investor_type}</span>
                          <span>·</span>
                          <span>{profile.country}</span>
                          <span>·</span>
                          <span>
                            Reports in{" "}
                            <strong>{CURRENCY_SYMBOL[profile.reporting_currency] ?? ""}{profile.reporting_currency}</strong>
                          </span>
                        </div>
                      </div>
                      <div className="ml-auto flex-shrink-0">
                        <span
                          className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                            profile.kyc_status === "Verified"
                              ? "bg-green-100 text-green-700"
                              : "bg-amber-100 text-amber-700"
                          }`}
                        >
                          {profile.kyc_status}
                        </span>
                      </div>
                    </div>

                    {/* Stats row */}
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="bg-white rounded-md px-3 py-2 border border-indigo-100">
                        <div className="text-gray-500">Active positions</div>
                        <div className="font-semibold text-gray-900 mt-0.5">
                          {profile.deal_count > 0 ? `${profile.deal_count} deal${profile.deal_count !== 1 ? "s" : ""}` : "No positions yet"}
                        </div>
                      </div>
                      <div className="bg-white rounded-md px-3 py-2 border border-indigo-100">
                        <div className="text-gray-500">Experience level</div>
                        <div className="font-semibold text-gray-900 mt-0.5 capitalize">
                          {profile.tech_savviness}
                        </div>
                      </div>
                    </div>

                    {/* Top sectors */}
                    {profile.top_sectors.length > 0 && (
                      <div>
                        <div className="text-xs text-gray-500 mb-1.5">Top sectors</div>
                        <div className="flex flex-wrap gap-1.5">
                          {profile.top_sectors.slice(0, 3).map((s) => (
                            <span
                              key={s.sector}
                              className="text-xs bg-white border border-indigo-200 text-indigo-700 px-2 py-0.5 rounded-full"
                            >
                              {s.sector}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            )}

            <button
              onClick={startChat}
              disabled={!selected || starting}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-200 disabled:text-indigo-400 text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
            >
              {starting ? "Opening session…" : "Enter portfolio →"}
            </button>
          </div>
        </div>

        {/* RIGHT — Platform overview */}
        <div className="lg:col-span-5 space-y-4">

          {/* Platform stats */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-4">
              Platform overview
            </h2>
            {stats ? (
              <div className="grid grid-cols-3 gap-3 text-center">
                <StatCard value={stats.investors} label="Investors" color="indigo" />
                <StatCard value={stats.companies} label="Companies" color="violet" />
                <StatCard value={stats.deals} label="Deals" color="sky" />
              </div>
            ) : (
              <div className="text-sm text-gray-400 animate-pulse">Loading…</div>
            )}
          </div>

          {/* AI capabilities */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-1">
              What you can ask
            </h2>
            <p className="text-xs text-gray-500 mb-4">
              The assistant has read access to full portfolio data and answers in
              real time with no hallucinated figures.
            </p>
            <ul className="space-y-3">
              {AI_CAPABILITIES.map((c) => (
                <li key={c.label} className="flex items-start gap-3">
                  <span className="text-base mt-0.5 flex-shrink-0">{c.icon}</span>
                  <div>
                    <div className="text-xs font-medium text-gray-800">{c.label}</div>
                    <div className="text-xs text-gray-500">{c.desc}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>

        </div>
      </div>
    </div>
  );
}

function StatCard({
  value,
  label,
  color,
}: {
  value: number;
  label: string;
  color: "indigo" | "violet" | "sky";
}) {
  const bg = { indigo: "bg-indigo-50", violet: "bg-violet-50", sky: "bg-sky-50" }[color];
  const text = { indigo: "text-indigo-700", violet: "text-violet-700", sky: "text-sky-700" }[color];
  return (
    <div className={`${bg} rounded-lg py-3 px-2`}>
      <div className={`text-2xl font-bold ${text}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
    </div>
  );
}
