import { useState } from "react";
import { useParams } from "react-router-dom";

import type { GitFile } from "../../api/git";
import { ApiError } from "../../api/client";
import {
  useCommitStaged,
  useGitDiff,
  useGitLog,
  useGitStatus,
  useRemoteOp,
  useStageFiles,
  useSuggestCommitMessage,
  useUnstageFiles,
} from "../../queries/git";
import { useToast } from "../../components/Toast";
import { Button } from "../../components/ui";

// The letter git itself would show — the author's existing vocabulary.
const STATUS_LETTER: Record<GitFile["status"], string> = {
  modified: "M",
  added: "A",
  deleted: "D",
  untracked: "?",
  renamed: "R",
};

export default function GitPage() {
  const { bookId = "" } = useParams();
  const toast = useToast();

  const status = useGitStatus(bookId);
  const log = useGitLog(bookId);
  const [selected, setSelected] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [fromStats, setFromStats] = useState(false);
  const [remoteError, setRemoteError] = useState<string | null>(null);

  const diff = useGitDiff(bookId, selected);
  const stage = useStageFiles(bookId);
  const unstage = useUnstageFiles(bookId);
  const commit = useCommitStaged(bookId);
  const suggest = useSuggestCommitMessage(bookId);
  const push = useRemoteOp(bookId, "push");
  const pull = useRemoteOp(bookId, "pull");

  const files = status.data?.files ?? [];
  const stagedCount = files.filter((f) => f.staged).length;
  const canCommit = stagedCount > 0 && message.trim().length > 0 && !commit.isPending;

  const toggleStage = (file: GitFile) => {
    const body = { paths: [file.path] };
    (file.staged ? unstage : stage).mutate(body, {
      onError: (err) => toast.error(err instanceof ApiError ? err.message : "Couldn't update staging."),
    });
  };

  const onSuggest = () =>
    suggest.mutate(undefined, {
      onSuccess: (res) => {
        setMessage(res.message);
        setFromStats(res.fromStats);
      },
      onError: (err) =>
        toast.error(err instanceof ApiError ? err.message : "Couldn't suggest a message."),
    });

  const onCommit = () =>
    commit.mutate(message.trim(), {
      onSuccess: (info) => {
        toast.success(`Committed ${info.hash.slice(0, 7)}`);
        setMessage("");
        setFromStats(false);
        setSelected(null);
        log.refetch();
      },
      onError: (err) => toast.error(err instanceof ApiError ? err.message : "Couldn't commit."),
    });

  const onRemote = (op: "push" | "pull") => {
    setRemoteError(null);
    const m = op === "push" ? push : pull;
    m.mutate(undefined, {
      onSuccess: (res) => {
        toast.success(res.summary || `${op === "push" ? "Pushed" : "Pulled"}`);
        log.refetch();
      },
      onError: (err) => {
        // Git's own words, verbatim — Authority hands off rather than pretending
        // to resolve anything (doc 04 §13).
        const detail = err instanceof ApiError ? (err.detail.gitError as string) : null;
        setRemoteError(detail || (err instanceof Error ? err.message : `Couldn't ${op}.`));
      },
    });
  };

  if (status.isError) {
    const err = status.error;
    const missingRepo = err instanceof ApiError && err.status === 404;
    return (
      <div className="p-8">
        <h1 className="mb-2 font-ui text-lg text-ink">Version control</h1>
        <p className="text-[0.875rem] text-ink-soft">
          {missingRepo
            ? "This book folder has no git repository, so there's no history to show."
            : "Couldn't read this book's git status."}
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      {/* Left: what changed, what to say about it, what happened before. */}
      <div className="flex min-h-0 w-[60%] flex-col overflow-auto border-r border-line p-6">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-baseline gap-3">
            <h1 className="font-ui text-lg text-ink">Version control</h1>
            {status.data?.branch && (
              // Which branch, and where it stands against the remote. Authority
              // doesn't manage branches (doc 07 §6) — but it should never leave
              // the author guessing which one they're committing to.
              <span className="flex items-baseline gap-2 text-[0.75rem]">
                <span className="font-mono text-ink-soft">⎇ {status.data.branch}</span>
                {status.data.hasRemote && (status.data.ahead > 0 || status.data.behind > 0) && (
                  <span className="text-attn">
                    {status.data.ahead > 0 && `${status.data.ahead} to push`}
                    {status.data.ahead > 0 && status.data.behind > 0 && " · "}
                    {status.data.behind > 0 && `${status.data.behind} to pull`}
                  </span>
                )}
                {status.data.hasRemote && status.data.ahead === 0 && status.data.behind === 0 && (
                  <span className="text-ink-faint">in sync with origin</span>
                )}
                {!status.data.hasRemote && <span className="text-ink-faint">no remote</span>}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {status.data?.hasRemote && (
              <>
                <Button onClick={() => onRemote("pull")} disabled={pull.isPending}>
                  {pull.isPending ? "Pulling…" : `Pull ↓${status.data.behind}`}
                </Button>
                <Button onClick={() => onRemote("push")} disabled={push.isPending}>
                  {push.isPending ? "Pushing…" : `Push ↑${status.data.ahead}`}
                </Button>
              </>
            )}
            {files.length > 0 && (
              <Button
                onClick={() => stage.mutate({ all: true })}
                disabled={stage.isPending}
              >
                Stage all
              </Button>
            )}
          </div>
        </div>

        {remoteError && (
          <div className="mb-4 rounded-control bg-danger-wash p-3 text-[0.8125rem] text-danger">
            <pre className="whitespace-pre-wrap font-mono text-[0.75rem]">{remoteError}</pre>
            <p className="mt-2">Resolve with your git tooling.</p>
          </div>
        )}

        {files.length === 0 ? (
          <p className="text-[0.875rem] text-ink-soft">
            Nothing has changed since your last commit. Everything is saved.
          </p>
        ) : (
          <ul className="mb-6 divide-y divide-line border-y border-line">
            {files.map((file) => (
              <li key={file.path}>
                <div
                  className={`flex cursor-pointer items-center gap-3 px-2 py-1.5 text-[0.8125rem] hover:bg-accent-wash/60 ${
                    selected === file.path ? "bg-accent-wash" : ""
                  }`}
                  onClick={() => setSelected(file.path)}
                >
                  <input
                    type="checkbox"
                    checked={file.staged}
                    onChange={() => toggleStage(file)}
                    onClick={(e) => e.stopPropagation()}
                    aria-label={file.staged ? `Unstage ${file.path}` : `Stage ${file.path}`}
                  />
                  <span className="w-4 font-mono text-ink-faint">{STATUS_LETTER[file.status]}</span>
                  <span className="truncate font-mono text-ink">{file.path}</span>
                </div>
              </li>
            ))}
          </ul>
        )}

        <div className="mb-6">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-[0.75rem] tracking-[0.02em] text-ink-soft">Commit message</span>
            <Button variant="ghost" onClick={onSuggest} disabled={suggest.isPending || stagedCount === 0}>
              {suggest.isPending ? "Writing…" : "✨ Suggest message"}
            </Button>
          </div>
          <textarea
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              setFromStats(false);
            }}
            rows={3}
            placeholder="What changed, and why?"
            className="w-full rounded-control border border-line bg-surface p-2 text-[0.875rem] text-ink outline-none focus:border-accent"
          />
          {fromStats && (
            <p className="mt-1 text-[0.75rem] text-ink-faint">Written from file stats</p>
          )}
          <div className="mt-2 flex justify-end">
            <Button variant="primary" onClick={onCommit} disabled={!canCommit}>
              {commit.isPending ? "Committing…" : "Commit staged files"}
            </Button>
          </div>
        </div>

        <div>
          <h2 className="mb-2 text-[0.75rem] tracking-[0.02em] text-ink-soft">Recent commits</h2>
          {log.data && log.data.length > 0 ? (
            <ul className="space-y-1">
              {log.data.map((c) => (
                <li key={c.hash} className="flex items-baseline gap-2 text-[0.8125rem]">
                  <span className="font-mono text-ink-faint">{c.hash.slice(0, 7)}</span>
                  <span className="min-w-0 flex-1 truncate text-ink">{c.message}</span>
                  <span className="shrink-0 text-ink-faint">{relativeTime(c.timestamp)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[0.8125rem] text-ink-faint">No commits yet.</p>
          )}
        </div>
      </div>

      {/* Right: read-only review. Fixing happens in the editor, not here. */}
      <div className="min-h-0 w-[40%] overflow-auto bg-surface p-4">
        {!selected ? (
          <p className="text-[0.875rem] text-ink-faint">Select a file to see its changes</p>
        ) : diff.isLoading ? (
          <p className="text-[0.875rem] text-ink-faint">Loading diff…</p>
        ) : diff.data?.binary ? (
          <p className="text-[0.875rem] text-ink-soft">Binary file</p>
        ) : (
          <pre className="overflow-x-auto font-mono text-[0.75rem] leading-relaxed">
            {(diff.data?.diff ?? "").split("\n").map((line, i) => (
              <div key={i} className={diffLineClass(line)}>
                {line || " "}
              </div>
            ))}
          </pre>
        )}
      </div>
    </div>
  );
}

function diffLineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) return "text-ink-faint";
  if (line.startsWith("+")) return "text-ok";
  if (line.startsWith("-")) return "text-danger";
  if (line.startsWith("@@")) return "text-accent";
  return "text-ink-soft";
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}
