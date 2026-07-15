// Theme controller (doc 06 §1.2). The stored *preference* is light|dark|system;
// the applied `data-theme` on <html> is only ever light|dark (system resolves via
// the OS). app.json is the source of truth; a localStorage hint mirrors it so the
// pre-paint script in index.html can avoid a flash on startup.
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getAppearance, patchAppearance, type ThemePref } from "./api/settings";
import { keys } from "./queries/keys";

const HINT_KEY = "authority-theme";

export function resolveTheme(pref: ThemePref): "light" | "dark" {
  if (pref === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return pref;
}

export function applyTheme(pref: ThemePref): void {
  document.documentElement.setAttribute("data-theme", resolveTheme(pref));
  try {
    localStorage.setItem(HINT_KEY, pref);
  } catch {
    /* private mode / disabled storage — the server value still governs */
  }
}

function storedHint(): ThemePref {
  try {
    const v = localStorage.getItem(HINT_KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* ignore */
  }
  return "system";
}

/** App-wide theme state: reads the authoritative value, applies it, follows the OS
 *  while in `system`, and persists changes. Mount once (in the app shell). */
export function useTheme(): { pref: ThemePref; setTheme: (next: ThemePref) => void } {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: keys.settings("appearance"), queryFn: getAppearance });
  const pref: ThemePref = data?.theme ?? storedHint();

  // Apply whenever the resolved preference changes (server load, toggle).
  useEffect(() => {
    applyTheme(pref);
  }, [pref]);

  // Live-follow the OS while the preference is `system`.
  useEffect(() => {
    if (pref !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [pref]);

  const mutation = useMutation({
    mutationFn: (next: ThemePref) => patchAppearance(next),
    onMutate: (next) => applyTheme(next), // optimistic — the switch feels instant
    onSuccess: (res) => qc.setQueryData(keys.settings("appearance"), res),
  });

  return { pref, setTheme: (next) => mutation.mutate(next) };
}
