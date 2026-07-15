// Bookshelf — the app home (doc 06 §4). Choose or create a book.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { coverUrl, type BookSummary } from "../../api/books";
import { ApiError } from "../../api/client";
import { useToast } from "../../components/Toast";
import { keys } from "../../queries/keys";
import { useBooks } from "../../queries/books";
import { CreateBookModal } from "./CreateBookModal";

export default function BookshelfPage() {
  const books = useBooks();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);

  const list = books.data ?? [];

  function onCreated(book: BookSummary) {
    setModalOpen(false);
    qc.invalidateQueries({ queryKey: keys.books });
    toast.success(`Created “${book.title}”`);
    navigate(`/book/${book.id}`);
  }

  const booksHomeUnset =
    books.isError &&
    books.error instanceof ApiError &&
    (books.error.detail?.code as string) === "books-home-unset";

  return (
    <div className="px-6 py-6">
      <div className="mb-6 flex items-baseline justify-between">
        <h1 className="text-[20px] font-semibold text-ink">Your books</h1>
      </div>

      {booksHomeUnset ? (
        <BooksHomeUnset />
      ) : books.isLoading ? (
        <p className="text-[0.875rem] text-ink-soft">Loading your shelf…</p>
      ) : books.isError ? (
        <p className="text-[0.875rem] text-danger">Couldn't load your books.</p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,180px)] gap-6">
          {list.map((book) => (
            <BookCard key={book.id} book={book} />
          ))}
          <AddBookCard onClick={() => setModalOpen(true)} />
          {list.length === 0 && (
            <p className="col-span-full mt-1 text-[0.875rem] text-ink-soft">
              Your shelf is empty. Create your first book to get started.
            </p>
          )}
        </div>
      )}

      {modalOpen && <CreateBookModal onClose={() => setModalOpen(false)} onCreated={onCreated} />}
    </div>
  );
}

function BookCard({ book }: { book: BookSummary }) {
  const [coverFailed, setCoverFailed] = useState(false);
  const showCover = book.hasCover && !coverFailed;

  const cover = (
    <div className="relative flex aspect-[3/4] items-center justify-center overflow-hidden rounded-card border border-line bg-surface shadow-sm">
      {book.error ? (
        <span className="px-3 text-center text-[0.75rem] text-danger">Couldn't read this book</span>
      ) : showCover ? (
        <img
          src={coverUrl(book.id)}
          alt={book.title}
          className="h-full w-full object-cover"
          onError={() => setCoverFailed(true)}
        />
      ) : (
        <span className="line-clamp-4 px-3 text-center font-prose text-[0.9375rem] text-ink">
          {book.title}
        </span>
      )}
    </div>
  );

  const label = (
    <span className="truncate text-[0.8125rem] text-ink" title={book.title}>
      {book.title}
    </span>
  );

  if (book.error) {
    return <div className="flex flex-col gap-2 opacity-80">{cover}{label}</div>;
  }

  return (
    <Link
      to={`/book/${book.id}`}
      className="group flex flex-col gap-2 outline-none focus-visible:opacity-80"
    >
      <div className="transition-transform group-hover:-translate-y-0.5">{cover}</div>
      {label}
    </Link>
  );
}

function AddBookCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex aspect-[3/4] flex-col items-center justify-center gap-3 rounded-card border border-dashed border-line bg-surface text-center transition-colors hover:border-accent hover:bg-accent-wash/40"
    >
      <span className="text-2xl text-ink-faint">+</span>
      <span className="text-[0.875rem] text-ink-soft">Add book</span>
    </button>
  );
}

function BooksHomeUnset() {
  return (
    <div className="rounded-card border border-dashed border-line bg-surface p-6 text-[0.875rem] text-ink-soft">
      Set your books folder in{" "}
      <a href="/settings/user" className="text-accent hover:underline">
        Settings → User
      </a>{" "}
      before creating a book.
    </div>
  );
}
