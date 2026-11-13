import type { Config } from "tailwindcss";

/**
 * Tailwind CSS Configuration mapped directly to Keelway DESIGN.md CSS variables.
 * Supports both Dark Mode (default) and Light Mode via [data-theme="light"].
 */
const config: Config = {
  darkMode: ["class", '[data-theme="dark"]'],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "sans-serif"],
        mono: [
          "var(--font-jetbrains-mono)",
          "ui-monospace",
          "SFMono-Regular",
          "monospace",
        ],
      },
      colors: {
        canvas: "var(--bg-canvas)",
        surface: {
          DEFAULT: "var(--bg-surface)",
          elevated: "var(--bg-surface-elevated)",
        },
        border: {
          subtle: "var(--border-subtle)",
          strong: "var(--border-strong)",
        },
        fg: {
          DEFAULT: "var(--fg-primary)",
          muted: "var(--fg-muted)",
          dim: "var(--fg-dim)",
        },
        teal: {
          accent: "var(--teal-accent)",
          surface: "var(--teal-surface)",
          ink: "var(--teal-ink)",
        },
        amber: {
          alert: "var(--amber-alert)",
          surface: "var(--amber-surface)",
          ink: "var(--amber-ink)",
        },
        fault: {
          DEFAULT: "var(--red-danger)",
          surface: "var(--red-surface)",
        },
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
      },
      maxWidth: {
        container: "1200px",
      },
    },
  },
  plugins: [],
};

export default config;
