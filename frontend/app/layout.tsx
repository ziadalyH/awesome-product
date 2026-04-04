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
        <main>{children}</main>
      </body>
    </html>
  );
}
