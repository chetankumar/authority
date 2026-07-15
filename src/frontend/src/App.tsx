import { NavLink, Outlet, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getHealth } from "./api/health";

// Global shell (doc 06 §3): top bar + left nav + disconnected banner + outlet.
export default function App() {
  // Drives the "Backend not responding" banner. The backend is a local process
  // the author can kill by accident, so we name the fix rather than mystify.
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 5000,
  });
  const disconnected = health.isError;

  return (
    <div className="flex h-full flex-col bg-paper text-ink">
      <TopBar />
      {disconnected && (
        <div className="w-full bg-danger-wash px-6 py-2 text-[0.8125rem] text-danger">
          Backend not responding — check the terminal window.
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <LeftNav />
        <main className="min-w-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function TopBar() {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-surface px-6">
      <Link to="/" className="flex items-center gap-2 font-ui font-semibold text-ink">
        <span className="text-accent">◆</span>
        <span>Authority</span>
      </Link>
      <span className="text-[0.8125rem] text-ink-soft">Welcome</span>
    </header>
  );
}

function LeftNav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    [
      "block rounded-control px-3 py-1.5 text-[0.875rem]",
      isActive ? "bg-accent-wash text-accent" : "text-ink-soft hover:bg-accent-wash/60",
    ].join(" ");

  return (
    <nav className="w-52 shrink-0 border-r border-line bg-surface p-3">
      <ul className="space-y-1">
        <li>
          <NavLink to="/" end className={linkClass}>
            Home
          </NavLink>
        </li>
        <li>
          <NavLink to="/settings" className={linkClass}>
            Settings
          </NavLink>
        </li>
      </ul>
    </nav>
  );
}
