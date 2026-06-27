import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EquiTie",
  description: "AI-powered investor platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">
        <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
          <span className="text-xl font-bold tracking-tight text-indigo-600">EquiTie</span>
          <span className="text-sm text-gray-400">investor platform</span>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
