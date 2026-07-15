/** @type {import('tailwindcss').Config} */
// Tailwind maps to the design tokens in src/styles/tokens.css — components
// reference these names, never raw hex (doc 06 §1.2).
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "var(--paper)",
        surface: "var(--surface)",
        ink: {
          DEFAULT: "var(--ink)",
          soft: "var(--ink-soft)",
          faint: "var(--ink-faint)",
        },
        line: "var(--line)",
        accent: {
          DEFAULT: "var(--accent)",
          wash: "var(--accent-wash)",
        },
        attn: {
          DEFAULT: "var(--attn)",
          wash: "var(--attn-wash)",
        },
        ok: {
          DEFAULT: "var(--ok)",
          wash: "var(--ok-wash)",
        },
        danger: {
          DEFAULT: "var(--danger)",
          wash: "var(--danger-wash)",
        },
      },
      fontFamily: {
        prose: ["Literata", "Georgia", "serif"],
        ui: ["Inter", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        control: "6px",
        card: "10px",
      },
      boxShadow: {
        overlay: "0 8px 24px rgb(0 0 0 / 0.10)",
      },
    },
  },
  plugins: [],
};
