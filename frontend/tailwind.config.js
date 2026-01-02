/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Cisco Magnetic / Meraki style colors
        primary: {
          DEFAULT: '#00bceb',
          50: '#e6f9ff',
          100: '#ccf3ff',
          200: '#99e7ff',
          300: '#66dbff',
          400: '#33cfff',
          500: '#00bceb',
          600: '#0096bc',
          700: '#00718d',
          800: '#004b5e',
          900: '#00262f',
        },
        surface: {
          DEFAULT: '#252542',
          50: '#f5f5f7',
          100: '#e8e8ed',
          200: '#d1d1db',
          300: '#a0a0b0',
          400: '#6b6b80',
          500: '#4a4a60',
          600: '#353550',
          700: '#252542',
          800: '#1a1a2e',
          900: '#0f0f1a',
        },
        success: '#6cc04a',
        warning: '#ffcc00',
        error: '#cf2030',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        'magnetic': '8px',
      },
    },
  },
  plugins: [],
}
