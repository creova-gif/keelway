// Build: npx -y tailwindcss@3.4.17 -c core/studio/tailwind.config.js -i core/studio/tailwind.input.css -o core/studio/assets/studio.css --minify
module.exports = {
  content: [__dirname + '/index.html'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        ide: {
          bg: 'rgb(var(--ide-bg) / <alpha-value>)',
          sidebar: 'rgb(var(--ide-sidebar) / <alpha-value>)',
          activity: 'rgb(var(--ide-activity) / <alpha-value>)',
          editor: 'rgb(var(--ide-editor) / <alpha-value>)',
          panel: 'rgb(var(--ide-panel) / <alpha-value>)',
          status: 'rgb(var(--ide-status) / <alpha-value>)',
          border: 'rgb(var(--ide-border) / <alpha-value>)',
          tab: 'rgb(var(--ide-tab) / <alpha-value>)',
          fg: 'rgb(var(--ide-fg) / <alpha-value>)',
          muted: 'rgb(var(--ide-muted) / <alpha-value>)',
          faint: 'rgb(var(--ide-faint) / <alpha-value>)',
        },
        accent: 'rgb(var(--accent) / <alpha-value>)',
        ok: 'rgb(var(--ok) / <alpha-value>)',
        warn: 'rgb(var(--warn) / <alpha-value>)',
        danger: 'rgb(var(--danger) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', '"Segoe UI"', 'Roboto', '"Noto Sans"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', '"Cascadia Code"', '"JetBrains Mono"', 'Menlo', 'Consolas', '"Noto Sans Mono"', 'monospace'],
      },
    },
  },
};
