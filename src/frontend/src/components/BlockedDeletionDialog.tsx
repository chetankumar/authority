import { Modal } from "./Modal";
import { Button } from "./ui";

export interface BlockedRef {
  label: string;
  onNavigate?: () => void;
}

// Shared blocked-deletion dialog (doc 06 §1.5), driven by any 409 blockedBy.
// Danger-tinted title; each referencing item is a link to its fix location.
export function BlockedDeletionDialog({
  name,
  refs,
  onClose,
}: {
  name: string;
  refs: BlockedRef[];
  onClose: () => void;
}) {
  return (
    <Modal
      title={`Can't delete ${name} yet`}
      onClose={onClose}
      footer={<Button variant="secondary" onClick={onClose}>Close</Button>}
    >
      <p className="mb-3 text-[0.875rem] text-ink-soft">
        It's still referenced here. Unassign it in these places first:
      </p>
      <ul className="space-y-1">
        {refs.map((r, i) => (
          <li key={i}>
            {r.onNavigate ? (
              <button onClick={r.onNavigate} className="text-[0.875rem] text-accent hover:underline">
                {r.label}
              </button>
            ) : (
              <span className="text-[0.875rem] text-ink">{r.label}</span>
            )}
          </li>
        ))}
      </ul>
    </Modal>
  );
}
