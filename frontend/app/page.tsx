"use client";

import { useState, useEffect } from "react";

/* ─── Types ──────────────────────────────────────────────────────────── */
type SuggestionStatus = "pending" | "approved" | "rejected";

interface EditSuggestion {
  id: string;
  file: string;
  section_title: string;
  current_content: string;
  suggested_content: string;
  reason: string;
  status: SuggestionStatus;
}

interface Session {
  session_id: string;
  query: string;
  suggestions: EditSuggestion[];
  saved: boolean;
  retrieval_mode: string;
}

interface DocSection {
  id: string;
  file: string;
  section_title: string;
  content: string;
  line_start: number;
  line_end: number;
}

/* ─── Status badge ───────────────────────────────────────────────────── */
function Badge({ status }: { status: SuggestionStatus }) {
  const cls = {
    pending: "bg-yellow-100 text-yellow-700",
    approved: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-600",
  }[status];
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {status}
    </span>
  );
}

/* ─── Suggestion Panel - Compact for side-by-side view ───────────────── */
function SuggestionPanel({
  suggestion,
  sessionId,
  onUpdate,
}: {
  suggestion: EditSuggestion;
  sessionId: string;
  onUpdate: (s: EditSuggestion) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(suggestion.suggested_content);
  const [tab, setTab] = useState<"current" | "suggested">("suggested");

  async function patch(body: Partial<EditSuggestion>) {
    const res = await fetch(
      `/api/sessions/${sessionId}/suggestions/${suggestion.id}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    );
    if (res.ok) onUpdate({ ...suggestion, ...body });
  }

  const borderColor =
    suggestion.status === "approved"
      ? "border-green-400"
      : suggestion.status === "rejected"
      ? "border-red-300"
      : "border-yellow-400";

  const bgColor =
    suggestion.status === "approved"
      ? "bg-green-50"
      : suggestion.status === "rejected"
      ? "bg-red-50"
      : "bg-yellow-50";

  return (
    <div
      className={`rounded-lg border-l-4 ${borderColor} ${bgColor} p-4 shadow-sm h-full flex flex-col`}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          ✨ AI Suggestion
        </span>
        <Badge status={suggestion.status} />
      </div>

      <p className="text-xs text-gray-600 mb-3">
        <span className="font-medium">Why: </span>
        {suggestion.reason}
      </p>

      {!editing && (
        <>
          <div className="flex gap-1 mb-2">
            {(["current", "suggested"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-2 py-1 text-xs rounded font-medium transition-colors ${
                  tab === t
                    ? "bg-gray-900 text-white"
                    : "bg-white border border-gray-200 text-gray-500 hover:bg-gray-50"
                }`}
              >
                {t === "current" ? "Current" : "Suggested"}
              </button>
            ))}
          </div>
          <pre className="text-xs bg-white border border-gray-200 rounded p-2 overflow-auto flex-1 whitespace-pre-wrap font-mono text-gray-700 leading-relaxed mb-3">
            {tab === "current"
              ? suggestion.current_content
              : suggestion.suggested_content}
          </pre>
        </>
      )}

      {editing && (
        <div className="mb-3 flex-1 flex flex-col">
          <p className="text-xs text-gray-500 mb-1 font-medium">
            Edit suggested content:
          </p>
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="flex-1 text-xs font-mono border border-blue-300 rounded p-2 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
        </div>
      )}

      <div className="flex gap-2 flex-wrap">
        {editing ? (
          <>
            <button
              onClick={() => {
                setEditContent(suggestion.suggested_content);
                setEditing(false);
              }}
              className="px-2 py-1 text-xs rounded border border-gray-300 hover:bg-white"
            >
              Cancel
            </button>
            <button
              onClick={async () => {
                await patch({ suggested_content: editContent });
                setEditing(false);
              }}
              className="px-2 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700"
            >
              Save
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => setEditing(true)}
              className="px-2 py-1 text-xs rounded border border-gray-300 hover:bg-white"
            >
              Edit
            </button>
            <button
              onClick={() => patch({ status: "rejected" })}
              disabled={suggestion.status === "rejected"}
              className="px-2 py-1 text-xs rounded border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-40"
            >
              Reject
            </button>
            <button
              onClick={() => patch({ status: "approved" })}
              disabled={suggestion.status === "approved"}
              className="px-2 py-1 text-xs rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-40"
            >
              Approve
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ─── Doc Section - Side by side with suggestion ─────────────────────── */
function DocBlock({
  section,
  suggestion,
  sessionId,
  onUpdate,
}: {
  section: DocSection;
  suggestion?: EditSuggestion;
  sessionId?: string;
  onUpdate?: (s: EditSuggestion) => void;
}) {
  const highlight = suggestion
    ? suggestion.status === "approved"
      ? "border-l-4 border-green-400 pl-4 bg-green-50/20"
      : suggestion.status === "rejected"
      ? "border-l-4 border-red-300 pl-4 bg-red-50/20"
      : "border-l-4 border-yellow-400 pl-4 bg-yellow-50/20"
    : "";

  if (suggestion && sessionId && onUpdate) {
    return (
      <div
        className={`mb-8 ${highlight} py-4`}
        id={`sec-${suggestion.id}`}
      >
        <h3 className="text-xl font-bold text-gray-900 mb-4">
          {section.section_title}
        </h3>
        <SuggestionPanel
          suggestion={suggestion}
          sessionId={sessionId}
          onUpdate={onUpdate}
        />
      </div>
    );
  }

  // Regular layout when no suggestion
  return (
    <div className="mb-6 py-2" id={`sec-${section.id}`}>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">
        {section.section_title}
      </h3>
      <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
        {section.content}
      </pre>
    </div>
  );
}

/* ─── Main Page ──────────────────────────────────────────────────────── */
export default function Home() {
  const [query, setQuery] = useState("");
  const [retrievalMode] = useState<"triage" | "rag" | "hybrid" | "auto">("auto");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [session, setSession] = useState<Session | null>(null);
  const [currentPage, setCurrentPage] = useState("index");
  const [sections, setSections] = useState<DocSection[]>([]);
  const [pages, setPages] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  // Load available pages
  useEffect(() => {
    fetch("/api/docs")
      .then((r) => r.json())
      .then((data: string[]) => setPages(data))
      .catch(console.error);
  }, []);

  // Load sections for current page
  useEffect(() => {
    if (!currentPage) return;
    fetch(`/api/docs/${currentPage}`)
      .then((r) => r.json())
      .then((data) => setSections(data.sections ?? []))
      .catch(console.error);
  }, [currentPage]);

  // Auto-navigate to first page with suggestions
  useEffect(() => {
    if (session && session.suggestions.length > 0) {
      const firstPage = session.suggestions[0].file;
      setCurrentPage(firstPage);
      // Scroll to first suggestion
      setTimeout(() => {
        const firstSuggestion = session.suggestions[0];
        document
          .getElementById(`sec-${firstSuggestion.id}`)
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 500);
    }
  }, [session?.session_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleUpdate = (updated: EditSuggestion) => {
    setSession((prev) =>
      prev
        ? {
            ...prev,
            suggestions: prev.suggestions.map((s) =>
              s.id === updated.id ? { ...s, ...updated } : s
            ),
          }
        : prev
    );
  };

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, retrieval_mode: retrievalMode }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Something went wrong");
      }
      const sessionData: Session = await res.json();
      setSession(sessionData);
      if (sessionData.suggestions.length === 0) {
        setError(
          "No suggestions generated. Try being more specific about what changed."
        );
      }
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to get suggestions"
      );
    } finally {
      setLoading(false);
    }
  }

  const handleSave = async () => {
    if (!session) return;
    setSaving(true);
    try {
      const res = await fetch(`/api/sessions/${session.session_id}/save`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        
        // Clear the session
        setSession(null);
        setError("");
        
        // Reload the current page to show updated content
        const currentPageToReload = currentPage;
        
        // Show success message
        alert(
          `Success! ${data.approved_count} approved suggestion(s) applied to docs_cache.json`
        );
        
        // Reload sections from the updated cache
        fetch(`/api/docs/${currentPageToReload}`)
          .then((r) => r.json())
          .then((data) => {
            setSections(data.sections ?? []);
          })
          .catch(console.error);
      }
    } catch (error) {
      console.error("Save failed:", error);
      setError("Failed to save changes");
    } finally {
      setSaving(false);
    }
  };

  // Group suggestions by page
  const byPage = session?.suggestions.reduce<
    Record<string, EditSuggestion[]>
  >((acc, s) => {
    (acc[s.file] ??= []).push(s);
    return acc;
  }, {}) ?? {};

  const pageSuggestions = session?.suggestions.filter(
    (s) => s.file === currentPage
  ) ?? [];

  const hasSession = !!session && session.suggestions.length > 0;

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Left Sidebar - Documentation Navigation */}
      <aside className="w-64 shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
            Documentation
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto py-3">
          <div className="px-3">
            {pages.map((page) => (
              <button
                key={page}
                onClick={() => setCurrentPage(page)}
                className={`w-full text-left px-3 py-2 rounded-lg mb-1 text-sm transition-colors ${
                  currentPage === page
                    ? "bg-blue-50 text-blue-700 font-medium"
                    : "text-gray-700 hover:bg-gray-50"
                }`}
              >
                {page}
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Documentation viewer */}
        <div className="flex-1 overflow-y-auto pb-32">
          <div className="max-w-4xl mx-auto px-8 py-8">
            {!hasSession && (
              <div className="text-center mb-8">
                <h1 className="text-4xl font-bold text-gray-900 mb-4">
                  OpenAI Agents SDK Documentation
                </h1>
                <p className="text-gray-600">
                  Browse the documentation or enter a query below to get AI-powered update suggestions
                </p>
              </div>
            )}

            {sections.map((section) => {
              const suggestion = pageSuggestions.find(
                (s) => s.section_title === section.section_title
              );
              return (
                <DocBlock
                  key={section.id}
                  section={section}
                  suggestion={suggestion}
                  sessionId={session?.session_id}
                  onUpdate={handleUpdate}
                />
              );
            })}
          </div>
        </div>

        {/* Floating query bar at bottom */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-50 w-full max-w-3xl px-4">
          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-2 bg-white/95 backdrop-blur-md border border-gray-300 rounded-xl shadow-2xl px-4 py-3"
          >
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder='What changed? e.g., "We removed support for agents.as_tool() method"'
              className="flex-1 text-sm bg-transparent focus:outline-none text-gray-800 placeholder:text-gray-400"
            />


            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="shrink-0 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {loading ? (
                <>
                  <svg
                    className="animate-spin h-4 w-4"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v8H4z"
                    />
                  </svg>
                  Analyzing…
                </>
              ) : (
                "Get Suggestions"
              )}
            </button>
          </form>

          {error && (
            <div className="mt-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
              {error}
            </div>
          )}
        </div>
      </main>

      {/* Right Sidebar - Suggestions (only when there are suggestions) */}
      {hasSession && (
        <aside className="w-80 shrink-0 bg-white border-l border-gray-200 flex flex-col">
          <div className="p-4 border-b border-gray-100">
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-2">
              Suggestions
            </h2>
            <p className="text-xs text-gray-600 leading-relaxed mb-2">
              &ldquo;{session.query}&rdquo;
            </p>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              session.retrieval_mode === "rag"
                ? "bg-purple-100 text-purple-700"
                : session.retrieval_mode === "hybrid"
                ? "bg-orange-100 text-orange-700"
                : session.retrieval_mode === "auto"
                ? "bg-green-100 text-green-700"
                : "bg-blue-100 text-blue-700"
            }`}>
              {session.retrieval_mode === "rag" ? "RAG" : session.retrieval_mode === "hybrid" ? "Hybrid" : session.retrieval_mode === "auto" ? "Auto" : "Triage"} mode
            </span>
          </div>

          <div className="flex-1 overflow-y-auto py-3">
            {Object.entries(byPage).map(([page, sugs]) => (
              <div key={page} className="mb-3 px-3">
                <p className="text-xs font-bold uppercase tracking-wider mb-2 px-1 text-gray-400">
                  {page}
                </p>
                {sugs.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      setCurrentPage(s.file);
                      setTimeout(
                        () =>
                          document
                            .getElementById(`sec-${s.id}`)
                            ?.scrollIntoView({
                              behavior: "smooth",
                              block: "center",
                            }),
                        200
                      );
                    }}
                    className="w-full text-left px-3 py-2 rounded-lg mb-1 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <span className="text-sm text-gray-700 font-medium line-clamp-2">
                        {s.section_title}
                      </span>
                      <Badge status={s.status} />
                    </div>
                    <p className="text-xs text-gray-500 line-clamp-2">
                      {s.reason}
                    </p>
                  </button>
                ))}
              </div>
            ))}
          </div>

          <div className="p-4 border-t border-gray-100 space-y-2">
            <button
              onClick={() => {
                setSession(null);
                setError("");
              }}
              className="w-full py-2 rounded-lg border border-gray-300 text-gray-700 text-sm font-medium hover:bg-gray-50 transition-colors"
            >
              Clear Suggestions
            </button>
            <button
              onClick={handleSave}
              disabled={saving || session.saved}
              className="w-full py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving…" : session.saved ? "Saved ✓" : "Save & Apply"}
            </button>
          </div>
        </aside>
      )}
    </div>
  );
}
