import { NavLink, Outlet } from "react-router-dom";

// Settings shell (doc 06 §5): three pages sharing a centered column, with tabs.
const tabs = [
  { to: "user", label: "User" },
  { to: "ai", label: "AI" },
  { to: "ai-jobs", label: "AI-Jobs" },
];

export default function SettingsLayout() {
  return (
    <div className="mx-auto max-w-[640px] px-6 py-6">
      <h1 className="mb-4 text-[20px] font-semibold text-ink">Settings</h1>
      <div className="mb-6 flex gap-1 border-b border-line">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) =>
              [
                "-mb-px border-b-2 px-3 py-2 text-[0.875rem]",
                isActive ? "border-accent text-accent" : "border-transparent text-ink-soft hover:text-ink",
              ].join(" ")
            }
          >
            {t.label}
          </NavLink>
        ))}
      </div>
      <Outlet />
    </div>
  );
}
