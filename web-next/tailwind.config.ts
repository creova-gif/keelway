import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)",
        surface: "var(--surface)",
        "surface-raised": "var(--surface-raised)",
        border: {
          DEFAULT: "var(--border-subtle)",
          strong: "var(--border-strong)",
        },
        fg: {
          DEFAULT: "var(--fg-primary)",
          muted: "var(--fg-muted)",
          dim: "var(--fg-dim)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          subtle: "var(--accent-subtle)",
          ink: "var(--accent-ink)",
        },
        ok: { DEFAULT: "var(--status-ok)", subtle: "var(--status-ok-subtle)", ink: "var(--status-ok-ink)" },
        warning: { DEFAULT: "var(--status-warning)", subtle: "var(--status-warning-subtle)" },
        danger: { DEFAULT: "var(--red-danger)", subtle: "var(--red-surface)", ink: "var(--red-ink)" },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jbmono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        xs: "2px",
        sm: "4px",
        md: "8px",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
