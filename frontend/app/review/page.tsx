"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

/** Approval lifecycle state of a suggestion. */
type SuggestionStatus = "pending" | "approved" | "rejected";

/** An AI-generated proposal to update a single documentation section. */
interface EditSuggestion {
  id: string;
  file: string;
  section_title: string;
  current_content: string;
  suggested_content: string;
  reason: string;
  status: SuggestionStatus;
}

/** A pipeline session loaded from `GET /api/sessions/:id`. */
interface Session {
  session_id: string;
  query: string;
  suggestions: EditSuggestion[];
  created_at: string;
  saved: boolean;
}

/**
 * Full-page review view for a single session.  Displays a side-by-side diff
 * for each suggestion and provides approve/reject/edit/save actions.
 */
function ReviewContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const sessionId = searchParams.get("session");

  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  useEffect(() => {
    if (!sessionId) {
      setError("No session ID provided");
      setLoading(false);
      return;
    }
    fetch(`/api/sessions/${sessionId}`)
      .then((r) => r.json())
      .then((data) => {
        setSession(data);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load session");
        setLoading(false);
      });
  }, [sessionId]);

  /**
   * PATCH a suggestion and merge the server response into local session state.
   *
   * @param suggestionId - ID of the suggestion to update.
   * @param patch        - Partial update payload (status and/or suggested_content).
   */
  async function updateSuggestion(
    suggestionId: string,
    patch: { status?: SuggestionStatus; suggested_content?: string }
  ) {
    const res = await fetch(
      `/api/sessions/${sessionId}/suggestions/${suggestionId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      }
    );
    if (!res.ok) return;
    const updated = await res.json();
    setSession((prev) =>
      prev
        ? {
            ...prev,
            suggestions: prev.suggestions.map((s) =>
              s.id === suggestionId ? { ...s, ...updated } : s
            ),
          }
        : prev
    );
  }

  /** Enter inline-edit mode for the given suggestion. */
  function startEdit(suggestion: EditSuggestion) {
    setEditingId(suggestion.id);
    setEditContent(suggestion.suggested_content);
  }

  /** Save the in-progress edit and exit inline-edit mode. */
  async function submitEdit(suggestionId: string) {
    await updateSuggestion(suggestionId, { suggested_content: editContent });
    setEditingId(null);
  }

  /** Apply approved suggestions to the server and navigate to `/saved`. */
  async function handleSave() {
    setSaving(true);
    const res = await fetch(`/api/sessions/${sessionId}/save`, { method: "POST" });
    if (res.ok) {
      router.push("/saved");
    }
    setSaving(false);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        Loading suggestions…
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-red-700">
        {error || "Session not found"}
      </div>
    );
  }

  const pending = session.suggestions.filter((s) => s.status === "pending").length;
  const approved = session.suggestions.filter((s) => s.status === "approved").length;
  const rejected = session.suggestions.filter((s) => s.status === "rejected").length;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1">Review Suggestions</h1>
        <p className="text-gray-500 text-sm">Query: &ldquo;{session.query}&rdquo;</p>
        <div className="flex gap-4 mt-3 text-sm">
          <span className="text-gray-500">{pending} pending</span>
          <span className="text-green-600">{approved} approved</span>
          <span className="text-red-500">{rejected} rejected</span>
        </div>
      </div>

      {session.suggestions.length === 0 && (
        <div className="rounded-lg bg-yellow-50 border border-yellow-200 px-4 py-6 text-center text-yellow-700">
          No suggestions were generated for this query. The documentation may already be up to date.
        </div>
      )}

      <div className="space-y-6">
        {session.suggestions.map((s) => (
          <div
            key={s.id}
            className={`rounded-xl border bg-white shadow-sm overflow-hidden ${
              s.status === "approved"
                ? "border-green-300"
                : s.status === "rejected"
                ? "border-red-300 opacity-60"
                : "border-gray-200"
            }`}
          >
            {/* Header */}
            <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-mono text-gray-500">{s.file}</p>
                <p className="font-semibold text-gray-800">{s.section_title}</p>
              </div>
              <StatusBadge status={s.status} />
            </div>

            {/* Reason */}
            <div className="px-5 py-3 bg-blue-50 border-b border-blue-100 text-sm text-blue-700">
              <strong>Why: </strong>{s.reason}
            </div>

            {/* Diff view */}
            <div className="grid grid-cols-2 divide-x divide-gray-200">
              <div className="p-4">
                <p className="text-xs font-semibold text-gray-400 uppercase mb-2">Current</p>
                <pre className="text-xs text-gray-600 whitespace-pre-wrap font-mono leading-relaxed">
                  {s.current_content}
                </pre>
              </div>
              <div className="p-4">
                <p className="text-xs font-semibold text-green-600 uppercase mb-2">Suggested</p>
                {editingId === s.id ? (
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={12}
                    className="w-full text-xs font-mono border border-gray-300 rounded p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                ) : (
                  <pre className="text-xs text-gray-800 whitespace-pre-wrap font-mono leading-relaxed">
                    {s.suggested_content}
                  </pre>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="px-5 py-3 border-t border-gray-100 flex gap-2 justify-end">
              {editingId === s.id ? (
                <>
                  <button
                    onClick={() => setEditingId(null)}
                    className="px-3 py-1.5 text-sm rounded-md border border-gray-300 hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => submitEdit(s.id)}
                    className="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700"
                  >
                    Save Edit
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => startEdit(s)}
                    className="px-3 py-1.5 text-sm rounded-md border border-gray-300 hover:bg-gray-50"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => updateSuggestion(s.id, { status: "rejected" })}
                    disabled={s.status === "rejected"}
                    className="px-3 py-1.5 text-sm rounded-md border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-40"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => updateSuggestion(s.id, { status: "approved" })}
                    disabled={s.status === "approved"}
                    className="px-3 py-1.5 text-sm rounded-md bg-green-600 text-white hover:bg-green-700 disabled:opacity-40"
                  >
                    Approve
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {session.suggestions.length > 0 && (
        <div className="mt-8 flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving || session.saved}
            className="px-6 py-3 rounded-lg bg-gray-900 text-white font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "Saving…" : session.saved ? "Already Saved" : "Save Results"}
          </button>
        </div>
      )}
    </div>
  );
}

/** Pill badge for suggestion status used in the review card header. */
function StatusBadge({ status }: { status: SuggestionStatus }) {
  const styles: Record<SuggestionStatus, string> = {
    pending: "bg-yellow-100 text-yellow-700",
    approved: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-600",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[status]}`}>
      {status}
    </span>
  );
}

/**
 * Next.js page component for `/review`.  Wraps `ReviewContent` in a
 * `Suspense` boundary so `useSearchParams` works in streaming mode.
 */
export default function ReviewPage() {
  return (
    <Suspense fallback={<div className="py-20 text-center text-gray-500">Loading…</div>}>
      <ReviewContent />
    </Suspense>
  );
}
