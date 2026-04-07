"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

/* ─── Types ─────────────────────────────────────────────────────────── */

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

/** A pipeline session returned by `POST /api/query`. */
interface Session {
  session_id: string;
  query: string;
  suggestions: EditSuggestion[];
  saved: boolean;
}

/** A single parsed section of a documentation page. */
interface DocSection {
  id: string;
  file: string;
  section_title: string;
  content: string;
  line_start: number;
  line_end: number;
}

/* ─── Status badge ───────────────────────────────────────────────────── */

/** Pill badge that colours itself based on suggestion status. */
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

/* ─── Inline suggestion panel ────────────────────────────────────────── */

/**
 * Inline card for a single suggestion with tab-based current/suggested view,
 * inline editing, and approve/reject actions.
 *
 * @param suggestion - The suggestion to display.
 * @param sessionId  - Parent session ID used when PATCHing the suggestion.
 * @param onUpdate   - Called with the locally-merged suggestion after a successful PATCH.
 */
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

  /** PATCH the suggestion and propagate the merged result via `onUpdate`. */
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
      ? "bg-red-50 opacity-70"
      : "bg-yellow-50";

  return (
    <div
      className={`my-4 rounded-lg border-l-4 ${borderColor} ${bgColor} p-4 shadow-sm`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          ✨ AI Suggestion
        </span>
        <Badge status={suggestion.status} />
      </div>

      <p className="text-sm text-gray-600 mb-3">
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
                className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                  tab === t
                    ? "bg-gray-900 text-white"
                    : "bg-white border border-gray-200 text-gray-500 hover:bg-gray-50"
                }`}
              >
                {t === "current" ? "Current" : "Suggested"}
              </button>
            ))}
          </div>
          <pre className="text-xs bg-white border border-gray-200 rounded p-3 overflow-auto max-h-52 whitespace-pre-wrap font-mono text-gray-700 leading-relaxed">
            {tab === "current"
              ? suggestion.current_content
              : suggestion.suggested_content}
          </pre>
        </>
      )}

      {editing && (
        <div className="mb-3">
          <p className="text-xs text-gray-500 mb-1 font-medium">
            Edit suggested content:
          </p>
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="w-full min-h-[140px] text-xs font-mono border border-blue-300 rounded p-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}

      <div className="flex gap-2 mt-3 flex-wrap">
        {editing ? (
          <>
            <button
              onClick={() => {
                setEditContent(suggestion.suggested_content);
                setEditing(false);
              }}
              className="px-3 py-1.5 text-xs rounded border border-gray-300 hover:bg-white"
            >
              Cancel
            </button>
            <button
              onClick={async () => {
                await patch({ suggested_content: editContent });
                setEditing(false);
              }}
              className="px-3 py-1.5 text-xs rounded bg-blue-600 text-white hover:bg-blue-700"
            >
              Save Edit
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => setEditing(true)}
              className="px-3 py-1.5 text-xs rounded border border-gray-300 hover:bg-white"
            >
              Edit
            </button>
            <button
              onClick={() => patch({ status: "rejected" })}
              disabled={suggestion.status === "rejected"}
              className="px-3 py-1.5 text-xs rounded border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-40"
            >
              Reject
            </button>
            <button
              onClick={() => patch({ status: "approved" })}
              disabled={suggestion.status === "approved"}
              className="px-3 py-1.5 text-xs rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-40"
            >
              Approve
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ─── Single doc section with optional suggestion ───────────────────── */

/**
 * Renders one documentation section.  When a `suggestion` is provided, the
 * section is highlighted by status and the `SuggestionPanel` is appended below.
 */
function DocBlock({
  section,
  suggestion,
  sessionId,
  onUpdate,
}: {
  section: DocSection;
  suggestion?: EditSuggestion;
  sessionId: string;
  onUpdate: (s: EditSuggestion) => void;
}) {
  const highlight = suggestion
    ? suggestion.status === "approved"
      ? "border-l-4 border-green-400 pl-4 bg-green-50/30"
      : suggestion.status === "rejected"
      ? "border-l-4 border-red-300 pl-4 bg-red-50/30 opacity-60"
      : "border-l-4 border-yellow-400 pl-4 bg-yellow-50/30"
    : "";

  return (
    <div
      className={`mb-6 ${highlight} py-2`}
      id={suggestion ? `sec-${suggestion.id}` : undefined}
    >
      <h3 className="text-lg font-semibold text-gray-900 mb-2">
        {section.section_title}
      </h3>
      <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
        {section.content}
      </pre>
      {suggestion && (
        <SuggestionPanel
          suggestion={suggestion}
          sessionId={sessionId}
          onUpdate={onUpdate}
        />
      )}
    </div>
  );
}

/* ─── Main editor ────────────────────────────────────────────────────── */

/**
 * Core editor view: sidebar navigation + scrollable doc viewer with inline
 * suggestion panels.  Loaded only after a valid `sessionId` is confirmed.
 *
 * @param sessionId - UUID of the session to load from `GET /api/sessions/:id`.
 */
function EditorInner({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [currentPage, setCurrentPage] = useState("");
  const [sections, setSections] = useState<DocSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  /* load session */
  useEffect(() => {
    fetch(`/api/sessions/${sessionId}`)
      .then((r) => r.json())
      .then((data: Session) => {
        setSession(data);
        if (data.suggestions.length > 0) setCurrentPage(data.suggestions[0].file);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [sessionId]);

  /* load page sections from docs_cache.json */
  useEffect(() => {
    if (!currentPage) return;
    fetch(`/api/docs/${currentPage}`)
      .then((r) => r.json())
      .then((data) => setSections(data.sections ?? []))
      .catch(() => setSections([]));
  }, [currentPage]);

  const handleUpdate = useCallback((updated: EditSuggestion) => {
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
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const res = await fetch(`/api/sessions/${sessionId}/save`, {
      method: "POST",
    });
    if (res.ok) {
      const data = await res.json();
      alert(
        `Saved! ${data.approved_count} approved suggestion(s) applied to docs_cache.json`
      );
      router.push("/saved");
    }
    setSaving(false);
  };

  if (loading)
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        Loading documentation…
      </div>
    );
  if (!session)
    return <div className="p-8 text-red-500">Session not found.</div>;

  /* group suggestions by page for sidebar */
  const byPage = session.suggestions.reduce<Record<string, EditSuggestion[]>>(
    (acc, s) => {
      (acc[s.file] ??= []).push(s);
      return acc;
    },
    {}
  );

  /* map suggestions to sections */
  const pageSuggestions = session.suggestions.filter(
    (s) => s.file === currentPage
  );

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* ── Sidebar ── */}
      <aside className="w-72 shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-100">
          <p className="text-xs text-gray-400 mb-1 font-medium uppercase tracking-wide">
            Query
          </p>
          <p className="text-sm text-gray-800 leading-snug">
            &ldquo;{session.query}&rdquo;
          </p>
        </div>

        <div className="flex-1 overflow-y-auto py-3">
          {Object.entries(byPage).map(([page, sugs]) => (
            <div key={page} className="mb-2 px-3">
              <p
                className={`text-xs font-bold uppercase tracking-wider mb-1 px-1 ${
                  currentPage === page ? "text-blue-600" : "text-gray-400"
                }`}
              >
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
                      400
                    );
                  }}
                  className="w-full text-left px-2 py-2 rounded-lg mb-0.5 flex items-center justify-between gap-2 hover:bg-gray-50 transition-colors"
                >
                  <span className="text-sm text-gray-700 truncate">
                    {s.section_title}
                  </span>
                  <Badge status={s.status} />
                </button>
              ))}
            </div>
          ))}
        </div>

        <div className="p-4 border-t border-gray-100">
          <button
            onClick={handleSave}
            disabled={saving || session.saved}
            className="w-full py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "Saving…" : session.saved ? "Saved ✓" : "Save & Apply"}
          </button>
        </div>
      </aside>

      {/* ── Doc viewer ── */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Page tabs */}
        <nav className="bg-white border-b border-gray-200 px-6 py-2 flex gap-2 overflow-x-auto shrink-0">
          {Object.keys(byPage).map((page) => (
            <button
              key={page}
              onClick={() => setCurrentPage(page)}
              className={`shrink-0 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                currentPage === page
                  ? "bg-blue-600 text-white"
                  : "text-gray-500 hover:text-gray-800 hover:bg-gray-100"
              }`}
            >
              {page}
            </button>
          ))}
        </nav>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-8 py-8">
            {sections.map((section) => {
              const suggestion = pageSuggestions.find(
                (s) => s.section_title === section.section_title
              );
              return (
                <DocBlock
                  key={section.id}
                  section={section}
                  suggestion={suggestion}
                  sessionId={sessionId}
                  onUpdate={handleUpdate}
                />
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}

/* ─── Page entry ─────────────────────────────────────────────────────── */

/**
 * Inner page component that reads the `session` query param and renders
 * `EditorInner`, or an error prompt when the param is missing.
 */
function EditorPageInner() {
  const params = useSearchParams();
  const sessionId = params.get("session");
  if (!sessionId)
    return (
      <div className="p-8 text-gray-500">
        No session ID.{" "}
        <a href="/" className="text-blue-600 underline">
          Start a new query
        </a>
        .
      </div>
    );
  return <EditorInner sessionId={sessionId} />;
}

/**
 * Next.js page component for `/editor`.  Wraps `EditorPageInner` in a
 * `Suspense` boundary to allow `useSearchParams` to work in streaming mode.
 */
export default function EditorPage() {
  return (
    <Suspense fallback={<div className="p-8 text-gray-400">Loading…</div>}>
      <EditorPageInner />
    </Suspense>
  );
}
