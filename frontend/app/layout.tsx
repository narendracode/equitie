import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "EquiTie",
  description: "AI-powered investor platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">
        <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-xl font-bold tracking-tight text-indigo-600">EquiTie</span>
            <span className="text-sm text-gray-400">investor platform</span>
          </Link>
          <nav className="flex items-center gap-4 ml-auto text-sm">
            <Link href="/" className="text-gray-600 hover:text-gray-900">
              Dashboard
            </Link>
            <Link
              href="/"
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-md font-medium"
            >
              Start Chat
            </Link>
          </nav>
        </header>
        <main className="max-w-7xl mx-auto px-6">{children}</main>
      </body>
    </html>
  );
}
