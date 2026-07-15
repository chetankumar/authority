import { Link } from "react-router-dom";

// Unknown routes → friendly panel with a way back (doc 06 §2).
export default function NotFound() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="text-ink-soft">This page doesn&apos;t exist.</p>
      <Link
        to="/"
        className="rounded-control bg-accent px-3 py-1.5 text-[0.875rem] text-white"
      >
        Back to bookshelf
      </Link>
    </div>
  );
}
