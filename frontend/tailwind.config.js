/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './pages/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        maple: {
          DEFAULT: '#C41E24',
          light: '#F9E8E8',
          dark: '#9B1820',
          50: '#FEF2F2',
        },
        slate: {
          50: '#F8FAFB',
          100: '#F0F3F5',
          200: '#E2E7EB',
          300: '#C8CED4',
          400: '#8C96A0',
          500: '#5E6B78',
          600: '#3F4C59',
          700: '#2C3640',
          800: '#1A2129',
          900: '#0D1117',
        },
        teal: {
          DEFAULT: '#1A8A7D',
          light: '#E6F5F3',
        },
      },
      fontFamily: {
        sans: ['DM Sans', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Playfair Display', 'Georgia', 'serif'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      spacing: {
        '18': '4.5rem',
      },
      maxWidth: {
        '8xl': '88rem',
      },
    },
  },
  plugins: [],
};
