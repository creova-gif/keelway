import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";

const config: Config = {
  darkMode: ["class", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      fontSize: {
        ui: ["var(--font-size-ui)", { lineHeight: "var(--line-height-ui)" }],
        code: ["var(--font-size-code)", { lineHeight: "1.25rem" }],
        badge: ["0.6875rem", { lineHeight: "0.875rem", letterSpacing: "0.02em" }],
      },
      colors: {
        canvas: "var(--bg-canvas)",
        chrome: "var(--bg-chrome)",
        code: "var(--bg-code)",
        surface: {
          DEFAULT: "var(--bg-surface)",
          elevated: "var(--bg-surface-elevated)",
        },
        border: {
          DEFAULT: "var(--border-subtle)",
          strong: "var(--border-strong)",
          control: "var(--border-control)",
          focus: "var(--border-focus)",
        },
        fg: {
          DEFAULT: "var(--fg-primary)",
          muted: "var(--fg-muted)",
          dim: "var(--fg-dim)",
          disabled: "var(--fg-disabled)",
        },
        teal: {
          accent: "var(--teal-accent)",
          ink: "var(--teal-ink)",
          surface: "var(--teal-surface)",
        },
        ok: {
          DEFAULT: "var(--status-ok)",
          subtle: "var(--status-ok-subtle)",
          ink: "var(--status-ok-ink)",
        },
        ochre: {
          DEFAULT: "var(--attn-ochre)",
          subtle: "var(--attn-ochre-subtle)",
          ink: "var(--attn-ochre-ink)",
        },
        warning: {
          DEFAULT: "var(--status-warning)",
          subtle: "var(--status-warning-subtle)",
          ink: "var(--status-warning-ink)",
        },
        running: {
          DEFAULT: "var(--status-running)",
          subtle: "var(--status-running-subtle)",
        },
        danger: {
          DEFAULT: "var(--red-danger)",
          subtle: "var(--red-surface)",
          ink: "var(--red-ink)",
        },
      },
      height: {
        row: "var(--row-h)",
        "task-row": "var(--task-row-h)",
        "table-row": "var(--table-row-h)",
        "ctrl-sm": "var(--control-h-sm)",
        "ctrl-md": "var(--control-h-md)",
        statusbar: "var(--shell-statusbar-h)",
      },
      minHeight: {
        row: "var(--row-h)",
        "task-row": "var(--task-row-h)",
        "table-row": "var(--table-row-h)",
        "ctrl-sm": "var(--control-h-sm)",
        "ctrl-md": "var(--control-h-md)",
        statusbar: "var(--shell-statusbar-h)",
      },
      width: {
        rail: "var(--shell-rail-w)",
        sidebar: "var(--shell-sidebar-w)",
        review: "var(--shell-review-w)",
        inspector: "var(--shell-inspector-w)",
      },
      maxWidth: {
        rail: "var(--shell-rail-w)",
        sidebar: "var(--shell-sidebar-w)",
        review: "var(--shell-review-w)",
        inspector: "var(--shell-inspector-w)",
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
      },
      boxShadow: {
        popover: "var(--shadow-popover)",
        modal: "var(--shadow-modal)",
      },
    },
  },
  plugins: [
    plugin(({ addVariant }) => {
      addVariant("compact", '[data-density="compact"] &');
      addVariant("comfortable", '[data-density="comfortable"] &');
    }),
  ],
};

export default config;
