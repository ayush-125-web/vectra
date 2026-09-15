/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          900: '#0A0E14',
          800: '#0E131C',
          700: '#12161F',
          600: '#1A202C',
          500: '#232A38',
          400: '#3A4256',
        },
        signal: {
          green: '#4ADE80',
          amber: '#F5A623',
          red: '#EF4444',
          blue: '#4C8DFF',
        },
        ink: {
          100: '#E8EAED',
          300: '#B4BAC7',
          500: '#8B93A6',
          700: '#5B6376',
        }
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
}
