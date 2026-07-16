// Book home (doc 08 J7): the landing when you enter a book. This first
// increment renders the book context (cover, title, summary, structure counts)
// and the workspace sections. Section pages (Scenes/Metadata/Tasks/Git/Compile)
// arrive in their own phases; they show here as upcoming entry points.
import { Link, useParams } from "react-router-dom";

import { coverUrl } from "../../api/books";
import { ApiError } from "../../api/client";
import { useBook } from "../../queries/books";

interface Section {
  key: string;
  label: string;
  description: string;
  icon: string;
  /** Relative path (under /book/:id) when the section is live; absent → "soon". */
  path?: string;
}

const SECTIONS: Section[] = [
  { key: "graph", label: "Scene Graph", description: "See the story's shape", icon: "◇", path: "graph" },
  { key: "table", label: "Scene Table", description: "The working ledger of scenes", icon: "▤", path: "table" },
  { key: "metadata", label: "Metadata", description: "Parts, chapters, plotlines & summary", icon: "❏", path: "metadata" },
  { key: "characters", label: "Characters", description: "The cast and their details", icon: "☺" },
  { key: "tasks", label: "Tasks", description: "To-dos across the book", icon: "✓" },
  { key: "notes", label: "Notes", description: "Conversations & AI chats", icon: "✎" },
  { key: "git", label: "Version control", description: "Stage, diff & commit changes", icon: "⎇" },
  { key: "compile", label: "Compile", description: "Readiness check & build", icon: "⇩" },
];

export default function BookPage() {
  const { bookId = "" } = useParams();
  const book = useBook(bookId);

  if (book.isLoading) {
    return <div className="px-6 py-6 text-[0.875rem] text-ink-soft">Opening the book…</div>;
  }

  if (book.isError) {
    const notFound = book.error instanceof ApiError && book.error.status === 404;
    return (
      <div className="px-6 py-6">
        <p className="text-[0.875rem] text-danger">
          {notFound ? "That book couldn't be found." : "Couldn't open this book."}
        </p>
        <Link to="/" className="mt-2 inline-block text-[0.8125rem] text-accent hover:underline">
          ← Back to your books
        </Link>
      </div>
    );
  }

  const data = book.data!;
  const partCount = data.parts.length;
  const chapterCount = data.chapters.length;

  return (
    <div className="px-6 py-6">
      <Link to="/" className="mb-4 inline-block text-[0.8125rem] text-ink-soft hover:text-ink">
        ← All books
      </Link>

      <header className="flex gap-5">
        <div className="flex aspect-[3/4] w-28 shrink-0 items-center justify-center overflow-hidden rounded-card border border-line bg-surface shadow-sm">
          {data.hasCover ? (
            <img src={coverUrl(data.id)} alt={data.title} className="h-full w-full object-cover" />
          ) : (
            <span className="line-clamp-4 px-2 text-center font-prose text-[0.8125rem] text-ink">
              {data.title}
            </span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <h1 className="font-prose text-[1.75rem] leading-tight text-ink">{data.title}</h1>
          <p className="mt-2 max-w-2xl text-[0.875rem] text-ink-soft">
            {data.storySummary || "No story summary yet."}
          </p>
          <div className="mt-3 flex gap-4 text-[0.8125rem] text-ink-faint">
            <span>{partCount} {partCount === 1 ? "part" : "parts"}</span>
            <span>{chapterCount} {chapterCount === 1 ? "chapter" : "chapters"}</span>
          </div>
        </div>
      </header>

      <section className="mt-8">
        <h2 className="mb-3 text-[0.75rem] uppercase tracking-[0.04em] text-ink-faint">Workspace</h2>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
          {SECTIONS.map((s) => {
            const inner = (
              <>
                <span className="text-lg text-accent">{s.icon}</span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[0.875rem] font-medium text-ink">{s.label}</span>
                    {!s.path && (
                      <span className="rounded-full bg-accent-wash px-1.5 py-0.5 text-[0.625rem] text-accent">
                        soon
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-[0.75rem] text-ink-soft">{s.description}</p>
                </div>
              </>
            );
            return s.path ? (
              <Link
                key={s.key}
                to={`/book/${data.id}/${s.path}`}
                className="flex items-start gap-3 rounded-card border border-line bg-surface p-4 transition-colors hover:border-accent"
              >
                {inner}
              </Link>
            ) : (
              <div
                key={s.key}
                className="flex items-start gap-3 rounded-card border border-line bg-surface p-4 opacity-70"
                title="Coming soon"
              >
                {inner}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
