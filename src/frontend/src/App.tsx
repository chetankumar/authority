import { NavLink, Outlet, Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getHealth } from "./api/health";
import { useUser } from "./queries/settings";
import { useBook } from "./queries/books";
import { useGitStatus } from "./queries/git";
import { useBookEvents } from "./events/useBookEvents";
import { useTheme } from "./theme";
import type { ThemePref } from "./api/settings";

// Global shell (doc 06 §3): top bar + left nav + disconnected banner + outlet.
export default function App() {
  const location = useLocation();
  const bookId = matchBookId(location.pathname);
  const isEditor = /\/scene\//.test(location.pathname);

  // Drives the "Backend not responding" banner. The backend is a local process
  // the author can kill by accident, so we name the fix rather than mystify.
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 5000 });
  const disconnected = health.isError;

  // One event channel per open book; feeds the git badge (doc 06 §2).
  useBookEvents(bookId);

  return (
    <div className="flex h-full flex-col bg-paper text-ink">
      <TopBar bookId={bookId} />
      {disconnected && (
        <div className="w-full bg-danger-wash px-6 py-2 text-[0.8125rem] text-danger">
          Backend not responding — check the terminal window.
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <LeftNav bookId={bookId} collapsed={isEditor} />
        <main className="min-w-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function matchBookId(pathname: string): string | null {
  const m = pathname.match(/^\/book\/([^/]+)/);
  return m ? m[1] : null;
}

function TopBar({ bookId }: { bookId: string | null }) {
  const user = useUser();
  const greeting = user.data?.name ? `Welcome, ${user.data.name}` : "Welcome";
  const book = useBook(bookId ?? "");
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-surface px-6">
      <div className="flex items-center gap-2 font-ui text-ink">
        <Link to="/" className="flex items-center gap-2 font-semibold">
          <img src="/authority-logo.png" alt="Authority" className="h-7 w-7 rounded-full" />
          <span>Authority</span>
        </Link>
        {bookId && book.data && (
          <>
            <span className="text-ink-faint">›</span>
            <Link to={`/book/${bookId}`} className="max-w-xs truncate text-ink-soft hover:text-ink">
              {book.data.title}
            </Link>
          </>
        )}
      </div>
      <div className="flex items-center gap-3">
        {bookId && <GitBadge bookId={bookId} />}
        <ThemeToggle />
        <span className="text-[0.8125rem] text-ink-soft">{greeting}</span>
      </div>
    </header>
  );
}

// The nudge that makes deliberate commits happen without auto-commit (doc 06 §3).
// Amber means a decision awaits. Clean → renders nothing, so the chrome stays
// quiet until there's genuinely something to save.
//
// Kept current by two paths on purpose (doc 07 §25–28): `git-status` over SSE
// (instant after an explicit commit, ~5s after the author stops typing), and a
// 10s poll inside useGitStatus underneath it. A badge that lies is worse than
// no badge, so the poll stays even though the event is the fast path.
function GitBadge({ bookId }: { bookId: string }) {
  const status = useGitStatus(bookId);
  if (!status.data?.dirty) return null;
  return (
    <Link
      to={`/book/${bookId}/git`}
      className="rounded-control bg-attn-wash px-2 py-1 text-[0.75rem] text-attn hover:opacity-90"
    >
      {status.data.summary} · Commit now?
    </Link>
  );
}

// Cycles the app-wide theme light → dark → system. The icon reflects the
// *preference*; "system" shows a half-moon to signal "follow the OS".
const THEME_CYCLE: Record<ThemePref, ThemePref> = { light: "dark", dark: "system", system: "light" };
const THEME_ICON: Record<ThemePref, string> = { light: "☀", dark: "☾", system: "◐" };
const THEME_LABEL: Record<ThemePref, string> = {
  light: "Light theme",
  dark: "Dark theme",
  system: "System theme",
};

function ThemeToggle() {
  const { pref, setTheme } = useTheme();
  return (
    <button
      onClick={() => setTheme(THEME_CYCLE[pref])}
      title={`${THEME_LABEL[pref]} — click to change`}
      aria-label={`${THEME_LABEL[pref]} (click to change)`}
      className="flex h-7 w-7 items-center justify-center rounded-control text-ink-soft hover:bg-accent-wash"
    >
      <span className="text-[0.9375rem]">{THEME_ICON[pref]}</span>
    </button>
  );
}

interface NavItem {
  to: string;
  label: string;
  icon: string;
  soon?: boolean;
  end?: boolean;
}

function LeftNav({ bookId, collapsed }: { bookId: string | null; collapsed: boolean }) {
  const items: NavItem[] = bookId
    ? [
        { to: `/book/${bookId}`, label: "Overview", icon: "▢", end: true },
        { to: `/book/${bookId}/graph`, label: "Scene Graph", icon: "◇" },
        { to: `/book/${bookId}/table`, label: "Scene Table", icon: "▤" },
        { to: `/book/${bookId}/characters`, label: "Character Sheet", icon: "☺" },
        { to: `/book/${bookId}/metadata`, label: "Metadata", icon: "❏" },
        { to: `/book/${bookId}/tasks`, label: "Tasks", icon: "✓", soon: true },
        { to: `/book/${bookId}/git`, label: "Version control", icon: "⎇" },
      ]
    : [];

  const width = collapsed ? "w-14" : "w-52";

  return (
    <nav className={`${width} shrink-0 border-r border-line bg-surface p-3 transition-[width] duration-150`}>
      {bookId ? (
        <ul className="space-y-1">
          {items.map((it) => (
            <li key={it.to}>
              {it.soon ? (
                <span
                  title="Arrives in a later phase"
                  className={`flex items-center gap-2 rounded-control px-3 py-1.5 text-[0.875rem] text-ink-faint ${collapsed ? "justify-center px-0" : ""}`}
                >
                  <span>{it.icon}</span>
                  {!collapsed && (
                    <span className="flex-1">
                      {it.label} <span className="text-[0.625rem]">soon</span>
                    </span>
                  )}
                </span>
              ) : (
                <NavLink to={it.to} end={it.end} title={collapsed ? it.label : undefined} className={navClass(collapsed)}>
                  <span>{it.icon}</span>
                  {!collapsed && <span>{it.label}</span>}
                </NavLink>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <ul className="space-y-1">
          <li>
            <NavLink to="/" end className={navClass(false)}>
              Home
            </NavLink>
          </li>
          <li>
            <NavLink to="/settings" className={navClass(false)}>
              Settings
            </NavLink>
            <ul className="ml-3 mt-1 space-y-0.5 border-l border-line pl-2">
              <li>
                <NavLink to="/settings/user" className={subNavClass}>
                  User
                </NavLink>
              </li>
              <li>
                <NavLink to="/settings/ai" className={subNavClass}>
                  AI
                </NavLink>
              </li>
              <li>
                <NavLink to="/settings/ai-jobs" className={subNavClass}>
                  AI-Jobs
                </NavLink>
              </li>
            </ul>
          </li>
        </ul>
      )}
    </nav>
  );
}

const navClass = (collapsed: boolean) => ({ isActive }: { isActive: boolean }) =>
  [
    "flex items-center gap-2 rounded-control px-3 py-1.5 text-[0.875rem]",
    collapsed ? "justify-center px-0" : "",
    isActive ? "bg-accent-wash text-accent" : "text-ink-soft hover:bg-accent-wash/60",
  ].join(" ");

const subNavClass = ({ isActive }: { isActive: boolean }) =>
  [
    "block rounded-control px-3 py-1 text-[0.8125rem]",
    isActive ? "text-accent" : "text-ink-soft hover:text-ink",
  ].join(" ");
