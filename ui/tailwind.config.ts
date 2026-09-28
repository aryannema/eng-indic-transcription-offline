import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'Arial', 'Helvetica', 'sans-serif'],
      },
      colors: {
        vigyan: {
          bg:       '#0b0c10',
          card:     '#1a1c23',
          border:   '#2a2d3a',
          text:     '#c5c6c7',
          amber:    '#fbbf24',   // amber-400 — matches vigyanbytes brand
          'amber-dim': '#d97706',
          ok:       '#34d399',
          warn:     '#fbbf24',
          crit:     '#f87171',
        },
      },
    },
  },
  plugins: [],
}

export default config
