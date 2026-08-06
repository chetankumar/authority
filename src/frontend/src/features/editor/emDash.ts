import { Extension, textInputRule } from "@tiptap/core";

/** Typing `--` inserts an em dash (U+2014) — writer-style, TipTap Typography subset. */
export const EmDash = Extension.create({
  name: "emDash",

  addInputRules() {
    return [
      textInputRule({
        find: /--$/,
        replace: "—",
      }),
    ];
  },
});

/**
 * If the caret sits just after `--` in a textarea value, replace with `—`
 * and return the new caret index; otherwise return null (no change).
 */
export function applyEmDashInSource(
  value: string,
  caret: number,
): { value: string; caret: number } | null {
  if (caret < 2 || value.slice(caret - 2, caret) !== "--") return null;
  return {
    value: value.slice(0, caret - 2) + "—" + value.slice(caret),
    caret: caret - 1,
  };
}
