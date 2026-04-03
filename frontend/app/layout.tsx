import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Doc Updater",
  description: "AI-powered documentation update assistant for OpenAI Agents SDK",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen text-gray-900 font-sans">
        <header className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            <a href="/" className="text-xl font-bold text-gray-900">
              Doc Updater
            </a>
            <nav className="flex gap-6 text-sm text-gray-600">
              <a href="/" className="hover:text-gray-900">New Query</a>
              <a href="/saved" className="hover:text-gray-900">Saved</a>
            </nav>
          </div>
        </header>
        <main className="max-w-4xl mx-auto px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
