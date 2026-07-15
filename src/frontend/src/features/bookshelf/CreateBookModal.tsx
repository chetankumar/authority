import { useRef, useState } from "react";

import { ApiError } from "../../api/client";
import { createBook, type BookSummary } from "../../api/books";
import { Modal } from "../../components/Modal";
import { Button, Field, Input } from "../../components/ui";

export function CreateBookModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (book: BookSummary) => void;
}) {
  const [title, setTitle] = useState("");
  const [cover, setCover] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function pickCover(file: File | null) {
    setCover(file);
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old);
      return file ? URL.createObjectURL(file) : null;
    });
  }

  async function save() {
    if (!title.trim()) {
      setFields({ title: "Give the book a title." });
      return;
    }
    setSaving(true);
    setFields({});
    try {
      const book = await createBook(title.trim(), cover);
      if (preview) URL.revokeObjectURL(preview);
      onCreated(book);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const next = { ...err.fields };
        if (!next.title && !next._form) next._form = err.message;
        setFields(next);
      } else if (err instanceof ApiError) setFields({ _form: err.message });
      else setFields({ _form: "Couldn't create the book." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title="Create a book"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={save} disabled={saving}>
            {saving ? "Creating…" : "Create book"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {fields._form && <p className="text-[0.8125rem] text-danger">{fields._form}</p>}

        <Field label="Title" error={fields.title}>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="My Great Novel"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter" && !saving) save();
            }}
          />
        </Field>

        <Field label="Cover" hint="Optional. Travels with the book; you can change it later.">
          <div className="flex items-center gap-3">
            <div className="flex aspect-[3/4] w-20 items-center justify-center overflow-hidden rounded-control border border-line bg-paper">
              {preview ? (
                <img src={preview} alt="Cover preview" className="h-full w-full object-cover" />
              ) : (
                <span className="text-[0.6875rem] text-ink-faint">No cover</span>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => pickCover(e.target.files?.[0] ?? null)}
              />
              <Button variant="secondary" onClick={() => fileRef.current?.click()}>
                Choose image…
              </Button>
              {cover && (
                <Button variant="ghost" onClick={() => pickCover(null)}>
                  Remove
                </Button>
              )}
            </div>
          </div>
        </Field>
      </div>
    </Modal>
  );
}
