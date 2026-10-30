// Build: npx tailwindcss@3.4.17 -c core/studio/tailwind.config.js -i core/studio/tailwind.input.css -o core/studio/assets/studio.css --minify
module.exports = {
  content: [__dirname + '/index.html'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        obsidian: '#05070D',
        surface: '#0C101D',
        surfaceLight: '#141B2D',
        surfaceCard: '#1A233A',
        borderSubtle: '#1E293B',
        accentBlue: '#2563EB',
        accentCobalt: '#3B82F6',
        emeraldShield: '#10B981',
        amberGate: '#F59E0B',
        crimsonKill: '#EF4444',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
    },
  },
};
