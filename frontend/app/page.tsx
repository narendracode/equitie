const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getStats() {
  try {
    const [investors, deals, companies] = await Promise.all([
      fetch(`${API}/investors?limit=1`, { cache: "no-store" }).then((r) => r.json()),
      fetch(`${API}/deals?limit=1`, { cache: "no-store" }).then((r) => r.json()),
      fetch(`${API}/portfolio-companies`, { cache: "no-store" }).then((r) => r.json()),
    ]);
    return {
      investors: investors.total ?? 0,
      deals: deals.total ?? 0,
      companies: companies.total ?? 0,
    };
  } catch {
    return null;
  }
}

export default async function Home() {
  const stats = await getStats();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">EquiTie investor platform overview</p>
      </div>

      {stats ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard label="Investors" value={stats.investors} />
          <StatCard label="Deals" value={stats.deals} />
          <StatCard label="Portfolio Companies" value={stats.companies} />
        </div>
      ) : (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
          API is starting up — refresh in a moment.
        </div>
      )}

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="font-medium mb-2">API Endpoints</h2>
        <ul className="space-y-1 text-sm text-gray-600 font-mono">
          <li>GET /health</li>
          <li>GET /investors</li>
          <li>GET /investors/:id</li>
          <li>GET /investors/:id/allocations</li>
          <li>GET /investors/:id/statement</li>
          <li>GET /deals</li>
          <li>GET /deals/:id</li>
          <li>GET /portfolio-companies</li>
          <li>GET /portfolio-companies/:id</li>
        </ul>
        <a
          href={`${API}/docs`}
          target="_blank"
          className="mt-4 inline-block text-sm text-indigo-600 hover:underline"
        >
          Open Swagger UI →
        </a>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
    </div>
  );
}
