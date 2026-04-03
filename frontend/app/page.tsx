"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Something went wrong");
      }

      const session = await res.json();
      router.push(`/review?session=${session.session_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to get suggestions");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-gray-900 mb-3">
          Documentation Update Assistant
        </h1>
        <p className="text-gray-500 text-lg">
          Describe a change to the OpenAI Agents SDK and get AI-powered
          documentation update suggestions.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            What changed or what do you want to update?
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Example: "We don't support agents as_tool anymore, other agents should only be invoked via handoff"`}
            rows={5}
            className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="w-full rounded-lg bg-blue-600 text-white font-medium py-3 px-6 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Analyzing documentation…
            </span>
          ) : (
            "Get Suggestions"
          )}
        </button>
      </form>

      <div className="mt-10 p-4 rounded-lg bg-blue-50 border border-blue-100 text-sm text-blue-700">
        <strong>How it works:</strong> The AI reads the OpenAI Agents SDK documentation,
        identifies sections affected by your change, and suggests precise edits. You can
        then review, edit, approve, or reject each suggestion before saving.
      </div>
    </div>
  );
}
