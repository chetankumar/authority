import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../api/client";
import { patchUser, type UserPatch } from "../../api/settings";
import { Button, Field, Input } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { keys } from "../../queries/keys";
import { useUser } from "../../queries/settings";

// User Settings (doc 06 §5.1): author name + books-home path. Save is the single
// primary button, disabled until dirty.
export default function UserSettingsPage() {
  const user = useUser();
  const qc = useQueryClient();
  const toast = useToast();

  const [name, setName] = useState("");
  const [booksHome, setBooksHome] = useState("");
  const [booksHomeError, setBooksHomeError] = useState<string | null>(null);
  const [offerCreate, setOfferCreate] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user.data) {
      setName(user.data.name ?? "");
      setBooksHome(user.data.booksHome ?? "");
    }
  }, [user.data]);

  const dirty =
    user.data != null &&
    (name !== (user.data.name ?? "") || booksHome !== (user.data.booksHome ?? ""));

  async function save(patch: UserPatch) {
    setSaving(true);
    setBooksHomeError(null);
    setOfferCreate(false);
    try {
      const updated = await patchUser(patch);
      qc.setQueryData(keys.settings("user"), updated);
      toast.success("Settings saved");
    } catch (err) {
      if (err instanceof ApiError) {
        const code = err.detail.code;
        if (err.status === 422 && code === "path-not-found") {
          setBooksHomeError("That folder doesn't exist yet.");
          setOfferCreate(true);
        } else if (err.status === 403) {
          setBooksHomeError("Not writable — pick another location.");
        } else {
          setBooksHomeError(err.fields.booksHome ?? err.message);
        }
      } else {
        toast.error("Couldn't save settings.");
      }
    } finally {
      setSaving(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    save({ name: name.trim() || null, booksHome: booksHome.trim() || null });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <Field label="Author name">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name"
        />
      </Field>

      <Field
        label="Books home"
        hint="Folder that will contain all your books"
        error={booksHomeError ?? undefined}
      >
        <Input
          value={booksHome}
          onChange={(e) => setBooksHome(e.target.value)}
          placeholder="C:\Users\you\Books"
        />
      </Field>

      {offerCreate && (
        <Button
          type="button"
          variant="secondary"
          onClick={() =>
            save({ name: name.trim() || null, booksHome: booksHome.trim(), createBooksHome: true })
          }
        >
          Create this folder
        </Button>
      )}

      <div>
        <Button type="submit" variant="primary" disabled={!dirty || saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </form>
  );
}
