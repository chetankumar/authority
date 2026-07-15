// Bookshelf — the app home (doc 06 §4). Choose or create a book.
// Skeleton phase: the shelf template + empty state. The books API and the
// Add/Edit Book modals arrive in the Bookshelf build phase.
export default function BookshelfPage() {
  const books: unknown[] = [];

  return (
    <div className="px-6 py-6">
      <div className="mb-6 flex items-baseline justify-between">
        <h1 className="text-[20px] font-semibold text-ink">Your books</h1>
      </div>

      {books.length === 0 ? (
        <EmptyShelf />
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,200px)] gap-6" />
      )}
    </div>
  );
}

function EmptyShelf() {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,200px)] gap-6">
      <div className="flex flex-col items-center justify-center gap-3 rounded-card border border-dashed border-line bg-surface p-4 text-center aspect-[3/4]">
        <span className="text-2xl text-ink-faint">+</span>
        <span className="text-[0.875rem] text-ink-soft">Add book</span>
      </div>
      <p className="col-span-full mt-2 text-[0.875rem] text-ink-soft">
        Your shelf is empty. Create your first book to get started.
      </p>
    </div>
  );
}
