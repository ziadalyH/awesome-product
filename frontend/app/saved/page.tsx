import Link from "next/link";

interface EditSuggestion {
  id: string;
  file: string;
  section_title: string;
  status: "pending" | "approved" | "rejected";
}

interface Session {
  session_id: string;
  query: string;
  suggestions: EditSuggestion[];
  created_at: string;
  saved: boolean;
}

async function getSessions(): Promise<Session[]> {
  try {
    const res = await fetch("http://localhost:8000/api/sessions", {
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function SavedPage() {
  const sessions = await getSessions();
  const saved = sessions.filter((s) => s.saved);

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Saved Results</h1>
        <p className="text-gray-500 text-sm">{saved.length} saved session{saved.length !== 1 ? "s" : ""}</p>
      </div>

      {saved.length === 0 && (
        <div className="rounded-lg bg-gray-100 border border-gray-200 px-6 py-10 text-center text-gray-500">
          No saved sessions yet.{" "}
          <Link href="/" className="text-blue-600 hover:underline">
            Start a new query
          </Link>
        </div>
      )}

      <div className="space-y-4">
        {saved.map((s) => {
          const approved = s.suggestions.filter((sg) => sg.status === "approved").length;
          const rejected = s.suggestions.filter((sg) => sg.status === "rejected").length;
          const pending = s.suggestions.filter((sg) => sg.status === "pending").length;

          return (
            <div
              key={s.session_id}
              className="rounded-xl border border-gray-200 bg-white shadow-sm p-5"
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <p className="font-medium text-gray-900 mb-1">&ldquo;{s.query}&rdquo;</p>
                  <p className="text-xs text-gray-400">
                    {new Date(s.created_at).toLocaleString()}
                  </p>
                </div>
                <Link
                  href={`/editor?session=${s.session_id}`}
                  className="shrink-0 text-sm px-3 py-1.5 rounded-md border border-gray-300 hover:bg-gray-50"
                >
                  View
                </Link>
              </div>
              <div className="flex gap-4 text-sm">
                <span className="text-gray-400">{s.suggestions.length} total</span>
                <span className="text-green-600">{approved} approved</span>
                <span className="text-red-500">{rejected} rejected</span>
                {pending > 0 && <span className="text-yellow-600">{pending} pending</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
